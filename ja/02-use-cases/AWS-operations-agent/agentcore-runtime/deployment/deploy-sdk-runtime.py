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
    print(f"\n📝 新しい SDK runtime ARN で動的設定を更新中...")
    try:
        # Update dynamic configuration
        updates = {
            "runtime": {
                "sdk_agent": {
                    "arn": runtime_arn
                }
            }
        }

        if endpoint_arn:
            updates["runtime"]["sdk_agent"]["endpoint_arn"] = endpoint_arn

        config_manager.update_dynamic_config(updates)
        print("   ✅ 新しい SDK runtime ARN で動的設定を更新しました")

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
AGENT_RUNTIME_NAME = base_config['runtime']['sdk_agent']['name']
ECR_URI = merged_config['runtime']['sdk_agent']['ecr_uri']  # ECR URI is dynamic

# Okta configuration
OKTA_DOMAIN = oauth_config['domain']
OKTA_AUDIENCE = oauth_config['jwt']['audience']

print("🚀 SDK エージェント用の AgentCore Runtime を作成中...")
print(f"   📝 名前: {AGENT_RUNTIME_NAME}")
print(f"   📦 コンテナ: {ECR_URI}")
print(f"   🔐 ロール: {ROLE_ARN}")

control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

try:
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

    print(f"✅ SDK AgentCore Runtime を作成しました！")
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
                print(f"✅ SDK Runtime の準備が完了しました！")

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
                        print(f"ℹ️  DEFAULT エンドポイントは既に存在します")
                        # Fetch existing endpoint ARN
                        try:
                            endpoints_response = control_client.list_agent_runtime_endpoints(agentRuntimeId=runtime_id)
                            default_endpoint = next((ep for ep in endpoints_response['runtimeEndpoints'] if ep['name'] == 'DEFAULT'), None)
                            if default_endpoint:
                                existing_endpoint_arn = default_endpoint['agentRuntimeEndpointArn']
                                print(f"🏷️  既存のエンドポイント ARN を発見: {existing_endpoint_arn}")
                                update_config_with_arns(config_manager, runtime_arn, existing_endpoint_arn)
                            else:
                                print(f"⚠️  DEFAULT エンドポイントが見つかりません")
                                update_config_with_arns(config_manager, runtime_arn, "")
                        except Exception as fetch_error:
                            print(f"⚠️  既存エンドポイントの取得中にエラー: {fetch_error}")
                            update_config_with_arns(config_manager, runtime_arn, "")
                    else:
                        print(f"❌ エンドポイントの作成中にエラー: {ep_error}")

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
    print(f"❌ SDK ランタイムの作成中にエラー: {e}")