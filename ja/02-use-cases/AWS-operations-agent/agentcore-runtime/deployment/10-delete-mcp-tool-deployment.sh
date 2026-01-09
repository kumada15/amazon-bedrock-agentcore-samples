#!/bin/bash

# MCP Tool Lambda デプロイを削除 (ZIP ベース)
echo "🗑️  MCP Tool Lambda デプロイを削除中 (ZIP ベース)..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
CONFIG_DIR="${PROJECT_DIR}/config"

# Load configuration from YAML (fallback if yq not available)
if command -v yq >/dev/null 2>&1; then
    REGION=$(yq eval '.aws.region' "${CONFIG_DIR}/static-config.yaml")
    ACCOUNT_ID=$(yq eval '.aws.account_id' "${CONFIG_DIR}/static-config.yaml")
    STACK_NAME=$(yq eval '.mcp_lambda.stack_name' "${CONFIG_DIR}/dynamic-config.yaml" 2>/dev/null)
else
    echo "⚠️  yq が見つかりません、既存の設定からデフォルト値を使用"
    # Fallback: extract from YAML using grep/sed
    REGION=$(grep "region:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*region: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ACCOUNT_ID=$(grep "account_id:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*account_id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    STACK_NAME=$(grep "stack_name:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*stack_name: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' 2>/dev/null)
fi

# 設定に見つからない場合のデフォルトスタック名 (ZIP デプロイスクリプトと一致)
if [[ -z "$STACK_NAME" || "$STACK_NAME" == "null" ]]; then
    STACK_NAME="bac-mcp-stack"
    echo "⚠️  設定にスタック名が見つかりません、デフォルトを使用: $STACK_NAME"
fi

echo "📝 設定:"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
echo "   スタック名: $STACK_NAME"
echo "   デプロイタイプ: ZIP ベース (Docker/ECR なし)"
echo ""

# AWS 認証情報を取得
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

# Function to check if stack exists
check_stack_exists() {
    local stack_name="$1"
    aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" --output text --query 'Stacks[0].StackStatus' 2>/dev/null
}

# 削除前にスタックリソースを取得する関数
get_stack_resources() {
    local stack_name="$1"
    echo "📋 削除前にスタックリソースを取得中..."

    STACK_RESOURCES=$(aws cloudformation describe-stack-resources \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --output json 2>/dev/null || echo "{}")

    if [[ "$STACK_RESOURCES" != "{}" ]]; then
        echo "   スタック内のリソース:"
        echo "$STACK_RESOURCES" | jq -r '.StackResources[]? | "      • \(.ResourceType): \(.LogicalResourceId) (\(.PhysicalResourceId // "N/A"))"' 2>/dev/null || echo "      • リソースを解析できませんでした"
    else
        echo "   ⚠️  スタックリソースを取得できませんでした"
    fi
}

# 動的設定をクリーンアップする関数
cleanup_dynamic_config() {
    echo "🧹 動的設定をクリーンアップ中..."

    DYNAMIC_CONFIG="${CONFIG_DIR}/dynamic-config.yaml"

    if [[ -f "$DYNAMIC_CONFIG" ]]; then
        if command -v yq >/dev/null 2>&1; then
            yq eval ".mcp_lambda.function_arn = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.function_name = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.function_role_arn = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.gateway_execution_role_arn = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.role_arn = \"\"" -i "$DYNAMIC_CONFIG"
            yq eval ".mcp_lambda.stack_name = \"\"" -i "$DYNAMIC_CONFIG"
        else
            # フォールバック: sed を使用して手動更新
            sed -i.bak "s|function_arn: \".*\"|function_arn: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|function_name: \".*\"|function_name: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|function_role_arn: \".*\"|function_role_arn: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|gateway_execution_role_arn: \".*\"|gateway_execution_role_arn: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|role_arn: \".*\"|role_arn: \"\"|" "$DYNAMIC_CONFIG"
            sed -i.bak "s|stack_name: \".*\"|stack_name: \"\"|" "$DYNAMIC_CONFIG"

            # バックアップファイルを削除
            rm -f "${DYNAMIC_CONFIG}.bak"
        fi

        echo "✅ 動的設定をクリアしました"
    else
        echo "⚠️  動的設定ファイルが見つかりません: $DYNAMIC_CONFIG"
    fi
}

# ZIP デプロイアーティファクトをクリーンアップする関数
cleanup_zip_artifacts() {
    echo "🧹 ZIP デプロイアーティファクトをクリーンアップ中..."

    MCP_LAMBDA_DIR="${PROJECT_DIR}/mcp-tool-lambda"

    if [[ -d "$MCP_LAMBDA_DIR" ]]; then
        # パッケージングディレクトリをクリーンアップ
        if [[ -d "${MCP_LAMBDA_DIR}/packaging" ]]; then
            echo "   パッケージングディレクトリを削除中..."
            rm -rf "${MCP_LAMBDA_DIR}/packaging"
            echo "   ✅ パッケージングディレクトリを削除しました"
        fi

        # SAM ビルドアーティファクトをクリーンアップ
        if [[ -d "${MCP_LAMBDA_DIR}/.aws-sam" ]]; then
            echo "   SAM ビルドアーティファクトを削除中..."
            rm -rf "${MCP_LAMBDA_DIR}/.aws-sam"
            echo "   ✅ SAM ビルドアーティファクトを削除しました"
        fi

        # samconfig.toml が存在する場合は削除
        if [[ -f "${MCP_LAMBDA_DIR}/samconfig.toml" ]]; then
            echo "   SAM 設定を削除中..."
            rm -f "${MCP_LAMBDA_DIR}/samconfig.toml"
            echo "   ✅ SAM 設定を削除しました"
        fi
    else
        echo "   ⚠️  MCP Lambda ディレクトリが見つかりません: $MCP_LAMBDA_DIR"
    fi
}

# メイン実行
echo "⚠️  警告: MCP Tool Lambda デプロイが削除されます (ZIP ベース)！"
echo "   削除対象:"
echo "   • Lambda 関数: bac-mcp-tool"
echo "   • IAM ロール: MCPToolFunctionRole および BedrockAgentCoreGatewayExecutionRole"
echo "   • CloudWatch ロググループ: /aws/lambda/bac-mcp-tool"
echo "   • CloudFormation スタック: $STACK_NAME"
echo "   • ローカル ZIP パッケージングアーティファクト"
echo "   • SAM ビルドアーティファクト"
echo ""
echo "   この操作は元に戻せません。"
echo ""
read -p "続行してもよろしいですか？ (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 MCP Tool 削除プロセスを開始中..."
    echo ""

    # スタックが存在するか確認
    STACK_STATUS=$(check_stack_exists "$STACK_NAME")

    if [[ -n "$STACK_STATUS" ]]; then
        echo "✅ CloudFormation スタックを検出: $STACK_NAME (ステータス: $STACK_STATUS)"
        echo ""

        # 削除前にスタックリソースを取得
        get_stack_resources "$STACK_NAME"
        echo ""

        # CloudFormation スタックを削除
        echo "🗑️  CloudFormation スタックを削除中: $STACK_NAME..."
        aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"

        if [[ $? -eq 0 ]]; then
            echo "✅ スタック削除を正常に開始しました"
            echo ""
            echo "⏳ スタック削除の完了を待機中..."
            echo "   数分かかる場合があります..."

            # スタック削除の完了を待機
            aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"

            if [[ $? -eq 0 ]]; then
                echo "✅ スタック削除が正常に完了しました"
            else
                echo "⚠️  スタック削除が失敗またはタイムアウトした可能性があります"
                echo "   AWS コンソールで現在のステータスを確認してください"
            fi
        else
            echo "❌ スタック削除の開始に失敗しました"
            exit 1
        fi
    else
        echo "⚠️  CloudFormation スタックが見つかりません: $STACK_NAME"
        echo "   スタックは既に削除されている可能性があります"
    fi

    echo ""

    # 動的設定をクリーンアップ
    cleanup_dynamic_config

    echo ""

    # ZIP デプロイアーティファクトをクリーンアップ
    cleanup_zip_artifacts

    echo ""
    echo "🎉 MCP Tool Lambda 削除完了！"
    echo "===================================="
    echo ""
    echo "✅ CloudFormation スタックを削除しました: $STACK_NAME"
    echo "✅ 動的設定をクリアしました"
    echo "✅ ZIP デプロイアーティファクトをクリーンアップしました"
    echo ""
    echo "📋 削除されたもの:"
    echo "   • Lambda 関数: bac-mcp-tool"
    echo "   • IAM ロール: MCPToolFunctionRole (Lambda 実行用)"
    echo "   • IAM ロール: BedrockAgentCoreGatewayExecutionRole (Gateway 用)"
    echo "   • CloudWatch ロググループ: /aws/lambda/bac-mcp-tool"
    echo "   • CloudFormation スタック: $STACK_NAME"
    echo "   • ローカルパッケージングディレクトリと ZIP アーティファクト"
    echo "   • SAM ビルドアーティファクト (.aws-sam ディレクトリ)"
    echo ""
    echo "💡 注意:"
    echo "   • AgentCore Gateway とターゲットは削除されていません"
    echo "   • OAuth プロバイダー設定は引き続き利用可能"
    echo "   • 静的設定は変更されていません"
    echo "   • ECR リポジトリは関係ありません (ZIP デプロイ)"
    echo ""
    echo ""
else
    echo ""
    echo "❌ ユーザーによって削除がキャンセルされました"
    echo ""
fi
