#!/usr/bin/env python3
"""
Market Trends Agent 完全クリーンアップスクリプト
deploy.py で作成されたすべてのリソースを削除します:
- AgentCore Runtime インスタンス
- AgentCore Memory インスタンス
- ECR リポジトリ
- IAM ロールとポリシー
- SSM パラメータ
- CodeBuild プロジェクト
- S3 アーティファクト
"""

import argparse
import logging
import boto3
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MarketTrendsAgentCleaner:
    """Market Trends Agent リソースの完全なクリーナー"""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.agent_name = "market_trends_agent"
        self.role_name = "MarketTrendsAgentRole"

        # Initialize AWS clients
        self.iam_client = boto3.client("iam", region_name=region)
        self.ecr_client = boto3.client("ecr", region_name=region)
        self.ssm_client = boto3.client("ssm", region_name=region)
        self.codebuild_client = boto3.client("codebuild", region_name=region)
        self.s3_client = boto3.client("s3", region_name=region)

        try:
            from bedrock_agentcore_starter_toolkit import Runtime
            from bedrock_agentcore.memory import MemoryClient

            self.runtime = Runtime()
            self.memory_client = MemoryClient(region_name=region)
            self.agentcore_available = True
        except ImportError:
            logger.warning(
                "bedrock-agentcore-starter-toolkit が利用できません - AgentCore クリーンアップをスキップします"
            )
            self.agentcore_available = False

    def cleanup_agentcore_runtime(self):
        """AgentCore Runtime インスタンスを削除する"""
        if not self.agentcore_available:
            logger.info("AgentCore Runtime クリーンアップをスキップ (ツールキットが利用できません)")
            return

        logger.info("AgentCore Runtime インスタンスをクリーンアップ中...")

        try:
            # Check if .agent_arn file exists
            arn_file = Path(".agent_arn")
            if arn_file.exists():
                with open(arn_file, "r") as f:
                    agent_arn = f.read().strip()

                logger.info(f"   エージェント ARN を発見: {agent_arn}")

                # Try to delete the runtime
                try:
                    # Extract agent ID from ARN
                    agent_id = agent_arn.split("/")[-1]
                    logger.info(f"   ランタイムを削除中: {agent_id}")

                    # Use the runtime toolkit to delete
                    self.runtime.delete()
                    logger.info("   AgentCore Runtime を正常に削除しました")

                    # Remove the ARN file
                    arn_file.unlink()
                    logger.info("   .agent_arn ファイルを削除しました")

                except Exception as e:
                    logger.warning(f"   ツールキット経由でランタイムを削除できませんでした: {e}")
                    logger.info("   ランタイムは AWS コンソールで手動クリーンアップが必要な場合があります")
            else:
                logger.info("   .agent_arn ファイルが見つかりません - クリーンアップするランタイムがありません")

        except Exception as e:
            logger.error(f"   AgentCore Runtime クリーンアップ中にエラーが発生しました: {e}")

    def cleanup_agentcore_memory(self):
        """AgentCore Memory インスタンスを削除する"""
        if not self.agentcore_available:
            logger.info("AgentCore Memory クリーンアップをスキップ (ツールキットが利用できません)")
            return

        logger.info("AgentCore Memory インスタンスをクリーンアップ中...")

        try:
            memories = self.memory_client.list_memories()
            market_memories = [
                m
                for m in memories
                if m.get("id", "").startswith("MarketTrendsAgentMultiStrategy-")
            ]

            if market_memories:
                logger.info(
                    f"   削除するメモリインスタンスが {len(market_memories)} 件見つかりました"
                )

                for memory in market_memories:
                    memory_id = memory.get("id")
                    status = memory.get("status")

                    try:
                        logger.info(
                            f"   メモリを削除中: {memory_id} (ステータス: {status})"
                        )
                        self.memory_client.delete_memory(memory_id)
                        logger.info(f"   メモリを削除しました: {memory_id}")
                    except Exception as e:
                        logger.warning(
                            f"   メモリ {memory_id} を削除できませんでした: {e}"
                        )

                # Remove local memory ID file
                memory_id_file = Path(".memory_id")
                if memory_id_file.exists():
                    memory_id_file.unlink()
                    logger.info("   .memory_id ファイルを削除しました")

            else:
                logger.info("   MarketTrendsAgent メモリインスタンスは見つかりませんでした")

        except Exception as e:
            logger.error(f"   AgentCore Memory クリーンアップ中にエラーが発生しました: {e}")

    def cleanup_ssm_parameters(self):
        """SSM パラメータを削除する"""
        logger.info("SSM パラメータをクリーンアップ中...")

        param_name = "/bedrock-agentcore/market-trends-agent/memory-id"

        try:
            self.ssm_client.delete_parameter(Name=param_name)
            logger.info(f"   SSM パラメータを削除しました: {param_name}")
        except self.ssm_client.exceptions.ParameterNotFound:
            logger.info(f"   SSM パラメータが見つかりません: {param_name}")
        except Exception as e:
            logger.warning(f"   SSM パラメータを削除できませんでした: {e}")

    def cleanup_ecr_repository(self):
        """ECR リポジトリを削除する"""
        logger.info("ECR リポジトリをクリーンアップ中...")

        repo_name = f"bedrock-agentcore-{self.agent_name}"

        try:
            # First, delete all images in the repository
            try:
                images = self.ecr_client.list_images(repositoryName=repo_name)
                if images["imageIds"]:
                    logger.info(
                        f"   リポジトリから {len(images['imageIds'])} 件のイメージを削除中"
                    )
                    self.ecr_client.batch_delete_image(
                        repositoryName=repo_name, imageIds=images["imageIds"]
                    )
                    logger.info("   リポジトリからすべてのイメージを削除しました")
            except Exception as e:
                logger.warning(f"   イメージを削除できませんでした: {e}")

            # Delete the repository
            self.ecr_client.delete_repository(repositoryName=repo_name, force=True)
            logger.info(f"   ECR リポジトリを削除しました: {repo_name}")

        except self.ecr_client.exceptions.RepositoryNotFoundException:
            logger.info(f"   ECR リポジトリが見つかりません: {repo_name}")
        except Exception as e:
            logger.warning(f"   ECR リポジトリを削除できませんでした: {e}")

    def cleanup_codebuild_project(self):
        """CodeBuild プロジェクトを削除する"""
        logger.info("CodeBuild プロジェクトをクリーンアップ中...")

        project_name = f"bedrock-agentcore-{self.agent_name}-builder"

        try:
            self.codebuild_client.delete_project(name=project_name)
            logger.info(f"   CodeBuild プロジェクトを削除しました: {project_name}")
        except self.codebuild_client.exceptions.InvalidInputException:
            logger.info(f"   CodeBuild プロジェクトが見つかりません: {project_name}")
        except Exception as e:
            logger.warning(f"   CodeBuild プロジェクトを削除できませんでした: {e}")

    def cleanup_s3_artifacts(self):
        """S3 アーティファクトを削除する（ベストエフォート）"""
        logger.info("S3 アーティファクトをクリーンアップ中...")

        try:
            # List buckets and look for CodeBuild artifacts
            buckets = self.s3_client.list_buckets()

            for bucket in buckets["Buckets"]:
                bucket_name = bucket["Name"]

                # Look for CodeBuild artifact buckets
                if "codebuild" in bucket_name.lower() and self.region in bucket_name:
                    try:
                        # List objects with our agent prefix
                        objects = self.s3_client.list_objects_v2(
                            Bucket=bucket_name, Prefix=self.agent_name
                        )

                        if "Contents" in objects:
                            logger.info(
                                f"   バケット {bucket_name} に {len(objects['Contents'])} 件のアーティファクトが見つかりました"
                            )

                            # Delete objects
                            delete_objects = [
                                {"Key": obj["Key"]} for obj in objects["Contents"]
                            ]
                            if delete_objects:
                                self.s3_client.delete_objects(
                                    Bucket=bucket_name,
                                    Delete={"Objects": delete_objects},
                                )
                                logger.info(
                                    f"   {bucket_name} から {len(delete_objects)} 件のアーティファクトを削除しました"
                                )

                    except Exception as e:
                        logger.debug(f"   バケット {bucket_name} をクリーンアップできませんでした: {e}")

        except Exception as e:
            logger.warning(f"   S3 アーティファクトをクリーンアップできませんでした: {e}")

    def cleanup_iam_resources(self):
        """IAM ロールとポリシーを削除する"""
        logger.info("IAM リソースをクリーンアップ中...")

        # Clean up main execution role
        try:
            # Delete inline policies
            try:
                policies = self.iam_client.list_role_policies(RoleName=self.role_name)
                for policy_name in policies["PolicyNames"]:
                    self.iam_client.delete_role_policy(
                        RoleName=self.role_name, PolicyName=policy_name
                    )
                    logger.info(f"   インラインポリシーを削除しました: {policy_name}")
            except Exception as e:
                logger.debug(f"   インラインポリシーを削除できませんでした: {e}")

            # Delete the role
            self.iam_client.delete_role(RoleName=self.role_name)
            logger.info(f"   IAM ロールを削除しました: {self.role_name}")

        except self.iam_client.exceptions.NoSuchEntityException:
            logger.info(f"   IAM ロールが見つかりません: {self.role_name}")
        except Exception as e:
            logger.warning(f"   IAM ロールを削除できませんでした: {e}")

        # Clean up CodeBuild execution role
        codebuild_role_pattern = f"AmazonBedrockAgentCoreSDKCodeBuild-{self.region}-"

        try:
            roles = self.iam_client.list_roles()
            for role in roles["Roles"]:
                role_name = role["RoleName"]
                if role_name.startswith(codebuild_role_pattern):
                    try:
                        # Delete inline policies
                        policies = self.iam_client.list_role_policies(
                            RoleName=role_name
                        )
                        for policy_name in policies["PolicyNames"]:
                            self.iam_client.delete_role_policy(
                                RoleName=role_name, PolicyName=policy_name
                            )

                        # Delete attached managed policies
                        attached_policies = self.iam_client.list_attached_role_policies(
                            RoleName=role_name
                        )
                        for policy in attached_policies["AttachedPolicies"]:
                            self.iam_client.detach_role_policy(
                                RoleName=role_name, PolicyArn=policy["PolicyArn"]
                            )

                        # Delete the role
                        self.iam_client.delete_role(RoleName=role_name)
                        logger.info(f"   CodeBuild IAM ロールを削除しました: {role_name}")

                    except Exception as e:
                        logger.warning(
                            f"   CodeBuild ロール {role_name} を削除できませんでした: {e}"
                        )

        except Exception as e:
            logger.warning(f"   CodeBuild IAM ロールをクリーンアップできませんでした: {e}")

    def cleanup_local_files(self):
        """ローカルのデプロイファイルを削除する"""
        logger.info("ローカルファイルをクリーンアップ中...")

        files_to_remove = [
            ".agent_arn",
            ".memory_id",
            "Dockerfile",
            ".dockerignore",
            ".bedrock_agentcore.yaml",
        ]

        for file_name in files_to_remove:
            file_path = Path(file_name)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"   削除しました: {file_name}")
            else:
                logger.debug(f"   ファイルが見つかりません: {file_name}")

    def cleanup_all(self, skip_iam: bool = False):
        """すべてのリソースをクリーンアップする"""
        logger.info("市場トレンドエージェントの完全クリーンアップを開始...")
        logger.info(f"   リージョン: {self.region}")
        logger.info(f"   エージェント: {self.agent_name}")

        # Clean up in reverse order of creation
        self.cleanup_agentcore_runtime()
        self.cleanup_agentcore_memory()
        self.cleanup_ssm_parameters()
        self.cleanup_codebuild_project()
        self.cleanup_s3_artifacts()
        self.cleanup_ecr_repository()

        if not skip_iam:
            self.cleanup_iam_resources()
        else:
            logger.info("IAM クリーンアップをスキップ (--skip-iam フラグ)")

        self.cleanup_local_files()

        logger.info("クリーンアップが完了しました！")
        logger.info(
            "削除できなかったリソースがある場合は、AWS コンソールで手動確認してください"
        )


def main():
    """メインクリーンアップ関数"""
    parser = argparse.ArgumentParser(
        description="Clean up all Market Trends Agent resources"
    )
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--skip-iam",
        action="store_true",
        help="Skip IAM role cleanup (useful if roles are shared)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("ドライランモード - リソースは削除されません")
        logger.info("   クリーンアップ対象:")
        logger.info("   - AgentCore Runtime インスタンス")
        logger.info("   - AgentCore Memory インスタンス")
        logger.info("   - ECR リポジトリ")
        logger.info("   - CodeBuild プロジェクト")
        logger.info("   - S3 アーティファクト")
        logger.info("   - SSM パラメータ")
        if not args.skip_iam:
            logger.info("   - IAM ロールとポリシー")
        logger.info("   - ローカルデプロイファイル")
        return

    # Confirm deletion
    print("⚠️  WARNING: This will delete ALL Market Trends Agent resources!")
    print(f"   Region: {args.region}")
    if args.skip_iam:
        print("   IAM resources will be PRESERVED")
    else:
        print("   IAM resources will be DELETED")

    confirm = input("\nAre you sure you want to continue? (type 'yes' to confirm): ")
    if confirm.lower() != "yes":
        print("❌ Cleanup cancelled")
        return

    # Create cleaner and run cleanup
    cleaner = MarketTrendsAgentCleaner(region=args.region)
    cleaner.cleanup_all(skip_iam=args.skip_iam)


if __name__ == "__main__":
    main()
