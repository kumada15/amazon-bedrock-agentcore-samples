#!/bin/bash
set -e

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

echo "psycopg2 Lambda レイヤーを作成中..."

# Get the script directory and project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Use the existing zip file
ZIP_FILE="$PROJECT_DIR/psycopg2-layer.zip"

# Check if the zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "エラー: psycopg2-layer.zip が見つかりません"
    exit 1
fi

echo "既存の psycopg2-layer.zip ファイルを使用します"

# Create Lambda layer
LAYER_VERSION=$(aws lambda publish-layer-version \
  --layer-name psycopg2-layer \
  --description "psycopg2 PostgreSQL driver" \
  --license-info "MIT" \
  --compatible-runtimes python3.12 \
  --zip-file fileb://$ZIP_FILE \
  --region $AWS_REGION)

LAYER_ARN=$(echo $LAYER_VERSION | jq -r '.LayerVersionArn')

# Create config directory if it doesn't exist
mkdir -p "$PROJECT_DIR/config"

# Save layer ARN to config file
echo "export PSYCOPG2_LAYER_ARN=$LAYER_ARN" > "$PROJECT_DIR/config/layer_config.env"
echo "レイヤー ARN を $PROJECT_DIR/config/layer_config.env に保存しました"

echo "psycopg2 Lambda レイヤーを作成しました。ARN: $LAYER_ARN"

echo "レイヤー作成完了"