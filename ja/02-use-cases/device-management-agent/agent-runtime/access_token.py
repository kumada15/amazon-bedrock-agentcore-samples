"""
Amazon Cognito アクセストークン管理モジュール

このモジュールは、デバイス管理システムの認証機能を提供し、
異なるデプロイ環境（ローカル開発 vs コンテナ化されたランタイム）向けの
フォールバックメカニズム付きで Amazon Cognito から OAuth トークン取得を処理します。

このモジュールは2つの認証方法をサポートします:
1. Amazon Bedrock AgentCore ワークロード ID（推奨）
2. 直接 Amazon Cognito OAuth クライアント認証情報フロー（フォールバック）

必須環境変数:
    COGNITO_DOMAIN: Amazon Cognito ドメイン URL
    COGNITO_CLIENT_ID: OAuth クライアント ID
    COGNITO_CLIENT_SECRET: OAuth クライアントシークレット

使用例:
    >>> token = get_gateway_access_token()
    >>> print(f"アクセストークン: {token}")
"""

import os
import requests
from dotenv import load_dotenv
from bedrock_agentcore.identity.auth import requires_access_token

load_dotenv()


def get_cognito_token_direct():
    """
    Amazon Cognito から直接 OAuth アクセストークンを取得します。

    この関数は、Amazon Cognito からアクセストークンを取得するための
    OAuth 2.0 クライアント認証情報フローを実装します。Amazon Bedrock
    AgentCore ワークロード ID が利用できない場合（例：コンテナ化された
    環境）のフォールバックとして使用されます。

    Returns:
        str: 成功した場合は OAuth アクセストークン、失敗した場合は None

    Raises:
        ValueError: 必須の環境変数が不足している場合
        requests.RequestException: Cognito への HTTP リクエストが失敗した場合

    環境変数:
        COGNITO_DOMAIN: Amazon Cognito ドメイン URL（例: https://domain.auth.region.amazoncognito.com）
        COGNITO_CLIENT_ID: Cognito App Client からの OAuth クライアント ID
        COGNITO_CLIENT_SECRET: Cognito App Client からの OAuth クライアントシークレット
    """
    try:
        # Get Cognito configuration from environment
        cognito_domain = os.getenv("COGNITO_DOMAIN")
        client_id = os.getenv("COGNITO_CLIENT_ID")
        client_secret = os.getenv("COGNITO_CLIENT_SECRET")
        
        print(f"デバッグ - Cognito ドメイン: {cognito_domain}")
        print(f"デバッグ - クライアント ID: {client_id}")
        print(f"デバッグ - クライアントシークレット: {'***' if client_secret else 'None'}")
        
        if not all([cognito_domain, client_id, client_secret]):
            missing = []
            if not cognito_domain:
                missing.append("COGNITO_DOMAIN")
            if not client_id:
                missing.append("COGNITO_CLIENT_ID")
            if not client_secret:
                missing.append("COGNITO_CLIENT_SECRET")
            raise ValueError(f"Missing Cognito configuration: {', '.join(missing)}")
        
        # Prepare token request
        token_url = f"{cognito_domain}/oauth2/token"
        print(f"デバッグ - トークン URL: {token_url}")
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'device-management-oauth/invoke'
        }
        
        print("デバッグ - トークンリクエストを実行中...")
        # Make token request
        response = requests.post(token_url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        print(f"デバッグ - レスポンスステータス: {response.status_code}")
        print(f"デバッグ - レスポンスヘッダー: {dict(response.headers)}")
        
        token_data = response.json()
        print(f"デバッグ - トークンデータキー: {list(token_data.keys())}")
        access_token = token_data.get('access_token')
        print(f"デバッグ - アクセストークン受信: {'はい' if access_token else 'いいえ'}")
        return access_token
        
    except Exception as e:
        print(f"Cognito トークンの直接取得エラー: {e}")
        import traceback
        traceback.print_exc()
        return None

@requires_access_token(
    provider_name="vgs-identity-provider",
    scopes=[],
    auth_flow="M2M",
)
def get_gateway_access_token_bedrock(access_token: str):
    """
    Amazon Bedrock AgentCore ワークロード ID を使用してアクセストークンを取得します。

    この関数は、ワークロード ID が設定された環境で実行する場合に
    Amazon Bedrock AgentCore ID プロバイダーを使用してアクセストークンを
    取得します。これは本番デプロイメントで推奨される方法です。

    Args:
        access_token (str): AgentCore ID システムによって提供されるアクセストークン

    Returns:
        str: 提供されたアクセストークン（AgentCore からパススルー）

    Note:
        この関数は @requires_access_token でデコレートされており、
        AgentCore ID プロバイダーからの実際のトークン取得を処理します。
    """
    # Note: Not logging actual token for security reasons
    print("Bedrock AgentCore からアクセストークンを受信しました")
    return access_token

def get_gateway_access_token():
    """
    認証方法間の自動フォールバック付きでアクセストークンを取得します。

    これはトークン取得のメインエントリポイントです。最初に Amazon Bedrock
    AgentCore ワークロード ID を試行し（本番環境で推奨）、ワークロード ID が
    利用できない場合は直接 Amazon Cognito OAuth にフォールバックします。

    認証フロー:
        1. Amazon Bedrock AgentCore ワークロード ID を試行
        2. ワークロード ID が失敗した場合、直接 Cognito OAuth にフォールバック
        3. いずれかの方法が成功した場合はトークンを返す
        4. 両方の方法が失敗した場合は例外を発生

    Returns:
        str: Gateway 認証用の有効な OAuth アクセストークン

    Raises:
        Exception: 両方の認証方法が失敗した場合
        ValueError: 必須の環境変数が不足している場合

    Example:
        >>> try:
        ...     token = get_gateway_access_token()
        ...     print("認証に成功しました")
        ... except Exception as e:
        ...     print(f"認証に失敗しました: {e}")
    """
    try:
        # Try bedrock_agentcore method first
        print("bedrock_agentcore 認証を試行中...")
        return get_gateway_access_token_bedrock()
    except ValueError as e:
        if "Workload access token has not been set" in str(e):
            print("Workload アクセストークンが利用できません。直接 Cognito 認証にフォールバックします...")
            # Fall back to direct Cognito token retrieval
            token = get_cognito_token_direct()
            if token:
                print("直接 Cognito 認証でトークンを正常に取得しました")
                return token
            else:
                raise Exception("Failed to obtain token via both bedrock_agentcore and direct Cognito methods")
        else:
            raise e
    except Exception as e:
        print(f"bedrock_agentcore 認証エラー: {e}")
        print("直接 Cognito 認証にフォールバックします...")
        # Fall back to direct Cognito token retrieval
        token = get_cognito_token_direct()
        if token:
            print("直接 Cognito 認証でトークンを正常に取得しました")
            return token
        else:
            raise Exception("bedrock_agentcore と直接 Cognito の両方の方法でトークンの取得に失敗しました")

if __name__ == "__main__":
    token = get_gateway_access_token()
    # Note: Not printing actual token for security reasons
    print(f"トークン取得: {'はい' if token else 'いいえ'}")