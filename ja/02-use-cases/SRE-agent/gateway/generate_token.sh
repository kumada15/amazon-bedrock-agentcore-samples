#!/bin/bash

# Generate Cognito access token for SRE Agent Gateway
# Extracts token generation functionality from create_gateway.sh

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load environment variables from .env file
if [ -f "${SCRIPT_DIR}/.env" ]; then
    echo "環境変数を gateway/.env ファイルから読み込み中..."
    # Source the .env file safely
    set -a  # automatically export all variables
    source "${SCRIPT_DIR}/.env"
    set +a  # stop automatically exporting
else
    echo "エラー: gateway ディレクトリに .env ファイルが見つかりません"
    echo "COGNITO_* 変数を含む .env ファイルを作成してください"
    exit 1
fi

# Generate Cognito access token
echo "Cognito アクセストークンを生成中..."
echo ".env ファイルに COGNITO_* 変数が設定されていることを確認してください"

cd "${SCRIPT_DIR}"
if python generate_token.py; then
    echo "アクセストークンの生成に成功しました！"
    echo "アクセストークンを .access_token に保存しました"
else
    echo "アクセストークンの生成に失敗しました"
    exit 1
fi