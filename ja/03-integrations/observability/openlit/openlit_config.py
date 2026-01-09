import os
import openlit


def init():
    """AgentCore用のOpenLITインストルメンテーションを初期化します。

    OpenLITはオープンソースのセルフホスト型可観測性ソリューションです。
    デフォルトでは認証やOTLPヘッダーは必要ありません。
    """

    # Get OTEL endpoint (defaults to local OpenLIT instance)
    otel_endpoint = os.environ.get(
        "OTEL_ENDPOINT",
        "http://localhost:4318",  # Default to local OpenLIT instance
    )

    # Initialize OpenLIT SDK
    # OpenLIT provides automatic instrumentation for popular LLM frameworks
    # No authentication required for self-hosted deployments
    openlit.init(
        otlp_endpoint=otel_endpoint,
        application_name=os.environ.get("OPENLIT_APP_NAME", "bedrock-agentcore-agent"),
        environment=os.environ.get("OPENLIT_ENVIRONMENT", "production"),
        disable_batch=False,
    )
    print(f"OpenLITをエンドポイントで初期化しました: {otel_endpoint}")
