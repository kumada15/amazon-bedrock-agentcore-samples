#!/usr/bin/env python3
"""
AWS Agent 認証プロバイダー API キー取得ツール

このモジュールは、Secrets Manager ARN を取得し、シークレット値を取得することで、
Amazon Bedrock AgentCore 認証プロバイダーから API キーを取得します。
"""

import argparse
import json
import logging
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# 設定定数
DEFAULT_CREDENTIAL_PROVIDER_NAME = "sre-agent-api-key-credential-provider"
DEFAULT_REGION = "us-east-1"
DEFAULT_ENDPOINT_URL = "https://bedrock-agentcore-control.us-east-1.amazonaws.com"


def _create_acps_client(region: str, endpoint_url: str) -> Any:
    """
    Agent 認証プロバイダーサービスクライアントを作成・設定します。

    Args:
        region: AWS リージョン名
        endpoint_url: サービスのエンドポイント URL

    Returns:
        設定済みの agentcredentialprovider 用 boto3 クライアント
    """
    sdk_config = Config(
        region_name=region,
        signature_version="v4",
        retries={"max_attempts": 2, "mode": "standard"},
    )

    return boto3.client(
        service_name="bedrock-agentcore-control",
        config=sdk_config,
        endpoint_url=endpoint_url,
    )


def _get_credential_provider_details(
    client: Any, provider_name: str
) -> Optional[Dict[str, Any]]:
    """
    Secrets Manager ARN を含む API キー認証プロバイダーの詳細を取得します。

    Args:
        client: ACPS クライアントインスタンス
        provider_name: 認証プロバイダーの名前

    Returns:
        secretsManagerArn を含むプロバイダー詳細、またはエラー時は None
    """
    try:
        logger.info(f"認証情報プロバイダーの取得を試みています: {provider_name}")
        response = client.get_api_key_credential_provider(name=provider_name)
        logger.info(f"認証情報プロバイダーを正常に取得しました: {provider_name}")
        logger.debug(f"Full response: {response}")

        # デバッグ用にレスポンスのすべてのキーをログ出力
        if response:
            logger.info(f"レスポンスキー: {list(response.keys())}")
            for key, value in response.items():
                if key != "apiKey":  # 機密データはログ出力しない
                    logger.info(f"  {key}: {value}")

        return response
    except ClientError as e:
        logger.error(f"認証情報プロバイダーの取得に失敗しました: {e}")
        logger.error(
            f"Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}"
        )
        logger.error(
            f"Error message: {e.response.get('Error', {}).get('Message', 'Unknown')}"
        )
        return None


def _retrieve_secret_value(secrets_manager_arn: str, region: str) -> Optional[str]:
    """
    AWS Secrets Manager からシークレット値を取得します。

    Args:
        secrets_manager_arn: Secrets Manager 内のシークレットの ARN
        region: AWS リージョン名

    Returns:
        シークレット値（API キー）、またはエラー時は None
    """
    try:
        # Secrets Manager クライアントを作成
        secrets_client = boto3.client(service_name="secretsmanager", region_name=region)

        # シークレットを取得
        response = secrets_client.get_secret_value(SecretId=secrets_manager_arn)

        # シークレット値を抽出
        if "SecretString" in response:
            secret_string = response["SecretString"]
            logger.debug(f"シークレット文字列の型: {type(secret_string)}")

            # まず JSON として解析を試みる
            try:
                secret_data = json.loads(secret_string)
                logger.info(f"シークレットは以下のキーを持つ JSON: {list(secret_data.keys())}")

                # 既知のフィールドから API キーを抽出
                api_key = secret_data.get("api_key_value")
                if api_key:
                    logger.info(
                        "Successfully retrieved API key from 'api_key_value' field"
                    )
                    return api_key
                else:
                    logger.error("シークレット内に 'api_key_value' フィールドが見つかりません")
                    logger.error(f"利用可能なフィールド: {list(secret_data.keys())}")
                    return None

            except json.JSONDecodeError:
                # JSON でない場合、シークレットは直接 API キーかもしれない
                logger.info("シークレットが JSON ではないため、生の API キーとして扱います")
                return secret_string.strip()
        else:
            logger.error("レスポンス内に SecretString が見つかりません")
            return None

    except ClientError as e:
        logger.error(f"Secrets Manager からのシークレット取得に失敗しました: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"シークレット JSON の解析に失敗しました: {e}")
        return None


def retrieve_api_key(
    credential_provider_name: str,
    region: str = DEFAULT_REGION,
    endpoint_url: str = DEFAULT_ENDPOINT_URL,
) -> Optional[str]:
    """
    認証プロバイダーから API キーを取得するメイン関数。

    Args:
        credential_provider_name: 認証プロバイダーの名前
        region: AWS リージョン名（デフォルト: us-east-1）
        endpoint_url: サービスのエンドポイント URL

    Returns:
        API キー、または取得に失敗した場合は None
    """
    logger.info("API キーの取得を開始")

    # ACPS クライアントを作成
    client = _create_acps_client(region, endpoint_url)

    # 認証プロバイダーの詳細を取得
    provider_details = _get_credential_provider_details(
        client, credential_provider_name
    )

    if not provider_details:
        logger.error("認証プロバイダーの詳細を取得できませんでした")
        return None

    # ネストされた構造から Secrets Manager ARN を抽出
    # ARN は apiKeySecretArn.secretArn に格納されている
    api_key_secret_arn = provider_details.get("apiKeySecretArn")
    if not api_key_secret_arn:
        logger.error("プロバイダー詳細に apiKeySecretArn が見つかりません")
        logger.error(f"レスポンス内の利用可能なフィールド: {list(provider_details.keys())}")
        return None

    secrets_manager_arn = api_key_secret_arn.get("secretArn")
    if not secrets_manager_arn:
        logger.error("apiKeySecretArn 内に secretArn が見つかりません")
        return None
    logger.info(f"使用する Secrets Manager ARN: {secrets_manager_arn}")
    # Secrets Manager から API キーを取得
    api_key = _retrieve_secret_value(secrets_manager_arn, region)

    if api_key:
        logger.info("API キーの取得が正常に完了しました")
        return api_key
    else:
        logger.error("API キーの取得に失敗しました")
        return None


def _parse_arguments() -> argparse.Namespace:
    """
    コマンドライン引数を解析します。

    Returns:
        解析されたコマンドライン引数
    """
    parser = argparse.ArgumentParser(
        description="Retrieve API key from AWS Agent Credential Provider Service"
    )

    parser.add_argument(
        "--credential-provider-name",
        default=DEFAULT_CREDENTIAL_PROVIDER_NAME,
        help=f"Name of the credential provider (default: {DEFAULT_CREDENTIAL_PROVIDER_NAME})",
    )

    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region (default: {DEFAULT_REGION})",
    )

    parser.add_argument(
        "--endpoint-url",
        default=DEFAULT_ENDPOINT_URL,
        help=f"Service endpoint URL (default: {DEFAULT_ENDPOINT_URL})",
    )

    return parser.parse_args()


def main() -> None:
    """メインエントリーポイント。"""
    args = _parse_arguments()

    api_key = retrieve_api_key(
        credential_provider_name=args.credential_provider_name,
        region=args.region,
        endpoint_url=args.endpoint_url,
    )

    if api_key:
        print("API キーの取得に成功しました")
        # 完全な API キーは表示しない
        print(
            "API キーは安全に取得され、プログラムから利用可能です。"
        )
    else:
        print("API キーの取得に失敗しました")


if __name__ == "__main__":
    main()
