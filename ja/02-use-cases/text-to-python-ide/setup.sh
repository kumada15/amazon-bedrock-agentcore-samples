#!/bin/bash

echo "AgentCore Code Interpreter アプリケーションをセットアップ中..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 が必要ですがインストールされていません。Python 3.8 以上をインストールしてください。"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Node.js が必要ですがインストールされていません。Node.js 16 以上をインストールしてください。"
    exit 1
fi

# Create virtual environment for Python backend
echo "Python 仮想環境を作成中..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Python 依存関係をインストール中..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Node.js dependencies for frontend
echo "Node.js 依存関係をインストール中..."
cd frontend
npm install
cd ..

# Copy environment file
if [ ! -f .env ]; then
    echo "テンプレートから .env ファイルを作成中..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo ".env ファイルを編集して AWS 認証情報と設定を入力してください。"
    else
        echo "基本的な .env ファイルを作成中..."
        cat > .env << EOF
# AWS Configuration (choose one method)
AWS_PROFILE=default
AWS_REGION=us-east-1

# Application Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
REACT_APP_API_URL=http://localhost:8000
EOF
        echo "基本的な .env ファイルを作成しました。AWS 認証情報を設定してください。"
    fi
fi

# Run setup verification
echo "セットアップ検証を実行中..."
source venv/bin/activate
python tests/verify_setup.py

echo ""
echo "セットアップ完了！"
echo ""
echo "アーキテクチャ: ハイブリッド Strands + AgentCore"
echo "- コード生成: Claude Haiku 4.5 を使用した Strands Agent"
echo "- コード実行: Code Interpreter Tool を使用した AgentCore Agent"
echo ""
echo "アプリケーションを起動するには:"
echo "1. クイックスタート: ./start.sh"
echo "2. 手動起動:"
echo "   - バックエンド: source venv/bin/activate && python backend/main.py"
echo "   - フロントエンド: cd frontend && npm start"
echo ""
echo ".env ファイルで AWS 認証情報を設定してください。"
