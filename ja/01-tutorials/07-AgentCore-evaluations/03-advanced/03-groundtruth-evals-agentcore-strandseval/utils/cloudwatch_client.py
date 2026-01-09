"""CloudWatch Logs からオブザーバビリティデータをクエリするクライアント。"""

import logging
import time
from typing import List

import boto3

from datetime import datetime, timezone
from typing import Optional

from .models import RuntimeLog, SessionInfo, Span, TraceData


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

    @staticmethod
    def build_discover_sessions_query() -> str:
        """時間ウィンドウ内でユニークなセッション ID を検出するクエリを構築します。

        Returns:
            スパン数と時間範囲を含むユニークなセッション ID を返す
            CloudWatch Logs Insights クエリ文字列
        """
        return """fields @timestamp, attributes.session.id as sessionId, traceId
        | filter ispresent(attributes.session.id)
        | stats count(*) as spanCount,
                min(@timestamp) as firstSeen,
                max(@timestamp) as lastSeen,
                count_distinct(traceId) as traceCount
          by sessionId
        | sort lastSeen desc"""

    @staticmethod
    def build_sessions_by_score_query(
        evaluator_name: str,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> str:
        """結果ロググループから評価スコアでセッションを検索するクエリを構築します。

        Args:
            evaluator_name: 評価器の名前（例: "Custom.StrandsEvalOfflineTravelEvaluator"）
            min_score: 最小スコアしきい値（以上）
            max_score: 最大スコアしきい値（以下）

        Returns:
            CloudWatch Logs Insights クエリ文字列
        """
        # Build score filter conditions
        score_filters = []
        if min_score is not None:
            score_filters.append(f"`{evaluator_name}` >= {min_score}")
        if max_score is not None:
            score_filters.append(f"`{evaluator_name}` <= {max_score}")

        score_filter_clause = ""
        if score_filters:
            score_filter_clause = "| filter " + " and ".join(score_filters)

        return f"""fields @timestamp,
               attributes.session.id as sessionId,
               attributes.gen_ai.response.id as traceId,
               `{evaluator_name}` as score,
               label
        | filter ispresent(`{evaluator_name}`)
        {score_filter_clause}
        | stats count(*) as evalCount,
                avg(score) as avgScore,
                min(score) as minScore,
                max(score) as maxScore,
                min(@timestamp) as firstEval,
                max(@timestamp) as lastEval
          by sessionId
        | sort avgScore asc"""


class ObservabilityClient:
    """CloudWatch Logs からスパンとランタイムログをクエリするクライアント。"""

    QUERY_TIMEOUT_SECONDS = 60
    POLL_INTERVAL_SECONDS = 2

    def __init__(
        self,
        region_name: str,
        log_group: str,
        agent_id: str = None,
        runtime_suffix: str = "DEFAULT",
    ):
        """ObservabilityClient を初期化します。

        Args:
            region_name: AWS リージョン名
            log_group: スパン/トレース用の CloudWatch ロググループ名
            agent_id: オプションのエージェント ID（現在フィルタリングには使用されていません）
            runtime_suffix: ロググループのランタイムサフィックス（デフォルト: DEFAULT）
        """
        self.region = region_name
        self.log_group = log_group
        self.agent_id = agent_id
        self.runtime_suffix = runtime_suffix

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
        self.logger.info("セッション %s のスパンをクエリ中、ロググループ: %s", session_id, self.log_group)

        query_string = self.query_builder.build_spans_by_session_query(session_id)

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=self.log_group,
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
                log_group_name=self.log_group,
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

    def discover_sessions(
        self,
        start_time_ms: int,
        end_time_ms: int,
        limit: int = 100,
    ) -> List[SessionInfo]:
        """時間ウィンドウ内でユニークなセッション ID を検出します。

        Args:
            start_time_ms: エポックからのミリ秒単位の開始時刻
            end_time_ms: エポックからのミリ秒単位の終了時刻
            limit: 返すセッションの最大数（デフォルト: 100）

        Returns:
            セッションメタデータを含む SessionInfo オブジェクトのリスト
        """
        self.logger.info(
            "ロググループ %s でセッションを検索中: %s から %s まで",
            self.log_group,
            datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc),
            datetime.fromtimestamp(end_time_ms / 1000, tz=timezone.utc),
        )

        query_string = self.query_builder.build_discover_sessions_query()

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=self.log_group,
            start_time=start_time_ms,
            end_time=end_time_ms,
        )

        sessions = []
        for result in results[:limit]:
            session_info = self._parse_session_discovery_result(result)
            if session_info:
                session_info.discovery_method = "time_based"
                sessions.append(session_info)

        self.logger.info("%d 個のセッションを検出しました", len(sessions))
        return sessions

    def discover_sessions_by_score(
        self,
        evaluation_log_group: str,
        evaluator_name: str,
        start_time_ms: int,
        end_time_ms: int,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        limit: int = 100,
    ) -> List[SessionInfo]:
        """評価結果ロググループから評価スコアでセッションを検出します。

        Args:
            evaluation_log_group: 評価結果を含むロググループ
            evaluator_name: フィルタリングする評価器の名前
            start_time_ms: エポックからのミリ秒単位の開始時刻
            end_time_ms: エポックからのミリ秒単位の終了時刻
            min_score: 最小スコアしきい値（以上）
            max_score: 最大スコアしきい値（以下）
            limit: 返すセッションの最大数（デフォルト: 100）

        Returns:
            セッションメタデータとスコア情報を含む SessionInfo オブジェクトのリスト
        """
        self.logger.info(
            "ロググループ %s でスコアによるセッションを検索中 (評価器: %s、スコア範囲: %s-%s)",
            evaluation_log_group,
            evaluator_name,
            min_score,
            max_score,
        )

        query_string = self.query_builder.build_sessions_by_score_query(
            evaluator_name=evaluator_name,
            min_score=min_score,
            max_score=max_score,
        )

        results = self._execute_cloudwatch_query(
            query_string=query_string,
            log_group_name=evaluation_log_group,
            start_time=start_time_ms,
            end_time=end_time_ms,
        )

        sessions = []
        for result in results[:limit]:
            session_info = self._parse_score_discovery_result(result)
            if session_info:
                session_info.discovery_method = "score_based"
                sessions.append(session_info)

        self.logger.info("スコアベースで %d 個のセッションを検出しました", len(sessions))
        return sessions

    def _parse_session_discovery_result(self, result) -> Optional[SessionInfo]:
        """時間ベースの検出用に CloudWatch の結果を SessionInfo に解析します。"""
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default=None):
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        session_id = get_field("sessionId")
        if not session_id:
            return None

        span_count_str = get_field("spanCount", "0")
        trace_count_str = get_field("traceCount")
        first_seen_str = get_field("firstSeen")
        last_seen_str = get_field("lastSeen")

        # Parse counts
        try:
            span_count = int(float(span_count_str))
        except (ValueError, TypeError):
            span_count = 0

        trace_count = None
        if trace_count_str:
            try:
                trace_count = int(float(trace_count_str))
            except (ValueError, TypeError):
                pass

        # Parse timestamps - require valid timestamps, don't fallback to now()
        first_seen = None
        last_seen = None
        if first_seen_str:
            try:
                first_seen = datetime.fromisoformat(first_seen_str.replace("Z", "+00:00"))
                # Ensure timezone-aware
                if first_seen.tzinfo is None:
                    first_seen = first_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"first_seen '{first_seen_str}' の解析に失敗しました: {e}")
        if last_seen_str:
            try:
                last_seen = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                # Ensure timezone-aware
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"last_seen '{last_seen_str}' の解析に失敗しました: {e}")

        # Skip sessions with missing timestamps
        if first_seen is None or last_seen is None:
            self.logger.warning(f"セッション {session_id} にタイムスタンプがありません。スキップします")
            return None

        return SessionInfo(
            session_id=session_id,
            span_count=span_count,
            first_seen=first_seen,
            last_seen=last_seen,
            trace_count=trace_count,
        )

    def _parse_score_discovery_result(self, result) -> Optional[SessionInfo]:
        """スコアベースの検出用に CloudWatch の結果を SessionInfo に解析します。

        注意: スコアベースの検出では、span_count は評価数を表します
        （このセッションで見つかった評価の数であり、トレースからのスパン数ではありません）。
        明確にするため、実際の eval_count はメタデータにも格納されます。
        """
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default=None):
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        session_id = get_field("sessionId")
        if not session_id:
            return None

        eval_count_str = get_field("evalCount", "0")
        avg_score_str = get_field("avgScore", "0")
        min_score_str = get_field("minScore", "0")
        max_score_str = get_field("maxScore", "0")
        first_eval_str = get_field("firstEval")
        last_eval_str = get_field("lastEval")

        # Parse counts and scores
        try:
            eval_count = int(float(eval_count_str))
        except (ValueError, TypeError):
            eval_count = 0

        try:
            avg_score = float(avg_score_str)
        except (ValueError, TypeError):
            avg_score = 0.0

        try:
            min_score = float(min_score_str)
        except (ValueError, TypeError):
            min_score = 0.0

        try:
            max_score = float(max_score_str)
        except (ValueError, TypeError):
            max_score = 0.0

        # Parse timestamps - require valid timestamps, don't fallback to now()
        first_seen = None
        last_seen = None
        if first_eval_str:
            try:
                first_seen = datetime.fromisoformat(first_eval_str.replace("Z", "+00:00"))
                # Ensure timezone-aware
                if first_seen.tzinfo is None:
                    first_seen = first_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"first_eval '{first_eval_str}' の解析に失敗しました: {e}")
        if last_eval_str:
            try:
                last_seen = datetime.fromisoformat(last_eval_str.replace("Z", "+00:00"))
                # Ensure timezone-aware
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"last_eval '{last_eval_str}' の解析に失敗しました: {e}")

        # Skip sessions with missing timestamps
        if first_seen is None or last_seen is None:
            self.logger.warning(f"セッション {session_id} にタイムスタンプがありません。スキップします")
            return None

        return SessionInfo(
            session_id=session_id,
            span_count=eval_count,  # For score-based: eval_count (see docstring)
            first_seen=first_seen,
            last_seen=last_seen,
            metadata={
                "avg_score": avg_score,
                "min_score": min_score,
                "max_score": max_score,
                "eval_count": eval_count,
            },
        )

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
