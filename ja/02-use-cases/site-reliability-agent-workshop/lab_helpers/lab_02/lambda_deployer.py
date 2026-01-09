"""
Lab 02: Lambda 関数のデプロイと設定ヘルパー

処理内容:
1. ECR リポジトリの作成
2. IAM 実行ロールの作成
3. 必要なポリシーのアタッチ
4. すべての設定を Parameter Store に保存

マルチアカウント対応: 各デプロイは独自の値を保存します。
"""

import boto3
import json
from lab_helpers.constants import (
    PARAMETER_PATHS,
    LAMBDA_CONFIG,
    ECR_CONFIG,
    IAM_POLICIES,
    BEDROCK_CONFIG,
)
from lab_helpers.parameter_store import put_parameter, get_parameters_by_path, store_workshop_metadata
from lab_helpers.config import MODEL_ID, AWS_REGION


def create_ecr_repository(repository_name, region_name=None):
    """
    ECR リポジトリを作成（既存の場合はそれを返す）

    Args:
        repository_name: リポジトリ名（例: "aiml301-diagnostic-agent"）
        region_name: AWS リージョン

    Returns:
        ECR リポジトリ URI
    """
    if region_name is None:
        region_name = AWS_REGION

    ecr = boto3.client('ecr', region_name=region_name)
    account_id = boto3.client('sts', region_name=region_name).get_caller_identity()['Account']

    try:
        # リポジトリが存在するか確認
        response = ecr.describe_repositories(repositoryNames=[repository_name])
        repo_uri = response['repositories'][0]['repositoryUri']
        print(f"✓ ECR リポジトリは既に存在します: {repo_uri}")
        return repo_uri
    except ecr.exceptions.RepositoryNotFoundException:
        # 新しいリポジトリを作成
        response = ecr.create_repository(repositoryName=repository_name)
        repo_uri = response['repository']['repositoryUri']
        print(f"✓ ECR リポジトリを作成しました: {repo_uri}")
        return repo_uri


def create_lambda_execution_role(role_name, region_name=None):
    """
    必要なポリシーを持つ Lambda 実行ロールを作成

    Args:
        role_name: IAM ロール名（例: "aiml301-diagnostic-lambda-role"）
        region_name: AWS リージョン

    Returns:
        ロール ARN
    """
    if region_name is None:
        region_name = AWS_REGION

    iam = boto3.client('iam', region_name=region_name)

    # 信頼ポリシー: Lambda サービスがこのロールを引き受けることを許可
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }

    try:
        # ロールが存在するか確認
        role = iam.get_role(RoleName=role_name)
        role_arn = role['Role']['Arn']
        print(f"✓ IAM ロールは既に存在します: {role_arn}")
    except iam.exceptions.NoSuchEntityException:
        # 新しいロールを作成
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Lambda execution role for AIML301 workshop agent"
        )
        role_arn = role['Role']['Arn']
        print(f"✓ IAM ロールを作成しました: {role_arn}")

    # CloudWatch Logs ポリシーをアタッチ（Lambda 基本実行）
    try:
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=IAM_POLICIES["cloudwatch_logs_policy"]
        )
        print(f"✓ CloudWatch Logs ポリシーをアタッチしました")
    except Exception as e:
        print(f"⚠ CloudWatch ポリシー (既にアタッチ済みの可能性があります): {e}")

    # Bedrock InvokeModel ポリシーをアタッチ（Strands エージェント用のすべての Bedrock アクションを含む）
    bedrock_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                    "aws-marketplace:Subscribe",
                    "aws-marketplace:ViewSubscriptions"
                ],
                "Resource": "*"
            }
        ]
    }

    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockInvokePolicy",
            PolicyDocument=json.dumps(bedrock_policy)
        )
        print(f"✓ Bedrock InvokeModel ポリシーをアタッチしました")
    except Exception as e:
        print(f"⚠ Bedrock ポリシーの更新: {e}")

    return role_arn


def prepare_lambda_build_context(handler_code, build_dir="lambda_diagnostic_agent"):
    """
    Dockerfile と requirements.txt を含む Lambda ビルドコンテキストを作成

    Args:
        handler_code: app.py 用の Python コード（lambda_handler 関数）
        build_dir: ビルドコンテキストを作成するディレクトリ
    """
    import os

    # ビルドディレクトリを作成
    os.makedirs(build_dir, exist_ok=True)

    # 定数から Dockerfile を生成
    dockerfile_content = f"""FROM --platform=linux/amd64 {ECR_CONFIG['base_image']}

# Copy requirements (to task root)
COPY requirements.txt ${{LAMBDA_TASK_ROOT}}/

# Install dependencies
RUN pip install --no-cache-dir -r ${{LAMBDA_TASK_ROOT}}/requirements.txt

# Copy Lambda handler and helper modules to task root
COPY app.py ${{LAMBDA_TASK_ROOT}}/
COPY lab_helpers ${{LAMBDA_TASK_ROOT}}/lab_helpers

# Set handler
CMD ["app.lambda_handler"]
"""

    # Strands エージェントデプロイ用の requirements
    # ツールオーケストレーション用の bedrock-agentcore と strands-agents を含む
    requirements = """strands-agents==1.12.0
bedrock-agentcore>=0.1.0
bedrock-agentcore-starter-toolkit>=0.1.24
boto3==1.40.65
botocore==1.40.65
pydantic>=2.0
requests>=2.30
"""

    # ファイルを書き込み
    with open(f"{build_dir}/Dockerfile", "w") as f:
        f.write(dockerfile_content)

    with open(f"{build_dir}/requirements.txt", "w") as f:
        f.write(requirements)

    with open(f"{build_dir}/app.py", "w") as f:
        f.write(handler_code)

    return {
        "build_dir": build_dir,
        "dockerfile": f"{build_dir}/Dockerfile",
        "requirements": f"{build_dir}/requirements.txt",
        "handler": f"{build_dir}/app.py"
    }


def setup_lab_02_infrastructure(handler_code, region_name=None):
    """
    Lab 02 インフラストラクチャの完全セットアップ:
    1. Lambda 仕様の表示
    2. Lambda ビルドコンテキストの作成（Dockerfile、requirements.txt、app.py）
    3. ECR リポジトリの作成
    4. Lambda 実行ロールの作成
    5. すべての値を Parameter Store に保存

    Args:
        handler_code: Lambda ハンドラー（app.py）用の Python コード
        region_name: AWS リージョン（None の場合は config.AWS_REGION を使用）

    Returns:
        作成されたすべてのリソースを含む辞書
    """
    if region_name is None:
        region_name = AWS_REGION

    print("=" * 70)
    print("LAB 02 インフラストラクチャをセットアップ中")
    print("=" * 70)
    print()

    # Lambda 仕様を表示
    print("Lambda 関数の仕様:")
    print(f"  メモリ: {LAMBDA_CONFIG['memory_size']}MB (Strands エージェント用に 2GB)")
    print(f"  タイムアウト: {LAMBDA_CONFIG['timeout']} 秒")
    print(f"  ベースイメージ: {ECR_CONFIG['base_image']}")
    print()

    # Lambda ビルドコンテキストを準備（Dockerfile、requirements.txt、app.py を作成）
    print("Lambda ビルドコンテキストを準備中...")
    build_context = prepare_lambda_build_context(handler_code)
    print(f"✓ ビルドディレクトリを作成しました: {build_context['build_dir']}")
    print(f"✓ Dockerfile を作成しました")
    print(f"✓ requirements.txt を作成しました")
    print(f"✓ app.py (Lambda ハンドラー) を作成しました")
    print()

    # アカウント ID を取得
    sts = boto3.client('sts', region_name=region_name)
    account_id = sts.get_caller_identity()['Account']
    print(f"AWS アカウント: {account_id}")
    print(f"AWS リージョン: {region_name}")
    print()

    # ワークショップメタデータを保存
    print("ワークショップメタデータを保存中...")
    store_workshop_metadata(account_id, region_name, region_name)
    print()

    # ECR リポジトリを作成
    print("ECR リポジトリをセットアップ中...")
    repository_name = "aiml301-diagnostic-agent"
    ecr_repository_uri = create_ecr_repository(repository_name, region_name)
    print()

    # Lambda 実行ロールを作成
    print("Lambda 実行ロールをセットアップ中...")
    role_name = "aiml301-diagnostic-lambda-role"
    lambda_role_arn = create_lambda_execution_role(role_name, region_name)
    print()

    # 設定を Parameter Store に保存
    print("Parameter Store に設定を保存中...")
    put_parameter(
        PARAMETER_PATHS["lab_02"]["ecr_repository_uri"],
        ecr_repository_uri,
        description="ECR repository URI for Lab 02 diagnostic agent",
        region_name=region_name
    )
    put_parameter(
        PARAMETER_PATHS["lab_02"]["ecr_repository_name"],
        repository_name,
        description="ECR repository name for Lab 02",
        region_name=region_name
    )
    put_parameter(
        PARAMETER_PATHS["lab_02"]["lambda_role_arn"],
        lambda_role_arn,
        description="Lambda execution role ARN for Lab 02",
        region_name=region_name
    )
    print()

    # 設定を返す
    config = {
        "account_id": account_id,
        "region": region_name,
        "ecr_repository_uri": ecr_repository_uri,
        "ecr_repository_name": repository_name,
        "lambda_role_arn": lambda_role_arn,
        "lambda_memory": LAMBDA_CONFIG["memory_size"],
        "lambda_timeout": LAMBDA_CONFIG["timeout"],
    }

    print("=" * 70)
    print("LAB 02 インフラストラクチャのセットアップが完了しました")
    print("=" * 70)
    print()
    print("設定サマリー:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()
    print("✓ すべての値が Parameter Store に保存されました")
    print("✓ Lambda コンテナデプロイの準備が完了しました")
    print()

    return config


def get_lab_02_deployment_instructions(config):
    """
    Lambda デプロイ用の Docker および AWS CLI コマンドを生成

    Args:
        config: setup_lab_02_infrastructure からの設定辞書

    Returns:
        デプロイ手順を含むフォーマット済み文字列
    """
    ecr_uri = config["ecr_repository_uri"]
    role_arn = config["lambda_role_arn"]
    region = config["region"]

    instructions = f"""
╔════════════════════════════════════════════════════════════════════╗
║        LAB 02: DOCKER BUILD & LAMBDA DEPLOYMENT STEPS             ║
╚════════════════════════════════════════════════════════════════════╝

📦 DOCKER BUILD (Run locally or in CI/CD):

1. Build Docker image:
   docker build --provenance=false -t aiml301-diagnostic-agent:latest ./lambda_diagnostic_agent/

2. Authenticate Docker to ECR:
   aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {ecr_uri.rsplit('/', 1)[0]}

3. Tag image:
   docker tag aiml301-diagnostic-agent:latest {ecr_uri}

4. Push to ECR:
   docker push {ecr_uri}

🚀 LAMBDA DEPLOYMENT (Run after Docker image is pushed):

5. Create Lambda function:
   aws lambda create-function \\
     --function-name aiml301-diagnostic-agent \\
     --role {role_arn} \\
     --code ImageUri={ecr_uri} \\
     --package-type Image \\
     --timeout {LAMBDA_CONFIG['timeout']} \\
     --memory-size {LAMBDA_CONFIG['memory_size']} \\
     --region {region}

6. Update Lambda environment variables (optional):
   aws lambda update-function-configuration \\
     --function-name aiml301-diagnostic-agent \\
     --environment Variables={{MODEL_ID={MODEL_ID},REGION={region}}} \\
     --region {region}

📝 NOTES:
   - Image URI: {ecr_uri}
   - Role ARN: {role_arn}
   - Memory: {LAMBDA_CONFIG['memory_size']}MB (2GB for Strands agent)
   - Timeout: {LAMBDA_CONFIG['timeout']}s
   - All values are stored in Parameter Store at: /aiml301/lab-02/*
"""

    return instructions


def show_lambda_config():
    """Lambda 設定定数を表示"""
    print("Lambda 設定定数:")
    print(f"  メモリ: {LAMBDA_CONFIG['memory_size']}MB")
    print(f"  タイムアウト: {LAMBDA_CONFIG['timeout']} 秒")
    print(f"  一時ストレージ: {LAMBDA_CONFIG['ephemeral_storage']}MB")
    print()
    print("ベースイメージ:")
    print(f"  {ECR_CONFIG['base_image']}")
    print()
    print("モデル ID (config.py より):")
    print(f"  {MODEL_ID}")


# ============================================================================
# ZIP デプロイメントサポート（Docker の VPC 対応代替手段）
# ============================================================================

def get_zip_deployment_instructions(config):
    """
    ZIP ベースの Lambda デプロイ手順を生成

    Args:
        config: 設定辞書

    Returns:
        ZIP デプロイ手順を含むフォーマット済み文字列
    """
    region = config["region"]
    role_arn = config["lambda_role_arn"]

    instructions = f"""
╔════════════════════════════════════════════════════════════════════╗
║          LAB 02: ZIP-BASED LAMBDA DEPLOYMENT (VPC-Friendly)       ║
╚════════════════════════════════════════════════════════════════════╝

📦 ZIP PACKAGE CREATION & DEPLOYMENT:

ONE-LINE DEPLOYMENT (recommended):
   bash lab_helpers/lab_02/deploy.sh

This handles everything:
   ✓ Creates IAM role
   ✓ Installs dependencies for Python 3.11
   ✓ Packages lib/ and lab_helpers/
   ✓ Creates ZIP (direct upload if <50MB, S3 if larger)
   ✓ Deploys Lambda function
   ✓ Saves configuration to Parameter Store

ALTERNATIVE: Using Python packager directly:
   from lab_helpers.lab_02.lambda_packager import setup_lambda_zip_deployment

   handler_code = '''... your app.py code ...'''
   requirements_content = '''... pip requirements ...'''

   result = setup_lambda_zip_deployment(handler_code, requirements_content)

🚀 ADVANTAGES OVER DOCKER:

✓ Works in SageMaker VPC mode (no Docker daemon needed)
✓ Faster deployment (8 min vs 12 min with Docker)
✓ No external network access required
✓ Simpler setup (Python + pip only)
✓ Package size: ~30-35 MB (well under 250 MB limit)

📊 DEPLOYMENT OPTIONS:

Size < 50 MB:  Direct ZIP upload to Lambda
Size > 50 MB:  S3 upload → Lambda
Our package:   ~30-35 MB (uses direct upload by default)

📝 CONFIGURATION:

   - Role ARN: {role_arn}
   - Region: {region}
   - Memory: {LAMBDA_CONFIG['memory_size']}MB
   - Timeout: {LAMBDA_CONFIG['timeout']}s
   - All values stored in Parameter Store at: /aiml301/lab-02/*
"""

    return instructions


def show_deployment_methods():
    """利用可能なデプロイ方式とその特性を表示"""
    from lab_helpers.constants import DEPLOYMENT_METHODS

    print("\n" + "=" * 70)
    print("LAMBDA デプロイ方式")
    print("=" * 70)

    for method_name, method_info in DEPLOYMENT_METHODS.items():
        print(f"\n{method_name.upper()}:")
        print(f"  説明: {method_info['description']}")
        print(f"  必要なもの: {', '.join(method_info['requires'])}")
        print(f"  VPC 互換性: {'✅ あり' if method_info['vpc_compatible'] else '❌ なし'}")
        print(f"  サイズ制限: {method_info['size_limit']}")
