#!/bin/bash
set -e

PROJECT_NAME=${PROJECT_NAME:-agentic-sales-analyst}
REGION=${AWS_REGION:-ap-southeast-2}

echo "🗑️  共有インフラストラクチャをクリーンアップ中"
echo "プロジェクト: $PROJECT_NAME"
echo "リージョン: $REGION"
echo ""
echo "⚠️  警告: 以下が削除されます:"
echo "  - ECR リポジトリ（すべてのコンテナイメージを含む）"
echo "  - IAM ロール"
echo "  - VPC とネットワーク"
echo ""
read -p "本当によろしいですか？ (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "クリーンアップがキャンセルされました"
    exit 0
fi

wait_for_delete() {
    local stack_name=$1
    echo "⏳ スタック $stack_name の削除を待機中..."
    aws cloudformation wait stack-delete-complete \
        --stack-name $stack_name \
        --region $REGION 2>/dev/null || true
    echo "✅ スタック $stack_name を削除しました"
}

echo ""
echo "ECR リポジトリを空にしています..."
REPO_NAME="${PROJECT_NAME}"

# リポジトリが存在するかチェック
if aws ecr describe-repositories --repository-names $REPO_NAME --region $REGION >/dev/null 2>&1; then
    echo "$REPO_NAME からすべてのイメージを削除中..."

    # すべてのイメージ ID を取得して削除
    IMAGE_IDS=$(aws ecr list-images --repository-name $REPO_NAME --region $REGION --query 'imageIds' --output json)

    if [ "$IMAGE_IDS" != "[]" ] && [ -n "$IMAGE_IDS" ]; then
        echo "削除するイメージが見つかりました。すべて削除します..."
        echo "$IMAGE_IDS" | aws ecr batch-delete-image \
            --repository-name $REPO_NAME \
            --region $REGION \
            --image-ids file:///dev/stdin || true

        # 残りのイメージを削除（マニフェストリストの依存関係を処理）
        REMAINING_IDS=$(aws ecr list-images --repository-name $REPO_NAME --region $REGION --query 'imageIds' --output json 2>/dev/null || echo "[]")
        if [ "$REMAINING_IDS" != "[]" ] && [ -n "$REMAINING_IDS" ]; then
            echo "残りのイメージを削除中..."
            echo "$REMAINING_IDS" | aws ecr batch-delete-image \
                --repository-name $REPO_NAME \
                --region $REGION \
                --image-ids file:///dev/stdin || true
        fi

        echo "✅ $REPO_NAME からすべてのイメージを削除しました"
    else
        echo "$REPO_NAME にイメージが見つかりません"
    fi
else
    echo "リポジトリ $REPO_NAME は存在しません。イメージのクリーンアップをスキップします"
fi

echo ""
echo "ECR リポジトリを削除中..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-ecr \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-ecr

echo ""
echo "IAM ロールを削除中..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-iam \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-iam

echo ""
echo "ネットワークインフラストラクチャを削除中..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-network \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-network

echo ""
echo "✅ インフラストラクチャのクリーンアップが完了しました！"
