#!/bin/bash
set -e

# Configuration
PROJECT_NAME=${PROJECT_NAME:-agentic-sales-analyst}
REGION=${AWS_REGION:-ap-southeast-2}

echo "🚀 共通インフラストラクチャをデプロイ中"
echo "プロジェクト: $PROJECT_NAME"
echo "リージョン: $REGION"

# Function to wait for stack completion
# amazonq-ignore-next-line
# amazonq-ignore-next-line
wait_for_stack() {
    local stack_name=$1
    echo "⏳ スタック $stack_name の完了を待機中..."
    aws cloudformation wait stack-create-complete \
        --stack-name $stack_name \
        --region $REGION 2>/dev/null || \
    aws cloudformation wait stack-update-complete \
        --stack-name $stack_name \
        --region $REGION 2>/dev/null
    echo "✅ スタック $stack_name が完了しました"
}

# Step 1: ネットワークをデプロイ
echo ""
echo "📡 ステップ 1: ネットワークインフラストラクチャをデプロイ中..."
# amazonq-ignore-next-line
aws cloudformation deploy \
    --stack-name ${PROJECT_NAME}-network \
    --template-file common/01-network.yaml \
    --parameter-overrides ProjectName=$PROJECT_NAME \
    --region $REGION

# Step 2: IAM をデプロイ
echo ""
echo "👤 ステップ 2: IAM ロールをデプロイ中..."
aws cloudformation deploy \
    --stack-name ${PROJECT_NAME}-iam \
    --template-file common/02-iam.yaml \
    --parameter-overrides ProjectName=$PROJECT_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION

# Step 3: ECR をデプロイ
echo ""
echo "📦 ステップ 3: ECR リポジトリをデプロイ中..."
aws cloudformation deploy \
    --stack-name ${PROJECT_NAME}-ecr \
    --template-file common/03-ecr.yaml \
    --parameter-overrides ProjectName=$PROJECT_NAME \
    --region $REGION

# Step 4: イメージをビルドしてプッシュ
echo ""
echo "🏗️ ステップ 4: コンテナイメージをビルドしてプッシュ中..."
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name ${PROJECT_NAME}-ecr \
    --query 'Stacks[0].Outputs[?OutputKey==`RepositoryUri`].OutputValue' \
    --output text \
    --region $REGION)

if [ -z "$ECR_URI" ]; then
    echo "❌ エラー: ECR リポジトリ URI を取得できませんでした"
    exit 1
fi

echo "ECR URI: $ECR_URI"

ACCOUNT_ID=$(echo $ECR_URI | cut -d'.' -f1)
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ エラー: ECR URI から AWS アカウント ID を抽出できませんでした"
    exit 1
fi

echo "ECR にログイン中..."
if ! aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com; then
    echo "❌ エラー: ECR へのログインに失敗しました"
    echo "AWS 認証情報と権限を確認してください"
    exit 1
fi
echo "✅ ECR へのログインに成功しました"

# buildx が利用可能かチェック
if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ エラー: docker buildx が利用できません"
    echo "Docker Desktop をインストールするか、Docker Engine を 19.03+ にアップグレードしてください"
    exit 1
fi

# buildx ビルダーが存在しない場合は作成
if ! docker buildx inspect multiarch-builder > /dev/null 2>&1; then
    echo "buildx ビルダーを作成中..."
    docker buildx create --name multiarch-builder --use
else
    echo "既存の buildx ビルダーを使用中..."
    docker buildx use multiarch-builder
fi

# amazonq-ignore-next-line
# PostgreSQL イメージをビルドしてプッシュ
echo "linux/amd64 用 PostgreSQL イメージをビルド中..."
docker buildx build --platform linux/amd64 -f ../Dockerfile.postgres -t $ECR_URI:postgres-latest --push ../

# バックエンドをビルドしてプッシュ
echo "linux/amd64 用バックエンドイメージをビルド中..."
docker buildx build --platform linux/amd64 -t $ECR_URI:backend-latest --push ../

# フロントエンドをビルドしてプッシュ
echo "linux/amd64 用フロントエンドイメージをビルド中..."
docker buildx build --platform linux/amd64 -t $ECR_URI:frontend-latest --push ../client

echo ""
echo "✅ インフラストラクチャのデプロイが完了しました！"
echo "📦 ECR URI: $ECR_URI"
echo ""
echo "次のステップ:"
echo "  ECS: cd ecs && ./deploy-ecs.sh"
echo "  EKS: cd eks && ./deploy-k8s.sh"
