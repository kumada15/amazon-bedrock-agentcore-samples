#!/usr/bin/env python3
"""
Strands エージェントを Amazon Bedrock AgentCore Runtime にデプロイします。

このスクリプトは bedrock-agentcore-starter-toolkit を使用して、
自動 Docker コンテナ化と OTEL インストルメンテーションでエージェントをデプロイします。
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _validate_environment() -> None:
    """必要な環境と依存関係を検証します。"""
    try:
        import boto3  # noqa: F401
        from bedrock_agentcore_starter_toolkit import Runtime  # noqa: F401

        logger.info("必要なパッケージを検出: boto3, bedrock-agentcore-starter-toolkit")

    except ImportError as e:
        logger.error(f"必要なパッケージが不足: {e}")
        logger.error("インストールしてください: pip install -r requirements.txt")
        sys.exit(1)

    # Validate AWS credentials by making an API call
    # boto3 automatically figures out credentials from various sources:
    # - Environment variables
    # - IAM role (EC2/Cloud9/ECS)
    # - Credentials file
    # - Config file
    # We don't care which - just validate it works
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        logger.info(f"AWS アカウント ID: {identity['Account']}")
        logger.info(f"AWS アイデンティティ ARN: {identity['Arn']}")

    except Exception as e:
        logger.error(f"AWS 認証情報の検証に失敗: {e}")
        logger.error("")
        logger.error("AWS 認証情報が設定されていることを確認してください。")
        logger.error("テスト方法: aws sts get-caller-identity")
        sys.exit(1)


def _deploy_agent(
    agent_name: str,
    region: str,
    entrypoint: str,
    requirements_file: str,
    script_dir: Path,
    braintrust_api_key: str = None,
    braintrust_project_id: str = None,
    auto_update_on_conflict: bool = False,
) -> dict:
    """
    エージェントを AgentCore Runtime にデプロイします。

    Args:
        agent_name: デプロイするエージェントの名前
        region: デプロイ先の AWS リージョン
        entrypoint: エージェントエントリーポイントファイルのパス
        requirements_file: requirements.txt のパス
        script_dir: 出力を保存するスクリプトディレクトリ
        braintrust_api_key: オブザーバビリティ用のオプションの Braintrust API キー
        braintrust_project_id: オプションの Braintrust プロジェクト ID
        auto_update_on_conflict: 既存のエージェントが存在する場合に自動更新するかどうか

    Returns:
        デプロイ結果を含む辞書
    """
    from bedrock_agentcore_starter_toolkit import Runtime

    logger.info("AgentCore Runtime デプロイメントを初期化中...")

    agentcore_runtime = Runtime()

    # Determine observability configuration
    enable_braintrust = bool(braintrust_api_key and braintrust_project_id)

    # Configure the agent
    logger.info("エージェントデプロイメントを設定中...")
    logger.info(f"  エージェント名: {agent_name}")
    logger.info(f"  エントリーポイント: {entrypoint}")
    logger.info(f"  Requirements: {requirements_file}")
    logger.info(f"  リージョン: {region}")
    logger.info(
        f"  Braintrust オブザーバビリティ: {'有効' if enable_braintrust else '無効（CloudWatch のみ）'}"
    )

    configure_kwargs = {
        "entrypoint": entrypoint,
        "auto_create_execution_role": True,
        "auto_create_ecr": True,
        "requirements_file": requirements_file,
        "region": region,
        "agent_name": agent_name,
    }

    # Disable AgentCore's built-in OTEL if using Braintrust
    # When Braintrust is enabled, Strands telemetry handles OTEL instrumentation
    if enable_braintrust:
        configure_kwargs["disable_otel"] = True
        logger.info("  AgentCore OTEL を無効化（Braintrust を使用）")
    else:
        logger.info("  AgentCore OTEL インストルメンテーション: 有効（CloudWatch のみ）")

    configure_response = agentcore_runtime.configure(**configure_kwargs)

    logger.info("エージェント設定が完了")
    logger.info(f"設定レスポンス: {json.dumps(configure_response, indent=2, default=str)}")

    # Launch the agent
    logger.info("AgentCore Runtime にエージェントを起動中...")
    logger.info("以下を実行:")
    logger.info("  1. エージェントコードで Docker コンテナをビルド")
    logger.info("  2. コンテナを Amazon ECR にプッシュ")
    logger.info("  3. AgentCore Runtime にデプロイ")
    logger.info("  これには数分かかる場合があります...")

    try:
        launch_kwargs = {
            "auto_update_on_conflict": auto_update_on_conflict,
        }

        # Add Braintrust environment variables if enabled
        if enable_braintrust:
            logger.info("Braintrust OTEL エクスポートを設定中...")
            launch_kwargs["env_vars"] = {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "https://api.braintrust.dev/otel",
                "OTEL_EXPORTER_OTLP_HEADERS": f"authorization=Bearer {braintrust_api_key},x-bt-parent=project_id:{braintrust_project_id}",
                "BRAINTRUST_API_KEY": braintrust_api_key,
                "BRAINTRUST_PROJECT_ID": braintrust_project_id,
            }

        launch_result = agentcore_runtime.launch(**launch_kwargs)
    except Exception as e:
        error_msg = str(e)

        # Check for common IAM permission errors
        if "codebuild:CreateProject" in error_msg or "AccessDeniedException" in error_msg:
            logger.error("=" * 70)
            logger.error("IAM 権限エラー")
            logger.error("=" * 70)
            logger.error("デプロイメントには追加の IAM 権限が必要です。")
            logger.error("")
            logger.error("不足している権限: codebuild:CreateProject")
            logger.error("")
            logger.error("解決策:")
            logger.error("  1. docs/iam-policy-deployment.json からポリシーをアタッチ")
            logger.error("")
            logger.error("  AWS CLI を使用:")
            logger.error("     aws iam put-role-policy \\")
            logger.error("       --role-name YOUR_ROLE_NAME \\")
            logger.error("       --policy-name BedrockAgentCoreDeployment \\")
            logger.error("       --policy-document file://docs/iam-policy-deployment.json")
            logger.error("")
            logger.error("  または README で完全な IAM セットアップ手順を参照してください。")
            logger.error("=" * 70)

        # Re-raise the exception with more context
        raise RuntimeError(f"デプロイメント失敗: {error_msg}") from e

    logger.info("エージェントの起動に成功！")

    # Extract deployment information
    agent_id = launch_result.agent_id
    agent_arn = launch_result.agent_arn
    ecr_uri = launch_result.ecr_uri

    logger.info(f"エージェント ID: {agent_id}")
    logger.info(f"エージェント ARN: {agent_arn}")
    logger.info(f"ECR URI: {ecr_uri}")

    # Save deployment info
    deployment_info = {
        "agent_id": agent_id,
        "agent_arn": agent_arn,
        "ecr_uri": ecr_uri,
        "region": region,
        "agent_name": agent_name,
        "braintrust_enabled": enable_braintrust,
    }

    return deployment_info


def _wait_for_agent_ready(agent_id: str, region: str) -> None:
    """
    エージェントの準備完了を待機します。

    launch() メソッドは既にエージェントの準備完了を待機するため、
    これは現時点ではプレースホルダーです。

    Args:
        agent_id: チェックするエージェント ID
        region: AWS リージョン
    """
    logger.info("エージェントのデプロイメントが正常に完了")
    logger.info("launch() メソッドでエージェントの準備完了を確認済み")
    # No additional status check needed - launch() already handles this
    return


def _save_deployment_info(deployment_info: dict, script_dir: Path) -> None:
    """
    デプロイ情報を .deployment_metadata.json に保存します。

    Args:
        deployment_info: デプロイ情報辞書
        script_dir: ファイルを保存するディレクトリ
    """
    # Save deployment metadata as single source of truth
    metadata_file = script_dir / ".deployment_metadata.json"
    metadata_file.write_text(json.dumps(deployment_info, indent=2))
    logger.info(f"デプロイメントメタデータを保存: {metadata_file}")


def main():
    """メインデプロイ関数。"""
    parser = argparse.ArgumentParser(
        description="Deploy Strands agent to Amazon Bedrock AgentCore Runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Deploy with CloudWatch observability only (default)
    uv run python deploy_agent.py

    # Deploy with Braintrust observability
    uv run python deploy_agent.py \\
        --braintrust-api-key YOUR_KEY \\
        --braintrust-project-id YOUR_PROJECT_ID

    # Deploy to specific region
    uv run python deploy_agent.py --region us-west-2

    # Deploy with custom agent name
    uv run python deploy_agent.py --name MyCustomAgent

    # Update existing agent (auto-update on conflict)
    uv run python deploy_agent.py --auto-update-on-conflict

Environment variables:
    BRAINTRUST_API_KEY: Braintrust API key (alternative to --braintrust-api-key)
    BRAINTRUST_PROJECT_ID: Braintrust project ID (alternative to --braintrust-project-id)
""",
    )

    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region for deployment (default: us-east-1)",
    )

    parser.add_argument(
        "--name",
        default="weather_time_observability_agent",
        help="Agent name (default: weather_time_observability_agent)",
    )

    parser.add_argument(
        "--entrypoint",
        default="agent/weather_time_agent.py",
        help="Path to agent entrypoint (default: agent/weather_time_agent.py)",
    )

    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Path to requirements file (default: requirements.txt)",
    )

    parser.add_argument(
        "--braintrust-api-key",
        default=os.environ.get("BRAINTRUST_API_KEY"),
        help="Braintrust API key for observability (optional, can use BRAINTRUST_API_KEY env var)",
    )

    parser.add_argument(
        "--braintrust-project-id",
        default=os.environ.get("BRAINTRUST_PROJECT_ID"),
        help="Braintrust project ID (optional, can use BRAINTRUST_PROJECT_ID env var)",
    )

    parser.add_argument(
        "--auto-update-on-conflict",
        action="store_true",
        help="Automatically update existing agent if it already exists (default: false)",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent
    parent_dir = script_dir.parent

    # Validate Braintrust configuration
    # Only consider credentials valid if they are non-empty and not placeholder values
    braintrust_api_key_valid = (
        args.braintrust_api_key
        and args.braintrust_api_key.strip()
        and "your-" not in args.braintrust_api_key.lower()
    )
    braintrust_project_valid = (
        args.braintrust_project_id
        and args.braintrust_project_id.strip()
        and "your-" not in args.braintrust_project_id.lower()
    )

    enable_braintrust = braintrust_api_key_valid and braintrust_project_valid

    # If one credential is provided but not both, warn and disable Braintrust
    if (braintrust_api_key_valid or braintrust_project_valid) and not (
        braintrust_api_key_valid and braintrust_project_valid
    ):
        logger.warning(
            "Braintrust 認証情報が不完全 - Braintrust オブザーバビリティを無効化（CloudWatch のみ使用）"
        )
        enable_braintrust = False

    logger.info("=" * 60)
    logger.info("AGENTCORE エージェントデプロイメント")
    logger.info("=" * 60)
    logger.info(f"エージェント名: {args.name}")
    logger.info(f"リージョン: {args.region}")
    logger.info(f"エントリーポイント: {args.entrypoint}")
    logger.info(f"Requirements: {args.requirements}")
    logger.info(
        f"Braintrust オブザーバビリティ: {'有効' if enable_braintrust else '無効（CloudWatch のみ）'}"
    )
    logger.info("=" * 60)

    # Validate environment
    _validate_environment()

    # Change to parent directory for deployment
    os.chdir(parent_dir)
    logger.info(f"作業ディレクトリ: {parent_dir}")

    # Deploy agent
    deployment_info = _deploy_agent(
        agent_name=args.name,
        region=args.region,
        entrypoint=args.entrypoint,
        requirements_file=args.requirements,
        script_dir=script_dir,
        braintrust_api_key=args.braintrust_api_key,
        braintrust_project_id=args.braintrust_project_id,
        auto_update_on_conflict=args.auto_update_on_conflict,
    )

    # Wait for agent to be ready
    _wait_for_agent_ready(agent_id=deployment_info["agent_id"], region=args.region)

    # Save deployment information
    _save_deployment_info(deployment_info, script_dir)

    # Print success message
    logger.info("")
    logger.info("=" * 60)
    logger.info("デプロイメント完了")
    logger.info("=" * 60)
    logger.info(f"エージェント ID: {deployment_info['agent_id']}")
    logger.info(f"エージェント ARN: {deployment_info['agent_arn']}")
    logger.info(f"リージョン: {args.region}")
    logger.info("")
    logger.info("次のステップ:")
    logger.info("1. エージェントをテスト: ./scripts/tests/test_agent.py --test weather")
    logger.info("2. ログを確認: ./scripts/check_logs.sh --time 30m")
    logger.info("3. オブザーバビリティデモを実行: uv run python simple_observability.py --scenario all")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
