#!/bin/bash
set -e

# Deploy script for the Insurance API Lambda function

# Check for AWS CLI
if ! command -v aws &> /dev/null
then
    echo "AWS CLI がインストールされていません。先にインストールしてください。"
    exit 1
fi

# Check for SAM CLI
if ! command -v sam &> /dev/null
then
    echo "AWS SAM CLI がインストールされていません。先にインストールしてください。"
    exit 1
fi

# Get AWS account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
    echo "エラー: $ACCOUNT_ID"
    exit 1
fi

REGION=$(aws configure get region)

# Set variables
STAGE=${1:-dev}  # Default to dev if not specified
STACK_NAME="insurance-api-$STAGE"
S3_BUCKET="insurance-api-$STAGE-$ACCOUNT_ID-$REGION"

echo "=== Insurance API デプロイ ==="
echo "ステージ: $STAGE"
echo "アカウント ID: $ACCOUNT_ID"
echo "リージョン: $REGION"
echo "スタック名: $STACK_NAME"
echo "S3 バケット: $S3_BUCKET"

# Create S3 bucket if it doesn't exist
if ! aws s3api head-bucket --bucket $S3_BUCKET 2>/dev/null; then
    echo "S3 バケットを作成中: $S3_BUCKET"
    aws s3 mb s3://$S3_BUCKET
fi

# Create a build directory for packaging
echo "ビルドパッケージを作成中..."
mkdir -p build

# Copy necessary files
cp -r ../local_insurance_api build/
cp ../lambda_function.py build/
cp template.yaml build/

# Create a data directory in build and copy data files
mkdir -p build/data
cp ../local_insurance_api/data/*.json build/data/

# Install dependencies in the build directory
echo "依存関係をインストール中..."
pip install -r ../local_insurance_api/requirements.txt -t build/

# Package the application
echo "アプリケーションをパッケージング中..."
sam package \
    --template-file build/template.yaml \
    --output-template-file build/packaged.yaml \
    --s3-bucket $S3_BUCKET

# Deploy the application
echo "アプリケーションをデプロイ中..."
sam deploy \
    --template-file build/packaged.yaml \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameter-overrides EnvironmentType="$STAGE"

echo "=== デプロイ完了 ==="
