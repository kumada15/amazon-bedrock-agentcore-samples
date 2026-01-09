#!/usr/bin/env python3
"""
OAuth テストスクリプト - AgentCore Identity サービスを使用した OAuth トークン生成のテスト
"""

import boto3
import json
import sys
import os
import yaml
from datetime import datetime

# Add project root to path for shared config manager
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.config_manager import AgentCoreConfigManager

class OAuthTester:
    def __init__(self, region=None):
        # Initialize configuration manager
        config_manager = AgentCoreConfigManager()
        base_config = config_manager.get_base_settings()
        
        self.region = region or base_config['aws']['region']
        self.agentcore_client = boto3.client('bedrock-agentcore', region_name=self.region)
        self.control_client = boto3.client('bedrock-agentcore-control', region_name=self.region)
        
    def get_workload_token(self, workload_name):
        """指定されたワークロードのワークロードアクセストークンを取得する"""
        try:
            print(f"🔐 ワークロードアクセストークンを取得中: {workload_name}")

            response = self.agentcore_client.get_workload_access_token(
                workloadName=workload_name
            )

            token = response.get('workloadAccessToken')
            print(f"   ✅ ワークロードトークンを取得しました（長さ: {len(token) if token else 0}）")
            print(f"   🔑 トークンプレビュー: {token[:30]}..." if token else "   ❌ トークンが返されませんでした")

            return token

        except Exception as e:
            print(f"❌ ワークロードトークンの取得中にエラー: {e}")
            return None
    
    def get_oauth_token(self, workload_token, provider_name, scopes=None, auth_flow="M2M"):
        """ワークロードトークンを使用して OAuth2 トークンを取得する"""
        try:
            print(f"🎫 プロバイダーから OAuth2 トークンを取得中")

            if scopes is None:
                scopes = ["api"]

            print(f"   📋 スコープ: {scopes}")
            print(f"   🔄 認証フロー: {auth_flow}")
            
            response = self.agentcore_client.get_resource_oauth2_token(
                workloadIdentityToken=workload_token,
                resourceCredentialProviderName=provider_name,
                scopes=scopes,
                oauth2Flow=auth_flow,
                forceAuthentication=False
            )
            
            access_token = response.get('accessToken')
            auth_url = response.get('authorizationUrl')
            
            if access_token:
                print(f"   ✅ OAuth2 トークンを正常に取得しました！")
                print(f"   🔑 トークンプレビュー: {access_token[:30]}...")
                print(f"   📏 トークン長: {len(access_token)}")
                return access_token
            elif auth_url:
                print(f"   🔗 認証が必要です: {auth_url}")
                return None
            else:
                print(f"   ❌ トークンまたは認証 URL が返されませんでした")
                return None

        except Exception as e:
            print(f"❌ OAuth トークンの取得中にエラー: {e}")
            return None
    
    def test_full_flow(self, workload_name, provider_name, scopes=None):
        """完全な OAuth フローをテストする: ワークロードトークン -> OAuth トークン"""
        try:
            print("🚀 完全な OAuth フローをテスト中")
            print("=" * 50)

            # Step 1: Get workload token
            print("\n📍 ステップ 1: ワークロードアクセストークンを取得")
            workload_token = self.get_workload_token(workload_name)
            if not workload_token:
                print("❌ ワークロードトークンの取得に失敗しました。続行できません。")
                return False

            # Step 2: Get OAuth token
            print("\n📍 ステップ 2: OAuth2 トークンを取得")
            oauth_token = self.get_oauth_token(workload_token, provider_name, scopes)
            if not oauth_token:
                print("❌ OAuth トークンの取得に失敗しました。")
                return False

            print("\n🎉 成功！完全な OAuth フローが動作しています！")
            print("=" * 50)
            print(f"✅ ワークロード: {workload_name}")
            print(f"✅ スコープ: {scopes or ['api']}")
            print(f"✅ トークンを取得し、使用可能な状態です")

            return True

        except Exception as e:
            print(f"❌ OAuth フローテスト中にエラー: {e}")
            return False
    
    def test_with_config(self, workload_name=None, provider_name=None):
        """設定ファイルを使用して OAuth をテストする"""
        try:
            print("🔧 設定ファイルを使用して OAuth をテスト中")
            
            # Initialize configuration manager
            config_manager = AgentCoreConfigManager()
            dynamic_config = config_manager.get_dynamic_config()
            base_config = config_manager.get_base_settings()
            
            # Get OAuth provider config from dynamic configuration
            oauth_provider_config = dynamic_config.get('oauth_provider', {})
            
            if oauth_provider_config:
                if not provider_name:
                    provider_name = oauth_provider_config.get('provider_name', 'bac-identity-provider-okta')
                
                scopes = ['api']  # Default scopes
                
                print(f"   📋 使用するスコープ: {scopes}")
            else:
                print("   ⚠️  OAuth プロバイダー設定が見つかりません。デフォルトを使用します")
                provider_name = provider_name or 'bac-identity-provider-okta'
                scopes = ['api']

            # Get workload name from base config
            if not workload_name:
                workload_name = base_config.get('runtime', {}).get('diy_agent', {}).get('name', 'bac-diy')
                print(f"   📋 設定からワークロードを使用: {workload_name}")
            
            return self.test_full_flow(workload_name, provider_name, scopes)
            
        except Exception as e:
            print(f"❌ 設定を使用したテスト中にエラー: {e}")
            return False
    
    def list_available_resources(self):
        """参照用に利用可能なワークロードアイデンティティと OAuth プロバイダーを一覧表示する"""
        try:
            print("📋 テスト用の利用可能なリソース")
            print("=" * 40)

            # List workload identities
            print("\n🆔 ワークロードアイデンティティ:")
            try:
                identities = self.control_client.list_workload_identities()
                identity_list = identities.get('workloadIdentities', [])
                if identity_list:
                    for identity in identity_list:
                        print(f"   • {identity.get('name')} ({identity.get('status')})")
                else:
                    print("   📭 ワークロードアイデンティティが見つかりません")
            except Exception as e:
                print(f"   ❌ アイデンティティの一覧取得中にエラー: {e}")

            # List OAuth providers
            print("\n🔐 OAuth2 資格情報プロバイダー:")
            try:
                providers = self.control_client.list_oauth2_credential_providers()
                provider_list = providers.get('credentialProviders', [])
                if provider_list:
                    for provider in provider_list:
                        print(f"   • {provider.get('name')}")
                        print(f"     ARN: {provider.get('credentialProviderArn')}")
                        print(f"     ベンダー: {provider.get('credentialProviderVendor')}")
                else:
                    print("   📭 OAuth2 プロバイダーが見つかりません")
            except Exception as e:
                print(f"   ❌ プロバイダーの一覧取得中にエラー: {e}")

            return True

        except Exception as e:
            print(f"❌ リソースの一覧取得中にエラー: {e}")
            return False

def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 oauth_test.py list                           # 利用可能なリソースを一覧表示")
        print("  python3 oauth_test.py test-config                    # 設定ファイルを使用してテスト")
        print("  python3 oauth_test.py test <workload> <provider>     # 特定のワークロード/プロバイダーをテスト")
        print("  python3 oauth_test.py workload-token <workload>      # ワークロードトークンのみを取得")
        print("  python3 oauth_test.py oauth-token <workload> <provider> [scopes]  # OAuth トークンを取得")
        print("")
        print("例:")
        print("  python3 oauth_test.py test-config")
        print("  python3 oauth_test.py test bac-diy bac-identity-provider-okta")
        print("  python3 oauth_test.py oauth-token bac-diy bac-identity-provider-okta api,read")
        sys.exit(1)
    
    tester = OAuthTester()
    command = sys.argv[1]
    
    if command == "list":
        tester.list_available_resources()
    elif command == "test-config":
        tester.test_with_config()
    elif command == "test" and len(sys.argv) > 3:
        workload = sys.argv[2]
        provider = sys.argv[3]
        tester.test_full_flow(workload, provider)
    elif command == "workload-token" and len(sys.argv) > 2:
        workload = sys.argv[2]
        tester.get_workload_token(workload)
    elif command == "oauth-token" and len(sys.argv) > 3:
        workload = sys.argv[2]
        provider = sys.argv[3]
        scopes = sys.argv[4].split(',') if len(sys.argv) > 4 else None
        
        # First get workload token
        workload_token = tester.get_workload_token(workload)
        if workload_token:
            tester.get_oauth_token(workload_token, provider, scopes)
    else:
        print("無効なコマンドまたは引数が不足しています")
        sys.exit(1)

if __name__ == "__main__":
    main()
