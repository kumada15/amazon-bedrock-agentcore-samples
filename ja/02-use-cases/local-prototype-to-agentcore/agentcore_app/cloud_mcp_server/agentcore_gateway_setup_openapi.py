#!/usr/bin/env python3
"""OpenAPI 仕様を使用した Bedrock AgentCore Gateway のセットアップ

このスクリプトは、OpenAPI 仕様を使用して保険 API を MCP ツールとして
公開する AWS Bedrock AgentCore Gateway をセットアップします。

スクリプトは設定のために .env ファイルから環境変数を読み込みます：

環境変数:
    AWS_REGION (str): Gateway の AWS リージョン（デフォルト: "us-west-2"）
    ENDPOINT_URL (str): Bedrock AgentCore のエンドポイント URL（デフォルト: us-west-2 の Bedrock AgentCore エンドポイント）
    GATEWAY_NAME (str): Gateway の名前（デフォルト: "InsuranceAPIGateway"）
    GATEWAY_DESCRIPTION (str): Gateway の説明
    API_GATEWAY_URL (str): 保険 API の API Gateway URL
    OPENAPI_FILE_PATH (str): OpenAPI 仕様ファイルへのパス（デフォルト: "../cloud_insurance_api/openapi.json"）
    API_KEY (str): API 認証用の API キー
    CREDENTIAL_LOCATION (str): API 認証情報の場所（デフォルト: "HEADER"）
    CREDENTIAL_PARAMETER_NAME (str): API 認証情報のパラメータ名（デフォルト: "X-Subscription-Token"）
    GATEWAY_INFO_FILE (str): Gateway 情報を保存するファイルパス（デフォルト: "gateway_info.json"）

出力:
    Cognito 認証付きの Bedrock AgentCore Gateway を作成
    OpenAPI 仕様を介して保険 API を使用するよう Gateway を設定
    後で使用するために Gateway 情報を JSON ファイルに保存
"""

import logging
import json
import os
from dotenv import load_dotenv
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

# Load environment variables from .env file
load_dotenv()

# Setup the client using environment variables
region = os.getenv("AWS_REGION", "us-west-2")
endpoint_url = os.getenv("ENDPOINT_URL", "https://bedrock-agentcore-control.us-west-2.amazonaws.com")

print(f"リージョン {region} で Gateway クライアントをセットアップ中")
client = GatewayClient(endpoint_url=endpoint_url, region_name=region)
client.logger.setLevel(logging.DEBUG)

# Get gateway name from environment variables
gateway_name = os.getenv("GATEWAY_NAME", "InsuranceAPIGateway")
gateway_description = os.getenv("GATEWAY_DESCRIPTION", "Insurance API Gateway with OpenAPI Specification")

# Create cognito authorizer
print(f"ゲートウェイ '{gateway_name}' の OAuth 認証を作成中")
cognito_response = client.create_oauth_authorizer_with_cognito(gateway_name)

# Create the gateway
print(f"MCP ゲートウェイ '{gateway_name}' を作成中")
gateway = client.create_mcp_gateway(
    name=gateway_name,
    authorizer_config=cognito_response["authorizer_config"],
)


# Load the insurance API OpenAPI specification from environment or default path
env_openapi_path = os.getenv("OPENAPI_FILE_PATH", "../cloud_insurance_api/openapi.json")
openapi_file_path = os.path.abspath(env_openapi_path)

print(f"OpenAPI 仕様を読み込み中: {openapi_file_path}")
with open(openapi_file_path, "r") as f:
    openapi_spec = json.load(f)

# Set the API Gateway URL from environment variables
api_gateway_url = os.getenv("API_GATEWAY_URL", "https://i0zzy6t0x9.execute-api.us-west-2.amazonaws.com/dev")

# Add server URL if not present in OpenAPI spec
if "servers" not in openapi_spec:
    print("OpenAPI 仕様にサーバー URL を追加中...")
    openapi_spec["servers"] = [{"url": api_gateway_url}]

# Get API credentials from environment variables
api_key = os.getenv("API_KEY", "BSAm0I6f_91QSB-CJQzsVpukUKTlXGJ")
credential_location = os.getenv("CREDENTIAL_LOCATION", "HEADER")
credential_parameter_name = os.getenv("CREDENTIAL_PARAMETER_NAME", "X-Subscription-Token")

# Create the OpenAPI target with OAuth2 configuration using Cognito
print("OpenAPI 仕様で MCP ゲートウェイターゲットを作成中")
open_api_target = client.create_mcp_gateway_target(
    gateway=gateway,
    name="API",
    target_type="openApiSchema",
    target_payload={
        "inlinePayload": json.dumps(openapi_spec)
    },
    credentials={
        "api_key": api_key,
        "credential_location": credential_location,
        "credential_parameter_name": credential_parameter_name
    }
)

# Print the gateway information
print("\n✅ ゲートウェイのセットアップが完了しました！")
print(f"ゲートウェイ ID: {gateway['gatewayId']}")
print(f"ゲートウェイ MCP URL: https://{gateway['gatewayId']}.gateway.bedrock-agentcore.{client.region}.amazonaws.com/mcp")
print(f"ターゲット ID: {open_api_target['targetId']}")

# Print authentication information
print("\n認証情報:")
print(f"クライアント ID: {cognito_response['client_info']['client_id']}")
print("クライアントシークレット: [非表示]")
print(f"トークンエンドポイント: {cognito_response['client_info']['token_endpoint']}")
print(f"スコープ: {cognito_response['client_info']['scope']}")

# Generate an access token for testing
access_token = client.get_access_token_for_cognito(cognito_response["client_info"])
print(f"\nアクセストークン: {access_token}")

# Save gateway information to file for later use
gateway_info = {
    "gateway": {
        "name": gateway["name"],
        "id": gateway["gatewayId"],
        "mcp_url": f"https://{gateway['gatewayId']}.gateway.bedrock-agentcore.{client.region}.amazonaws.com/mcp",
        "region": client.region,
        "description": gateway.get("description", "Insurance API Gateway with OpenAPI Specification")
    },
    "api": {
        "gateway_url": api_gateway_url,
        "openapi_file_path": openapi_file_path,
        "target_id": open_api_target["targetId"]
    },
    "auth": {
        "access_token": access_token,
        "client_id": cognito_response["client_info"]["client_id"],
        "client_secret": cognito_response["client_info"]["client_secret"],
        "token_endpoint": cognito_response["client_info"]["token_endpoint"],
        "scope": cognito_response["client_info"]["scope"],
        "user_pool_id": cognito_response["client_info"]["user_pool_id"],
        "discovery_url": cognito_response["authorizer_config"]["customJWTAuthorizer"]["discoveryUrl"]
    }
}

# Get gateway info file path from environment or use default
gateway_info_file = os.getenv("GATEWAY_INFO_FILE", "gateway_info.json")

print(f"\nゲートウェイ情報を {gateway_info_file} に保存中...")
with open(gateway_info_file, "w") as f:
    json.dump(gateway_info, f, indent=2)

print("\nセットアップ完了！これで Insurance API で MCP サーバーを使用できます。")