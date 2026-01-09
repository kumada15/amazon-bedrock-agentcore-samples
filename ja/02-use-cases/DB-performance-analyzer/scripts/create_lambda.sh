#!/bin/bash
set -e

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Load configurations
source "$PROJECT_DIR/config/iam_config.env"
source "$PROJECT_DIR/config/cognito_config.env"

echo "DB Performance Analyzer 用 Lambda 関数を作成中..."

# Use the correct path to the pg_analyze_performance.py file
PG_ANALYZE_PY_FILE="$SCRIPT_DIR/pg_analyze_performance.py"
if [ -f "$PG_ANALYZE_PY_FILE" ]; then
    echo "$PG_ANALYZE_PY_FILE の pg_analyze_performance.py を使用します"
else
    echo "エラー: $PG_ANALYZE_PY_FILE に pg_analyze_performance.py が見つかりません"
    exit 1
fi

# Create a directory for the Lambda code
LAMBDA_DIR=$(mktemp -d)
echo "$LAMBDA_DIR に Lambda パッケージを作成中"
cp "$PG_ANALYZE_PY_FILE" "$LAMBDA_DIR/lambda_function.py"

# Create a zip file for the Lambda function
ZIP_FILE=$(mktemp).zip
(cd "$LAMBDA_DIR" && zip -r "$ZIP_FILE" .)
echo "$ZIP_FILE に zip ファイルを作成しました"

# Load VPC configuration if available
if [ -f "$PROJECT_DIR/config/vpc_config.env" ]; then
    source "$PROJECT_DIR/config/vpc_config.env"
    echo "VPC 設定を読み込みました"
    echo "VPC ID: $VPC_ID"
    echo "サブネット ID: $SUBNET_IDS"
    echo "Lambda セキュリティグループ ID: $LAMBDA_SECURITY_GROUP_ID"
    echo "DB セキュリティグループ ID: $DB_SECURITY_GROUP_IDS"
    
    # Check if LAMBDA_SECURITY_GROUP_ID is set
    if [ -z "$LAMBDA_SECURITY_GROUP_ID" ]; then
        echo "エラー: vpc_config.env に LAMBDA_SECURITY_GROUP_ID が設定されていません"
        exit 1
    fi
    
    # Prepare VPC config JSON
    VPC_CONFIG="{\"SubnetIds\":[\"${SUBNET_IDS//,/\",\"}\"],\"SecurityGroupIds\":[\"$LAMBDA_SECURITY_GROUP_ID\"]}"
    echo "VPC 設定: $VPC_CONFIG"
    
    # Load layer configuration if available
    LAYERS_PARAM=""
    if [ -f "$PROJECT_DIR/config/layer_config.env" ]; then
        source "$PROJECT_DIR/config/layer_config.env"
        if [ ! -z "$PSYCOPG2_LAYER_ARN" ]; then
            LAYERS_PARAM="--layers $PSYCOPG2_LAYER_ARN"
            echo "psycopg2 レイヤーを使用します: $PSYCOPG2_LAYER_ARN"
        else
            echo "警告: layer_config.env の PSYCOPG2_LAYER_ARN が空です"
        fi
    else
        echo "警告: $PROJECT_DIR/config/layer_config.env に layer_config.env が見つかりません"
        echo "psycopg2 レイヤーを作成中..."
        "$SCRIPT_DIR/create_psycopg2_layer.sh"
        if [ -f "$PROJECT_DIR/config/layer_config.env" ]; then
            source "$PROJECT_DIR/config/layer_config.env"
            if [ ! -z "$PSYCOPG2_LAYER_ARN" ]; then
                LAYERS_PARAM="--layers $PSYCOPG2_LAYER_ARN"
                echo "psycopg2 レイヤーを使用します: $PSYCOPG2_LAYER_ARN"
            else
                echo "エラー: レイヤー作成後も PSYCOPG2_LAYER_ARN が空です"
                exit 1
            fi
        else
            echo "エラー: レイヤー作成後も layer_config.env が見つかりません"
            exit 1
        fi
    fi
    
    # Create the Lambda function with VPC configuration
    echo "VPC 設定付きで Lambda 関数を作成中..."
    LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name DBPerformanceAnalyzer \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$ZIP_FILE \
      --vpc-config "$VPC_CONFIG" \
      $LAYERS_PARAM \
      --timeout 30 \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
    
else
    # Create the Lambda function without VPC configuration
    echo "VPC 設定なしで Lambda 関数を作成中..."
    LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name DBPerformanceAnalyzer \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$ZIP_FILE \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
fi

LAMBDA_ARN=$(echo $LAMBDA_RESPONSE | jq -r '.FunctionArn')
echo "Lambda 関数を作成しました: $LAMBDA_ARN"

# Add permission for Gateway to invoke Lambda
echo "Gateway が Lambda を呼び出すための権限を追加中..."
echo "Gateway ロール ARN: $GATEWAY_ROLE_ARN"

# Add permission for Gateway service to invoke Lambda
aws lambda add-permission \
  --function-name DBPerformanceAnalyzer \
  --statement-id GatewayServiceInvoke \
  --action lambda:InvokeFunction \
  --principal bedrock-agentcore.amazonaws.com \
  --region $AWS_REGION

# Add permission for Gateway role to invoke Lambda
aws lambda add-permission \
  --function-name DBPerformanceAnalyzer \
  --statement-id GatewayRoleInvoke \
  --action lambda:InvokeFunction \
  --principal $GATEWAY_ROLE_ARN \
  --region $AWS_REGION

# Clean up temporary files
rm -rf $LAMBDA_DIR
rm $ZIP_FILE

# Create config directory if it doesn't exist
mkdir -p "$PROJECT_DIR/config"

# Save Lambda ARN to config
cat > "$PROJECT_DIR/config/lambda_config.env" << EOF
export LAMBDA_ARN=$LAMBDA_ARN
EOF

# Create PGStat Lambda function
echo "PGStat Lambda 関数を作成中..."

# Use the correct path to the pgstat_analyse_database.py file
PGSTAT_PY_FILE="$SCRIPT_DIR/pgstat_analyse_database.py"
if [ -f "$PGSTAT_PY_FILE" ]; then
    echo "$PGSTAT_PY_FILE の pgstat_analyse_database.py を使用します"
else
    echo "エラー: $PGSTAT_PY_FILE に pgstat_analyse_database.py が見つかりません"
    exit 1
fi

# Create a directory for the Lambda code
PGSTAT_LAMBDA_DIR=$(mktemp -d)
echo "$PGSTAT_LAMBDA_DIR に PGStat Lambda パッケージを作成中"
cp "$PGSTAT_PY_FILE" "$PGSTAT_LAMBDA_DIR/lambda_function.py"

# Create a zip file for the Lambda function
PGSTAT_ZIP_FILE=$(mktemp).zip
(cd "$PGSTAT_LAMBDA_DIR" && zip -r "$PGSTAT_ZIP_FILE" .)
echo "$PGSTAT_ZIP_FILE に PGStat zip ファイルを作成しました"

# Create the Lambda function with VPC configuration if available
if [ -f "$PROJECT_DIR/config/vpc_config.env" ]; then
    # VPC config already loaded above
    
    # Create the Lambda function with VPC configuration
    echo "VPC 設定付きで PGStat Lambda 関数を作成中..."
    PGSTAT_LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name PGStatAnalyzeDatabase \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$PGSTAT_ZIP_FILE \
      --vpc-config "$VPC_CONFIG" \
      $LAYERS_PARAM \
      --timeout 300 \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
    
else
    # Create the Lambda function without VPC configuration
    echo "VPC 設定なしで PGStat Lambda 関数を作成中..."
    PGSTAT_LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name PGStatAnalyzeDatabase \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$PGSTAT_ZIP_FILE \
      --timeout 300 \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
fi

PGSTAT_LAMBDA_ARN=$(echo $PGSTAT_LAMBDA_RESPONSE | jq -r '.FunctionArn')
echo "PGStat Lambda 関数を作成しました: $PGSTAT_LAMBDA_ARN"

# Add permission for Gateway to invoke PGStat Lambda
echo "Gateway が PGStat Lambda を呼び出すための権限を追加中..."
echo "Gateway ロール ARN: $GATEWAY_ROLE_ARN"

# Add permission for Gateway service to invoke PGStat Lambda
aws lambda add-permission \
  --function-name PGStatAnalyzeDatabase \
  --statement-id GatewayServiceInvoke \
  --action lambda:InvokeFunction \
  --principal bedrock-agentcore.amazonaws.com \
  --region $AWS_REGION

# Add permission for Gateway role to invoke PGStat Lambda
aws lambda add-permission \
  --function-name PGStatAnalyzeDatabase \
  --statement-id GatewayRoleInvoke \
  --action lambda:InvokeFunction \
  --principal $GATEWAY_ROLE_ARN \
  --region $AWS_REGION

# Clean up temporary files
rm -rf $PGSTAT_LAMBDA_DIR
rm $PGSTAT_ZIP_FILE

# Append PGStat Lambda ARN to config
cat >> "$PROJECT_DIR/config/lambda_config.env" << EOF
export PGSTAT_LAMBDA_ARN=$PGSTAT_LAMBDA_ARN
EOF

echo "Lambda 関数のセットアップが正常に完了しました"