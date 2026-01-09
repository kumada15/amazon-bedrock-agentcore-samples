"""CloudWatch Logs からオブザーバビリティデータをクエリするクライアント。"""

import logging
import time
from typing import List

import boto3

from .models import RuntimeLog, Span, TraceData


class CloudWatchQueryBuilder:
    """CloudWatch Logs Insights クエリのビルダー。"""

    @staticmethod
    def build_spans_by_session_query(session_id: str, agent_id: str = None) -> str:
        """aws/spans ロググループからセッションの全スパンを取得するクエリを構築します。

        Args:
            session_id: フィルタリングするセッション ID
            agent_id: フィルタリングするオプションのエージェント ID

        Returns:
            CloudWatch Logs Insights クエリ文字列
        """
        base_filter = f"attributes.session.id = '{session_id}'"

        if agent_id:
            parse_and_filter = f"""| parse resource.attributes.cloud.resource_id "runtime/*/" as parsedAgentId
        | filter parsedAgentId = '{agent_id}'"""
        else:
            parse_and_filter = ""

        return f"""fields @timestamp,
               @message,
               traceId,
               spanId,
               name as spanName,
               kind,
               status.code as statusCode,
               status.message as statusMessage,
               durationNano/1000000 as durationMs,
               attributes.session.id as sessionId,
               startTimeUnixNano,
               endTimeUnixNano,
               parentSpanId,
               events,
               resource.attributes.service.name as serviceName,
               resource.attributes.cloud.resource_id as resourceId,
               attributes.aws.remote.service as serviceType
        | filter {base_filter}
        {parse_and_filter}
        | sort startTimeUnixNano asc"""

    @staticmethod
    def build_runtime_logs_by_traces_batch(trace_ids: List[str]) -> str:
        """複数のトレースのランタイムログを1つのクエリで取得する最適化されたクエリを構築します。

        Args:
            trace_ids: フィルタリングするトレース ID のリスト

        Returns:
            CloudWatch Logs Insights クエリ文字列
        """
        if not trace_ids:
            return ""

        trace_ids_quoted = ", ".join([f"'{tid}'" for tid in trace_ids])

        return f"""fields @timestamp, @message, spanId, traceId, @logStream
        | filter traceId in [{trace_ids_quoted}]
        | sort @timestamp asc"""

    @staticmethod
    def build_runtime_logs_by_trace_direct(trace_id: str) -> str:
        """トレースのランタイムログを取得するクエリを構築します。

        Args:
            trace_id: フィルタリングするトレース ID

        Returns:
            CloudWatch Logs Insights クエリ文字列
        """
        return f"""fields @timestamp, @message, spanId, traceId, @logStream
        | filter traceId = '{trace_id}'
        | sort @timestamp asc"""


class ObservabilityClient:
    """CloudWatch Logs からスパンとランタイムログをクエリするクライアント。"""

    SPANS_LOG_GROUP = "aws/spans"
    QUERY_TIMEOUT_SECONDS = 60
    POLL_INTERVAL_SECONDS = 2

    def __init__(
        self,
        region_name: str,
        agent_id: str,
        runtime_suffix: str = "DEFAULT",
    ):
        """ObservabilityClient を初期化します。

        Args:
            region_name: AWS リージョン名
            agent_id: エージェント固有のログをクエリするためのエージェント ID
            runtime_suffix: ロググループのランタイムサフィックス（デフォルト: DEFAULT）
        """
        self.region = region_name
        self.agent_id = agent_id
        self.runtime_suffix = runtime_suffix
        self.runtime_log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-{runtime_suffix}"

        self.logs_client = boto3.client("logs", region_name=region_name)
        self.query_builder = CloudWatchQueryBuilder()

        self.logger = logging.getLogger("cloudwatch_client")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def query_spans_by_session(
        self,
        session_id: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[Span]:
        """aws/spans ロググループからセッションの全スパンをクエリします。

        Args:
            session_id: クエリするセッション ID
            start_time_ms: エポックからのミリ秒単位の開始時刻
            end_time_ms: エポックからのミリ秒単位の終了時刻

        Returns:
            Span オブジェクトのリスト
        """
        self.logger.info("セッション %s のスパンをクエリ中 (エージェント: %s)", session_id, self.agent_id)

        query_string = self.query_builder.build_spans_by_session_query(session_id, agent_id=self.agent_id)

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=self.SPANS_LOG_GROUP,
            start_time=start_time_ms,
            end_time=end_time_ms,
        )

        spans = [Span.from_cloudwatch_result(result) for result in results]
        self.logger.info("セッション %s で %d 個のスパンを検出しました", session_id, len(spans))

        return spans

    def query_runtime_logs_by_traces(
        self,
        trace_ids: List[str],
        start_time_ms: int,
        end_time_ms: int,
    ) -> List[RuntimeLog]:
        """エージェント固有のロググループから複数のトレースのランタイムログをクエリします。

        Args:
            trace_ids: クエリするトレース ID のリスト
            start_time_ms: エポックからのミリ秒単位の開始時刻
            end_time_ms: エポックからのミリ秒単位の終了時刻

        Returns:
            RuntimeLog オブジェクトのリスト
        """
        if not trace_ids:
            return []

        self.logger.info("%d 個のトレースのランタイムログをクエリ中", len(trace_ids))

        query_string = self.query_builder.build_runtime_logs_by_traces_batch(trace_ids)

        try:
            results = self._execute_cloudwatch_query(
                query_string=query_string,
                log_group_name=self.runtime_log_group,
                start_time=start_time_ms,
                end_time=end_time_ms,
            )

            logs = [RuntimeLog.from_cloudwatch_result(result) for result in results]
            self.logger.info("%d 個のトレースから %d 個のランタイムログを検出しました", len(trace_ids), len(logs))
            return logs

        except Exception as e:
            self.logger.error("ランタイムログのクエリに失敗しました: %s", str(e))
            return []

    def get_session_data(
        self,
        session_id: str,
        start_time_ms: int,
        end_time_ms: int,
        include_runtime_logs: bool = True,
    ) -> TraceData:
        """スパンとオプションでランタイムログを含む完全なセッションデータを取得します。

        Args:
            session_id: クエリするセッション ID
            start_time_ms: エポックからのミリ秒単位の開始時刻
            end_time_ms: エポックからのミリ秒単位の終了時刻
            include_runtime_logs: ランタイムログを取得するかどうか（デフォルト: True）

        Returns:
            スパンとランタイムログを含む TraceData オブジェクト
        """
        self.logger.info("セッション %s のデータを取得中", session_id)

        spans = self.query_spans_by_session(session_id, start_time_ms, end_time_ms)

        session_data = TraceData(
            session_id=session_id,
            spans=spans,
        )

        if include_runtime_logs:
            trace_ids = session_data.get_trace_ids()
            if trace_ids:
                runtime_logs = self.query_runtime_logs_by_traces(trace_ids, start_time_ms, end_time_ms)
                session_data.runtime_logs = runtime_logs

        self.logger.info(
            "セッションデータを取得しました: スパン %d 個、トレース %d 個、ランタイムログ %d 個",
            len(session_data.spans),
            len(session_data.get_trace_ids()),
            len(session_data.runtime_logs),
        )

        return session_data

    def _execute_cloudwatch_query(
        self,
        query_string: str,
        log_group_name: str,
        start_time: int,
        end_time: int,
    ) -> list:
        """CloudWatch Logs Insights クエリを実行し、結果を待機します。

        Args:
            query_string: CloudWatch Logs Insights クエリ
            log_group_name: クエリするロググループ
            start_time: エポックからのミリ秒単位の開始時刻
            end_time: エポックからのミリ秒単位の終了時刻

        Returns:
            結果辞書のリスト

        Raises:
            TimeoutError: タイムアウト内にクエリが完了しない場合
            Exception: クエリが失敗した場合
        """
        self.logger.debug("ロググループ %s で CloudWatch クエリを開始", log_group_name)

        try:
            response = self.logs_client.start_query(
                logGroupName=log_group_name,
                startTime=start_time // 1000,
                endTime=end_time // 1000,
                queryString=query_string,
            )
        except self.logs_client.exceptions.ResourceNotFoundException as e:
            self.logger.error("ロググループが見つかりません: %s", log_group_name)
            raise Exception(f"Log group not found: {log_group_name}") from e

        query_id = response["queryId"]
        self.logger.debug("クエリ ID %s で開始しました", query_id)

        start_poll_time = time.time()
        while True:
            elapsed = time.time() - start_poll_time
            if elapsed > self.QUERY_TIMEOUT_SECONDS:
                raise TimeoutError(f"Query {query_id} timed out after {self.QUERY_TIMEOUT_SECONDS} seconds")

            result = self.logs_client.get_query_results(queryId=query_id)
            status = result["status"]

            if status == "Complete":
                results = result.get("results", [])
                self.logger.debug("クエリが完了しました。結果: %d 件", len(results))
                return results
            elif status == "Failed" or status == "Cancelled":
                raise Exception(f"Query {query_id} failed with status: {status}")

            time.sleep(self.POLL_INTERVAL_SECONDS)
