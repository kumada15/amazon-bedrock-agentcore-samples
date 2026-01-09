#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
DASHBOARD_NAME="${DASHBOARD_NAME:-AgentCore-Observability-Demo}"
LOG_GROUP_NAME="${LOG_GROUP_NAME:-/aws/agentcore/traces}"
FORCE=false

# Help text
show_help() {
    cat << EOF
Clean up resources created by the AgentCore observability demo.

This script removes:
1. Deployed agent from AgentCore Runtime
2. CloudWatch dashboard
3. CloudWatch log groups (optional)
4. Local configuration files

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -r, --region REGION     AWS region (default: us-east-1)
    -f, --force             Skip confirmation prompts
    -k, --keep-logs         Keep CloudWatch log groups

Environment Variables:
    AWS_REGION              AWS region for resources
    DASHBOARD_NAME          CloudWatch dashboard name
    LOG_GROUP_NAME          CloudWatch log group name

Example:
    # Interactive cleanup
    ./cleanup.sh

    # Force cleanup without prompts
    ./cleanup.sh --force

    # Cleanup but keep logs
    ./cleanup.sh --keep-logs

EOF
}

KEEP_LOGS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -k|--keep-logs)
            KEEP_LOGS=true
            shift
            ;;
        *)
            echo "不明なオプション: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "========================================"
echo "AGENTCORE OBSERVABILITY クリーンアップ"
echo "========================================"
echo ""
echo "以下のリソースが削除されます:"
echo ""

# 存在するものをチェック
AGENT_ID=""
if [ -f "$SCRIPT_DIR/.deployment_metadata.json" ]; then
    AGENT_ID=$(jq -r '.agent_id' "$SCRIPT_DIR/.deployment_metadata.json")
    echo "- AgentCore Runtime エージェント: $AGENT_ID"
fi

echo "- CloudWatch ダッシュボード: $DASHBOARD_NAME"

if [ "$KEEP_LOGS" = false ]; then
    echo "- CloudWatch ロググループ: $LOG_GROUP_NAME"
else
    echo "- CloudWatch ロググループ: （保持）"
fi

echo "- ローカル設定ファイル"
echo ""
echo "リージョン: $AWS_REGION"
echo ""

if [ "$FORCE" = false ]; then
    read -p "クリーンアップを続行しますか？ (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "クリーンアップがキャンセルされました"
        exit 0
    fi
    echo ""
fi

# エージェントを削除
if [ -n "$AGENT_ID" ]; then
    echo "エージェントを削除中: $AGENT_ID"
    uv run python "$SCRIPT_DIR/delete_agent.py" \
        --region "$AWS_REGION" \
        --agent-id "$AGENT_ID" \
        2>/dev/null || echo "注意: エージェントは既に削除されているか見つかりませんでした"
    echo "エージェントの削除が完了しました"
fi

# CloudWatch ダッシュボードを削除
echo "CloudWatch ダッシュボードを削除中: $DASHBOARD_NAME"
aws cloudwatch delete-dashboards \
    --dashboard-names "$DASHBOARD_NAME" \
    --region "$AWS_REGION" \
    2>/dev/null || echo "注意: ダッシュボードが存在しない可能性があります"

# ロググループを削除（保持しない場合）
if [ "$KEEP_LOGS" = false ]; then
    echo "CloudWatch ロググループを削除中: $LOG_GROUP_NAME"
    aws logs delete-log-group \
        --log-group-name "$LOG_GROUP_NAME" \
        --region "$AWS_REGION" \
        2>/dev/null || echo "注意: ロググループが存在しない可能性があります"
fi

# ローカルファイルを削除
echo "ローカル設定ファイルをクリーンアップ中..."

if [ -f "$SCRIPT_DIR/.deployment_metadata.json" ]; then
    rm "$SCRIPT_DIR/.deployment_metadata.json"
    echo "削除しました: .deployment_metadata.json"
fi

if [ -f "$SCRIPT_DIR/cloudwatch-urls.txt" ]; then
    rm "$SCRIPT_DIR/cloudwatch-urls.txt"
    echo "削除しました: cloudwatch-urls.txt"
fi

if [ -f "$SCRIPT_DIR/xray-permissions.json" ]; then
    rm "$SCRIPT_DIR/xray-permissions.json"
    echo "削除しました: xray-permissions.json"
fi

if [ -f "$SCRIPT_DIR/braintrust-usage.md" ]; then
    rm "$SCRIPT_DIR/braintrust-usage.md"
    echo "削除しました: braintrust-usage.md"
fi

echo ""
echo "========================================"
echo "クリーンアップ完了"
echo "========================================"
echo ""
echo "削除されたリソース:"
if [ -n "$AGENT_ID" ]; then
    echo "- エージェント: $AGENT_ID"
fi
echo "- ダッシュボード: $DASHBOARD_NAME"
if [ "$KEEP_LOGS" = false ]; then
    echo "- ロググループ: $LOG_GROUP_NAME"
fi
echo "- ローカル設定ファイル"
echo ""
echo "再デプロイするには、次を実行してください:"
echo "  ./deploy_agent.sh"
echo ""
