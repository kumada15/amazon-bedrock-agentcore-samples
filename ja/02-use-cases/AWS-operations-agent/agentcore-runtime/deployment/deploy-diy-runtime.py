#!/usr/bin/env python3

# ============================================================================
# IMPORTS
# ============================================================================

import boto3
import time
import sys
import os
import yaml

# ============================================================================
# CONFIGURATION
# ============================================================================

# Add project root to path for shared config manager
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from shared.config_manager import AgentCoreConfigManager

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def update_config_with_arns(config_manager, runtime_arn, endpoint_arn):
    """新しい ARN で動的設定を更新する"""
    print(f"\n📝 新しい DIY runtime ARN で動的設定を更新中...")
    try:
        # Update dynamic configuration
        updates = {
            "runtime": {
                "diy_agent": {
                    "arn": runtime_arn
                }
            }
        }

        if endpoint_arn:
            updates["runtime"]["diy_agent"]["endpoint_arn"] = endpoint_arn

        config_manager.update_dynamic_config(updates)
        print("   ✅ 新しい DIY runtime ARN で動的設定を更新しました")

    except Exception as config_error:
        print(f"   ⚠️  設定の更新中にエラー: {config_error}")

# Initialize configuration manager
config_manager = AgentCoreConfigManager()

# Get configuration values
base_config = config_manager.get_base_settings()
merged_config = config_manager.get_merged_config()  # For runtime values that may be dynamic
oauth_config = config_manager.get_oauth_settings()

# Extract configuration values
REGION = base_config['aws']['region']
ROLE_ARN = base_config['runtime']['role_arn']
AGENT_RUNTIME_NAME = base_config['runtime']['diy_agent']['name']
ECR_URI = merged_config['runtime']['diy_agent']['ecr_uri']  # ECR URI is dynamic

# Okta configuration
OKTA_DOMAIN = oauth_config['domain']
OKTA_AUDIENCE = oauth_config['jwt']['audience']

print("🚀 DIY エージェント用の AgentCore Runtime を作成中...")
print(f"   📝 名前: {AGENT_RUNTIME_NAME}")
print(f"   📦 コンテナ: {ECR_URI}")
print(f"   🔐 ロール: {ROLE_ARN}")

control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

print("🚀 DIY エージェント用の AgentCore Runtime を作成または更新中...")
print(f"   📝 名前: {AGENT_RUNTIME_NAME}")
print(f"   📦 コンテナ: {ECR_URI}")
print(f"   🔐 ロール: {ROLE_ARN}")

control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

# Check if runtime already exists
runtime_exists = False
existing_runtime_arn = None
existing_runtime_id = None

try:
    # Try to list runtimes and find our DIY runtime
    runtimes_response = control_client.list_agent_runtimes()
    for runtime in runtimes_response.get('agentRuntimes', []):
        if runtime.get('agentRuntimeName') == AGENT_RUNTIME_NAME:
            runtime_exists = True
            existing_runtime_arn = runtime.get('agentRuntimeArn')
            existing_runtime_id = existing_runtime_arn.split('/')[-1] if existing_runtime_arn else None
            print(f"✅ 既存のランタイムを発見: {existing_runtime_arn}")
            break
except Exception as e:
    print(f"⚠️  既存ランタイムの確認中にエラー: {e}")

try:
    if runtime_exists and existing_runtime_arn and existing_runtime_id:
        # Runtime exists - ECR image has been updated, runtime will use it automatically
        print(f"\n🔄 ランタイムが存在します。新しいコンテナイメージで更新中...")

        # Get existing endpoint ARN
        existing_endpoint_arn = None
        try:
            endpoints_response = control_client.list_agent_runtime_endpoints(
                agentRuntimeId=existing_runtime_id
            )
            for endpoint in endpoints_response.get('agentRuntimeEndpoints', []):
                if endpoint.get('name') == 'DEFAULT':
                    existing_endpoint_arn = endpoint.get('agentRuntimeEndpointArn')
                    print(f"✅ 既存のエンドポイントを発見: {existing_endpoint_arn}")
                    break
        except Exception as e:
            print(f"⚠️  エンドポイント ARN の取得中にエラー: {e}")

        # Since ECR image is updated and runtime uses latest image,
        # we just need to update the config with current ARNs
        print(f"✅ ECR イメージを更新しました - 次回呼び出し時に新しいコンテナを使用します")

        # Update config with existing ARNs
        update_config_with_arns(config_manager, existing_runtime_arn, existing_endpoint_arn or "")

        print(f"\n🎉 DIY エージェントの更新が完了しました！")
        print(f"🏷️  Runtime ARN: {existing_runtime_arn}")
        print(f"💾 ECR URI: {ECR_URI}")
        print(f"🔗 Endpoint ARN: {existing_endpoint_arn or '見つかりません'}")
        print(f"ℹ️  ランタイムは更新されたコンテナイメージを自動的に使用します")
            
    else:
        # Runtime doesn't exist - create new runtime
        print(f"\n🆕 新しいランタイムを作成中...")

        response = control_client.create_agent_runtime(
            agentRuntimeName=AGENT_RUNTIME_NAME,
            agentRuntimeArtifact={
                'containerConfiguration': {
                    'containerUri': ECR_URI
                }
            },
            networkConfiguration={"networkMode": "PUBLIC"},
            roleArn=ROLE_ARN,
            authorizerConfiguration={
                'customJWTAuthorizer': {
                    'discoveryUrl': oauth_config['jwt']['discovery_url'],
                    'allowedAudience': [OKTA_AUDIENCE]
                }
            }
        )

        runtime_arn = response['agentRuntimeArn']
        runtime_id = runtime_arn.split('/')[-1]

        print(f"✅ DIY AgentCore Runtime を作成しました！")
        print(f"🏷️  ARN: {runtime_arn}")
        print(f"🆔 Runtime ID: {runtime_id}")

        print(f"\n⏳ ランタイムが READY になるのを待機中...")
        max_wait = 600  # 10 minutes
        wait_time = 0

        while wait_time < max_wait:
            try:
                status_response = control_client.get_agent_runtime(agentRuntimeId=runtime_id)
                status = status_response.get('status')
                print(f"   📊 ステータス: {status} ({wait_time}秒)")

                if status == 'READY':
                    print(f"✅ DIY Runtime の準備が完了しました！")

                    # Create DEFAULT endpoint
                    print(f"\n🔗 DEFAULT エンドポイントを作成中...")
                    try:
                        endpoint_response = control_client.create_agent_runtime_endpoint(
                            agentRuntimeId=runtime_id,
                            name="DEFAULT"
                        )
                        print(f"✅ DEFAULT エンドポイントを作成しました！")
                        print(f"🏷️  Endpoint ARN: {endpoint_response['agentRuntimeEndpointArn']}")

                        # Update config with new ARNs
                        update_config_with_arns(config_manager, runtime_arn, endpoint_response['agentRuntimeEndpointArn'])

                    except Exception as ep_error:
                        if "already exists" in str(ep_error):
                            print(f"ℹ️  DEFAULT エンドポイントは既に存在します。既存のエンドポイント ARN を取得中...")
                            try:
                                # Get the existing endpoint ARN
                                endpoints_response = control_client.list_agent_runtime_endpoints(agentRuntimeId=runtime_id)
                                for endpoint in endpoints_response.get('agentRuntimeEndpoints', []):
                                    if endpoint.get('name') == 'DEFAULT':
                                        endpoint_arn = endpoint.get('agentRuntimeEndpointArn')
                                        print(f"🏷️  既存のエンドポイント ARN を発見: {endpoint_arn}")
                                        update_config_with_arns(config_manager, runtime_arn, endpoint_arn)
                                        break
                                else:
                                    # Fallback: construct the endpoint ARN
                                    endpoint_arn = f"{runtime_arn}/runtime-endpoint/DEFAULT"
                                    print(f"🔧 エンドポイント ARN を構築: {endpoint_arn}")
                                    update_config_with_arns(config_manager, runtime_arn, endpoint_arn)
                            except Exception as list_error:
                                print(f"⚠️  エンドポイント ARN の取得に失敗: {list_error}")
                                # Fallback: construct the endpoint ARN
                                endpoint_arn = f"{runtime_arn}/runtime-endpoint/DEFAULT"
                                print(f"🔧 構築したエンドポイント ARN を使用: {endpoint_arn}")
                                update_config_with_arns(config_manager, runtime_arn, endpoint_arn)
                        else:
                            print(f"❌ エンドポイントの作成中にエラー: {ep_error}")
                            # Still update with just runtime ARN
                            update_config_with_arns(config_manager, runtime_arn, "")

                    break
                elif status in ['FAILED', 'DELETING']:
                    print(f"❌ ランタイムの作成に失敗しました。ステータス: {status}")
                    break

                time.sleep(15)
                wait_time += 15

            except Exception as e:
                print(f"❌ ステータス確認中にエラー: {e}")
                break

        if wait_time >= max_wait:
            print(f"⚠️  ランタイムの作成に予想以上の時間がかかっています")

        print(f"\n🧪 テスト用:")
        print(f"   ARN: {runtime_arn}")
        print(f"   ID: {runtime_id}")

except Exception as e:
    print(f"❌ DIY ランタイムの作成/更新中にエラー: {e}")
    sys.exit(1)