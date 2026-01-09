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
    echo "サブネット ID: $SUBNET_IDS"
else
    echo "エラー: $PROJECT_DIR/config/vpc_config.env に VPC 設定が見つかりません"
    exit 1
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

# First, verify and fix DNS settings
echo "VPC の DNS 設定を確認中..."
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

echo "AWS サービス用 VPC エンドポイントを作成中..."

# Create security group for VPC endpoints
ENDPOINT_SG_NAME="vpc-endpoints-sg"
ENDPOINT_SG_DESC="Security group for VPC endpoints"

# Check if security group already exists
EXISTING_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$ENDPOINT_SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region $AWS_REGION)

if [ "$EXISTING_SG" != "None" ] && [ ! -z "$EXISTING_SG" ]; then
    echo "既存のセキュリティグループを使用します: $EXISTING_SG"
    ENDPOINT_SG_ID=$EXISTING_SG
else
    echo "VPC エンドポイント用セキュリティグループを作成中..."
    ENDPOINT_SG_ID=$(aws ec2 create-security-group \
        --group-name $ENDPOINT_SG_NAME \
        --description "$ENDPOINT_SG_DESC" \
        --vpc-id $VPC_ID \
        --region $AWS_REGION \
        --output text \
        --query "GroupId")

    echo "セキュリティグループを作成しました: $ENDPOINT_SG_ID"

    # Add inbound rule to allow traffic from Lambda security group
    aws ec2 authorize-security-group-ingress \
        --group-id $ENDPOINT_SG_ID \
        --protocol tcp \
        --port 443 \
        --source-group $LAMBDA_SECURITY_GROUP_ID \
        --region $AWS_REGION

    echo "Lambda セキュリティグループからのトラフィックを許可するインバウンドルールを追加しました"
fi

# Get account ID for endpoint policy
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
    echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
    echo "エラー: $ACCOUNT_ID"
    exit 1
fi

# Create endpoint policy that restricts access to this account only
ENDPOINT_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"*","Resource":"*","Condition":{"StringEquals":{"aws:PrincipalAccount":"'"$ACCOUNT_ID"'"}}}]}'

# Create VPC endpoints for required AWS services
SERVICES=("ssm" "secretsmanager" "logs" "monitoring")

for SERVICE in "${SERVICES[@]}"; do
    echo "$SERVICE 用 VPC エンドポイントを作成中..."

    # Check if endpoint already exists
    EXISTING_ENDPOINT=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=com.amazonaws.$AWS_REGION.$SERVICE" \
        --query "VpcEndpoints[0].VpcEndpointId" \
        --output text \
        --region $AWS_REGION)

    if [ "$EXISTING_ENDPOINT" != "None" ] && [ ! -z "$EXISTING_ENDPOINT" ]; then
        echo "$SERVICE 用 VPC エンドポイントは既に存在します: $EXISTING_ENDPOINT"

        # Update the existing endpoint policy
        echo "既存のエンドポイント $EXISTING_ENDPOINT のポリシーを更新中..."
        aws ec2 modify-vpc-endpoint \
            --vpc-endpoint-id $EXISTING_ENDPOINT \
            --policy "$ENDPOINT_POLICY" \
            --region $AWS_REGION

        continue
    fi

    # Convert comma-separated subnet IDs to array for AWS CLI
    IFS=',' read -ra SUBNET_ARRAY <<< "$SUBNET_IDS"

    # Create the VPC endpoint with proper subnet formatting
    echo "サブネット ${SUBNET_ARRAY[@]} で $SERVICE 用エンドポイントを作成中"
    ENDPOINT_ID=$(aws ec2 create-vpc-endpoint \
        --vpc-id $VPC_ID \
        --vpc-endpoint-type Interface \
        --service-name com.amazonaws.$AWS_REGION.$SERVICE \
        --subnet-ids ${SUBNET_ARRAY[@]} \
        --security-group-ids $ENDPOINT_SG_ID \
        --policy "$ENDPOINT_POLICY" \
        --private-dns-enabled \
        --region $AWS_REGION \
        --output text \
        --query "VpcEndpoint.VpcEndpointId")
    
    echo "$SERVICE 用 VPC エンドポイントを作成しました: $ENDPOINT_ID"
done

# Verify route tables for the subnets
echo "サブネットのルートテーブルを確認中..."
IFS=',' read -ra SUBNET_ARRAY <<< "$SUBNET_IDS"
for SUBNET in "${SUBNET_ARRAY[@]}"; do
    echo "サブネット $SUBNET のルートテーブルを確認中"
    ROUTE_TABLE=$(aws ec2 describe-route-tables \
        --filters "Name=association.subnet-id,Values=$SUBNET" \
        --query "RouteTables[0].RouteTableId" \
        --output text \
        --region $AWS_REGION)

    if [ "$ROUTE_TABLE" != "None" ] && [ ! -z "$ROUTE_TABLE" ]; then
        echo "サブネット $SUBNET はルートテーブル $ROUTE_TABLE に関連付けられています"
    else
        echo "警告: サブネット $SUBNET はどのルートテーブルにも関連付けられていません！"
    fi
done

echo "VPC エンドポイントの作成が正常に完了しました"