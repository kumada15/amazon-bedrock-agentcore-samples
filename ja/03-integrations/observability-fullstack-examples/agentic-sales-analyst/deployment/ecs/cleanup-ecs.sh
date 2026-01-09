#!/bin/bash
set -e

PROJECT_NAME=${PROJECT_NAME:-agentic-sales-analyst}
REGION=${AWS_REGION:-ap-southeast-2}

echo "🗑️  ECS 固有リソースをクリーンアップ中"
echo "プロジェクト: $PROJECT_NAME"
echo "リージョン: $REGION"

wait_for_delete() {
    local stack_name=$1
    echo "⏳ スタック $stack_name の削除を待機中..."
    aws cloudformation wait stack-delete-complete \
        --stack-name $stack_name \
        --region $REGION 2>/dev/null || true
    echo "✅ スタック $stack_name を削除しました"
}

empty_s3_buckets() {
    local stack_name=$1
    echo "🪣 スタック $stack_name の S3 バケットを空にしています..."

    # スタックからすべての S3 バケットを取得
    BUCKET_NAMES=$(aws cloudformation describe-stack-resources \
        --stack-name $stack_name \
        --query 'StackResources[?ResourceType==`AWS::S3::Bucket`].PhysicalResourceId' \
        --output text \
        --region $REGION 2>/dev/null || echo "")

    if [ -n "$BUCKET_NAMES" ]; then
        for bucket in $BUCKET_NAMES; do
            if [ -n "$bucket" ] && [ "$bucket" != "None" ]; then
                echo "バケットを空にしています: $bucket"
                aws s3 rm s3://$bucket --recursive --region $REGION 2>/dev/null || true
                echo "✅ バケット $bucket を空にしました"
            fi
        done
    else
        echo "スタック $stack_name に S3 バケットが見つかりません"
    fi
}

echo ""
echo "ECS サービスを削除中..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-ecs-service \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-ecs-service

echo ""
echo "ECS クラスターを削除する前に S3 バケットを空にしています..."
empty_s3_buckets ${PROJECT_NAME}-ecs-cluster

echo ""
echo "ECS クラスターを削除中..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-ecs-cluster \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-ecs-cluster

echo ""
echo "✅ ECS のクリーンアップが完了しました！"
echo ""
echo "共有インフラストラクチャ（ネットワーク、IAM、ECR）を削除するには:"
echo "  cd .."
echo "  ./cleanup-infrastructure.sh"
