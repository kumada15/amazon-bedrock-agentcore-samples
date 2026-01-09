#!/bin/bash

################################################################################
# Device Management System - Complete Deployment Script (Frontend Copy)
#
# NOTE: This is a duplicate of the root-level deploy_all.sh script.
# It exists in the frontend directory for convenience but should be kept
# in sync with the main deployment script.
#
# RECOMMENDATION: Use the root-level deploy_all.sh instead:
#   cd ../.. && ./deploy_all.sh
#
# This script orchestrates the end-to-end deployment of the Device Management
# System, deploying all components in the correct order with proper dependency
# management and configuration updates.
#
# DEPLOYMENT WORKFLOW:
#   1. Prerequisites validation (AWS CLI, Python, pip, AWS credentials)
#   2. Device Management Lambda function deployment
#   3. Gateway creation with Cognito OAuth authentication
#   4. Gateway target configuration with MCP tools
#   5. Gateway observability setup (CloudWatch Logs, X-Ray)
#   6. Agent Runtime deployment with OpenTelemetry instrumentation
#   7. Frontend configuration updates
#
# For complete documentation, see the root-level deploy_all.sh script.
#
################################################################################

set -e  # Exit on error

# Function to display section headers
section() {
  echo ""
  echo "=========================================="
  echo "  $1"
  echo "=========================================="
  echo ""
}

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
section "前提条件を確認中"

# Check for AWS CLI
if ! command_exists aws; then
  echo "エラー: AWS CLI がインストールされていません。先にインストールしてください。"
  exit 1
fi

# Check for Python
if ! command_exists python; then
  echo "エラー: Python がインストールされていません。Python 3.8 以上をインストールしてください。"
  exit 1
fi

# Check for pip
if ! command_exists pip; then
  echo "エラー: pip がインストールされていません。先にインストールしてください。"
  exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "エラー: AWS 認証情報が設定されていないか無効です。'aws configure' を実行してください。"
  exit 1
fi

echo "すべての前提条件を満たしています。"

# Step 1: Deploy Device Management Lambda
section "ステップ 1: Device Management Lambda をデプロイ中"

cd device-management
echo "Python 依存関係をインストール中..."
pip install -r requirements.txt

echo "Lambda 関数をデプロイ中..."
chmod +x deploy.sh
./deploy.sh

# Get the Lambda ARN from the output file or AWS CLI
if [ -f lambda_arn.txt ]; then
  LAMBDA_ARN=$(grep LAMBDA_ARN lambda_arn.txt | cut -d= -f2)
  echo "Lambda ARN: $LAMBDA_ARN"
else
  # Fallback: get Lambda ARN directly from AWS
  LAMBDA_FUNCTION_NAME=${LAMBDA_FUNCTION_NAME:-"DeviceManagementLambda"}
  LAMBDA_ARN=$(aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" --region us-west-2 --query 'Configuration.FunctionArn' --output text 2>/dev/null)
  if [ -z "$LAMBDA_ARN" ]; then
    echo "エラー: Lambda ARN が見つかりません。Lambda 関数が正常にデプロイされていることを確認してください。"
    exit 1
  fi
  echo "Lambda ARN（AWS から取得）: $LAMBDA_ARN"
fi

cd ..

# Step 2: Create Gateway
section "ステップ 2: Gateway を作成中"

cd gateway

# Check if .env file exists, if not create it
if [ ! -f .env ]; then
  echo "Gateway 用の .env ファイルを作成中..."
  
  # Create basic .env file structure
  cat > .env << EOF
# AWS and endpoint configuration
AWS_REGION=us-west-2
ENDPOINT_URL=https://bedrock-agentcore-control.us-west-2.amazonaws.com

# Lambda configuration (from device-management module)
LAMBDA_ARN=$LAMBDA_ARN

# Target configuration
GATEWAY_IDENTIFIER=your-gateway-identifier
TARGET_NAME=device-management-target
TARGET_DESCRIPTION=List, Update device management activities

# Gateway creation configuration
GATEWAY_NAME=Device-Management-Gateway
GATEWAY_DESCRIPTION=Device Management Gateway
EOF
  
  echo "gateway/.env ファイルを編集して、Cognito の詳細とその他の必要な値を設定してください。"
  echo "その後、このスクリプトを再実行してください。"
  exit 0
else
  # Update existing .env file with Lambda ARN
  echo "既存の .env ファイルを Lambda ARN で更新中..."
  if grep -q "^LAMBDA_ARN=" .env; then
    # Update existing LAMBDA_ARN line
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s|^LAMBDA_ARN=.*|LAMBDA_ARN=$LAMBDA_ARN|g" .env
    else
      sed -i "s|^LAMBDA_ARN=.*|LAMBDA_ARN=$LAMBDA_ARN|g" .env
    fi
  else
    # Add LAMBDA_ARN to the file
    echo "" >> .env
    echo "# Lambda configuration (from device-management module)" >> .env
    echo "LAMBDA_ARN=$LAMBDA_ARN" >> .env
  fi
fi

echo "Gateway を作成中..."
python create_gateway.py

# Get the Gateway ID from the output
GATEWAY_NAME=$(grep GATEWAY_NAME .env | cut -d= -f2)
GATEWAY_ID=$(aws bedrock-agentcore list-gateways --query "gateways[?name=='$GATEWAY_NAME'].gatewayId" --output text)

if [ -z "$GATEWAY_ID" ]; then
  echo "エラー: Gateway ID の取得に失敗しました。"
  exit 1
fi

echo "Gateway ID: $GATEWAY_ID"

# Update the .env file with the Gateway ID
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s|GATEWAY_IDENTIFIER=.*|GATEWAY_IDENTIFIER=$GATEWAY_ID|g" .env
else
  sed -i "s|GATEWAY_IDENTIFIER=.*|GATEWAY_IDENTIFIER=$GATEWAY_ID|g" .env
fi

echo "Gateway ターゲットを作成中..."
python device-management-target.py

# Update .env with Gateway ARN and ID for observability
GATEWAY_ARN=$(aws bedrock-agentcore list-gateways --query "gateways[?gatewayId=='$GATEWAY_ID'].gatewayArn" --output text)
if ! grep -q "^GATEWAY_ARN=" .env; then
  echo "GATEWAY_ARN=$GATEWAY_ARN" >> .env
fi
if ! grep -q "^GATEWAY_ID=" .env; then
  echo "GATEWAY_ID=$GATEWAY_ID" >> .env
fi

echo "Gateway のオブザーバビリティを設定中..."
python gateway_observability.py

cd ..

# Step 3: Deploy Agent Runtime
section "ステップ 3: Agent Runtime をデプロイ中"

cd agent-runtime

# Check if .env file exists, if not create it
if [ ! -f .env ]; then
  echo "Agent Runtime 用の .env ファイルを作成中..."
  cp .env.example .env
  
  # Update the Gateway URL in the .env file
  GATEWAY_URL="https://$GATEWAY_ID.gateway.bedrock-agentcore.us-west-2.amazonaws.com"
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|MCP_SERVER_URL=.*|MCP_SERVER_URL=$GATEWAY_URL|g" .env
  else
    sed -i "s|MCP_SERVER_URL=.*|MCP_SERVER_URL=$GATEWAY_URL|g" .env
  fi
  
  echo "agent-runtime/.env ファイルを編集して、Cognito の詳細とその他の必要な値を設定してください。"
  echo "その後、このスクリプトを再実行してください。"
  exit 0
fi

# Update requirements-runtime.txt with observability packages
echo "requirements-runtime.txt をオブザーバビリティパッケージで更新中..."
if ! grep -q "aws_opentelemetry_distro_genai_beta" requirements-runtime.txt; then
  echo "aws_opentelemetry_distro_genai_beta>=0.1.2" >> requirements-runtime.txt
fi
if ! grep -q "aws-xray-sdk" requirements-runtime.txt; then
  echo "aws-xray-sdk>=2.12.0" >> requirements-runtime.txt
fi
if ! grep -q "watchtower" requirements-runtime.txt; then
  echo "watchtower>=3.0.1" >> requirements-runtime.txt
fi
if ! grep -q "opentelemetry-instrumentation-requests" requirements-runtime.txt; then
  echo "opentelemetry-instrumentation-requests>=0.40b0" >> requirements-runtime.txt
fi
if ! grep -q "opentelemetry-instrumentation-boto3" requirements-runtime.txt; then
  echo "opentelemetry-instrumentation-boto3>=0.40b0" >> requirements-runtime.txt
fi

# Update Dockerfile with OpenTelemetry configuration
echo "Dockerfile を OpenTelemetry 設定で更新中..."
cat > Dockerfile << 'EOF'
FROM public.ecr.aws/docker/library/python:3.12-slim
WORKDIR /app

# Copy entire project (respecting .dockerignore)
COPY . .

# Install dependencies
RUN python -m pip install --no-cache-dir -r requirements-runtime.txt

# Install AWS OpenTelemetry Distro for GenAI
RUN python -m pip install aws_opentelemetry_distro_genai_beta>=0.1.2

# Install AWS X-Ray SDK
RUN python -m pip install aws-xray-sdk

# Set AWS region environment variable
ENV AWS_REGION=us-west-2
ENV AWS_DEFAULT_REGION=us-west-2

# Set OpenTelemetry environment variables
ENV OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=""
ENV OTEL_METRICS_EXPORTER="otlp"
ENV OTEL_TRACES_EXPORTER="otlp"
ENV OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
ENV OTEL_RESOURCE_ATTRIBUTES="service.name=device-management-agent"

# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080

# Use OpenTelemetry instrumentation to run the application
CMD ["opentelemetry-instrument", "python3.12", "-m", "strands-agent-runtime"]
EOF

# Update .bedrock_agentcore.yaml to ensure observability is enabled
echo ".bedrock_agentcore.yaml でオブザーバビリティが有効になっていることを確認中..."
if [ -f .bedrock_agentcore.yaml ]; then
  # Check if observability section exists and update it
  if grep -q "observability:" .bedrock_agentcore.yaml; then
    # Use awk to update the observability section
    awk '
    /observability:/ {
      print "      observability:";
      print "        enabled: true";
      print "        cloudwatch:";
      print "          log_group: \"/aws/bedrock-agentcore/device-management-agent\"";
      print "        xray:";
      print "          trace_enabled: true";
      found=1;
      next;
    }
    /enabled:/ && found==1 { found=0; next; }
    found==1 { next; }
    { print }
    ' .bedrock_agentcore.yaml > .bedrock_agentcore.yaml.tmp && mv .bedrock_agentcore.yaml.tmp .bedrock_agentcore.yaml
  fi
fi

echo "Agent Runtime 用の Python 依存関係をインストール中..."
pip install -r requirements-runtime.txt

echo "Agent Runtime をデプロイ中..."
python strands_agent_runtime_deploy.py

cd ..

# Step 4: Update frontend configuration
section "ステップ 4: フロントエンド設定を更新中"

# Get the Gateway URL
GATEWAY_URL="https://$GATEWAY_ID.gateway.bedrock-agentcore.us-west-2.amazonaws.com"
echo "Gateway URL: $GATEWAY_URL"

# Create .env file for frontend if it doesn't exist
if [ ! -f frontend/.env ]; then
  echo "フロントエンド用の .env ファイルを作成中..."
  echo "MCP_SERVER_URL=$GATEWAY_URL" > frontend/.env
  echo "COGNITO_DOMAIN=$(grep FRONTEND_COGNITO_DOMAIN .env | cut -d= -f2)" >> frontend/.env
  echo "COGNITO_CLIENT_ID=$(grep FRONTEND_COGNITO_APP_CLIENT_ID .env | cut -d= -f2)" >> frontend/.env

  echo "frontend/.env ファイルの不足している値を設定してください。"
fi

# Step 5: Move chat_app_bedrock to frontend directory
section "ステップ 5: chat_app_bedrock をフロントエンドディレクトリに移動中"

if [ -d chat_app_bedrock ] && [ ! -d frontend/chat_app_bedrock ]; then
  echo "chat_app_bedrock をフロントエンドディレクトリに移動中..."
  mv chat_app_bedrock frontend/
fi

section "デプロイが正常に完了しました！"
echo "次のステップ:"
echo "1. 合成データを生成: cd device-management && python synthetic_data.py"
echo "2. フロントエンドをセットアップ: frontend/README.md の手順に従ってください"
echo "3. システムをテスト: Q CLI またはチャットアプリケーションを使用して MCP サーバーと対話"
echo "4. システムを監視: CloudWatch Logs と X-Ray トレースでオブザーバビリティデータを確認"
echo ""
echo "Gateway URL: $GATEWAY_URL"
echo ""
echo "オブザーバビリティ情報:"
echo "- CloudWatch ログ グループ: /aws/bedrock-agentcore/device-management-agent"
echo "- X-Ray トレース: Agent Runtime で有効"
echo "- メトリクス: CloudWatch Metrics の 'device-management-agent' 名前空間で利用可能"
echo ""
echo "ログを表示: https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logsV2:log-groups"
echo "トレースを表示: https://console.aws.amazon.com/xray/home?region=us-west-2#/traces"
