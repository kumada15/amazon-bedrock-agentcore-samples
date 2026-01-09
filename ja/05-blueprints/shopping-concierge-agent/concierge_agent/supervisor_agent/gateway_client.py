"""
AgentCore Gateway 統合用の Gateway クライアントユーティリティ。
OAuth2 認証と MCP クライアント作成を処理します。
"""

import os
import boto3
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

# トークンキャッシュ
_token_cache: Optional[str] = None
_token_expiry: Optional[datetime] = None


def get_ssm_parameter(parameter_name: str, region: str) -> str:
    """
    SSM Parameter Store からパラメータを取得する。

    Args:
        parameter_name: SSM パラメータ名
        region: AWS リージョン

    Returns:
        パラメータ値
    """
    ssm = boto3.client("ssm", region_name=region)
    try:
        response = ssm.get_parameter(Name=parameter_name)
        return response["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        raise ValueError(f"SSM parameter not found: {parameter_name}")
    except Exception as e:
        raise ValueError(f"Failed to retrieve SSM parameter {parameter_name}: {e}")


def get_gateway_access_token() -> str:
    """
    Gateway 認証用の OAuth2 アクセストークンを取得する。
    トークンはキャッシュされ、自動的に更新されます。

    Returns:
        Bearer トークン文字列
    """
    global _token_cache, _token_expiry

    # キャッシュされたトークンがまだ有効であれば返す
    if _token_cache and _token_expiry and datetime.now() < _token_expiry:
        logger.debug("キャッシュされた Gateway トークンを使用")
        return _token_cache

    logger.info("新しい Gateway OAuth2 トークンを取得中...")

    # 環境変数から設定を取得
    client_id = os.environ.get("GATEWAY_CLIENT_ID")
    user_pool_id = os.environ.get("GATEWAY_USER_POOL_ID")
    scope = os.environ.get("GATEWAY_SCOPE", "concierge-gateway/invoke")
    region = os.environ.get("AWS_REGION", "us-east-1")

    if not client_id or not user_pool_id:
        raise ValueError("GATEWAY_CLIENT_ID and GATEWAY_USER_POOL_ID must be set")

    try:
        # Cognito からクライアントシークレットを取得
        cognito = boto3.client("cognito-idp", region_name=region)
        response = cognito.describe_user_pool_client(
            UserPoolId=user_pool_id, ClientId=client_id
        )
        client_secret = response["UserPoolClient"]["ClientSecret"]

        # Cognito ドメインを取得
        pool_response = cognito.describe_user_pool(UserPoolId=user_pool_id)
        domain = pool_response["UserPool"].get("Domain")
        if not domain:
            raise ValueError("Cognito ドメインが設定されていません")

        # トークンをリクエスト
        token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"

        token_response = requests.post(
            token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            },
            timeout=10,
        )
        token_response.raise_for_status()

        data = token_response.json()
        _token_cache = data["access_token"]

        # (expires_in - 600) 秒間キャッシュ（10分のバッファ）
        expires_in = data.get("expires_in", 3600)
        _token_expiry = datetime.now() + timedelta(seconds=expires_in - 600)

        logger.info(f"Gateway トークンを取得しました。有効期限: {expires_in}秒")
        return _token_cache

    except Exception as e:
        logger.error(f"Gateway トークンの取得に失敗しました: {e}")
        raise


def get_gateway_client(tool_filter_pattern: str, prefix: str = "gateway") -> MCPClient:
    """
    指定されたツールフィルタリングを持つ Gateway MCP クライアントを取得する。

    Args:
        tool_filter_pattern: ツールをフィルタリングする正規表現パターン（例: "^carttools___"）
        prefix: ツール名のプレフィックス（デフォルト: "gateway"）

    Returns:
        指定されたツールにフィルタリングされた MCPClient

    Example:
        cart_client = get_gateway_client("^carttools___")
    """
    import re

    region = os.environ.get("AWS_REGION", "us-east-1")
    deployment_id = os.getenv("DEPLOYMENT_ID", "default")

    gateway_url = get_ssm_parameter(
        f"/concierge-agent/{deployment_id}/gateway-url", region
    )
    access_token = get_gateway_access_token()

    logger.info(
        f"Gateway MCP クライアントを作成中: フィルター: {tool_filter_pattern}, プレフィックス: {prefix}"
    )

    tool_filters = {"allowed": [re.compile(tool_filter_pattern)]}

    client = MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url, headers={"Authorization": f"Bearer {access_token}"}
        ),
        prefix=prefix,
        tool_filters=tool_filters,
    )

    logger.info(f"Gateway MCP クライアントを作成しました。フィルター: {tool_filter_pattern}")
    return client
