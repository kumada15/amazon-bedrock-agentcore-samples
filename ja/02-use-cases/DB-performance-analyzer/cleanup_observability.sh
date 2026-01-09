#!/bin/bash
set -e

echo "=== AgentCore Gateway オブザーバビリティをクリーンアップ中 ==="

# Get the script directory and project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

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

# Function to clean up log groups for a resource
cleanup_log_groups() {
    local resource_id=$1
    local resource_type=$2
    
    echo "$resource_type: $resource_id のロググループをクリーンアップ中"
    
    # Delete resource-specific log group
    if [ "$resource_type" = "gateway" ]; then
        RESOURCE_LOG_GROUP="/aws/bedrock-agentcore/gateways/$resource_id"
    elif [ "$resource_type" = "target" ]; then
        RESOURCE_LOG_GROUP="/aws/bedrock-agentcore/targets/$resource_id"
    fi
    
    echo "ロググループを削除中: $RESOURCE_LOG_GROUP"
    aws logs delete-log-group --log-group-name "$RESOURCE_LOG_GROUP" --region $AWS_REGION 2>/dev/null || echo "ロググループ $RESOURCE_LOG_GROUP は存在しないか、削除できませんでした"
    
    echo "$resource_type: $resource_id のロググループクリーンアップが完了しました"
}

# Clean up log groups for gateway
if [ ! -z "$GATEWAY_IDENTIFIER" ]; then
    cleanup_log_groups "$GATEWAY_IDENTIFIER" "gateway"
fi

# Clean up log groups for targets
if [ ! -z "$TARGET_ID" ]; then
    cleanup_log_groups "$TARGET_ID" "target"
fi

if [ ! -z "$PGSTAT_TARGET_ID" ]; then
    cleanup_log_groups "$PGSTAT_TARGET_ID" "target"
fi

echo "\n注意: PutDeliverySource 操作は AgentCore メモリリソースにのみ有効で、Gateway やターゲットには適用されません。"
echo "そのため、配信元や配信先は作成されておらず、クリーンアップの必要はありません。"
echo "\nAgentCore Gateway には配信元を必要としない基本的なオブザーバビリティ機能が組み込まれています。"
echo "Lambda ターゲットを使用した詳細なエンドツーエンドトレースには、Lambda 関数に ADOT 計装が必要です。"

echo "=== AgentCore Gateway オブザーバビリティクリーンアップ完了 ==="