"""
Amazon Bedrock AgentCore Identity 用 Authorization Code フロー（3LO）の OAuth2 コールバックサーバーサンプル

このモジュールは、AgentCore Identity の OAuth2 3-legged（3LO）認証フローを処理する
ローカルコールバックサーバーを実装します。ユーザーのブラウザ、外部 OAuth プロバイダー
（Google、Github など）、および AgentCore Identity サービス間の仲介役として機能します。

主要コンポーネント:
- localhost:9090 で動作する FastAPI サーバー
- 外部プロバイダーからの OAuth2 コールバックリダイレクトを処理
- ユーザートークンの保存とセッション完了を管理
- 準備完了確認用のヘルスチェックエンドポイントを提供

使用コンテキスト:
このサーバーは、認証済みユーザーに代わって外部リソース（Google カレンダー、Github リポジトリなど）に
アクセスする必要がある AgentCore Runtime 上で動作するエージェントと連携して使用されます。
典型的なフローは以下の通りです：
1. エージェントが外部リソースへのアクセスをリクエスト
2. ユーザーが同意のために OAuth プロバイダーにリダイレクトされる
3. プロバイダーがこのコールバックサーバーにリダイレクト
4. サーバーが AgentCore Identity との認証フローを完了
"""

import time
import uvicorn
import logging
import argparse
import requests
import json

from datetime import timedelta
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from bedrock_agentcore.services.identity import IdentityClient, UserTokenIdentifier

# OAuth2 コールバックサーバーの設定定数
OAUTH2_CALLBACK_SERVER_PORT = 9090  # コールバックサーバーがリッスンするポート
PING_ENDPOINT = "/ping"  # ヘルスチェックエンドポイント
OAUTH2_CALLBACK_ENDPOINT = (
    "/oauth2/callback"  # プロバイダーリダイレクト用の OAuth2 コールバックエンドポイント
)
USER_IDENTIFIER_ENDPOINT = (
    "/userIdentifier/token"  # ユーザートークン識別子を保存するエンドポイント
)

logger = logging.getLogger(__name__)


def _is_workshop_studio() -> bool:
    """
    SageMaker Workshop Studio 環境で実行中かどうかを確認します。

    Returns:
        bool: Workshop Studio で実行中の場合は True、それ以外は False
    """
    try:
        with open("/opt/ml/metadata/resource-metadata.json", "r") as file:
            json.load(file)
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def get_oauth2_callback_base_url() -> str:
    """
    外部 OAuth プロバイダーリダイレクト用のベース URL を取得します（ブラウザからアクセス可能）。

    これは外部 OAuth プロバイダー（GitHub、Google など）がリダイレクトする URL です。
    OAuth セッションバインディングが機能するには、ユーザーのブラウザがこの URL にアクセスできる必要があります。

    環境検出:
    - Workshop Studio: SageMaker プロキシ URL を返します (https://domain.studio.sagemaker.aws/proxy/9090)
    - ローカル開発: localhost URL を返します (http://localhost:9090)

    Returns:
        str: OAuth コールバック用のブラウザアクセス可能なベース URL

    用途:
        この URL は以下の場合に使用されます：
        1. Workload identity の allowedResourceOauth2ReturnUrls 登録
        2. エージェントデコレーターの callback_url パラメータ
        3. ユーザーのブラウザがコールバックサーバーに到達する必要があるシナリオ
    """
    if not _is_workshop_studio():
        base_url = f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}"
        logger.info(f"外部 OAuth コールバック ベース URL (ローカル): {base_url}")
        return base_url

    try:
        import boto3

        with open("/opt/ml/metadata/resource-metadata.json", "r") as file:
            data = json.load(file)
            domain_id = data["DomainId"]
            space_name = data["SpaceName"]

        sagemaker_client = boto3.client("sagemaker")
        response = sagemaker_client.describe_space(
            DomainId=domain_id, SpaceName=space_name
        )
        base_url = response["Url"] + f"/proxy/{OAUTH2_CALLBACK_SERVER_PORT}"
        logger.info(f"外部 OAuth コールバック ベース URL (SageMaker): {base_url}")
        return base_url
    except Exception as e:
        logger.warning(
            f"SageMaker プロキシ URL の取得エラー: {e}。localhost にフォールバックします"
        )
        return f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}"


def _get_internal_base_url() -> str:
    """
    内部通信用のベース URL を取得します（ノートブック/Streamlit → コールバックサーバー）。

    ノートブック/Streamlit と OAuth2 コールバックサーバーは同じ環境で実行されるため、
    常に localhost になります（ローカル開発では同じマシン、SageMaker では同じコンテナ）。

    Returns:
        str: サーバー間通信用の内部ベース URL（常に localhost）

    用途:
        この URL は以下の場合に使用されます：
        1. ユーザートークンの保存 (POST /userIdentifier/token)
        2. ヘルスチェック (GET /ping)
        3. 同じ実行環境内での内部通信
    """
    return f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}"


class OAuth2CallbackServer:
    """
    AgentCore Identity との 3-legged OAuth フローを処理する OAuth2 コールバックサーバー。

    このサーバーは、ユーザー認可後に外部 OAuth プロバイダー（Google、Github など）が
    リダイレクトするローカルコールバックエンドポイントとして機能します。
    AgentCore Identity サービスと連携して OAuth フローの完了を管理します。

    サーバーは以下を維持します：
    - API 通信用の AgentCore Identity クライアント
    - セッションバインディング用のユーザートークン識別子
    - ルートが設定された FastAPI アプリケーション
    """

    def __init__(self, region: str):
        """
        OAuth2 コールバックサーバーを初期化します。

        Args:
            region (str): AgentCore Identity サービスがデプロイされている AWS リージョン
        """
        # 指定されたリージョン用の AgentCore Identity クライアントを初期化
        self.identity_client = IdentityClient(region=region)

        # ユーザートークン識別子の保存 - OAuth セッションを特定のユーザーにバインドするために使用
        # これは OAuth フロー開始前に USER_IDENTIFIER_ENDPOINT 経由で設定されます
        self.user_token_identifier = None

        # FastAPI アプリケーションインスタンスを作成
        self.app = FastAPI()

        # すべての HTTP ルートを設定
        self._setup_routes()

    def _setup_routes(self):
        """
        OAuth2 コールバックサーバーの FastAPI ルートを設定します。

        3つのエンドポイントを設定します：
        1. POST /userIdentifier/token - セッションバインディング用のユーザートークン識別子を保存
        2. GET /ping - ヘルスチェックエンドポイント
        3. GET /oauth2/callback - プロバイダーリダイレクト用の OAuth2 コールバックハンドラー
        """

        @self.app.post(USER_IDENTIFIER_ENDPOINT)
        async def _store_user_token(user_token_identifier_value: UserTokenIdentifier):
            """
            OAuth セッションバインディング用のユーザートークン識別子を保存します。

            このエンドポイントは、今後の OAuth セッションを特定のユーザーに関連付けるために、
            OAuth フロー開始前に呼び出されます。ユーザートークン識別子は通常、
            インバウンド認証からのユーザーの JWT トークンから派生します。

            Args:
                user_token_identifier_value: ユーザー識別情報を含む UserTokenIdentifier オブジェクト
            """
            self.user_token_identifier = user_token_identifier_value

        @self.app.get(PING_ENDPOINT)
        async def _handle_ping():
            """
            サーバーの準備完了を確認するヘルスチェックエンドポイント。

            Returns:
                dict: サーバーが動作中であることを示すシンプルなステータスレスポンス
            """
            return {"status": "success"}

        @self.app.get(OAUTH2_CALLBACK_ENDPOINT)
        async def _handle_oauth2_callback(session_id: str):
            """
            外部プロバイダーからの OAuth2 コールバックを処理します。

            これは、ユーザー認可後に外部 OAuth プロバイダー（Google、Github など）がリダイレクトする
            コアエンドポイントです。session_id パラメータを受け取り、それを使用して
            AgentCore Identity との OAuth フローを完了します。

            OAuth フローのコンテキスト：
            1. ユーザーが AgentCore Identity によって生成された認可 URL をクリック
            2. ユーザーが外部プロバイダー（例：Google、Github）でアクセスを認可
            3. プロバイダーが session_id 付きでこのコールバックにリダイレクト
            4. このハンドラーが AgentCore Identity を呼び出してフローを完了

            Args:
                session_id (str): OAuth プロバイダーリダイレクトからのセッション識別子

            Returns:
                dict: OAuth フロー完了を示す成功メッセージ

            Raises:
                HTTPException: session_id が欠落しているか、user_token_identifier が設定されていない場合
            """
            # session_id パラメータが存在することを検証
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="session_id クエリパラメータがありません",
                )

            # ユーザートークン識別子が事前に保存されていることを確認
            # これは OAuth セッションを正しいユーザーにバインドするために必要です
            if not self.user_token_identifier:
                logger.error("ユーザートークン識別子が設定されていません")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="内部サーバーエラー",
                )

            # AgentCore Identity サービスを呼び出して OAuth フローを完了
            # これにより OAuth セッションがユーザーに関連付けられ、アクセストークンが取得されます
            self.identity_client.complete_resource_token_auth(
                session_uri=session_id, user_identifier=self.user_token_identifier
            )

            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>OAuth2 成功</title>
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
                    <h1>OAuth2 3LO フローが正常に完了しました</h1>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=200)

    def get_app(self) -> FastAPI:
        """
        設定された FastAPI アプリケーションインスタンスを取得します。

        Returns:
            FastAPI: すべてのルートが設定されたアプリケーション
        """
        return self.app


def get_oauth2_callback_url() -> str:
    """
    外部プロバイダー用の完全な OAuth2 コールバック URL を生成します（ブラウザからアクセス可能）。

    この URL は workload identity に登録され、OAuth 認可後にユーザーのブラウザを
    リダイレクトするために AgentCore によって使用されます。ユーザーのブラウザからアクセス可能である必要があります。

    環境対応の動作：
    - ローカル開発: http://localhost:9090/oauth2/callback を返します
    - SageMaker Studio: https://domain.studio.sagemaker.aws/proxy/9090/oauth2/callback を返します

    Returns:
        str: エンドポイントパスを含む完全なブラウザアクセス可能なコールバック URL

    用途:
        この URL は以下の場合に使用されます：
        1. workload identity で allowedResourceOauth2ReturnUrls を登録する場合
        2. @requires_access_token デコレーターに callback_url を渡す場合
        3. AgentCore がブラウザをコールバックにリダイレクトする必要があるシナリオ
    """
    base_url = get_oauth2_callback_base_url()
    return f"{base_url}{OAUTH2_CALLBACK_ENDPOINT}"


def store_token_in_oauth2_callback_server(user_token_value: str):
    """
    実行中の OAuth2 コールバックサーバーにユーザートークン識別子を保存します（内部通信）。

    この関数は、OAuth フロー開始前にユーザーのトークン識別子を保存するために
    コールバックサーバーに POST リクエストを送信します。トークン識別子は
    OAuth セッションを特定のユーザーにバインドするために使用されます。

    同じ実行環境（同じマシンまたは同じコンテナ）内でのサーバー間通信のため、
    内部ベース URL（常に localhost）を使用します。

    Args:
        user_token_value (str): OAuth フローでユーザーを識別するために使用される
                               ユーザートークン（通常は Cognito からの JWT アクセストークン）

    使用コンテキスト:
        OAuth フローを開始する前に呼び出され、コールバックサーバーが
        OAuth セッションがどのユーザーに属するかを認識できるようにします。
        マルチユーザーシナリオでの適切なセッションバインディングに不可欠です。

    例:
        # OAuth を必要とするエージェントを呼び出す前に
        bearer_token = reauthenticate_user(client_id)
        store_token_in_oauth2_callback_server(bearer_token)
    """
    if user_token_value:
        base_url = _get_internal_base_url()
        requests.post(
            f"{base_url}{USER_IDENTIFIER_ENDPOINT}",
            json={"user_token": user_token_value},
            timeout=2,
        )
    else:
        logger.error("無視: 無効な user_token が提供されました...")


def wait_for_oauth2_server_to_be_ready(
    duration: timedelta = timedelta(seconds=40),
) -> bool:
    """
    OAuth2 コールバックサーバーが準備完了してレスポンシブになるまで待機します（内部通信）。

    この関数は、サーバーのヘルスチェックエンドポイントが正常に応答するか、
    タイムアウトに達するまでポーリングします。OAuth フローを開始する前に
    サーバーが準備完了していることを確認するために不可欠です。

    同じ実行環境（同じマシンまたは同じコンテナ）内でのサーバー間通信のため、
    内部ベース URL（常に localhost）を使用します。

    Args:
        duration (timedelta): サーバー準備完了を待機する最大時間
                             デフォルトは40秒

    Returns:
        bool: タイムアウト内にサーバーが準備完了した場合は True、それ以外は False

    使用コンテキスト:
        OAuth2 コールバックサーバープロセスを開始した後に呼び出され、
        OAuth フローをトリガーする可能性のあるエージェント呼び出しを続行する前に
        OAuth コールバックを処理する準備ができていることを確認します。

    例:
        # サーバープロセスを開始
        server_process = subprocess.Popen([...])

        # 準備完了を待機
        if wait_for_oauth2_server_to_be_ready():
            # OAuth 対応の操作を続行
            invoke_agent()
        else:
            # サーバー起動失敗を処理
            server_process.terminate()
    """
    logger.info("OAuth2 コールバックサーバーの準備完了を待機中...")
    base_url = _get_internal_base_url()
    timeout_in_seconds = duration.seconds

    start_time = time.time()
    while time.time() - start_time < timeout_in_seconds:
        try:
            # サーバーのヘルスチェックエンドポイントに ping を送信
            response = requests.get(
                f"{base_url}{PING_ENDPOINT}",
                timeout=2,
            )
            if response.status_code == status.HTTP_200_OK:
                logger.info("OAuth2 コールバックサーバーの準備が完了しました！")
                return True
        except requests.exceptions.RequestException:
            # サーバーがまだ準備できていない、待機を継続
            pass

        time.sleep(2)
        elapsed = int(time.time() - start_time)

        # 待機中であることを示すために10秒ごとに進捗をログ出力
        if elapsed % 10 == 0 and elapsed > 0:
            logger.info(f"引き続き待機中... ({elapsed}/{timeout_in_seconds}秒)")

    logger.error(
        f"タイムアウト: OAuth2 コールバックサーバーが {timeout_in_seconds} 秒経過しても準備完了しませんでした"
    )
    return False


def main():
    """
    OAuth2 コールバックサーバーをスタンドアロンアプリケーションとして実行するメインエントリーポイント。

    コマンドライン引数を解析し、uvicorn を使用して FastAPI サーバーを起動します。
    サーバーは指定された AWS リージョンの OAuth2 コールバックを処理します。

    環境対応のホストバインディング：
    - ローカル開発: 127.0.0.1 にバインド（セキュリティのため localhost のみ）
    - SageMaker Studio: 0.0.0.0 にバインド（プロキシがサーバーに到達できるようにする）

    コマンドラインの使用法:
        python oauth2_callback_server.py --region us-east-1

    サーバーは手動で終了するまで実行され、指定されたリージョンの
    AgentCore エージェントの OAuth2 コールバックを処理します。
    """
    parser = argparse.ArgumentParser(description="OAuth2 コールバックサーバー")
    parser.add_argument(
        "-r", "--region", type=str, required=True, help="AWS リージョン（例：us-east-1）"
    )

    args = parser.parse_args()
    oauth2_callback_server = OAuth2CallbackServer(region=args.region)

    # 環境に基づいてホストバインディングを決定
    # SageMaker では、プロキシがサーバーに到達できるように 0.0.0.0 にバインド
    # ローカル開発では、セキュリティのため 127.0.0.1 にバインド
    host = "0.0.0.0" if _is_workshop_studio() else "127.0.0.1"
    base_url = get_oauth2_callback_base_url()

    logger.info(
        f"OAuth2 コールバックサーバーを {host}:{OAUTH2_CALLBACK_SERVER_PORT} で起動しています"
    )
    logger.info(f"外部コールバック URL: {base_url}{OAUTH2_CALLBACK_ENDPOINT}")

    # uvicorn を使用して FastAPI サーバーを起動
    uvicorn.run(
        oauth2_callback_server.get_app(),
        host=host,
        port=OAUTH2_CALLBACK_SERVER_PORT,
    )


if __name__ == "__main__":
    main()
