"""
天気、時刻、電卓クエリ用の Strands ベースのエージェント。

このエージェントは Amazon Bedrock AgentCore Runtime にデプロイされるように
設計されており、そこで OpenTelemetry インストルメンテーションを受け取ります。

Amazon Bedrock モデルを使用した Strands フレームワークを使用しています。

Braintrust オブザーバビリティが有効な場合（BRAINTRUST_API_KEY 環境変数経由）、
エージェントは Braintrust にトレースをエクスポートするために Strands テレメトリを初期化します。
"""

import logging
import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Initialize AgentCore Runtime App
app = BedrockAgentCoreApp()


@tool
def get_weather(city: str) -> dict[str, Any]:
    """
    指定された都市の現在の天気情報を取得します。

    Args:
        city: 都市名（例: 'Seattle'、'New York'）

    Returns:
        気温、天気状況、湿度を含む天気情報
    """
    from tools.weather_tool import get_weather as weather_impl

    logger.info(f"都市の天気を取得中: {city}")
    result = weather_impl(city)
    logger.debug(f"天気の結果: {result}")

    return result


@tool
def get_time(timezone: str) -> dict[str, Any]:
    """
    指定された都市またはタイムゾーンの現在時刻を取得します。

    Args:
        timezone: タイムゾーン名（例: 'America/New_York'、'Europe/London'）または都市名

    Returns:
        現在時刻、日付、タイムゾーン、UTC オフセット情報
    """
    from tools.time_tool import get_time as time_impl

    logger.info(f"タイムゾーンの時刻を取得中: {timezone}")
    result = time_impl(timezone)
    logger.debug(f"時刻の結果: {result}")

    return result


@tool
def calculator(operation: str, a: float, b: float = None) -> dict[str, Any]:
    """
    数学計算を実行します。

    Args:
        operation: 数学演算（add、subtract、multiply、divide、factorial）
        a: 1 番目の数（または階乗用の数）
        b: 2 番目の数（階乗では使用しない）

    Returns:
        演算の詳細を含む計算結果
    """
    from tools.calculator_tool import calculator as calc_impl

    logger.info(f"計算を実行中: {operation}({a}, {b})")
    result = calc_impl(operation, a, b)
    logger.debug(f"計算の結果: {result}")

    return result


# Initialize Bedrock model
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(model_id=MODEL_ID)

logger.info(f"Strands エージェントをモデルで初期化中: {MODEL_ID}")


def _initialize_agent() -> Agent:
    """
    適切なテレメトリ設定でエージェントを初期化します。

    この関数は、テレメトリ初期化前に環境変数（特に Braintrust 設定）が
    設定されていることを確認するために遅延呼び出しされます。

    Returns:
        設定済みの Strands Agent インスタンス
    """
    # Initialize Braintrust telemetry if configured
    braintrust_api_key = os.getenv("BRAINTRUST_API_KEY")
    if braintrust_api_key:
        logger.info("Braintrust オブザーバビリティが有効 - テレメトリを初期化中")
        try:
            from strands.telemetry import StrandsTelemetry

            strands_telemetry = StrandsTelemetry()
            strands_telemetry.setup_otlp_exporter()
            logger.info("Strands テレメトリの初期化に成功")
        except Exception as e:
            logger.warning(f"Strands テレメトリの初期化に失敗: {e}")
            logger.warning("Braintrust オブザーバビリティなしで続行")
    else:
        logger.info("Braintrust オブザーバビリティは未設定（CloudWatch のみ）")

    # Create and return the agent
    agent = Agent(
        model=model,
        tools=[get_weather, get_time, calculator],
        system_prompt=(
            "あなたは天気、時刻、電卓ツールにアクセスできる親切なアシスタントです。"
            "これらのツールを使用して、ユーザーの質問に正確に回答してください。常に明確で"
            "簡潔な応答をツールの出力に基づいて提供してください。ツール使用時の注意:\n"
            "- 天気: 都市名を直接使用してください\n"
            "- 時刻: 'America/New_York' のようなタイムゾーン形式または都市名を使用してください\n"
            "- 電卓: 'add'、'subtract'、'multiply'、'divide'、'factorial' などの演算を使用してください\n"
            "フレンドリーで親切な応答を心がけてください。"
        ),
    )

    logger.info("エージェントをツールで初期化: get_weather, get_time, calculator")

    return agent


@app.entrypoint
def strands_agent_bedrock(payload: dict[str, Any]) -> str:
    """
    AgentCore Runtime 呼び出し用のエントリーポイント。

    この関数は @app.entrypoint でデコレートされており、AgentCore Runtime の
    エントリーポイントになります。デプロイ時、エージェントは OpenTelemetry
    インストルメンテーションを提供する Strands テレメトリを初期化します。

    テレメトリ設定:
    - BRAINTRUST_API_KEY 環境変数が設定されている場合: Strands テレメトリが初期化され、
      OTEL_EXPORTER_OTLP_* 環境変数を通じて Braintrust に OTEL トレースをエクスポートします
    - BRAINTRUST_API_KEY が設定されていない場合: エージェントは CloudWatch ログのみで動作します

    Args:
        payload: ユーザープロンプトを含む入力ペイロード

    Returns:
        エージェントの応答テキスト
    """
    user_input = payload.get("prompt", "")

    logger.info(f"エージェントがプロンプトで呼び出されました: {user_input}")

    # Initialize agent with proper configuration (lazy initialization)
    agent = _initialize_agent()

    # Invoke the Strands agent
    response = agent(user_input)

    # Extract response text
    response_text = response.message["content"][0]["text"]

    logger.info("エージェントの呼び出しが正常に完了")
    logger.debug(f"レスポンス: {response_text}")

    return response_text


if __name__ == "__main__":
    # When deployed to AgentCore Runtime, this will start the HTTP server
    # listening on port 8080 with /invocations and /ping endpoints
    app.run()
