#!/bin/bash

# Prerequisites setup script for AgentCore deployment
# This script ensures all necessary AWS resources and configurations are in place

set -e  # Exit on any error

echo "AgentCore 前提条件のセットアップ"
echo "================================"
echo ""
echo -e "${YELLOW}プラットフォーム注意: このスクリプトは macOS でのみテストされています${NC}"
echo -e "${BLUE}   他のプラットフォームでは手動インストールが必要な場合があります${NC}"
echo ""

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

# Load configuration
if [[ ! -f "${CONFIG_DIR}/static-config.yaml" ]]; then
    echo -e "${RED}設定ファイルが見つかりません: ${CONFIG_DIR}/static-config.yaml${NC}"
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
ROLE_NAME="bac-execution-role"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo -e "${BLUE}設定:${NC}"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
echo "   ロール ARN: $ROLE_ARN"
echo ""

# Function to check if command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}$1 がインストールされていません${NC}"
        return 1
    else
        echo -e "${GREEN}$1 が利用可能です${NC}"
        return 0
    fi
}

# Function to setup Python virtual environment and dependencies
setup_python_environment() {
    echo -e "${BLUE}Python 仮想環境をセットアップ中...${NC}"

    # Check if we're already in the AgentCore directory
    if [[ ! -f "${PROJECT_DIR}/requirements.txt" ]]; then
        echo -e "${RED}requirements.txt が ${PROJECT_DIR} に見つかりません${NC}"
        return 1
    fi

    # Create virtual environment if it doesn't exist
    if [[ ! -d "${PROJECT_DIR}/.venv" ]]; then
        echo "   仮想環境を作成中..."
        if python3 -m venv "${PROJECT_DIR}/.venv"; then
            echo -e "${GREEN}仮想環境を作成しました${NC}"
        else
            echo -e "${RED}仮想環境の作成に失敗しました${NC}"
            return 1
        fi
    else
        echo -e "${GREEN}仮想環境は既に存在します${NC}"
    fi

    # Activate virtual environment and install dependencies
    echo "   Python 依存関係をインストール中..."
    cd "${PROJECT_DIR}"
    source .venv/bin/activate

    # Upgrade pip first
    pip install --upgrade pip > /dev/null 2>&1

    # Install requirements with better error handling
    echo "   Python 依存関係をインストール中..."

    # First, try to install bedrock-agentcore specifically
    echo "   bedrock-agentcore SDK をインストール中..."
    if pip install bedrock-agentcore>=0.1.1 --quiet; then
        echo -e "${GREEN}   bedrock-agentcore SDK をインストールしました${NC}"
    else
        echo -e "${RED}   bedrock-agentcore SDK のインストールに失敗しました${NC}"
        echo -e "${BLUE}   このパッケージは OAuth プロバイダーの作成に必要です${NC}"
        return 1
    fi

    # Install all other requirements
    if pip install -r "${PROJECT_DIR}/requirements.txt" --quiet; then
        echo -e "${GREEN}Python 依存関係をインストールしました${NC}"
    else
        echo -e "${YELLOW}一部の Python 依存関係のインストールに失敗した可能性があります${NC}"
        echo -e "${BLUE}   'strands' のようなコンパイルが必要なパッケージでは想定される動作です${NC}"
        echo -e "${BLUE}   重要な依存関係を確認中...${NC}"

        # Test if critical packages are available
        if python -c "import bedrock_agentcore" 2>/dev/null; then
            echo -e "${GREEN}   bedrock-agentcore が利用可能です${NC}"
        else
            echo -e "${RED}   bedrock-agentcore が利用できません${NC}"
            return 1
        fi
    fi

    # Install/upgrade AWS CLI in the virtual environment
    echo "   仮想環境に最新の AWS CLI をインストール中..."
    if pip install --upgrade awscli > /dev/null 2>&1; then
        echo -e "${GREEN}仮想環境に最新の AWS CLI をインストールしました${NC}"
    else
        echo -e "${YELLOW}仮想環境への AWS CLI のインストールに失敗しました${NC}"
        echo -e "${BLUE}   システムの AWS CLI を使用します${NC}"
    fi

    return 0
}

# Function to check AWS credentials
check_aws_credentials() {
    echo -e "${BLUE}AWS 認証情報を確認中...${NC}"

    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}AWS 認証情報が設定されていないか無効です${NC}"
        echo "   以下のいずれかで AWS 認証情報を設定してください:"
        echo "   - aws configure"
        echo "   - aws sso login (SSO を使用する場合)"
        echo "   - AWS_PROFILE 環境変数を設定"
        return 1
    fi

    local caller_identity=$(aws sts get-caller-identity 2>/dev/null)
    local current_account=$(echo "$caller_identity" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)

    if [[ "$current_account" != "$ACCOUNT_ID" ]]; then
        echo -e "${YELLOW}警告: 現在の AWS アカウント ($current_account) が設定 ($ACCOUNT_ID) と一致しません${NC}"
        read -p "続行しますか？ (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi

    echo -e "${GREEN}AWS 認証情報がアカウント $current_account で有効です${NC}"
    return 0
}

# Function to update existing role policies
update_existing_role_policies() {
    # Load permission policy from file and substitute account ID
    local permission_policy_file="${SCRIPT_DIR}/bac-permissions-policy.json"
    if [[ ! -f "$permission_policy_file" ]]; then
        echo -e "${RED}権限ポリシーファイルが見つかりません: $permission_policy_file${NC}"
        return 1
    fi
    local permission_policy=$(sed "s/165938467517/$ACCOUNT_ID/g" "$permission_policy_file")

    # Update permission policy
    local policy_name="bac-execution-policy"
    if aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$policy_name" \
        --policy-document "$permission_policy" &> /dev/null; then
        echo -e "${GREEN}IAM ロールの権限を更新しました${NC}"
    else
        echo -e "${YELLOW}警告: 権限ポリシーの更新に失敗しました${NC}"
    fi
}

# Function to create IAM role
create_iam_role() {
    echo -e "${BLUE}IAM ロールを確認中: $ROLE_NAME${NC}"

    if aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
        echo -e "${GREEN}IAM ロールは既に存在します${NC}"
        echo "   現在のアカウント ID でロールポリシーを更新中..."
        update_existing_role_policies
        return 0
    fi

    echo "   IAM ロールを作成中..."

    # Load trust policy from file and substitute account ID
    local trust_policy_file="${SCRIPT_DIR}/bac-trust-policy.json"
    if [[ ! -f "$trust_policy_file" ]]; then
        echo -e "${RED}信頼ポリシーファイルが見つかりません: $trust_policy_file${NC}"
        return 1
    fi
    local trust_policy=$(sed "s/165938467517/$ACCOUNT_ID/g" "$trust_policy_file")

    # Create the role
    if aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$trust_policy" \
        --description "Execution role for AgentCore runtime" &> /dev/null; then
        echo -e "${GREEN}IAM ロールの作成に成功しました${NC}"
    else
        echo -e "${RED}IAM ロールの作成に失敗しました${NC}"
        return 1
    fi

    # Load permission policy from file and substitute account ID
    local permission_policy_file="${SCRIPT_DIR}/bac-permissions-policy.json"
    if [[ ! -f "$permission_policy_file" ]]; then
        echo -e "${RED}権限ポリシーファイルが見つかりません: $permission_policy_file${NC}"
        return 1
    fi
    local permission_policy=$(sed "s/165938467517/$ACCOUNT_ID/g" "$permission_policy_file")

    # Attach permission policy
    local policy_name="bac-execution-policy"
    if aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$policy_name" \
        --policy-document "$permission_policy" &> /dev/null; then
        echo -e "${GREEN}IAM ロールに権限をアタッチしました${NC}"
    else
        echo -e "${YELLOW}警告: 権限ポリシーのアタッチに失敗しました${NC}"
    fi

    return 0
}

# Function to check ECR repositories
check_ecr_repositories() {
    echo -e "${BLUE}ECR リポジトリを確認中...${NC}"

    local repos=("bac-runtime-repo-diy" "bac-runtime-repo-sdk")

    for repo in "${repos[@]}"; do
        if aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &> /dev/null; then
            echo -e "${GREEN}ECR リポジトリが存在します: $repo${NC}"
        else
            echo "   ECR リポジトリを作成中: $repo"
            if aws ecr create-repository --repository-name "$repo" --region "$REGION" &> /dev/null; then
                echo -e "${GREEN}ECR リポジトリを作成しました: $repo${NC}"
            else
                echo -e "${RED}ECR リポジトリの作成に失敗しました: $repo${NC}"
                return 1
            fi
        fi
    done

    return 0
}

# Function to validate config files
validate_config() {
    echo -e "${BLUE}設定ファイルを検証中...${NC}"

    # Check static-config.yaml
    if [[ ! -f "${CONFIG_DIR}/static-config.yaml" ]]; then
        echo -e "${RED}見つかりません: static-config.yaml${NC}"
        return 1
    fi

    # Check dynamic-config.yaml exists (create if missing)
    if [[ ! -f "${CONFIG_DIR}/dynamic-config.yaml" ]]; then
        echo -e "${YELLOW}見つからない dynamic-config.yaml を作成中${NC}"
        # Create empty dynamic config if it doesn't exist
        cat > "${CONFIG_DIR}/dynamic-config.yaml" << 'EOF'
# Dynamic Configuration - Updated by deployment scripts only
# This file contains all configuration values that are generated/updated during deployment
gateway:
  id: ""
  arn: ""
  url: ""
oauth_provider:
  provider_name: ""
  provider_arn: ""
  domain: ""
  scopes: []
mcp_lambda:
  function_name: ""
  function_arn: ""
  role_arn: ""
  stack_name: ""
  gateway_execution_role_arn: ""
runtime:
  diy_agent:
    arn: ""
    ecr_uri: ""
    endpoint_arn: ""
  sdk_agent:
    arn: ""
    ecr_uri: ""
    endpoint_arn: ""
client:
  diy_runtime_endpoint: ""
  sdk_runtime_endpoint: ""
EOF
    fi
    
    # Validate required fields in static config
    local required_fields=("region" "account_id")
    for field in "${required_fields[@]}"; do
        if ! grep -q "$field:" "${CONFIG_DIR}/static-config.yaml"; then
            echo -e "${RED}static config に必須フィールドがありません: $field${NC}"
            return 1
        fi
    done

    echo -e "${GREEN}設定ファイルは有効です${NC}"
    return 0
}

# Function to test AgentCore Identity permissions
test_agentcore_identity_permissions() {
    echo -e "${BLUE}AgentCore Identity の権限をテスト中...${NC}"

    # Check if we can list existing resources (basic permission test)
    if aws bedrock-agentcore-control list-workload-identities --region "$REGION" &> /dev/null; then
        echo -e "${GREEN}AgentCore Identity のリスト権限が機能しています${NC}"

        # Check if we have the critical GetResourceOauth2Token permission
        # We can't directly test this without creating resources, so we'll note it
        echo -e "${BLUE}注: Okta 統合用に GetResourceOauth2Token 権限が追加されています${NC}"
        echo -e "${BLUE}   Okta などの外部プロバイダーから OAuth2 トークンを取得できます${NC}"

        return 0
    else
        echo -e "${YELLOW}AgentCore Identity の権限が反映されるまで時間がかかる場合があります${NC}"
        echo -e "${BLUE}   AccessDeniedException エラーが発生した場合:${NC}"
        echo -e "${BLUE}   1. IAM の変更が反映されるまで 2-3 分待ってください${NC}"
        echo -e "${BLUE}   2. このスクリプトを再実行して権限を確認してください${NC}"
        return 1
    fi
}

# Function to show Okta integration status
show_okta_integration_status() {
    echo -e "${BLUE}Okta 統合ステータス${NC}"
    echo -e "${BLUE}=========================${NC}"

    if grep -q "okta:" "${CONFIG_DIR}/static-config.yaml"; then
        echo -e "${GREEN}static-config.yaml に Okta 設定が存在します${NC}"


        echo -e "${BLUE}Okta 統合の要件:${NC}"
        echo -e "${BLUE}   1. AgentCore Identity 権限 (このセットアップに含まれています)${NC}"
        echo -e "${BLUE}   2. 'Client Credentials' 許可が有効な Okta アプリケーション${NC}"
        echo -e "${BLUE}   3. Okta 認可サーバーで作成されたカスタム 'api' スコープ${NC}"
        echo -e "${BLUE}   4. static-config.yaml の有効なクライアント ID とシークレット${NC}"

    else
        echo -e "${YELLOW}Okta 設定が見つかりません${NC}"
        echo -e "${BLUE}   ${CONFIG_DIR}/static-config.yaml に Okta 認証情報を含む okta セクションを追加してください${NC}"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}依存関係を確認中...${NC}"

    local deps_ok=true
    check_command "aws" || deps_ok=false
    check_command "docker" || deps_ok=false
    check_command "python3" || deps_ok=false

    # Check for bedrock-agentcore-control CLI (critical for OAuth provider setup)
    if aws bedrock-agentcore-control help &> /dev/null; then
        echo -e "${GREEN}aws bedrock-agentcore-control が利用可能です${NC}"
    else
        echo -e "${RED}aws bedrock-agentcore-control が利用できません${NC}"
        echo -e "${BLUE}   この CLI は OAuth プロバイダーの作成に必要です${NC}"
        echo -e "${BLUE}   最新の AWS CLI バージョンがインストールされていることを確認してください${NC}"
        echo -e "${BLUE}   実行: aws --version (2.15.0 以降が必要です)${NC}"
        deps_ok=false
    fi

    if command -v yq &> /dev/null; then
        echo -e "${GREEN}yq が利用可能です (推奨)${NC}"
    else
        echo -e "${YELLOW}yq が見つかりません (フォールバック解析を使用します)${NC}"
    fi

    if [[ "$deps_ok" != true ]]; then
        echo -e "${RED}必要な依存関係がありません${NC}"
        exit 1
    fi
    
    echo ""
    
    # Setup Python environment
    setup_python_environment || exit 1
    
    echo ""
    
    # Run checks
    validate_config || exit 1
    check_aws_credentials || exit 1
    create_iam_role || exit 1
    check_ecr_repositories || exit 1
    
    echo ""
    
    # Test AgentCore Identity permissions
    test_agentcore_identity_permissions
    
    echo ""
    
    # Show Okta integration status
    show_okta_integration_status
    
    echo ""
    echo -e "${GREEN}前提条件のセットアップが完了しました！${NC}"
    echo ""
    echo -e "${BLUE}次のステップ:${NC}"
    echo "   1. DIY エージェントをデプロイ: ./deploy-diy.sh"
    echo "   2. SDK エージェントをデプロイ: ./deploy-sdk.sh"
    echo "   3. ランタイムを作成: python3 deploy-diy-runtime.py"
    echo "   4. ランタイムを作成: python3 deploy-sdk-runtime.py"
    echo ""
    echo -e "${BLUE}Okta 統合の場合:${NC}"
    echo "   5. Okta 統合をテスト: cd src/auth && python okta_working_final.py"
    echo "   6. AgentCore Identity + Okta OAuth2 トークン取得を確認"
}

# Run main function
main "$@"