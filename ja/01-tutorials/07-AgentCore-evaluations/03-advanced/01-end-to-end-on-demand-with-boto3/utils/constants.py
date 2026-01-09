"""CloudWatch トレースデータエクスポートと評価用の定数。"""

import os

# API 設定
DEFAULT_MAX_EVALUATION_ITEMS = int(os.getenv("AGENTCORE_MAX_EVAL_ITEMS", "1000"))
MAX_SPAN_IDS_IN_CONTEXT = int(os.getenv("AGENTCORE_MAX_SPAN_IDS", "20"))

DEFAULT_RUNTIME_SUFFIX = "DEFAULT"

# ダッシュボード設定
EVALUATION_OUTPUT_DIR = "evaluation_output"
EVALUATION_INPUT_DIR = "evaluation_input"
DASHBOARD_DATA_FILE = "dashboard_data.js"
DASHBOARD_HTML_FILE = "evaluation_dashboard.html"
EVALUATION_OUTPUT_PATTERN = "*.json"
DEFAULT_FILE_ENCODING = "utf-8"

# Session スコープ Evaluator（sessionId のみ）
# これらの Evaluator はセッション内のすべてのトレースにわたるデータを必要とします
SESSION_SCOPED_EVALUATORS = {
    "Builtin.GoalSuccessRate",
}

# Span スコープ Evaluator（spanIds のみ）
# これらの Evaluator は特定の span レベルのデータ（ツール呼び出し）を必要とします
SPAN_SCOPED_EVALUATORS = {
    "Builtin.ToolSelectionAccuracy",
    "Builtin.ToolParameterAccuracy",
}

# フレキシブルスコープ Evaluator（spanIds 不要）
# これらの Evaluator はセッションまたはトレースレベルで動作可能（span ID は不要）
FLEXIBLE_SCOPED_EVALUATORS = {
    "Builtin.Correctness",
    "Builtin.Faithfulness",
    "Builtin.Helpfulness",
    "Builtin.ResponseRelevance",
    "Builtin.Conciseness",
    "Builtin.Coherence",
    "Builtin.InstructionFollowing",
    "Builtin.Refusal",
    "Builtin.Harmfulness",
    "Builtin.Stereotyping",
}


class AttributePrefixes:
    """OpenTelemetry 属性プレフィックス。"""
    GEN_AI = "gen_ai"