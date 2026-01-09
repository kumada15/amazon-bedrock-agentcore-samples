#!/bin/bash

# Create AgentCore Gateway and MCP targets using OAuth provider and MCP tool Lambda
echo "🚀 AgentCore Gateway と MCP ターゲットを作成中..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
RUNTIME_DIR="$(dirname "$SCRIPT_DIR")"  # agentcore-runtime directory
CONFIG_DIR="${PROJECT_DIR}/config"

# Load configuration from YAML (fallback if yq not available)
if command -v yq >/dev/null 2>&1; then
    REGION=$(yq eval '.aws.region' "${CONFIG_DIR}/static-config.yaml")
    ACCOUNT_ID=$(yq eval '.aws.account_id' "${CONFIG_DIR}/static-config.yaml")
    ROLE_ARN=$(yq eval '.runtime.role_arn' "${CONFIG_DIR}/static-config.yaml")
    # Get gateway execution role from dynamic config
    GATEWAY_EXECUTION_ROLE_ARN=$(yq eval '.mcp_lambda.gateway_execution_role_arn' "${CONFIG_DIR}/dynamic-config.yaml")
else
    echo "⚠️  yq が見つかりません。既存の設定からデフォルト値を使用します"
    # Fallback: extract from YAML using grep/sed
    REGION=$(grep "region:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*region: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ACCOUNT_ID=$(grep "account_id:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*account_id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ROLE_ARN=$(grep "role_arn:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*role_arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    # Get gateway execution role from dynamic config
    GATEWAY_EXECUTION_ROLE_ARN=$(grep "gateway_execution_role_arn:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*gateway_execution_role_arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
fi

# Load OAuth provider configuration from dynamic config
if command -v yq >/dev/null 2>&1; then
    PROVIDER_ARN=$(yq eval '.oauth_provider.provider_arn' "${CONFIG_DIR}/dynamic-config.yaml")
    OKTA_DOMAIN=$(yq eval '.okta.domain' "${CONFIG_DIR}/static-config.yaml")
else
    PROVIDER_ARN=$(grep "provider_arn:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*provider_arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    OKTA_DOMAIN=$(grep "domain:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*domain: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
fi

if [[ -z "$PROVIDER_ARN" || "$PROVIDER_ARN" == "null" ]]; then
    echo "❌ OAuth プロバイダー ARN が設定に見つかりません"
    echo "   先に ./02-setup-oauth-provider.sh を実行してください"
    exit 1
fi

# Load Okta JWT configuration from static config
if command -v yq >/dev/null 2>&1; then
    JWT_DISCOVERY_URL=$(yq eval '.okta.jwt.discovery_url' "${CONFIG_DIR}/static-config.yaml")
    JWT_AUDIENCE=$(yq eval '.okta.jwt.audience' "${CONFIG_DIR}/static-config.yaml")
else
    JWT_DISCOVERY_URL=$(grep "discovery_url:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*discovery_url: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    JWT_AUDIENCE=$(grep "audience:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*audience: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
fi

# Load Lambda function configuration from dynamic config
if command -v yq >/dev/null 2>&1; then
    LAMBDA_FUNCTION_ARN=$(yq eval '.mcp_lambda.function_arn' "${CONFIG_DIR}/dynamic-config.yaml" 2>/dev/null)
else
    LAMBDA_FUNCTION_ARN=$(grep "function_arn:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*function_arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' 2>/dev/null)
fi

if [[ -z "$LAMBDA_FUNCTION_ARN" || "$LAMBDA_FUNCTION_ARN" == "null" ]]; then
    echo "❌ MCP Lambda 関数 ARN が設定に見つかりません"
    echo "   先に ./03-deploy-mcp-tool-lambda.sh を実行してください"
    exit 1
fi

if [[ -z "$ROLE_ARN" || "$ROLE_ARN" == "null" ]]; then
    echo "❌ Gateway 実行ロール ARN (bac-execution-role) が設定に見つかりません"
    echo "   先に ./01-prerequisites.sh を実行してください"
    exit 1
fi

# Configuration values (environment-agnostic)
GATEWAY_NAME="bac-gtw"
GATEWAY_DESCRIPTION="BAC Gateway for AWS operations via MCP"
TARGET_NAME="bac-tool"
TARGET_DESCRIPTION="BAC MCP Target with AWS service tools"

echo "📝 設定:"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
echo "   Gateway 名: $GATEWAY_NAME"
echo "   ターゲット名: $TARGET_NAME"
echo "   Gateway ロール ARN (bac-execution-role): $ROLE_ARN"
echo "   Lambda 関数ロール ARN: $GATEWAY_EXECUTION_ROLE_ARN"
echo "   プロバイダー ARN: $PROVIDER_ARN"
echo "   Lambda ARN: $LAMBDA_FUNCTION_ARN"
echo "   JWT ディスカバリー URL: $JWT_DISCOVERY_URL"
echo "   JWT オーディエンス: $JWT_AUDIENCE"
echo ""

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

# Path to gateway operations scripts
GATEWAY_OPS_DIR="${RUNTIME_DIR}/gateway-ops-scripts"

# Function to check if Python scripts are available
check_gateway_scripts() {
    if [[ ! -d "$GATEWAY_OPS_DIR" ]]; then
        echo "❌ Gateway 操作スクリプトが見つかりません: $GATEWAY_OPS_DIR"
        return 1
    fi

    local required_scripts=("create-gateway.py" "create-target.py")
    for script in "${required_scripts[@]}"; do
        if [[ ! -f "${GATEWAY_OPS_DIR}/${script}" ]]; then
            echo "❌ 必須スクリプトが見つかりません: ${GATEWAY_OPS_DIR}/${script}"
            return 1
        fi
    done

    echo "✅ Gateway 操作スクリプトが見つかりました"
    return 0
}

# Check if gateway operations scripts are available
echo "🔍 Gateway 操作スクリプトを確認中..."
if ! check_gateway_scripts; then
    echo "❌ Gateway 操作スクリプトが利用できません"
    echo "   期待される場所: $GATEWAY_OPS_DIR"
    exit 1
fi

# Activate virtual environment to ensure Python dependencies are available
echo "🐍 Python 仮想環境をアクティベート中..."
cd "${PROJECT_DIR}" && source .venv/bin/activate

# Create the gateway using Python script
echo "🏗️  Python スクリプトで AgentCore Gateway を作成中..."
cd "$GATEWAY_OPS_DIR"

GATEWAY_RESPONSE=$(python3 create-gateway.py \
    --name "$GATEWAY_NAME" \
    --description "$GATEWAY_DESCRIPTION" 2>&1)

if [[ $? -ne 0 ]]; then
    echo "❌ Gateway の作成に失敗しました"
    echo "$GATEWAY_RESPONSE"
    exit 1
fi

echo "$GATEWAY_RESPONSE"

# Extract Gateway information from response (Python script outputs human-readable format)
GATEWAY_ID=$(echo "$GATEWAY_RESPONSE" | grep "   Gateway ID:" | sed 's/.*Gateway ID: *//' | tail -1 | tr -d '\n\r')
GATEWAY_URL=$(echo "$GATEWAY_RESPONSE" | grep "   Gateway URL:" | sed 's/.*Gateway URL: *//' | tail -1 | tr -d '\n\r')

if [[ -z "$GATEWAY_ID" ]]; then
    echo "⚠️  レスポンスから Gateway ID を抽出できませんでした"
    # Try to get gateway ID from list if creation was successful
    LIST_RESPONSE=$(python3 list-gateways.py 2>/dev/null || echo "")
    if [[ -n "$LIST_RESPONSE" ]]; then
        echo "🔍 リストから Gateway を検索中..."
        echo "$LIST_RESPONSE"
    fi
fi

# Get Gateway ARN from dynamic config (updated by Python script)
if command -v yq >/dev/null 2>&1; then
    GATEWAY_ARN=$(yq eval '.gateway.arn' "${CONFIG_DIR}/dynamic-config.yaml" 2>/dev/null)
else
    GATEWAY_ARN=$(grep "arn:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' 2>/dev/null)
fi

echo "✅ Gateway 作成プロセスが完了しました！"
if [[ -n "$GATEWAY_ID" ]]; then
    echo "   Gateway ID: $GATEWAY_ID"
fi

# Create the target using Python script
echo "🎯 Python スクリプトで AWS ツール付き MCP ターゲットを作成中..."
echo "   使用する Gateway ID: $GATEWAY_ID"
echo "   使用する Lambda ARN: $LAMBDA_FUNCTION_ARN"

TARGET_RESPONSE=$(python3 create-target.py \
    --gateway-id "$GATEWAY_ID" \
    --lambda-arn "$LAMBDA_FUNCTION_ARN" \
    --name "$TARGET_NAME" \
    --description "$TARGET_DESCRIPTION" 2>&1)
if [[ $? -ne 0 ]]; then
    echo "❌ ターゲットの作成に失敗しました"
    echo "$TARGET_RESPONSE"
    exit 1
fi

echo "$TARGET_RESPONSE"

# Extract Target information from response
TARGET_ID=$(echo "$TARGET_RESPONSE" | grep "   Target ID:" | sed 's/.*Target ID: *//' | tail -1 | tr -d '\n\r')
TOOL_COUNT=$(echo "$TARGET_RESPONSE" | grep "   Tool Count:" | sed 's/.*Tool Count: *//' | tail -1 | tr -d '\n\r')

# Target ARN is not provided by AWS API, construct it manually
if [[ -n "$GATEWAY_ID" && -n "$TARGET_ID" ]]; then
    TARGET_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:gateway/${GATEWAY_ID}/target/${TARGET_ID}"
else
    TARGET_ARN="unknown"
fi

echo "✅ ターゲット作成プロセスが完了しました！"
if [[ -n "$TARGET_ID" && "$TARGET_ID" != "unknown" ]]; then
    echo "   ターゲット ID: $TARGET_ID"
fi

# Return to original directory
cd "${SCRIPT_DIR}"

echo ""
echo "🎉 AgentCore Gateway とターゲットの作成が完了しました！"
echo "======================================================"
echo ""
echo "📋 作成されたリソース:"
if [[ -n "$GATEWAY_ID" && "$GATEWAY_ID" != "unknown" ]]; then
    echo "   • Gateway: $GATEWAY_NAME ($GATEWAY_ID)"
else
    echo "   • Gateway: $GATEWAY_NAME (作成開始済み)"
fi
if [[ -n "$TARGET_ID" && "$TARGET_ID" != "unknown" ]]; then
    echo "   • ターゲット: $TARGET_NAME ($TARGET_ID)"
else
    echo "   • ターゲット: $TARGET_NAME (作成開始済み)"
fi
echo "   • Lambda 関数: $LAMBDA_FUNCTION_ARN"
echo "   • OAuth プロバイダー: $PROVIDER_ARN"
echo ""
echo "🔍 ステータスを確認:"
echo "   • Gateway 一覧: cd ${GATEWAY_OPS_DIR} && python3 list-gateways.py"
echo "   • ターゲット一覧: cd ${GATEWAY_OPS_DIR} && python3 list-targets.py"
if [[ -n "$GATEWAY_ID" && "$GATEWAY_ID" != "unknown" ]]; then
    echo "   • Gateway 詳細: cd ${GATEWAY_OPS_DIR} && python3 get-gateway.py --gateway-id $GATEWAY_ID"
fi
echo ""
echo "🚀 次のステップ:"
echo "   • エージェントランタイムをデプロイ: ./05-deploy-diy.sh と ./06-deploy-sdk.sh"
echo "   • 準備ができたら Gateway への MCP 接続をテスト"
echo "================================================"
echo "✅ Gateway とターゲットがデプロイ・設定されました"
echo ""
echo "📋 Gateway 詳細:"
echo "   • Gateway ID: ${GATEWAY_ID:-unknown}"
echo "   • Gateway ARN: ${GATEWAY_ARN:-unknown}"
echo "   • Gateway URL: ${GATEWAY_URL:-unknown}"
echo "   • Gateway 名: $GATEWAY_NAME"
echo ""
echo "📋 ターゲット詳細:"
echo "   • ターゲット ID: ${TARGET_ID:-unknown}"
echo "   • ターゲット ARN: ${TARGET_ARN:-unknown}"
echo "   • ターゲット名: $TARGET_NAME"
echo "   • Lambda 関数: $(basename "$LAMBDA_FUNCTION_ARN")"
echo "   • 利用可能なツール: ${TOOL_COUNT:-unknown} 個"
echo ""
echo "📋 作成されたもの:"
echo "   • OAuth2 JWT 認証付き AgentCore Gateway"
echo "   • Lambda 関数に接続された MCP ターゲット"
echo "   • 20 以上の AWS サービス用ツールスキーマ"
echo "   • Gateway 詳細で更新された設定"
echo ""
echo "🔧 利用可能なツール:"
echo "   • 基本: hello_world, get_time"
echo "   • AWS サービス: EC2, S3, Lambda, RDS, CloudFormation, IAM"
echo "   • AWS サービス: ECS, EKS, SNS, SQS, DynamoDB, Route53"
echo "   • AWS サービス: API Gateway, SES, CloudWatch, Cost Explorer"
echo "   • AWS サービス: Bedrock, SageMaker"
echo ""
echo "🚀 Gateway は MCP ツール呼び出しの準備ができました！"
echo "   AgentCore エージェントで Gateway URL を使用してください"
echo "   ツールは AWS 操作の自然言語クエリを受け付けます"
echo ""
echo "🚀 次のステップ:"
echo "   1. ./05-deploy-diy.sh を実行して DIY エージェントランタイムをデプロイ"
echo "   2. ./06-deploy-sdk.sh を実行して SDK エージェントランタイムをデプロイ"
echo "   3. エージェントは Gateway を使用して AWS ツールにアクセスします"