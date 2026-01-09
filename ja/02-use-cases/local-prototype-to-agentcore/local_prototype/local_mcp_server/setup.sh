#!/bin/bash

# LocalMCP MCP Server Setup Script

echo "🚀 LocalMCP MCP Server をセットアップ中..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 仮想環境を作成中..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 仮想環境をアクティベート中..."
source venv/bin/activate

# Install dependencies
echo "📥 依存関係をインストール中..."
pip install -r requirements.txt

echo "✅ セットアップ完了！"
echo ""
echo "サーバーを実行するには:"
echo "  source venv/bin/activate"
echo "  python server.py"
echo ""
echo "デモクライアントを実行するには:"
echo "  python client.py"
echo ""
echo "インタラクティブモードで実行するには:"
echo "  python client.py -i"
