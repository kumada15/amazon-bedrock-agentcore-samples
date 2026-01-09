from bedrock_agentcore.runtime import BedrockAgentCoreApp
import os
from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from langfuse import get_client


streamable_http_mcp_client = MCPClient(lambda: streamablehttp_client("https://langfuse.com/api/mcp"))

# Bedrock モデルを初期化する関数
def get_bedrock_model():
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    
    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=0.0,
        max_tokens=4096
    )
    return bedrock_model

# Bedrock モデルを初期化
bedrock_model = get_bedrock_model()

# エージェントのシステムプロンプトを定義（AWS サンプルと同一）
system_prompt = os.getenv("SYSTEM_PROMPT", "あなたは開発者をサポートする経験豊富なエージェントです。")
env = os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "DEV")

app = BedrockAgentCoreApp()

@app.entrypoint
def strands_agent_bedrock(payload):
    """
    ペイロードを使用してエージェントを呼び出し
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")
    print("ユーザー入力:", user_input)

    # Strands テレメトリを初期化し、OTLP エクスポーターをセットアップ
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()

    # MCP ツールを使用してエージェントを作成
    with streamable_http_mcp_client:

        mcp_tools = streamable_http_mcp_client.list_tools_sync()

        # エージェントを作成
        agent = Agent(
            model=bedrock_model,
            system_prompt=system_prompt,
            tools=mcp_tools
        )
        # DEV および TST 環境で AgentCore と Langfuse 実験からのトレースを統合するために OTEL 分散トレーシングのスパンを再オープン
        if env == "DEV" or env == "TST":
            with get_client().start_as_current_observation(name='strands-agent', trace_context={"trace_id": trace_id, "parent_observation_id": parent_obs_id}):
                response = agent(user_input)
        else:
            
            response = agent(user_input)

    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
