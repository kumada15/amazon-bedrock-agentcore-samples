#!/usr/bin/env python3
"""
Identity Manager - AgentCore Workload Identity の CRUD 操作
"""

import boto3
import json
import sys
import os
from datetime import datetime

# Add config directory to path
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
sys.path.append(config_path)

class IdentityManager:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.control_client = boto3.client('bedrock-agentcore-control', region_name=region)
        
    def list_identities(self):
        """ページネーションサポート付きですべてのワークロードアイデンティティを一覧表示する"""
        try:
            print("🔍 ワークロードアイデンティティを一覧表示中...")
            
            all_identities = []
            next_token = None
            page_count = 0
            
            while True:
                page_count += 1
                
                # Use maximum allowed page size (20)
                if next_token:
                    response = self.control_client.list_workload_identities(
                        maxResults=20,
                        nextToken=next_token
                    )
                else:
                    response = self.control_client.list_workload_identities(maxResults=20)
                
                page_identities = response.get('workloadIdentities', [])
                all_identities.extend(page_identities)
                
                if page_count <= 5 or page_count % 100 == 0:  # Show progress for first 5 pages and every 100th page
                    print(f"   📄 ページ {page_count}: {len(page_identities)} 件のアイデンティティ (合計: {len(all_identities)})")
                
                next_token = response.get('nextToken')
                if not next_token:
                    break
                    
                # Safety limit to prevent infinite loops
                if page_count > 2000:
                    print("      ⚠️  安全のため2000ページで停止しました")
                    break

            if page_count > 5:
                print(f"   📊 ページネーション完了: {page_count} ページ、合計 {len(all_identities)} 件のアイデンティティ")

            if not all_identities:
                print("   📋 ワークロードアイデンティティが見つかりません")
                return []

            print(f"   📋 {len(all_identities)} 件のアイデンティティが見つかりました:")
            # Show only first 10 for readability
            for i, identity in enumerate(all_identities[:10]):
                print(f"      • 名前: {identity.get('name')}")
                print(f"        ARN: {identity.get('workloadIdentityArn')}")
                print(f"        ステータス: {identity.get('status')}")
                print(f"        プリンシパル: {identity.get('principalArn')}")
                print(f"        作成日時: {identity.get('createdTime', 'Unknown')}")
                print()

            if len(all_identities) > 10:
                print(f"      ... 他に {len(all_identities) - 10} 件のアイデンティティがあります")
                print()

            return all_identities

        except Exception as e:
            print(f"❌ アイデンティティの一覧取得中にエラー: {e}")
            return []
    
    def get_identity(self, identity_name):
        """特定のワークロードアイデンティティの詳細を取得する"""
        try:
            print(f"🔍 アイデンティティの詳細を取得中: {identity_name}")
            response = self.control_client.get_workload_identity(name=identity_name)

            identity = response
            print(f"   📋 アイデンティティの詳細:")
            print(f"      • 名前: {identity.get('name')}")
            print(f"      • ARN: {identity.get('workloadIdentityArn')}")
            print(f"      • ステータス: {identity.get('status')}")
            print(f"      • プリンシパル ARN: {identity.get('principalArn')}")
            print(f"      • Agent Runtime ARN: {identity.get('agentRuntimeArn')}")
            print(f"      • 作成日時: {identity.get('createdTime')}")
            print(f"      • 更新日時: {identity.get('updatedTime')}")

            # Show configuration if available
            config = identity.get('workloadIdentityConfiguration', {})
            if config:
                print(f"      • 設定:")
                print(f"        - コールバック URL: {config.get('callbackUrls', [])}")
                print(f"        - 許可されたオーディエンス: {config.get('allowedAudiences', [])}")

            return identity

        except Exception as e:
            print(f"❌ アイデンティティの取得中にエラー: {e}")
            return None
    
    def create_identity(self, name, principal_arn, callback_urls=None, allowed_audiences=None):
        """新しいワークロードアイデンティティを作成する"""
        try:
            print(f"🆕 ワークロードアイデンティティを作成中: {name}")
            
            # Build configuration
            config = {}
            if callback_urls:
                config['callbackUrls'] = callback_urls
            if allowed_audiences:
                config['allowedAudiences'] = allowed_audiences
            
            request = {
                'workloadIdentityName': name,
                'principalArn': principal_arn
            }
            
            if config:
                request['workloadIdentityConfiguration'] = config
            
            response = self.control_client.create_workload_identity(**request)

            print(f"   ✅ アイデンティティが正常に作成されました！")
            print(f"      • ARN: {response.get('workloadIdentityArn')}")

            return response

        except Exception as e:
            print(f"❌ アイデンティティの作成中にエラー: {e}")
            return None
    
    def delete_identity(self, identity_name):
        """ワークロードアイデンティティを削除する"""
        try:
            print(f"🗑️  ワークロードアイデンティティを削除中: {identity_name}")

            self.control_client.delete_workload_identity(name=identity_name)
            print(f"   ✅ アイデンティティの削除を開始しました: {identity_name}")

            return True

        except Exception as e:
            print(f"❌ アイデンティティの削除中にエラー: {e}")
            return False
    
    def delete_all_identities(self, confirm=False):
        """適切なページネーションサポート付きですべてのワークロードアイデンティティを削除する（危険な操作）"""
        if not confirm:
            print("⚠️  警告: これによりすべてのワークロードアイデンティティが削除されます！")
            print("⚠️  この操作はすべてのページのアイデンティティを処理します。20,000件以上になる可能性があります！")
            response = input("確認するには 'DELETE ALL' と入力してください: ")
            if response != "DELETE ALL":
                print("❌ 操作がキャンセルされました")
                return False

        print("🔍 すべてのアイデンティティの完全なリストを取得中（時間がかかる場合があります）...")
        identities = self.list_identities()

        if not identities:
            print("✅ 削除するアイデンティティがありません")
            return True

        print(f"\n🗑️  {len(identities)} 件のアイデンティティの一括削除を開始中...")
        print("📊 バッチごとに進捗を表示しながら処理します...")
        
        deleted_count = 0
        failed_count = 0
        batch_size = 100  # Process in batches for better progress tracking
        
        for i in range(0, len(identities), batch_size):
            batch = identities[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(identities) + batch_size - 1) // batch_size
            
            print(f"\n📦 バッチ {batch_num}/{total_batches} を処理中 ({len(batch)} 件のアイデンティティ)...")
            
            batch_deleted = 0
            batch_failed = 0
            
            for identity in batch:
                identity_name = identity.get('name')
                if identity_name:
                    if self.delete_identity(identity_name):
                        deleted_count += 1
                        batch_deleted += 1
                    else:
                        failed_count += 1
                        batch_failed += 1
                else:
                    print(f"⚠️  名前がないアイデンティティをスキップ: {identity}")
                    failed_count += 1
                    batch_failed += 1

            print(f"   📊 バッチ {batch_num} 結果: {batch_deleted} 件削除、{batch_failed} 件失敗")
            print(f"   📈 全体の進捗: {deleted_count}/{len(identities)} ({(deleted_count/len(identities)*100):.1f}%)")
            
            # Add a small delay between batches to avoid rate limiting
            if batch_num < total_batches:
                import time
                time.sleep(1)
        
        print(f"\n📊 一括削除の最終結果:")
        print(f"   ✅ 正常に削除: {deleted_count} 件")
        print(f"   ❌ 削除失敗: {failed_count} 件")
        print(f"   📋 処理合計: {len(identities)} 件")
        print(f"   📈 成功率: {(deleted_count/len(identities)*100):.1f}%")

        # Verify deletion by checking remaining count
        print(f"\n🔍 削除を確認中（速度のため最初のページのみチェック）...")
        try:
            response = self.control_client.list_workload_identities(maxResults=20)
            remaining_identities = response.get('workloadIdentities', [])
            has_more = 'nextToken' in response

            print(f"   📊 最初のページの結果: {len(remaining_identities)} 件のアイデンティティ")
            if has_more:
                print("   📄 追加のページがあります - 一部のアイデンティティがまだ残っている可能性があります")
                print("   💡 残りのアイデンティティを削除するには、スクリプトを再度実行する必要があるかもしれません")
            elif len(remaining_identities) == 0:
                print("   🎉 最初のページが空です - 削除が成功したようです！")
            else:
                print(f"   ⚠️  最初のページにまだ {len(remaining_identities)} 件のアイデンティティが残っています")

        except Exception as e:
            print(f"   ❌ 削除の確認中にエラー: {e}")

        return failed_count == 0
    
    def update_identity(self, identity_name, callback_urls=None, allowed_audiences=None):
        """ワークロードアイデンティティの設定を更新する"""
        try:
            print(f"📝 ワークロードアイデンティティを更新中: {identity_name}")

            # Build configuration
            config = {}
            if callback_urls:
                config['callbackUrls'] = callback_urls
            if allowed_audiences:
                config['allowedAudiences'] = allowed_audiences

            if not config:
                print("   ⚠️  更新する設定が提供されていません")
                return None

            response = self.control_client.update_workload_identity(
                workloadIdentityName=identity_name,
                workloadIdentityConfiguration=config
            )

            print(f"   ✅ アイデンティティが正常に更新されました！")
            print(f"      • 更新された設定: {json.dumps(config, indent=8)}")

            return response

        except Exception as e:
            print(f"❌ アイデンティティの更新中にエラー: {e}")
            return None

def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 identity_manager.py list")
        print("  python3 identity_manager.py get <identity_name>")
        print("  python3 identity_manager.py create <name> <principal_arn> [callback_urls] [allowed_audiences]")
        print("  python3 identity_manager.py delete <identity_name>")
        print("  python3 identity_manager.py delete-all [--confirm]")
        print("  python3 identity_manager.py update <identity_name> [callback_urls] [allowed_audiences]")
        print("")
        print("例:")
        print("  python3 identity_manager.py create my-identity arn:aws:iam::123456789012:role/my-role")
        print("  python3 identity_manager.py update my-identity 'http://localhost:8080/callback' 'my-audience'")
        print("  python3 identity_manager.py delete-all  # 対話形式の確認")
        print("  python3 identity_manager.py delete-all --confirm  # 確認をスキップ")
        print("")
        print("⚠️  警告: delete-all はすべてのページを処理し、20,000件以上のアイデンティティを削除する可能性があります！")
        sys.exit(1)
    
    manager = IdentityManager()
    command = sys.argv[1]
    
    if command == "list":
        manager.list_identities()
    elif command == "get" and len(sys.argv) > 2:
        manager.get_identity(sys.argv[2])
    elif command == "create" and len(sys.argv) > 3:
        name = sys.argv[2]
        principal_arn = sys.argv[3]
        callback_urls = [sys.argv[4]] if len(sys.argv) > 4 else None
        allowed_audiences = [sys.argv[5]] if len(sys.argv) > 5 else None
        manager.create_identity(name, principal_arn, callback_urls, allowed_audiences)
    elif command == "delete" and len(sys.argv) > 2:
        manager.delete_identity(sys.argv[2])
    elif command == "delete-all":
        confirm = "--confirm" in sys.argv
        manager.delete_all_identities(confirm=confirm)
    elif command == "update" and len(sys.argv) > 2:
        name = sys.argv[2]
        callback_urls = [sys.argv[3]] if len(sys.argv) > 3 else None
        allowed_audiences = [sys.argv[4]] if len(sys.argv) > 4 else None
        manager.update_identity(name, callback_urls, allowed_audiences)
    else:
        print("無効なコマンドまたは引数が不足しています")
        sys.exit(1)

if __name__ == "__main__":
    main()