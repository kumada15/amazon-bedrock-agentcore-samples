#!/bin/bash

# Basic Agent Runtime CloudFormation スタック用デプロイスクリプト
# このスクリプトは、シンプルな Strands エージェントを持つ基本的な AgentCore Runtime をデプロイします

set -e

# 設定
STACK_NAME="${1:-basic-agent-demo}"
REGION="${2:-us-west-2}"
TEMPLATE_FILE="template.yaml"

echo "=========================================="
echo "Basic Agent Runtime をデプロイしています"
echo "=========================================="
echo "スタック名: $STACK_NAME"
echo "リージョン: $REGION"
echo "=========================================="

# テンプレートファイルが存在するか確認
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "エラー: テンプレートファイル '$TEMPLATE_FILE' が見つかりません！"
    exit 1
fi

# CloudFormation スタックをデプロイ
echo ""
echo "CloudFormation スタックを作成しています..."
aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://"$TEMPLATE_FILE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ スタックの作成が正常に開始されました！"
    echo ""
    echo "スタックの作成完了を待っています..."
    echo "約 10-15 分かかります..."
    echo ""
    
    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✓ スタックが正常にデプロイされました！"
        echo "=========================================="
        echo ""
        echo "スタック出力:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs' \
            --output table \
            --region "$REGION"
        echo ""
        echo "Agent Runtime ID:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeId`].OutputValue' \
            --output text \
            --region "$REGION"
        echo ""
        echo "このスタックを削除するには:"
        echo "  ./cleanup.sh $STACK_NAME $REGION"
        echo ""
    else
        echo ""
        echo "✗ スタックの作成に失敗したか、タイムアウトしました"
        echo "詳細は CloudFormation コンソールを確認してください"
        exit 1
    fi
else
    echo ""
    echo "✗ スタックの作成開始に失敗しました"
    exit 1
fi
