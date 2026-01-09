#!/bin/bash

# ============================================================================
# Deploy Script for MCP Server on AgentCore Runtime (Terraform)
# ============================================================================
# This script automates the deployment process for the Terraform configuration
# Usage: ./deploy.sh

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_info "MCP Server on AgentCore Runtime のデプロイを開始しています..."
echo ""

# Check Terraform installation
if ! command_exists terraform; then
    print_error "Terraform がインストールされていません。Terraform >= 1.6 をインストールしてください"
    print_info "Visit: https://www.terraform.io/downloads"
    exit 1
fi

# Check Terraform version
TERRAFORM_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*' | cut -d'"' -f4)
print_success "Terraform バージョン: $TERRAFORM_VERSION"

# Check AWS CLI installation
if ! command_exists aws; then
    print_error "AWS CLI がインストールされていません。AWS CLI をインストールして設定してください"
    print_info "Visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

print_success "AWS CLI がインストールされています"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    print_error "AWS 認証情報が設定されていないか、無効です"
    print_info "Run: aws configure"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
print_success "AWS アカウント: $AWS_ACCOUNT"
print_success "AWS リージョン: $AWS_REGION"

echo ""

# ============================================================================
# Configuration Check
# ============================================================================

print_info "設定ファイルを確認しています..."

# Check if terraform.tfvars exists
if [ ! -f "terraform.tfvars" ]; then
    print_warning "terraform.tfvars が見つかりません"
    print_info "サンプルから terraform.tfvars を作成しています..."

    if [ -f "terraform.tfvars.example" ]; then
        cp terraform.tfvars.example terraform.tfvars
        print_success "terraform.tfvars を作成しました"
        print_warning "terraform.tfvars を確認して設定を更新してください"
        print_info "その後、このスクリプトを再実行してください"
        exit 0
    else
        print_error "terraform.tfvars.example が見つかりません"
        exit 1
    fi
fi

print_success "設定ファイルが見つかりました: terraform.tfvars"
echo ""

# ============================================================================
# Terraform Initialization
# ============================================================================

print_info "Terraform を初期化しています..."
if terraform init; then
    print_success "Terraform の初期化が完了しました"
else
    print_error "Terraform の初期化に失敗しました"
    exit 1
fi

echo ""

# ============================================================================
# Terraform Validation
# ============================================================================

print_info "Terraform 設定を検証しています..."
if terraform validate; then
    print_success "Terraform 設定は有効です"
else
    print_error "Terraform の検証に失敗しました"
    exit 1
fi

echo ""

# ============================================================================
# Terraform Format Check
# ============================================================================

print_info "Terraform のフォーマットを確認しています..."
if terraform fmt -check -recursive > /dev/null 2>&1; then
    print_success "Terraform ファイルは正しくフォーマットされています"
else
    print_warning "フォーマットが必要なファイルがあります。terraform fmt を実行しています..."
    terraform fmt -recursive
    print_success "ファイルをフォーマットしました"
fi

echo ""

# ============================================================================
# Terraform Plan
# ============================================================================

print_info "Terraform 実行プランを作成しています..."
print_warning "しばらくお待ちください..."
echo ""

if terraform plan -out=tfplan; then
    print_success "Terraform プランが正常に作成されました"
else
    print_error "Terraform プランの作成に失敗しました"
    exit 1
fi

echo ""

# ============================================================================
# Deployment Confirmation
# ============================================================================

print_warning "========================================"
print_warning "デプロイの確認"
print_warning "========================================"
print_info "以下のリソースがデプロイされます:"
print_info "  - S3 バケット（ソースコードストレージ）"
print_info "  - ECR リポジトリ"
print_info "  - CodeBuild プロジェクト"
print_info "  - Cognito ユーザープール + クライアント（JWT 認証）"
print_info "  - IAM ロールとポリシー"
print_info "  - AgentCore Runtime（MCP プロトコル付き）"
echo ""
print_info "デプロイには以下が含まれます:"
print_info "  - MCP サーバー付き ARM64 Docker イメージのビルド"
print_info "  - AWS リソースの作成"
print_info "  - テストユーザーでの JWT 認証の設定"
echo ""

read -p "デプロイを続行しますか？ (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    print_info "ユーザーによってデプロイがキャンセルされました"
    rm -f tfplan
    exit 0
fi

# ============================================================================
# Terraform Apply
# ============================================================================

print_info "デプロイを開始しています..."
echo ""

if terraform apply tfplan; then
    print_success "デプロイが正常に完了しました！"
else
    print_error "デプロイに失敗しました"
    rm -f tfplan
    exit 1
fi

# Clean up plan file
rm -f tfplan

echo ""

# ============================================================================
# Deployment Summary
# ============================================================================

print_success "========================================"
print_success "デプロイ完了"
print_success "========================================"
echo ""

print_info "デプロイ出力を取得しています..."
echo ""

# Get outputs
RUNTIME_ID=$(terraform output -raw agent_runtime_id 2>/dev/null || echo "N/A")
RUNTIME_ARN=$(terraform output -raw agent_runtime_arn 2>/dev/null || echo "N/A")
ECR_URL=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "N/A")
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id 2>/dev/null || echo "N/A")
CLIENT_ID=$(terraform output -raw cognito_user_pool_client_id 2>/dev/null || echo "N/A")

print_success "Agent Runtime ID: $RUNTIME_ID"
print_success "Agent Runtime ARN: $RUNTIME_ARN"
print_success "ECR Repository URL: $ECR_URL"
print_success "Cognito User Pool ID: $USER_POOL_ID"
print_success "Cognito Client ID: $CLIENT_ID"

echo ""
print_info "次のステップ:"
print_info "1. 認証用の JWT トークンを取得:"
print_info "   terraform output -raw get_token_command | bash"
echo ""
print_info "2. MCP サーバーをテスト:"
print_info "   # ステップ 1 で取得した JWT トークンをエクスポートして:"
print_info "   python test_mcp_server.py $RUNTIME_ARN \$JWT_TOKEN $AWS_REGION"
echo ""
print_info "3. すべての出力を表示:"
print_info "   terraform output"
echo ""
print_info "4. AWS コンソールで監視:"
print_info "   https://console.aws.amazon.com/bedrock/home?region=$AWS_REGION#/agentcore"
echo ""
print_success "デプロイが正常に完了しました！"
