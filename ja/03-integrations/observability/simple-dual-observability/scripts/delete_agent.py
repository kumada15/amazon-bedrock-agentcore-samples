#!/usr/bin/env python3
"""
bedrock-agentcore-starter-toolkit を使用して AgentCore Runtime エージェントを削除します。

このスクリプトは Amazon Bedrock AgentCore Runtime からデプロイされたエージェントを削除します。
"""

import argparse
import logging
import sys
from pathlib import Path

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _load_deployment_metadata(script_dir: Path) -> dict:
    """.deployment_metadata.json ファイルからデプロイメントメタデータを読み込みます。"""
    import json

    metadata_file = script_dir / ".deployment_metadata.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _delete_agent(agent_id: str, region: str) -> None:
    """
    AgentCore Runtime からエージェントを削除します。

    Args:
        agent_id: 削除するエージェント ID
        region: AWS リージョン
    """
    logger.info(f"エージェントを削除中: {agent_id}")
    logger.info(f"リージョン: {region}")

    try:
        import boto3

        # Delete the agent endpoint using boto3
        client = boto3.client("bedrock-agentcore", region_name=region)

        logger.info("エージェントランタイムエンドポイントを削除中...")
        client.delete_agent_runtime_endpoint(agentId=agent_id, endpointName="DEFAULT")

        logger.info("=" * 70)
        logger.info("エージェントの削除に成功")
        logger.info("=" * 70)
        logger.info(f"エージェント ID: {agent_id}")
        logger.info("エージェントは AgentCore Runtime から削除されました")

    except Exception as e:
        logger.error("=" * 70)
        logger.error("削除に失敗")
        logger.error("=" * 70)
        logger.error(f"エラー: {str(e)}")
        raise RuntimeError(f"エージェントの削除に失敗: {str(e)}") from e


def main() -> None:
    """エージェント削除のメインエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="Delete AgentCore Runtime agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Delete agent (reads from .deployment_metadata.json automatically)
    uv run python scripts/delete_agent.py

    # Delete with explicit region
    uv run python scripts/delete_agent.py --region us-west-2

    # Delete specific agent ID
    uv run python scripts/delete_agent.py --agent-id my-agent-id --region us-east-1

Environment variables:
    AWS_REGION: AWS region (if --region not specified)
""",
    )

    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (default: reads from .deployment_metadata.json or AWS_REGION env var)",
    )

    parser.add_argument(
        "--agent-id",
        default=None,
        help="Agent ID to delete (default: reads from .deployment_metadata.json)",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent

    # Load deployment metadata
    metadata = _load_deployment_metadata(script_dir)

    # Get agent ID
    agent_id = args.agent_id or metadata.get("agent_id")
    if not agent_id:
        logger.error("--agent-id でエージェント ID が指定されておらず、.deployment_metadata.json も見つかりません")
        logger.error("--agent-id を指定するか、.deployment_metadata.json が存在することを確認してください")
        sys.exit(1)

    # Get region
    region = args.region or metadata.get("region") or __import__("os").environ.get("AWS_REGION")
    if not region:
        logger.error("リージョンが指定されていません")
        logger.error(
            "--region を指定するか、.deployment_metadata.json に 'region' が含まれていることを確認するか、AWS_REGION 環境変数を設定してください"
        )
        sys.exit(1)

    # Delete the agent
    try:
        _delete_agent(
            agent_id=agent_id,
            region=region,
        )
    except Exception as e:
        logger.error(f"エージェントの削除に失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
