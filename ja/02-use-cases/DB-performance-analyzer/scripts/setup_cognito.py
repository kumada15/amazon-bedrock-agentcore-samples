#!/usr/bin/env python3
import os
import json
import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway import GatewayClient

def main():
    # リージョンを設定
    region = os.environ.get('AWS_REGION', 'us-west-2')
    print(f"AWS リージョン: {region}")

    # GatewayClient を作成
    client = GatewayClient(region_name=region)
    
    # Cognito authorizer を作成
    print("Cognito authorizer を作成中...")
    cognito_result = client.create_oauth_authorizer_with_cognito("db-performance-analyzer")
    
    # Cognito の詳細を表示
    print(f"Cognito User Pool ID: {cognito_result['client_info']['user_pool_id']}")
    print(f"Cognito Client ID: {cognito_result['client_info']['client_id']}")
    print(f"Cognito ドメイン: {cognito_result['client_info']['domain_prefix']}")
    print(f"Discovery URL: {cognito_result['authorizer_config']['customJWTAuthorizer']['discoveryUrl']}")
    
    # トークンを取得
    print("OAuth トークンを取得中...")
    token = client.get_access_token_for_cognito(cognito_result['client_info'])
    print(f"アクセストークン: {token[:20]}...")
    
    # 設定ファイルに書き込む内容を取得
    config_content = f"""export COGNITO_USERPOOL_ID={cognito_result['client_info']['user_pool_id']}
export COGNITO_APP_CLIENT_ID={cognito_result['client_info']['client_id']}
export COGNITO_CLIENT_SECRET={cognito_result['client_info']['client_secret']}
export COGNITO_DOMAIN_NAME={cognito_result['client_info']['domain_prefix']}
export COGNITO_DISCOVERY_URL={cognito_result['authorizer_config']['customJWTAuthorizer']['discoveryUrl']}
export COGNITO_ACCESS_TOKEN={token}
"""
    
    # プロジェクトの config ディレクトリに保存
    current_dir = os.getcwd()
    os.makedirs(os.path.join(current_dir, "config"), exist_ok=True)
    with open(os.path.join(current_dir, "config/cognito_config.env"), "w") as f:
        f.write(config_content)
    print(f"Cognito 設定を {os.path.join(current_dir, 'config/cognito_config.env')} に保存しました")
    
    # scripts ディレクトリから実行している場合、親の config ディレクトリへのシンボリックリンクを作成
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(current_dir) == "scripts":
        print("scripts ディレクトリから実行中、config へのアクセスを確保しています...")
        config_path = os.path.join(script_dir, "../config")
        if not os.path.exists(config_path):
            os.makedirs(config_path, exist_ok=True)
    
    print("Cognito のセットアップが正常に完了しました")
    
    # 他のスクリプトで使用するために Cognito の結果を返す
    return cognito_result, token


if __name__ == "__main__":
    main()
