#!/bin/bash
set -e

echo "=== AgentCore Gateway オブザーバビリティをセットアップ中 ==="

# Get the script directory and project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load configurations
if [ -f "$PROJECT_DIR/config/gateway_config.env" ]; then
    source "$PROJECT_DIR/config/gateway_config.env"
fi

if [ -f "$PROJECT_DIR/config/target_config.env" ]; then
    source "$PROJECT_DIR/config/target_config.env"
fi

if [ -f "$PROJECT_DIR/config/pgstat_target_config.env" ]; then
    source "$PROJECT_DIR/config/pgstat_target_config.env"
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
    echo "エラー: $ACCOUNT_ID"
    exit 1
fi

# Step 1: Note about CloudWatch Transaction Search
echo "ステップ 1: CloudWatch Transaction Search..."
echo "注意: CloudWatch コンソールで CloudWatch Transaction Search を有効にする必要があります。"
echo "CloudWatch コンソール > Application Signals > Transaction search に移動し、"
echo "まだ有効になっていない場合は 'Enable Transaction Search' をクリックしてください。"
echo "これはオブザーバビリティに必要な一度限りのセットアップです。"
echo ""
echo "ロググループのセットアップを続行中..."

# Step 2: Create log groups for resources
echo "ステップ 2: リソース用ロググループを作成中..."

# Create log group for gateway
GATEWAY_LOG_GROUP="/aws/bedrock-agentcore/gateways/$GATEWAY_IDENTIFIER"
aws logs create-log-group --log-group-name "$GATEWAY_LOG_GROUP" --region $AWS_REGION || echo "ロググループは既に存在するか、作成できませんでした"

# Create log group for targets
if [ ! -z "$TARGET_ID" ]; then
    TARGET_LOG_GROUP="/aws/bedrock-agentcore/targets/$TARGET_ID"
    aws logs create-log-group --log-group-name "$TARGET_LOG_GROUP" --region $AWS_REGION || echo "ロググループは既に存在するか、作成できませんでした"
fi

if [ ! -z "$PGSTAT_TARGET_ID" ]; then
    PGSTAT_TARGET_LOG_GROUP="/aws/bedrock-agentcore/targets/$PGSTAT_TARGET_ID"
    aws logs create-log-group --log-group-name "$PGSTAT_TARGET_LOG_GROUP" --region $AWS_REGION || echo "ロググループは既に存在するか、作成できませんでした"
fi

# Step 3: Note about delivery sources and destinations
echo "ステップ 3: 配信元と配信先に関する注意..."
echo "注意: PutDeliverySource 操作は AgentCore メモリリソースにのみ有効で、Gateway やターゲットには適用されません。"
echo "エラーメッセージ 'This resource is not allowed for this LogType. Valid options are [memory]' はこの制限を示しています。"
echo "\nただし、AgentCore Gateway には配信元を必要としない組み込みのオブザーバビリティ機能があります。"
echo "Transaction Search が有効な場合、Gateway ログは自動的に CloudWatch に送信され、トレースは X-Ray に送信されます。"
echo "\nGateway とターゲットには適用されないため、配信元/配信先の設定をスキップします。"

echo "\n注意: AgentCore Gateway には基本的な組み込みオブザーバビリティ機能があります。"
echo "基本的なトレースとログを表示するには、CloudWatch コンソールで CloudWatch Transaction Search を有効にする必要があります。"
echo "CloudWatch > Application Signals > Transaction search に移動し、'Enable Transaction Search' をクリックしてください。"
echo "\nLambda ターゲットを使用した詳細なエンドツーエンドトレースには、Lambda 関数を ADOT SDK で計装する必要があります。"

echo "=== AgentCore Gateway オブザーバビリティセットアップ完了 ==="
echo "基本的なオブザーバビリティデータを表示するには、CloudWatch コンソールを開き、以下に移動してください:"
echo "  - Application Signals > Transaction search"
echo "  - Log groups > /aws/bedrock-agentcore/gateways/$GATEWAY_IDENTIFIER"
echo "  - Log groups > /aws/bedrock-agentcore/targets/<target-id>"
echo "  - X-Ray > Traces"
echo ""
echo "注意: 詳細なエンドツーエンドトレースには、Lambda 関数に ADOT 計装が必要です。"