#!/bin/bash

# Script to create .env file from SSM Parameter Store values
# Usage: ./setup-env.sh [region]

set -e

# Default values
AWS_REGION="${1:-us-west-2}"

echo ".env ファイルをセットアップ中..."
echo "AWS リージョン: $AWS_REGION"
echo ""

# Fetch values from SSM Parameter Store
echo "SSM Parameter Store からパラメータを取得中..."

USER_POOL_ID=$(aws ssm get-parameter \
    --name "/app/customersupportvpc/agentcore/user_pool_id" \
    --region "$AWS_REGION" \
    --query "Parameter.Value" \
    --output text)

WEB_CLIENT_ID=$(aws ssm get-parameter \
    --name "/app/customersupportvpc/agentcore/web_client_id" \
    --region "$AWS_REGION" \
    --query "Parameter.Value" \
    --output text)

COGNITO_DOMAIN=$(aws ssm get-parameter \
    --name "/app/customersupportvpc/agentcore/cognito_domain" \
    --region "$AWS_REGION" \
    --query "Parameter.Value" \
    --output text)

AGENT_ARN=$(aws ssm get-parameter \
    --name "/app/customersupportvpc/agentcore/agent_runtime_arn" \
    --region "$AWS_REGION" \
    --query "Parameter.Value" \
    --output text)

# Remove https:// prefix from domain if present
COGNITO_DOMAIN=$(echo "$COGNITO_DOMAIN" | sed 's|https://||')

echo "✓ User Pool ID: $USER_POOL_ID"
echo "✓ Web Client ID: $WEB_CLIENT_ID"
echo "✓ Cognito Domain: $COGNITO_DOMAIN"
echo "✓ Agent ARN: $AGENT_ARN"
echo ""

# Create .env file
ENV_FILE="$(dirname "$0")/.env"

echo ".env ファイルを作成中: $ENV_FILE"

cat > "$ENV_FILE" << EOF
# AWS Configuration
# Default region for AWS SDK
VITE_AWS_REGION=$AWS_REGION

# Cognito Configuration
# You can get these values from your AWS Cognito User Pool
VITE_COGNITO_USER_POOL_ID=$USER_POOL_ID
VITE_COGNITO_USER_POOL_CLIENT_ID=$WEB_CLIENT_ID
VITE_COGNITO_DOMAIN=$COGNITO_DOMAIN

# CloudFormation Stack Name (with environment suffix)
# Can also be passed via URL parameter: ?stack=your-stack-name
# Examples: customer-support-vpc-dev, customer-support-vpc-prod, customer-support-vpc-test
VITE_AGENT_ARN=$AGENT_ARN

EOF

echo "✓ .env ファイルを正常に作成しました！"
echo ""
echo "内容:"
cat "$ENV_FILE"
