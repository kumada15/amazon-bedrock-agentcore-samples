"""
ユーザー好み戦略を用いたスライドデッキエージェント用 AgentCore Memory セットアップ
"""

import logging
import json
import boto3
from botocore.exceptions import ClientError

# Memory management modules (based on sample)
from bedrock_agentcore_starter_toolkit.operations.memory.manager import (
    Memory,
    MemoryManager,
)
from bedrock_agentcore_starter_toolkit.operations.memory.models.strategies import (
    CustomUserPreferenceStrategy,
    ExtractionConfig,
    ConsolidationConfig,
)
from bedrock_agentcore.memory.session import MemorySessionManager

from config import AWS_REGION, MEMORY_NAME, MEMORY_EXPIRY_DAYS

logger = logging.getLogger(__name__)


class SlideMemoryManager:
    """スライドデッキのユーザー好み用 AgentCore Memory を管理"""

    def __init__(self, region: str = AWS_REGION):
        self.region = region
        self.memory_manager = MemoryManager(region_name=region)
        self.memory_name = MEMORY_NAME
        self.memory_id = None
        self.memory_execution_role_arn = None

    def create_memory_execution_role(self) -> str:
        """AgentCore Memory カスタム戦略用の IAM ロールを作成する"""
        iam_client = boto3.client("iam", region_name=self.region)

        # Get current AWS account ID
        sts_client = boto3.client("sts", region_name=self.region)
        account_id = sts_client.get_caller_identity()["Account"]

        role_name = "SlideDeckAgentMemoryExecutionRole"
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

        # Trust policy for AgentCore Memory service
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["bedrock-agentcore.amazonaws.com"]},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:*"
                        },
                    },
                }
            ],
        }

        # Permissions policy for Bedrock model invocation
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [
                        "arn:aws:bedrock:*::foundation-model/*",
                        "arn:aws:bedrock:*:*:inference-profile/*",
                    ],
                    "Condition": {"StringEquals": {"aws:ResourceAccount": account_id}},
                }
            ],
        }

        try:
            # Check if role already exists
            try:
                iam_client.get_role(RoleName=role_name)
                logger.info(f"✅ IAM ロールは既に存在します: {role_arn}")
                return role_arn
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchEntity":
                    raise

            # Create the role
            logger.info(f"IAM ロールを作成中: {role_name}")
            iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Execution role for Slide Deck Agent Memory",
            )

            # Attach the permissions policy
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="SlideDeckMemoryBedrockAccess",
                PolicyDocument=json.dumps(permissions_policy),
            )

            logger.info(f"✅ IAM ロールを正常に作成しました: {role_arn}")

            # Wait for role propagation
            import time

            logger.info("⏳ ロールの伝播を待機中...")
            time.sleep(10)

            return role_arn

        except Exception as e:
            logger.error(f"❌ IAM ロールの作成に失敗しました: {e}")
            raise

    def create_user_preference_strategy(self) -> CustomUserPreferenceStrategy:
        """スライドデッキスタイリング用のユーザー好み戦略を作成する"""

        return CustomUserPreferenceStrategy(
            name="SlideStylePreferences",
            description="Captures user preferences for slide deck styling, themes, colors, and presentation types",
            extraction_config=ExtractionConfig(
                append_to_prompt="""
                Extract user preferences for slide presentations including:
                - Color schemes (blue, green, purple, red) and when they prefer each
                - Font families (modern, classic, technical, creative) and usage contexts
                - Presentation types (tech, business, academic, creative) and associated styles
                - Content types (legal, compliance, technical, business, creative) and their preferred color schemes
                - Visual preferences (gradients, shadows, spacing: compact/comfortable/spacious)
                - Theme styles (professional, elegant, minimal) and preferred combinations
                - Any patterns in their choices for different audiences or topics

                Focus on explicit preferences and recurring patterns in their choices.
                """,
                model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
            consolidation_config=ConsolidationConfig(
                append_to_prompt="""
                Consolidate user slide deck style preferences into a comprehensive profile:
                - Default color scheme and when they deviate from it
                - Preferred font combinations for different presentation contexts
                - Style patterns for tech vs business vs academic presentations
                - Visual design preferences (modern vs classic, minimal vs detailed)
                - Consistent choices that indicate strong preferences

                Create a clear preference profile for future slide generation.
                """,
                model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
            namespaces=["slidedecks/user/{actorId}/style_preferences"],
        )

    def create_memory(self) -> Memory:
        """ユーザー好み戦略を用いたスライドデッキ Memory リソースを作成する"""

        # Create IAM role
        self.memory_execution_role_arn = self.create_memory_execution_role()

        # Create single user preference strategy
        strategy = self.create_user_preference_strategy()

        logger.info(f"✅ Memory 戦略を設定しました: {strategy.name}")
        logger.info(f"   説明: {strategy.description}")
        logger.info(f"   名前空間: {strategy.namespaces}")

        try:
            memory = self.memory_manager.get_or_create_memory(
                name=self.memory_name,
                strategies=[strategy],  # Single strategy focused on user preferences
                description="Memory for slide deck agent user style preferences",
                event_expiry_days=MEMORY_EXPIRY_DAYS,
                memory_execution_role_arn=self.memory_execution_role_arn,
            )

            self.memory_id = memory.id
            logger.info("✅ Memory を正常に作成しました:")
            logger.info(f"   Memory ID: {memory.id}")
            logger.info(f"   Memory 名: {memory.name}")

            return memory

        except Exception as e:
            logger.error(f"❌ Memory の作成に失敗しました: {e}")
            raise

    def get_session_manager(self, memory_id: str) -> MemorySessionManager:
        """作成された Memory 用の MemorySessionManager を取得する"""
        return MemorySessionManager(memory_id=memory_id, region_name=self.region)

    def cleanup_memory(self, memory_id: str):
        """Memory リソースをクリーンアップする"""
        try:
            self.memory_manager.delete_memory(memory_id)
            logger.info(f"✅ Memory を正常に削除しました: {memory_id}")
        except Exception as e:
            logger.error(f"❌ Memory の削除に失敗しました: {e}")

    def delete_existing_memory(self) -> bool:
        """名前で既存の Memory を検索して削除する"""
        try:
            logger.info(f"🔍 既存の Memory を検索中: {self.memory_name}")

            # List all memories to find the one with matching name
            memories = self.memory_manager.list_memories()

            for memory in memories:
                if memory.name == self.memory_name:
                    logger.info(f"📦 既存の Memory を発見しました: {memory.id}")
                    logger.info("⚠️  新しい設定を適用するため Memory を削除中...")
                    self.cleanup_memory(memory.id)
                    logger.info("✅ Memory を正常に削除しました")
                    return True

            logger.info(f"ℹ️  この名前の既存 Memory は見つかりませんでした: {self.memory_name}")
            return False

        except Exception as e:
            logger.error(f"❌ 既存 Memory の削除に失敗しました: {e}")
            return False


# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def setup_slide_deck_memory() -> tuple:
    """スライドデッキ Memory をセットアップし、Memory オブジェクトと MemorySessionManager を返す"""

    logger.info("🚀 スライドデッキエージェント Memory をセットアップ中（ユーザー好みのみ）...")

    # Create memory manager
    memory_mgr = SlideMemoryManager()

    # Create memory resource
    memory = memory_mgr.create_memory()

    # Create session manager
    session_manager = memory_mgr.get_session_manager(memory.id)

    logger.info("🎉 スライドデッキエージェント Memory の準備完了！")

    return memory, session_manager, memory_mgr


if __name__ == "__main__":
    # Demo the memory setup
    try:
        memory, session_mgr, mgr = setup_slide_deck_memory()
        print(f"Memory ID: {memory.id}")
        print(f"Memory 名: {memory.name}")
        print("✅ Memory セットアップ完了 - ユーザー好み学習の準備ができました！")
    except Exception as e:
        print(f"❌ Memory セットアップでエラーが発生しました: {e}")
