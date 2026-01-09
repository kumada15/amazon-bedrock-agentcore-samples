#!/bin/bash

set -e
set -o pipefail

# ----- Config -----
BUCKET_NAME=${1:-customersupport}
INFRA_STACK_NAME=${2:-CustomerSupportStackInfra}
COGNITO_STACK_NAME=${3:-CustomerSupportStackCognito}
REGION=$(aws configure get region || echo "${AWS_DEFAULT_REGION:-us-east-1}")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FULL_BUCKET_NAME="${BUCKET_NAME}-${ACCOUNT_ID}"
ZIP_FILE="lambda.zip"
S3_KEY="lambda.zip"
if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
    echo "エラー: $ACCOUNT_ID"
    exit 1
fi

# ----- Confirm Deletion -----
read -p "⚠️ スタック '$INFRA_STACK_NAME'、'$COGNITO_STACK_NAME' を削除し、S3 をクリーンアップしてもよろしいですか？ (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "❌ クリーンアップがキャンセルされました。"
  exit 1
fi

# ----- 1. Delete CloudFormation stacks -----
echo "🧨 スタックを削除中: $INFRA_STACK_NAME..."
aws cloudformation delete-stack --stack-name "$INFRA_STACK_NAME" --region "$REGION"
echo "⏳ $INFRA_STACK_NAME の削除を待機中..."
aws cloudformation wait stack-delete-complete --stack-name "$INFRA_STACK_NAME" --region "$REGION"
echo "✅ スタック $INFRA_STACK_NAME を削除しました。"

echo "🧨 スタックを削除中: $COGNITO_STACK_NAME..."
aws cloudformation delete-stack --stack-name "$COGNITO_STACK_NAME" --region "$REGION"
echo "⏳ $COGNITO_STACK_NAME の削除を待機中..."
aws cloudformation wait stack-delete-complete --stack-name "$COGNITO_STACK_NAME" --region "$REGION"
echo "✅ スタック $COGNITO_STACK_NAME を削除しました。"

# ----- 2. Delete zip file from S3 -----
echo "🧹 s3://$FULL_BUCKET_NAME の全コンテンツを削除中..."
aws s3 rm "s3://$FULL_BUCKET_NAME" --recursive || echo "⚠️ バケットのクリーンアップに失敗したか、既に空です。"

# ----- 3. Optionally delete the bucket -----
read -p "🪣 バケット '$FULL_BUCKET_NAME' を削除しますか？ (y/N): " delete_bucket
if [[ "$delete_bucket" == "y" || "$delete_bucket" == "Y" ]]; then
  echo "🚮 バケット $FULL_BUCKET_NAME を削除中..."
  aws s3 rb "s3://$FULL_BUCKET_NAME" --force
  echo "✅ バケットを削除しました。"
else
  echo "🪣 バケットを保持: $FULL_BUCKET_NAME"
fi

# ----- 4. Clean up local zip file -----
echo "🗑️ ローカルファイル $ZIP_FILE を削除中..."
rm -f "$ZIP_FILE"

# ----- 5. Delete Knowledge Base -----

echo "🗑️ ナレッジベースを削除中"
uv run python prerequisite/knowledge_base.py --mode delete

echo "✅ クリーンアップが完了しました。"