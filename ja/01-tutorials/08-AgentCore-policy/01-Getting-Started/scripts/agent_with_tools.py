"""
ツール付きエージェントモジュール

このモジュールは、AgentCore Gateway 経由で保険引受ツールにアクセスできる
エージェントを作成し、対話するための関数を提供します。
"""

import json
import os
import requests
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client


def load_config():
    """config.json から設定を読み込む"""
    config_path = Path(__file__).parent.parent / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please run deploy_lambdas.py and setup_gateway.py first."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 必須フィールドを検証
    if "gateway" not in config:
        raise ValueError(
            "Gateway configuration not found in config.json\n"
            "Please run setup_gateway.py first."
        )

    return config


def create_streamable_http_transport(mcp_url: str, access_token: str):
    """MCP クライアント用の streamable HTTP トランスポートを作成"""
    return streamablehttp_client(
        mcp_url, headers={"Authorization": f"Bearer {access_token}"}
    )


def fetch_access_token(client_id, client_secret, token_url):
    """Cognito からアクセストークンを取得"""
    response = requests.post(
        token_url,
        data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if response.status_code != 200:
        raise Exception(f"Failed to get access token: {response.text}")

    return response.json()["access_token"]


def list_available_tools(gateway_url: str, access_token: str):
    """Gateway から利用可能なすべてのツールを一覧表示"""
    try:
        mcp_client = MCPClient(
            lambda: create_streamable_http_transport(gateway_url, access_token)
        )
        with mcp_client:
            tools_list = mcp_client.list_tools_sync()
            # MCPAgentTool には description 属性がない可能性があるため、デフォルト付き getattr を使用
            return [
                (tool.tool_name, getattr(tool, "description", ""))
                for tool in tools_list
            ]
    except Exception as e:
        print(f"⚠️  ツールを一覧表示できませんでした: {e}")
        return []


class AgentSession:
    """
    MCP クライアントのライフサイクルを適切に処理するエージェントセッション用コンテキストマネージャー。

    使用方法:
        with AgentSession() as session:
            response = session.invoke("どのようなツールがありますか？")
    """

    def __init__(self, model_id="amazon.nova-lite-v1:0", verbose=True):
        self.model_id = model_id
        self.verbose = verbose
        self.mcp_client = None
        self.agent = None
        self.config = None
        self.gateway_url = None
        self.access_token = None

    def __enter__(self):
        """エージェントセッションをセットアップ"""
        # 設定を読み込み
        if self.verbose:
            print("📦 Loading configuration...")
        self.config = load_config()

        gateway_config = self.config["gateway"]
        client_info = gateway_config["client_info"]

        CLIENT_ID = client_info["client_id"]
        CLIENT_SECRET = client_info["client_secret"]
        TOKEN_URL = client_info["token_endpoint"]
        self.gateway_url = gateway_config["gateway_url"]
        region = self.config.get("region", "us-east-1")

        # AWS リージョンを設定
        os.environ["AWS_DEFAULT_REGION"] = region

        if self.verbose:
            print("✅ Configuration loaded")
            print(f"   Gateway: {gateway_config.get('gateway_name', 'N/A')}")
            print(f"   Region: {region}")

        # アクセストークンを取得
        if self.verbose:
            print("\n🔑 Authenticating...")
        self.access_token = fetch_access_token(CLIENT_ID, CLIENT_SECRET, TOKEN_URL)
        if self.verbose:
            print("✅ Authentication successful")

        # 利用可能なツールを一覧表示
        if self.verbose:
            print("\n📋 Listing available tools...")
        tool_info = list_available_tools(self.gateway_url, self.access_token)

        if tool_info and self.verbose:
            print(f"✅ Found {len(tool_info)} tool(s):")
            for tool_name, tool_desc in tool_info:
                print(f"   • {tool_name}")
                if tool_desc:
                    print(f"     {tool_desc}")

        # Bedrock モデルをセットアップ
        if self.verbose:
            print(f"\n🤖 Setting up model: {self.model_id}")
        bedrockmodel = BedrockModel(
            model_id=self.model_id,
            streaming=True,
        )

        # MCP クライアントを作成
        self.mcp_client = MCPClient(
            lambda: create_streamable_http_transport(
                self.gateway_url, self.access_token
            )
        )

        # MCP クライアントコンテキストに入る
        self.mcp_client.__enter__()

        # MCP クライアントからツールを取得
        tools = self.mcp_client.list_tools_sync()

        # システムプロンプト付きでエージェントを作成
        system_prompt = """あなたは保険引受業務のための親切な AI アシスタントです。

Gateway からのツールにアクセスできます。Gateway はツールアクセスを制限するポリシーで設定されています。
Gateway から提供されるツールのみを使用してください。情報を捏造しないでください。

ツールを使用する際は、どのツールを呼び出したか、何をしているか、結果を表示してください。
ツール呼び出しが失敗した場合は、エラーをユーザーに明確に説明してください。"""

        self.agent = Agent(model=bedrockmodel, tools=tools, system_prompt=system_prompt)

        if self.verbose:
            print("✅ Agent ready!\n")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """エージェントセッションをクリーンアップ"""
        if self.mcp_client:
            try:
                self.mcp_client.__exit__(exc_type, exc_val, exc_tb)
                if self.verbose:
                    print("✅ Agent session closed")
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Error closing agent session: {e}")

    def invoke(self, prompt, verbose=None):
        """
        プロンプトでエージェントを呼び出す。

        Args:
            prompt: ユーザーのプロンプト/質問
            verbose: プロンプトを出力するかどうか（デフォルト: セッションの verbose 設定を使用）

        Returns:
            str: エージェントのレスポンス
        """
        if verbose is None:
            verbose = self.verbose

        if verbose:
            print(f"💬 Prompt: {prompt}\n")
            print("🤔 Thinking...\n")

        try:
            response = self.agent(prompt)

            # レスポンスコンテンツを抽出
            if hasattr(response, "message"):
                content = response.message.get("content", str(response))
            else:
                content = str(response)

            if verbose:
                print(f"🤖 Agent: {content}\n")

            return content

        except Exception as e:
            error_msg = f"Error: {e}"
            if verbose:
                print(f"❌ {error_msg}\n")
            return error_msg


# 使用例関数
def example_usage():
    """このモジュールの使用例"""
    print("=" * 70)
    print("🚀 保険引受エージェントの例")
    print("=" * 70)
    print()

    # エージェントセッションのコンテキストマネージャーを使用
    with AgentSession() as session:
        # サンプルプロンプト
        prompts = [
            "どのようなツールにアクセスできますか？",
            "US リージョン向けに 50000 ドルの補償範囲でアプリケーションを作成してください",
        ]

        print("=" * 70)
        print("📝 サンプルプロンプトを実行中...")
        print("=" * 70)
        print()

        for prompt in prompts:
            session.invoke(prompt)
            print("-" * 70)
            print()

    print("✅ 完了！")


if __name__ == "__main__":
    example_usage()
