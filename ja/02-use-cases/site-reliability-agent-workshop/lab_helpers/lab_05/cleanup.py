"""
Lab 05: Supervisor エージェントリソースのクリーンアップ

Lab 05 デプロイ中に作成されたすべてのリソースをクリーンアップします:
- Supervisor エージェント Runtime
- IAM ロール
- ECR リポジトリ（オプション）
- agent-supervisor.py ファイル
- Dockerfile
- .bedrock_agentcore.yaml
"""

import os
import boto3
import logging
from typing import Dict, List
from botocore.exceptions import ClientError

from lab_helpers.config import AWS_REGION
from lab_helpers.constants import PARAMETER_PATHS
from .iam_setup import delete_supervisor_runtime_iam_role

logger = logging.getLogger(__name__)


def delete_supervisor_runtime(
    runtime_name: str,
    region: str = AWS_REGION,
    verbose: bool = True
) -> bool:
    """
    Supervisor エージェント Runtime を削除します。

    Args:
        runtime_name: 削除する Supervisor Runtime の名前
        region: AWS リージョン
        verbose: ステータスメッセージを出力する

    Returns:
        成功時は True、それ以外は False
    """
    try:
        agentcore = boto3.client('bedrock-agentcore-control', region_name=region)

        if verbose:
            logger.info(f"🗑️  Supervisor ランタイムを削除中: {runtime_name}")

        # List runtimes to find the one to delete
        response = agentcore.list_agent_runtimes()
        runtime_id = None

        for runtime in response.get('agentRuntimes', []):
            if runtime['agentRuntimeName'] == runtime_name:
                runtime_id = runtime['agentRuntimeId']
                break

        if not runtime_id:
            if verbose:
                logger.warning(f"⚠️  ランタイムが見つかりません: {runtime_name}")
            return True

        # Delete the runtime
        agentcore.delete_agent_runtime(agentRuntimeId=runtime_id)

        if verbose:
            logger.info(f"✅ Supervisor ランタイムを削除しました: {runtime_id}")

        return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            if verbose:
                logger.warning(f"⚠️  ランタイムが見つかりません: {runtime_name}")
            return True
        logger.error(f"❌ ランタイムの削除中にエラーが発生しました: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ランタイムの削除中に予期しないエラーが発生しました: {e}")
        return False


def delete_supervisor_gateway(
    gateway_name: str,
    region: str = AWS_REGION,
    verbose: bool = True
) -> bool:
    """
    Supervisor Gateway を削除します。

    Args:
        gateway_name: 削除する Supervisor Gateway の名前
        region: AWS リージョン
        verbose: ステータスメッセージを出力する

    Returns:
        成功時は True、それ以外は False
    """
    try:
        agentcore = boto3.client('bedrock-agentcore-control', region_name=region)

        if verbose:
            logger.info(f"🗑️  Supervisor ゲートウェイを削除中: {gateway_name}")

        # List gateways to find the one to delete
        response = agentcore.list_gateways()
        gateway_id = None

        for gateway in response.get('gatewaySummaries', []):
            if gateway_name in gateway['gatewayArn']:
                gateway_id = gateway['gatewayId']
                break

        if not gateway_id:
            if verbose:
                logger.warning(f"⚠️  ゲートウェイが見つかりません: {gateway_name}")
            return True

        # Delete the gateway
        agentcore.delete_gateway(gatewayIdentifier=gateway_id)

        if verbose:
            logger.info(f"✅ Supervisor ゲートウェイを削除しました: {gateway_id}")

        return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            if verbose:
                logger.warning(f"⚠️  ゲートウェイが見つかりません: {gateway_name}")
            return True
        logger.error(f"❌ ゲートウェイの削除中にエラーが発生しました: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ゲートウェイの削除中に予期しないエラーが発生しました: {e}")
        return False


def delete_ecr_repository(
    repository_name: str,
    region: str = AWS_REGION,
    verbose: bool = True,
    force: bool = True
) -> bool:
    """
    Supervisor Runtime 用の ECR リポジトリを削除します。

    Args:
        repository_name: ECR リポジトリの名前
        region: AWS リージョン
        verbose: ステータスメッセージを出力する
        force: リポジトリにイメージがある場合でも強制削除

    Returns:
        成功時は True、それ以外は False
    """
    try:
        ecr = boto3.client('ecr', region_name=region)

        if verbose:
            logger.info(f"🗑️  ECR リポジトリを削除中: {repository_name}")

        ecr.delete_repository(
            repositoryName=repository_name,
            force=force
        )

        if verbose:
            logger.info(f"✅ ECR リポジトリを削除しました: {repository_name}")

        return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryNotFoundException':
            if verbose:
                logger.warning(f"⚠️  リポジトリが見つかりません: {repository_name}")
            return True
        logger.error(f"❌ ECR リポジトリの削除中にエラーが発生しました: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ECR リポジトリの削除中に予期しないエラーが発生しました: {e}")
        return False


def delete_supervisor_files(
    file_names: List[str] = None,
    verbose: bool = True
) -> Dict[str, bool]:
    """
    プロジェクトルートから Supervisor 関連ファイルを削除します。

    Args:
        file_names: 削除するファイル名のリスト（未指定の場合は標準ファイルにデフォルト）
        verbose: ステータスメッセージを出力する

    Returns:
        各ファイルの削除ステータスを含む Dict
    """
    if file_names is None:
        file_names = ['agent-supervisor.py', 'Dockerfile', '.bedrock_agentcore.yaml']

    # Get the project root directory (3 levels up from lab_helpers/lab_05/cleanup.py)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    deletion_status = {}

    for file_name in file_names:
        try:
            file_path = os.path.join(project_root, file_name)

            if verbose:
                logger.info(f"🗑️  {file_name} を削除中: {file_path}")

            if os.path.exists(file_path):
                os.remove(file_path)
                if verbose:
                    logger.info(f"✅ {file_name} を削除しました")
                deletion_status[file_name] = True
            else:
                if verbose:
                    logger.warning(f"⚠️  ファイルが見つかりません: {file_path}")
                deletion_status[file_name] = True

        except Exception as e:
            logger.error(f"❌ {file_name} の削除中にエラーが発生しました: {e}")
            deletion_status[file_name] = False

    return deletion_status


def cleanup_lab_05(
    region_name: str = AWS_REGION,
    verbose: bool = True,
    delete_ecr: bool = True
) -> Dict[str, bool]:
    """
    すべての Lab 05 リソースをクリーンアップします。

    Args:
        region_name: AWS リージョン
        verbose: ステータスメッセージを出力する
        delete_ecr: ECR リポジトリを削除するかどうか（デフォルト: True）

    Returns:
        各リソースのクリーンアップステータスを含む Dict
    """
    logger.info("\n🧹 Lab-05 クリーンアップを開始中...")
    if verbose:
        logger.info("=" * 70)

    cleanup_status = {}

    # 1. Delete supervisor runtime
    if verbose:
        logger.info("\n1️⃣  Supervisor ランタイムを削除中...")
    cleanup_status['runtime'] = delete_supervisor_runtime(
        runtime_name='aiml301_sre_agentcore_supervisor_runtime',
        region=region_name,
        verbose=verbose
    )

    # 2. Delete IAM role
    if verbose:
        logger.info("\n2️⃣  IAM ロールを削除中...")
    cleanup_status['iam_role'] = delete_supervisor_runtime_iam_role(
        role_name='aiml301_sre_agentcore-lab05-supervisor-runtime-role',
        region=region_name
    )

    # 3. Delete ECR repository
    if verbose:
        logger.info("\n3️⃣  ECR リポジトリを削除中...")
    cleanup_status['ecr'] = delete_ecr_repository(
        repository_name='bedrock-agentcore-aiml301_sre_agentcore_supervisor_runtime',
        region=region_name,
        verbose=verbose,
        force=True
    )

    # 4. Delete supervisor-related files
    if verbose:
        logger.info("\n4️⃣  Supervisor ファイルを削除中...")
    files_cleanup = delete_supervisor_files(verbose=verbose)
    cleanup_status.update(files_cleanup)

    # Summary
    if verbose:
        logger.info("\n" + "=" * 70)
        logger.info("✅ Lab-05 クリーンアップサマリー:")
        for resource, status in cleanup_status.items():
            status_icon = "✓" if status else "✗"
            logger.info(f"   {status_icon} {resource.upper()}: {'成功' if status else '失敗'}")

        logger.info("\n💡 すべての Lab-05 Supervisor リソースがクリーンアップされました！")
        logger.info("=" * 70)

    return cleanup_status
