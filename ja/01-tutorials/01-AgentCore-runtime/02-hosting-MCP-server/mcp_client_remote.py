import asyncio
import sys
import logging
import boto3
from boto3.session import Session
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from streamable_http_sigv4 import streamablehttp_client_with_sigv4


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_streamable_http_transport_sigv4(
    mcp_url: str, service_name: str, region: str
):
    """
    AWS SigV4認証を使用したストリーミングHTTPトランスポートを作成します。

    この関数は、AWS Signature Version 4 (SigV4)を使用してリクエストを認証する
    MCPクライアントトランスポートを作成します。標準のMCPクライアントはAWS IAM認証を
    ネイティブでサポートしていないため、このギャップを埋める必要があります。

    Args:
        mcp_url (str): MCPゲートウェイエンドポイントのURL
        service_name (str): SigV4署名用のAWSサービス名（通常は「bedrock-agentcore」）
        region (str): ゲートウェイがデプロイされているAWSリージョン

    Returns:
        StreamableHTTPTransportWithSigV4: SigV4認証用に設定されたトランスポートインスタンス

    Example:
        >>> transport = create_streamable_http_transport_sigv4(
        ...     mcp_url=".../mcp",
        ...     service_name="bedrock-agentcore",
        ...     region="us-west-2"
        ... )
    """
    # 現在のboto3セッションからAWS認証情報を取得
    # これらの認証情報はSigV4でリクエストに署名するために使用されます
    session = boto3.Session()
    credentials = session.get_credentials()

    # SigV4署名機能を持つカスタムトランスポートを作成して返す
    return streamablehttp_client_with_sigv4(
        url=mcp_url,
        credentials=credentials,
        service=service_name,
        region=region,
    )


def get_full_tools_list(client):
    """
    MCPクライアントからツールの完全なリストを取得し、ページネーションを処理します。

    MCPサーバーはページネーションされたレスポンスでツールを返す場合があります。
    この関数はページネーションを自動的に処理し、すべての利用可能なツールを
    単一のリストで返します。

    Args:
        client: MCPクライアントインスタンス（strands.tools.mcp.mcp_client.MCPClientから）

    Returns:
        list: MCPサーバーから利用可能なすべてのツールの完全なリスト

    Example:
        >>> mcp_client = MCPClient(lambda: create_transport())
        >>> all_tools = get_full_tools_list(mcp_client)
        >>> print(f"{len(all_tools)} 個のツールが見つかりました")
    """
    more_tools = True
    tools = []
    pagination_token = None

    # すべてのページを取得するまでループ
    while more_tools:
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)

        tools.extend(tmp_tools)

        # さらに取得するページがあるかチェック
        if tmp_tools.pagination_token is None:
            # これ以上ページがない - 完了
            more_tools = False
        else:
            # さらにページが存在する - 次のページを取得する準備
            more_tools = True
            pagination_token = tmp_tools.pagination_token

    return tools


async def main():
    boto_session = Session()
    region = boto_session.region_name
    print(f"使用するAWSリージョン: {region}")

    ssm_client = boto3.client("ssm", region_name=region)

    agent_arn_response = ssm_client.get_parameter(
        Name="/mcp_server/runtime_iam/agent_arn"
    )
    agent_arn = agent_arn_response["Parameter"]["Value"]
    print(f"取得したエージェントARN: {agent_arn}")

    if not agent_arn:
        print("❌ エラー: AGENT_ARNが見つかりません")
        sys.exit(1)

    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    try:
        async with create_streamable_http_transport_sigv4(
            mcp_url=mcp_url, service_name="bedrock-agentcore", region=region
        ) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                print("\n🔄 MCPセッションを初期化中...")
                await session.initialize()
                print("✓ MCPセッション初期化完了")

                print("\n🔄 利用可能なツールを一覧表示中...")
                tool_result = await session.list_tools()

                print("\n📋 利用可能なMCPツール:")
                print("=" * 50)
                for tool in tool_result.tools:
                    print(f"🔧 {tool.name}")
                    print(f"   説明: {tool.description}")
                    if hasattr(tool, "inputSchema") and tool.inputSchema:
                        properties = tool.inputSchema.get("properties", {})
                        if properties:
                            print(f"   パラメータ: {list(properties.keys())}")
                    print()

                print(f"✅ MCPサーバーへの接続に成功しました!")
                print(f"{len(tool_result.tools)} 個のツールが利用可能です。")

    except Exception as e:
        print(f"❌ MCPサーバーへの接続エラー: {e}")
        import traceback

        print("\n🔍 完全なエラートレースバック:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
