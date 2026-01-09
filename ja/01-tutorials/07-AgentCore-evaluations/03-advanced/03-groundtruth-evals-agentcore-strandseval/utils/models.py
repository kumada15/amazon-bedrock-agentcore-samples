"""トレースデータと評価のデータモデル。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from strands_evals.mappers.session_mapper import SessionMapper
    from strands_evals.types.trace import Session


@dataclass
class Span:
    """トレースメタデータを持つ OpenTelemetry スパン。"""

    trace_id: str
    span_id: str
    span_name: str
    start_time_unix_nano: Optional[int] = None
    raw_message: Optional[Dict[str, Any]] = None

    @classmethod
    def from_cloudwatch_result(cls, result: Any) -> "Span":
        """CloudWatch Logs Insights クエリ結果から Span を作成します。"""
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default: Any = None) -> Any:
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        def parse_json_field(field_name: str) -> Any:
            value = get_field(field_name)
            if value and isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value

        def get_int_field(field_name: str) -> Optional[int]:
            value = get_field(field_name)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
            return None

        return cls(
            trace_id=get_field("traceId", ""),
            span_id=get_field("spanId", ""),
            span_name=get_field("spanName", ""),
            start_time_unix_nano=get_int_field("startTimeUnixNano"),
            raw_message=parse_json_field("@message"),
        )


@dataclass
class RuntimeLog:
    """エージェント固有のロググループからのランタイムログエントリ。"""

    timestamp: str
    message: str
    span_id: Optional[str] = None
    trace_id: Optional[str] = None
    raw_message: Optional[Dict[str, Any]] = None

    @classmethod
    def from_cloudwatch_result(cls, result: Any) -> "RuntimeLog":
        """CloudWatch Logs Insights クエリ結果から RuntimeLog を作成します。"""
        fields = result if isinstance(result, list) else result.get("fields", [])

        def get_field(field_name: str, default: Any = None) -> Any:
            for field_item in fields:
                if field_item.get("field") == field_name:
                    return field_item.get("value", default)
            return default

        def parse_json_field(field_name: str) -> Any:
            value = get_field(field_name)
            if value and isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value

        return cls(
            timestamp=get_field("@timestamp", ""),
            message=get_field("@message", ""),
            span_id=get_field("spanId"),
            trace_id=get_field("traceId"),
            raw_message=parse_json_field("@message"),
        )


@dataclass
class TraceData:
    """スパンとランタイムログを含む完全なセッションデータ。"""

    session_id: Optional[str] = None
    spans: List[Span] = field(default_factory=list)
    runtime_logs: List[RuntimeLog] = field(default_factory=list)

    def get_trace_ids(self) -> List[str]:
        """スパンからすべてのユニークなトレース ID を取得します。"""
        return list(set(span.trace_id for span in self.spans if span.trace_id))

    def get_tool_execution_spans(self, tool_name_filter: Optional[str] = None) -> List[str]:
        """ツール実行スパンのスパン ID を取得します。

        Args:
            tool_name_filter: フィルタリングするオプションのツール名（例: "calculate_bmi"）

        Returns:
            gen_ai.operation.name == "execute_tool" であるスパン ID のリスト
        """
        tool_span_ids = []

        for span in self.spans:
            if not span.raw_message:
                continue

            attributes = span.raw_message.get("attributes", {})

            # Check if this is a tool execution span
            operation_name = attributes.get("gen_ai.operation.name")
            if operation_name != "execute_tool":
                continue

            # Apply tool name filter if provided
            if tool_name_filter:
                tool_name = attributes.get("gen_ai.tool.name")
                if tool_name != tool_name_filter:
                    continue

            tool_span_ids.append(span.span_id)

        return tool_span_ids

    def to_session(self, mapper: SessionMapper) -> Session:
        """提供されたマッパーを使用して Strands Eval Session に変換します。

        Args:
            mapper: SessionMapper 実装（例: CloudWatchSessionMapper）

        Returns:
            評価用の Session オブジェクト
        """
        return mapper.map_to_session(self.spans, self.session_id or "")


class EvaluationRequest:
    """評価 API のリクエストペイロード。"""

    def __init__(
        self,
        evaluator_id: str,
        session_spans: List[Dict[str, Any]],
        evaluation_target: Optional[Dict[str, Any]] = None
    ):
        self.evaluator_id = evaluator_id
        self.session_spans = session_spans
        self.evaluation_target = evaluation_target

    def to_api_request(self) -> tuple:
        """API リクエストフォーマットに変換します。

        Returns:
            (evaluator_id_param, request_body) のタプル
        """
        request_body = {"evaluationInput": {"sessionSpans": self.session_spans}}

        if self.evaluation_target:
            request_body["evaluationTarget"] = self.evaluation_target

        return self.evaluator_id, request_body


@dataclass
class EvaluationResult:
    """評価 API からの結果。"""

    evaluator_id: str
    evaluator_name: str
    evaluator_arn: str
    explanation: str
    context: Dict[str, Any]
    value: Optional[float] = None
    label: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None

    @classmethod
    def from_api_response(cls, api_result: Dict[str, Any]) -> "EvaluationResult":
        """API レスポンスから EvaluationResult を作成します。"""
        return cls(
            evaluator_id=api_result.get("evaluatorId", ""),
            evaluator_name=api_result.get("evaluatorName", ""),
            evaluator_arn=api_result.get("evaluatorArn", ""),
            explanation=api_result.get("explanation", ""),
            context=api_result.get("context", {}),
            value=api_result.get("value"),  # None if not present
            label=api_result.get("label"),  # None if not present
            token_usage=api_result.get("tokenUsage"),  # None if not present
            error=None,
        )


@dataclass
class EvaluationResults:
    """セッションの評価結果のコレクション。"""

    session_id: str
    results: List[EvaluationResult] = field(default_factory=list)
    input_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    def add_result(self, result: EvaluationResult) -> None:
        """評価結果を追加します。"""
        self.results.append(result)

    def to_dict(self) -> Dict[str, Any]:
        """JSON シリアライゼーション用に辞書に変換します。"""
        output = {
            "session_id": self.session_id,
            "results": [
                {
                    "evaluator_id": r.evaluator_id,
                    "evaluator_name": r.evaluator_name,
                    "evaluator_arn": r.evaluator_arn,
                    "value": r.value,
                    "label": r.label,
                    "explanation": r.explanation,
                    "context": r.context,
                    "token_usage": r.token_usage,
                    "error": r.error,
                }
                for r in self.results
            ],
        }
        if self.metadata:
            output["metadata"] = self.metadata
        if self.input_data:
            output["input_data"] = self.input_data
        return output


@dataclass
class SessionInfo:
    """検出されたセッションに関する情報。

    Attributes:
        session_id: セッションのユニーク識別子
        span_count: スパン数（time_based）または評価数（score_based）
            - time_based 検出: トレースからの実際のスパン数
            - score_based 検出: 評価数（metadata.eval_count にも格納）
        first_seen: 最初のアクティビティのタイムスタンプ
        last_seen: 最後のアクティビティのタイムスタンプ
        trace_count: ユニークなトレースの数（time_based 検出のみ）
        discovery_method: セッションの検出方法（"time_based" または "score_based"）
        metadata: 追加データ（score_based の場合: avg_score、min_score、max_score、eval_count）
    """

    session_id: str
    span_count: int
    first_seen: datetime
    last_seen: datetime
    trace_count: Optional[int] = None
    discovery_method: Optional[str] = None  # "time_based" or "score_based"
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON シリアライゼーション用に辞書に変換します。"""
        return {
            "session_id": self.session_id,
            "span_count": self.span_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "trace_count": self.trace_count,
            "discovery_method": self.discovery_method,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionInfo":
        """辞書から SessionInfo を作成します。"""
        first_seen = data["first_seen"]
        last_seen = data["last_seen"]

        # Parse datetime strings if needed and ensure timezone-aware
        if isinstance(first_seen, str):
            first_seen = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)

        if isinstance(last_seen, str):
            last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        return cls(
            session_id=data["session_id"],
            span_count=data["span_count"],
            first_seen=first_seen,
            last_seen=last_seen,
            trace_count=data.get("trace_count"),
            discovery_method=data.get("discovery_method"),
            metadata=data.get("metadata"),
        )


@dataclass
class SessionDiscoveryResult:
    """セッション検出操作の結果。"""

    sessions: List[SessionInfo]
    discovery_time: datetime
    log_group: str
    time_range_start: datetime
    time_range_end: datetime
    discovery_method: str
    filter_criteria: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON シリアライゼーション用に辞書に変換します。"""
        return {
            "sessions": [s.to_dict() for s in self.sessions],
            "discovery_time": self.discovery_time.isoformat(),
            "log_group": self.log_group,
            "time_range_start": self.time_range_start.isoformat(),
            "time_range_end": self.time_range_end.isoformat(),
            "discovery_method": self.discovery_method,
            "filter_criteria": self.filter_criteria,
        }

    def save_to_json(self, filepath: str) -> None:
        """検出結果を JSON ファイルに保存します。"""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_json(cls, filepath: str) -> "SessionDiscoveryResult":
        """JSON ファイルから検出結果を読み込みます。"""
        with open(filepath, "r") as f:
            data = json.load(f)

        return cls(
            sessions=[SessionInfo.from_dict(s) for s in data["sessions"]],
            discovery_time=datetime.fromisoformat(
                data["discovery_time"].replace("Z", "+00:00")
            ),
            log_group=data["log_group"],
            time_range_start=datetime.fromisoformat(
                data["time_range_start"].replace("Z", "+00:00")
            ),
            time_range_end=datetime.fromisoformat(
                data["time_range_end"].replace("Z", "+00:00")
            ),
            discovery_method=data["discovery_method"],
            filter_criteria=data.get("filter_criteria"),
        )

    def get_session_ids(self) -> List[str]:
        """セッション ID のリストを取得します。"""
        return [s.session_id for s in self.sessions]
