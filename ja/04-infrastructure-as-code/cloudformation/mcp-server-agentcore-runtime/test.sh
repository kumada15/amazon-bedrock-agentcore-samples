#!/bin/bash
# Streamlined testing script for MCP Server

set -e

STACK_NAME="${1:-mcp-server-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "MCP Server テストスクリプト"
echo "=========================================="
echo "スタック名: $STACK_NAME"
echo "リージョン: $REGION"
echo ""

# Get stack outputs
echo "📋 スタック設定を取得しています..."
CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolClientId`].OutputValue' \
  --output text \
  --region "$REGION")

AGENT_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerRuntimeArn`].OutputValue' \
  --output text \
  --region "$REGION")

if [ -z "$CLIENT_ID" ] || [ -z "$AGENT_ARN" ]; then
  echo "❌ エラー: スタック出力を取得できませんでした"
  echo "   スタック '$STACK_NAME' がリージョン '$REGION' に存在することを確認してください"
  exit 1
fi

echo "✓ 設定を取得しました"
echo ""

# Get authentication token
echo "🔐 認証トークンを取得しています..."
TOKEN_OUTPUT=$(python get_token.py "$CLIENT_ID" testuser MyPassword123! "$REGION" 2>&1)

# Extract token from output (it's the line after "Access Token:")
JWT_TOKEN=$(echo "$TOKEN_OUTPUT" | grep -A 1 "Access Token:" | tail -n 1 | tr -d '[:space:]')

if [ -z "$JWT_TOKEN" ]; then
  echo "❌ エラー: 認証トークンを取得できませんでした"
  echo "$TOKEN_OUTPUT"
  exit 1
fi

echo "✓ 認証が成功しました"
echo ""

# Test MCP server
echo "🧪 MCP サーバーをテストしています..."
echo ""
python test_mcp_server.py "$AGENT_ARN" "$JWT_TOKEN" "$REGION"

echo ""
echo "=========================================="
echo "✅ テスト完了！"
echo "=========================================="
