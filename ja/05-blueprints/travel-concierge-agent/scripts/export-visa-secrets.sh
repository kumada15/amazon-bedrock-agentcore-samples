#!/bin/bash
# Store Visa secrets in AWS Secrets Manager
# Usage: ./scripts/export-visa-secrets.sh

set -e

REGION="us-east-1"

echo "🔐 Visa シークレットを AWS Secrets Manager に保存しています..."
echo ""

# Prompt for Visa API credentials
read -p "Visa API キーを入力: " VISA_API_KEY
read -p "Visa 共有シークレットを入力: " VISA_SHARED_SECRET
read -p "Visa 暗号化 API キーを入力: " VISA_ENCRYPTION_API_KEY
read -p "Visa 暗号化共有シークレットを入力: " VISA_ENCRYPTION_SHARED_SECRET
read -p "Visa キー ID を入力: " VISA_KEY_ID

# Function to create or update secret
store_secret() {
  local secret_name=$1
  local secret_value=$2
  
  if aws secretsmanager describe-secret --secret-id "$secret_name" --region $REGION &>/dev/null; then
    aws secretsmanager put-secret-value \
      --secret-id "$secret_name" \
      --secret-string "$secret_value" \
      --region $REGION &>/dev/null
    echo "✅ 更新しました: $secret_name"
  else
    aws secretsmanager create-secret \
      --name "$secret_name" \
      --secret-string "$secret_value" \
      --region $REGION &>/dev/null
    echo "✅ 作成しました: $secret_name"
  fi
}

# Store API credentials
store_secret "visa/api-key" "$VISA_API_KEY"
store_secret "visa/shared-secret" "$VISA_SHARED_SECRET"
store_secret "visa/encryption-api-key" "$VISA_ENCRYPTION_API_KEY"
store_secret "visa/encryption-shared-secret" "$VISA_ENCRYPTION_SHARED_SECRET"
store_secret "visa/vic_key_id" "$VISA_KEY_ID"

# Store PEM certificates if they exist
if [ -f "./infrastructure/certs/server_mle_cert.pem" ]; then
  VISA_SERVER_MLE_CERT=$(cat ./infrastructure/certs/server_mle_cert.pem)
  store_secret "visa/server-mle-cert" "$VISA_SERVER_MLE_CERT"
else
  echo "⚠️  警告: ./infrastructure/certs/server_mle_cert.pem が見つかりません、スキップします"
fi

if [ -f "./infrastructure/certs/mle_private_cert.pem" ]; then
  VISA_MLE_PRIVATE_CERT=$(cat ./infrastructure/certs/mle_private_cert.pem)
  store_secret "visa/mle-private-cert" "$VISA_MLE_PRIVATE_CERT"
else
  echo "⚠️  警告: ./infrastructure/certs/mle_private_cert.pem が見つかりません、スキップします"
fi

echo ""
echo "🎉 Visa シークレットを AWS Secrets Manager に保存しました！"
echo ""
echo "次のステップ:"
echo "1. カートマネージャーをデプロイ: cd infrastructure/mcp-servers && cdk deploy CartStack"
