"""
Lab 02: リソースのクリーンアップ

Lab 02 で作成されたすべてのリソースを削除します:

AWS リソース:
- AgentCore Gateway とすべてのターゲット
- Lambda 関数 (aiml301-diagnostic-agent)
- ECR リポジトリ (aiml301-diagnostic-agent)
- S3 バケットとすべてのデプロイパッケージ
- IAM ロール（Lambda 実行、Gateway サービス）
- Parameter Store エントリ
- CloudWatch ログ

ローカル成果物（Docker アプローチ）:
- lambda_diagnostic_agent/（Docker ビルドディレクトリ）

ローカル成果物（ZIP アプローチ）:
- lambda_diagnostic_agent_zip/（lib/ 依存関係を含む ZIP ビルドディレクトリ）
- lambda_diagnostic_agent_zip.zip（ZIP パッケージファイル）
- その他の *_zip ディレクトリ（パターンマッチング）
- その他の *.zip ファイル（パターンマッチング）

一時ファイル:
- __pycache__/ ディレクトリ
- *.pyc コンパイル済み Python ファイル

保持されるリソース:
- Lab-02-diagnostics-agent.ipynb（ノートブックファイルは保持）
- lab_helpers/ モジュール（再利用のため保持）
"""

import boto3
import time
import shutil
import os
from lab_helpers.constants import PARAMETER_PATHS


def cleanup_lab_02(region_name="us-west-2", cleanup_s3=True):
    """
    Lab 02 のすべてのリソースをクリーンアップ（Docker および ZIP デプロイメント）

    この関数は Lab 02 で作成されたすべての AWS リソースとローカル成果物を削除します:

    AWS クリーンアップ:
    1. AgentCore Gateway（およびすべてのターゲット）
    2. Lambda 関数 (aiml301-diagnostic-agent)
    3. ECR リポジトリ（Docker アプローチを使用している場合）
    4. S3 バケットとすべてのデプロイパッケージ（cleanup_s3=True の場合）
    5. IAM ロール（Lambda 実行ロール、Gateway サービスロール）
    6. Parameter Store エントリ
    7. CloudWatch ログ

    ローカルクリーンアップ:
    - lambda_diagnostic_agent/（Docker ビルド成果物）
    - lambda_diagnostic_agent_zip/（依存関係を含む ZIP ビルドディレクトリ）
    - lambda_diagnostic_agent_zip.zip（ZIP パッケージ）
    - その他の *_zip ディレクトリおよび *.zip ファイル（パターンベース）
    - Python キャッシュ（__pycache__/、*.pyc）

    Args:
        region_name: AWS リージョン（デフォルト: us-west-2）
        cleanup_s3: S3 バケットとオブジェクトもクリーンアップ（デフォルト: True）
                   S3 デプロイパッケージを保持したい場合は False に設定

    Returns:
        None（ステータスを stdout に出力）

    Example:
        from lab_helpers.lab_02.cleanup import cleanup_lab_02
        cleanup_lab_02(region_name="us-west-2", cleanup_s3=True)
    """
    print("🧹 Lab 02 のリソースをクリーンアップ中...\n")
    print("=" * 70)

    # Initialize clients
    agentcore_client = boto3.client('bedrock-agentcore-control', region_name=region_name)
    lambda_client = boto3.client('lambda', region_name=region_name)
    ecr_client = boto3.client('ecr', region_name=region_name)
    s3_client = boto3.client('s3', region_name=region_name)
    iam_client = boto3.client('iam')
    ssm_client = boto3.client('ssm', region_name=region_name)
    logs_client = boto3.client('logs', region_name=region_name)

    # 1. Delete Gateway (targets first, then gateway)
    print("[1/7] Gateway とターゲットを削除中...")
    try:
        # Find gateway by name
        gateways = agentcore_client.list_gateways()
        for gw in gateways.get('items', []):
            if gw['name'] == 'aiml301-diagnostics-gateway':
                gateway_id = gw['gatewayId']
                targets_deleted = True  # Assume success unless proven otherwise

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
                        print("  ターゲットの削除を確認中...")
                        max_retries = 5
                        retry_count = 0
                        targets_deleted = False

                        while retry_count < max_retries and not targets_deleted:
                            time.sleep(3)  # Wait for AWS propagation
                            remaining_targets = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                            remaining_count = len(remaining_targets.get('items', []))

                            if remaining_count == 0:
                                print("  ✓ すべてのターゲットの削除を確認しました")
                                targets_deleted = True
                            else:
                                retry_count += 1
                                if retry_count < max_retries:
                                    print(f"  ⏳ リトライ {retry_count}/{max_retries-1}: {remaining_count} 件のターゲットがまだ存在します...")
                                else:
                                    print(f"  ⚠ {max_retries} 回のリトライ後も {remaining_count} 件のターゲットが残っています")
                    else:
                        print("  ✓ ターゲットが見つかりません")
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
                        print("  ⚠ ターゲットがまだ存在するため Gateway の削除をスキップします")
                        print("     少し待ってから再度クリーンアップを実行してください")
                except Exception as e:
                    print(f"  ⚠ Gateway 削除: {e}")

                break
        else:
            print("  ✓ Gateway が見つかりません (OK)")
    except Exception as e:
        print(f"  ⚠ Gateway 検索エラー: {e}")

    # 2. Delete Lambda function
    print("[2/7] Lambda 関数を削除中...")
    try:
        lambda_client.delete_function(FunctionName="aiml301-diagnostic-agent")
        print("  ✓ Lambda を削除しました")
    except lambda_client.exceptions.ResourceNotFoundException:
        print("  ✓ Lambda が見つかりません (OK)")
    except Exception as e:
        print(f"  ⚠ Lambda 削除: {e}")

    # 3. Delete ECR repository
    print("[3/7] ECR リポジトリを削除中...")
    try:
        ecr_client.delete_repository(repositoryName="aiml301-diagnostic-agent", force=True)
        print("  ✓ ECR リポジトリを削除しました")
    except ecr_client.exceptions.RepositoryNotFoundException:
        print("  ✓ ECR リポジトリが見つかりません (OK)")
    except Exception as e:
        print(f"  ⚠ ECR 削除: {e}")

    # 3.5. Delete S3 deployment packages (ZIP-based deployment)
    if cleanup_s3:
        print("[3.5/7] S3 デプロイパッケージを削除中...")
        try:
            bucket_name = "aiml301-lambda-packages"
            # List all objects in bucket
            try:
                response = s3_client.list_objects_v2(Bucket=bucket_name)
                if 'Contents' in response:
                    for obj in response['Contents']:
                        s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
                        print(f"    • 削除しました: {obj['Key']}")

                # Delete bucket itself
                s3_client.delete_bucket(Bucket=bucket_name)
                print(f"  ✓ S3 バケットを削除しました: {bucket_name}")
            except s3_client.exceptions.NoSuchBucket:
                print(f"  ✓ S3 バケットが見つかりません (OK): {bucket_name}")
        except Exception as e:
            print(f"  ⚠ S3 クリーンアップ: {e}")

    # 4. Delete IAM roles
    print("[4/7] IAM ロールを削除中...")

    # Delete Lambda execution role
    try:
        _delete_role(iam_client, "aiml301-diagnostic-lambda-role")
        print("  ✓ Lambda 実行ロールを削除しました")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Lambda 実行ロールが見つかりません (OK)")
    except Exception as e:
        print(f"  ⚠ Lambda ロール: {e}")

    # Delete Gateway service role
    try:
        _delete_role(iam_client, "aiml301-gateway-service-role")
        print("  ✓ Gateway サービスロールを削除しました")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Gateway サービスロールが見つかりません (OK)")
    except Exception as e:
        print(f"  ⚠ Gateway ロール: {e}")

    # 5. Delete Parameter Store entries (using constants for consistency)
    print("[5/7] Parameter Store エントリを削除中...")
    try:
        params_to_delete = [
            PARAMETER_PATHS["lab_02"]["ecr_repository_uri"],
            PARAMETER_PATHS["lab_02"]["ecr_repository_name"],
            PARAMETER_PATHS["lab_02"]["lambda_role_arn"],
            PARAMETER_PATHS["lab_02"]["lambda_function_arn"],
            PARAMETER_PATHS["lab_02"]["gateway_role_arn"],
            PARAMETER_PATHS["lab_02"]["lambda_function_name"],
            PARAMETER_PATHS["lab_02"]["gateway_id"],
            PARAMETER_PATHS["lab_02"]["gateway_url"],
        ]
        # Filter out any None values
        params_to_delete = [p for p in params_to_delete if p]
        if params_to_delete:
            ssm_client.delete_parameters(Names=params_to_delete)
            print(f"  ✓ Parameter Store エントリを削除しました ({len(params_to_delete)} 件のパラメータ)")
        else:
            print("  ✓ 削除するパラメータがありません")
    except Exception as e:
        print(f"  ⚠ パラメータ: {e}")

    # 6. Delete CloudWatch logs
    print("[6/7] CloudWatch ロググループを削除中...")
    try:
        logs_client.delete_log_group(logGroupName="/aws/lambda/aiml301-diagnostic-agent")
        print("  ✓ Lambda ロググループを削除しました")
    except logs_client.exceptions.ResourceNotFoundException:
        print("  ✓ Lambda ロググループが見つかりません (OK)")
    except Exception as e:
        print(f"  ⚠ ロググループ: {e}")

    # 7. Delete build artifacts (both Docker and ZIP approaches)
    print("[7/7] ビルド成果物と一時ファイルを削除中...")
    try:
        import glob

        artifacts_deleted = 0

        # Docker build directory
        docker_dir = "lambda_diagnostic_agent"
        if os.path.exists(docker_dir):
            shutil.rmtree(docker_dir)
            print(f"  ✓ Docker ビルドディレクトリを削除しました: {docker_dir}")
            artifacts_deleted += 1
        else:
            print(f"  ✓ Docker ビルドディレクトリが見つかりません (OK)")

        # ZIP build directory (specific)
        zip_build_dir = "lambda_diagnostic_agent_zip"
        if os.path.exists(zip_build_dir):
            shutil.rmtree(zip_build_dir)
            print(f"  ✓ ZIP ビルドディレクトリを削除しました: {zip_build_dir}")
            artifacts_deleted += 1
        else:
            print(f"  ✓ ZIP ビルドディレクトリが見つかりません (OK)")

        # ZIP file (specific)
        zip_file = "lambda_diagnostic_agent_zip.zip"
        if os.path.exists(zip_file):
            os.remove(zip_file)
            print(f"  ✓ ZIP ファイルを削除しました: {zip_file}")
            artifacts_deleted += 1
        else:
            print(f"  ✓ ZIP ファイルが見つかりません (OK)")

        # Clean up any other *_zip directories (catch-all for alternative patterns)
        zip_dirs = glob.glob("*_zip")
        for zip_dir in zip_dirs:
            if os.path.isdir(zip_dir) and zip_dir != zip_build_dir:
                try:
                    shutil.rmtree(zip_dir)
                    print(f"  ✓ 追加の ZIP ディレクトリを削除しました: {zip_dir}")
                    artifacts_deleted += 1
                except Exception as e:
                    print(f"  ⚠ {zip_dir} を削除できませんでした: {e}")

        # Clean up any other *.zip files (catch-all for alternative patterns)
        zip_files = glob.glob("*.zip")
        for zf in zip_files:
            if zf != zip_file:
                try:
                    os.remove(zf)
                    print(f"  ✓ 追加の ZIP ファイルを削除しました: {zf}")
                    artifacts_deleted += 1
                except Exception as e:
                    print(f"  ⚠ {zf} を削除できませんでした: {e}")

        # Clean up __pycache__ directories that might have been created
        pycache_dirs = glob.glob("**/__pycache__", recursive=True)
        for cache_dir in pycache_dirs:
            try:
                shutil.rmtree(cache_dir)
                print(f"  ✓ Python キャッシュを削除しました: {cache_dir}")
                artifacts_deleted += 1
            except Exception as e:
                pass  # Silent fail for cache cleanup

        # Clean up *.pyc files
        pyc_files = glob.glob("**/*.pyc", recursive=True)
        for pyc in pyc_files:
            try:
                os.remove(pyc)
                artifacts_deleted += 1
            except Exception as e:
                pass  # Silent fail for pyc cleanup

        if artifacts_deleted > 0:
            print(f"\n  クリーンアップした成果物の合計: {artifacts_deleted}")

    except Exception as e:
        print(f"  ⚠ ビルド成果物のクリーンアップ: {e}")

    print("\n" + "=" * 70)
    print("✅ Lab 02 のクリーンアップが完了しました")
    print("\nセクション 1 から Lab 02 全体を再実行できます")


def _delete_role(iam_client, role_name):
    """ヘルパー: すべてのポリシーをデタッチしてロールを削除"""
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
    cleanup_lab_02(region_name=AWS_REGION)
