#!/usr/bin/env python3
"""
Runtime Manager - AgentCore Runtime の CRUD 操作
"""

import boto3
import json
import sys
import os
from datetime import datetime

# Add project root to path for shared config manager
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.config_manager import AgentCoreConfigManager

class RuntimeManager:
    def __init__(self, region=None):
        # Initialize configuration manager
        config_manager = AgentCoreConfigManager()
        base_config = config_manager.get_base_settings()
        
        self.region = region or base_config['aws']['region']
        self.control_client = boto3.client('bedrock-agentcore-control', region_name=self.region)
        
    def list_runtimes(self):
        """すべてのエージェント Runtime を一覧表示する"""
        try:
            print("🔍 エージェントランタイムを一覧表示中...")
            response = self.control_client.list_agent_runtimes()
            runtimes = response.get('agentRuntimes', [])

            if not runtimes:
                print("   📋 ランタイムが見つかりません")
                return []

            print(f"   📋 {len(runtimes)}個のランタイムが見つかりました:")
            for runtime in runtimes:
                print(f"      • Name: {runtime.get('agentRuntimeName')}")
                print(f"        ARN: {runtime.get('agentRuntimeArn')}")
                print(f"        Status: {runtime.get('status')}")
                print(f"        Created: {runtime.get('createdTime', 'Unknown')}")
                print()
                
            return runtimes
            
        except Exception as e:
            print(f"❌ ランタイム一覧取得中にエラー: {e}")
            return []

    def get_runtime(self, runtime_id):
        """特定の Runtime の詳細を取得する"""
        try:
            print(f"🔍 ランタイムの詳細を取得中: {runtime_id}")
            response = self.control_client.get_agent_runtime(agentRuntimeId=runtime_id)
            
            runtime = response
            print(f"   📋 ランタイムの詳細:")
            print(f"      • Name: {runtime.get('agentRuntimeName')}")
            print(f"      • ARN: {runtime.get('agentRuntimeArn')}")
            print(f"      • Status: {runtime.get('status')}")
            print(f"      • Role ARN: {runtime.get('roleArn')}")
            print(f"      • Network Mode: {runtime.get('networkConfiguration', {}).get('networkMode')}")
            print(f"      • Container URI: {runtime.get('agentRuntimeArtifact', {}).get('containerConfiguration', {}).get('containerUri')}")
            
            # Check for authorizer configuration
            auth_config = runtime.get('authorizerConfiguration')
            if auth_config:
                print(f"      • Auth Config: {json.dumps(auth_config, indent=8)}")
            
            return runtime
            
        except Exception as e:
            print(f"❌ ランタイム取得中にエラー: {e}")
            return None

    def delete_runtime(self, runtime_id):
        """Runtime を削除する"""
        try:
            print(f"🗑️  ランタイムを削除中: {runtime_id}")

            # First delete endpoints
            print("   🔗 エンドポイントを確認中...")
            try:
                endpoints_response = self.control_client.list_agent_runtime_endpoints(agentRuntimeId=runtime_id)
                endpoints = endpoints_response.get('agentRuntimeEndpointSummaries', [])
                
                for endpoint in endpoints:
                    endpoint_id = endpoint.get('agentRuntimeEndpointId')
                    print(f"      🗑️  エンドポイントを削除中: {endpoint_id}")
                    self.control_client.delete_agent_runtime_endpoint(
                        agentRuntimeId=runtime_id,
                        agentRuntimeEndpointId=endpoint_id
                    )
                    print(f"      ✅ エンドポイントを削除しました: {endpoint_id}")

            except Exception as ep_error:
                print(f"      ⚠️  エンドポイント処理中にエラー: {ep_error}")
            
            # Delete the runtime
            self.control_client.delete_agent_runtime(agentRuntimeId=runtime_id)
            print(f"   ✅ ランタイム削除を開始しました: {runtime_id}")

            return True

        except Exception as e:
            print(f"❌ ランタイム削除中にエラー: {e}")
            return False
    
    def delete_all_runtimes(self, confirm=False):
        """すべてのエージェント Runtime を削除する"""
        try:
            print("🔍 すべてのエージェントランタイムを検索中...")
            runtimes = self.list_runtimes()

            if not runtimes:
                print("✅ 削除するランタイムが見つかりません")
                return True

            print(f"\n⚠️  警告: すべての{len(runtimes)}個のランタイムが削除されます！")

            if not confirm:
                print("🛑 削除を続行するには --confirm フラグを使用してください")
                print("   例: python3 runtime_manager.py delete-all --confirm")
                return False

            # Confirm deletion
            print(f"\n🗑️  {len(runtimes)}個のランタイムを削除中...")
            
            deleted_count = 0
            failed_count = 0
            
            for i, runtime in enumerate(runtimes, 1):
                runtime_name = runtime.get('agentRuntimeName', 'Unknown')
                runtime_id = runtime.get('agentRuntimeId')
                
                if not runtime_id:
                    # Extract ID from ARN if not directly available
                    arn = runtime.get('agentRuntimeArn', '')
                    if '/runtime/' in arn:
                        runtime_id = arn.split('/runtime/')[-1]
                
                print(f"\n[{i}/{len(runtimes)}] 削除中: {runtime_name} ({runtime_id})")

                if self.delete_runtime(runtime_id):
                    deleted_count += 1
                    print(f"   ✅ 削除に成功しました: {runtime_name}")
                else:
                    failed_count += 1
                    print(f"   ❌ 削除に失敗しました: {runtime_name}")

            print(f"\n📊 削除サマリー:")
            print(f"   ✅ 削除に成功: {deleted_count}")
            print(f"   ❌ 削除に失敗: {failed_count}")
            print(f"   📋 処理した合計: {len(runtimes)}")

            if failed_count == 0:
                print("🎉 すべてのランタイムが正常に削除されました！")
            else:
                print(f"⚠️  {failed_count}個のランタイムの削除に失敗しました - 上記のログを確認してください")
            
            return failed_count == 0
            
        except Exception as e:
            print(f"❌ 全削除操作中にエラー: {e}")
            return False

    def list_endpoints(self, runtime_id):
        """Runtime のエンドポイントを一覧表示する"""
        try:
            print(f"🔍 ランタイムのエンドポイントを一覧表示中: {runtime_id}")
            response = self.control_client.list_agent_runtime_endpoints(agentRuntimeId=runtime_id)
            endpoints = response.get('runtimeEndpoints', [])

            if not endpoints:
                print("   📋 エンドポイントが見つかりません")
                return []

            print(f"   📋 {len(endpoints)}個のエンドポイントが見つかりました:")
            for endpoint in endpoints:
                print(f"      • Name: {endpoint.get('name')}")
                print(f"        ID: {endpoint.get('id')}")
                print(f"        ARN: {endpoint.get('agentRuntimeEndpointArn')}")
                print(f"        Status: {endpoint.get('status')}")
                print()
                
            return endpoints
            
        except Exception as e:
            print(f"❌ エンドポイント一覧取得中にエラー: {e}")
            return []

def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 runtime_manager.py list")
        print("  python3 runtime_manager.py get <runtime_id>")
        print("  python3 runtime_manager.py delete <runtime_id>")
        print("  python3 runtime_manager.py delete-all [--confirm]")
        print("  python3 runtime_manager.py endpoints <runtime_id>")
        sys.exit(1)
    
    manager = RuntimeManager()
    command = sys.argv[1]
    
    if command == "list":
        manager.list_runtimes()
    elif command == "get" and len(sys.argv) > 2:
        manager.get_runtime(sys.argv[2])
    elif command == "delete" and len(sys.argv) > 2:
        manager.delete_runtime(sys.argv[2])
    elif command == "delete-all":
        # Check for --confirm flag
        confirm = "--confirm" in sys.argv
        manager.delete_all_runtimes(confirm=confirm)
    elif command == "endpoints" and len(sys.argv) > 2:
        manager.list_endpoints(sys.argv[2])
    else:
        print("無効なコマンドまたは引数が不足しています")
        sys.exit(1)

if __name__ == "__main__":
    main()