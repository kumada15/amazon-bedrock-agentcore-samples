#!/bin/bash
set -e

echo "=== DB Performance Analyzer 用 AgentCore Gateway セットアップ ==="
echo "このスクリプトは AgentCore Gateway に必要なすべてのリソースを作成します"

# Create config directory
mkdir -p config

# Step 1: Install required packages
echo "ステップ 1: 必要なパッケージをインストール中..."
# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "仮想環境を作成中..."
    python3 -m venv venv
fi

# Activate virtual environment and install packages
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Step 2: Create IAM role for Gateway
echo "ステップ 2: Gateway 用 IAM ロールを作成中..."
./scripts/create_iam_roles.sh

# Step 3: Set up Cognito resources
echo "ステップ 3: Cognito リソースをセットアップ中..."
source venv/bin/activate
python3 scripts/setup_cognito.py
deactivate

# Load Cognito configuration
if [ -f "config/cognito_config.env" ]; then
    source config/cognito_config.env
    echo "Cognito 設定を読み込みました"
else
    echo "エラー: config/cognito_config.env が見つかりません"
    exit 1
fi

# Step 4: Create psycopg2 Lambda layer
echo "ステップ 4: psycopg2 Lambda レイヤーを作成中..."
./scripts/create_psycopg2_layer.sh

# Step 5: Get VPC configuration from database cluster
echo "ステップ 5: VPC 設定を取得中..."
# Check if we have database configuration
if [ -f "config/db_prod_config.env" ]; then
    source config/db_prod_config.env
    if [ ! -z "$DB_CLUSTER_NAME" ]; then
        source venv/bin/activate
        python3 scripts/get_vpc_config.py --cluster-name "$DB_CLUSTER_NAME"
        deactivate
    else
        echo "警告: config/db_prod_config.env に DB_CLUSTER_NAME が見つかりません"
    fi
elif [ -f "config/db_dev_config.env" ]; then
    source config/db_dev_config.env
    if [ ! -z "$DB_CLUSTER_NAME" ]; then
        source venv/bin/activate
        python3 scripts/get_vpc_config.py --cluster-name "$DB_CLUSTER_NAME"
        deactivate
    else
        echo "警告: config/db_dev_config.env に DB_CLUSTER_NAME が見つかりません"
    fi
else
    echo "警告: データベース設定が見つかりません。Lambda は VPC 設定なしで作成されます。"
fi

# Step 5b: Create VPC endpoints for AWS services
if [ -f "config/vpc_config.env" ]; then
    echo "ステップ 5b: AWS サービス用 VPC エンドポイントを作成中..."
    chmod +x ./scripts/create_vpc_endpoints.sh
    ./scripts/create_vpc_endpoints.sh
fi

# Step 6: Create Lambda function
echo "ステップ 6: Lambda 関数を作成中..."
./scripts/create_lambda.sh

# Step 7: Create Gateway
echo "ステップ 7: Gateway を作成中..."
# Load IAM configuration
if [ -f "config/iam_config.env" ]; then
    source config/iam_config.env
    echo "GATEWAY_ROLE_ARN: $GATEWAY_ROLE_ARN で IAM 設定を読み込みました"
else
    echo "エラー: config/iam_config.env が見つかりません。IAM ロールを再作成中..."
    ./scripts/create_iam_roles.sh
    if [ -f "config/iam_config.env" ]; then
        source config/iam_config.env
        echo "GATEWAY_ROLE_ARN: $GATEWAY_ROLE_ARN で IAM 設定を読み込みました"
    else
        echo "エラー: IAM ロールの作成に失敗しました"
        exit 1
    fi
fi

# Set the role ARN for the gateway
export ROLE_ARN=$GATEWAY_ROLE_ARN
echo "ROLE_ARN=$ROLE_ARN を設定中"

# Create the gateway
source venv/bin/activate
python3 scripts/create_gateway.py
deactivate

# Load Gateway configuration
if [ -f "config/gateway_config.env" ]; then
    source config/gateway_config.env
    echo "GATEWAY_IDENTIFIER: $GATEWAY_IDENTIFIER で Gateway 設定を読み込みました"
else
    echo "警告: config/gateway_config.env が見つかりません。親ディレクトリを確認中..."
    if [ -f "../config/gateway_config.env" ]; then
        # Copy the file to the expected location
        cp ../config/gateway_config.env config/
        source config/gateway_config.env
        echo "GATEWAY_IDENTIFIER: $GATEWAY_IDENTIFIER で Gateway 設定を読み込みました"
    else
        echo "エラー: どの場所にも Gateway 設定が見つかりません"
        exit 1
    fi
fi

# Step 8: Create Gateway Target
echo "ステップ 8: Gateway ターゲットを作成中..."
# Export environment variables for lambda-target-analyze-db-performance.py
export LAMBDA_ARN=$LAMBDA_ARN
export TARGET_NAME="db-performance-analyzer"
export TARGET_DESCRIPTION="DB Performance Analyzer tools"

# Create the target using create_target.py
source venv/bin/activate
python3 scripts/create_target.py
deactivate

# Step 9: Test Gateway
echo "ステップ 9: Gateway をテスト中..."
# Construct the gateway endpoint
MCP_ENDPOINT="https://${GATEWAY_IDENTIFIER}.gateway.bedrock-agentcore.${REGION}.amazonaws.com/mcp"

# Get a fresh token
echo "テスト用に新しいトークンを取得中..."
source venv/bin/activate
python3 scripts/get_token.py
deactivate

# Reload the Cognito configuration to get the fresh token
if [ -f "config/cognito_config.env" ]; then
    source config/cognito_config.env
    echo "config/cognito_config.env から新しいトークンを読み込みました"
fi

# Test listing tools with the correct format
echo "正しいフォーマットで listTools をテスト中..."
curl -s -X POST \
  -H "Authorization: Bearer $COGNITO_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "list-tools-request",
    "method": "tools/list",
    "params": {}
  }' \
  "$MCP_ENDPOINT" | jq .

# Test invoking explain_query tool with the correct format
echo -e "\n正しいフォーマットで invokeTool をテスト中..."
curl -s -X POST \
  -H "Authorization: Bearer $COGNITO_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "invoke-tool-request",
    "method": "tools/call",
    "params": {
      "name": "db-performance-analyzer___explain_query",
      "arguments": {
        "environment": "dev",
        "action_type": "explain_query",
        "query": "SELECT version()"
      }
    }
  }' \
  "$MCP_ENDPOINT" | jq .

# Test invoking slow_query tool with the correct format
echo -e "\nslow_query ツールをテスト中..."
curl -s -X POST \
  -H "Authorization: Bearer $COGNITO_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "invoke-slow-query-request",
    "method": "tools/call",
    "params": {
      "name": "pgstat-analyzer___slow_query",
      "arguments": {
        "environment": "dev",
        "action_type": "slow_query"
      }
    }
  }' \
  "$MCP_ENDPOINT" | jq .

echo -e "\n=== セットアップ完了 ==="
echo "Gateway ID: $GATEWAY_IDENTIFIER"
echo "Gateway エンドポイント: $MCP_ENDPOINT"
if [ -f "config/target_config.env" ]; then
    source config/target_config.env
    echo "ターゲット ID: $TARGET_ID"
fi
echo "リソースをクリーンアップするには: ./cleanup.sh を実行してください"