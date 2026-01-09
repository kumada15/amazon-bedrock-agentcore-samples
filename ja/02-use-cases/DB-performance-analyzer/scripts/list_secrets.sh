#!/bin/bash
# List all secrets in the AWS account

# Default region
REGION=${AWS_REGION:-"us-west-2"}
FILTER=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --region)
            REGION="$2"
            shift
            shift
            ;;
        --filter)
            FILTER="$2"
            shift
            shift
            ;;
        *)
            echo "不明なオプション: $1"
            echo "使用法: $0 [--region <region>] [--filter <filter_text>]"
            exit 1
            ;;
    esac
done

echo "リージョン $REGION のすべてのシークレットを一覧表示中..."

# List all secrets
ALL_SECRETS=$(aws secretsmanager list-secrets \
    --region "$REGION" \
    --query "SecretList[].{Name:Name,ARN:ARN}" \
    --output json)

# Display results
if [ -z "$FILTER" ]; then
    echo "$ALL_SECRETS" | jq -r '.[] | "名前: \(.Name)\nARN: \(.ARN)\n"'
    echo "シークレット合計: $(echo "$ALL_SECRETS" | jq '. | length')"
else
    echo "フィルタリング中: $FILTER を含むシークレット"
    FILTERED=$(echo "$ALL_SECRETS" | jq -r --arg FILTER "$FILTER" '[.[] | select(.Name | contains($FILTER))]')
    echo "$FILTERED" | jq -r '.[] | "名前: \(.Name)\nARN: \(.ARN)\n"'
    echo "一致するシークレット合計: $(echo "$FILTERED" | jq '. | length')"
fi