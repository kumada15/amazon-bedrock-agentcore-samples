import asyncio
import httpx
import os
import threading
import time
import webbrowser
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Patch httpx at the request level to inject User-Agent header
# This ensures ALL HTTP requests have the User-Agent header, including OAuth discovery calls
_original_httpx_request = httpx.Request.__init__

def _patched_httpx_request_init(self, method, url, *args, **kwargs):
    """すべての HTTP リクエストに User-Agent ヘッダーを挿入するパッチ適用版 Request.__init__"""
    # Get or create headers
    headers = kwargs.get('headers')
    if headers is None:
        headers = {}
        kwargs['headers'] = headers
    
    # Convert to mutable dict if needed
    if not isinstance(headers, dict):
        headers = dict(headers)
        kwargs['headers'] = headers
    
    # Inject User-Agent if not present (case-insensitive check)
    if 'User-Agent' not in headers and 'user-agent' not in headers:
        headers['User-Agent'] = 'python-mcp-sdk/1.0 (BedrockAgentCore-Runtime)'
    
    # Call original __init__
    _original_httpx_request(self, method, url, *args, **kwargs)

# Apply the patch globally before importing MCP modules
httpx.Request.__init__ = _patched_httpx_request_init

# Now import MCP modules - they will use patched httpx
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken


class InMemoryTokenStorage(TokenStorage):
    """シンプルなインメモリトークンストレージの実装"""

    def __init__(self):
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info


class CallbackHandler(BaseHTTPRequestHandler):
    """OAuth コールバックをキャプチャするシンプルな HTTP ハンドラー"""

    def __init__(self, request, client_address, server, callback_data):
        """コールバックデータストレージで初期化"""
        self.callback_data = callback_data
        super().__init__(request, client_address, server)

    def do_GET(self):
        """OAuth リダイレクトからの GET リクエストを処理"""
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        #print(f'Query Params parsed: {query_params}')

        if "code" in query_params:
            self.callback_data["authorization_code"] = query_params["code"][0]
            self.callback_data["state"] = query_params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <script>setTimeout(() => window.close(), 2000);</script>
            </body>
            </html>
            """)
        elif "error" in query_params:
            self.callback_data["error"] = query_params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
            <html>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {query_params["error"][0]}</p>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """.encode()
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """デフォルトのロギングを抑制"""
        pass


class CallbackServer:
    """OAuth コールバックを処理するシンプルなサーバー"""

    def __init__(self, port=3030):
        self.port = port
        self.server = None
        self.thread = None
        self.callback_data = {"authorization_code": None, "state": None, "error": None}

    def _create_handler_with_data(self):
        """コールバックデータへのアクセス権を持つハンドラークラスを作成"""
        callback_data = self.callback_data

        class DataCallbackHandler(CallbackHandler):
            def __init__(self, request, client_address, server):
                super().__init__(request, client_address, server, callback_data)

        return DataCallbackHandler

    def start(self):
        """バックグラウンドスレッドでコールバックサーバーを開始"""
        handler_class = self._create_handler_with_data()
        self.server = HTTPServer(("localhost", self.port), handler_class)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"🖥️  コールバックサーバーを起動しました: http://localhost:{self.port}")

    def stop(self):
        """コールバックサーバーを停止"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout=300):
        """タイムアウト付きで OAuth コールバックを待機"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise Exception(f"OAuth error: {self.callback_data['error']}")
            time.sleep(0.1)
        raise Exception("Timeout waiting for OAuth callback")

    def get_state(self):
        """受信した state パラメータを取得"""
        return self.callback_data["state"]


def add_auth0_audience_parameter(authorization_url: str, audience: str) -> str:
    """
    Auth0 の 'audience' パラメータを認可 URL に追加します。

    Auth0 では、どの API のトークン設定を使用するかを特定するために 'audience' パラメータが必要です。
    これがない場合、Auth0 は JWT ではなく不透明なトークンまたは JWE を返します。

    この関数は、既存のすべてのクエリパラメータ（OAuth の 'resource' パラメータを含む）を
    保持しながら、audience パラメータを適切に追加します。

    Args:
        authorization_url: OAuth フローからの認可 URL
        audience: Auth0 API 識別子（例: "runtime-api"）

    Returns:
        audience パラメータが追加された変更後の URL

    Reference:
        https://auth0.com/docs/secure/tokens/access-tokens/get-access-tokens
    """
    # Only apply to Auth0 URLs that don't already have audience
    if 'auth0.com' not in authorization_url or 'audience=' in authorization_url:
        return authorization_url
    
    # Parse URL and query parameters
    parsed = urlparse(authorization_url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Add audience parameter
    query_params['audience'] = [audience]
    
    # Rebuild URL with new parameter
    new_query = urlencode(query_params, doseq=True)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))


class SimpleAuthClient:
    """Auth0 OAuth サポート付きのシンプルな MCP クライアント"""

    def __init__(
        self,
        server_url: str,
        transport_type: str = "streamable-http",
        auth0_audience: str | None = None,
    ):
        self.server_url = server_url
        self.transport_type = transport_type
        self.auth0_audience = auth0_audience
        self.session: ClientSession | None = None

    async def connect(self):
        """MCP サーバーに接続"""
        print(f"🔗 {self.server_url} に接続を試みています...")

        try:
            callback_server = CallbackServer(port=3030)
            callback_server.start()

            async def callback_handler() -> tuple[str, str | None]:
                """OAuth コールバックを待機し、認証コードと state を返す"""
                print("⏳ 認証コールバックを待機中...")
                try:
                    auth_code = callback_server.wait_for_callback(timeout=300)
                    return auth_code, callback_server.get_state()
                finally:
                    callback_server.stop()

            client_metadata_dict = {
                "client_name": "MCP Auth0 Client",
                "redirect_uris": ["http://localhost:3030/callback"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            }

            async def redirect_handler(authorization_url: str) -> None:
                """Auth0 audience パラメータ付きで URL をブラウザで開くリダイレクトハンドラー"""
                # Add Auth0 audience parameter if configured
                if self.auth0_audience:
                    authorization_url = add_auth0_audience_parameter(
                        authorization_url,
                        self.auth0_audience
                    )
                
                webbrowser.open(authorization_url)

            print("\n🔧 OAuthクライアントプロバイダーを作成中...")
            # Create OAuth authentication handler
            # Note: httpx.AsyncClient is globally patched to inject User-Agent header
            oauth_auth = OAuthClientProvider(
                server_url=self.server_url,
                client_metadata=OAuthClientMetadata.model_validate(client_metadata_dict),
                storage=InMemoryTokenStorage(),
                redirect_handler=redirect_handler,
                callback_handler=callback_handler,
            )
            print("🔧 OAuthクライアントプロバイダーの作成に成功しました")

            # Create transport with auth handler based on transport type
            if self.transport_type == "sse":
                print("📡 認証付きSSEトランスポート接続を開始中...")
                async with sse_client(
                    url=self.server_url,
                    auth=oauth_auth,
                    timeout=60,
                ) as (read_stream, write_stream):
                    await self._run_session(read_stream, write_stream, None)
            else:
                print("📡 認証付きStreamableHTTPトランスポート接続を開始中...")
                async with streamablehttp_client(
                    url=self.server_url,
                    auth=oauth_auth,
                    timeout=timedelta(seconds=60),
                ) as (read_stream, write_stream, get_session_id):
                    await self._run_session(read_stream, write_stream, get_session_id)

        except Exception as e:
            print(f"❌ 接続に失敗しました: {e}")
            import traceback
            traceback.print_exc()

    async def _run_session(self, read_stream, write_stream, get_session_id):
        """指定されたストリームで MCP セッションを実行"""
        print("🤝 MCPセッションを初期化中...")
        async with ClientSession(read_stream, write_stream) as session:
            self.session = session
            print("⚡ セッション初期化を開始中...")
            await session.initialize()
            print("✨ セッション初期化が完了しました!")

            print(f"\n✅ MCPサーバーに接続しました: {self.server_url}")
            if get_session_id:
                session_id = get_session_id()
                if session_id:
                    print(f"セッションID: {session_id}")

            # Run interactive loop
            #await self.interactive_loop()
            await self.invoke_mcp_server()

    async def list_tools(self):
        """サーバーから利用可能なツールを一覧表示"""
        if not self.session:
            print("❌ サーバーに接続されていません")
            return

        try:
            result = await self.session.list_tools()
            if hasattr(result, "tools") and result.tools:
                print("\n📋 利用可能なツール:")
                for i, tool in enumerate(result.tools, 1):
                    print(f"{i}. {tool.name}")
                    if tool.description:
                        print(f"   説明: {tool.description}")
                    print()
            else:
                print("利用可能なツールがありません")
        except Exception as e:
            print(f"❌ ツール一覧の取得に失敗しました: {e}")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None):
        """特定のツールを呼び出す"""
        if not self.session:
            print("❌ サーバーに接続されていません")
            return

        try:
            result = await self.session.call_tool(tool_name, arguments or {})
            print(f"\n🔧 ツール '{tool_name}' の結果:")
            if hasattr(result, "content"):
                for content in result.content:
                    if content.type == "text":
                        print(content.text)
                    else:
                        print(content)
            else:
                print(result)
        except Exception as e:
            print(f"❌ ツール '{tool_name}' の呼び出しに失敗しました: {e}")

    async def invoke_mcp_server(self):
        """MCP サーバーとツールを呼び出す"""
        print("利用可能なツールを表示: ")
        await self.list_tools()
        
        tool_name = "add_numbers"
        arguments= {'a':2, 'b':2}
        print(f"{tool_name} ツールをパラメータ {arguments} で呼び出し中。")
        await self.call_tool(tool_name, arguments)


        tool_name = "multiply_numbers"
        arguments= {'a':2, 'b':4}
        print(f"{tool_name} ツールをパラメータ {arguments} で呼び出し中。")
        await self.call_tool(tool_name, arguments)

        tool_name = "greet_user"
        arguments= {'name': 'Somebody'}
        print(f"{tool_name} ツールをパラメータ {arguments} で呼び出し中。")
        await self.call_tool(tool_name, arguments)


async def main(agent_arn, base_endpoint, auth0_audience):
    """メインエントリーポイント"""
    
    if not agent_arn:
        print("❌ AGENT_ARN環境変数を設定してください")
        print("例: export AGENT_ARN='arn:aws:bedrock:us-west-2:123456789012:agent/ABCD1234'")
        return

    # Encode the ARN for use in URL
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # Construct MCP URL from encoded ARN (no qualifier - SDK discovers it from PRM API)
    server_url = f"{base_endpoint}/runtimes/{encoded_arn}/invocations"
    
    # Get optional transport type
    transport_type = os.getenv("MCP_TRANSPORT_TYPE", "streamable-http")

    print("🚀 MCP Auth0クライアント")
    print(f"エージェントARN: {agent_arn}")
    print(f"エンドポイント: {base_endpoint}")
    print(f"接続先: {server_url}")
    print(f"トランスポートタイプ: {transport_type}")
    if auth0_audience:
        print(f"Auth0オーディエンス: {auth0_audience}")

    # Start connection flow - OAuth will be handled automatically
    client = SimpleAuthClient(
        server_url,
        transport_type,
        auth0_audience,
    )
    await client.connect()


def run_test():
    """uv スクリプト用の CLI エントリーポイント"""
    asyncio.run(main())


if __name__ == "__main__":
    run_test()
