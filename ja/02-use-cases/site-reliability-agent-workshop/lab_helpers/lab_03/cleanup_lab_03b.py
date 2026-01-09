"""
Lab 03B: Fine-Grained Access Control Resource Cleanup

Removes Lab 3B-specific resources while preserving Lab 3A base resources.

AWS RESOURCES DELETED:
- AgentCore Gateway with JWT auth (interceptor-gateway-jwt-*)
- Gateway targets
- Lambda interceptor function
- Lambda execution role

AWS RESOURCES PRESERVED:
- AgentCore Runtime (reused from Lab 3A)
- Cognito User Pool and users
- OAuth2 Credential Provider
- Parameter Store entries
"""

import boto3
import time
from typing import Optional
from lab_helpers.constants import PARAMETER_PATHS

def cleanup_lab_03b(region_name: str = "us-east-1", verbose: bool = True) -> None:
    """
    Clean up Lab 3B resources (JWT Gateway and Lambda Interceptor).
    
    Preserves Lab 3A resources (Runtime, Cognito, OAuth2 provider).
    
    Args:
        region_name: AWS region
        verbose: Print detailed status
    """
    print("🧹 Lab 3B のリソースをクリーンアップ中...\n")
    print("=" * 70)
    
    agentcore_client = boto3.client('bedrock-agentcore-control', region_name=region_name)
    lambda_client = boto3.client('lambda', region_name=region_name)
    iam_client = boto3.client('iam')
    ssm_client = boto3.client('ssm', region_name=region_name)
    
    # 1. Delete Gateway with JWT auth
    print("[1/3] Lab 3B の Gateway を削除中...")
    try:
        gateways = agentcore_client.list_gateways()
        for gw in gateways.get('items', []):
            if 'interceptor-gateway-jwt' in gw.get('name', ''):
                gateway_id = gw['gatewayId']
                gateway_name = gw.get('name', 'N/A')
                
                print(f"  Gateway を検出: {gateway_name}")
                
                # Delete targets first
                targets = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                for target in targets.get('items', []):
                    target_id = target['targetId']
                    agentcore_client.delete_gateway_target(
                        gatewayIdentifier=gateway_id,
                        targetId=target_id
                    )
                    print(f"    ✓ ターゲットを削除しました: {target_id}")
                
                # Wait for targets to be deleted
                if targets.get('items'):
                    print("  ⏳ ターゲットの削除を待機中...")
                    for _ in range(30):
                        time.sleep(2)
                        check = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                        if len(check.get('items', [])) == 0:
                            break
                
                # Delete gateway
                agentcore_client.delete_gateway(gatewayIdentifier=gateway_id)
                print(f"  ✓ Gateway を削除しました: {gateway_name}")
                break
        else:
            print("  ✓ Gateway は見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ Gateway クリーンアップエラー: {e}")
    
    # 2. Delete Lambda interceptor
    print("[2/3] Lambda インターセプターを削除中...")
    try:
        function_name = "aiml301_sre_agentcore-interceptor-request"
        try:
            lambda_client.delete_function(FunctionName=function_name)
            print(f"  ✓ Lambda を削除しました: {function_name}")
        except lambda_client.exceptions.ResourceNotFoundException:
            print(f"  ✓ Lambda は見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ Lambda クリーンアップエラー: {e}")
    
    # 3. Delete Lambda execution role
    print("[3/3] Lambda 実行ロールを削除中...")
    try:
        role_name = "aiml301_sre_agentcore-interceptor-role"
        try:
            # Detach policies
            policies = iam_client.list_attached_role_policies(RoleName=role_name)
            for policy in policies.get('AttachedPolicies', []):
                iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
            
            # Delete inline policies
            inline = iam_client.list_role_policies(RoleName=role_name)
            for policy_name in inline.get('PolicyNames', []):
                iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            
            # Delete role
            iam_client.delete_role(RoleName=role_name)
            print(f"  ✓ IAM ロールを削除しました: {role_name}")
        except iam_client.exceptions.NoSuchEntityException:
            print(f"  ✓ IAM ロールは見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ IAM ロールクリーンアップエラー: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Lab 3B のクリーンアップが完了しました")
    print("\n保持されたリソース:")
    print("  ✓ AgentCore Runtime (Lab 3A より)")
    print("  ✓ Cognito User Pool とユーザー")
    print("  ✓ OAuth2 資格情報プロバイダー")
    print("  ✓ Parameter Store エントリ")
