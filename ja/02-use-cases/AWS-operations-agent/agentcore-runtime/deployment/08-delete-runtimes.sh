#!/bin/bash

# Delete all AgentCore Runtimes
echo "🗑️  すべての AgentCore ランタイムを削除中..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
RUNTIME_DIR="$(dirname "$SCRIPT_DIR")"  # agentcore-runtime directory
CONFIG_DIR="${PROJECT_DIR}/config"

# Load configuration from YAML (fallback if yq not available)
if command -v yq >/dev/null 2>&1; then
    REGION=$(yq eval '.aws.region' "${CONFIG_DIR}/static-config.yaml")
    ACCOUNT_ID=$(yq eval '.aws.account_id' "${CONFIG_DIR}/static-config.yaml")
else
    echo "⚠️  yq が見つかりません。既存の設定からデフォルト値を使用します"
    # Fallback: extract from YAML using grep/sed
    REGION=$(grep "region:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*region: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ACCOUNT_ID=$(grep "account_id:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*account_id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
fi

echo "📝 設定:"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
echo ""

# Get AWS credentials
echo "🔐 AWS 認証情報を取得中..."
if [ -n "$AWS_PROFILE" ]; then
    echo "   AWS プロファイルを使用: $AWS_PROFILE"
    aws configure list --profile "$AWS_PROFILE"
else
    echo "   デフォルトの AWS 認証情報を使用"
    aws configure list
fi

# Check AWS credentials
echo "🔍 AWS 認証情報を確認中..."
if aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
    CALLER_IDENTITY=$(aws sts get-caller-identity --region "$REGION" 2>/dev/null)
    CURRENT_ACCOUNT=$(echo "$CALLER_IDENTITY" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)
    echo "✅ AWS 認証情報が設定されています"
    echo "   現在のアカウント: $CURRENT_ACCOUNT"
    echo "   ターゲットアカウント: $ACCOUNT_ID"

    if [ "$CURRENT_ACCOUNT" != "$ACCOUNT_ID" ]; then
        echo "⚠️  警告: 現在のアカウント ($CURRENT_ACCOUNT) が設定のアカウント ($ACCOUNT_ID) と異なります"
        echo "   現在のアカウント認証情報で続行します..."
    fi
else
    echo "❌ AWS 認証情報が設定されていないか無効です"
    echo "   実行してください: aws configure または aws sso login --profile <your-profile>"
    echo "   現在の AWS 設定:"
    aws configure list
    exit 1
fi
echo ""

# Function to delete runtime
delete_runtime() {
    local runtime_arn="$1"
    local runtime_name="$2"

    if [ -z "$runtime_arn" ]; then
        echo "   ⚠️  $runtime_name ランタイム ARN が見つかりません - スキップします"
        return 0
    fi

    # Extract runtime ID from ARN (format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id)
    local runtime_id=$(echo "$runtime_arn" | sed 's|.*runtime/||')

    echo "🗑️  $runtime_name ランタイムを削除中..."
    echo "   ARN: $runtime_arn"
    echo "   ID: $runtime_id"

    # Check if runtime exists first
    if ! aws bedrock-agentcore-control get-agent-runtime \
        --agent-runtime-id "$runtime_id" \
        --region "$REGION" >/dev/null 2>&1; then
        echo "   ℹ️  $runtime_name ランタイムが見つからないか、既に削除されています"
        return 0
    fi

    # Delete the runtime
    if aws bedrock-agentcore-control delete-agent-runtime \
        --agent-runtime-id "$runtime_id" \
        --region "$REGION" 2>/dev/null; then
        echo "   ✅ $runtime_name ランタイムの削除を開始しました"

        # Wait for deletion to complete
        echo "   ⏳ $runtime_name ランタイムの削除完了を待機中..."
        local max_attempts=30
        local attempt=1

        while [ $attempt -le $max_attempts ]; do
            if ! aws bedrock-agentcore-control get-agent-runtime \
                --agent-runtime-id "$runtime_id" \
                --region "$REGION" >/dev/null 2>&1; then
                echo "   ✅ $runtime_name ランタイムを正常に削除しました"
                return 0
            fi

            echo "   ⏳ 試行 $attempt/$max_attempts - $runtime_name ランタイムはまだ存在します..."
            sleep 10
            ((attempt++))
        done

        echo "   ⚠️  $runtime_name ランタイムの削除がタイムアウト - まだ進行中の可能性があります"
        return 1
    else
        echo "   ❌ $runtime_name ランタイムの削除に失敗しました"
        echo "   💡 ランタイムが既に削除されている場合は正常です"
        return 1
    fi
}

# Get runtime ARNs from dynamic configuration
echo "📖 動的設定からランタイム ARN を読み込み中..."
DYNAMIC_CONFIG="${CONFIG_DIR}/dynamic-config.yaml"

if [ -f "$DYNAMIC_CONFIG" ]; then
    if command -v yq >/dev/null 2>&1; then
        DIY_RUNTIME_ARN=$(yq eval '.runtime.diy_agent.arn' "$DYNAMIC_CONFIG")
        SDK_RUNTIME_ARN=$(yq eval '.runtime.sdk_agent.arn' "$DYNAMIC_CONFIG")
    else
        # Fallback parsing
        DIY_RUNTIME_ARN=$(grep -A 10 "diy_agent:" "$DYNAMIC_CONFIG" | grep "arn:" | head -1 | sed 's/.*arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
        SDK_RUNTIME_ARN=$(grep -A 10 "sdk_agent:" "$DYNAMIC_CONFIG" | grep "arn:" | head -1 | sed 's/.*arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    fi

    # Clean up empty values
    [ "$DIY_RUNTIME_ARN" = "null" ] && DIY_RUNTIME_ARN=""
    [ "$SDK_RUNTIME_ARN" = "null" ] && SDK_RUNTIME_ARN=""

    echo "   DIY ランタイム ARN: ${DIY_RUNTIME_ARN:-'未設定'}"
    echo "   SDK ランタイム ARN: ${SDK_RUNTIME_ARN:-'未設定'}"
else
    echo "   ⚠️  動的設定ファイルが見つかりません: $DYNAMIC_CONFIG"
    DIY_RUNTIME_ARN=""
    SDK_RUNTIME_ARN=""
fi

echo ""

# List all existing runtimes for reference
echo "📋 アカウント内のすべての既存ランタイムを一覧表示中..."
if aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" >/dev/null 2>&1; then
    runtime_list=$(aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" --query 'agentRuntimes[*].{Name:agentRuntimeName,ID:agentRuntimeId,Status:status}' --output table 2>/dev/null)
    if [ -n "$runtime_list" ] && echo "$runtime_list" | grep -q "agentcoreDIYTest\|bac_runtime"; then
        echo "$runtime_list"
    else
        echo "   ℹ️  アカウントにランタイムが見つかりません"
    fi
else
    echo "   ⚠️  ランタイムを一覧表示できません (権限の問題の可能性があります)"
fi

echo ""

# Delete runtimes
echo "🗑️  ランタイム削除プロセスを開始中..."
echo ""

# Delete DIY runtime
if [ -n "$DIY_RUNTIME_ARN" ]; then
    delete_runtime "$DIY_RUNTIME_ARN" "DIY"
else
    echo "⚠️  削除する DIY ランタイムが見つかりません"
fi

echo ""

# Delete SDK runtime
if [ -n "$SDK_RUNTIME_ARN" ]; then
    delete_runtime "$SDK_RUNTIME_ARN" "SDK"
else
    echo "⚠️  削除する SDK ランタイムが見つかりません"
fi

echo ""

# Update dynamic configuration to clear runtime ARNs
echo "📝 ランタイム ARN をクリアするために動的設定を更新中..."
if command -v yq >/dev/null 2>&1; then
    yq eval '.runtime.diy_agent.arn = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.diy_agent.ecr_uri = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.diy_agent.endpoint_arn = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.sdk_agent.arn = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.sdk_agent.ecr_uri = ""' -i "$DYNAMIC_CONFIG"
    yq eval '.runtime.sdk_agent.endpoint_arn = ""' -i "$DYNAMIC_CONFIG"
    echo "   ✅ 動的設定を更新 - ランタイム ARN と ECR URI をクリアしました"
else
    echo "   ⚠️  yq が見つかりません - sed フォールバックでランタイムフィールドをクリアします"
    # Fallback: use sed to clear the fields
    sed -i '' \
        -e 's|arn: "arn:aws:bedrock-agentcore:.*"|arn: ""|g' \
        -e 's|ecr_uri: ".*\.dkr\.ecr\..*"|ecr_uri: ""|g' \
        -e 's|endpoint_arn: "arn:aws:bedrock-agentcore:.*"|endpoint_arn: ""|g' \
        "$DYNAMIC_CONFIG"
    echo "   ✅ 動的設定を更新 - ランタイム ARN と ECR URI をクリアしました"
fi

echo ""

# Optional: Clean up ECR repositories
echo "🧹 オプション: ECR リポジトリのクリーンアップ..."
echo "   Docker イメージを削除しますが、リポジトリは保持します"

ECR_REPOS=("bac-runtime-repo-diy" "bac-runtime-repo-sdk")

for repo in "${ECR_REPOS[@]}"; do
    echo "   ECR リポジトリを確認中: $repo"

    # List images in repository
    if aws ecr describe-images --repository-name "$repo" --region "$REGION" >/dev/null 2>&1; then
        echo "   📦 ECR リポジトリを検出: $repo"

        # Get image digests
        image_digests=$(aws ecr list-images --repository-name "$repo" --region "$REGION" --query 'imageIds[*].imageDigest' --output text 2>/dev/null)

        if [ -n "$image_digests" ] && [ "$image_digests" != "None" ]; then
            echo "   🗑️  $repo からイメージを削除中..."
            for digest in $image_digests; do
                aws ecr batch-delete-image \
                    --repository-name "$repo" \
                    --image-ids imageDigest="$digest" \
                    --region "$REGION" >/dev/null 2>&1
            done
            echo "   ✅ $repo からイメージを削除しました"
        else
            echo "   ℹ️  $repo にイメージが見つかりません"
        fi
    else
        echo "   ℹ️  ECR リポジトリ $repo が見つからないか、アクセスできません"
    fi
done

echo ""
echo "✅ ランタイムのクリーンアップが完了しました！"
echo ""
echo "📋 概要:"
echo "   • すべての AgentCore ランタイムを削除"
echo "   • 動的設定からランタイム ARN をクリア"
echo "   • ECR リポジトリのイメージをクリーンアップ"
echo ""
echo "💡 次のステップ:"
echo "   • 09-delete-all-gateways-targets.sh を実行して Gateway とターゲットを削除"
echo "   • 10-delete-mcp-tool-deployment.sh を実行して MCP Lambda を削除"
echo "   • 11-delete-oauth-provider.sh を実行して完全にクリーンアップ"
echo "   • 12-delete-memory.sh を実行してメモリを削除"
