"""
Lab 04: AgentCore Runtime デプロイメントヘルパー

AgentCore Browser を使用した Strands Prevention エージェントを Amazon Bedrock AgentCore Runtime にデプロイします。

機能:
- Runtime 実行用の IAM ロール作成（Browser 権限を含む）
- エージェントコードのパッケージング（Strands + Browser）
- bedrock-agentcore-starter-toolkit による Runtime デプロイ
- Parameter Store への設定保存
- デプロイメントライフサイクル管理（作成、更新、削除）
- Lab-03 Gateway との統合（オプション）

AWS パターンに基づく:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-toolkit.html
- https://github.com/awslabs/amazon-bedrock-agentcore-samples
"""

import json
import boto3
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from botocore.exceptions import ClientError

# Import centralized configuration
from lab_helpers.config import AWS_REGION
from lab_helpers.constants import PARAMETER_PATHS

logger = logging.getLogger(__name__)

# Configuration defaults
REGION = AWS_REGION  # Use centralized region from config.py
PREFIX = "aiml301"
RUNTIME_NAME = f"{PREFIX}-prevention-runtime"
RUNTIME_ROLE_NAME = f"{PREFIX}-agentcore-prevention-role"
RUNTIME_POLICY_NAME = f"{PREFIX}-prevention-runtime-policy"


class AgentCoreRuntimeDeployer:
    """Strands Prevention Agent を AgentCore Runtime にデプロイするためのヘルパー"""

    def __init__(
        self,
        region: str = REGION,
        prefix: str = PREFIX,
        runtime_name: str = RUNTIME_NAME,
        verbose: bool = True
    ):
        """
        AWS クライアントと設定でデプロイヤーを初期化します。

        Args:
            region: AWS リージョン（デフォルト: us-west-2）
            prefix: リソース命名プレフィックス（デフォルト: aiml301）
            runtime_name: デプロイされる Runtime の名前（デフォルト: aiml301-prevention-runtime）
            verbose: 詳細ログを有効にする
        """
        self.region = region
        self.prefix = prefix
        self.runtime_name = runtime_name
        self.verbose = verbose

        # AWS clients
        self.iam = boto3.client('iam', region_name=region)
        self.agentcore = boto3.client('bedrock-agentcore-control', region_name=region)
        self.ssm = boto3.client('ssm', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        self.logs = boto3.client('logs', region_name=region)

        # Get account ID
        self.account_id = self.sts.get_caller_identity()['Account']

        # Initialize logger
        if verbose:
            logging.basicConfig(level=logging.INFO)
            logger.setLevel(logging.INFO)

    def _log(self, message: str, level: str = "info"):
        """フォーマット付きでメッセージをログ出力する"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        levels = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
        icon = levels.get(level, "•")
        print(f"{icon} [{timestamp}] {message}")
        getattr(logger, level, logger.info)(message)

    def check_prerequisites(self) -> bool:
        """デプロイのすべての前提条件が満たされているか確認する"""
        self._log("前提条件を確認中...")

        try:
            # Check toolkit installation
            try:
                from bedrock_agentcore_starter_toolkit import Runtime
                self._log("bedrock-agentcore-starter-toolkit がインストールされています", "success")
            except ImportError:
                self._log(
                    "bedrock-agentcore-starter-toolkit が見つかりません。"
                    "pip install bedrock-agentcore-starter-toolkit でインストールしてください",
                    "error"
                )
                return False

            # Check FastMCP installation
            try:
                import fastmcp
                self._log("fastmcp がインストールされています", "success")
            except ImportError:
                self._log(
                    "fastmcp が見つかりません。"
                    "pip install fastmcp でインストールしてください",
                    "error"
                )
                return False

            # Check Strands Tools installation
            try:
                import strands_tools
                self._log("strands_tools がインストールされています", "success")
            except ImportError:
                self._log(
                    "strands_tools が見つかりません。"
                    "pip install strands-agents-tools でインストールしてください",
                    "error"
                )
                return False

            # Check AWS credentials and permissions
            identity = self.sts.get_caller_identity()
            self._log(f"AWS アカウント: {self.account_id}", "success")
            self._log(f"AWS IAM ユーザー/ロール: {identity.get('Arn')}", "success")

            # Check IAM permissions (attempt to list roles)
            try:
                self.iam.list_roles(MaxItems=1)
                self._log("IAM 権限が確認されました", "success")
            except ClientError as e:
                self._log(f"IAM 権限が不足しています: {e}", "error")
                return False

            # Check AgentCore access
            try:
                self.agentcore.list_agent_runtimes()
                self._log("AgentCore アクセスが確認されました", "success")
            except ClientError as e:
                self._log(f"AgentCore アクセスが拒否されました: {e}", "error")
                return False

            self._log("すべての前提条件が満たされています", "success")
            return True

        except Exception as e:
            self._log(f"前提条件チェックが失敗しました: {e}", "error")
            return False

    def create_runtime_iam_role(self) -> Dict:
        """
        AgentCore Runtime 実行用の IAM ロールを作成します。

        このロールは以下を許可します:
        - Runtime サービスによるロールの引き受け
        - CloudWatch ログ記録
        - ECR イメージアクセス
        - Bedrock モデル呼び出し（Prevention Agent 用）
        - Parameter Store アクセス
        - AgentCore Browser アクセス
        - Workload Identity 管理（MCP エンドポイント認証用）
        - OAuth2 認証情報アクセス（Gateway M2M トークン検証用）
        - Secrets Manager アクセス（認証情報保存用）

        Returns:
            ロール ARN とメタデータを含む Dict
        """
        self._log("Runtime 用の IAM ロールを作成中...")

        # Trust policy: Allow bedrock-agentcore service to assume role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": self.account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/*"
                        }
                    }
                }
            ]
        }

        # Permissions policy for Runtime (includes Browser permissions and MCP/OAuth2 access)
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/bedrock-agentcore/runtime/*"
                },
                {
                    "Sid": "ECRAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "BedrockModels",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream"
                    ],
                    "Resource": [
                        f"arn:aws:bedrock:{self.region}::foundation-model/*",
                        f"arn:aws:bedrock:{self.region}:{self.account_id}:inference-profile/*",
                        "arn:aws:bedrock:us-east-1::foundation-model/*",
                        f"arn:aws:bedrock:us-east-1:{self.account_id}:inference-profile/*",
                        "arn:aws:bedrock:us-east-2::foundation-model/*",
                        f"arn:aws:bedrock:us-east-2:{self.account_id}:inference-profile/*",
                        "arn:aws:bedrock:us-west-2::foundation-model/*",
                        f"arn:aws:bedrock:us-west-2:{self.account_id}:inference-profile/*"
                    ]
                },
                {
                    "Sid": "AgentCoreBrowser",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:*",
                        "aws-marketplace:Subscribe", 
                        "aws-marketplace:ViewSubscriptions"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "ParameterStore",
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath"
                    ],
                    "Resource": f"arn:aws:ssm:{self.region}:{self.account_id}:parameter/{self.prefix}/*"
                },
                {
                    "Sid": "WorkloadIdentity",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:CreateWorkloadIdentity"
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default/workload-identity/*"
                    ]
                },
                {
                    "Sid": "OAuth2Credentials",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetResourceOauth2Token"
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:token-vault/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:token-vault/*/oauth2credentialprovider/*",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default/workload-identity/*"
                    ]
                },
                {
                    "Sid": "SecretsManager",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Resource": [
                        f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:bedrock-agentcore-identity!*",
                        f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:bedrock-agentcore-*"
                    ]
                }
            ]
        }

        try:
            # Check if role exists
            try:
                role = self.iam.get_role(RoleName=RUNTIME_ROLE_NAME)
                self._log(f"IAM ロールが既に存在します: {RUNTIME_ROLE_NAME}", "warning")
                role_arn = role['Role']['Arn']
            except self.iam.exceptions.NoSuchEntityException:
                # Create new role
                role = self.iam.create_role(
                    RoleName=RUNTIME_ROLE_NAME,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Execution role for AgentCore Runtime - Lab 04 Prevention Agent",
                    MaxSessionDuration=3600
                )
                role_arn = role['Role']['Arn']
                self._log(f"IAM ロールを作成しました: {RUNTIME_ROLE_NAME}", "success")

                # Wait for role to propagate in IAM
                time.sleep(10)

            # Attach permissions policy
            self.iam.put_role_policy(
                RoleName=RUNTIME_ROLE_NAME,
                PolicyName=RUNTIME_POLICY_NAME,
                PolicyDocument=json.dumps(permissions_policy)
            )
            self._log(f"権限ポリシーをアタッチしました: {RUNTIME_POLICY_NAME}", "success")

            # Store role ARN in Parameter Store
            param_name = PARAMETER_PATHS["lab_04"]["runtime_role_arn"]
            self.ssm.put_parameter(
                Name=param_name,
                Value=role_arn,
                Type="String",
                Overwrite=True,
                Description="Lab-04 AgentCore Runtime 用の IAM ロール ARN"
            )
            self._log(f"ロール ARN を Parameter Store に保存しました", "success")

            return {
                "role_arn": role_arn,
                "role_name": RUNTIME_ROLE_NAME,
                "policy_name": RUNTIME_POLICY_NAME,
                "account_id": self.account_id
            }

        except Exception as e:
            self._log(f"IAM ロールの作成に失敗しました: {e}", "error")
            raise

    def package_agent_code(
        self,
        agent_script_path: Path,
        requirements_path: Optional[Path] = None,
        include_files: Optional[List[Path]] = None
    ) -> Dict:
        """
        Strands Prevention エージェントコードをデプロイ用にパッケージングします。

        Args:
            agent_script_path: エージェント Python スクリプトへのパス
            requirements_path: requirements.txt へのパス（オプション）
            include_files: 含める追加ファイル（オプション）

        Returns:
            パッケージメタデータとファイルパスを含む Dict
        """
        self._log(f"{agent_script_path} からエージェントコードをパッケージング中...")

        # Verify agent script exists
        if not Path(agent_script_path).exists():
            self._log(f"エージェントスクリプトが見つかりません: {agent_script_path}", "error")
            raise FileNotFoundError(f"エージェントスクリプトが見つかりません: {agent_script_path}")

        # Read agent code
        with open(agent_script_path, 'r') as f:
            agent_code = f.read()

        package_info = {
            "agent_script": str(agent_script_path),
            "code_size_bytes": len(agent_code.encode()),
            "code_size_mb": round(len(agent_code.encode()) / (1024 * 1024), 2),
            "timestamp": datetime.utcnow().isoformat(),
            "files": {
                "agent_script": str(agent_script_path)
            }
        }

        # Add requirements if provided
        if requirements_path and Path(requirements_path).exists():
            with open(requirements_path, 'r') as f:
                requirements = f.read()
            package_info["files"]["requirements"] = str(requirements_path)
            package_info["requirements_lines"] = len(requirements.splitlines())

        # Add other files if provided
        if include_files:
            for file_path in include_files:
                if Path(file_path).exists():
                    package_info["files"][Path(file_path).name] = str(file_path)

        self._log(f"エージェントコードをパッケージングしました: {package_info['code_size_mb']} MB", "success")

        return package_info

    def deploy_runtime(
        self,
        agent_code: str,
        agent_name: str = "prevention-agent",
        role_arn: Optional[str] = None,
        description: Optional[str] = None,
        timeout_seconds: int = 300
    ) -> Dict:
        """
        Strands エージェントを AgentCore Runtime にデプロイします。

        Args:
            agent_code: 文字列としてのエージェント Python コード
            agent_name: エージェント/Runtime の名前
            role_arn: IAM ロール ARN（未指定の場合は Parameter Store から取得）
            description: Runtime の説明
            timeout_seconds: 実行タイムアウト

        Returns:
            デプロイ情報を含む Dict（Runtime ID、ARN、エンドポイントなど）
        """
        self._log(f"Runtime をデプロイ中: {agent_name}...")

        # Get role ARN if not provided
        if not role_arn:
            try:
                response = self.ssm.get_parameter(
                    Name=PARAMETER_PATHS["lab_04"]["runtime_role_arn"]
                )
                role_arn = response['Parameter']['Value']
                self._log(f"Parameter Store からロール ARN を取得しました", "info")
            except ClientError:
                self._log("Parameter Store にロール ARN が見つかりません。ロールを作成中...", "warning")
                role_info = self.create_runtime_iam_role()
                role_arn = role_info['role_arn']

        try:
            # Create runtime using bedrock-agentcore-starter-toolkit
            from bedrock_agentcore_starter_toolkit import Runtime

            runtime = Runtime(
                name=self.runtime_name,
                entrypoint=agent_code,
                role_arn=role_arn,
                region_name=self.region,
                timeout_seconds=timeout_seconds,
                description=description or f"Strands prevention agent with Browser - Lab 04"
            )

            # Deploy to AgentCore
            runtime_config = runtime.deploy()

            self._log(f"Runtime のデプロイが成功しました", "success")

            deployment_info = {
                "runtime_name": self.runtime_name,
                "runtime_id": runtime_config.get('agent_runtime_id'),
                "runtime_arn": runtime_config.get('agent_runtime_arn'),
                "role_arn": role_arn,
                "region": self.region,
                "deployment_time": datetime.utcnow().isoformat(),
                "status": "DEPLOYED",
                "entrypoint": "agent_invocation",
                "tools": [
                    "validate_prevention_environment",
                    "analyze_infrastructure_prevention",
                    "research_aws_best_practices"
                ]
            }

            # Store deployment info in Parameter Store
            self.ssm.put_parameter(
                Name=f"/{self.prefix}/lab-04/runtime-config",
                Value=json.dumps(deployment_info, indent=2),
                Type="String",
                Overwrite=True,
                Description="Lab-04 AgentCore Runtime デプロイ設定"
            )

            return deployment_info

        except Exception as e:
            self._log(f"Runtime のデプロイに失敗しました: {e}", "error")
            raise

    def get_runtime_status(self, runtime_id: Optional[str] = None) -> Dict:
        """
        デプロイされた Runtime のステータスを取得します。

        Args:
            runtime_id: Runtime ID（未指定の場合は Parameter Store から取得）

        Returns:
            Runtime ステータスを含む Dict
        """
        try:
            # Get runtime ID if not provided
            if not runtime_id:
                response = self.ssm.get_parameter(
                    Name=f"/{self.prefix}/lab-04/runtime-config"
                )
                config = json.loads(response['Parameter']['Value'])
                runtime_id = config.get('runtime_id')

            if not runtime_id:
                self._log("Runtime ID が見つかりません", "error")
                return {"status": "NOT_FOUND"}

            # Get runtime details
            response = self.agentcore.get_agent_runtime(
                agentRuntimeIdentifier=runtime_id
            )

            status_info = {
                "runtime_id": response['agentRuntime']['agentRuntimeId'],
                "runtime_arn": response['agentRuntime']['agentRuntimeArn'],
                "status": response['agentRuntime']['status'],
                "created_at": response['agentRuntime'].get('createdAt'),
                "last_modified": response['agentRuntime'].get('lastModifiedAt')
            }

            self._log(f"Runtime ステータス: {status_info['status']}", "info")
            return status_info

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self._log(f"Runtime が見つかりません: {runtime_id}", "warning")
                return {"status": "NOT_FOUND"}
            raise

    def cleanup(self, force: bool = False) -> bool:
        """
        Lab-04 のリソースをクリーンアップします。

        Args:
            force: 確認なしで強制削除

        Returns:
            クリーンアップ成功時は True
        """
        self._log("クリーンアップを開始中...")

        if not force:
            confirm = input(
                f"Lab-04 Runtime '{self.runtime_name}' と関連リソースを削除しますか？"
                "この操作は元に戻せません。(yes/no): "
            )
            if confirm.lower() != 'yes':
                self._log("クリーンアップがキャンセルされました", "warning")
                return False

        try:
            # Get runtime ID from Parameter Store
            try:
                response = self.ssm.get_parameter(
                    Name=f"/{self.prefix}/lab-04/runtime-config"
                )
                config = json.loads(response['Parameter']['Value'])
                runtime_id = config.get('runtime_id')

                if runtime_id:
                    # Delete runtime
                    self.agentcore.delete_agent_runtime(
                        agentRuntimeIdentifier=runtime_id
                    )
                    self._log(f"Runtime を削除しました: {runtime_id}", "success")
            except ClientError as e:
                if e.response['Error']['Code'] != 'ParameterNotFound':
                    self._log(f"Runtime 削除エラー: {e}", "warning")

            # Delete IAM role and policies
            try:
                self.iam.delete_role_policy(
                    RoleName=RUNTIME_ROLE_NAME,
                    PolicyName=RUNTIME_POLICY_NAME
                )
                self._log(f"ロールポリシーを削除しました: {RUNTIME_POLICY_NAME}", "success")
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity':
                    self._log(f"ポリシー削除エラー: {e}", "warning")

            try:
                self.iam.delete_role(RoleName=RUNTIME_ROLE_NAME)
                self._log(f"IAM ロールを削除しました: {RUNTIME_ROLE_NAME}", "success")
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity':
                    self._log(f"ロール削除エラー: {e}", "warning")

            # Delete Parameter Store entries
            try:
                self.ssm.delete_parameter(Name=PARAMETER_PATHS["lab_04"]["runtime_role_arn"])
                self._log("Parameter Store エントリを削除しました: runtime-role-arn", "success")
            except ClientError:
                pass

            try:
                self.ssm.delete_parameter(Name=f"/{self.prefix}/lab-04/runtime-config")
                self._log("Parameter Store エントリを削除しました: runtime-config", "success")
            except ClientError:
                pass

            # Delete CloudWatch log groups
            try:
                log_groups = self.logs.describe_log_groups(
                    logGroupNamePrefix=f"/aws/bedrock-agentcore/runtime/{self.runtime_name}"
                )
                for log_group in log_groups.get('logGroups', []):
                    self.logs.delete_log_group(logGroupName=log_group['logGroupName'])
                    self._log(f"ロググループを削除しました: {log_group['logGroupName']}", "success")
            except ClientError:
                pass

            self._log("クリーンアップが正常に完了しました", "success")
            return True

        except Exception as e:
            self._log(f"クリーンアップに失敗しました: {e}", "error")
            raise


def store_runtime_configuration(runtime_arn: str, runtime_id: str = None, region: str = "us-west-2", prefix: str = "aiml301") -> None:
    """セッション間で永続化するために Runtime 設定を Parameter Store に保存する"""
    from lab_helpers.parameter_store import put_parameter

    print("\n" + "="*70)
    print("🔍 DEBUG: store_runtime_configuration() called")
    print("="*70)
    print(f"  Runtime ARN: {runtime_arn}")
    print(f"  Runtime ID: {runtime_id}")
    print(f"  Region: {region}")
    print(f"  Prefix: {prefix}")
    print()

    # Store runtime ARN using centralized constants
    runtime_arn_path = PARAMETER_PATHS["lab_04"]["runtime_arn"]
    print(f"📝 Runtime ARN を Parameter Store に保存中:")
    print(f"  パス: {runtime_arn_path}")
    print(f"  値: {runtime_arn}")
    try:
        result = put_parameter(
            key=runtime_arn_path,
            value=runtime_arn,
            description="Lab-04 用 AgentCore Runtime ARN",
            region_name=region,
            overwrite=True
        )
        print(f"✅ Runtime ARN を正常に保存しました (バージョン: {result})")
    except Exception as e:
        print(f"❌ Runtime ARN の保存に失敗しました: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Store runtime ID if provided
    if runtime_id:
        runtime_id_path = PARAMETER_PATHS["lab_04"]["runtime_id"]
        print(f"\n📝 Runtime ID を Parameter Store に保存中:")
        print(f"  パス: {runtime_id_path}")
        print(f"  値: {runtime_id}")
        try:
            result = put_parameter(
                key=runtime_id_path,
                value=runtime_id,
                description="Lab-04 用 AgentCore Runtime ID",
                region_name=region,
                overwrite=True
            )
            print(f"✅ Runtime ID を正常に保存しました (バージョン: {result})")
        except Exception as e:
            print(f"❌ Runtime ID の保存に失敗しました: {e}")
            import traceback
            traceback.print_exc()
            raise
    else:
        print(f"\n⏭️  Runtime ID が指定されていません。スキップ...")

    print("\n" + "="*70)
    print("✅ store_runtime_configuration() complete")
    print("="*70 + "\n")
