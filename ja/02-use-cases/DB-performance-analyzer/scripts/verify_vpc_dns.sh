#!/bin/bash
set -e

# Get the script directory and project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Load VPC configuration
if [ -f "$PROJECT_DIR/config/vpc_config.env" ]; then
    source "$PROJECT_DIR/config/vpc_config.env"
    echo "VPC 設定を読み込みました"
    echo "VPC ID: $VPC_ID"
else
    echo "エラー: $PROJECT_DIR/config/vpc_config.env に VPC 設定が見つかりません"
    exit 1
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

echo "VPC $VPC_ID の DNS 設定を確認中..."

# Check DNS support
DNS_SUPPORT=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsSupport --region $AWS_REGION --query 'EnableDnsSupport.Value' --output text)
if [ "$DNS_SUPPORT" == "True" ] || [ "$DNS_SUPPORT" == "true" ]; then
    echo "VPC $VPC_ID の DNS サポートは既に有効です"
else
    echo "VPC $VPC_ID の DNS サポートを有効化中..."
    aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support "{\"Value\":true}" --region $AWS_REGION
    echo "DNS サポートを有効化しました"
fi

# Check DNS hostnames
DNS_HOSTNAMES=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsHostnames --region $AWS_REGION --query 'EnableDnsHostnames.Value' --output text)
if [ "$DNS_HOSTNAMES" == "True" ] || [ "$DNS_HOSTNAMES" == "true" ]; then
    echo "VPC $VPC_ID の DNS ホスト名は既に有効です"
else
    echo "VPC $VPC_ID の DNS ホスト名を有効化中..."
    aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames "{\"Value\":true}" --region $AWS_REGION
    echo "DNS ホスト名を有効化しました"
fi

echo "DNS 設定の確認が完了しました"