#!/usr/bin/env python3
import os
import json
import boto3
import shutil
from bedrock_agentcore_starter_toolkit.operations.gateway import GatewayClient

def main():
    # リージョンを設定
    region = os.environ.get('AWS_REGION', 'us-west-2')
    print(f"AWS リージョン: {region}")
    
    # GatewayClient を作成
    client = GatewayClient(region_name=region)
    
    # IAM ロール ARN を読み込む
    role_arn = os.environ.get('ROLE_ARN')
    print(f"環境変数からの Role ARN: {role_arn}")
    
    if not role_arn:
        # config ファイルから読み込みを試みる
        config_paths = [
            "./config/iam_config.env",  # プロジェクトルートから実行時
            "../config/iam_config.env",  # scripts ディレクトリから実行時
        ]

        for config_path in config_paths:
            if os.path.exists(config_path):
                print(f"config ファイルを検出: {config_path}")
                with open(config_path, "r") as f:
                    for line in f:
                        if line.startswith("export GATEWAY_ROLE_ARN="):
                            role_arn = line.replace("export GATEWAY_ROLE_ARN=", "").strip()
                            break
                break
    
    if not role_arn:
        print("エラー: IAM ロール ARN が見つかりません。先に create_iam_roles.sh を実行してください。")
        return

    print(f"使用する IAM ロール ARN: {role_arn}")
    
    # 既存の Cognito 設定を読み込む
    cognito_config = {}
    config_paths = [
        "./config/cognito_config.env",  # プロジェクトルートから実行時
        "../config/cognito_config.env",  # scripts ディレクトリから実行時
    ]

    for config_path in config_paths:
        if os.path.exists(config_path):
            print(f"Cognito 設定ファイルを検出: {config_path}")
            with open(config_path, "r") as f:
                for line in f:
                    if line.startswith("export "):
                        key, value = line.replace("export ", "").strip().split("=", 1)
                        cognito_config[key] = value
            break
    
    if not cognito_config:
        print("警告: 既存の Cognito 設定が見つかりません。新しい設定が作成されます。")
        # GatewayClient を使用して Gateway を作成（新しい Cognito authorizer を作成）
        gateway = client.create_mcp_gateway(
            name="DB-Performance-Analyzer-Gateway",
            role_arn=role_arn
        )
    else:
        print("既存の Cognito 設定を使用します")
        # 既存の Cognito 設定で Gateway を作成
        gateway = client.client.create_gateway(
            name="DB-Performance-Analyzer-Gateway",
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "discoveryUrl": cognito_config["COGNITO_DISCOVERY_URL"],
                    "allowedClients": [cognito_config["COGNITO_APP_CLIENT_ID"]]
                }
            },
            description="Gateway for DB Performance Analysis"
        )
    
    print(f"Gateway を作成しました。ID: {gateway['gatewayId']}")
    print(f"Gateway ARN: {gateway['gatewayArn']}")
    
    # 設定ファイルに書き込む内容を取得
    config_content = f"""export GATEWAY_IDENTIFIER={gateway['gatewayId']}
export GATEWAY_ARN={gateway['gatewayArn']}
export REGION={region}
"""
    
    # プロジェクトの config ディレクトリに保存
    current_dir = os.getcwd()
    os.makedirs(os.path.join(current_dir, "config"), exist_ok=True)
    with open(os.path.join(current_dir, "config/gateway_config.env"), "w") as f:
        f.write(config_content)
    print(f"Gateway 設定を {os.path.join(current_dir, 'config/gateway_config.env')} に保存しました")
    
    # scripts ディレクトリから実行している場合、親の config ディレクトリの存在を確認
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(current_dir) == "scripts":
        print("scripts ディレクトリから実行中、config へのアクセスを確保しています...")
        config_path = os.path.join(script_dir, "../config")
        if not os.path.exists(config_path):
            os.makedirs(config_path, exist_ok=True)
    
    return gateway

if __name__ == "__main__":
    main()