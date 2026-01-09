"""
Lab 05: Supervisor Runtime IAM セットアップ

以下の権限を持つ Supervisor エージェントランタイム用の IAM ロールを作成します:
- オーケストレーション用の Bedrock モデル呼び出し
- JWT トークン伝播による 3 つのサブエージェント Gateway 呼び出し
- Parameter Store からの Gateway URL 取得
- CloudWatch へのログ書き込み
"""

import json
import boto3
import logging
from typing import Dict
from botocore.exceptions import ClientError

from lab_helpers.config import AWS_REGION

logger = logging.getLogger(__name__)


def create_supervisor_runtime_iam_role(
    role_name: str,
    region: str = AWS_REGION,
    account_id: str = None
) -> Dict:
    """
    マルチ Gateway オーケストレーション権限を持つ Supervisor Runtime 用の IAM ロールを作成します。

    Supervisor ランタイムには以下の権限が必要です:
    1. 3 つの異なるエージェント Gateway への接続（Diagnostics、Remediation、Prevention）
    2. 複数のエージェント間でのリクエストのオーケストレーション
    3. LLM ベースのオーケストレーションロジック用の Bedrock モデル呼び出し
    4. Parameter Store からの Gateway URL 取得
    5. CloudWatch へのログ書き込み

    認証には JWT トークン伝播を使用:
    - ユーザーは Authorization ヘッダーで JWT トークンを提供
    - Supervisor Runtime は JWT を抽出し Gateway 接続に伝播
    - M2M 認証情報やトークン取得は不要

    Args:
        role_name: IAM ロールの名前
        region: AWS リージョン（デフォルト: config から取得）
        account_id: AWS アカウント ID（未指定の場合は自動検出）

    Returns:
        role_name、role_arn、ポリシー詳細を含む Dict
    """
    iam = boto3.client('iam', region_name=region)
    sts = boto3.client('sts', region_name=region)

    # Get account ID
    if not account_id:
        account_id = sts.get_caller_identity()['Account']

    logger.info(f"Supervisor ランタイム IAM ロールを作成中: {role_name}")
    logger.info(f"認証: JWT トークン伝播 (ユーザー JWT → Supervisor → Gateways)")

    # Trust policy: Allow bedrock-agentcore service to assume role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    # Create role
    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="IAM role for Lab 05 Supervisor Agent Runtime - Multi-agent orchestration",
            Tags=[
                {"Key": "Workshop", "Value": "AIML301"},
                {"Key": "Lab", "Value": "Lab-05"},
                {"Key": "Component", "Value": "SupervisorRuntime"}
            ]
        )
        role_arn = response['Role']['Arn']
        logger.info(f"✅ ロールを作成しました: {role_arn}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            logger.warning(f"⚠️ ロール {role_name} は既に存在します。既存のロールを使用します")
            response = iam.get_role(RoleName=role_name)
            role_arn = response['Role']['Arn']
        else:
            logger.error(f"❌ ロールの作成に失敗しました: {e}")
            raise

    # Inline policy for supervisor-specific permissions
    policy_name = f"{role_name}-policy"
    supervisor_policy = {
        "Version": "2012-10-17",
        "Statement": [
            # 1. Bedrock Model Invocation (for orchestration logic)
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream"
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",  # Cross-region model IDs (e.g., us.anthropic.claude-*)
                    f"arn:aws:bedrock:{region}:{account_id}:inference-profile/*",
                    f"arn:aws:bedrock:us-east-1:{account_id}:inference-profile/*",
                    f"arn:aws:bedrock:us-east-2:{account_id}:inference-profile/*",
                    f"arn:aws:bedrock:us-west-2:{account_id}:inference-profile/*"
                ]
            },
            # 2. CloudWatch Logs (Runtime logging)
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/*"
                ]
            },
            # 2b. X-Ray Tracing (Runtime observability and tracing)
            {
                "Sid": "XRayTracing",
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords"
                ],
                "Resource": "*"
            },
            # 3. Gateway Access (call sub-agent gateways)
            {
                "Sid": "GatewayAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeGateway",
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:ListGateways"
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/*"
                ]
            },
            # 6. Parameter Store (Configuration and gateway URL retrieval)
            {
                "Sid": "ParameterStoreRead",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath"
                ],
                "Resource": [
                    f"arn:aws:ssm:{region}:{account_id}:parameter/*"
                ]
            },
            # 7. KMS (Decrypt secrets and parameters)
            {
                "Sid": "KMSDecrypt",
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:DescribeKey"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "kms:ViaService": [
                            f"secretsmanager.{region}.amazonaws.com",
                            f"ssm.{region}.amazonaws.com"
                        ]
                    }
                }
            },
            # 8. ECR Access (Pull container images)
            {
                "Sid": "ECRAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                "Resource": "*"
            },
        ]
    }

    # Attach inline policy
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(supervisor_policy)
        )
        logger.info(f"✅ インラインポリシーをアタッチしました: {policy_name}")
    except ClientError as e:
        logger.error(f"❌ ポリシーのアタッチに失敗しました: {e}")
        raise

    # Return role information
    return {
        "role_name": role_name,
        "role_arn": role_arn,
        "policy_name": policy_name,
        "region": region,
        "account_id": account_id,
        "permissions": {
            "bedrock_models": "InvokeModel and streaming",
            "gateways": "Call 3 sub-agent gateways with JWT propagation",
            "cloudwatch_logs": "Runtime logging",
            "parameter_store": "Gateway URL retrieval (/aiml301/lab-0X/gateway-id)",
            "kms": "Decrypt parameters",
            "ecr": "Pull container images"
        }
    }


def delete_supervisor_runtime_iam_role(role_name: str, region: str = AWS_REGION) -> bool:
    """
    Supervisor ランタイムの IAM ロールと関連ポリシーを削除します。

    Args:
        role_name: 削除する IAM ロールの名前
        region: AWS リージョン（デフォルト: config から取得）

    Returns:
        削除成功時は True、それ以外は False
    """
    iam = boto3.client('iam', region_name=region)

    logger.info(f"Supervisor ランタイム IAM ロールを削除中: {role_name}")

    try:
        # List and delete inline policies
        response = iam.list_role_policies(RoleName=role_name)
        for policy_name in response.get('PolicyNames', []):
            iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            logger.info(f"✅ インラインポリシーを削除しました: {policy_name}")

        # List and detach managed policies
        response = iam.list_attached_role_policies(RoleName=role_name)
        for policy in response.get('AttachedPolicies', []):
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
            logger.info(f"✅ マネージドポリシーをデタッチしました: {policy['PolicyName']}")

        # Delete role
        iam.delete_role(RoleName=role_name)
        logger.info(f"✅ ロールを削除しました: {role_name}")

        return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            logger.warning(f"⚠️ ロール {role_name} は存在しません")
            return True
        else:
            logger.error(f"❌ ロールの削除に失敗しました: {e}")
            return False
