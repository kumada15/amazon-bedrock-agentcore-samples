#!/bin/bash

set -e
set -o pipefail

# ----- Config -----
BUCKET_NAME=${1:-customersupport}
INFRA_STACK_NAME=${2:-CustomerSupportStackInfra}
COGNITO_STACK_NAME=${3:-CustomerSupportStackCognito}
INFRA_TEMPLATE_FILE="prerequisite/infrastructure.yaml"
COGNITO_TEMPLATE_FILE="prerequisite/cognito.yaml"
REGION=$(aws configure get region || echo "${AWS_DEFAULT_REGION:-us-east-1}")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FULL_BUCKET_NAME="${BUCKET_NAME}-${ACCOUNT_ID}"
ZIP_FILE="lambda.zip"
LAMBDA_SRC="prerequisite/lambda/python"
S3_KEY="${ZIP_FILE}"

if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
    echo "エラー: $ACCOUNT_ID"
    exit 1
fi


# ----- 1. Create S3 bucket -----
echo "🪣 S3 バケットを使用: $FULL_BUCKET_NAME"
if [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket \
    --bucket "$FULL_BUCKET_NAME" \
    2>/dev/null || echo "ℹ️ バケットは既に存在するか、あなたが所有しています。"
else
  aws s3api create-bucket \
    --bucket "$FULL_BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" \
    2>/dev/null || echo "ℹ️ バケットは既に存在するか、あなたが所有しています。"
fi

# ----- 2. Zip Lambda code -----
echo "📦 $LAMBDA_SRC の内容を $ZIP_FILE に圧縮中..."
cd "$LAMBDA_SRC"
zip -r "../../../$ZIP_FILE" . > /dev/null
cd - > /dev/null

# ----- 3. Upload to S3 -----
echo "☁️ $ZIP_FILE を s3://$FULL_BUCKET_NAME/$S3_KEY にアップロード中..."
aws s3 cp "$ZIP_FILE" "s3://$FULL_BUCKET_NAME/$S3_KEY"

# ----- 4. Deploy CloudFormation -----
deploy_stack() {
  set +e

  local stack_name=$1
  local template_file=$2
  shift 2
  local params=("$@")

  echo "🚀 CloudFormation スタックをデプロイ中: $stack_name"

  output=$(aws cloudformation deploy \
    --stack-name "$stack_name" \
    --template-file "$template_file" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    "${params[@]}" 2>&1)

  exit_code=$?

  echo "$output"

  if [ $exit_code -ne 0 ]; then
    if echo "$output" | grep -qi "No changes to deploy"; then
      echo "ℹ️ スタック $stack_name に更新はありません、続行します..."
      return 0
    else
      echo "❌ スタック $stack_name のデプロイ中にエラー:"
      echo "$output"
      return $exit_code
    fi
  else
    echo "✅ スタック $stack_name を正常にデプロイしました。"
    return 0
  fi
}

# ----- Run both stacks -----
echo "🔧 インフラストラクチャスタックのデプロイを開始中..."
deploy_stack "$INFRA_STACK_NAME" "$INFRA_TEMPLATE_FILE" --parameter-overrides LambdaS3Bucket="$FULL_BUCKET_NAME" LambdaS3Key="$S3_KEY"
infra_exit_code=$?

echo "🔧 Cognito スタックのデプロイを開始中..."
deploy_stack "$COGNITO_STACK_NAME" "$COGNITO_TEMPLATE_FILE"
cognito_exit_code=$?

echo "🔍 SSM からナレッジベースとデータソース ID を取得中..."

# ----- 6. Create Knowledge Base -----

# Export region for Python script
export AWS_DEFAULT_REGION="$REGION"
uv run python prerequisite/knowledge_base.py --mode create

echo "✅ デプロイが完了しました。"
