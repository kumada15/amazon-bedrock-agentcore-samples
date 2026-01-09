#!/usr/bin/env python3
"""
AWS Agent 認証プロバイダーサービス管理ツール

このモジュールは Amazon Bedrock AgentCore 用の API キー認証プロバイダーを管理します。
認証プロバイダーの一覧表示、削除、作成を、SecretsManager の競合に対する
適切なエラーハンドリングとリトライロジックで処理します。
"""

import argparse
import logging
import time
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Configuration constants
DEFAULT_CREDENTIAL_PROVIDER_NAME = "sre-agent-api-key-credential-provider"
DEFAULT_REGION = "us-east-1"
DEFAULT_ENDPOINT_URL = "https://bedrock-agentcore-control.us-east-1.amazonaws.com"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5
PROPAGATION_DELAY = 15


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


def _check_provider_exists(client: Any, provider_name: str) -> bool:
    """
    指定された名前の認証プロバイダーが既に存在するかどうかを確認します。

    Args:
        client: ACPS クライアントインスタンス
        provider_name: 確認する認証プロバイダーの名前

    Returns:
        存在する場合は True、それ以外は False
    """
    try:
        existing_providers = client.list_api_key_credential_providers()
        logger.info("既存の API キー認証プロバイダー一覧を取得しました")

        if "credentialProviders" in existing_providers:
            for provider in existing_providers["credentialProviders"]:
                if provider.get("name") == provider_name:
                    logger.info(f"既存の認証プロバイダーを発見: {provider_name}")
                    return True

        logger.info(f"名前 {provider_name} の既存認証プロバイダーは見つかりませんでした")
        return False

    except ClientError as e:
        logger.error(f"認証プロバイダー一覧の取得に失敗しました: {e}")
        raise


def _delete_existing_provider(client: Any, provider_name: str) -> None:
    """
    既存の認証プロバイダーを削除し、反映を待機します。

    Args:
        client: ACPS クライアントインスタンス
        provider_name: 削除する認証プロバイダーの名前
    """
    try:
        logger.info(f"既存の認証プロバイダーを削除中: {provider_name}")
        client.delete_api_key_credential_provider(name=provider_name)
        logger.info("既存の認証プロバイダーを正常に削除しました")

        # Wait for deletion to propagate
        logger.info(f"削除の反映を待機中... ({PROPAGATION_DELAY}秒)")
        time.sleep(PROPAGATION_DELAY)

    except ClientError as e:
        logger.error(f"認証プロバイダーの削除に失敗しました: {e}")
        raise


def _create_provider_with_retry(
    client: Any, provider_name: str, api_key: str
) -> Dict[str, Any]:
    """
    SecretsManager の競合に対するリトライロジックを使用して新しい認証プロバイダーを作成します。

    Args:
        client: ACPS クライアントインスタンス
        provider_name: 新しい認証プロバイダーの名前
        api_key: 認証プロバイダーの API キー

    Returns:
        作成 API 呼び出しからのレスポンス
    """
    retry_delay = INITIAL_RETRY_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            response = client.create_api_key_credential_provider(
                name=provider_name, apiKey=api_key
            )
            logger.info("認証プロバイダーを正常に作成しました")
            return response

        except ClientError as e:
            if e.response["Error"][
                "Code"
            ] == "ConflictException" and "SecretsManager" in str(e):
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"SecretsManager の競合が発生 (試行 {attempt + 1}/{MAX_RETRIES})。"
                        f"{retry_delay}秒後にリトライします..."
                    )
                    time.sleep(retry_delay)
                    retry_delay += 2  # Exponential backoff
                else:
                    logger.error(
                        f"{MAX_RETRIES}回の試行後も認証プロバイダーの作成に失敗しました: {e}"
                    )
                    raise
            else:
                logger.error(f"認証プロバイダーの作成に失敗しました: {e}")
                raise

    # This should never be reached
    raise RuntimeError("Unexpected end of retry loop")


def _list_workload_identities(client: Any) -> Optional[Dict[str, Any]]:
    """
    すべてのワークロードアイデンティティを一覧表示します。

    Args:
        client: ACPS クライアントインスタンス

    Returns:
        ワークロードアイデンティティのレスポンス、またはエラー時は None
    """
    try:
        workload_identities = client.list_workload_identities()
        logger.info("すべてのワークロードアイデンティティを一覧表示しました")
        return workload_identities
    except ClientError as e:
        logger.error(f"ワークロードアイデンティティ一覧の取得に失敗しました: {e}")
        return None


def _list_oauth2_providers(client: Any) -> Optional[Dict[str, Any]]:
    """
    すべての OAuth2 認証プロバイダーを一覧表示します。

    Args:
        client: ACPS クライアントインスタンス

    Returns:
        OAuth2 プロバイダーのレスポンス、またはエラー時は None
    """
    try:
        oauth2_providers = client.list_oauth2_credential_providers()
        logger.info("すべての OAuth2 認証プロバイダーを一覧表示しました")
        return oauth2_providers
    except ClientError as e:
        logger.error(f"OAuth2 認証プロバイダー一覧の取得に失敗しました: {e}")
        return None


def _save_credential_provider_arn(
    credential_provider_arn: str, file_path: str = ".credentials_provider"
) -> None:
    """
    認証プロバイダー ARN をローカルファイルに保存します。

    Args:
        credential_provider_arn: 保存する ARN
        file_path: ARN を保存するファイルのパス
    """
    try:
        Path(file_path).write_text(credential_provider_arn)
        logger.info(f"認証プロバイダー ARN を {file_path} に保存しました")
    except Exception as e:
        logger.error(f"認証プロバイダー ARN の保存に失敗しました: {e}")
        raise


def setup_credential_provider(
    credential_provider_name: str, api_key: str, region: str, endpoint_url: str
) -> None:
    """
    API キー認証プロバイダーをセットアップするメイン関数。

    Args:
        credential_provider_name: 認証プロバイダーの名前
        api_key: 認証プロバイダーの API キー
        region: AWS リージョン名
        endpoint_url: サービスのエンドポイント URL

    この関数は、既存のプロバイダーの確認、見つかった場合の削除、
    新しいプロバイダーの作成というプロセス全体を調整します。
    """
    logger.info("認証プロバイダーのセットアップを開始します")

    # Create ACPS client
    client = _create_acps_client(region, endpoint_url)

    # Check if provider already exists
    provider_exists = _check_provider_exists(client, credential_provider_name)

    # Delete existing provider if found
    if provider_exists:
        _delete_existing_provider(client, credential_provider_name)

    # Create new credential provider
    logger.info(f"新しい API キー認証プロバイダーを作成中: {credential_provider_name}")
    response = _create_provider_with_retry(client, credential_provider_name, api_key)

    print("認証プロバイダーの作成に成功しました")
    pprint(response)

    # Extract and save credential provider ARN
    credential_provider_arn = response.get("credentialProviderArn")
    if credential_provider_arn:
        _save_credential_provider_arn(credential_provider_arn)
        print(f"\n認証プロバイダー ARN: {credential_provider_arn}")
        print("ARN を .credentials_provider ファイルに保存しました")
    else:
        logger.warning("レスポンスに credentialProviderArn が見つかりませんでした")

    # List additional information
    print("\nすべてのワークロードアイデンティティを一覧表示:")
    workload_identities = _list_workload_identities(client)
    if workload_identities:
        pprint(workload_identities)

    print("\nすべての OAuth2 認証プロバイダーを一覧表示:")
    oauth2_providers = _list_oauth2_providers(client)
    if oauth2_providers:
        pprint(oauth2_providers)

    logger.info("認証プロバイダーのセットアップが正常に完了しました")


def _parse_arguments() -> argparse.Namespace:
    """
    コマンドライン引数を解析します。

    Returns:
        解析されたコマンドライン引数
    """
    parser = argparse.ArgumentParser(
        description="Create and manage AWS Agent Credential Provider Service API key providers"
    )

    parser.add_argument(
        "--credential-provider-name",
        default=DEFAULT_CREDENTIAL_PROVIDER_NAME,
        help=f"Name for the credential provider (default: {DEFAULT_CREDENTIAL_PROVIDER_NAME})",
    )

    parser.add_argument(
        "--api-key",
        required=True,
        help="API key for the credential provider (required)",
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

    setup_credential_provider(
        credential_provider_name=args.credential_provider_name,
        api_key=args.api_key,
        region=args.region,
        endpoint_url=args.endpoint_url,
    )


if __name__ == "__main__":
    main()
