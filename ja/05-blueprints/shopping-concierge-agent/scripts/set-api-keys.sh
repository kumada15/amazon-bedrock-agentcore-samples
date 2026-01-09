#!/bin/bash

# Script to set API keys in AWS Systems Manager Parameter Store
# Usage: ./scripts/set-api-keys.sh

REGION="us-east-1"

echo "🔑 AWS Systems Manager Parameter Store に API キーを設定しています..."
echo ""

# SERP API Key (Product Search)
read -p "SERP API キーを入力してください (スキップするには Enter を押してください): " SERP_KEY
if [ ! -z "$SERP_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/shopping/serp-api-key" \
    --value "$SERP_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ SERP API キーを設定しました"
fi

echo ""
echo "🎉 API キーの設定が完了しました！"
echo ""
echo "注意: キーを設定した後、MCP サーバーを再デプロイする必要があります:"
echo "  cd infrastructure/mcp-servers && cdk deploy ShoppingStack"
