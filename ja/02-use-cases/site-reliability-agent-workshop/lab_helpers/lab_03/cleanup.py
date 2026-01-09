"""
Lab 03: Remediation Agent Resource Cleanup

Removes all resources created during Lab 03:

AWS RESOURCES DELETED:
- AgentCore Gateway and all targets
- AgentCore Runtime (remediation-runtime)
- OAuth2 Credential Provider
- Secrets Manager secrets (m2m credentials)
- IAM roles (Runtime execution, Gateway service)
- CloudWatch logs

AWS RESOURCES PRESERVED:
- Parameter Store entries (put_parameter() now handles overwrites intelligently)
  • Re-run Section 7.3c to update with new runtime_arn/runtime_id after redeploying

LOCAL ARTIFACTS DELETED:
- agent-remediation.py
- Dockerfile
- .bedrock_agentcore.yaml
- .dockerignore
- Python cache (__pycache__/, *.pyc)

LOCAL ARTIFACTS PRESERVED:
- Lab-03-remediation-agent.ipynb (notebook file)
- lab_helpers/ module (preserved for reuse)
"""

import boto3
import json
import time
import shutil
import os
import logging
from lab_helpers.constants import PARAMETER_PATHS
from lab_helpers.lab_03.configure_logging import cleanup_runtime_logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def cleanup_lab_03(region_name: str = "us-west-2", verbose: bool = True) -> None:
    """
    Clean up all Lab 03 resources (Runtime and Gateway).

    This function removes AWS resources and local artifacts created during Lab 03:

    AWS RESOURCES DELETED:
    1. AgentCore Gateway (and all targets)
    2. AgentCore Runtime (remediation-runtime)
    3. OAuth2 Credential Provider
    4. Secrets Manager secrets (m2m credentials)
    5. IAM roles (Runtime execution role, Gateway service role)
    6. CloudWatch logs

    AWS RESOURCES PRESERVED:
    - Parameter Store entries (intelligently overwritten on re-deploy)

    LOCAL ARTIFACTS DELETED:
    7. Generated files (agent-remediation.py, Dockerfile, .bedrock_agentcore.yaml, .dockerignore)
    8. Python cache (__pycache__/, *.pyc)

    Args:
        region_name: AWS region (default: us-west-2)
        verbose: Print detailed status messages (default: True)

    Returns:
        None (prints status to stdout)

    Example:
        from lab_helpers.lab_03.cleanup import cleanup_lab_03
        cleanup_lab_03(region_name="us-west-2", verbose=True)
    """
    print("🧹 Lab 03 のリソースをクリーンアップ中...\n")
    print("=" * 70)

    if verbose:
        logging.basicConfig(level=logging.INFO)

    # Initialize clients
    agentcore_client = boto3.client('bedrock-agentcore-control', region_name=region_name)
    iam_client = boto3.client('iam')
    ssm_client = boto3.client('ssm', region_name=region_name)
    logs_client = boto3.client('logs', region_name=region_name)
    secrets_client = boto3.client('secretsmanager', region_name=region_name)

    # Debug: Find all parameters related to Lab 03
    if verbose:
        print("[DEBUG] Parameter Store 内の Lab 03 パラメータを検索中...")
        try:
            response = ssm_client.describe_parameters(
                Filters=[
                    {'Key': 'Name', 'Values': ['lab-03', 'lab03', 'remediation', 'aiml301']}
                ]
            )
            if response.get('Parameters'):
                print(f"  {len(response['Parameters'])} 件のパラメータが見つかりました:")
                for param in response['Parameters']:
                    print(f"    • {param['Name']}")
            else:
                print("  Lab 03 パラメータが見つかりません")
        except Exception as e:
            print(f"  ℹ パラメータ検索エラー: {e}")
        print()

    # 1. Delete OAuth2 Credential Provider
    print("[1/7] OAuth2 資格情報プロバイダーを削除中...")
    provider_deleted = False

    try:
        # Get provider ARN from Parameter Store
        try:
            response = ssm_client.get_parameter(Name=PARAMETER_PATHS["lab_03"]["oauth2_provider_arn"])
            provider_arn = response['Parameter']['Value']

            if provider_arn:
                # Extract provider name from ARN
                # ARN format: arn:aws:bedrock-agentcore:region:account:token-vault/default/oauth2credentialprovider/PROVIDER_NAME
                provider_name = provider_arn.split('/')[-1]

                if verbose:
                    print(f"  ℹ プロバイダー ARN を検出: {provider_arn}")
                    print(f"  ℹ 抽出したプロバイダー名: {provider_name}")

                try:
                    # Delete the provider using the correct 'name' parameter
                    agentcore_client.delete_oauth2_credential_provider(
                        name=provider_name
                    )
                    print(f"  ✓ OAuth2 資格情報プロバイダーを削除しました: {provider_name}")
                    provider_deleted = True
                except Exception as e:
                    error_str = str(e)
                    # Check if it's already deleted or doesn't exist
                    if "ResourceNotFoundException" in error_str or "does not exist" in error_str.lower():
                        print("  ✓ プロバイダーは既に削除済みまたは見つかりません (ok)")
                    else:
                        print(f"  ⚠ プロバイダー {provider_name} の削除に失敗: {error_str}")

        except ssm_client.exceptions.ParameterNotFound:
            if verbose:
                print("  ℹ プロバイダー ARN が Parameter Store に見つかりません (ok)")

    except Exception as e:
        print(f"  ⚠ OAuth2 クリーンアップエラー: {e}")

    # 1b. Delete Secrets Manager secrets created by OAuth2 credential provider
    print("[1b/8] Secrets Manager シークレットを削除中...")
    try:
        # Paginate through secrets to find those created by the OAuth2 credential provider
        # OAuth2 provider creates secrets with pattern: bedrock-agentcore-identity!default/oauth2/aiml301-m2m-credentials-*
        paginator = secrets_client.get_paginator('list_secrets')
        pages = paginator.paginate()

        oauth2_secrets = []
        for page in pages:
            for secret in page.get('SecretList', []):
                secret_name = secret['Name']
                # Match OAuth2 credential provider secrets
                if ('bedrock-agentcore-identity' in secret_name and 'm2m-credentials' in secret_name) or \
                   ('bedrock-agentcore-identity' in secret_name and 'aiml301' in secret_name) or \
                   'm2m-credentials' in secret_name:
                    oauth2_secrets.append(secret)

        if oauth2_secrets:
            for secret in oauth2_secrets:
                secret_name = secret['Name']
                try:
                    secrets_client.delete_secret(
                        SecretId=secret_name,
                        ForceDeleteWithoutRecovery=True
                    )
                    print("  ✓ シークレットを削除しました！")
                except Exception as e:
                    error_str = str(e)
                    if "ResourceNotFoundException" not in error_str:
                        # Check if it's owned by bedrock-agentcore-identity (expected)
                        if "bedrock-agentcore-identity" in error_str:
                            print("  ℹ シークレットはサービス所有です - プロバイダー削除時に自動削除されます")
                        else:
                            print(f"  ⚠ シークレットの削除に失敗: {error_str}")
        else:
            print("  ✓ OAuth2 m2m 資格情報シークレットは見つかりません")

    except Exception as e:
        print(f"  ⚠ Secrets Manager クリーンアップエラー: {e}")

    # 2. Delete Gateway (targets first, then gateway)
    print("[2/8] Gateway とターゲットを削除中...")
    try:
        # Find gateway by name
        gateways = agentcore_client.list_gateways()
        for gw in gateways.get('items', []):
            if 'remediation-gateway' in gw['name']:
                gateway_id = gw['gatewayId']

                # Step 1: Delete targets
                try:
                    targets = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                    target_count = len(targets.get('items', []))

                    if target_count > 0:
                        print(f"  {target_count} 件のターゲットを削除中...")
                        for target in targets.get('items', []):
                            target_id = target['targetId']
                            agentcore_client.delete_gateway_target(
                                gatewayIdentifier=gateway_id,
                                targetId=target_id
                            )
                            print(f"    • ターゲットを削除しました: {target_id}")

                        # Step 2: Verify targets are deleted with retry logic
                        print("  ターゲット削除を確認中...")
                        max_retries = 5
                        retry_count = 0
                        targets_deleted = False

                        while retry_count < max_retries and not targets_deleted:
                            time.sleep(3)  # Wait for AWS propagation
                            remaining_targets = agentcore_client.list_gateway_targets(
                                gatewayIdentifier=gateway_id
                            )
                            remaining_count = len(remaining_targets.get('items', []))

                            if remaining_count == 0:
                                print("  ✓ すべてのターゲットの削除を確認しました")
                                targets_deleted = True
                            else:
                                retry_count += 1
                                if retry_count < max_retries:
                                    print(
                                        f"  ⏳ リトライ {retry_count}/{max_retries-1}: "
                                        f"{remaining_count} 件のターゲットがまだ存在..."
                                    )
                                else:
                                    print(
                                        f"  ⚠ {max_retries} 回のリトライ後も "
                                        f"{remaining_count} 件のターゲットが関連付けされたまま"
                                    )
                    else:
                        print("  ✓ ターゲットは見つかりません")
                        targets_deleted = True

                except Exception as e:
                    print(f"  ⚠ ターゲット削除: {e}")
                    targets_deleted = False

                # Step 3: Delete gateway (only if targets are confirmed deleted)
                try:
                    if targets_deleted:
                        agentcore_client.delete_gateway(gatewayIdentifier=gateway_id)
                        print("  ✓ Gateway を削除しました")
                    else:
                        print("  ⚠ Gateway 削除をスキップ - ターゲットがまだ存在します")
                        print("     しばらく後にクリーンアップを再試行してください")
                except Exception as e:
                    print(f"  ⚠ Gateway 削除: {e}")

                break
        else:
            print("  ✓ Gateway は見つかりません (ok)")

    except Exception as e:
        print(f"  ⚠ Gateway 検索エラー: {e}")

    # 3. Delete Runtime and associated CloudWatch Logs Delivery
    print("[3/8] AgentCore Runtime を削除中...")
    try:
        runtime_deleted = False
        runtime_id_for_logging = None
        prefixes = ["aiml301_sre_agentcore", "aiml301-sre-agentcore", "aiml301", "lab-03"]

        # First, try to get runtime info from Parameter Store
        for prefix in prefixes:
            if runtime_deleted:
                break

            try:
                # Try multiple parameter names (most specific first)
                param_names = [
                    f"/{prefix}/lab-03/runtime-id",        # Direct ID (most likely)
                    f"/{prefix}/lab-03/runtime-config",    # JSON with ID
                    f"/{prefix}/runtime-id",               # Fallback variations
                    f"/{prefix}/runtime-config",
                ]

                for param_name in param_names:
                    try:
                        response = ssm_client.get_parameter(Name=param_name)
                        param_value = response['Parameter']['Value']

                        if verbose:
                            print(f"  パラメータを検出: {param_name}")

                        # Try to parse as JSON first
                        runtime_id = None
                        try:
                            runtime_config = json.loads(param_value)
                            runtime_id = runtime_config.get('runtime_id')
                        except (json.JSONDecodeError, TypeError):
                            # If not JSON, assume it's the runtime ID directly
                            if param_value and param_value.strip():
                                runtime_id = param_value.strip()

                        if runtime_id:
                            print("  Runtime ID を検出: ****")

                            # Clean up CloudWatch Logs Delivery BEFORE deleting runtime
                            try:
                                print("  Runtime の CloudWatch Logs Delivery をクリーンアップ中...")
                                cleanup_runtime_logging(runtime_id, region=region_name)
                            except Exception as e:
                                print(f"  ⚠ CloudWatch Logs Delivery クリーンアップ警告: {e}")

                            try:
                                agentcore_client.delete_agent_runtime(agentRuntimeId=runtime_id)
                                print("  ✓ Runtime 削除を開始しました: ****")

                                # Wait for Runtime to be fully deleted
                                print("  ⏳ Runtime 削除の完了を待機中...")
                                max_retries = 60
                                retry_count = 0

                                while retry_count < max_retries:
                                    time.sleep(5)
                                    try:
                                        status_check = agentcore_client.get_agent_runtime(agentRuntimeId=runtime_id)
                                        current_status = status_check.get('status', 'UNKNOWN')
                                        retry_count += 1
                                        print(f"     ステータス: {current_status} (チェック {retry_count}/{max_retries})")

                                        if current_status == 'DELETING':
                                            continue
                                    except agentcore_client.exceptions.ResourceNotFoundException:
                                        print("  ✓ Runtime を完全に削除しました: ****")
                                        runtime_deleted = True
                                        break
                                    except Exception as e:
                                        if "not found" in str(e).lower():
                                            print("  ✓ Runtime を完全に削除しました: ****")
                                            runtime_deleted = True
                                            break
                                        else:
                                            print(f"  ⚠ ステータス確認エラー: {e}")
                                            break

                                if not runtime_deleted:
                                    print(f"  ⚠ {max_retries} 回のリトライ後も Runtime がまだ削除中の可能性があります")

                                break

                            except Exception as e:
                                error_str = str(e)
                                if "ResourceNotFoundException" not in error_str and "does not exist" not in error_str.lower():
                                    print(f"  ⚠ Runtime 削除エラー: {error_str}")

                    except ssm_client.exceptions.ParameterNotFound:
                        if verbose:
                            print(f"  パラメータが見つかりません: {param_name}")

            except Exception as e:
                if verbose:
                    print(f"  ℹ Parameter Store 検索 ({prefix}): {e}")

        # Fallback: try to list and find runtimes
        if not runtime_deleted:
            if verbose:
                print("  Runtime が Parameter Store にありません、API を確認中...")

            try:
                runtimes = agentcore_client.list_agent_runtimes()
                all_items = runtimes.get('items', [])

                if verbose and all_items:
                    print(f"  API 経由で {len(all_items)} 件の Runtime を検出")

                for rt in all_items:
                    runtime_name = rt['agentRuntimeName'].lower()
                    if 'remediation' in runtime_name or 'aiml301' in runtime_name:
                        runtime_id = rt['agentRuntimeId']
                        print(f"  Runtime を検出: {rt['agentRuntimeName']}")

                        # Clean up CloudWatch Logs Delivery BEFORE deleting runtime
                        try:
                            print("  Runtime の CloudWatch Logs Delivery をクリーンアップ中...")
                            cleanup_runtime_logging(runtime_id, region=region_name)
                        except Exception as e:
                            print(f"  ⚠ CloudWatch Logs Delivery クリーンアップ警告: {e}")

                        try:
                            agentcore_client.delete_agent_runtime(agentRuntimeId=runtime_id)
                            print("  ✓ Runtime 削除を開始しました: ****")

                            # Wait for Runtime to be fully deleted
                            print("  ⏳ Runtime 削除の完了を待機中...")
                            max_retries = 30
                            retry_count = 0

                            while retry_count < max_retries:
                                time.sleep(5)
                                try:
                                    status_check = agentcore_client.get_agent_runtime(agentRuntimeId=runtime_id)
                                    current_status = status_check.get('status', 'UNKNOWN')
                                    retry_count += 1
                                    print(f"     ステータス: {current_status} (チェック {retry_count}/{max_retries})")

                                    if current_status == 'DELETING':
                                        continue
                                except agentcore_client.exceptions.ResourceNotFoundException:
                                    print("  ✓ Runtime を完全に削除しました: ****")
                                    runtime_deleted = True
                                    break
                                except Exception as e:
                                    if "not found" in str(e).lower():
                                        print("  ✓ Runtime を完全に削除しました: ****")
                                        runtime_deleted = True
                                        break
                                    else:
                                        print(f"  ⚠ ステータス確認エラー: {e}")
                                        break

                            if not runtime_deleted:
                                print(f"  ⚠ {max_retries} 回のリトライ後も Runtime がまだ削除中の可能性があります")

                            break
                        except Exception as e:
                            print(f"  ⚠ Runtime 削除に失敗: {e}")

            except Exception as e:
                if verbose:
                    print(f"  ℹ API 検索エラー: {e}")

        if not runtime_deleted:
            print("  ✓ Runtime は見つかりません (ok)")

    except Exception as e:
        print(f"  ⚠ Runtime クリーンアップエラー: {e}")

    # 3b. Delete Custom Code Interpreter
    print("[3b/8] Custom Code Interpreter を削除中...")
    try:
        # Try to get from SSM first
        interpreter_id = None
        try:
            response = ssm_client.get_parameter(Name=PARAMETER_PATHS['lab_03']['code_interpreter_id'])
            interpreter_id = response['Parameter']['Value']
            print(f"  SSM から Interpreter ID を検出: {interpreter_id}")
        except ssm_client.exceptions.ParameterNotFound:
            if verbose:
                print("  Interpreter ID が SSM にありません、API を確認中...")
        
        # If not in SSM, list and find
        if not interpreter_id:
            list_response = agentcore_client.list_code_interpreters()
            for item in list_response.get('codeInterpreterSummaries', []):
                if 'aiml301' in item.get('name', '').lower() and 'custom' in item.get('name', '').lower():
                    interpreter_id = item['codeInterpreterId']
                    print(f"  API 経由で Interpreter を検出: {interpreter_id}")
                    break
        
        if interpreter_id:
            try:
                agentcore_client.delete_code_interpreter(codeInterpreterId=interpreter_id)
                print(f"  ✓ Code Interpreter を削除しました: {interpreter_id}")
            except Exception as e:
                if "ResourceNotFoundException" in str(e) or "not found" in str(e).lower():
                    print("  ✓ Code Interpreter は既に削除済み (ok)")
                else:
                    print(f"  ⚠ Code Interpreter の削除に失敗: {e}")
        else:
            print("  ✓ Code Interpreter は見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ Code Interpreter クリーンアップエラー: {e}")

    # 4. Delete IAM roles
    print("[4/8] IAM ロールを削除中...")

    # Delete Custom Runtime execution role
    try:
        _delete_role(iam_client, "aiml301_sre_agentcore_CustomRuntimeRole")
        print("  ✓ Custom Runtime 実行ロールを削除しました")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Custom Runtime 実行ロールは見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ Custom Runtime ロール: {e}")

    # Delete Code Interpreter execution role
    try:
        _delete_role(iam_client, "aiml301_sre_agentcore-CodeInterpreterRole")
        print("  ✓ Code Interpreter 実行ロールを削除しました")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Code Interpreter 実行ロールは見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ Code Interpreter ロール: {e}")

    # Delete old Runtime execution role (if exists)
    try:
        _delete_role(iam_client, "aiml301-agentcore-remediation-role")
        print("  ✓ 旧 Runtime 実行ロールを削除しました")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ 旧 Runtime 実行ロールは見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ 旧 Runtime ロール: {e}")

    # Delete Gateway service role
    try:
        _delete_role(iam_client, "aiml301-remediation-gateway-role")
        print("  ✓ Gateway サービスロールを削除しました")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Gateway サービスロールは見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ Gateway ロール: {e}")

    # 5. Parameter Store entries (PRESERVED for reuse)
    print("[5/8] Parameter Store エントリ...")
    print("  ✓ 保持されました (put_parameter() が上書きをインテリジェントに処理)")
    print("  ℹ 最新の ARN/ID で値を更新するにはセクション 7.3c を再実行してください")

    # 6. Delete CloudWatch logs
    print("[6/8] CloudWatch ロググループを削除中...")
    try:
        # Find and delete log groups matching pattern
        logs_pattern = "/aws/bedrock-agentcore/runtime"
        log_groups = logs_client.describe_log_groups(logGroupNamePrefix=logs_pattern)

        for lg in log_groups.get('logGroups', []):
            if 'remediation' in lg['logGroupName'].lower():
                try:
                    logs_client.delete_log_group(logGroupName=lg['logGroupName'])
                    print(f"  ✓ ロググループを削除しました: {lg['logGroupName']}")
                except Exception as e:
                    print(f"  ⚠ {lg['logGroupName']} の削除に失敗: {e}")

    except logs_client.exceptions.ResourceNotFoundException:
        print("  ✓ ロググループは見つかりません (ok)")
    except Exception as e:
        print(f"  ⚠ ロググループクリーンアップ: {e}")

    # 7. Delete local generated files
    print("[7/8] ローカルアーティファクトを削除中...")
    try:
        # Get current working directory
        cwd = os.getcwd()

        # Files to delete
        files_to_delete = [
            os.path.join(cwd, 'agent-remediation.py'),
            os.path.join(cwd, 'Dockerfile'),
            os.path.join(cwd, '.bedrock_agentcore.yaml'),
            os.path.join(cwd, '.dockerignore'),
        ]

        deleted_count = 0
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"  ✓ 削除しました: {os.path.basename(file_path)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  ⚠ {os.path.basename(file_path)} の削除に失敗: {e}")

        # Clean up Python cache
        pycache_paths = [
            os.path.join(cwd, '__pycache__'),
            os.path.join(cwd, 'agent_remediation.cpython-*.pyc'),
        ]

        for pycache in pycache_paths:
            if '__pycache__' in pycache and os.path.isdir(pycache):
                try:
                    shutil.rmtree(pycache)
                    print("  ✓ 削除しました: __pycache__")
                except Exception as e:
                    print(f"  ⚠ __pycache__ の削除に失敗: {e}")

        if deleted_count == 0:
            print("  ✓ ローカルアーティファクトは見つかりません (ok)")

    except Exception as e:
        print(f"  ⚠ ローカルクリーンアップ: {e}")


    # 7. Delete local generated files
    print("[8/8] 修復プランを含む S3 バケットを削除中...")   
    s3_client = boto3.client('s3', region_name=region_name)
    s3_resource = boto3.resource('s3', region_name=region_name)
    
    parameter_name = '/aiml301_sre_workshop/remediation_s3_bucket'


    try:
        # Get bucket name from Parameter Store
        response = ssm_client.get_parameter(Name=parameter_name)
        bucket_name = response['Parameter']['Value']
        print(f"Parameter Store でバケット名を検出: {bucket_name}")
        
        # Empty and delete the bucket
        bucket = s3_resource.Bucket(bucket_name)
        print(f"バケットを空にしています: {bucket_name}")
        bucket.objects.all().delete()
        bucket.object_versions.all().delete()
        
        print(f"バケットを削除中: {bucket_name}")
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"バケットを正常に削除しました: {bucket_name}")
        
        # Delete the parameter
        ssm_client.delete_parameter(Name=parameter_name)
        print(f"パラメータを削除しました: {parameter_name}")
        
        print("クリーンアップ完了！")
        
    except ClientError as e:
        print(f"クリーンアップ中にエラー: {e}")
        raise

    print("\n" + "=" * 70)
    print("✅ Lab 03 のクリーンアップが完了しました")
    print("\nこれでセクション 1 から Lab 03 を再実行できます")


def _delete_role(iam_client, role_name: str) -> None:
    """
    Helper: Detach all policies and delete role.

    Args:
        iam_client: IAM boto3 client
        role_name: Name of IAM role to delete
    """
    # Detach managed policies
    policies = iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in policies.get('AttachedPolicies', []):
        iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])

    # Delete inline policies
    inline_policies = iam_client.list_role_policies(RoleName=role_name)
    for policy_name in inline_policies.get('PolicyNames', []):
        iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    # Delete role
    iam_client.delete_role(RoleName=role_name)


if __name__ == "__main__":
    from lab_helpers.config import AWS_REGION

    print("Lab 03: すべてのリソースをクリーンアップ")
    print("=" * 70)
    print("\n警告: 以下が削除されます:")
    print("\n削除される AWS リソース:")
    print("  • AgentCore Gateway とすべてのターゲット")
    print("  • AgentCore Runtime")
    print("  • OAuth2 資格情報プロバイダー")
    print("  • Secrets Manager シークレット (m2m 資格情報)")
    print("  • IAM ロール (Runtime, Gateway)")
    print("  • CloudWatch ログ")
    print("\n保持される AWS リソース:")
    print("  ✓ Parameter Store エントリ (再デプロイ時に更新されます)")
    print("\n削除されるローカルファイル:")
    print("  • agent-remediation.py")
    print("  • Dockerfile")
    print("  • .bedrock_agentcore.yaml")
    print("  • .dockerignore")
    print("  • Python キャッシュ (__pycache__/)")
    print("\nこの操作は元に戻せません。\n")

    confirm = input("よろしいですか？続行するには 'yes' と入力してください: ")
    if confirm.lower() == 'yes':
        cleanup_lab_03(region_name=AWS_REGION, verbose=True)
    else:
        print("クリーンアップがキャンセルされました")
