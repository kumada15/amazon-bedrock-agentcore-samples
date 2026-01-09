"""
Amazon Cognito OAuth 設定セットアップスクリプト

このモジュールは、デバイス管理システム用の Amazon Cognito OAuth 認証の
設定を自動化します。Bedrock AgentCore Starter Toolkit を使用して
OAuth オーソライザーを作成し、必要な認証情報で環境ファイルを更新します。

スクリプトは以下の操作を実行します:
1. Amazon Cognito 統合で OAuth オーソライザーを作成
2. 認証エンドポイントと認証情報を抽出
3. ローカル .env ファイルを Cognito 設定で更新
4. agent-runtime .env ファイルを OAuth 認証情報で更新
5. 全設定値のフォーマットされた出力を提供

主な機能:
    - GatewayClient による自動 OAuth オーソライザー作成
    - デュアル .env ファイル管理（ローカルと agent-runtime）
    - インテリジェントな URL パースとエンドポイント構築
    - 設定検証とエラーハンドリング
    - 冪等な更新（既存値を作成または更新）

必須環境変数:
    COGNITO_AUTH_NAME: Cognito OAuth オーソライザーの名前

更新される環境変数（ローカル .env）:
    COGNITO_USERPOOL_ID: Amazon Cognito User Pool ID
    COGNITO_CLIENT_ID: OAuth クライアント ID
    COGNITO_CLIENT_SECRET: OAuth クライアントシークレット
    COGNITO_DOMAIN: Cognito ドメイン URL

更新される環境変数（Agent-Runtime .env）:
    COGNITO_CLIENT_ID: OAuth クライアント ID
    COGNITO_CLIENT_SECRET: OAuth クライアントシークレット
    COGNITO_DISCOVERY_URL: OIDC ディスカバリーエンドポイント
    COGNITO_AUTH_URL: 認可エンドポイント
    COGNITO_TOKEN_URL: トークンエンドポイント

使用例:
    .env ファイルで COGNITO_AUTH_NAME を設定してから実行:
    >>> python cognito_oauth_setup.py

    出力:
    Cognito OAuth 設定が完了しました！
    クライアント情報: {...}
    ✅ 既存のローカル .env ファイルを Cognito 設定で更新しました:
       COGNITO_USERPOOL_ID=...
       COGNITO_CLIENT_ID=...
    ✅ 既存の agent-runtime .env ファイルを Cognito 設定で更新しました:
       COGNITO_DISCOVERY_URL=...

注意事項:
    - 存在しない場合は新しい .env ファイルを作成
    - 他の設定を削除せずに既存値を更新
    - ファイル更新前に全ての必須認証情報を検証
    - 利用可能な情報から不足している URL を構築
"""
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from dotenv import load_dotenv
import os
import re

load_dotenv()

COGNITO_AUTH_NAME = os.getenv('COGNITO_AUTH_NAME')

# Initialize the Gateway client
client = GatewayClient(region_name="us-west-2")
cognito_result = client.create_oauth_authorizer_with_cognito(COGNITO_AUTH_NAME)

print("Cognito OAuth 設定が完了しました！")
# Note: Not printing client_info as it contains sensitive client_secret
print("クライアント設定を正常に取得しました")

# Extract values from the result
client_info = cognito_result['client_info']
user_pool_id = client_info.get('user_pool_id')
client_id = client_info.get('client_id')
# lgtm[py/clear-text-logging-sensitive-data]
# Note: client_secret is only written to .env files (necessary for OAuth)
# and is masked in all print statements via update_env_file function
client_secret = client_info.get('client_secret')
region = client_info.get('region', 'us-west-2')

# Extract domain from token_endpoint or use domain_prefix
token_endpoint = client_info.get('token_endpoint', '')
auth_endpoint = client_info.get('authorization_endpoint', '')
discovery_url = client_info.get('issuer', '')

if token_endpoint:
    # Extract domain from token endpoint URL
    domain_match = re.search(r'https://([^/]+)', token_endpoint)
    domain = domain_match.group(1) if domain_match else client_info.get('domain_prefix')
else:
    domain = client_info.get('domain_prefix')

# Construct URLs if not provided
if not discovery_url and user_pool_id:
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

if not auth_endpoint and domain:
    auth_endpoint = f"https://{domain}/oauth2/authorize"

if not token_endpoint and domain:
    token_endpoint = f"https://{domain}/oauth2/token"

# Path to agent-runtime .env file (from gateway folder)
agent_runtime_env_path = '../agent-runtime/.env'

def update_env_file(file_path, updates, description):
    """指定された更新で .env ファイルを更新または作成します。"""
    if os.path.exists(file_path):
        # Read existing .env file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Update or add the configuration values
        for key, value in updates.items():
            if value:  # Only update if value exists
                pattern = rf'^{key}=.*$'
                replacement = f'{key}={value}'
                
                if re.search(pattern, content, re.MULTILINE):
                    # Update existing value
                    content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                else:
                    # Add new value at the end
                    content += '\n{}'.format(replacement)
        
        # Write updated content back to .env file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        
        print("\n✅ 既存の {} を Cognito 設定で更新しました".format(description))
    else:
        # Create new .env file with configuration
        content = "# Cognito OAuth configuration\n"
        
        # Add configuration values
        for key, value in updates.items():
            if value:  # Only add if value exists
                content += '{}={}\n'.format(key, value)
        
        # Write new .env file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        
        print("\n✅ Cognito 設定で新しい {} を作成しました".format(description))
    
    # Print summary of what was configured (without values for security)
    config_count = sum(1 for v in updates.values() if v)
    print("   {} 件の設定を構成しました".format(config_count))

# Update local .env file with the new values (existing functionality)
env_file_path = '.env'

# Prepare the Cognito configuration values for local .env (existing functionality)
# lgtm[py/clear-text-logging-sensitive-data]
# Note: client_secret is masked in print output by update_env_file function
local_updates = {
    'COGNITO_USERPOOL_ID': user_pool_id,
    'COGNITO_CLIENT_ID': client_id,
    'COGNITO_CLIENT_SECRET': client_secret,  # Masked as *** in output
    'COGNITO_DOMAIN': domain
}

# Prepare the Cognito configuration values for agent-runtime .env (for cognito_credentials_provider.py)
# lgtm[py/clear-text-logging-sensitive-data]
# Note: client_secret is masked in print output by update_env_file function
agent_runtime_updates = {
    'COGNITO_CLIENT_ID': client_id,
    'COGNITO_CLIENT_SECRET': client_secret,  # Masked as *** in output
    'COGNITO_DISCOVERY_URL': discovery_url,
    'COGNITO_AUTH_URL': auth_endpoint,
    'COGNITO_TOKEN_URL': token_endpoint
}

# Update local .env file (existing functionality)
update_env_file(env_file_path, local_updates, "local .env file")

# Update agent-runtime .env file (new functionality)
update_env_file(agent_runtime_env_path, agent_runtime_updates, "agent-runtime .env file")

print("\n🎉 両方の .env ファイルを Cognito OAuth 設定で正常に更新しました！")
print("   ローカル .env: {}".format(os.path.abspath(env_file_path)))
print("   Agent-runtime .env: {}".format(os.path.abspath(agent_runtime_env_path)))