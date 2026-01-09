#!/usr/bin/env python3
"""
Market Trends Agent 完全デプロイスクリプト
IAM ロール作成、権限設定、コンテナデプロイ、およびエージェントセットアップを処理する
"""

import argparse
import json
import logging
import boto3
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MarketTrendsAgentDeployer:
    """Market Trends Agent の完全なデプロイヤー"""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.iam_client = boto3.client("iam", region_name=region)
        self.ssm_client = boto3.client("ssm", region_name=region)

    def create_execution_role(self, role_name: str) -> str:
        """必要なすべての権限を持つ IAM 実行ロールを作成する"""

        # Trust policy for Bedrock AgentCore
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        # Get account ID and region for specific resource ARNs
        account_id = boto3.client("sts").get_caller_identity()["Account"]

        # Comprehensive execution policy with least privilege permissions
        execution_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BedrockModelInvocation",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [
                        "arn:aws:bedrock:*::foundation-model/*",
                        f"arn:aws:bedrock:{self.region}:{account_id}:*",
                    ],
                },
                {
                    "Sid": "ECRImageAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                    "Resource": [
                        f"arn:aws:ecr:{self.region}:{account_id}:repository/*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["logs:DescribeLogGroups"],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                    ],
                },
                {
                    "Sid": "ECRTokenAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                    ],
                    "Resource": ["*"],
                },
                {
                    "Effect": "Allow",
                    "Resource": "*",
                    "Action": "cloudwatch:PutMetricData",
                    "Condition": {
                        "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                    },
                },
                {
                    "Sid": "GetAgentAccessToken",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:workload-identity-directory/default/workload-identity/market-trends-agent-*",
                    ],
                },
                {
                    "Sid": "BedrockAgentCoreMemoryOperations",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:ListMemories",
                        "bedrock-agentcore:ListEvents",
                        "bedrock-agentcore:CreateEvent",
                        "bedrock-agentcore:RetrieveMemories",
                        "bedrock-agentcore:GetMemoryStrategies",
                        "bedrock-agentcore:DeleteMemory",
                        "bedrock-agentcore:GetMemory",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:memory/*"
                    ],
                },
                {
                    "Sid": "BedrockAgentCoreBrowserOperations",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetBrowserSession",
                        "bedrock-agentcore:StartBrowserSession",
                        "bedrock-agentcore:StopBrowserSession",
                        "bedrock-agentcore:CreateBrowserSession",
                        "bedrock-agentcore:DeleteBrowserSession",
                        "bedrock-agentcore:ConnectBrowserAutomationStream",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:browser-custom/*",
                        f"arn:aws:bedrock-agentcore:*:aws:browser/*"
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:PutParameter",
                        "ssm:DeleteParameter",
                    ],
                    "Resource": f"arn:aws:ssm:{self.region}:{account_id}:parameter/bedrock-agentcore/market-trends-agent/*",
                    "Sid": "SSMParameterAccess",
                },
            ],
        }

        try:
            # Create the role
            logger.info(f"IAM ロールを作成中: {role_name}")
            role_response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Execution role for Market Trends Agent with comprehensive permissions",
            )

            # Attach the comprehensive execution policy
            logger.info(
                f"包括的な実行ポリシーをロールにアタッチ中: {role_name}"
            )
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="MarketTrendsAgentComprehensivePolicy",
                PolicyDocument=json.dumps(execution_policy),
            )

            role_arn = role_response["Role"]["Arn"]
            logger.info(f"IAM ロールを作成しました。ARN: {role_arn}")

            # Wait for role to propagate
            logger.info("ロールの反映を待機中...")
            time.sleep(10)

            return role_arn

        except self.iam_client.exceptions.EntityAlreadyExistsException:
            logger.info(f"IAM ロール {role_name} は既に存在します。既存のロールを使用します")

            # Update the existing role with comprehensive permissions
            logger.info("既存のロールに包括的な権限を更新中...")
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="MarketTrendsAgentComprehensivePolicy",
                PolicyDocument=json.dumps(execution_policy),
            )

            role_response = self.iam_client.get_role(RoleName=role_name)
            return role_response["Role"]["Arn"]

        except Exception as e:
            logger.error(f"IAM ロールの作成に失敗しました: {e}")
            raise

    def create_agentcore_memory(self) -> str:
        """AgentCore Memory を作成し、ARN を SSM Parameter Store に保存する"""
        try:
            from bedrock_agentcore.memory import MemoryClient
            from bedrock_agentcore.memory.constants import StrategyType

            memory_name = "MarketTrendsAgentMultiStrategy"
            memory_client = MemoryClient(region_name=self.region)

            # Check if memory ARN already exists in SSM
            param_name = "/bedrock-agentcore/market-trends-agent/memory-arn"
            try:
                response = self.ssm_client.get_parameter(Name=param_name)
                existing_memory_arn = response["Parameter"]["Value"]
                logger.info(
                    f"SSM で既存のメモリ ARN を発見: {existing_memory_arn}"
                )
                return existing_memory_arn
            except self.ssm_client.exceptions.ParameterNotFound:
                logger.info(
                    "SSM に既存のメモリ ARN が見つかりません。新しいメモリを作成中..."
                )

            # Check if memory exists by name
            try:
                memories = memory_client.list_memories()
                for memory in memories:
                    if (
                        memory.get("name") == memory_name
                        and memory.get("status") == "ACTIVE"
                    ):
                        memory_arn = memory["arn"]
                        logger.info(f"既存のアクティブなメモリを発見: {memory_arn}")

                        # Store in SSM for future use
                        self.ssm_client.put_parameter(
                            Name=param_name,
                            Value=memory_arn,
                            Type="String",
                            Overwrite=True,
                            Description="Memory ARN for Market Trends Agent",
                        )
                        logger.info("既存のメモリ ARN を SSM に保存しました")
                        return memory_arn
            except Exception as e:
                logger.warning(f"既存のメモリ確認中にエラーが発生しました: {e}")

            # Create new memory
            logger.info("新しい AgentCore Memory を作成中...")

            strategies = [
                {
                    StrategyType.USER_PREFERENCE.value: {
                        "name": "BrokerPreferences",
                        "description": "Captures broker preferences, risk tolerance, and investment styles",
                        "namespaces": ["market-trends/broker/{actorId}/preferences"],
                    }
                },
                {
                    StrategyType.SEMANTIC.value: {
                        "name": "MarketTrendsSemantic",
                        "description": "Stores financial facts, market analysis, and investment insights",
                        "namespaces": ["market-trends/broker/{actorId}/semantic"],
                    }
                },
            ]

            memory = memory_client.create_memory_and_wait(
                name=memory_name,
                description="Market Trends Agent with multi-strategy memory for broker financial interests",
                strategies=strategies,
                event_expiry_days=90,
                max_wait=300,
                poll_interval=10,
            )

            memory_arn = memory["arn"]
            logger.info(f"メモリを正常に作成しました: {memory_arn}")

            # Store memory ARN in SSM Parameter Store
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=memory_arn,
                Type="String",
                Overwrite=True,
                Description="Memory ARN for Market Trends Agent",
            )
            logger.info("メモリ ARN を SSM Parameter Store に保存しました")

            return memory_arn

        except Exception as e:
            logger.error(f"メモリの作成に失敗しました: {e}")
            raise

    def deploy_agent(
        self,
        agent_name: str,
        role_name: str = "MarketTrendsAgentRole",
        entrypoint: str = "market_trends_agent.py",
        requirements_file: str = None,
    ) -> str:
        """すべての要件を満たして Market Trends Agent をデプロイする"""

        try:
            from bedrock_agentcore_starter_toolkit import Runtime

            logger.info("市場トレンドエージェントのデプロイを開始")
            logger.info(f"   エージェント名: {agent_name}")
            logger.info(f"   リージョン: {self.region}")
            logger.info(f"   エントリポイント: {entrypoint}")

            # Step 1: Determine dependency management approach
            if requirements_file is None:
                # Auto-detect: prefer uv if pyproject.toml exists, fallback to requirements.txt
                if Path("pyproject.toml").exists():
                    logger.info(
                        "pyproject.toml を使用した uv による依存関係管理"
                    )
                    requirements_file = "pyproject.toml"
                elif Path("requirements.txt").exists():
                    logger.info(
                        "requirements.txt を使用した pip による依存関係管理"
                    )
                    requirements_file = "requirements.txt"
                else:
                    raise FileNotFoundError(
                        "No pyproject.toml or requirements.txt found"
                    )

            logger.info(f"   依存関係: {requirements_file}")

            # Step 2: Create AgentCore Memory
            memory_arn = self.create_agentcore_memory()

            # Step 3: Create execution role with all permissions
            execution_role_arn = self.create_execution_role(role_name)

            # Step 4: Initialize runtime
            runtime = Runtime()

            # Step 5: Configure the runtime
            logger.info("ランタイムを設定中...")

            runtime.configure(
                execution_role=execution_role_arn,
                entrypoint=entrypoint,
                requirements_file=requirements_file,
                region=self.region,
                agent_name=agent_name,
                auto_create_ecr=True,
            )

            logger.info("設定が完了しました")

            # Step 6: Launch the runtime
            logger.info("ランタイムを起動中 (数分かかる場合があります)...")
            logger.info("   コンテナイメージをビルド中...")
            logger.info("   ECR にプッシュ中...")
            logger.info("   AgentCore Runtime を作成中...")

            runtime.launch(auto_update_on_conflict=True)

            logger.info("起動が完了しました")

            # Step 7: Get status and extract ARN
            logger.info("ランタイムのステータスを取得中...")
            status = runtime.status()

            # Extract runtime ARN
            runtime_arn = None
            if hasattr(status, "agent_arn"):
                runtime_arn = status.agent_arn
            elif hasattr(status, "config") and hasattr(status.config, "agent_arn"):
                runtime_arn = status.config.agent_arn

            if runtime_arn:
                # Save ARN to file
                arn_file = Path(".agent_arn")
                with open(arn_file, "w") as f:
                    f.write(runtime_arn)

                logger.info("\n市場トレンドエージェントが正常にデプロイされました！")
                logger.info(f"ランタイム ARN: {runtime_arn}")
                logger.info(f"メモリ ARN: {memory_arn}")
                logger.info(f"リージョン: {self.region}")
                logger.info(f"実行ロール: {execution_role_arn}")
                logger.info(f"ARN を保存しました: {arn_file}")

                # Show CloudWatch logs info
                agent_id = runtime_arn.split("/")[-1]
                log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-DEFAULT"
                logger.info("\nモニタリング:")
                logger.info(f"   CloudWatch ログ: {log_group}")
                logger.info(f"   ログ追跡: aws logs tail {log_group} --follow")

                logger.info("\n次のステップ:")
                logger.info("1. エージェントをテスト: python test_agent.py")
                logger.info("2. CloudWatch でログを監視")
                logger.info("3. 統合のためにランタイム ARN を使用")

                return runtime_arn
            else:
                logger.error("ランタイム ARN を抽出できませんでした")
                logger.info(f"ステータス: {status}")
                return None

        except ImportError:
            logger.error("bedrock-agentcore-starter-toolkit がインストールされていません")
            if Path("pyproject.toml").exists():
                logger.info("インストールコマンド: uv add bedrock-agentcore-starter-toolkit")
            else:
                logger.info(
                    "インストールコマンド: pip install bedrock-agentcore-starter-toolkit"
                )
            return None
        except Exception as e:
            logger.error(f"デプロイに失敗しました: {e}")
            import traceback

            logger.error(f"完全なエラー: {traceback.format_exc()}")
            return None


def check_prerequisites():
    """すべての前提条件が満たされているか確認する"""
    logger.info("前提条件を確認中...")

    # Check if required files exist
    required_files = [
        "market_trends_agent.py",
        "tools/browser_tool.py",
        "tools/broker_card_tools.py",
        "tools/memory_tools.py",
        "tools/__init__.py",
    ]

    # Check for dependency files (either pyproject.toml or requirements.txt)
    has_pyproject = Path("pyproject.toml").exists()
    has_requirements = Path("requirements.txt").exists()

    if not has_pyproject and not has_requirements:
        logger.error("依存関係ファイルが見つかりません (pyproject.toml または requirements.txt)")
        return False

    if has_pyproject:
        logger.info("pyproject.toml を発見 - uv を使用して依存関係を管理します")
    elif has_requirements:
        logger.info(
            "requirements.txt を発見 - pip を使用して依存関係を管理します"
        )

    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    if missing_files:
        logger.error(f"必須ファイルが見つかりません: {missing_files}")
        return False

    # Note: Docker/Podman not required - AgentCore uses AWS CodeBuild for container building
    logger.info(
        "コンテナビルドは AWS CodeBuild を使用します (ローカル Docker は不要)"
    )

    # Check AWS credentials
    try:
        boto3.client("sts").get_caller_identity()
        logger.info("AWS 認証情報が設定済みです")
    except Exception as e:
        logger.error(f"AWS 認証情報が設定されていません: {e}")
        return False

    logger.info("すべての前提条件を満たしています")
    return True


def main():
    """メインデプロイ関数"""
    parser = argparse.ArgumentParser(
        description="Deploy Market Trends Agent to Amazon Bedrock AgentCore Runtime"
    )
    parser.add_argument(
        "--agent-name",
        default="market_trends_agent",
        help="Name for the agent (default: market_trends_agent)",
    )
    parser.add_argument(
        "--role-name",
        default="MarketTrendsAgentRole",
        help="IAM role name (default: MarketTrendsAgentRole)",
    )
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--skip-checks", action="store_true", help="Skip prerequisite checks"
    )

    args = parser.parse_args()

    # Check prerequisites
    if not args.skip_checks and not check_prerequisites():
        logger.error("前提条件を満たしていません。上記の問題を解決するか --skip-checks を使用してください")
        exit(1)

    # Create deployer and deploy
    deployer = MarketTrendsAgentDeployer(region=args.region)

    runtime_arn = deployer.deploy_agent(
        agent_name=args.agent_name, role_name=args.role_name
    )

    if runtime_arn:
        logger.info("\nデプロイが正常に完了しました！")
        logger.info("'python test_agent.py' を実行してデプロイしたエージェントをテストしてください。")
    else:
        logger.error("デプロイに失敗しました")
        exit(1)


if __name__ == "__main__":
    main()
