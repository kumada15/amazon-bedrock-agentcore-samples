"""マルチセッションサポート付き CloudWatch から Strands Eval への変換ユーティリティ。

このモジュールは以下のユーティリティを提供します:
- OTEL トレース用の CloudWatch Logs クエリ（ObservabilityClient）
- CloudWatch ロググループからのセッション検出（時間ベースおよびスコアベース）
- CloudWatch span から Strands Eval Session 形式へのマッピング（CloudWatchSessionMapper）
- span、セッション、評価結果のデータモデル
- オリジナルトレース ID 付きカスタム CloudWatch ロギング（send_evaluation_to_cloudwatch）

注: 設定は config.py（ノートブックと同じディレクトリ）にあります。
"""

from .cloudwatch_client import CloudWatchQueryBuilder, ObservabilityClient
from .evaluation_cloudwatch_logger import (
    EvaluationLogConfig,
    log_evaluation_batch,
    send_evaluation_to_cloudwatch,
)
from .models import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationResults,
    RuntimeLog,
    SessionDiscoveryResult,
    SessionInfo,
    Span,
    TraceData,
)
from .session_mapper import CloudWatchSessionMapper

__all__ = [
    # CloudWatch client
    "ObservabilityClient",
    "CloudWatchQueryBuilder",
    # Session mapper
    "CloudWatchSessionMapper",
    # Custom CloudWatch logger
    "send_evaluation_to_cloudwatch",
    "log_evaluation_batch",
    "EvaluationLogConfig",
    # Models
    "Span",
    "RuntimeLog",
    "TraceData",
    "SessionInfo",
    "SessionDiscoveryResult",
    "EvaluationRequest",
    "EvaluationResult",
    "EvaluationResults",
]
