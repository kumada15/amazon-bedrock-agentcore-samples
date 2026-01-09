#!/bin/bash

# Setup OAuth2 Credential Provider for AgentCore
# Run this BEFORE deploying agents so they have OAuth capability from day 1

set -e  # Exit on any error

echo "🔧 AgentCore OAuth2 認証プロバイダーセットアップ"
echo "=============================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
CONFIG_DIR="${PROJECT_DIR}/config"

# Load static configuration
if [[ ! -f "${CONFIG_DIR}/static-config.yaml" ]]; then
    echo -e "${RED}❌ 設定ファイルが見つかりません: ${CONFIG_DIR}/static-config.yaml${NC}"
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
OKTA_DOMAIN_STATIC=$(get_yaml_value "domain" "${CONFIG_DIR}/static-config.yaml")

echo -e "${BLUE}📝 このスクリプトは以下を実行します:${NC}"
echo "   1. Okta 認証情報を入力 (セキュア入力)"
echo "   2. AgentCore に OAuth2 認証プロバイダーを作成"
echo "   3. プロバイダー詳細で設定ファイルを更新"
echo "   4. エージェントデプロイの準備"
echo ""

# Function to verify prerequisites
verify_prerequisites() {
    echo -e "${BLUE}🔍 前提条件を確認中...${NC}"

    # Check if prerequisites.sh has been run
    if ! aws iam get-role --role-name bac-execution-role &> /dev/null; then
        echo -e "${RED}❌ IAM ロールが見つかりません: bac-execution-role${NC}"
        echo "   先に ./prerequisites.sh を実行してください"
        return 1
    fi

    # Check ECR repositories
    local repos=("bac-runtime-repo-diy" "bac-runtime-repo-sdk")
    for repo in "${repos[@]}"; do
        if ! aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &> /dev/null; then
            echo -e "${RED}❌ ECR リポジトリが見つかりません: $repo${NC}"
            echo "   先に ./prerequisites.sh を実行してください"
            return 1
        fi
    done

    echo -e "${GREEN}✅ 前提条件を確認しました${NC}"
    return 0
}

# Function to collect Okta credentials securely
collect_okta_credentials() {
    echo -e "${BLUE}🔐 Okta 認証情報の収集${NC}"
    echo -e "${BLUE}=============================${NC}"
    echo "Okta アプリケーションの認証情報を入力してください:"
    echo ""

    # Use Okta domain from static config or prompt if not found
    if [[ -n "$OKTA_DOMAIN_STATIC" ]]; then
        OKTA_DOMAIN="$OKTA_DOMAIN_STATIC"
        echo "設定から Okta ドメインを使用: $OKTA_DOMAIN"
    else
        echo -n "Okta ドメイン (例: trial-7575566.okta.com): "
        read OKTA_DOMAIN

        if [[ -z "$OKTA_DOMAIN" ]]; then
            echo -e "${RED}❌ Okta ドメインは必須です${NC}"
            return 1
        fi
    fi

    # Collect Client ID
    echo -n "クライアント ID: "
    read OKTA_CLIENT_ID

    if [[ -z "$OKTA_CLIENT_ID" ]]; then
        echo -e "${RED}❌ クライアント ID は必須です${NC}"
        return 1
    fi

    # Collect Client Secret (hidden input)
    echo -n "クライアントシークレット (入力は非表示): "
    read -s OKTA_CLIENT_SECRET
    echo ""  # New line after hidden input

    if [[ -z "$OKTA_CLIENT_SECRET" ]]; then
        echo -e "${RED}❌ クライアントシークレットは必須です${NC}"
        return 1
    fi

    # Collect custom scope
    echo ""
    echo -e "${BLUE}ℹ️  カスタムスコープ設定:${NC}"
    echo "   • このスコープは Okta 認可サーバーで作成する必要があります"
    echo "   • 移動先: Security > API > Authorization Servers > [your-server] > Scopes"
    echo "   • カスタムスコープ (例: 'api') が存在しない場合は作成してください"
    echo ""
    echo -n "カスタムスコープ (デフォルト: api): "
    read OKTA_SCOPE
    OKTA_SCOPE=${OKTA_SCOPE:-api}

    echo ""
    echo -e "${GREEN}✅ 認証情報を収集しました${NC}"
    echo "   ドメイン: $OKTA_DOMAIN"
    echo "   クライアント ID: $OKTA_CLIENT_ID"
    echo "   クライアントシークレット: [非表示]"
    echo "   スコープ: $OKTA_SCOPE"
    echo ""

    return 0
}

# Function to create OAuth2 credential provider
create_oauth_provider() {
    echo -e "${BLUE}🔧 OAuth2 認証プロバイダーを作成中${NC}"
    echo -e "${BLUE}=====================================${NC}"

    local provider_name="bac-identity-provider-okta"
    local well_known_url="https://${OKTA_DOMAIN}/oauth2/default/.well-known/openid-configuration"

    echo "   プロバイダー名: $provider_name"
    echo "   ドメイン: $OKTA_DOMAIN"
    echo "   ディスカバリー URL: $well_known_url"
    echo "   クライアント ID: $OKTA_CLIENT_ID"
    echo ""

    # Check if provider already exists
    if aws bedrock-agentcore-control get-oauth2-credential-provider --name "$provider_name" --region "$REGION" &> /dev/null; then
        echo -e "${YELLOW}⚠️  プロバイダーは既に存在します。設定を更新中...${NC}"
        
        # Update existing provider with correct configuration
        local update_output
        if update_output=$(aws bedrock-agentcore-control update-oauth2-credential-provider \
            --name "$provider_name" \
            --credential-provider-vendor "CustomOauth2" \
            --oauth2-provider-config-input "{
                \"customOauth2ProviderConfig\": {
                    \"oauthDiscovery\": {
                        \"discoveryUrl\": \"$well_known_url\"
                    },
                    \"clientId\": \"$OKTA_CLIENT_ID\",
                    \"clientSecret\": \"$OKTA_CLIENT_SECRET\"
                }
            }" \
            --region "$REGION" 2>&1); then

            echo -e "${GREEN}✅ OAuth2 認証プロバイダーを更新しました${NC}"
        else
            echo -e "${RED}❌ OAuth2 認証プロバイダーの更新に失敗しました${NC}"
            echo "$update_output"
            return 1
        fi
    else
        echo "   新しい OAuth2 認証プロバイダーを作成中..."
        
        # Create new provider using AWS CLI (more reliable than SDK)
        local create_output
        if create_output=$(aws bedrock-agentcore-control create-oauth2-credential-provider \
            --name "$provider_name" \
            --credential-provider-vendor "CustomOauth2" \
            --oauth2-provider-config-input "{
                \"customOauth2ProviderConfig\": {
                    \"oauthDiscovery\": {
                        \"discoveryUrl\": \"$well_known_url\"
                    },
                    \"clientId\": \"$OKTA_CLIENT_ID\",
                    \"clientSecret\": \"$OKTA_CLIENT_SECRET\"
                }
            }" \
            --region "$REGION" 2>&1); then

            echo -e "${GREEN}✅ OAuth2 認証プロバイダーを作成しました${NC}"
        else
            echo -e "${RED}❌ OAuth2 認証プロバイダーの作成に失敗しました${NC}"
            echo "$create_output"
            return 1
        fi
    fi
    
    # Get provider details for configuration update
    local provider_details
    if provider_details=$(aws bedrock-agentcore-control get-oauth2-credential-provider \
        --name "$provider_name" \
        --region "$REGION" 2>&1); then

        # Extract ARN from the response using multiple approaches for reliability
        # First try with jq if available
        if command -v jq >/dev/null 2>&1; then
            PROVIDER_ARN=$(echo "$provider_details" | jq -r '.credentialProviderArn' 2>/dev/null)
        fi

        # Fallback: Extract ARN using grep and sed (handle escaped JSON)
        if [[ -z "$PROVIDER_ARN" || "$PROVIDER_ARN" == "null" ]]; then
            # Look for the credentialProviderArn field in the JSON response
            PROVIDER_ARN=$(echo "$provider_details" | grep -o 'credentialProviderArn[^,}]*' | sed 's/.*: *["\\"]*\([^"\\]*\).*/\1/' | head -1)
        fi

        # Additional fallback: try a different pattern
        if [[ -z "$PROVIDER_ARN" ]]; then
            PROVIDER_ARN=$(echo "$provider_details" | sed -n 's/.*"credentialProviderArn": *"\([^"]*\)".*/\1/p' | head -1)
        fi

        # Final fallback: extract from the escaped JSON string
        if [[ -z "$PROVIDER_ARN" ]]; then
            PROVIDER_ARN=$(echo "$provider_details" | sed -n 's/.*\\\"credentialProviderArn\\\":\\\"\\([^\\]*\\)\\\".*/\1/p' | head -1)
        fi

        PROVIDER_NAME="$provider_name"

        echo "   名前: $PROVIDER_NAME"
        echo "   ARN: $PROVIDER_ARN"

        # Validate that we got an ARN
        if [[ -z "$PROVIDER_ARN" ]]; then
            echo -e "${YELLOW}⚠️  警告: レスポンスから ARN を抽出できませんでした${NC}"
            echo "   レスポンス: $provider_details"
        fi

        return 0
    else
        echo -e "${RED}❌ プロバイダー詳細の取得に失敗しました${NC}"
        echo "$provider_details"
        return 1
    fi
}

# Function to update configuration files
update_config_files() {
    echo -e "${BLUE}📝 設定ファイルを更新中${NC}"
    echo -e "${BLUE}===============================${NC}"
    
    
    # Update dynamic-config.yaml to include OAuth info (without secrets)
    local dynamic_config="${CONFIG_DIR}/dynamic-config.yaml"
    
    if [[ -f "$dynamic_config" ]]; then
        # Update OAuth provider section in dynamic config
        if grep -q "oauth_provider:" "$dynamic_config"; then
            # Use sed to update the oauth_provider section (using | as delimiter to handle ARN with /)
            sed -i '' \
                -e "s|provider_name: \"\"|provider_name: \"$PROVIDER_NAME\"|" \
                -e "s|provider_arn: \"\"|provider_arn: \"$PROVIDER_ARN\"|" \
                -e "s|scopes: \[\]|scopes: [\"$OKTA_SCOPE\"]|" \
                "$dynamic_config"
            
            echo -e "${GREEN}✅ 更新完了: dynamic-config.yaml${NC}"

            # Validate the updates
            if [[ -n "$PROVIDER_ARN" ]]; then
                if grep -q "provider_arn: \"$PROVIDER_ARN\"" "$dynamic_config"; then
                    echo -e "${GREEN}   ✓ プロバイダー ARN を正常に更新しました${NC}"
                else
                    echo -e "${YELLOW}   ⚠️  プロバイダー ARN が正しく更新されていない可能性があります${NC}"
                fi
            else
                echo -e "${YELLOW}   ⚠️  プロバイダー ARN が空です - 手動更新が必要な可能性があります${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  dynamic-config.yaml に oauth_provider セクションが見つかりません${NC}"
        fi
    fi
    
    return 0
}

# Function to show next steps
show_next_steps() {
    echo -e "${GREEN}🎉 OAuth2 セットアップ完了！${NC}"
    echo -e "${GREEN}=========================${NC}"
    echo ""
    echo -e "${BLUE}📋 作成されたもの:${NC}"
    echo "   • OAuth2 認証プロバイダー: $PROVIDER_NAME"
    echo "   • 更新済み: config/dynamic-config.yaml"
    echo ""
    echo -e "${BLUE}🚀 次のステップ:${NC}"
    echo "   1. DIY エージェントをデプロイ: ./deploy-diy.sh"
    echo "   2. SDK エージェントをデプロイ: ./deploy-sdk.sh"
    echo "   3. ランタイムを作成: python3 deploy-diy-runtime.py"
    echo "   4. ランタイムを作成: python3 deploy-sdk-runtime.py"
    echo ""
    echo -e "${BLUE}💻 エージェントで OAuth を使用:${NC}"
    echo "   @requires_access_token("
    echo "       provider_name=\"$PROVIDER_NAME\","
    echo "       scopes=[\"$OKTA_SCOPE\"],"
    echo "       auth_flow=\"M2M\""
    echo "   )"
    echo "   async def my_function(*, access_token: str):"
    echo "       # access_token には Okta OAuth2 トークンが含まれます"
    echo ""
    echo -e "${BLUE}🔒 セキュリティに関する注意:${NC}"
    echo "   • 認証情報は AgentCore Identity に安全に保存されます"
    echo "   • シークレットは設定ファイルに保存されません"
    echo "   • トークンは自動的に管理・更新されます"
}

# Main execution
main() {
    echo -e "${BLUE}ステップ 2: OAuth2 認証プロバイダーセットアップ${NC}"
    echo "エージェントをデプロイする前にこれを実行してください"
    echo ""
    
    # Verify prerequisites
    if ! verify_prerequisites; then
        exit 1
    fi
    
    echo ""
    
    # Collect Okta credentials
    if ! collect_okta_credentials; then
        exit 1
    fi
    
    # Create OAuth2 credential provider
    if ! create_oauth_provider; then
        exit 1
    fi
    
    echo ""
    
    # Update configuration files
    if ! update_config_files; then
        exit 1
    fi
    
    echo ""
    
    # Show next steps
    show_next_steps
}

# Run main function
main "$@"
