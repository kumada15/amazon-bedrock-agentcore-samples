#!/usr/bin/env python3
import os
import sys
import json
import requests

def main():
    # cognito_config.env ファイルを検索
    config_paths = [
        "./config/cognito_config.env",  # プロジェクトルートから実行時
        "../config/cognito_config.env",  # scripts ディレクトリから実行時
    ]

    # scripts ディレクトリから実行している場合、正しい場所を検索するようにする
    current_dir = os.getcwd()
    if os.path.basename(current_dir) == "scripts":
        config_paths = [
            "../config/cognito_config.env",  # scripts ディレクトリから実行時
            "./config/cognito_config.env",  # フォールバック
        ]
    
    config_file = None
    for path in config_paths:
        if os.path.exists(path):
            config_file = path
            print(f"Cognito 設定を検出: {path}")
            break
    
    if not config_file:
        print("エラー: cognito_config.env が見つかりません")
        sys.exit(1)
    
    # 環境変数を読み込む
    cognito_config = {}
    with open(config_file, 'r') as f:
        for line in f:
            if line.startswith('export '):
                key, value = line.replace('export ', '').strip().split('=', 1)
                cognito_config[key] = value.strip('"\'')
    
    # トークンを取得
    url = f"https://{cognito_config['COGNITO_DOMAIN_NAME']}.auth.us-west-2.amazoncognito.com/oauth2/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': cognito_config['COGNITO_APP_CLIENT_ID'],
        'client_secret': cognito_config['COGNITO_CLIENT_SECRET']
    }
    
    try:
        print(f"トークンをリクエスト中: {url}")
        print(f"使用するクライアント ID: {cognito_config['COGNITO_APP_CLIENT_ID']}")
        
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        token = token_data.get('access_token')
        
        if not token:
            print(f"エラー: レスポンスにアクセストークンがありません。完全なレスポンス: {token_data}")
            sys.exit(1)

        print(f"トークンを受信しました: {token[:20]}...")
        print(f"トークンの有効期限: {token_data.get('expires_in', '不明')} 秒")
        
        # cognito_config.env を更新
        with open(config_file, 'r') as f:
            lines = f.readlines()
        
        with open(config_file, 'w') as f:
            for line in lines:
                if line.startswith('export COGNITO_ACCESS_TOKEN='):
                    f.write(f'export COGNITO_ACCESS_TOKEN={token}\n')
                else:
                    f.write(line)
        
        # mcp.json を更新
        mcp_file = os.path.expanduser('~/.aws/amazonq/mcp.json')
        try:
            with open(mcp_file, 'r') as f:
                mcp_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # mcp.json が存在しないか無効な場合は新規作成
            mcp_data = {"mcpServers": {}}

        # config から Gateway ID を取得
        gateway_config_paths = [
            "./config/gateway_config.env",  # プロジェクトルートから実行時
            "../config/gateway_config.env",  # scripts ディレクトリから実行時
        ]

        # scripts ディレクトリから実行している場合、正しい場所を検索するようにする
        if os.path.basename(current_dir) == "scripts":
            gateway_config_paths = [
                "../config/gateway_config.env",  # scripts ディレクトリから実行時
                "./config/gateway_config.env",  # フォールバック
            ]
        
        gateway_id = None
        for path in gateway_config_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    for line in f:
                        if line.startswith('export GATEWAY_IDENTIFIER='):
                            gateway_id = line.replace('export GATEWAY_IDENTIFIER=', '').strip()
                            break
                if gateway_id:
                    break
        
        if not gateway_id:
            print("警告: 設定ファイルで GATEWAY_IDENTIFIER が見つかりません")
        else:
            # Gateway ID とトークンで mcp.json を更新
            gateway_url = f"https://{gateway_id}.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"
            server_name = "db-performance-analyzer"

            # 既存のエントリを更新
            for server in mcp_data.get('mcpServers', {}):
                for i, arg in enumerate(mcp_data['mcpServers'][server]['args']):
                    if arg.startswith('Authorization: Bearer '):
                        mcp_data['mcpServers'][server]['args'][i] = f'Authorization: Bearer {token}'

            # エントリが存在しない場合は追加
            if server_name not in mcp_data.get('mcpServers', {}):
                mcp_data.setdefault('mcpServers', {})[server_name] = {
                    "command": "npx",
                    "timeout": 60000,
                    "args": [
                        "mcp-remote@latest",
                        gateway_url,
                        "--header",
                        f"Authorization: Bearer {token}"
                    ]
                }
                print(f"mcp.json に {server_name} のエントリを追加しました")

            with open(mcp_file, 'w') as f:
                json.dump(mcp_data, f, indent=2)

        return token

    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()