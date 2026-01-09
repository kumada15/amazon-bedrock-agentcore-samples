#!/bin/bash
set -e

# Configuration
PROJECT_NAME=${PROJECT_NAME:-agentic-sales-analyst}
REGION=${AWS_REGION:-ap-southeast-2}

echo "🐳 ECS 固有リソースをデプロイ中"
echo "プロジェクト: $PROJECT_NAME"
echo "リージョン: $REGION"
echo ""
echo "⚠️  BRAVE_SEARCH_API_KEY を指定する必要があります"
read -p "BRAVE_SEARCH_API_KEY を入力してください: " BRAVE_API_KEY
echo ""

# Get ECR URI from infrastructure stack
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name ${PROJECT_NAME}-ecr \
    --query 'Stacks[0].Outputs[?OutputKey==`RepositoryUri`].OutputValue' \
    --output text \
    --region $REGION 2>/dev/null)

if [ -z "$ECR_URI" ]; then
    echo "❌ エラー: インフラストラクチャがデプロイされていません。先に ../deploy-infrastructure.sh を実行してください"
    exit 1
fi

echo "ECR URI を使用: $ECR_URI"

# Step 1: ECS クラスターをデプロイ
echo ""
echo "🐳 ステップ 1: ECS クラスターをデプロイ中..."
aws cloudformation deploy \
    --stack-name ${PROJECT_NAME}-ecs-cluster \
    --template-file cluster.yaml \
    --parameter-overrides ProjectName=$PROJECT_NAME \
    --region $REGION

# Step 2: ECS サービスをデプロイ
echo ""
echo "🚀 ステップ 2: ECS サービスをデプロイ中..."

aws cloudformation deploy \
    --stack-name ${PROJECT_NAME}-ecs-service \
    --template-file service.yaml \
    --parameter-overrides \
        ProjectName=$PROJECT_NAME \
        BackendImage=$ECR_URI:backend-latest \
        FrontendImage=$ECR_URI:frontend-latest \
        BraveSearchAPIKey=$BRAVE_API_KEY \
        DesiredCount=1 \
    --region $REGION

# Get ALB URL
ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name ${PROJECT_NAME}-ecs-cluster \
    --query 'Stacks[0].Outputs[?OutputKey==`ALBDNSName`].OutputValue' \
    --output text \
    --region $REGION)

echo ""
echo "✅ ECS デプロイが完了しました！"
echo "🌐 アプリケーション URL: http://$ALB_DNS"
echo "📊 CloudWatch Logs: /aws/bedrock-agentcore/runtimes/$PROJECT_NAME"
