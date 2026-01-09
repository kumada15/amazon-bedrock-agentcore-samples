import boto3
from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp,
)  # ### AGENTCORE RUNTIME - LINE 1 ####
from lab_helpers.lab1_strands_agent import (
    MODEL_ID,
    SYSTEM_PROMPT,
    get_product_info,
    get_return_policy,
    get_technical_support,
)
from lab_helpers.lab2_memory import (
    ACTOR_ID,
    SESSION_ID,
    CustomerSupportMemoryHooks,
    memory_client,
)
from lab_helpers.utils import get_ssm_parameter
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# boto3 クライアントを初期化
sts_client = boto3.client("sts")

# AWS アカウント詳細を取得
REGION = boto3.session.Session().region_name

# Lab1 インポート: Bedrock モデルを作成
model = BedrockModel(model_id=MODEL_ID)

# Lab2 インポート: フックを通じてメモリを初期化
memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")
memory_hooks = CustomerSupportMemoryHooks(
    memory_id, memory_client, ACTOR_ID, SESSION_ID
)

# AgentCore Runtime アプリを初期化
app = BedrockAgentCoreApp()  #### AGENTCORE RUNTIME - LINE 2 ####


@app.entrypoint  #### AGENTCORE RUNTIME - LINE 3 ####
async def invoke(payload, context=None):
    """AgentCore Runtime エントリーポイント関数"""
    user_input = payload.get("prompt", "")

    # リクエストヘッダーにアクセス - None ケースを処理
    request_headers = context.request_headers or {}

    # クライアント JWT トークンを取得
    auth_header = request_headers.get("Authorization", "")

    print(f"Authorization ヘッダー: {auth_header}")
    # Gateway ID を取得
    existing_gateway_id = get_ssm_parameter("/app/customersupport/agentcore/gateway_id")

    # Bedrock AgentCore Control クライアントを初期化
    gateway_client = boto3.client(
        "bedrock-agentcore-control",
        region_name=REGION,
    )
    # 既存の Gateway 詳細を取得
    gateway_response = gateway_client.get_gateway(gatewayIdentifier=existing_gateway_id)

    # Gateway URL を取得
    gateway_url = gateway_response["gatewayUrl"]

    # JWT トークンが利用可能な場合、コンテキストマネージャー内で MCP クライアントとエージェントを作成
    if gateway_url and auth_header:
        try:
            mcp_client = MCPClient(
                lambda: streamablehttp_client(
                    url=gateway_url, headers={"Authorization": auth_header}
                )
            )

            with mcp_client:
                # ツール = mcp_client.list_tools_sync()
                tools = [
                    get_product_info,
                    get_return_policy,
                    get_technical_support,
                ] + mcp_client.list_tools_sync()

                # すべてのカスタマーサポートツールでエージェントを作成
                agent = Agent(
                    model=model,
                    tools=tools,
                    system_prompt=SYSTEM_PROMPT,
                    hooks=[memory_hooks],
                )
                # エージェントを呼び出し
                response = agent(user_input)
                return response.message["content"][0]["text"]
        except Exception as e:
            print(f"MCP クライアントエラー: {str(e)}")
            return f"エラー: {str(e)}"
    else:
        return "エラー: Gateway URL または Authorization ヘッダーがありません"


if __name__ == "__main__":
    app.run()  #### AGENTCORE RUNTIME - LINE 4 ####
