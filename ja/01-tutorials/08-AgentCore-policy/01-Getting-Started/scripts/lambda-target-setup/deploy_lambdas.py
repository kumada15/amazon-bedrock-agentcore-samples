"""
Lambda 関数をデプロイして ARN を config.json に保存

使用方法:
    python deploy_lambdas.py [role_arn]

例:
    # 既存のロールを使用
    python deploy_lambdas.py arn:aws:iam::123456789012:role/MyLambdaRole

    # 新しいロールを自動作成
    python deploy_lambdas.py
"""

import boto3
import zipfile
import io
import os
import json
import sys
import time


def get_or_create_lambda_role(iam_client):
    """Lambda 実行用の IAM ロールを取得または作成"""
    role_name = "AgentCoreLambdaExecutionRole"

    try:
        response = iam_client.get_role(RoleName=role_name)
        print(f"   ✅ Using existing IAM role: {role_name}")
        return response["Role"]["Arn"], False
    except iam_client.exceptions.NoSuchEntityException:
        print(f"   📝 Creating IAM role: {role_name}")

        # Lambda 用の信頼ポリシー
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        # ロールを作成
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for AgentCore Lambda functions",
        )

        # 基本的な Lambda 実行ポリシーをアタッチ
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        print(f"   ✅ IAM role created: {role_name}")
        print("   ⏳ Waiting 10 seconds for IAM propagation...")
        return response["Role"]["Arn"], True


def deploy_lambda(lambda_client, function_name, js_file, role_arn):
    """JS ファイルから Lambda 関数をデプロイ"""

    print(f"📦 Deploying {function_name}...")

    # JS ファイルを読み込み
    script_dir = os.path.dirname(os.path.abspath(__file__))
    js_path = os.path.join(script_dir, js_file)

    with open(js_path, "r") as f:
        code_content = f.read()

    # コードを index.mjs（ES モジュール）としてメモリ内に zip ファイルを作成
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("index.mjs", code_content)

    zip_buffer.seek(0)
    zip_content = zip_buffer.read()

    try:
        # 関数の作成を試みる
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime="nodejs20.x",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": zip_content},
            Description=f"AgentCore {function_name}",
            Timeout=30,
            MemorySize=256,
        )

        print("   ✅ Lambda created")
        print(f"   ARN: {response['FunctionArn']}")
        return response["FunctionArn"]

    except lambda_client.exceptions.ResourceConflictException:
        # 関数が既に存在する場合は更新
        print("   ℹ️  Function exists, updating code...")

        response = lambda_client.update_function_code(
            FunctionName=function_name, ZipFile=zip_content
        )

        print("   ✅ Code updated")
        print(f"   ARN: {response['FunctionArn']}")
        return response["FunctionArn"]

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def save_config(lambda_arns, output_file="config.json"):
    """Lambda ARN を Getting-Started ディレクトリの config.json に保存"""

    # スクリプトディレクトリを取得（lambda-target-setup）
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Getting-Started ディレクトリに上がる: lambda-target-setup -> scripts -> Getting-Started
    getting_started_dir = os.path.dirname(os.path.dirname(script_dir))
    config_path = os.path.join(getting_started_dir, output_file)

    config = {"lambdas": lambda_arns, "region": "us-east-1"}

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n💾 Configuration saved to: {config_path}")


def main():
    print("🚀 Deploying Lambda Functions\n")
    print("=" * 70)

    # AWS クライアントを初期化
    lambda_client = boto3.client("lambda", region_name="us-east-1")
    iam_client = boto3.client("iam", region_name="us-east-1")

    # ロール ARN が引数として提供されているか確認
    if len(sys.argv) >= 2:
        role_arn = sys.argv[1]

        # ロール ARN フォーマットを検証
        if not role_arn.startswith("arn:aws:iam::"):
            print(f"\n❌ Error: Invalid role ARN format: {role_arn}")
            print("期待される形式: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME")
            print("\n" + "=" * 70)
            sys.exit(1)

        print(f"\n🔐 Using provided IAM role: {role_arn}")
        print()
        newly_created = False
    else:
        # ロールが提供されていない場合は作成
        print("\n🔐 No role provided, setting up IAM role...")
        role_arn, newly_created = get_or_create_lambda_role(iam_client)
        print()

        # ロールが今作成された場合は IAM の伝播を待機
        if newly_created:
            time.sleep(10)

    # 各関数をデプロイ
    functions = [
        ("ApplicationTool", "application_tool.js"),
        ("ApprovalTool", "approval_tool.js"),
        ("RiskModelTool", "risk_model_tool.js"),
    ]

    lambda_arns = {}

    for function_name, js_file in functions:
        arn = deploy_lambda(lambda_client, function_name, js_file, role_arn)
        if arn:
            lambda_arns[function_name] = arn
        print()
        # デプロイ間の小さな遅延
        time.sleep(1)

    # 設定を保存
    if lambda_arns:
        save_config(lambda_arns)

    print("=" * 70)
    print(f"\n✅ Deployment complete! {len(lambda_arns)}/3 functions deployed.")
    print("\nLambda ARNs have been saved to config.json")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
