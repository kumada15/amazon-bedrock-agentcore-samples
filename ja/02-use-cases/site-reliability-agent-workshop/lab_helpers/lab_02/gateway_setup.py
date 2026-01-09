"""
Lab 02: AgentCore Gateway サービスロールのセットアップ

Gateway が Lambda ターゲットを呼び出すために必要な IAM サービスロールを作成します。
Lambda 実行ロールとは別に、Gateway 専用のロールが必要です。
"""

import json
import boto3
from lab_helpers.constants import PARAMETER_PATHS
from lab_helpers.parameter_store import put_parameter

def create_gateway_service_role(region_name="us-west-2", account_id=None):
    """
    AgentCore Gateway 用の IAM サービスロールを作成します。

    Gateway に必要な権限:
    1. Lambda 関数の呼び出し
    2. CloudWatch ログへのアクセス
    3. 必要に応じて他のサービスの呼び出し

    Args:
        region_name: AWS リージョン
        account_id: AWS アカウント ID（指定しない場合は自動取得）

    Returns:
        ロール ARN およびその他の詳細を含む辞書
    """
    iam_client = boto3.client('iam', region_name=region_name)
    sts_client = boto3.client('sts', region_name=region_name)
    ssm_client = boto3.client('ssm', region_name=region_name)

    # アカウント ID が提供されていない場合は取得
    if not account_id:
        account_id = sts_client.get_caller_identity()['Account']

    role_name = "aiml301-gateway-service-role"

    # 信頼関係: bedrock-agentcore サービスがこのロールを引き受けることを許可
    # セキュリティのため特定のアカウントと Gateway ARN パターンに制限
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region_name}:{account_id}:gateway/*"
                    }
                }
            }
        ]
    }

    # 権限: Gateway は Lambda の呼び出し、CloudWatch へのアクセス、AgentCore リソースの管理が必要
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeLambdaFunctions",
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": "*"
            },
            {
                "Sid": "BedrockAgentCorePermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*"
                ],
                "Resource": "*"
            },
            {
                "Sid": "CloudWatchLogsPermissions",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams"
                ],
                "Resource": "*"
            }
        ]
    }

    try:
        # ロールが既に存在するか確認
        try:
            role = iam_client.get_role(RoleName=role_name)
            print(f"✓ Gateway サービスロールは既に存在します: {role['Role']['Arn']}")
            role_arn = role['Role']['Arn']
        except iam_client.exceptions.NoSuchEntityException:
            print(f"Gateway サービスロールを作成中: {role_name}")

            # ロールを作成
            response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Service role for AgentCore Gateway to invoke Lambda targets"
            )

            role_arn = response['Role']['Arn']
            print(f"✓ Gateway サービスロールを作成しました: {role_arn}")

            # Lambda 呼び出し用のインラインポリシーをアタッチ
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="gateway-invoke-lambda",
                PolicyDocument=json.dumps(permissions_policy)
            )
            print(f"✓ 権限ポリシーをアタッチしました")

        # 後で使用するために Parameter Store に保存（一貫性のため定数を使用）
        gateway_role_arn_param = PARAMETER_PATHS["lab_02"]["gateway_role_arn"]
        put_parameter(
            gateway_role_arn_param,
            role_arn,
            description="Gateway service role ARN for Lab 02",
            region_name=region_name
        )
        print(f"✓ ロール ARN を Parameter Store に保存しました: {gateway_role_arn_param}")

        return {
            'role_arn': role_arn,
            'role_name': role_name,
            'account_id': account_id,
            'region': region_name
        }

    except Exception as e:
        print(f"❌ Gateway サービスロールの作成中にエラー: {e}")
        raise


if __name__ == "__main__":
    from lab_helpers.config import AWS_REGION

    print("=" * 70)
    print("AgentCore Gateway サービスロールをセットアップ中")
    print("=" * 70)
    print()

    result = create_gateway_service_role(region_name=AWS_REGION)

    print()
    print("=" * 70)
    print("✅ Gateway サービスロールのセットアップが完了しました")
    print("=" * 70)
    print(f"ロール ARN: {result['role_arn']}")
    print()
