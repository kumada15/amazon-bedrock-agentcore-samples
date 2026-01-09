#!/usr/bin/env python3
"""
Cognito トークンジェネレーター

このスクリプトは、クライアント認証情報を使用して Amazon Cognito から OAuth2 アクセストークンを生成し、
AgentCore Gateway で使用するために .access_token ファイルに保存します。
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Any, Dict

import dotenv
import requests

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)


def _get_cognito_token(
    cognito_domain_url: str,
    client_id: str,
    client_secret: str,
    audience: str = "MCPGateway",
) -> Dict[str, Any]:
    """
    クライアント認証情報グラントタイプを使用して Amazon Cognito または Auth0 から OAuth2 トークンを取得します。

    Args:
        cognito_domain_url: 完全な Cognito/Auth0 ドメイン URL
        client_id: アプリクライアント ID
        client_secret: アプリクライアントシークレット
        audience: トークンのオーディエンス（デフォルト: MCPGateway）

    Returns:
        access_token、expires_in、token_type を含むトークンレスポンス
    """
    # トークンエンドポイント URL を構築
    if "auth0.com" in cognito_domain_url:
        url = f"{cognito_domain_url.rstrip('/')}/oauth/token"
        # Auth0 用に JSON フォーマットを使用
        headers = {"Content-Type": "application/json"}
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": audience,
            "grant_type": "client_credentials",
            "scope": "invoke:gateway",
        }
        # Auth0 用に JSON として送信
        response_method = lambda: requests.post(url, headers=headers, json=data)
    else:
        # Cognito フォーマット
        url = f"{cognito_domain_url.rstrip('/')}/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        # Cognito 用にフォームデータとして送信
        response_method = lambda: requests.post(url, headers=headers, data=data)

    try:
        # リクエストを実行
        response = response_method()
        response.raise_for_status()  # Raise exception for bad status codes

        provider_type = "Auth0" if "auth0.com" in cognito_domain_url else "Cognito"
        logging.info(f"Successfully obtained {provider_type} access token")
        return response.json()

    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting token: {e}")
        if hasattr(response, "text") and response.text:
            logging.error(f"Response: {response.text}")
        raise


def _save_access_token(
    token_response: Dict[str, Any], output_file: str = ".access_token"
) -> None:
    """
    アクセストークンをファイルに保存します。

    Args:
        token_response: Cognito からのトークンレスポンス
        output_file: 出力ファイルパス
    """
    access_token = token_response["access_token"]
    Path(output_file).write_text(access_token)
    logging.info(f"Access token saved to {output_file}")
    logging.info(
        f"Token expires in {token_response.get('expires_in', 'unknown')} seconds"
    )


def generate_and_save_token(audience: str = "MCPGateway") -> None:
    """
    環境変数を使用して Cognito トークンを生成し、ファイルに保存します。

    Args:
        audience: トークンのオーディエンス（デフォルト: MCPGateway）
    """
    # .env ファイルから環境変数を読み込み
    dotenv.load_dotenv()

    # 必要な環境変数を取得
    cognito_domain_url = os.environ.get("COGNITO_DOMAIN")
    client_id = os.environ.get("COGNITO_CLIENT_ID")
    client_secret = os.environ.get("COGNITO_CLIENT_SECRET")

    # すべての必要な変数が存在するか検証
    if not all([cognito_domain_url, client_id, client_secret]):
        missing_vars = []
        if not cognito_domain_url:
            missing_vars.append("COGNITO_DOMAIN")
        if not client_id:
            missing_vars.append("COGNITO_CLIENT_ID")
        if not client_secret:
            missing_vars.append("COGNITO_CLIENT_SECRET")

        logging.error(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
        logging.error("Please set these variables in your .env file")
        raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")

    logging.info("Generating Cognito access token from environment variables...")

    # トークンを生成
    token_response = _get_cognito_token(
        cognito_domain_url=cognito_domain_url,
        client_id=client_id,
        client_secret=client_secret,
        audience=audience,
    )

    # トークンをファイルに保存
    _save_access_token(token_response)

    logging.info("Token generation completed successfully!")


def main():
    """Cognito トークンを生成して保存するメイン関数。"""
    parser = argparse.ArgumentParser(
        description="Generate OAuth2 access tokens from Cognito/Auth0"
    )
    parser.add_argument(
        "--audience", default="MCPGateway", help="Token audience (default: MCPGateway)"
    )

    args = parser.parse_args()

    try:
        generate_and_save_token(audience=args.audience)
    except Exception as e:
        logging.error(f"Token generation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
