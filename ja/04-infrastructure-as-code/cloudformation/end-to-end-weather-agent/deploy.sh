#!/bin/bash

# Deploy script for Weather Agent Runtime CloudFormation stack
# This script deploys a complete weather agent with browser, code interpreter, and memory

set -e

# Configuration
STACK_NAME="${1:-weather-agent-demo}"
REGION="${2:-us-west-2}"
TEMPLATE_FILE="end-to-end-weather-agent.yaml"

echo "=========================================="
echo "Weather Agent Runtime をデプロイしています"
echo "=========================================="
echo "スタック名: $STACK_NAME"
echo "リージョン: $REGION"
echo "=========================================="

# Check if template file exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "エラー: テンプレートファイル '$TEMPLATE_FILE' が見つかりません！"
    exit 1
fi

# Deploy the CloudFormation stack
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
    echo "約 15-20 分かかります..."
    echo "（Docker イメージのビルド、Browser、Code Interpreter、Memory を使用したエージェントのデプロイ）"
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
        echo "Browser ID:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`BrowserId`].OutputValue' \
            --output text \
            --region "$REGION"
        echo ""
        echo "Code Interpreter ID:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`CodeInterpreterId`].OutputValue' \
            --output text \
            --region "$REGION"
        echo ""
        echo "Memory ID:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`MemoryId`].OutputValue' \
            --output text \
            --region "$REGION"
        echo ""
        echo "Results Bucket:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucket`].OutputValue' \
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
