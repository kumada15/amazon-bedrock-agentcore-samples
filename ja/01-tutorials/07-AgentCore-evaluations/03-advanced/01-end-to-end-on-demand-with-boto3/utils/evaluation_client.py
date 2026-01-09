"""AgentCore Evaluation DataPlane API のクライアント。"""

import json
import os
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from .cloudwatch_client import ObservabilityClient
from .constants import (
    DASHBOARD_DATA_FILE,
    DASHBOARD_HTML_FILE,
    DEFAULT_FILE_ENCODING,
    DEFAULT_MAX_EVALUATION_ITEMS,
    DEFAULT_RUNTIME_SUFFIX,
    EVALUATION_OUTPUT_DIR,
    EVALUATION_OUTPUT_PATTERN,
    SESSION_SCOPED_EVALUATORS,
    SPAN_SCOPED_EVALUATORS,
)
from .models import EvaluationRequest, EvaluationResult, EvaluationResults, TraceData


class EvaluationClient:
    """AgentCore Evaluation Data Plane API のクライアント。"""

    DEFAULT_REGION = "us-east-1"

    def __init__(
        self, region: Optional[str] = None, boto_client: Optional[Any] = None
    ):
        """評価クライアントを初期化します。

        Args:
            region: AWS リージョン（環境変数または us-east-1 がデフォルト）
            boto_client: テスト用のオプションの事前設定された boto3 クライアント
        """
        self.region = region or os.getenv("AGENTCORE_EVAL_REGION", self.DEFAULT_REGION)
        
        if boto_client:
            self.client = boto_client
        else:
            self.client = boto3.client(
                "agentcore-evaluation-dataplane", region_name=self.region
            )

    def _validate_scope_compatibility(self, evaluator_id: str, scope: str) -> None:
        """評価器が要求されたスコープと互換性があることを検証します。

        Args:
            evaluator_id: 評価器識別子
            scope: 評価スコープ（"session"、"trace"、または "span"）

        Raises:
            ValueError: 評価器とスコープの組み合わせが無効な場合
        """
        if scope == "span":
            if evaluator_id not in SPAN_SCOPED_EVALUATORS:
                raise ValueError(
                    f"{evaluator_id} cannot use span scope. "
                    f"Only {SPAN_SCOPED_EVALUATORS} support span-level evaluation."
                )

        elif scope == "trace":
            if evaluator_id in SESSION_SCOPED_EVALUATORS:
                raise ValueError(f"{evaluator_id} requires session scope (cannot use trace scope)")
            if evaluator_id in SPAN_SCOPED_EVALUATORS:
                raise ValueError(f"{evaluator_id} requires span scope (cannot use trace scope)")

        elif scope == "session":
            if evaluator_id in SPAN_SCOPED_EVALUATORS:
                raise ValueError(f"{evaluator_id} requires span scope (cannot use session scope)")

        else:
            raise ValueError(f"Invalid scope: {scope}. Must be 'session', 'trace', or 'span'")

    def _build_evaluation_target(
        self, scope: str, trace_id: Optional[str] = None, span_ids: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """スコープに基づいて evaluationTarget を構築します。

        Args:
            scope: 評価スコープ（"session"、"trace"、または "span"）
            trace_id: trace スコープ用のトレース ID
            span_ids: span スコープ用のスパン ID のリスト

        Returns:
            evaluationTarget 辞書、またはセッションスコープの場合は None

        Raises:
            ValueError: スコープに必要な ID が不足している場合
        """
        if scope == "session":
            return None

        elif scope == "trace":
            if not trace_id:
                raise ValueError("trace_id is required when scope='trace'")
            return {"traceIds": [trace_id]}

        elif scope == "span":
            if not span_ids:
                raise ValueError("span_ids are required when scope='span'")
            return {"spanIds": span_ids}

        else:
            raise ValueError(f"Invalid scope: {scope}. Must be 'session', 'trace', or 'span'")

    def _extract_raw_spans(self, trace_data: TraceData) -> List[Dict[str, Any]]:
        """TraceData から生のスパンドキュメントを抽出します。

        Args:
            trace_data: スパンとランタイムログを含む TraceData

        Returns:
            生のスパンドキュメントのリスト
        """
        raw_spans = []

        for span in trace_data.spans:
            if span.raw_message:
                raw_spans.append(span.raw_message)

        for log in trace_data.runtime_logs:
            if log.raw_message:
                raw_spans.append(log.raw_message)

        return raw_spans

    def _filter_relevant_spans(self, raw_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """評価用の高信号スパンのみにフィルタリングします。

        以下のみを保持します：
        - gen_ai.* 属性を持つスパン（LLM 呼び出し、エージェント操作）
        - 会話データを含むログイベント（入力/出力メッセージ）

        Args:
            raw_spans: 生のスパン/ログドキュメントのリスト

        Returns:
            関連するスパンのフィルタリングされたリスト
        """
        relevant_spans = []
        for span_doc in raw_spans:
            attributes = span_doc.get("attributes", {})
            if any(k.startswith("gen_ai") for k in attributes.keys()):
                relevant_spans.append(span_doc)
                continue

            body = span_doc.get("body", {})
            if isinstance(body, dict) and ("input" in body or "output" in body):
                relevant_spans.append(span_doc)

        return relevant_spans

    def _get_most_recent_session_spans(
        self, trace_data: TraceData, max_items: int = DEFAULT_MAX_EVALUATION_ITEMS
    ) -> List[Dict[str, Any]]:
        """セッション内のすべてのトレースから最新の関連スパンを取得します。

        Args:
            trace_data: すべてのセッションデータを含む TraceData
            max_items: 返すアイテムの最大数

        Returns:
            生のスパンドキュメントのリスト（最新のものが先頭）
        """
        raw_spans = self._extract_raw_spans(trace_data)

        if not raw_spans:
            return []

        relevant_spans = self._filter_relevant_spans(raw_spans)

        def get_timestamp(span_doc):
            return span_doc.get("startTimeUnixNano") or span_doc.get("timeUnixNano") or 0

        relevant_spans.sort(key=get_timestamp, reverse=True)

        return relevant_spans[:max_items]

    def _fetch_session_data(self, session_id: str, agent_id: str, region: str) -> TraceData:
        """CloudWatch からセッションデータを取得します。

        Args:
            session_id: 取得するセッション ID
            agent_id: フィルタリング用のエージェント ID
            region: AWS リージョン

        Returns:
            セッションスパンとログを含む TraceData

        Raises:
            RuntimeError: セッションデータを取得できない場合
        """
        obs_client = ObservabilityClient(region_name=region, agent_id=agent_id, runtime_suffix=DEFAULT_RUNTIME_SUFFIX)

        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        start_time_ms = int(start_time.timestamp() * 1000)
        end_time_ms = int(end_time.timestamp() * 1000)

        try:
            trace_data = obs_client.get_session_data(
                session_id=session_id, start_time_ms=start_time_ms, end_time_ms=end_time_ms, include_runtime_logs=True
            )
        except Exception as e:
            raise RuntimeError(f"Failed to fetch session data: {e}") from e

        if not trace_data or not trace_data.spans:
            raise RuntimeError(f"No trace data found for session {session_id}")

        return trace_data

    def _count_span_types(self, raw_spans: List[Dict[str, Any]]) -> tuple:
        """スパン、ログ、gen_ai スパンをカウントします。

        Args:
            raw_spans: 生のスパンドキュメントのリスト

        Returns:
            (spans_count, logs_count, genai_spans_count) のタプル
        """
        spans_count = sum(1 for item in raw_spans if "spanId" in item and "startTimeUnixNano" in item)
        logs_count = sum(1 for item in raw_spans if "body" in item and "timeUnixNano" in item)
        genai_spans = sum(
            1
            for span in raw_spans
            if "spanId" in span and any(k.startswith("gen_ai") for k in span.get("attributes", {}).keys())
        )
        return spans_count, logs_count, genai_spans

    def _save_input(
        self,
        session_id: str,
        otel_spans: List[Dict[str, Any]],
    ) -> str:
        """入力データを JSON ファイルに保存します。

        評価 API に送信されるスパンのみを保存します。

        Args:
            session_id: セッション ID
            otel_spans: API に送信されるスパン

        Returns:
            保存されたファイルへのパス
        """
        from .constants import EVALUATION_INPUT_DIR
        os.makedirs(EVALUATION_INPUT_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_short = session_id[:16] if len(session_id) > 16 else session_id
        filename = f"{EVALUATION_INPUT_DIR}/input_{session_short}_{timestamp}.json"

        # Save only the spans (the actual API input)
        with open(filename, "w", encoding=DEFAULT_FILE_ENCODING) as f:
            json.dump(otel_spans, f, indent=2)

        print(f"入力を保存しました: {filename}")
        return filename

    def _save_output(self, results: EvaluationResults) -> str:
        """評価結果を JSON ファイルに保存します。

        Args:
            results: EvaluationResults オブジェクト

        Returns:
            保存されたファイルへのパス
        """
        os.makedirs(EVALUATION_OUTPUT_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_short = results.session_id[:16] if len(results.session_id) > 16 else results.session_id
        filename = f"{EVALUATION_OUTPUT_DIR}/output_{session_short}_{timestamp}.json"

        with open(filename, "w", encoding=DEFAULT_FILE_ENCODING) as f:
            json.dump(results.to_dict(), f, indent=2)

        print(f"出力を保存しました: {filename}")
        return filename

    def _scan_evaluation_outputs(self) -> List[Path]:
        """評価出力ディレクトリをスキャンして JSON ファイルを取得します。

        Returns:
            見つかった JSON ファイルの Path オブジェクトのリスト

        Raises:
            FileNotFoundError: 出力ディレクトリが存在しない場合
        """
        output_dir = Path.cwd() / EVALUATION_OUTPUT_DIR

        if not output_dir.exists():
            raise FileNotFoundError(f"Directory '{EVALUATION_OUTPUT_DIR}' does not exist")

        if not output_dir.is_dir():
            raise NotADirectoryError(f"'{EVALUATION_OUTPUT_DIR}' is not a directory")

        json_files = list(output_dir.glob(EVALUATION_OUTPUT_PATTERN))

        if not json_files:
            print(f"警告: '{EVALUATION_OUTPUT_DIR}' に JSON ファイルが見つかりません")
            return []

        return sorted(json_files)

    def _scan_evaluation_inputs(self) -> List[Path]:
        """evaluation_input ディレクトリをスキャンして JSON ファイルを取得します。

        Returns:
            見つかった入力 JSON ファイルの Path オブジェクトのリスト
        """
        from .constants import EVALUATION_INPUT_DIR
        input_dir = Path.cwd() / EVALUATION_INPUT_DIR

        if not input_dir.exists() or not input_dir.is_dir():
            return []

        return list(input_dir.glob("input_*.json"))

    def _extract_trace_data_from_input(self, input_file: Path) -> Optional[Dict[str, Any]]:
        """入力ファイルを解析してトレースレベルの情報を抽出します。

        Args:
            input_file: 入力 JSON ファイルへのパス

        Returns:
            トレースデータを含む辞書、抽出に失敗した場合は None
        """
        try:
            with open(input_file, "r", encoding=DEFAULT_FILE_ENCODING) as f:
                spans = json.load(f)

            if not isinstance(spans, list) or not spans:
                return None

            # Extract session_id and trace_id from first span
            first_span = spans[0]
            session_id = first_span.get("attributes", {}).get("session.id")
            trace_id = first_span.get("traceId")

            if not session_id or not trace_id:
                return None

            # Extract input and output messages
            input_messages = []
            output_messages = []
            tools_used = []

            for span in spans:
                body = span.get("body", {})

                # Extract input messages
                if "input" in body and isinstance(body["input"], dict):
                    messages = body["input"].get("messages", [])
                    for msg in messages:
                        if isinstance(msg, dict):
                            input_messages.append(msg)

                # Extract output messages
                if "output" in body and isinstance(body["output"], dict):
                    messages = body["output"].get("messages", [])
                    for msg in messages:
                        if isinstance(msg, dict):
                            output_messages.append(msg)

                            # Extract tools from message content
                            content = msg.get("content", {})
                            if isinstance(content, dict):
                                message_str = content.get("message", "")
                            elif isinstance(content, str):
                                message_str = content
                            else:
                                message_str = ""

                            # Try to find toolUse in content
                            if "toolUse" in message_str:
                                try:
                                    # Content might be double-encoded JSON
                                    parsed = json.loads(message_str) if message_str.startswith("[") else None
                                    if isinstance(parsed, list):
                                        for item in parsed:
                                            if isinstance(item, dict) and "toolUse" in item:
                                                tool_name = item["toolUse"].get("name")
                                                if tool_name:
                                                    tools_used.append(tool_name)
                                except (json.JSONDecodeError, TypeError):
                                    pass

            # Get unique tools with counts
            tools_with_counts = {}
            for tool in tools_used:
                tools_with_counts[tool] = tools_with_counts.get(tool, 0) + 1

            # Get timestamps for this trace
            timestamps = [span.get("timeUnixNano") for span in spans if span.get("timeUnixNano")]
            min_timestamp = min(timestamps) if timestamps else None
            max_timestamp = max(timestamps) if timestamps else None

            # Extract token usage from spans if available
            total_input_tokens = 0
            total_output_tokens = 0

            for span in spans:
                attrs = span.get("attributes", {})
                total_input_tokens += attrs.get("gen_ai.usage.input_tokens", 0)
                total_output_tokens += attrs.get("gen_ai.usage.output_tokens", 0)

            # Calculate latency in milliseconds if timestamps available
            latency_ms = None
            if min_timestamp and max_timestamp:
                latency_ms = (max_timestamp - min_timestamp) / 1_000_000  # Convert nanoseconds to milliseconds

            return {
                "session_id": session_id,
                "trace_id": trace_id,
                "input_messages": input_messages,
                "output_messages": output_messages,
                "tools_used": tools_with_counts,
                "span_count": len(spans),
                "timestamp": min_timestamp,
                "timestamp_end": max_timestamp,
                "latency_ms": latency_ms,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
            }

        except json.JSONDecodeError as e:
            print(f"警告: 入力ファイル {input_file.name} の解析に失敗しました: {e}")
            return None
        except Exception as e:
            print(f"警告: {input_file.name} からのトレースデータ抽出中にエラーが発生しました: {e}")
            return None

    def _match_input_output_files(
        self,
        output_files: List[Path],
        input_files: List[Path]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """出力ファイルを対応する入力ファイルとマッチングし、トレースデータを抽出します。

        Args:
            output_files: 評価出力ファイルパスのリスト
            input_files: 評価入力ファイルパスのリスト

        Returns:
            (session_id, trace_id) タプルをトレースデータにマッピングする辞書
        """
        # Build a map of input data by (session_id, trace_id)
        trace_data_map = {}

        for input_file in input_files:
            trace_data = self._extract_trace_data_from_input(input_file)
            if trace_data:
                key = (trace_data["session_id"], trace_data["trace_id"])
                trace_data_map[key] = trace_data

        return trace_data_map

    def _aggregate_evaluation_data(self, json_files: List[Path]) -> List[Dict[str, Any]]:
        """JSON ファイルから session_id ごとにトレースレベルの詳細を含む評価データを集約します。

        Args:
            json_files: 処理する JSON ファイルパスのリスト

        Returns:
            トレースレベル情報を含む集約されたセッションデータ辞書のリスト
        """
        sessions_map = {}
        skipped_files = []

        # Scan for input files and extract trace data
        input_files = self._scan_evaluation_inputs()
        trace_data_map = self._match_input_output_files(json_files, input_files)

        print(f"トレースデータを含む入力ファイル {len(input_files)} 個を検出しました")

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding=DEFAULT_FILE_ENCODING) as f:
                    data = json.load(f)
                    session_id = data.get("session_id")

                    if not session_id:
                        skipped_files.append((json_file.name, "No session_id found"))
                        continue

                    if session_id not in sessions_map:
                        sessions_map[session_id] = {
                            "session_id": session_id,
                            "results": [],
                            "metadata": data.get("metadata", {}),
                            "source_files": [],
                            "evaluation_runs": 0,
                            "traces": {}  # New: map of trace_id to trace data
                        }

                    # Only increment if there are actual results
                    results = data.get("results", [])
                    if results:
                        sessions_map[session_id]["results"].extend(results)
                        sessions_map[session_id]["evaluation_runs"] += 1

                        # Group results by trace_id
                        for result in results:
                            context = result.get("context", {})
                            span_context = context.get("spanContext", {})
                            trace_id = span_context.get("traceId")

                            if trace_id:
                                # Get or create trace entry
                                if trace_id not in sessions_map[session_id]["traces"]:
                                    # Try to get trace data from input files
                                    trace_key = (session_id, trace_id)
                                    trace_data = trace_data_map.get(trace_key, {})

                                    sessions_map[session_id]["traces"][trace_id] = {
                                        "trace_id": trace_id,
                                        "session_id": session_id,
                                        "results": [],
                                        "input": trace_data.get("input_messages", []),
                                        "output": trace_data.get("output_messages", []),
                                        "tools_used": trace_data.get("tools_used", {}),
                                        "span_count": trace_data.get("span_count", 0),
                                        "timestamp": trace_data.get("timestamp"),
                                        "latency_ms": trace_data.get("latency_ms"),
                                        "input_tokens": trace_data.get("input_tokens", 0),
                                        "output_tokens": trace_data.get("output_tokens", 0),
                                        "total_tokens": trace_data.get("total_tokens", 0),
                                    }

                                # Add result to this trace
                                sessions_map[session_id]["traces"][trace_id]["results"].append(result)

                    sessions_map[session_id]["source_files"].append(json_file.name)

                    # Merge metadata (later files override earlier ones)
                    if data.get("metadata"):
                        sessions_map[session_id]["metadata"].update(data.get("metadata", {}))

            except json.JSONDecodeError as e:
                skipped_files.append((json_file.name, f"JSON decode error: {e}"))
            except PermissionError as e:
                skipped_files.append((json_file.name, f"Permission denied: {e}"))
            except Exception as e:
                skipped_files.append((json_file.name, f"Error: {e}"))

        # Convert traces dict to list for each session
        for session in sessions_map.values():
            session["traces"] = list(session["traces"].values())

        # Report skipped files
        if skipped_files:
            print(f"警告: {len(skipped_files)} 個のファイルをスキップしました:")
            for filename, reason in skipped_files:
                print(f"  - {filename}: {reason}")

        return list(sessions_map.values())

    def _write_dashboard_data(self, evaluation_data: List[Dict[str, Any]]) -> Path:
        """集約された評価データを dashboard_data.js ファイルに書き込みます。

        Args:
            evaluation_data: 集約されたセッションデータのリスト

        Returns:
            生成された dashboard_data.js ファイルへのパス

        Raises:
            IOError: ファイル書き込みに失敗した場合
        """
        js_content = f"""// Auto-generated dashboard data
// Generated from {EVALUATION_OUTPUT_DIR} directory
// Sessions aggregated by session_id

const EVALUATION_DATA = {json.dumps(evaluation_data, indent=2)};

// Export for use in dashboard
if (typeof window !== 'undefined') {{
    window.EVALUATION_DATA = EVALUATION_DATA;
}}
"""

        dashboard_data_path = Path.cwd() / DASHBOARD_DATA_FILE

        try:
            with open(dashboard_data_path, "w", encoding=DEFAULT_FILE_ENCODING) as f:
                f.write(js_content)
        except PermissionError as e:
            raise IOError(f"Permission denied writing to {DASHBOARD_DATA_FILE}: {e}") from e
        except Exception as e:
            raise IOError(f"Failed to write {DASHBOARD_DATA_FILE}: {e}") from e

        return dashboard_data_path

    def _open_dashboard_in_browser(self, dashboard_html_path: Path) -> bool:
        """ダッシュボード HTML ファイルをデフォルトブラウザで開きます。

        Args:
            dashboard_html_path: ダッシュボード HTML ファイルへのパス

        Returns:
            ブラウザが正常に開いた場合は True、それ以外は False
        """
        if not dashboard_html_path.exists():
            print(f"警告: {DASHBOARD_HTML_FILE} が {dashboard_html_path} に見つかりません")
            return False

        try:
            # Use as_uri() for proper cross-platform file:// URL handling
            dashboard_url = dashboard_html_path.as_uri()
            success = webbrowser.open(dashboard_url)

            if success:
                print(f"ブラウザでダッシュボードを開いています: {dashboard_html_path.name}")
                return True
            else:
                print("警告: ブラウザを自動的に開けませんでした。")
                print(f"手動で開いてください: {dashboard_url}")
                return False

        except Exception as e:
            print(f"警告: ブラウザを開けませんでした: {e}")
            print(f"{DASHBOARD_HTML_FILE} を手動で開いてください")
            return False

    def _create_dashboard(self) -> None:
        """ダッシュボードデータを生成し、ダッシュボードをブラウザで開きます。

        このメソッドは evaluation_output/ ディレクトリ内のすべての評価出力を集約し、
        dashboard_data.js ファイルを生成し、ダッシュボード HTML を
        デフォルトブラウザで開きます。

        注意: これはディレクトリ内のすべての評価出力ファイルを集約します。
        現在のセッションの評価だけではありません。

        Raises:
            FileNotFoundError: evaluation_output ディレクトリが存在しない場合
            IOError: ダッシュボードデータファイルを書き込めない場合
        """
        try:
            # Step 1: Scan for JSON files
            json_files = self._scan_evaluation_outputs()

            if not json_files:
                print("ダッシュボード用に集計する評価出力がありません")
                return

            print(f"評価出力ファイル {len(json_files)} 個を検出しました")

            # Step 2: Aggregate data
            evaluation_data = self._aggregate_evaluation_data(json_files)

            if not evaluation_data:
                print("ダッシュボードを生成するための有効な評価データが見つかりません")
                return

            # Step 3: Write dashboard data file
            dashboard_data_path = self._write_dashboard_data(evaluation_data)

            total_evaluations = sum(len(session.get("results", [])) for session in evaluation_data)
            print(
                f"ダッシュボードデータを生成しました: セッション {len(evaluation_data)} 個、評価 {total_evaluations} 個"
            )

            # Step 4: Open dashboard in browser
            dashboard_html_path = Path.cwd() / DASHBOARD_HTML_FILE
            self._open_dashboard_in_browser(dashboard_html_path)

        except FileNotFoundError as e:
            print(f"ダッシュボード作成に失敗しました: {e}")
            print("auto_save_output=True で評価を実行したことを確認してください")
        except IOError as e:
            print(f"ダッシュボード作成に失敗しました: {e}")
        except Exception as e:
            print(f"ダッシュボード作成中に予期しないエラーが発生しました: {e}")

    def evaluate(
        self, evaluator_id: str, session_spans: List[Dict[str, Any]], evaluation_target: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """変換されたスパンで評価 API を呼び出します。

        Args:
            evaluator_id: 単一の評価器識別子
            session_spans: OpenTelemetry フォーマットのスパンドキュメントのリスト
            evaluation_target: 評価する spanIds または traceIds を含むオプションの辞書

        Returns:
            evaluationResults を含む生の API レスポンス

        Raises:
            RuntimeError: API 呼び出しが失敗した場合
        """
        request = EvaluationRequest(
            evaluator_id=evaluator_id, session_spans=session_spans, evaluation_target=evaluation_target
        )

        evaluator_id_param, request_body = request.to_api_request()

        try:
            response = self.client.evaluate(evaluatorId=evaluator_id_param, **request_body)
            return response
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            raise RuntimeError(f"Evaluation API error ({error_code}): {error_msg}") from e

    def evaluate_session(
        self,
        session_id: str,
        evaluator_ids: List[str],
        agent_id: str,
        region: str,
        scope: str,
        trace_id: Optional[str] = None,
        span_filter: Optional[Dict[str, str]] = None,
        auto_save_input: bool = False,
        auto_save_output: bool = False,
        auto_create_dashboard: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResults:
        """1つ以上の評価器を使用してセッションを評価します。

        Args:
            session_id: 評価するセッション ID
            evaluator_ids: 評価器識別子のリスト（例: ["Builtin.Helpfulness"]）
            agent_id: セッションデータ取得用のエージェント ID
            region: ObservabilityClient 用の AWS リージョン
            scope: 評価スコープ - "session"、"trace"、または "span"
            trace_id: trace スコープ用のトレース ID（オプション）
            span_filter: span スコープ用のフィルター（オプションの辞書、例: {"tool_name": "calculate_bmi"}）
            auto_save_input: True の場合、入力スパンを evaluation_input/ フォルダに保存
            auto_save_output: True の場合、結果を evaluation_output/ フォルダに保存
            auto_create_dashboard: True の場合、すべての評価出力を集約し、
                dashboard_data.js を生成し、ダッシュボードをブラウザで開きます。auto_save_output=True が必要です。
                注意: 現在のセッションだけでなく、ディレクトリ内のすべての評価出力を集約します。
            metadata: 実験や説明などを追跡するためのオプションのメタデータ辞書

        Returns:
            評価結果を含む EvaluationResults

        Raises:
            RuntimeError: セッションデータを取得できないか評価に失敗した場合
            ValueError: スコープと評価器の組み合わせが無効か、必要な ID が不足している場合
        """
        # Validate evaluator_ids is not empty
        if not evaluator_ids:
            raise ValueError("evaluator_ids cannot be empty")

        # Validate scope for all evaluators first
        for evaluator_id in evaluator_ids:
            self._validate_scope_compatibility(evaluator_id, scope)

        trace_data = self._fetch_session_data(session_id, agent_id, region)

        num_traces = len(trace_data.get_trace_ids())
        num_spans = len(trace_data.spans)
        print(f"セッション内で {num_traces} 個のトレースにまたがる {num_spans} 個のスパンを検出しました")

        # Auto-discover span IDs if scope is "span"
        span_ids = None
        if scope == "span":
            tool_name_filter = (span_filter or {}).get("tool_name")
            span_ids = trace_data.get_tool_execution_spans(tool_name_filter=tool_name_filter)

            if not span_ids:
                filter_msg = f" (filter: tool_name={tool_name_filter})" if tool_name_filter else ""
                raise ValueError(f"No tool execution spans found in session{filter_msg}")

            print(f"評価用のツール実行スパン {len(span_ids)} 個を検出しました")

        # Build evaluation target based on scope
        evaluation_target = self._build_evaluation_target(scope=scope, trace_id=trace_id, span_ids=span_ids)

        if evaluation_target:
            target_type = "traceIds" if "traceIds" in evaluation_target else "spanIds"
            target_ids = evaluation_target[target_type]
            print(f"評価対象: {target_type} = {target_ids}")

        print(f"最新の関連アイテム {DEFAULT_MAX_EVALUATION_ITEMS} 個を収集中")
        otel_spans = self._get_most_recent_session_spans(trace_data, max_items=DEFAULT_MAX_EVALUATION_ITEMS)

        if not otel_spans:
            print("警告: フィルタリング後に関連するアイテムが見つかりません")

        spans_count, logs_count, genai_spans = self._count_span_types(otel_spans)
        print(
            f"評価 API に {len(otel_spans)} 個のアイテムを送信中 "
            f"（スパン {spans_count} 個 [gen_ai 属性付き {genai_spans} 個]、"
            f"ログイベント {logs_count} 個）"
        )

        # Save input if requested (only the spans sent to API)
        if auto_save_input:
            self._save_input(session_id, otel_spans)

        results = EvaluationResults(session_id=session_id, metadata=metadata)

        for evaluator_id in evaluator_ids:
            try:
                response = self.evaluate(
                    evaluator_id=evaluator_id, session_spans=otel_spans, evaluation_target=evaluation_target
                )

                api_results = response.get("evaluationResults", [])

                if not api_results:
                    print(f"警告: 評価器 {evaluator_id} から結果が返されませんでした")

                for api_result in api_results:
                    result = EvaluationResult.from_api_response(api_result)
                    results.add_result(result)

            except Exception as e:
                error_result = EvaluationResult(
                    evaluator_id=evaluator_id,
                    evaluator_name=evaluator_id,
                    evaluator_arn="",
                    explanation=f"Evaluation failed: {str(e)}",
                    context={"spanContext": {"sessionId": session_id}},
                    error=str(e),
                )
                results.add_result(error_result)

        # results.input_data = {"spans": otel_spans} # commenting out, will think later if this is meaningful to add

        # Save output if requested
        if auto_save_output:
            self._save_output(results)

        # Create dashboard if requested
        if auto_create_dashboard:
            if auto_save_output:
                self._create_dashboard()
            else:
                print("警告: auto_create_dashboard には auto_save_output=True が必要です")
                print("ダッシュボードは作成されませんでした。ダッシュボード生成を有効にするには auto_save_output=True を設定してください。")

        return results
