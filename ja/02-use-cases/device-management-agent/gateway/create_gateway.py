"""
Amazon Bedrock AgentCore Gateway 作成スクリプト

このスクリプトは、デバイス管理システム用の Amazon Bedrock AgentCore
Gateway を作成および設定します。Gateway は MCP（Model Context Protocol）
リクエストのセキュアなエントリポイントとして機能し、Amazon Cognito による
認証を処理し、適切な AWS Lambda 関数ターゲットにリクエストをルーティングします。

スクリプトは以下の操作を実行します:
1. 環境変数から設定を読み込み
2. Amazon Cognito JWT 認証を設定
3. Amazon Bedrock AgentCore Gateway を作成
4. Gateway 情報で環境変数を更新

必須環境変数:
    AWS_REGION: Gateway デプロイ用の AWS リージョン
    ENDPOINT_URL: Amazon Bedrock AgentCore コントロールエンドポイント
    COGNITO_USERPOOL_ID: 認証用の Amazon Cognito User Pool ID
    COGNITO_CLIENT_ID: Amazon Cognito App Client ID
    ROLE_ARN: bedrock-agentcore 権限を持つ IAM ロール ARN
    GATEWAY_NAME: Gateway の名前（オプション）
    GATEWAY_DESCRIPTION: Gateway の説明（オプション）

更新される環境変数:
    GATEWAY_ID: 生成された Gateway 識別子
    GATEWAY_ARN: 生成された Gateway ARN
    GATEWAY_IDENTIFIER: GATEWAY_ID のエイリアス

使用例:
    python create_gateway.py

出力:
    ゲートウェイを正常に作成しました！
    ゲートウェイ ID: gateway-12345
    ゲートウェイ ARN: arn:aws:bedrock-agentcore:region:account:gateway/gateway-12345
"""

import boto3
import os
import sys
from dotenv import load_dotenv, set_key
from bedrock_agentcore_starter_toolkit.operations.gateway import GatewayClient

# Initialize the Gateway client
gateway_client = GatewayClient(region_name="us-west-2")

# Load environment variables from .env file
load_dotenv()

# Get environment variables
AWS_REGION = os.getenv('AWS_REGION')
ENDPOINT_URL = os.getenv('ENDPOINT_URL')
COGNITO_USERPOOL_ID = os.getenv('COGNITO_USERPOOL_ID')
COGNITO_CLIENT_ID = os.getenv('COGNITO_CLIENT_ID')
GATEWAY_NAME = os.getenv('GATEWAY_NAME', 'Device-Management-Gateway')
ROLE_ARN = os.getenv('ROLE_ARN')
GATEWAY_DESCRIPTION = os.getenv('GATEWAY_DESCRIPTION', 'Device Management Gateway')

print("エンドポイント URL: {}".format(ENDPOINT_URL))
print("AWS リージョン: {}".format(AWS_REGION))

# Initialize the Bedrock Agent Core Control client
bedrock_agent_core_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=AWS_REGION
)

# Configure the authentication
auth_config = {
    "customJWTAuthorizer": { 
        "allowedClients": [COGNITO_CLIENT_ID],
        "discoveryUrl": f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USERPOOL_ID}/.well-known/openid-configuration"
    }
}

# Create the gateway
try:
    create_response = bedrock_agent_core_client.create_gateway(
        name=GATEWAY_NAME,
        roleArn=ROLE_ARN,  # The IAM Role must have permissions to create/list/get/delete Gateway 
        protocolType='MCP',
        authorizerType='CUSTOM_JWT',
        authorizerConfiguration=auth_config, 
        description=GATEWAY_DESCRIPTION
    )

    # Print the gateway ID and other information
    gateway_id = create_response.get('gatewayId')
    gateway_arn = create_response.get('gatewayArn')
    print("ゲートウェイを正常に作成しました！")
    print(f"ゲートウェイ ID: {gateway_id}")
    print(f"ゲートウェイ ARN: {gateway_arn}")
    print(f"作成時刻: {create_response.get('creationTime')}")

    # Update the .env file with the gateway information
    env_file_path = '.env'
    try:
        if gateway_id:
            set_key(env_file_path, 'GATEWAY_ID', gateway_id)
            print(f".env ファイルを GATEWAY_ID で更新しました: {gateway_id}")
        
        if gateway_arn:
            set_key(env_file_path, 'GATEWAY_ARN', gateway_arn)
            print(f".env ファイルを GATEWAY_ARN で更新しました: {gateway_arn}")
            
        # Also keep the legacy GATEWAY_IDENTIFIER for backward compatibility
        if gateway_id:
            set_key(env_file_path, 'GATEWAY_IDENTIFIER', gateway_id)
            print(f".env ファイルを GATEWAY_IDENTIFIER で更新しました: {gateway_id}")
            
    except Exception as e:
        print(f"警告: .env ファイルの更新に失敗しました: {e}")

except Exception as e:
    print(f"ゲートウェイ作成エラー: {e}")
    sys.exit(1)
