#!/bin/bash

# SAM と ZIP パッケージングを使用して MCP Tool Lambda 関数をデプロイ (Docker 不要)
echo "🚀 MCP Tool Lambda 関数をデプロイ中 (ZIP ベース、Docker 不要)..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"  # Go up one level to reach AgentCore root
RUNTIME_DIR="${PROJECT_DIR}/agentcore-runtime"  # agentcore-runtime directory

# Load configuration from consolidated config files
CONFIG_DIR="${PROJECT_DIR}/config"

# 静的設定ファイルが存在するか確認
if [[ ! -f "${CONFIG_DIR}/static-config.yaml" ]]; then
    echo "❌ 設定ファイルが見つかりません: ${CONFIG_DIR}/static-config.yaml"
    exit 1
fi

# Extract values from YAML (fallback method if yq not available)
get_yaml_value() {
    local key="$1"
    local file="$2"
    # Handle nested YAML keys with proper indentation
    grep "  $key:" "$file" | head -1 | sed 's/.*: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' | xargs
}

REGION=$(get_yaml_value "region" "${CONFIG_DIR}/static-config.yaml")
ACCOUNT_ID=$(get_yaml_value "account_id" "${CONFIG_DIR}/static-config.yaml")

if [[ -z "$REGION" || -z "$ACCOUNT_ID" ]]; then
    echo "❌ static-config.yaml から region または account_id を読み取れませんでした"
    exit 1
fi

STACK_NAME="bac-mcp-stack"

echo "📝 設定:"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
echo "   スタック名: $STACK_NAME"
echo "   デプロイタイプ: ZIP ベース (Docker 不要)"
echo ""

# SSO から AWS 認証情報を取得
echo "🔐 AWS 認証情報を取得中..."
if [ -n "$AWS_PROFILE" ]; then
    echo "AWS プロファイルを使用: $AWS_PROFILE"
else
    echo "デフォルトの AWS 認証情報を使用"
fi

# Use configured AWS profile if specified in static config
AWS_PROFILE_CONFIG=$(grep "aws_profile:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*aws_profile: *["'\'']*\([^"'\''#]*\)["'\'']*.*$/\1/' | xargs 2>/dev/null)
if [[ -n "$AWS_PROFILE_CONFIG" && "$AWS_PROFILE_CONFIG" != "\"\"" && "$AWS_PROFILE_CONFIG" != "''" ]]; then
    echo "設定済み AWS プロファイルを使用: $AWS_PROFILE_CONFIG"
    export AWS_PROFILE="$AWS_PROFILE_CONFIG"
fi

# SAM がインストールされているか確認
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI がインストールされていません。SAM CLI をインストールしてください:"
    echo "   https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi

echo "✅ SAM CLI 検出: $(sam --version)"

# Python が利用可能か確認
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 がインストールされていません。Python 3 をインストールしてください。"
    exit 1
fi

echo "✅ Python 検出: $(python3 --version)"

# Change to MCP tool directory
cd "${SCRIPT_DIR}"

# ZIP テンプレートが存在するか確認
if [[ ! -f "mcp-tool-template-zip.yaml" ]]; then
    echo "❌ ZIP ベース SAM テンプレートが見つかりません: mcp-tool-template-zip.yaml"
    exit 1
fi

echo "✅ ZIP ベース SAM テンプレート検出: mcp-tool-template-zip.yaml"

# 既存スタックを削除して新規デプロイを確保
echo "🧹 新規デプロイを確認中..."

# スタックが存在する場合は新規デプロイのため削除
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &>/dev/null; then
    echo "   📦 既存の CloudFormation スタックを検出: $STACK_NAME"
    echo "   🔄 新規デプロイのため既存スタックを削除中..."

    # CloudFormation スタックを削除
    echo "   🗑️  CloudFormation スタックを削除中..."
    aws cloudformation delete-stack \
        --stack-name "$STACK_NAME" \
        --region "$REGION"

    # スタック削除の完了を待機
    echo "   ⏳ スタック削除の完了を待機中..."
    aws cloudformation wait stack-delete-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"

    echo "   ✅ スタックの削除が完了しました"
else
    echo "   ℹ️  既存スタックなし、新規デプロイを続行"
fi

# SAM ビルドキャッシュをクリーン
echo "🧹 SAM ビルドキャッシュをクリーン中..."
if [[ -d ".aws-sam" ]]; then
    rm -rf .aws-sam
    echo "   ✅ SAM ビルドキャッシュをクリアしました"
else
    echo "   ℹ️  クリアする SAM ビルドキャッシュなし"
fi

# Lambda 関数をパッケージング
echo "📦 Lambda 関数をパッケージング中..."
if ! python3 package_for_lambda.py; then
    echo "❌ Lambda パッケージングに失敗しました"
    exit 1
fi

echo "✅ Lambda パッケージングが完了しました"

# SAM アプリケーションをビルド
echo "🔨 SAM アプリケーションをビルド中..."
if ! sam build --template-file mcp-tool-template-zip.yaml --no-cached; then
    echo "❌ SAM ビルドに失敗しました"
    exit 1
fi

echo "✅ SAM ビルドが完了しました"

# SAM アプリケーションをデプロイ
echo "📤 SAM アプリケーションをデプロイ中..."
if sam deploy \
    --template-file mcp-tool-template-zip.yaml \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --parameter-overrides "Environment=prod" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --resolve-s3 \
    --no-fail-on-empty-changeset; then
    echo "✅ SAM デプロイが完了しました"
else
    echo "❌ SAM デプロイに失敗しました"
    exit 1
fi

# CloudFormation スタック出力から Lambda 関数 ARN を取得
echo "📋 Lambda 関数の詳細を取得中..."
FUNCTION_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='MCPToolFunctionArn'].OutputValue" \
    --output text)

FUNCTION_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='MCPToolFunctionName'].OutputValue" \
    --output text)

FUNCTION_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='MCPToolFunctionRoleArn'].OutputValue" \
    --output text)

GATEWAY_EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='BedrockAgentCoreGatewayExecutionRoleArn'].OutputValue" \
    --output text)

if [[ -z "$FUNCTION_ARN" || "$FUNCTION_ARN" == "None" ]]; then
    echo "❌ CloudFormation スタックから Lambda 関数 ARN を取得できませんでした"
    exit 1
fi

if [[ -z "$GATEWAY_EXECUTION_ROLE_ARN" || "$GATEWAY_EXECUTION_ROLE_ARN" == "None" ]]; then
    echo "❌ CloudFormation スタックから Gateway 実行ロール ARN を取得できませんでした"
    exit 1
fi

# Lambda の詳細で動的設定ファイルを更新
echo "📝 Lambda の詳細で動的設定を更新中..."

# 動的設定の mcp_lambda セクションを更新
DYNAMIC_CONFIG="${CONFIG_DIR}/dynamic-config.yaml"

# 動的設定ファイルが存在するか確認
if [[ ! -f "$DYNAMIC_CONFIG" ]]; then
    echo "❌ 動的設定ファイルが見つかりません: $DYNAMIC_CONFIG"
    exit 1
fi

# sed を使用して mcp_lambda セクションを更新 (ARN の / に対応するため | を区切り文字として使用)
echo "   📝 dynamic-config.yaml の mcp_lambda セクションを更新中..."

sed -i '' \
    -e "s|function_name: \"\"|function_name: \"$FUNCTION_NAME\"|" \
    -e "s|function_arn: \"\"|function_arn: \"$FUNCTION_ARN\"|" \
    -e "s|role_arn: \"\"|role_arn: \"$FUNCTION_ROLE_ARN\"|" \
    -e "s|stack_name: \"\"|stack_name: \"$STACK_NAME\"|" \
    -e "s|gateway_execution_role_arn: \"\"|gateway_execution_role_arn: \"$GATEWAY_EXECUTION_ROLE_ARN\"|" \
    "$DYNAMIC_CONFIG"

echo "✅ Lambda の詳細で設定を更新しました"

# Lambda 関数をテスト
echo "🧪 Lambda 関数をテスト中..."
TEST_PAYLOAD='{"name": "AgentCore"}'

if aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --payload "$TEST_PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    /tmp/lambda-test-response.json > /dev/null; then
    
    echo "✅ Lambda 関数のテストが成功しました"
    echo "   レスポンス: $(cat /tmp/lambda-test-response.json)"
    rm -f /tmp/lambda-test-response.json
else
    echo "⚠️  Lambda 関数のテストに失敗しました (ツール名の抽出に失敗した場合は想定内の動作です)"
fi

echo ""
echo "🎉 MCP Tool Lambda デプロイ完了！"
echo "======================================"
echo "✅ Lambda 関数がデプロイおよび設定されました (ZIP ベース、Docker 不要)"
echo ""
echo "📋 デプロイの詳細:"
echo "   • 関数名: $FUNCTION_NAME"
echo "   • 関数 ARN: $FUNCTION_ARN"
echo "   • Lambda 関数ロール ARN: $FUNCTION_ROLE_ARN"
echo "   • Gateway 実行ロール ARN: $GATEWAY_EXECUTION_ROLE_ARN"
echo "   • スタック名: $STACK_NAME"
echo "   • リージョン: $REGION"
echo "   • デプロイタイプ: ZIP ベース (Docker キャッシュの問題なし)"
echo ""
echo "📋 デプロイされたもの:"
echo "   • MCP ツールハンドラー付き Lambda 関数 (ZIP パッケージ)"
echo "   • Bedrock と AWS サービスの権限を持つ IAM ロール"
echo "   • 関数ログ用 CloudWatch ロググループ"
echo "   • SAM 管理デプロイインフラストラクチャ"
echo ""
echo "🚀 次のステップ:"
echo "   ./05-create-gateway-targets.sh を実行して AgentCore Gateway とターゲットを作成"
echo "   Lambda 関数は MCP ツール呼び出しを処理する準備ができています"
echo ""
echo "💡 関数の機能:"
echo "   • 基本ツール: hello_world, get_time"
echo "   • AWS サービスツール: EC2, S3, Lambda, RDS および 16 以上のサービス"
echo "   • Strands Agent による自然言語クエリ処理"
echo ""
echo "🔧 デプロイの特徴:"
echo "   • ZIP ベースデプロイにより Docker キャッシュの問題を排除"
echo "   • Lambda x86_64 用アーキテクチャ固有の依存関係インストール"
echo "   • 新規デプロイのための自動スタッククリーンアップ"
echo "   • Docker 依存関係不要"
echo "   • API Gateway なし (MCP Gateway 統合用 Lambda のみ)"
