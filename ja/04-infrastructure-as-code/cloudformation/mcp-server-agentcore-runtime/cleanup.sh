#!/bin/bash
# Cleanup script for MCP Server deployment

set -e

STACK_NAME="${1:-mcp-server-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "MCP Server クリーンアップスクリプト"
echo "=========================================="
echo "スタック名: $STACK_NAME"
echo "リージョン: $REGION"
echo ""

read -p "⚠️  すべてのリソースが削除されます。続行しますか？ (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "クリーンアップがキャンセルされました"
    exit 0
fi

echo ""
echo "🗑️  CloudFormation スタックを削除しています..."
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "✓ スタックの削除が開始されました"
echo ""
echo "⏳ スタックの削除完了を待っています..."
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo ""
echo "=========================================="
echo "✅ クリーンアップ完了！"
echo "=========================================="
echo ""
echo "すべてのリソースが削除されました。"
echo ""
