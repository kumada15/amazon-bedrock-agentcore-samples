#!/usr/bin/env python3
"""
Credentials Manager - OAuth2 資格情報プロバイダーの CRUD 操作
"""

import boto3
import json
import sys
import os
import yaml
from datetime import datetime

# Add config directory to path
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
sys.path.append(config_path)

class CredentialsManager:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.control_client = boto3.client('bedrock-agentcore-control', region_name=region)
        
    def list_providers(self):
        """すべての OAuth2 資格情報プロバイダーを一覧表示する"""
        try:
            print("🔍 OAuth2 資格情報プロバイダーを一覧表示中...")
            response = self.control_client.list_oauth2_credential_providers()
            providers = response.get('credentialProviders', [])

            if not providers:
                print("   📋 OAuth2 資格情報プロバイダーが見つかりません")
                return []

            print(f"   📋 {len(providers)} 件のプロバイダーが見つかりました:")
            for provider in providers:
                print(f"      • 名前: {provider.get('name')}")
                print(f"        ARN: {provider.get('credentialProviderArn')}")
                print(f"        ベンダー: {provider.get('credentialProviderVendor')}")
                print(f"        作成日時: {provider.get('createdTime', 'Unknown')}")
                print(f"        更新日時: {provider.get('lastUpdatedTime', 'Unknown')}")
                print()

            return providers

        except Exception as e:
            print(f"❌ プロバイダーの一覧取得中にエラー: {e}")
            print(f"   🔍 デバッグ: 例外タイプ: {type(e)}")
            import traceback
            print(f"   🔍 デバッグ: トレースバック:")
            traceback.print_exc()
            return []
    
    def get_provider(self, provider_name):
        """特定の OAuth2 資格情報プロバイダーの詳細を取得する"""
        try:
            print(f"🔍 プロバイダーの詳細を取得中: {provider_name}")
            response = self.control_client.get_oauth2_credential_provider(
                oauth2CredentialProviderName=provider_name
            )

            provider = response
            print(f"   📋 プロバイダーの詳細:")
            print(f"      • 名前: {provider.get('name')}")
            # print(f"      • ARN: {provider.get('oauth2CredentialProviderArn')}")
            print(f"      • ステータス: {provider.get('status')}")
            print(f"      • ドメイン: {provider.get('domain')}")
            # print(f"      • Type: {provider.get('oauth2CredentialProviderType')}")
            print(f"      • 作成日時: {provider.get('createdTime')}")
            print(f"      • 更新日時: {provider.get('updatedTime')}")

            # Show configuration if available
            config = provider.get('oauth2CredentialProviderConfiguration', {})
            if config:
                print(f"      • 設定:")
                print(f"        - クライアント ID: {'非表示' if config.get('clientId') else '未設定'}")
                print(f"        - 認証サーバー: {'非表示' if config.get('authorizationServer') else '未設定'}")
                print(f"        - トークンエンドポイント: {'非表示' if config.get('tokenEndpoint') else '未設定'}")
                print(f"        - 認証エンドポイント: {'非表示' if config.get('authorizationEndpoint') else '未設定'}")

                # Don't show sensitive fields like client_secret
                sensitive_fields = ['clientSecret', 'privateKey']
                for field in sensitive_fields:
                    if field in config:
                        print(f"        - {field}: [非表示]")

            return provider

        except Exception as e:
            print(f"❌ プロバイダーの取得中にエラー: {e}")
            return None
    
    def create_okta_provider(self, name, domain, client_id, client_secret, scopes=None):
        """Okta OAuth2 資格情報プロバイダーを作成する"""
        try:
            print(f"🆕 Okta OAuth2 プロバイダーを作成中: {name}")
            
            # Default scopes if none provided
            if scopes is None:
                scopes = ["api"]
            
            # Okta configuration
            config = {
                'clientId': client_id,
                'clientSecret': client_secret,
                'authorizationServer': 'default',  # Default Okta auth server
                'tokenEndpoint': f'https://{domain}/oauth2/default/v1/token',
                'authorizationEndpoint': f'https://{domain}/oauth2/default/v1/authorize',
                'scopes': scopes
            }
            
            response = self.control_client.create_oauth2_credential_provider(
                oauth2CredentialProviderName=name,
                domain=domain,
                oauth2CredentialProviderType='OKTA',
                oauth2CredentialProviderConfiguration=config
            )

            print(f"   ✅ プロバイダーが正常に作成されました！")
            print(f"      • ドメイン: {domain}")
            print(f"      • スコープ: {scopes}")

            return response

        except Exception as e:
            print(f"❌ プロバイダーの作成中にエラー: {e}")
            return None
    
    def create_provider_from_config(self, name, config_file=None):
        """設定ファイルから OAuth2 プロバイダーを作成する"""
        try:
            if config_file is None:
                config_file = os.path.join(config_path, 'okta-config.yaml')

            print(f"🆕 設定ファイルから OAuth2 プロバイダーを作成中: {config_file}")
            
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            okta_config = config.get('okta', {})
            domain = okta_config.get('domain')
            client_creds = okta_config.get('client_credentials', {})
            client_id = client_creds.get('client_id')
            
            # Try to get client secret from environment or config
            client_secret = os.getenv('OKTA_CLIENT_SECRET')
            if not client_secret:
                client_secret = client_creds.get('client_secret', '').replace('${OKTA_CLIENT_SECRET}', '')
            
            if not all([domain, client_id, client_secret]):
                print("❌ 必要な Okta 設定が不足しています")
                print(f"   ドメイン: {domain}")
                print(f"   クライアント ID: {client_id}")
                print(f"   クライアントシークレット: {'設定済み' if client_secret else '未設定'}")
                return None
            
            scopes = [client_creds.get('scope', 'api')]
            
            return self.create_okta_provider(name, domain, client_id, client_secret, scopes)

        except Exception as e:
            print(f"❌ 設定ファイルからのプロバイダー作成中にエラー: {e}")
            return None
    
    def delete_provider(self, provider_name):
        """OAuth2 資格情報プロバイダーを削除する"""
        try:
            print(f"🗑️  OAuth2 プロバイダーを削除中: {provider_name}")

            self.control_client.delete_oauth2_credential_provider(
                oauth2CredentialProviderName=provider_name
            )
            print(f"   ✅ プロバイダーの削除を開始しました: {provider_name}")

            return True

        except Exception as e:
            print(f"❌ プロバイダーの削除中にエラー: {e}")
            return False
    
    def update_provider_config(self, provider_name, config_updates):
        """OAuth2 プロバイダーの設定を更新する"""
        try:
            print(f"📝 OAuth2 プロバイダーを更新中: {provider_name}")

            response = self.control_client.update_oauth2_credential_provider(
                oauth2CredentialProviderName=provider_name,
                oauth2CredentialProviderConfiguration=config_updates
            )

            print(f"   ✅ プロバイダーが正常に更新されました！")

            return response

        except Exception as e:
            print(f"❌ プロバイダーの更新中にエラー: {e}")
            return None

def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 credentials_manager.py list")
        print("  python3 credentials_manager.py get <provider_name>")
        print("  python3 credentials_manager.py create-okta <name> <domain> <client_id> <client_secret> [scopes]")
        print("  python3 credentials_manager.py create-from-config <name> [config_file]")
        print("  python3 credentials_manager.py delete <provider_name>")
        print("")
        print("例:")
        print("  python3 credentials_manager.py create-okta my-okta trial-123.okta.com abc123 secret456 api")
        print("  python3 credentials_manager.py create-from-config bac-identity-provider-okta")
        sys.exit(1)
    
    manager = CredentialsManager()
    command = sys.argv[1]
    
    if command == "list":
        manager.list_providers()
    elif command == "get" and len(sys.argv) > 2:
        manager.get_provider(sys.argv[2])
    elif command == "create-okta" and len(sys.argv) > 5:
        name = sys.argv[2]
        domain = sys.argv[3]
        client_id = sys.argv[4]
        client_secret = sys.argv[5]
        scopes = sys.argv[6].split(',') if len(sys.argv) > 6 else None
        manager.create_okta_provider(name, domain, client_id, client_secret, scopes)
    elif command == "create-from-config" and len(sys.argv) > 2:
        name = sys.argv[2]
        config_file = sys.argv[3] if len(sys.argv) > 3 else None
        manager.create_provider_from_config(name, config_file)
    elif command == "delete" and len(sys.argv) > 2:
        manager.delete_provider(sys.argv[2])
    else:
        print("無効なコマンドまたは引数が不足しています")
        sys.exit(1)

if __name__ == "__main__":
    main()
