#!/bin/bash

# Slide Deck Agent Demo - Environment Setup Script
# This script creates a Python virtual environment and installs all dependencies

set -e  # Exit on any error

echo "🧠 スライドデッキエージェントデモ - 環境セットアップ"
echo "=============================================="
echo

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 作業ディレクトリ: $SCRIPT_DIR"
echo

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 がインストールされていないか、PATH に含まれていません"
    echo "Python 3.10 以上をインストールしてから再試行してください"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "🐍 Python を検出: $PYTHON_VERSION"

# Check if virtual environment already exists
if [ -d "slide_demo_env" ]; then
    echo "⚠️  仮想環境は既に存在します"
    read -p "再作成しますか？ (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  既存の環境を削除中..."
        rm -rf slide_demo_env
    else
        echo "👍 既存の環境を使用します"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "slide_demo_env" ]; then
    echo "🏗️  仮想環境を作成中..."
    python3 -m venv slide_demo_env
    if [ $? -ne 0 ]; then
        echo "❌ 仮想環境の作成に失敗しました"
        exit 1
    fi
    echo "✅ 仮想環境を作成しました: slide_demo_env"
else
    echo "✅ 既存の仮想環境を使用します"
fi

echo

# Activate virtual environment
echo "🔄 仮想環境をアクティベート中..."
source slide_demo_env/bin/activate

if [ $? -ne 0 ]; then
    echo "❌ 仮想環境のアクティベートに失敗しました"
    exit 1
fi

echo "✅ 仮想環境をアクティベートしました"

# Verify we're in the virtual environment
VIRTUAL_ENV_PYTHON=$(which python)
echo "🐍 使用する Python: $VIRTUAL_ENV_PYTHON"

echo

# Upgrade pip
echo "⬆️  pip をアップグレード中..."
python -m pip install --upgrade pip --quiet

if [ $? -ne 0 ]; then
    echo "❌ pip のアップグレードに失敗しました"
    exit 1
fi

echo "✅ pip を正常にアップグレードしました"

echo

# Install requirements
echo "📦 requirements.txt から依存関係をインストール中..."
echo "   これには数分かかる場合があります..."

pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ 依存関係のインストールに失敗しました"
    echo "上記のエラーメッセージを確認して再試行してください"
    exit 1
fi

echo "✅ すべての依存関係を正常にインストールしました"

echo

# Verify key packages
echo "🧪 主要なインストールを確認中..."

# Test python-pptx
python -c "from pptx import Presentation; print('   ✅ python-pptx: OK')" 2>/dev/null || echo "   ❌ python-pptx: 失敗"

# Test Flask
python -c "from flask import Flask; print('   ✅ Flask: OK')" 2>/dev/null || echo "   ❌ Flask: 失敗"

# Test other key packages
python -c "import boto3; print('   ✅ boto3: OK')" 2>/dev/null || echo "   ❌ boto3: 失敗"
python -c "from jinja2 import Template; print('   ✅ Jinja2: OK')" 2>/dev/null || echo "   ❌ Jinja2: 失敗"

echo

# Check AWS credentials (optional)
echo "🔐 AWS 設定を確認中..."
if command -v aws &> /dev/null; then
    if aws sts get-caller-identity &> /dev/null; then
        echo "   ✅ AWS 認証情報が設定されています"
    else
        echo "   ⚠️  AWS 認証情報が設定されていません"
        echo "   💡 メモリ機能のために 'aws configure' を実行してください"
    fi
else
    echo "   ⚠️  AWS CLI が見つかりません"
    echo "   💡 完全な機能のために AWS CLI をインストールして 'aws configure' を実行してください"
fi

echo

# Success message
echo "🎉 環境セットアップが完了しました！"
echo
echo "📋 次のステップ:"
echo "   1. 環境をアクティベート (まだの場合):"
echo "      source slide_demo_env/bin/activate"
echo
echo "   2. デモを実行:"
echo "      python main.py"
echo
echo "   3. ブラウザを開く:"
echo "      http://localhost:5000"
echo
echo "   4. 終了時に無効化:"
echo "      deactivate"

# Create activation helper script
cat > activate_env.sh << 'EOF'
#!/bin/bash
# Helper script to activate the slide demo environment
source slide_demo_env/bin/activate
echo "🧠 スライドデモ環境をアクティベートしました！"
echo "'python main.py' を実行してデモを開始してください"
EOF

chmod +x activate_env.sh
echo "💡 ヘルパースクリプトを作成しました: ./activate_env.sh"

echo
echo "🚀 エージェントメモリの重要性をデモする準備ができました！"