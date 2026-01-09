#!/bin/bash
# Streamlined deployment script for MCP Server on AgentCore Runtime

set -e

STACK_NAME="${1:-mcp-server-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "MCP Server デプロイスクリプト"
echo "=========================================="
echo "スタック名: $STACK_NAME"
echo "リージョン: $REGION"
echo ""

# Deploy CloudFormation stack
echo "📦 CloudFormation スタックをデプロイしています..."
aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body file://mcp-server-template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"

echo "✓ スタックの作成が開始されました"
echo ""

# Wait for stack to complete
echo "⏳ スタックの完了を待っています（約 10-15 分かかります）..."
aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "✓ スタックのデプロイが完了しました！"
echo ""

# Get stack outputs
echo "📋 スタック出力を取得しています..."
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

echo ""
echo "=========================================="
echo "✅ デプロイ完了！"
echo "=========================================="
echo ""
echo "スタック名: $STACK_NAME"
echo "リージョン: $REGION"
echo "Client ID: $CLIENT_ID"
echo "Agent ARN: $AGENT_ARN"
echo ""
echo "テスト認証情報:"
echo "  ユーザー名: testuser"
echo "  パスワード: MyPassword123!"
echo ""
echo "=========================================="
echo "次のステップ:"
echo "=========================================="
echo ""
echo "MCP サーバーをテスト:"
echo "  ./test.sh $STACK_NAME $REGION"
echo ""
