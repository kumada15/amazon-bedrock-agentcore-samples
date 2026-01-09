from strands import Agent
from strands.models import BedrockModel
from mcp import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# BedrockAgentCoreApp を初期化
app = BedrockAgentCoreApp()


# AWS Documentation MCP サーバーに接続
def create_aws_docs_client():
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"]
            )
        )
    )


# AWS CDK MCP サーバーに接続
def create_cdk_client():
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(command="uvx", args=["awslabs.cdk-mcp-server@latest"])
        )
    )


# 両方の MCP サーバーからツールを使用してエージェントを作成する関数
def create_agent():
    model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    model = BedrockModel(model_id=model_id)

    aws_docs_client = create_aws_docs_client()
    cdk_client = create_cdk_client()

    with aws_docs_client, cdk_client:
        # 両方の MCP サーバーからツールを取得
        tools = aws_docs_client.list_tools_sync() + cdk_client.list_tools_sync()

        # これらのツールでエージェントを作成
        agent = Agent(
            model=model,
            tools=tools,
            system_prompt="""あなたは AWS ドキュメントと CDK ベストプラクティスにアクセスできる親切な AWS アシスタントです。
            AWS サービスと Infrastructure as Code パターンについて簡潔で正確な情報を提供してください。
            料金や CDK について質問された場合は、ツールを使用して最新の情報を検索してください。""",
        )

    return agent, aws_docs_client, cdk_client


@app.entrypoint
def invoke_agent(payload):
    """入力ペイロードを処理してエージェントの応答を返す"""
    agent, aws_docs_client, cdk_client = create_agent()

    with aws_docs_client, cdk_client:
        user_input = payload.get("prompt")
        print(f"リクエストを処理中: {user_input}")
        response = agent(user_input)
        return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
