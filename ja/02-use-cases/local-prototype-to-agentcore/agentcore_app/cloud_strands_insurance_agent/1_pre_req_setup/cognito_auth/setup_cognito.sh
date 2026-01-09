#!/bin/bash

# Bedrock AgentCore Cognito Auth Setup Script
# This script helps set up the Cognito User Pool and App Client for Bedrock AgentCore authentication

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════╗"
echo "║      BEDROCK AGENTCORE COGNITO AUTH    ║"
echo "║         Authentication Setup           ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}エラー: AWS CLI がインストールされていません。先にインストールしてください。${NC}"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}エラー: jq がインストールされていません。先にインストールしてください。${NC}"
    exit 1
fi

# Check if user is logged in to AWS
echo "AWS 認証情報を確認中..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}エラー: AWS に認証されていません。先に 'aws configure' を実行してください。${NC}"
    exit 1
fi

# Get AWS account information
echo "AWS アカウント情報を取得中..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}エラー: AWS アカウント ID を特定できませんでした。${NC}"
    exit 1
fi

# Default values
DEFAULT_REGION="us-east-1"
DEFAULT_POOL_NAME="BedrockAgentCoreUserPool"
DEFAULT_CLIENT_NAME="BedrockAgentCoreClient"
DEFAULT_USERNAME="agentcore-user"
DEFAULT_PASSWORD="MyPassword123!"

# Get region
echo -e "\nCognito リソース用の AWS リージョンを入力 (デフォルト: ${DEFAULT_REGION}):"
read -p "> " REGION_INPUT
REGION=${REGION_INPUT:-$DEFAULT_REGION}

# Get User Pool name
echo -e "\nCognito ユーザープール名を入力 (デフォルト: ${DEFAULT_POOL_NAME}):"
read -p "> " POOL_NAME_INPUT
POOL_NAME=${POOL_NAME_INPUT:-$DEFAULT_POOL_NAME}

# Get App Client name
echo -e "\nCognito アプリクライアント名を入力 (デフォルト: ${DEFAULT_CLIENT_NAME}):"
read -p "> " CLIENT_NAME_INPUT
CLIENT_NAME=${CLIENT_NAME_INPUT:-$DEFAULT_CLIENT_NAME}

# Get username
echo -e "\nテストユーザーのユーザー名を入力 (デフォルト: ${DEFAULT_USERNAME}):"
read -p "> " USERNAME_INPUT
USERNAME=${USERNAME_INPUT:-$DEFAULT_USERNAME}

# Get password
echo -e "\nテストユーザーのパスワードを入力 (デフォルト: ${DEFAULT_PASSWORD}):"
read -p "> " PASSWORD_INPUT
PASSWORD=${PASSWORD_INPUT:-$DEFAULT_PASSWORD}

# Confirm settings
echo -e "\n${YELLOW}設定の確認:${NC}"
echo "  - AWS アカウント ID: ${ACCOUNT_ID}"
echo "  - AWS リージョン: ${REGION}"
echo "  - ユーザープール名: ${POOL_NAME}"
echo "  - アプリクライアント名: ${CLIENT_NAME}"
echo "  - ユーザー名: ${USERNAME}"
echo "  - パスワード: ${PASSWORD}"

echo -e "\nこれらの設定で続行しますか？ (Y/n)"
read -p "> " PROCEED
PROCEED=${PROCEED:-Y}
if [[ $PROCEED == "n" || $PROCEED == "N" || $PROCEED == "no" || $PROCEED == "No" || $PROCEED == "NO" ]]; then
    echo -e "${YELLOW}セットアップがキャンセルされました。${NC}"
    exit 0
fi

echo -e "\n${YELLOW}Cognito ユーザープールを作成中...${NC}"
# Create User Pool and capture Pool ID
POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "${POOL_NAME}" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region ${REGION} | jq -r '.UserPool.Id')

if [ -z "$POOL_ID" ] || [ "$POOL_ID" == "null" ]; then
    echo -e "${RED}エラー: ユーザープールの作成に失敗しました。${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Cognito アプリクライアントを作成中...${NC}"
# Create App Client and capture Client ID
CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id ${POOL_ID} \
  --client-name "${CLIENT_NAME}" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --region ${REGION} | jq -r '.UserPoolClient.ClientId')

if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" == "null" ]; then
    echo -e "${RED}エラー: アプリクライアントの作成に失敗しました。${NC}"
    exit 1
fi

echo -e "\n${YELLOW}テストユーザーを作成中...${NC}"
# Create User
aws cognito-idp admin-create-user \
  --user-pool-id ${POOL_ID} \
  --username "${USERNAME}" \
  --temporary-password "Temp123!" \
  --region ${REGION} \
  --message-action SUPPRESS > /dev/null

if [ $? -ne 0 ]; then
    echo -e "${RED}エラー: テストユーザーの作成に失敗しました。${NC}"
    exit 1
fi

echo -e "\n${YELLOW}テストユーザーの永続パスワードを設定中...${NC}"
# Set Permanent Password
aws cognito-idp admin-set-user-password \
  --user-pool-id ${POOL_ID} \
  --username "${USERNAME}" \
  --password "${PASSWORD}" \
  --region ${REGION} \
  --permanent > /dev/null

if [ $? -ne 0 ]; then
    echo -e "${RED}エラー: ユーザーパスワードの設定に失敗しました。${NC}"
    exit 1
fi

echo -e "\n${YELLOW}ユーザーを認証してアクセストークンを取得中...${NC}"
# Authenticate User and capture Access Token
BEARER_TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "${CLIENT_ID}" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME="${USERNAME}",PASSWORD="${PASSWORD}" \
  --region ${REGION} | jq -r '.AuthenticationResult.AccessToken')

if [ -z "$BEARER_TOKEN" ] || [ "$BEARER_TOKEN" == "null" ]; then
    echo -e "${RED}エラー: ユーザーの認証とトークンの取得に失敗しました。${NC}"
    exit 1
fi

# Discovery URL
DISCOVERY_URL="https://cognito-idp.${REGION}.amazonaws.com/${POOL_ID}/.well-known/openid-configuration"

# Save config to JSON file
echo -e "\n${YELLOW}設定を cognito_config.json に保存中...${NC}"
cat > cognito_config.json << EOF
{
  "pool_id": "${POOL_ID}",
  "client_id": "${CLIENT_ID}",
  "discovery_url": "${DISCOVERY_URL}",
  "bearer_token": "${BEARER_TOKEN}",
  "region": "${REGION}",
  "username": "${USERNAME}",
  "password": "${PASSWORD}"
}
EOF

# Save summary to markdown file
cat > cognito_result.md << EOF
# Cognito Authentication Setup

## Configuration
- **User Pool ID**: ${POOL_ID}
- **Client ID**: ${CLIENT_ID}
- **Region**: ${REGION}
- **Discovery URL**: ${DISCOVERY_URL}

## Test User
- **Username**: ${USERNAME}
- **Password**: ${PASSWORD}

## Authentication Token
\`\`\`
${BEARER_TOKEN}
\`\`\`

## Notes
- The token expires after 1 hour by default
- Use the refresh_token.sh script to get a new token when needed
- Configuration is saved in cognito_config.json for easy access
EOF

echo -e "\n${GREEN}✅ Cognito 認証のセットアップが正常に完了しました！${NC}"
echo -e "\n${GREEN}ユーザープール ID:${NC} ${POOL_ID}"
echo -e "${GREEN}Discovery URL:${NC} ${DISCOVERY_URL}"
echo -e "${GREEN}クライアント ID:${NC} ${CLIENT_ID}"
echo -e "${GREEN}Bearer トークン:${NC} ${BEARER_TOKEN}"
echo -e "\n完全な設定は cognito_config.json に保存されました"
echo -e "概要は cognito_result.md に保存されました"
echo -e "\nトークンの有効期限が切れたら更新するには: ./refresh_token.sh を実行"