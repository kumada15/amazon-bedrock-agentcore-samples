#!/usr/bin/env python3
"""
AgentCore Gateway 管理ツール

このツールは、MCP プロトコルサポートと JWT 認証を備えた AWS AgentCore Gateway の
作成と管理機能を提供します。Gateway の作成と S3 またはインラインスキーマからの
OpenAPI ターゲットの追加をサポートします。
"""

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Configuration constants
GATEWAY_DELETION_PROPAGATION_DELAY = 3


# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)


def _extract_account_id_from_arn(arn: str) -> str:
    """
    ARN から AWS アカウント ID を抽出します。

    Args:
        arn: AWS ARN 文字列

    Returns:
        ARN から抽出されたアカウント ID
    """
    try:
        # ARN format: arn:aws:service:region:account-id:resource
        parts = arn.split(":")
        if len(parts) >= 5:
            return parts[4]
        else:
            logging.error(f"Invalid ARN format: {arn}")
            return ""
    except Exception as e:
        logging.error(f"Failed to extract account ID from ARN: {e}")
        return ""


def _create_agentcore_client(region: str, endpoint_url: str) -> Any:
    """
    リトライ設定を含む AWS サービスとの通信用 AgentCore クライアントを作成して返します。

    Args:
        region: AWS リージョン名
        endpoint_url: AgentCore エンドポイント URL

    Returns:
        設定済みの bedrock-agentcore-control 用 boto3 クライアント
    """
    # リージョンがエンドポイント URL と一致するか検証
    import re
    endpoint_region_match = re.search(r'\.([a-z0-9-]+)\.amazonaws\.com', endpoint_url)
    if endpoint_region_match:
        endpoint_region = endpoint_region_match.group(1)
        if endpoint_region != region:
            error_msg = (
                f"Region mismatch: The --region parameter '{region}' does not match "
                f"the region in the endpoint URL '{endpoint_region}'. "
                f"Please ensure both use the same region (e.g., --region {endpoint_region})"
            )
            logging.error(error_msg)
            raise ValueError(error_msg)
    
    # 試行回数とタイムアウトを増やしたカスタムリトライ設定
    retry_config = Config(
        retries={"max_attempts": 20, "mode": "adaptive"},
        connect_timeout=60,
        read_timeout=60,
    )

    try:
        client = boto3.client(
            "bedrock-agentcore-control",
            region_name=region,
            endpoint_url=endpoint_url,
            config=retry_config,
        )
        logging.info(f"Created AgentCore client for region {region}")
        return client
    except Exception as e:
        logging.error(f"Failed to create AgentCore client: {e}")
        raise


def _print_gateway_response(response: Dict[str, Any]) -> None:
    """
    フォーマットされた Gateway 作成レスポンスの詳細を出力します。

    Args:
        response: AWS からの Gateway 作成レスポンス
    """
    print("=" * 80)
    print("Gateway 作成レスポンス")
    print("=" * 80)

    # ステータスと基本情報
    print(f"\nステータス: {response.get('status', 'N/A')}")
    print(f"HTTP ステータス: {response['ResponseMetadata']['HTTPStatusCode']}")

    # Gateway 詳細
    print(f"\nGateway URL: {response.get('gatewayUrl', 'N/A')}")
    print(f"Gateway ID: {response.get('gatewayId', 'N/A')}")
    print(f"Gateway 名: {response.get('name', 'N/A')}")
    print(f"説明: {response.get('description', 'N/A')}")

    # ARN 情報
    print(f"\nGateway ARN: {response.get('gatewayArn', 'N/A')}")
    print(f"ロール ARN: {response.get('roleArn', 'N/A')}")

    # プロトコル設定
    protocol_config = response.get("protocolConfiguration", {}).get("mcp", {})
    print(f"\nプロトコルタイプ: {response.get('protocolType', 'N/A')}")
    print(
        f"サポートバージョン: {', '.join(protocol_config.get('supportedVersions', []))}"
    )
    print(f"検索タイプ: {protocol_config.get('searchType', 'N/A')}")

    # 認証設定
    auth_config = response.get("authorizerConfiguration", {}).get(
        "customJWTAuthorizer", {}
    )
    print(f"\n認証タイプ: {response.get('authorizerType', 'N/A')}")
    print(f"ディスカバリー URL: {auth_config.get('discoveryUrl', 'N/A')}")
    print(f"許可オーディエンス: {', '.join(auth_config.get('allowedAudience', []))}")

    # タイムスタンプ
    print(f"\n作成日時: {response.get('createdAt', 'N/A')}")
    print(f"更新日時: {response.get('updatedAt', 'N/A')}")

    # リクエストメタデータ
    response_metadata = response["ResponseMetadata"]
    request_id = response_metadata["RequestId"]
    timestamp = response_metadata["HTTPHeaders"]["date"]

    print(f"\nリクエスト ID: {request_id}")
    print(f"タイムスタンプ: {timestamp}")
    print("=" * 80)


def _save_gateway_url(gateway_url: str, output_file: str = ".gateway_uri") -> None:
    """
    Gateway URL をファイルに保存します。

    Args:
        gateway_url: 保存する Gateway URL
        output_file: 出力ファイルパス
    """
    # 末尾のスラッシュを削除（存在する場合）
    gateway_url = gateway_url.rstrip("/")

    # 末尾の '/mcp' を削除（存在する場合）
    if gateway_url.endswith("/mcp"):
        gateway_url = gateway_url[:-4]

    Path(output_file).write_text(gateway_url)
    logging.info(f"Saved gateway URL to {output_file}")


def _check_gateway_exists(client: Any, gateway_name: str) -> str:
    """
    指定された名前の Gateway が既に存在するかどうかを確認します。

    Args:
        client: AgentCore クライアント
        gateway_name: 確認する Gateway の名前

    Returns:
        存在する場合は Gateway ID、見つからない場合は空文字列
    """
    try:
        response = client.list_gateways()
        gateways = response.get("items", [])

        for gateway in gateways:
            if gateway.get("name") == gateway_name:
                gateway_id = gateway.get("gatewayId", "")
                logging.info(
                    f"Found existing gateway: {gateway_name} (ID: {gateway_id})"
                )
                return gateway_id

        logging.info(f"No existing gateway found with name: {gateway_name}")
        return ""
    except ClientError as e:
        logging.error(f"Failed to list gateways: {e}")
        raise


def _delete_gateway_targets(client: Any, gateway_id: str) -> None:
    """
    Gateway に関連付けられたすべてのターゲットを削除します。

    Args:
        client: AgentCore クライアント
        gateway_id: ターゲットを削除する Gateway ID
    """
    try:
        logging.info(f"Listing targets for gateway: {gateway_id}")
        targets_response = client.list_gateway_targets(gatewayIdentifier=gateway_id)
        targets = targets_response.get("items", [])

        if not targets:
            logging.info(f"No targets found for gateway: {gateway_id}")
            return

        logging.info(f"Found {len(targets)} targets to delete")

        for target in targets:
            target_id = target.get("targetId", "")
            target_name = target.get("name", "Unknown")

            if target_id:
                logging.info(f"Deleting target: {target_name} (ID: {target_id})")
                delete_response = client.delete_gateway_target(
                    targetId=target_id, gatewayIdentifier=gateway_id
                )
                logging.info(f"Target deleted successfully: {target_name}")

                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(f"Target delete response: {delete_response}")
            else:
                logging.warning(f"Target has no ID, skipping: {target_name}")

        logging.info(f"All targets deleted for gateway: {gateway_id}")

    except ClientError as e:
        logging.error(f"Failed to delete targets for gateway {gateway_id}: {e}")
        raise


def _delete_gateway(client: Any, gateway_id: str) -> None:
    """
    ID で Gateway を削除します。関連するすべてのターゲットも含みます。

    Args:
        client: AgentCore クライアント
        gateway_id: 削除する Gateway ID
    """
    try:
        # First delete all targets
        _delete_gateway_targets(client, gateway_id)

        # Then delete the gateway
        logging.info(f"Deleting gateway: {gateway_id}")
        delete_response = client.delete_gateway(gatewayIdentifier=gateway_id)
        logging.info(f"Gateway deleted successfully: {gateway_id}")

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Gateway delete response: {delete_response}")

        # 削除の伝播を待機
        logging.info(
            f"Waiting {GATEWAY_DELETION_PROPAGATION_DELAY} seconds for deletion to propagate..."
        )
        time.sleep(GATEWAY_DELETION_PROPAGATION_DELAY)
    except ClientError as e:
        logging.error(f"Failed to delete gateway {gateway_id}: {e}")
        raise


def create_gateway(
    client: Any,
    gateway_name: str,
    role_arn: str,
    discovery_url: str,
    allowed_audience: str = None,
    allowed_clients: list = None,
    description: str = "AgentCore Gateway created via SDK",
    search_type: str = "SEMANTIC",
    protocol_version: str = "2025-03-26",
) -> Dict[str, Any]:
    """
    JWT 認証を備えた新しい AgentCore Gateway を作成します。

    Args:
        client: AgentCore クライアント
        gateway_name: Gateway の名前
        role_arn: 必要な権限を持つ IAM ロール ARN
        discovery_url: JWT ディスカバリー URL
        allowed_audience: 許可される JWT オーディエンス（Auth0/Okta 用）
        allowed_clients: 許可される JWT クライアント ID（Cognito 用）
        description: Gateway の説明
        search_type: MCP 検索タイプ（デフォルト: SEMANTIC）
        protocol_version: MCP プロトコルバージョン（デフォルト: 2025-03-26）

    Returns:
        Gateway 作成レスポンス
    """
    # Cognito（クライアント）か Auth0/Okta（オーディエンス）かに基づいて認証設定を構築
    auth_config = {"customJWTAuthorizer": {"discoveryUrl": discovery_url}}

    if allowed_clients:
        # Cognito 用 - allowedClients を使用
        auth_config["customJWTAuthorizer"]["allowedClients"] = (
            allowed_clients if isinstance(allowed_clients, list) else [allowed_clients]
        )
    elif allowed_audience:
        # Auth0/Okta 用 - allowedAudience を使用
        auth_config["customJWTAuthorizer"]["allowedAudience"] = [allowed_audience]
    else:
        raise ValueError("Either allowed_audience or allowed_clients must be specified")

    protocol_configuration = {
        "mcp": {"searchType": search_type, "supportedVersions": [protocol_version]}
    }

    try:
        response = client.create_gateway(
            name=gateway_name,
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=auth_config,
            protocolConfiguration=protocol_configuration,
            description=description,
            exceptionLevel="DEBUG",
        )
        logging.info(f"Created gateway: {response.get('gatewayId')}")
        return response
    except ClientError as e:
        logging.error(f"Failed to create gateway: {e}")
        raise


def create_s3_target(
    client: Any,
    gateway_id: str,
    s3_uri: str,
    provider_arn: str,
    target_name_prefix: str = "open",
    description: str = "S3 target for OpenAPI schema",
) -> Dict[str, Any]:
    """
    S3 の OpenAPI スキーマから Gateway ターゲットを作成します。

    Args:
        client: AgentCore クライアント
        gateway_id: Gateway 識別子
        s3_uri: OpenAPI スキーマの S3 URI
        provider_arn: OAuth 認証プロバイダー ARN
        target_name_prefix: ターゲット名のプレフィックス
        description: ターゲットの説明

    Returns:
        ターゲット作成レスポンス
    """
    s3_target_config = {"mcp": {"openApiSchema": {"s3": {"uri": s3_uri}}}}

    # OAuth 認証プロバイダー設定
    # credential_config = {
    #     "credentialProviderType": "OAUTH",
    #     "credentialProvider": {
    #         "oauthCredentialProvider": {
    #             "providerArn": provider_arn,
    #             "scopes": []
    #         }
    #     }
    # }

    # API キー認証プロバイダー設定
    credential_config = {
        "credentialProviderType": "API_KEY",
        "credentialProvider": {
            "apiKeyCredentialProvider": {
                # "credentialPrefix": "",
                "providerArn": provider_arn,
                "credentialLocation": "HEADER",  # QUERY_PARAMETER
                "credentialParameterName": "X-API-KEY",
            }
        },
    }
    try:
        response = client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=target_name_prefix,
            description=description,
            targetConfiguration=s3_target_config,
            credentialProviderConfigurations=[credential_config],
        )
        logging.info(f"Created S3 target: {response.get('targetId')}")
        return response
    except ClientError as e:
        logging.error(f"Failed to create S3 target: {e}")
        raise


def create_inline_target(
    client: Any,
    gateway_id: str,
    openapi_schema: str,
    provider_arn: str,
    target_name_prefix: str = "inline",
    description: str = "Inline target for OpenAPI schema",
) -> Dict[str, Any]:
    """
    インライン OpenAPI スキーマから Gateway ターゲットを作成します。

    Args:
        client: AgentCore クライアント
        gateway_id: Gateway 識別子
        openapi_schema: 文字列としてのインライン OpenAPI スキーマ
        provider_arn: OAuth 認証プロバイダー ARN
        target_name_prefix: ターゲット名のプレフィックス
        description: ターゲットの説明

    Returns:
        ターゲット作成レスポンス
    """
    openapi_target_config = {
        "mcp": {"openApiSchema": {"inlinePayload": openapi_schema}}
    }

    credential_config = {
        "credentialProviderType": "OAUTH",
        "credentialProvider": {
            "oauthCredentialProvider": {"providerArn": provider_arn, "scopes": []}
        },
    }

    try:
        response = client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=target_name_prefix,
            description=description,
            targetConfiguration=openapi_target_config,
            credentialProviderConfigurations=[credential_config],
        )
        logging.info(f"Created inline target: {response.get('targetId')}")
        return response
    except ClientError as e:
        logging.error(f"Failed to create inline target: {e}")
        raise


def verify_gateway(client: Any, gateway_id: str) -> Dict[str, Any]:
    """
    詳細を取得して Gateway の作成を検証します。

    Args:
        client: AgentCore クライアント
        gateway_id: Gateway 識別子

    Returns:
        Gateway の詳細
    """
    try:
        response = client.get_gateway(gatewayIdentifier=gateway_id)
        logging.info(
            f"Verified gateway: {gateway_id}, Status: {response.get('status')}"
        )
        return response
    except ClientError as e:
        logging.error(f"Failed to verify gateway: {e}")
        raise


def list_gateway_targets(client: Any, gateway_id: str) -> Dict[str, Any]:
    """
    Gateway のすべてのターゲットを一覧表示します。

    Args:
        client: AgentCore クライアント
        gateway_id: Gateway 識別子

    Returns:
        Gateway ターゲットのリスト
    """
    try:
        response = client.list_gateway_targets(gatewayIdentifier=gateway_id)
        logging.info(
            f"Found {len(response.get('items', []))} targets for gateway {gateway_id}"
        )
        return response
    except ClientError as e:
        logging.error(f"Failed to list gateway targets: {e}")
        raise


def main():
    """Gateway の作成と管理を調整するメイン関数。"""
    parser = argparse.ArgumentParser(
        description="Create and manage AWS AgentCore Gateways with MCP protocol support"
    )

    # 必須引数
    parser.add_argument("gateway_name", help="Name for the AgentCore Gateway")

    # AWS 設定
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--endpoint-url",
        default="https://bedrock-agentcore-control.us-east-1.amazonaws.com",
        help="AgentCore endpoint URL",
    )
    parser.add_argument(
        "--role-arn", required=True, help="IAM Role ARN with gateway permissions"
    )

    # 認可設定
    parser.add_argument(
        "--discovery-url", required=True, help="JWT discovery URL for authorization"
    )
    parser.add_argument(
        "--allowed-audience",
        default="MCPGateway",
        help="Allowed JWT audience (default: MCPGateway)",
    )
    parser.add_argument(
        "--allowed-clients", help="Allowed JWT client IDs (for Cognito)"
    )

    # Gateway 設定
    parser.add_argument(
        "--description-for-gateway",
        default="AgentCore Gateway created via SDK",
        help="Gateway description",
    )
    parser.add_argument(
        "--description-for-target",
        action="append",
        help="Target description (can be specified multiple times)",
    )
    parser.add_argument(
        "--search-type", default="SEMANTIC", help="MCP search type (default: SEMANTIC)"
    )
    parser.add_argument(
        "--protocol-version",
        default="2025-03-26",
        help="MCP protocol version (default: 2025-03-26)",
    )

    # ターゲット設定
    parser.add_argument(
        "--create-s3-target", action="store_true", help="Create an S3 OpenAPI target"
    )
    parser.add_argument(
        "--s3-uri",
        action="append",
        help="S3 URI for OpenAPI schema (can be specified multiple times)",
    )
    parser.add_argument(
        "--create-inline-target",
        action="store_true",
        help="Create an inline OpenAPI target",
    )
    parser.add_argument(
        "--openapi-schema-file", help="File containing OpenAPI schema for inline target"
    )
    parser.add_argument(
        "--provider-arn", help="OAuth credential provider ARN for targets"
    )

    # 出力オプション
    parser.add_argument(
        "--save-gateway-url",
        action="store_true",
        help="Save gateway URL to .gateway_uri file",
    )
    parser.add_argument(
        "--delete-gateway-if-exists",
        action="store_true",
        help="Delete gateway if it already exists before creating new one",
    )
    parser.add_argument(
        "--output-json", action="store_true", help="Output responses in JSON format"
    )
    parser.add_argument(
        "--enable-observability",
        action="store_true",
        help="Enable CloudWatch logs and X-Ray tracing for the gateway",
    )

    args = parser.parse_args()

    # AgentCore クライアントを作成
    client = _create_agentcore_client(args.region, args.endpoint_url)

    # Gateway が既に存在するかチェックし、要求があれば削除を処理
    existing_gateway_id = _check_gateway_exists(client, args.gateway_name)
    if existing_gateway_id:
        if args.delete_gateway_if_exists:
            logging.info("Deleting existing gateway before creating new one")
            _delete_gateway(client, existing_gateway_id)
        else:
            logging.warning(
                f"Gateway '{args.gateway_name}' already exists (ID: {existing_gateway_id})"
            )
            logging.warning(
                "Use --delete-gateway-if-exists to delete it before creating a new one"
            )
            print(f"Gateway '{args.gateway_name}' は既に存在します")
            print(f"   Gateway ID: {existing_gateway_id}")
            print("   削除して再作成するには --delete-gateway-if-exists フラグを使用してください")
            exit(1)

    # Gateway を作成
    logging.info(f"Creating gateway: {args.gateway_name}")
    create_response = create_gateway(
        client=client,
        gateway_name=args.gateway_name,
        role_arn=args.role_arn,
        discovery_url=args.discovery_url,
        allowed_audience=args.allowed_audience if not args.allowed_clients else None,
        allowed_clients=(
            args.allowed_clients.split(",") if args.allowed_clients else None
        ),
        description=args.description_for_gateway,
        search_type=args.search_type,
        protocol_version=args.protocol_version,
    )

    if args.output_json:
        print(json.dumps(create_response, indent=2, default=str))
    else:
        _print_gateway_response(create_response)

    gateway_id = create_response["gatewayId"]
    gateway_url = create_response.get("gatewayUrl", "")
    gateway_arn = create_response.get("gatewayArn", "")

    # オブザーバビリティが要求されたかチェック
    if args.enable_observability:
        logging.error("Observability feature is not yet supported")
        print(
            "\nエラー: --enable-observability 機能は現在サポートされていませんが、まもなく利用可能になります。"
        )
        print("   --enable-observability フラグなしでコマンドを実行してください。")
        exit(1)

    # 要求があれば Gateway URL を保存
    if args.save_gateway_url and gateway_url:
        _save_gateway_url(gateway_url)

    # Gateway 作成を検証
    verify_response = verify_gateway(client, gateway_id)
    if args.output_json:
        print("\nGateway の検証:")
        print(json.dumps(verify_response, indent=2, default=str))

    # 要求があれば S3 ターゲットを作成
    if args.create_s3_target:
        if not args.provider_arn:
            logging.error("Provider ARN required for creating targets")
            parser.error("--provider-arn is required when creating targets")

        if not args.s3_uri:
            logging.error("At least one S3 URI required when creating S3 targets")
            parser.error("--s3-uri is required when creating S3 targets")

        # 複数の S3 URI と説明を処理
        s3_uris = args.s3_uri
        descriptions = args.description_for_target or []

        # すべての URI に説明があることを確認（不足の場合はデフォルトを使用）
        while len(descriptions) < len(s3_uris):
            descriptions.append("S3 target for OpenAPI schema")

        s3_responses = []
        for i, s3_uri in enumerate(s3_uris):
            # S3 URI からターゲット用の意味のある名前を抽出
            target_name = (
                s3_uri.split("/")[-1].replace(".yaml", "").replace(".json", "")
            )
            if not target_name or target_name == s3_uri:
                target_name = f"target-{i + 1}"

            # AWS の命名要件を満たすためアンダースコアをハイフンに置換
            # AWS の要件: ([0-9a-zA-Z][-]?){1,100}
            target_name = target_name.replace("_", "-")

            logging.info(
                f"Creating S3 OpenAPI target {i + 1}/{len(s3_uris)}: {target_name}"
            )
            s3_response = create_s3_target(
                client=client,
                gateway_id=gateway_id,
                s3_uri=s3_uri,
                provider_arn=args.provider_arn,
                target_name_prefix=target_name,
                description=descriptions[i],
            )
            s3_responses.append(s3_response)

            if args.output_json:
                print(f"\nS3 Target {i + 1} の作成:")
                print(json.dumps(s3_response, indent=2, default=str))

        if not args.output_json:
            print(f"\n{len(s3_responses)} 件の S3 ターゲットの作成に成功しました")

    # 要求があればインラインターゲットを作成
    if args.create_inline_target:
        if not args.provider_arn:
            logging.error("Provider ARN required for creating targets")
            parser.error("--provider-arn is required when creating targets")

        if not args.openapi_schema_file:
            logging.error("OpenAPI schema file required for inline target")
            parser.error("--openapi-schema-file is required for inline targets")

        # ファイルから OpenAPI スキーマを読み込み
        schema_content = Path(args.openapi_schema_file).read_text()

        logging.info("Creating inline OpenAPI target")
        inline_response = create_inline_target(
            client=client,
            gateway_id=gateway_id,
            openapi_schema=schema_content,
            provider_arn=args.provider_arn,
            description=args.description_for_target,
        )

        if args.output_json:
            print("\nインラインターゲットの作成:")
            print(json.dumps(inline_response, indent=2, default=str))

    # すべてのターゲットを一覧表示
    if args.create_s3_target or args.create_inline_target:
        targets_response = list_gateway_targets(client, gateway_id)
        if args.output_json:
            print("\nGateway ターゲット:")
            print(json.dumps(targets_response, indent=2, default=str))
        else:
            targets = targets_response.get("items", [])
            print(f"\nGateway には {len(targets)} 件のターゲットがあります:")
            for target in targets:
                print(
                    f"   - {target.get('name', 'Unknown')} (ID: {target.get('targetId', 'N/A')})"
                )
                print(f"     説明: {target.get('description', 'N/A')}")
                print(f"     ステータス: {target.get('status', 'N/A')}")

    print("\nGateway の作成と設定が正常に完了しました！")
    if gateway_url:
        print(f"Gateway URL: {gateway_url}")
    logging.info("Gateway creation and configuration completed successfully")


if __name__ == "__main__":
    main()
