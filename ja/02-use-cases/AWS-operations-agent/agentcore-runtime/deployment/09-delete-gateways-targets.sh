#!/bin/bash

# すべての AgentCore Gateway とターゲットを削除
echo "🗑️  すべての AgentCore Gateway とターゲットを削除中..."

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
    echo "⚠️  yq が見つかりません、既存の設定からデフォルト値を使用"
    # Fallback: extract from YAML using grep/sed
    REGION=$(grep "region:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*region: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
    ACCOUNT_ID=$(grep "account_id:" "${CONFIG_DIR}/static-config.yaml" | head -1 | sed 's/.*account_id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/')
fi

echo "📝 設定:"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
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

# Path to gateway operations scripts
GATEWAY_OPS_DIR="${RUNTIME_DIR}/gateway-ops-scripts"

# Python スクリプトが利用可能か確認する関数
check_gateway_scripts() {
    if [[ ! -d "$GATEWAY_OPS_DIR" ]]; then
        echo "❌ Gateway 操作スクリプトが見つかりません: $GATEWAY_OPS_DIR"
        return 1
    fi

    local required_scripts=("list-gateways.py" "list-targets.py" "delete-gateway.py" "delete-target.py")
    for script in "${required_scripts[@]}"; do
        if [[ ! -f "${GATEWAY_OPS_DIR}/${script}" ]]; then
            echo "⚠️  スクリプトが見つかりません: ${GATEWAY_OPS_DIR}/${script} (AWS CLI にフォールバックします)"
        fi
    done

    echo "✅ Gateway 操作ディレクトリを検出"
    return 0
}

# Gateway 操作スクリプトが利用可能か確認
echo "🔍 Gateway 操作スクリプトを確認中..."
if ! check_gateway_scripts; then
    echo "❌ Gateway 操作スクリプトが利用できません"
    echo "   期待される場所: $GATEWAY_OPS_DIR"
    exit 1
fi

# Python 依存関係を確保するため仮想環境をアクティベート
echo "🐍 Python 仮想環境をアクティベート中..."
cd "${PROJECT_DIR}" && source .venv/bin/activate

# Load current gateway configuration if available
CURRENT_GATEWAY_ID=""
CURRENT_GATEWAY_ARN=""
CURRENT_GATEWAY_URL=""

if command -v yq >/dev/null 2>&1; then
    CURRENT_GATEWAY_ID=$(yq eval '.gateway.id' "${CONFIG_DIR}/dynamic-config.yaml" 2>/dev/null)
    CURRENT_GATEWAY_ARN=$(yq eval '.gateway.arn' "${CONFIG_DIR}/dynamic-config.yaml" 2>/dev/null)
    CURRENT_GATEWAY_URL=$(yq eval '.gateway.url' "${CONFIG_DIR}/dynamic-config.yaml" 2>/dev/null)
else
    CURRENT_GATEWAY_ID=$(grep "id:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*id: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' 2>/dev/null)
    CURRENT_GATEWAY_ARN=$(grep "arn:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*arn: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' 2>/dev/null)
    CURRENT_GATEWAY_URL=$(grep "url:" "${CONFIG_DIR}/dynamic-config.yaml" | head -1 | sed 's/.*url: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' 2>/dev/null)
fi

# 設定済み Gateway があるか確認
if [[ -n "$CURRENT_GATEWAY_ID" && "$CURRENT_GATEWAY_ID" != "null" && "$CURRENT_GATEWAY_ID" != '""' ]]; then
    echo "📋 動的設定で設定済み Gateway を検出:"
    echo "   • Gateway ID: $CURRENT_GATEWAY_ID"
    echo "   • Gateway ARN: $CURRENT_GATEWAY_ARN"
    echo "   • Gateway URL: $CURRENT_GATEWAY_URL"
    echo ""
fi

# Change to gateway ops directory
cd "$GATEWAY_OPS_DIR"

# Gateway のすべてのターゲットを削除する関数
delete_gateway_targets() {
    local gateway_id="$1"
    local gateway_name="$2"

    echo "🎯 Gateway のターゲットを削除中: $gateway_name ($gateway_id)"

    # まず Python スクリプトを試し、失敗したら AWS CLI にフォールバック
    if [[ -f "list-targets.py" ]]; then
        echo "   📋 Python スクリプトでターゲットを一覧表示中..."
        TARGETS_RESPONSE=$(python3 list-targets.py --gateway-id "$gateway_id" 2>/dev/null || echo "")

        if [[ -n "$TARGETS_RESPONSE" ]]; then
            echo "$TARGETS_RESPONSE"

            # ターゲット ID を抽出 (実際の出力形式に応じて調整が必要な場合があります)
            TARGET_IDS=$(echo "$TARGETS_RESPONSE" | grep -o "Target ID: [^[:space:]]*" | cut -d' ' -f3 || echo "")

            if [[ -n "$TARGET_IDS" ]]; then
                echo "   🗑️  削除するターゲットを検出:"
                for target_id in $TARGET_IDS; do
                    echo "      • $target_id"

                    if [[ -f "delete-target.py" ]]; then
                        echo "      🗑️  Python スクリプトでターゲット $target_id を削除中..."
                        python3 delete-target.py --gateway-id "$gateway_id" --target-id "$target_id" --force 2>/dev/null || echo "      ⚠️  ターゲット $target_id の削除に失敗しました"
                    else
                        echo "      🗑️  AWS CLI でターゲット $target_id を削除中..."
                        aws bedrock-agentcore-control delete-gateway-target \
                            --gateway-identifier "$gateway_id" \
                            --target-identifier "$target_id" \
                            --region "$REGION" 2>/dev/null || echo "      ⚠️  ターゲット $target_id の削除に失敗しました"
                    fi
                done
            else
                echo "   ✅ Gateway $gateway_name にターゲットはありません"
            fi
        else
            echo "   ⚠️  Gateway $gateway_name のターゲットを一覧表示できませんでした"
        fi
    else
        echo "   📋 AWS CLI でターゲットを一覧表示中..."
        TARGETS_JSON=$(aws bedrock-agentcore-control list-gateway-targets \
            --gateway-identifier "$gateway_id" \
            --region "$REGION" \
            --output json 2>/dev/null || echo "{}")

        TARGET_IDS=$(echo "$TARGETS_JSON" | jq -r '.items[]?.targetId // empty' 2>/dev/null || echo "")

        if [[ -n "$TARGET_IDS" ]]; then
            echo "   🗑️  削除するターゲットを検出:"
            for target_id in $TARGET_IDS; do
                echo "      • $target_id"
                echo "      🗑️  ターゲット $target_id を削除中..."
                aws bedrock-agentcore-control delete-gateway-target \
                    --gateway-identifier "$gateway_id" \
                    --target-identifier "$target_id" \
                    --region "$REGION" 2>/dev/null || echo "      ⚠️  ターゲット $target_id の削除に失敗しました"
            done
        else
            echo "   ✅ Gateway $gateway_name にターゲットはありません"
        fi
    fi
}

# 特定の設定済み Gateway を削除する関数
delete_configured_gateway() {
    local gateway_id="$1"
    echo "🏗️  設定済み Gateway を削除中: $gateway_id"

    # まずターゲットを削除
    delete_gateway_targets "$gateway_id" "configured-gateway"

    # Gateway を削除
    echo "   🗑️  Gateway $gateway_id を削除中..."
    if [[ -f "delete-gateway.py" ]]; then
        python3 delete-gateway.py --gateway-id "$gateway_id" --force 2>/dev/null || echo "   ⚠️  Gateway $gateway_id の削除に失敗しました"
    else
        aws bedrock-agentcore-control delete-gateway \
            --gateway-identifier "$gateway_id" \
            --region "$REGION" 2>/dev/null || echo "   ⚠️  Gateway $gateway_id の削除に失敗しました"
    fi

    echo "✅ 設定済み Gateway の削除が完了しました"
}

# すべての Gateway を削除する関数
delete_all_gateways() {
    echo "🏗️  すべての Gateway を削除中..."

    # まず Python スクリプトを試し、失敗したら AWS CLI にフォールバック
    if [[ -f "list-gateways.py" ]]; then
        echo "📋 Python スクリプトで Gateway を一覧表示中..."
        GATEWAYS_RESPONSE=$(python3 list-gateways.py 2>/dev/null || echo "")

        if [[ -n "$GATEWAYS_RESPONSE" ]]; then
            echo "$GATEWAYS_RESPONSE"

            # Gateway ID と名前を抽出 (調整が必要な場合があります)
            GATEWAY_INFO=$(echo "$GATEWAYS_RESPONSE" | grep -E "Gateway ID:|Name:" | paste - - | sed 's/.*Gateway ID: *\([^[:space:]]*\).*Name: *\([^[:space:]]*\).*/\1 \2/' || echo "")

            if [[ -n "$GATEWAY_INFO" ]]; then
                echo ""
                echo "🗑️  削除する Gateway を検出:"
                while read -r gateway_id gateway_name; do
                    if [[ -n "$gateway_id" && "$gateway_id" != "null" ]]; then
                        echo "   • $gateway_name ($gateway_id)"

                        # まずターゲットを削除
                        delete_gateway_targets "$gateway_id" "$gateway_name"

                        # Gateway を削除
                        echo "   🗑️  Gateway $gateway_name ($gateway_id) を削除中..."
                        if [[ -f "delete-gateway.py" ]]; then
                            python3 delete-gateway.py --gateway-id "$gateway_id" --force 2>/dev/null || echo "   ⚠️  Gateway $gateway_id の削除に失敗しました"
                        else
                            aws bedrock-agentcore-control delete-gateway \
                                --gateway-identifier "$gateway_id" \
                                --region "$REGION" 2>/dev/null || echo "   ⚠️  Gateway $gateway_id の削除に失敗しました"
                        fi
                    fi
                done <<< "$GATEWAY_INFO"
            else
                echo "✅ 削除する Gateway はありません"
            fi
        else
            echo "⚠️  Python スクリプトで Gateway を一覧表示できませんでした、AWS CLI を試します..."
        fi
    fi

    # Python スクリプトが動作しなかった場合は AWS CLI にフォールバック
    if [[ -z "$GATEWAYS_RESPONSE" ]] || [[ "$GATEWAYS_RESPONSE" == "" ]]; then
        echo "📋 AWS CLI で Gateway を一覧表示中..."
        GATEWAYS_JSON=$(aws bedrock-agentcore-control list-gateways \
            --region "$REGION" \
            --output json 2>/dev/null || echo "{}")

        GATEWAY_IDS=$(echo "$GATEWAYS_JSON" | jq -r '.items[]?.gatewayId // empty' 2>/dev/null || echo "")

        if [[ -n "$GATEWAY_IDS" ]]; then
            echo ""
            echo "🗑️  削除する Gateway を検出:"
            for gateway_id in $GATEWAY_IDS; do
                # Gateway 名を取得
                GATEWAY_NAME=$(echo "$GATEWAYS_JSON" | jq -r ".items[] | select(.gatewayId == \"$gateway_id\") | .name // \"Unknown\"" 2>/dev/null || echo "Unknown")
                echo "   • $GATEWAY_NAME ($gateway_id)"

                # まずターゲットを削除
                delete_gateway_targets "$gateway_id" "$GATEWAY_NAME"

                # Gateway を削除
                echo "   🗑️  Gateway $GATEWAY_NAME ($gateway_id) を削除中..."
                aws bedrock-agentcore-control delete-gateway \
                    --gateway-identifier "$gateway_id" \
                    --region "$REGION" 2>/dev/null || echo "   ⚠️  Gateway $gateway_id の削除に失敗しました"
            done
        else
            echo "✅ 削除する Gateway はありません"
        fi
    fi
}

# メイン実行
if [[ -n "$CURRENT_GATEWAY_ID" && "$CURRENT_GATEWAY_ID" != "null" && "$CURRENT_GATEWAY_ID" != '""' ]]; then
    echo "🤔 削除オプション:"
    echo "   1. 設定済み Gateway のみ削除 ($CURRENT_GATEWAY_ID)"
    echo "   2. アカウント内のすべての Gateway を削除"
    echo ""
    read -p "オプションを選択 (1/2) またはキャンセル (N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[1]$ ]]; then
        echo ""
        echo "⚠️  警告: 設定済み Gateway とそのターゲットが削除されます！"
        echo "   Gateway ID: $CURRENT_GATEWAY_ID"
        echo "   この操作は元に戻せません。"
        echo ""
        read -p "続行してもよろしいですか？ (y/N): " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            echo "🚀 設定済み Gateway の削除を開始中..."
            echo ""
            delete_configured_gateway "$CURRENT_GATEWAY_ID"
        else
            echo ""
            echo "❌ ユーザーによって削除がキャンセルされました"
            echo ""
            exit 0
        fi
    elif [[ $REPLY =~ ^[2]$ ]]; then
        echo ""
        echo "⚠️  警告: アカウント内のすべての AgentCore Gateway とターゲットが削除されます！"
        echo "   この操作は元に戻せません。"
        echo ""
        read -p "続行してもよろしいですか？ (y/N): " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            echo "🚀 すべての Gateway の削除を開始中..."
            echo ""
            delete_all_gateways
        else
            echo ""
            echo "❌ ユーザーによって削除がキャンセルされました"
            echo ""
            exit 0
        fi
    else
        echo ""
        echo "❌ ユーザーによって削除がキャンセルされました"
        echo ""
        exit 0
    fi
else
    echo "⚠️  警告: すべての AgentCore Gateway とターゲットが削除されます！"
    echo "   動的設定に設定済み Gateway が見つかりません。"
    echo "   この操作は元に戻せません。"
    echo ""
    read -p "続行してもよろしいですか？ (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "🚀 削除プロセスを開始中..."
        echo ""

        delete_all_gateways
    else
        echo ""
        echo "❌ ユーザーによって削除がキャンセルされました"
        echo ""
        exit 0
    fi
fi

# クリーンアップ関数 (削除成功後に呼び出される)
cleanup_dynamic_config() {
    echo ""
    echo "🧹 動的設定をクリーンアップ中..."

    # 動的設定から Gateway 情報をクリア
    DYNAMIC_CONFIG="${CONFIG_DIR}/dynamic-config.yaml"
    if command -v yq >/dev/null 2>&1; then
        yq eval ".gateway.arn = \"\"" -i "$DYNAMIC_CONFIG"
        yq eval ".gateway.id = \"\"" -i "$DYNAMIC_CONFIG"
        yq eval ".gateway.url = \"\"" -i "$DYNAMIC_CONFIG"
    else
        # フォールバック: sed を使用して手動更新 (YAML のダブルクォートを処理)
        sed -i.bak 's|arn: ".*"|arn: ""|' "$DYNAMIC_CONFIG"
        sed -i.bak 's|id: ".*"|id: ""|' "$DYNAMIC_CONFIG"
        sed -i.bak 's|url: ".*"|url: ""|' "$DYNAMIC_CONFIG"
        rm -f "${DYNAMIC_CONFIG}.bak"
    fi

    echo "✅ 動的設定をクリアしました"
}

# クリーンアップを呼び出して完了メッセージを表示
cleanup_dynamic_config

echo ""
echo "🎉 Gateway とターゲットの削除完了！"
echo "======================================"
echo ""
echo "✅ AgentCore Gateway とターゲットの削除が完了しました"
echo "✅ 動的設定がクリアされました"
echo ""
echo "📋 削除されたもの:"
echo "   • 選択した AgentCore Gateway"
echo "   • すべての Gateway ターゲット"
echo "   • 動的設定からの Gateway 設定"
echo ""
echo "💡 注意:"
echo "   • MCP Lambda 関数は引き続きデプロイ済み"
echo "   • IAM ロールは引き続き利用可能"
echo "   • OAuth プロバイダーは引き続き設定済み"
echo ""
echo "🚀 Gateway とターゲットを再作成するには:"
echo "   ./04-create-gateway-targets.sh を実行"
echo ""

# Return to original directory
cd "${SCRIPT_DIR}"
