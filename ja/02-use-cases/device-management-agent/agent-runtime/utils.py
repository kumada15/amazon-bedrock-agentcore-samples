"""
デバイス管理システム - ユーティリティ関数

このモジュールは、デバイス管理システムのエージェントランタイム用の
ユーティリティ関数とクラスを提供します。AWS リージョン設定、
Amazon Cognito トークン管理、および OAuth 認証ヘルパーを含みます。

主要コンポーネント:
    - AWS リージョン設定ユーティリティ
    - CognitoTokenManager: 自動リフレッシュ機能付き OAuth トークン管理
    - MCP サーバー通信用の認証ヘルパー
    - 環境変数の検証と設定

クラス:
    CognitoTokenManager: 自動リフレッシュ機能付き OAuth トークンを管理

関数:
    get_aws_region(): 環境変数から AWS リージョンを取得
    get_oauth_token(): MCP サーバー認証用の有効な OAuth トークンを取得

環境変数:
    AWS_REGION: AWS リージョン（デフォルトは us-west-2）
    COGNITO_DOMAIN: Amazon Cognito ドメイン URL
    COGNITO_CLIENT_ID: OAuth クライアント ID
    COGNITO_CLIENT_SECRET: OAuth クライアントシークレット

使用例:
    >>> token_manager = CognitoTokenManager()
    >>> token = token_manager.get_valid_token()
    >>> print(f"トークン: {token}")
"""
import os
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

def get_aws_region() -> str:
    """
    環境変数から AWS リージョンを取得します。

    Returns:
        str: AWS リージョン名、指定されていない場合は 'us-west-2' をデフォルト

    環境変数:
        AWS_REGION: サービス呼び出しに使用する AWS リージョン
    """
    return os.getenv("AWS_REGION", "us-west-2")


class CognitoTokenManager:
    """
    自動リフレッシュ機能付きで Amazon Cognito OAuth トークンを管理します。

    このクラスは Amazon Cognito との OAuth 2.0 クライアント認証情報フローを処理し、
    トークンの有効期限が切れた場合は自動的にリフレッシュし、認証リクエストを
    最小限に抑えるために有効なトークンをキャッシュします。

    Attributes:
        token (str): 現在の OAuth アクセストークン
        token_expires_at (datetime): トークンの有効期限タイムスタンプ
        cognito_domain (str): Amazon Cognito ドメイン URL
        client_id (str): OAuth クライアント ID
        client_secret (str): OAuth クライアントシークレット

    Raises:
        ValueError: 必須の環境変数が不足している場合

    Example:
        >>> manager = CognitoTokenManager()
        >>> token = manager.get_valid_token()
        >>> # 有効期限切れの場合、トークンは自動的にリフレッシュされます
    """
    
    def __init__(self):
        self.token = None
        self.token_expires_at = None
        self.cognito_domain = os.getenv("COGNITO_DOMAIN")
        self.client_id = os.getenv("COGNITO_CLIENT_ID")
        self.client_secret = os.getenv("COGNITO_CLIENT_SECRET")
        
        if not all([self.cognito_domain, self.client_id, self.client_secret]):
            raise ValueError("Missing required Cognito environment variables: COGNITO_DOMAIN, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET")
    
    def _fetch_new_token(self) -> Optional[str]:
        """Cognito から新しい OAuth トークンを取得します"""
        try:
            url = f"https://{self.cognito_domain}/oauth2/token"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            logger.info(f"{url} から新しいトークンをリクエストしています")
            response = requests.post(url, headers=headers, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour
                
                # Set expiration time with a 5-minute buffer
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                
                logger.info("新しい OAuth トークンを正常に取得しました")
                return access_token
            else:
                logger.error(f"トークンの取得に失敗しました: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"OAuth トークンの取得中にエラーが発生しました: {str(e)}")
            return None
    
    def _is_token_expired(self) -> bool:
        """現在のトークンが期限切れまたは期限切れ間近かどうかを確認します"""
        if not self.token or not self.token_expires_at:
            return True
        return datetime.now() >= self.token_expires_at
    
    def get_token(self) -> Optional[str]:
        """有効な OAuth トークンを取得し、必要に応じてリフレッシュします"""
        if self._is_token_expired():
            logger.info("トークンが期限切れまたは存在しないため、新しいトークンを取得しています")
            self.token = self._fetch_new_token()
        
        return self.token

# Global token manager instance
_token_manager = None

def get_oauth_token() -> Optional[str]:
    """Cognito 認証用の有効な OAuth トークンを取得します"""
    global _token_manager
    
    try:
        if _token_manager is None:
            _token_manager = CognitoTokenManager()
        
        return _token_manager.get_token()
    except Exception as e:
        logger.error(f"OAuth トークンの取得中にエラーが発生しました: {str(e)}")
        return None

def get_auth_headers() -> dict:
    """Bearer トークン付きの認証ヘッダーを取得します"""
    token = get_oauth_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    else:
        logger.warning("認証に有効なトークンがありません")
        return {}

def create_agentcore_client():
    """AgentCore クライアントと boto セッションを作成します"""
    import boto3
    
    # Create boto session
    boto_session = boto3.Session(region_name=os.getenv("AWS_REGION", "us-west-2"))
    
    # Create bedrock-agentcore client directly using boto3
    agentcore_client = boto_session.client(
        'bedrock-agentcore',
        region_name=os.getenv("AWS_REGION", "us-west-2")
        #endpoint_url=os.getenv("ENDPOINT_URL")
    )
    
    return boto_session, agentcore_client

def get_gateway_endpoint(agentcore_client, gateway_id: str) -> str:
    """Gateway ID から Gateway エンドポイント URL を取得します"""
    try:
        # Use the correct boto3 method for bedrock-agentcore
        response = agentcore_client.describe_gateway(gatewayId=gateway_id)
        endpoint = response.get('gateway', {}).get('gatewayEndpoint', '')
        return endpoint
    except Exception as e:
        logger.error(f"Gateway エンドポイントの取得中にエラーが発生しました: {str(e)}")
        # If we can't get the endpoint, return the one from environment
        return os.getenv("gateway_endpoint", "")