#!/bin/bash

# Cleanup script for Multi-Agent Runtime CloudFormation stack
# This script deletes the CloudFormation stack and all associated resources

set -e

# Configuration
STACK_NAME="${1:-multi-agent-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "Multi-Agent Runtime をクリーンアップしています"
echo "=========================================="
echo "スタック名: $STACK_NAME"
echo "リージョン: $REGION"
echo "=========================================="

# Confirm deletion
read -p "スタック '$STACK_NAME' を削除しますか？ (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "クリーンアップがキャンセルされました。"
    exit 0
fi

echo ""
echo "CloudFormation スタックを削除しています..."
aws cloudformation delete-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ スタックの削除が正常に開始されました！"
    echo ""
    echo "スタックの削除完了を待っています..."
    echo "数分かかる場合があります..."
    echo ""
    
    aws cloudformation wait stack-delete-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✓ スタックが正常に削除されました！"
        echo "=========================================="
        echo ""
        echo "すべてのリソースがクリーンアップされました。"
        echo ""
    else
        echo ""
        echo "✗ スタックの削除に失敗したか、タイムアウトしました"
        echo "詳細は CloudFormation コンソールを確認してください"
        exit 1
    fi
else
    echo ""
    echo "✗ スタックの削除開始に失敗しました"
    exit 1
fi
