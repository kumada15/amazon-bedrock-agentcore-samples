#!/bin/bash
# Synchronize gateway targets after MCP deployment
set -e

# Set default region if not set
export AWS_REGION=${AWS_REGION:-us-east-1}
DEPLOYMENT_ID=$(node -p "require('./deployment-config.json').deploymentId")

echo "🔄 デプロイメント $DEPLOYMENT_ID の Gateway ターゲットを同期しています"

# Get gateway ID dynamically based on deployment ID
GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways \
  --query "items[?contains(name, 'agentstack-${DEPLOYMENT_ID}')].gatewayId | [0]" \
  --output text)

if [ -z "$GATEWAY_ID" ] || [ "$GATEWAY_ID" == "None" ]; then
  echo "❌ デプロイメント $DEPLOYMENT_ID の Gateway が見つかりません"
  exit 1
fi

echo "Gateway を検出: $GATEWAY_ID"

# Get all target IDs
TARGET_IDS=$(aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier "$GATEWAY_ID" \
  --query 'items[].targetId' \
  --output text)

echo "ターゲットを検出: $TARGET_IDS"

# Sync each target individually (API limit is 1 per call)
for TARGET_ID in $TARGET_IDS; do
  echo "ターゲットを同期中: $TARGET_ID"
  aws bedrock-agentcore-control synchronize-gateway-targets \
    --gateway-identifier "$GATEWAY_ID" \
    --target-id-list "[\"$TARGET_ID\"]" \
    --no-cli-pager
done

echo "同期を開始しました。完了を待っています..."

# Wait for all targets to be READY
for i in {1..30}; do
  sleep 10

  # Check if all are READY
  NOT_READY=$(aws bedrock-agentcore-control list-gateway-targets \
    --gateway-identifier "$GATEWAY_ID" \
    --query 'items[?status!=`READY`].name' \
    --output text)

  if [ -z "$NOT_READY" ]; then
    echo "✅ すべてのターゲットが同期されました！"
    exit 0
  fi

  echo "待機中... (準備未完了: $NOT_READY)"
done

echo "⚠️ 同期を待機中にタイムアウトしました"
exit 1
