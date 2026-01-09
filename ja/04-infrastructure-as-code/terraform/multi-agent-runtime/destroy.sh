#!/bin/bash

# ============================================================================
# Destroy Script for Multi-Agent Runtime (Terraform)
# ============================================================================
# This script safely destroys all resources created by this Terraform configuration
# Usage: ./destroy.sh

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

print_warning "リソースのクリーンアップを開始しています..."
echo ""

# Check Terraform installation
if ! command_exists terraform; then
    print_error "Terraform がインストールされていません"
    exit 1
fi

# Check AWS CLI installation
if ! command_exists aws; then
    print_error "AWS CLI がインストールされていません"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    print_error "AWS 認証情報が設定されていないか、無効です"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
print_info "AWS アカウント: $AWS_ACCOUNT"
print_info "AWS リージョン: $AWS_REGION"

echo ""

# ============================================================================
# Check for Terraform State
# ============================================================================

if [ ! -f "terraform.tfstate" ] && [ ! -f ".terraform/terraform.tfstate" ]; then
    print_warning "Terraform ステートが見つかりません"
    print_info "リソースがデプロイされていないか、ステートがリモートに保存されています"

    read -p "バックエンドからステートをインポートしますか？ (yes/no): " -r
    echo ""

    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "リモートステートを取得するために Terraform を初期化しています..."
        terraform init
    else
        print_info "クリーンアップがキャンセルされました"
        exit 0
    fi
fi

# ============================================================================
# Show Destruction Plan
# ============================================================================

print_info "削除プランを作成しています..."
echo ""

if ! terraform plan -destroy; then
    print_error "削除プランの作成に失敗しました"
    exit 1
fi

echo ""

# ============================================================================
# Destruction Confirmation
# ============================================================================

print_warning "========================================"
print_warning "リソース削除の確認"
print_warning "========================================"
print_warning "以下のリソースが完全に削除されます:"
print_warning "  - Orchestrator Runtime"
print_warning "  - Specialist Runtime"
print_warning "  - 2つの S3 バケット（ソースコードストレージ）"
print_warning "  - 2つの ECR リポジトリ（すべてのイメージを含む）"
print_warning "  - 2つの CodeBuild プロジェクト"
print_warning "  - IAM ロールとポリシー（A2A 権限を含む）"
print_warning "  - CloudWatch ロググループ"
echo ""
print_warning "この操作は元に戻せません！"
echo ""
print_info "他の AWS サービスのリソース（例：S3 バケット）は引き続きコストが発生する可能性があります"
echo ""

read -p "本当にすべてのリソースを削除しますか？ (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    print_info "ユーザーによって削除がキャンセルされました"
    exit 0
fi

# Double confirmation for safety
print_warning "2回目の確認が必要です..."
read -p "'DESTROY' と入力して確認してください: " -r
echo ""

if [ "$REPLY" != "DESTROY" ]; then
    print_info "削除がキャンセルされました - 確認テキストが一致しませんでした"
    exit 0
fi

# ============================================================================
# Execute Destruction
# ============================================================================

print_warning "リソースの削除を開始しています..."
echo ""

if terraform destroy -auto-approve; then
    print_success "すべてのリソースが正常に削除されました"
else
    print_error "削除に失敗しました"
    print_warning "一部のリソースがまだ存在している可能性があります。AWS コンソールを確認してください"
    exit 1
fi

echo ""

# ============================================================================
# Cleanup Local Files
# ============================================================================

print_info "ローカルの Terraform ファイルをクリーンアップしています..."

# Ask about state file cleanup
read -p "ローカルの Terraform ステートファイルを削除しますか？ (yes/no): " -r
echo ""

if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    rm -f terraform.tfstate
    rm -f terraform.tfstate.backup
    rm -f tfplan
    print_success "ローカルステートファイルを削除しました"
fi

# Ask about .terraform directory
read -p ".terraform ディレクトリを削除しますか？ (yes/no): " -r
echo ""

if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    rm -rf .terraform
    rm -f .terraform.lock.hcl
    print_success ".terraform ディレクトリを削除しました"
fi

echo ""

# ============================================================================
# Verification
# ============================================================================

print_info "リソースのクリーンアップを確認しています..."
echo ""

# Check for ECR repositories
STACK_NAME=$(grep 'stack_name' terraform.tfvars 2>/dev/null | cut -d'"' -f2 || echo "agentcore-basic")
ECR_REPOS=$(aws ecr describe-repositories --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$ECR_REPOS" -eq 0 ]; then
    print_success "ECR リポジトリがクリーンアップされました"
else
    print_warning "'$STACK_NAME' に一致する ECR リポジトリが $ECR_REPOS 個見つかりました"
    print_info "手動でクリーンアップが必要な場合があります"
fi

# Check for AgentCore runtimes (both agents)
RUNTIME_COUNT=$(aws bedrock-agentcore list-agent-runtimes --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$RUNTIME_COUNT" -eq 0 ]; then
    print_success "AgentCore Runtime がクリーンアップされました（Orchestrator と Specialist）"
else
    print_warning "'$STACK_NAME' に一致する AgentCore Runtime が $RUNTIME_COUNT 個見つかりました"
    print_info "手動でクリーンアップが必要な場合があります"
fi

# Check for S3 buckets (both agent source buckets)
S3_BUCKETS=$(aws s3api list-buckets --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$S3_BUCKETS" -eq 0 ]; then
    print_success "S3 バケットがクリーンアップされました（Orchestrator と Specialist ソースバケット）"
else
    print_warning "'$STACK_NAME' に一致する S3 バケットが $S3_BUCKETS 個見つかりました"
    print_info "手動でクリーンアップが必要な場合があります"
fi

echo ""

# ============================================================================
# Completion Summary
# ============================================================================

print_success "========================================"
print_success "クリーンアップ完了"
print_success "========================================"
echo ""

print_info "クリーンアップ概要:"
print_success "  ✓ Terraform リソースが削除されました"
print_success "  ✓ ローカルステートファイルがクリーンアップされました（選択した場合）"
echo ""

print_info "AWS コンソールで確認する項目:"
print_info "1. Bedrock AgentCore - Runtime が残っていないこと"
print_info "   https://console.aws.amazon.com/bedrock/home?region=$AWS_REGION#/agentcore"
echo ""
print_info "2. S3 - バケットが残っていないこと"
print_info "   https://console.aws.amazon.com/s3/buckets?region=$AWS_REGION"
echo ""
print_info "3. ECR - リポジトリが残っていないこと（Orchestrator & Specialist）"
print_info "   https://console.aws.amazon.com/ecr/repositories?region=$AWS_REGION"
echo ""
print_info "4. CodeBuild - プロジェクトが残っていないこと（Orchestrator & Specialist）"
print_info "   https://console.aws.amazon.com/codesuite/codebuild/projects?region=$AWS_REGION"
echo ""
print_info "6. CloudWatch Logs - 孤立したロググループがないか確認"
print_info "   https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups"
echo ""

print_success "クリーンアップが正常に完了しました！"
print_info "再デプロイするには: ./deploy.sh を実行してください"
