#!/bin/bash

################################################################################
# CloudFormation Stack Deployment Script
#
# This script automates the deployment of the Customer Support VPC stack
# by uploading templates to S3 and creating the CloudFormation stack.
################################################################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
STACK_NAME_BASE="customer-support-vpc"
ENVIRONMENT="dev"
DB_USERNAME="postgres"
MODEL_ID="global.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION="us-west-2"
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFN_DIR="${SCRIPT_DIR}/cloudformation"

################################################################################
# Helper Functions
################################################################################

print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# 日本語ヘルパー関数
print_info_ja() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success_ja() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning_ja() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error_ja() {
    echo -e "${RED}✗${NC} $1"
}

print_header_ja() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

check_prerequisites() {
    print_header "前提条件を確認中"

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI がインストールされていません。先にインストールしてください。"
        echo "参照: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi
    print_success "AWS CLI を検出: $(aws --version | cut -d' ' -f1)"

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS 認証情報が設定されていません。先に 'aws configure' を実行してください。"
        exit 1
    fi

    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_success "AWS アカウント ID: ${AWS_ACCOUNT_ID}"

    # Check if CloudFormation directory exists
    if [ ! -d "$CFN_DIR" ]; then
        print_error "CloudFormation ディレクトリが見つかりません: $CFN_DIR"
        exit 1
    fi
    print_success "CloudFormation テンプレートを検出"
}

create_s3_bucket() {
    print_header "テンプレート用 S3 バケットを作成中"

    local bucket_name="$1"

    # Check if bucket exists
    if aws s3 ls "s3://${bucket_name}" 2>/dev/null; then
        print_warning "S3 バケットは既に存在します: ${bucket_name}"
        return 0
    fi

    print_info "S3 バケットを作成中: ${bucket_name}"

    # Create bucket (handle us-east-1 special case)
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$bucket_name" \
            --region "$REGION"
    else
        aws s3api create-bucket \
            --bucket "$bucket_name" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi

    print_success "S3 バケットを作成しました: ${bucket_name}"

    # Enable versioning
    print_info "バケットのバージョニングを有効化中..."
    aws s3api put-bucket-versioning \
        --bucket "$bucket_name" \
        --versioning-configuration Status=Enabled

    print_success "バケットのバージョニングを有効化しました"

    # Enable encryption
    print_info "デフォルト暗号化を有効化中..."
    aws s3api put-bucket-encryption \
        --bucket "$bucket_name" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }'

    print_success "デフォルト暗号化を有効化しました"
}

upload_templates() {
    print_header "CloudFormation テンプレートを S3 にアップロード中"

    local bucket_name="$1"

    # Upload nested stack templates
    print_info "ネストスタックテンプレートをアップロード中..."
    aws s3 cp "$CFN_DIR/" "s3://${bucket_name}/cloudformation/" \
        --recursive \
        --exclude "customer-support-stack.yaml" \
        --region "$REGION"

    # Upload master stack
    print_info "マスタースタックテンプレートをアップロード中..."
    aws s3 cp "$CFN_DIR/customer-support-stack.yaml" \
        "s3://${bucket_name}/" \
        --region "$REGION"

    print_success "すべてのテンプレートを正常にアップロードしました"

    # List uploaded files
    print_info "アップロードされたファイル:"
    aws s3 ls "s3://${bucket_name}/cloudformation/" --recursive
}

validate_template() {
    print_header "CloudFormation テンプレートを検証中"

    local bucket_name="$1"
    local template_url="https://${bucket_name}.s3.${REGION}.amazonaws.com/customer-support-stack.yaml"

    print_info "テンプレートを検証中: ${template_url}"

    if aws cloudformation validate-template \
        --template-url "$template_url" \
        --region "$REGION" &> /dev/null; then
        print_success "テンプレートの検証に成功しました"
        return 0
    else
        print_error "テンプレートの検証に失敗しました"
        return 1
    fi
}

deploy_stack() {
    print_header "CloudFormation スタックをデプロイ中"

    local bucket_name="$1"
    local template_url="https://${bucket_name}.s3.${REGION}.amazonaws.com/customer-support-stack.yaml"
    local base_url="https://${bucket_name}.s3.${REGION}.amazonaws.com/cloudformation"

    print_info "スタック名: ${STACK_NAME}"
    print_info "リージョン: ${REGION}"
    print_info "環境: ${ENVIRONMENT}"
    print_info "モデル ID: ${MODEL_ID}"
    print_info "管理者メール: ${ADMIN_EMAIL}"
    print_info "テンプレート URL: ${template_url}"

    # Validate admin email and password
    if [ -z "$ADMIN_EMAIL" ]; then
        print_error "管理者メールアドレスが必要です。--email オプションを使用してください。"
        exit 1
    fi

    if [ -z "$ADMIN_PASSWORD" ]; then
        print_error "管理者パスワードが必要です。--password オプションを使用してください。"
        exit 1
    fi

    # Check if stack already exists
    if aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" &> /dev/null; then

        print_warning "スタックは既に存在します: ${STACK_NAME}"
        read -p "スタックを更新しますか？ (y/n): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "スタックを更新中..."
            aws cloudformation update-stack \
                --stack-name "$STACK_NAME" \
                --template-url "$template_url" \
                --parameters \
                    ParameterKey=TemplateBaseURL,ParameterValue="$base_url" \
                    ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
                    ParameterKey=DBMasterUsername,ParameterValue="$DB_USERNAME" \
                    ParameterKey=ModelID,ParameterValue="$MODEL_ID" \
                    ParameterKey=AdminUserEmail,ParameterValue="$ADMIN_EMAIL" \
                    ParameterKey=AdminUserPassword,ParameterValue="$ADMIN_PASSWORD" \
                --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
                --region "$REGION"

            print_info "スタック更新の完了を待機中..."
            aws cloudformation wait stack-update-complete \
                --stack-name "$STACK_NAME" \
                --region "$REGION"

            print_success "スタックを正常に更新しました！"
        else
            print_info "更新がキャンセルされました"
            exit 0
        fi
    else
        print_info "新しいスタックを作成中..."
        aws cloudformation create-stack \
            --stack-name "$STACK_NAME" \
            --template-url "$template_url" \
            --parameters \
                ParameterKey=TemplateBaseURL,ParameterValue="$base_url" \
                ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
                ParameterKey=DBMasterUsername,ParameterValue="$DB_USERNAME" \
                ParameterKey=ModelID,ParameterValue="$MODEL_ID" \
                ParameterKey=AdminUserEmail,ParameterValue="$ADMIN_EMAIL" \
                ParameterKey=AdminUserPassword,ParameterValue="$ADMIN_PASSWORD" \
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
            --region "$REGION" \
            --tags \
                Key=Project,Value=CustomerSupportVPC \
                Key=Environment,Value="$ENVIRONMENT" \
                Key=ManagedBy,Value=CloudFormation

        print_success "スタック作成を開始しました"
        print_info "スタック作成の完了を待機中（30〜45分かかる場合があります）..."

        aws cloudformation wait stack-create-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"

        print_success "スタックを正常に作成しました！"
    fi
}

get_stack_outputs() {
    print_header "スタック出力"

    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
}

print_usage() {
    cat << EOF
使用法: $0 [オプション]

Customer Support VPC CloudFormation スタックをデプロイ

オプション:
    -b, --bucket BUCKET_NAME    テンプレート用 S3 バケット名 (オプション、未指定時は自動生成)
    -s, --stack STACK_NAME      CloudFormation スタックのベース名 (デフォルト: customer-support-vpc)
                                注: 環境名が自動的に付加されます (例: customer-support-vpc-dev)
    -r, --region REGION         AWS リージョン (デフォルト: us-west-2)
    -e, --env ENVIRONMENT       環境名 (デフォルト: dev、スタック名に付加)
    -u, --db-user USERNAME      データベースマスターユーザー名 (デフォルト: postgres)
    -m, --model MODEL_ID        Bedrock モデル ID (デフォルト: global.anthropic.claude-haiku-4-5-20251001-v1:0)
    --email EMAIL               管理者ユーザーメール (必須)
    --password PASSWORD         管理者ユーザーパスワード (必須、8文字以上で大文字、小文字、数字、特殊文字を含む)
    -h, --help                  このヘルプメッセージを表示

例:
    # dev 環境をデプロイ (スタック名: customer-support-vpc-dev)
    $0 --email admin@example.com --password 'MyP@ssw0rd123'

    # 本番環境をデプロイ (スタック名: customer-support-vpc-prod)
    $0 --env prod --email admin@example.com --password 'MyP@ssw0rd123'

    # Haiku モデルでテスト環境をデプロイ (スタック名: customer-support-vpc-test)
    $0 --env test --email admin@example.com --password 'MyP@ssw0rd123' --model global.anthropic.claude-haiku-4-5-20251001-v1:0

    # 特定リージョンにカスタムモデルでデプロイ (スタック名: customer-support-vpc-dev)
    $0 --region us-west-2 --model global.anthropic.claude-haiku-4-5-20251001-v1:0 --email admin@example.com --password 'MyP@ssw0rd123'

    # フルカスタマイズ (スタック名: prod-support-prod)
    $0 --bucket customersupportvpc-prod \\
       --stack prod-support \\
       --env prod \\
       --region us-east-1 \\
       --model global.anthropic.claude-haiku-4-5-20251001-v1:0 \\
       --email admin@example.com \\
       --password 'MyP@ssw0rd123'

注意:
    - 管理者メールとパスワードは Cognito ユーザープールに必須です
    - パスワードは8文字以上で、大文字、小文字、数字、特殊文字を含む必要があります
    - スタック名には自動的に環境サフィックスが付加されます (例: -dev, -prod, -test)
    - バケット名が指定されない場合、'customersupportvpc-' プレフィックスに12文字の
      ランダムな小文字英数字が続く S3 準拠の名前が自動生成されます。

EOF
}

generate_bucket_name() {
    # Generate S3-compliant bucket name with customersupportvpc prefix
    # S3 naming rules: lowercase, numbers, hyphens, 3-63 chars, no underscores
    local random_suffix=$(head /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | head -c 12)
    echo "customersupportvpc-${random_suffix}"
}

################################################################################
# Main Script
################################################################################

main() {
    # Parse command line arguments
    BUCKET_NAME=""
    CUSTOM_STACK_NAME=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            -b|--bucket)
                BUCKET_NAME="$2"
                shift 2
                ;;
            -s|--stack)
                CUSTOM_STACK_NAME="$2"
                shift 2
                ;;
            -r|--region)
                REGION="$2"
                shift 2
                ;;
            -e|--env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -u|--db-user)
                DB_USERNAME="$2"
                shift 2
                ;;
            -m|--model)
                MODEL_ID="$2"
                shift 2
                ;;
            --email)
                ADMIN_EMAIL="$2"
                shift 2
                ;;
            --password)
                ADMIN_PASSWORD="$2"
                shift 2
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                print_error "不明なオプション: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    # Set stack name with environment suffix
    if [ -n "$CUSTOM_STACK_NAME" ]; then
        STACK_NAME="${CUSTOM_STACK_NAME}-${ENVIRONMENT}"
    else
        STACK_NAME="${STACK_NAME_BASE}-${ENVIRONMENT}"
    fi

    # Generate bucket name if not provided
    if [ -z "$BUCKET_NAME" ]; then
        BUCKET_NAME=$(generate_bucket_name)
        print_info "生成された S3 バケット名: ${BUCKET_NAME}"
    fi

    # Validate required parameters
    if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
        print_error "管理者メールとパスワードが必要です！"
        print_usage
        exit 1
    fi

    print_header "Customer Support VPC スタックデプロイ"
    echo "スタック名:       $STACK_NAME"
    echo "S3 バケット:      $BUCKET_NAME"
    echo "リージョン:       $REGION"
    echo "環境:             $ENVIRONMENT"
    echo "DB ユーザー名:    $DB_USERNAME"
    echo "モデル ID:        $MODEL_ID"
    echo "管理者メール:     $ADMIN_EMAIL"
    echo "パスワード:       ******** (非表示)"
    echo ""

    read -p "デプロイを続行しますか？ (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "デプロイがキャンセルされました"
        exit 0
    fi

    # Execute deployment steps
    check_prerequisites
    create_s3_bucket "$BUCKET_NAME"
    upload_templates "$BUCKET_NAME"
    validate_template "$BUCKET_NAME"
    deploy_stack "$BUCKET_NAME"
    get_stack_outputs

    print_header "デプロイ完了"
    print_success "スタックを正常にデプロイしました！"
    print_info "スタック名: ${STACK_NAME}"
    print_info "リージョン: ${REGION}"
    print_info ""
    print_info "AWS コンソールでスタックを表示:"
    print_info "https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${STACK_NAME}"
}

# Run main function
main "$@"
