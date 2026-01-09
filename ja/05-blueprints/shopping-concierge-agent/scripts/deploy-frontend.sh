#!/bin/bash
set -e

# Frontend deployment script for Vite app to Amplify Hosting
# Usage: ./scripts/deploy-frontend.sh [--mock|--no-mock]
#   --mock    : Use Visa mock mode (no real API calls)
#   --no-mock : Use real Visa API via Lambda proxy

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 フロントエンドを Amplify にデプロイしています${NC}\n"

# Parse flags
MOCK_FLAG=""
for arg in "$@"; do
    case $arg in
        --mock) MOCK_FLAG="--mock" ;;
        --no-mock) MOCK_FLAG="--no-mock" ;;
    esac
done

# Get deployment ID from config
DEPLOYMENT_ID=$(node -p "require('./deployment-config.json').deploymentId")
STACK_NAME="FrontendStack-${DEPLOYMENT_ID}"

# Set default region if not set
export AWS_REGION=${AWS_REGION:-us-east-1}

# Get configuration from CDK stack
echo -e "${BLUE}Amplify 設定を取得しています...${NC}"
APP_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='AmplifyAppId'].OutputValue" \
    --output text 2>/dev/null)

STAGING_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='StagingBucketName'].OutputValue" \
    --output text 2>/dev/null)

if [ -z "$APP_ID" ] || [ "$APP_ID" = "None" ]; then
    echo -e "${RED}❌ エラー: Amplify App ID が見つかりません${NC}"
    echo -e "${YELLOW}💡 先にフロントエンドスタックをデプロイしてください:${NC}"
    echo -e "   cd infrastructure/frontend-stack && npm install && cdk deploy"
    exit 1
fi

echo -e "${GREEN}✓${NC} App ID: $APP_ID"
echo -e "${GREEN}✓${NC} Staging Bucket: $STAGING_BUCKET"
echo ""

# Update environment configuration
echo -e "${BLUE}環境設定を更新しています...${NC}"
./scripts/setup-web-ui-env.sh --force $MOCK_FLAG
echo ""

# Build the frontend
echo -e "${BLUE}フロントエンドをビルドしています...${NC}"
cd web-ui
npm run build

if [ ! -d "dist" ]; then
    echo -e "${RED}❌ エラー: ビルドディレクトリ 'dist' が見つかりません${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} ビルドが完了しました"
echo ""

# Create deployment package
echo -e "${BLUE}デプロイパッケージを作成しています...${NC}"
cd dist
S3_KEY="amplify-deploy-$(date +%s).zip"
zip -r ../amplify-deploy.zip . -q
cd ..

ZIP_SIZE=$(ls -lah amplify-deploy.zip | awk '{print $5}')
echo -e "${GREEN}✓${NC} パッケージを作成しました (${ZIP_SIZE})"
echo ""

# Upload to S3
echo -e "${BLUE}S3 にアップロードしています...${NC}"
aws s3 cp amplify-deploy.zip "s3://$STAGING_BUCKET/$S3_KEY" --no-progress

echo -e "${GREEN}✓${NC} アップロードが完了しました"
echo ""

# Start Amplify deployment
echo -e "${BLUE}Amplify デプロイを開始しています...${NC}"
DEPLOYMENT_OUTPUT=$(aws amplify start-deployment \
    --app-id "$APP_ID" \
    --branch-name main \
    --source-url "s3://$STAGING_BUCKET/$S3_KEY" \
    --output json 2>&1)

if [ $? -eq 0 ]; then
    JOB_ID=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.jobSummary.jobId')
    echo -e "${GREEN}✓${NC} デプロイを開始しました (Job ID: $JOB_ID)"
    echo ""

    # Get app URL
    APP_URL=$(aws amplify get-app --app-id "$APP_ID" --query 'app.defaultDomain' --output text)

    echo -e "${BLUE}デプロイを監視しています...${NC}"
    while true; do
        STATUS=$(aws amplify get-job \
            --app-id "$APP_ID" \
            --branch-name main \
            --job-id "$JOB_ID" \
            --output json | jq -r '.job.summary.status')

        echo "  ステータス: $STATUS"

        case $STATUS in
            "SUCCEED")
                echo ""
                echo -e "${GREEN}✅ デプロイが正常に完了しました！${NC}"
                echo ""
                echo -e "${BLUE}App URL:${NC} https://main.$APP_URL"
                echo -e "${BLUE}コンソール:${NC} https://console.aws.amazon.com/amplify/apps/$APP_ID"
                break
                ;;
            "FAILED")
                echo -e "${RED}❌ デプロイに失敗しました${NC}"
                exit 1
                ;;
            "CANCELLED")
                echo -e "${RED}❌ デプロイがキャンセルされました${NC}"
                exit 1
                ;;
            *)
                sleep 10
                ;;
        esac
    done
else
    echo -e "${RED}❌ Amplify デプロイに失敗しました${NC}"
    echo "$DEPLOYMENT_OUTPUT"
    exit 1
fi

# Return to project root
cd ..

# Cleanup
rm -f web-ui/amplify-deploy.zip
