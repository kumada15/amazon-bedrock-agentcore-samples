#!/bin/bash

# Deploy the manual FastAPI implementation to ECR
echo "🚀 DIY エージェント (FastAPI) をデプロイ中..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
RUNTIME_DIR="$(dirname "$SCRIPT_DIR")"  # agentcore-runtime directory

# Load configuration from unified config system
CONFIG_DIR="${PROJECT_DIR}/config"
BASE_SETTINGS="${CONFIG_DIR}/static-config.yaml"

if command -v yq >/dev/null 2>&1; then
    REGION=$(yq eval '.aws.region' "${BASE_SETTINGS}")
    ACCOUNT_ID=$(yq eval '.aws.account_id' "${BASE_SETTINGS}")
else
    echo "⚠️  yq が見つかりません。grep/sed フォールバックを使用します"
    # Fallback: extract from YAML using grep/sed
    REGION=$(grep "region:" "${BASE_SETTINGS}" | head -1 | sed 's/.*region: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ACCOUNT_ID=$(grep "account_id:" "${BASE_SETTINGS}" | head -1 | sed 's/.*account_id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
fi
ECR_REPO="bac-runtime-repo-diy"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"

# Get AWS credentials from SSO
echo "🔐 AWS 認証情報を取得中..."
if [ -n "$AWS_PROFILE" ]; then
    echo "AWS プロファイルを使用: $AWS_PROFILE"
else
    echo "デフォルトの AWS 認証情報を使用"
fi

# Use configured AWS profile if specified in static config
AWS_PROFILE_CONFIG=$(grep "aws_profile:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*aws_profile: *["'\'']*\([^"'\''#]*\)["'\'']*.*$/\1/' | xargs 2>/dev/null)
if [[ -n "$AWS_PROFILE_CONFIG" && "$AWS_PROFILE_CONFIG" != "\"\"" && "$AWS_PROFILE_CONFIG" != "''" ]]; then
    echo "設定された AWS プロファイルを使用: $AWS_PROFILE_CONFIG"
    export AWS_PROFILE="$AWS_PROFILE_CONFIG"
fi

# Login to ECR
echo "🔑 ECR にログイン中..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URI}

# Check if repository exists, create if not
echo "📦 ECR リポジトリを確認中..."
if ! aws ecr describe-repositories --repository-names ${ECR_REPO} --region ${REGION} >/dev/null 2>&1; then
    echo "📦 ECR リポジトリを作成中: ${ECR_REPO}"
    aws ecr create-repository --repository-name ${ECR_REPO} --region ${REGION}
else
    echo "✅ ECR リポジトリは存在します: ${ECR_REPO}"
fi

# Build ARM64 image using DIY Dockerfile
echo "🔨 ARM64 イメージをビルド中..."
cd "${PROJECT_DIR}"
docker build --no-cache --platform linux/arm64 -f agentcore-runtime/deployment/Dockerfile.diy -t ${ECR_REPO}:latest .

# Tag for ECR
echo "🏷️  イメージにタグ付け中..."
docker tag ${ECR_REPO}:latest ${ECR_URI}:latest

# Push to ECR
echo "📤 ECR にプッシュ中..."
docker push ${ECR_URI}:latest

# Update dynamic configuration with ECR URI
echo "📝 ECR URI で動的設定を更新中..."
DYNAMIC_CONFIG="${CONFIG_DIR}/dynamic-config.yaml"
if command -v yq >/dev/null 2>&1; then
    # Ensure the runtime.diy_agent section exists
    yq eval '.runtime.diy_agent.ecr_uri = "'"${ECR_URI}:latest"'"' -i "${DYNAMIC_CONFIG}"
    echo "   ✅ ECR URI で動的設定を更新しました"
else
    echo "   ⚠️  yq が見つかりません。ECR URI は Python デプロイスクリプトで更新されます"
    echo "   📝 ECR URI: ${ECR_URI}:latest"
fi

echo "✅ DIY エージェントをデプロイしました: ${ECR_URI}:latest"
echo ""

# Automatically run the runtime deployment script
echo "🚀 ランタイムデプロイスクリプトを実行中..."
echo "   実行: python3 deploy-diy-runtime.py"
echo ""

cd "${SCRIPT_DIR}"
if python3 deploy-diy-runtime.py; then
    echo ""
    echo "🎉 DIY エージェントのデプロイが完了しました！"
    echo "================================="
    echo "✅ ECR イメージをデプロイ: ${ECR_URI}:latest"
    echo "✅ AgentCore ランタイムを作成・設定しました"
    echo ""
    echo "📋 デプロイされたもの:"
    echo "   • Docker イメージをビルドして ECR にプッシュ"
    echo "   • AgentCore ランタイムインスタンスを作成"
    echo "   • ワークロード ID をランタイムに関連付け"
    echo ""
    echo "💻 DIY エージェントは OAuth2 トークンと MCP Gateway を使用する準備ができました！"
    echo "   エージェントコードで @requires_access_token デコレータを使用"
    echo "   ツールアクセス用に MCP Gateway に接続"
else
    echo ""
    echo "❌ ランタイムのデプロイに失敗しました"
    echo "上記のエラーメッセージを確認し、手動で実行してください:"
    echo "   python3 deploy-diy-runtime.py"
    exit 1
fi