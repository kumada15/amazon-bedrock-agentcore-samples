"""
Amazon Bedrock AgentCore Identity を使用した認可コードフロー用のサンプル OAuth2 コールバックサーバー。

このモジュールは AgentCore Identity 用の OAuth2 3-legged（3LO）認証フローを処理する
ローカルコールバックサーバーを実装します。ユーザーのブラウザ、外部 OAuth プロバイダー
（Google、Entra など）、および AgentCore Identity サービス間の仲介役として機能します。

主要コンポーネント:
- ローカルで実行される FastAPI サーバー
- 外部プロバイダーからの OAuth2 コールバックリダイレクトを処理
- ユーザー識別子の保存とセッション完了を管理
- 準備状態確認用のヘルスチェックエンドポイントを提供

使用コンテキスト:
このサーバーは、認証されたユーザーの代わりに外部リソース（Google カレンダー、Microsoft Entra など）
にアクセスする必要がある AgentCore Runtime 上で実行されるエージェントと組み合わせて使用されます。

典型的なフロー:
  1. エージェントが外部リソースへのアクセスを要求
  2. ユーザーが同意のため OAuth プロバイダーにリダイレクトされる
  3. プロバイダーがこのコールバックサーバーにリダイレクト
  4. サーバーが AgentCore Identity で認証フローを完了
"""

import time
import json
import uvicorn
import logging
import argparse
import requests

from typing import Annotated, Optional
from datetime import datetime, timedelta, timezone
from fastapi import Cookie, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from bedrock_agentcore.services.identity import IdentityClient, UserIdIdentifier


# Configuration constants for the OAuth2 callback server
OAUTH2_CALLBACK_SERVER_PORT = 9090  # Port where the callback server listens
PING_ENDPOINT = "/ping"  # Health check endpoint
OAUTH2_CALLBACK_ENDPOINT = (
    "/oauth2/callback"  # OAuth2 callback endpoint for provider redirects
)
USER_IDENTIFIER_ENDPOINT = (
    "/userIdentifier/userId"  # Endpoint to store userId identifiers
)

logger = logging.getLogger(__name__)


class OAuth2CallbackServer:
    """
    AgentCore Identity との 3-legged OAuth フローを処理するための OAuth2 コールバックサーバー。

    このサーバーは、ユーザー認可後に外部 OAuth プロバイダー（Google、Github など）が
    リダイレクトするローカルコールバックエンドポイントとして機能します。
    AgentCore Identity サービスと連携して OAuth フローの完了を管理します。

    サーバーが保持するもの:
    - API 通信用の AgentCore Identity クライアント
    - セッションバインディング用の UserId 識別子
    - 設定済みルートを持つ FastAPI アプリケーション
    """

    def __init__(self, region: str):
        """
        OAuth2 コールバックサーバーを初期化します。

        Args:
            region (str): AgentCore Identity サービスがデプロイされている AWS リージョン
        """
        # Initialize AgentCore Identity client for the specified region
        self.identity_client = IdentityClient(region=region)
        self.user_id_identifier = None

        self.app = FastAPI()

        # Configure all HTTP routes
        self._setup_routes()

    def _setup_routes(self):
        """
        OAuth2 コールバックサーバー用の FastAPI ルートを設定します。

        3 つのエンドポイントを設定します:
        1. POST /userIdentifier/userId - セッションバインディング用の userId 識別子を保存
        2. GET /ping - ヘルスチェックエンドポイント
        3. GET /oauth2/callback - プロバイダーリダイレクト用の OAuth2 コールバックハンドラー
        """

        @self.app.post(USER_IDENTIFIER_ENDPOINT)
        async def _store_user_id(
            user_id_identifier_value: UserIdIdentifier,
        ) -> JSONResponse:
            """
            OAuth セッションバインディング用の userId 識別子を保存します。

            このエンドポイントは、OAuth フローを開始する前に呼び出され、
            これから行われる OAuth セッションを特定のユーザーに関連付けます。

            Args:
                user_id_identifier_value: ユーザー識別情報を含む UserIdIdentifier オブジェクト
            """
            if not user_id_identifier_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing user_identifier value",
                )

            self.user_id_identifier = user_id_identifier_value
            response = JSONResponse(
                status_code=status.HTTP_200_OK, content={"status": "success"}
            )
            response.set_cookie(
                key="user_id_identifier",
                value=user_id_identifier_value.user_id,
                secure=True,
                httponly=True,
                expires=datetime.now(timezone.utc) + timedelta(hours=1),
            )

            return response

        @self.app.get(PING_ENDPOINT)
        async def _handle_ping() -> JSONResponse:
            """
            サーバーの準備状態を確認するヘルスチェックエンドポイント。

            Returns:
                dict: サーバーが動作中であることを示すシンプルなステータスレスポンス
            """
            return JSONResponse(
                status_code=status.HTTP_200_OK, content={"status": "success"}
            )

        def _try_parse_identity_sdk_config() -> Optional[str]:
            try:
                with open(".agentcore.json", encoding="utf-8") as agent_config:
                    config = json.load(agent_config)
                    return config.get("user_id")
            except Exception as e:
                logger.debug(
                    f"'.agentcore.json' からの Identity SDK 設定のパースに失敗: {repr(e)}"
                )
                return None

        def _get_user_identifier(
            user_id_identifier: Optional[str] = None,
        ) -> Optional[UserIdIdentifier]:
            """
            フォールバックロジックでユーザー識別子を取得します。

            優先順位:
            1. ブラウザの Cookie 値（パラメータとして渡される）
            2. サーバーメモリの値（インスタンス属性）
            3. Identity SDK 設定のパース

            Args:
                user_id_identifier: ブラウザ Cookie からのオプションのユーザー ID

            Returns:
                UserIdIdentifier インスタンス、または有効な識別子が見つからない場合は None
            """
            if user_id_identifier:
                return UserIdIdentifier(user_id=user_id_identifier)

            if self.user_id_identifier:
                return self.user_id_identifier

            user_id = _try_parse_identity_sdk_config()
            if user_id:
                return UserIdIdentifier(user_id=user_id)

            return None

        @self.app.get(OAUTH2_CALLBACK_ENDPOINT)
        async def _handle_oauth2_callback(
            session_id: str, user_id_identifier: Annotated[str | None, Cookie()] = None
        ) -> HTMLResponse:
            """
            外部プロバイダーからの OAuth2 コールバックを処理します。

            これは、ユーザー認可後に外部 OAuth プロバイダー（Google、Github など）が
            リダイレクトするコアエンドポイントです。session_id パラメータを受け取り、
            それを使用して AgentCore Identity との OAuth フローを完了します。

            OAuth フローのコンテキスト:
            1. ユーザーが AgentCore Identity が生成した認可 URL をクリック
            2. ユーザーが外部プロバイダー（Google、Github など）でアクセスを認可
            3. プロバイダーが session_id を含めてこのコールバックにリダイレクト
            4. このハンドラーが AgentCore Identity を呼び出してフローを完了

            Args:
                session_id (str): OAuth プロバイダーリダイレクトからのセッション識別子
                user_id_identifier (str): ブラウザ Cookie に保存された UserId

            Returns:
                dict: OAuth フロー完了を示す成功メッセージ

            Raises:
                HTTPException: session_id が欠落しているか user_id_identifier が設定されていない場合
            """
            # Validate that session_id parameter is present
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing session_id url query parameter",
                )

            # use browser cookie value if available, otherwise, use value stored on the server memory or config
            user_identifier = _get_user_identifier(user_id_identifier)

            # This is required to bind the OAuth session to the correct user.
            if not user_identifier:
                logger.error("ユーザー識別子が設定されていません")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No user identifier configured",
                )

            # Complete the OAuth flow by calling AgentCore Identity service
            # This associates the OAuth session with the user and retrieves access tokens
            self.identity_client.complete_resource_token_auth(
                session_uri=session_id, user_identifier=user_identifier
            )

            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>OAuth2 Success</title>
                <style>
                    body {
                        margin: 0;
                        padding: 0;
                        height: 100vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        font-family: Arial, sans-serif;
                        background-color: #f5f5f5;
                    }
                    .container {
                        text-align: center;
                        padding: 2rem;
                        background-color: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    }
                    h1 {
                        color: #28a745;
                        margin: 0;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Completed OAuth2 3LO flow successfully</h1>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=200)

    def get_app(self) -> FastAPI:
        """
        設定済みの FastAPI アプリケーションインスタンスを取得します。

        Returns:
            FastAPI: すべてのルートが設定されたアプリケーション
        """
        return self.app


def get_oauth2_callback_url() -> str:
    """
    外部プロバイダー用の完全な OAuth2 コールバック URL を生成します。

    この URL はリダイレクト URI として外部 OAuth プロバイダー（Google、Github など）に
    登録されます。ユーザー認可後、プロバイダーは session_id パラメータを含めて
    ユーザーのブラウザをこの URL にリダイレクトします。

    Returns:
        str: 完全なコールバック URL（例: "http://localhost:9090/oauth2/callback"）

    使用例:
        この URL は通常、以下の場合に使用されます:
        1. AgentCore Identity で OAuth2 認証情報プロバイダーを設定する場合
        2. 外部 OAuth プロバイダーにリダイレクト URI を登録する場合
        3. ワークロード ID の許可された戻り URL を設定する場合
    """
    return f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{OAUTH2_CALLBACK_ENDPOINT}"


def store_user_id_in_oauth2_callback_server(user_id_value: str):
    if user_id_value:
        response = requests.post(
            f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{USER_IDENTIFIER_ENDPOINT}",
            json={"user_id": user_id_value},
            timeout=2,
        )
        response.raise_for_status()
    else:
        logger.error("無視: 無効な user_id が指定されました...")


def wait_for_oauth2_server_to_be_ready(
    duration: timedelta = timedelta(seconds=40),
) -> bool:
    """
    OAuth2 コールバックサーバーが準備完了してレスポンシブになるのを待機します。

    この関数は、サーバーのヘルスチェックエンドポイントが正常に応答するか
    タイムアウトに達するまでポーリングします。OAuth フローを開始する前に
    サーバーが準備完了していることを確認するために不可欠です。

    Args:
        duration (timedelta): サーバー準備を待機する最大時間
                             デフォルトは 40 秒

    Returns:
        bool: タイムアウト内にサーバーが準備完了した場合は True、そうでない場合は False

    使用コンテキスト:
        OAuth2 コールバックサーバープロセスを開始した後、OAuth フローを
        トリガーする可能性のあるエージェント呼び出しを進める前に、
        OAuth コールバックを処理する準備ができていることを確認するために呼び出されます。

    例:
        # サーバープロセスを開始
        server_process = subprocess.Popen([...])

        # 準備完了を待機
        if wait_for_oauth2_server_to_be_ready():
            # OAuth 対応操作を続行
            invoke_agent()
        else:
            # サーバー起動失敗を処理
            server_process.terminate()
    """
    logger.info("OAuth2 コールバックサーバーの準備を待機中...")
    timeout_in_seconds = duration.seconds

    start_time = time.time()
    while time.time() - start_time < timeout_in_seconds:
        try:
            # Ping the server's health check endpoint
            response = requests.get(
                f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{PING_ENDPOINT}",
                timeout=2,
            )
            if response.status_code == status.HTTP_200_OK:
                logger.info("OAuth2 コールバックサーバーの準備完了！")
                return True
        except requests.exceptions.RequestException:
            # Server not ready yet, continue waiting
            pass

        time.sleep(2)
        elapsed = int(time.time() - start_time)

        # Log progress every 10 seconds to show we're still waiting
        if elapsed % 10 == 0 and elapsed > 0:
            logger.info(f"まだ待機中... ({elapsed}/{timeout_in_seconds}秒)")

    logger.error(
        f"タイムアウト: OAuth2 コールバックサーバーが {timeout_in_seconds} 秒後も準備できませんでした"
    )
    return False


def main():
    """
    OAuth2 コールバックサーバーをスタンドアロンアプリケーションとして実行するためのメインエントリーポイント。

    コマンドライン引数をパースし、uvicorn を使用して FastAPI サーバーを起動します。
    サーバーは localhost:9090 で実行され、指定された AWS リージョンの
    OAuth2 コールバックを処理します。

    コマンドラインの使用方法:
        python oauth2_callback_server.py --region us-east-1

    サーバーは手動で終了するまで実行され、指定されたリージョン内の
    すべての AgentCore エージェントの OAuth2 コールバックを処理します。
    """
    parser = argparse.ArgumentParser(description="OAuth2 Callback Server")
    parser.add_argument(
        "-r", "--region", type=str, required=True, help="AWS Region (e.g. us-east-1)"
    )

    args = parser.parse_args()
    oauth2_callback_server = OAuth2CallbackServer(region=args.region)

    # Start the FastAPI server using uvicorn
    # Server runs on localhost only for security (not exposed externally)
    uvicorn.run(
        oauth2_callback_server.get_app(),
        host="127.0.0.1",
        port=OAUTH2_CALLBACK_SERVER_PORT,
    )


if __name__ == "__main__":
    main()
