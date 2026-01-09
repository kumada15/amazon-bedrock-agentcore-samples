#!/bin/bash

# Manual start script for troubleshooting

echo "手動起動 - AgentCore Code Interpreter"
echo "=" * 50

# Step 1: Check environment
echo "1. 環境を確認中..."
if [ ! -d "venv" ]; then
    echo "❌ 仮想環境が見つかりません。./setup.sh を実行してください"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ .env ファイルが見つかりません。.env.example からコピーして設定してください。"
    exit 1
fi

echo "✅ 環境ファイルが見つかりました"

# Step 2: Activate virtual environment
echo ""
echo "2. 仮想環境をアクティベート中..."
source venv/bin/activate
echo "✅ 仮想環境がアクティベートされました"

# Step 3: Run diagnostics
echo ""
echo "3. 診断を実行中..."
python diagnose_backend.py
if [ $? -ne 0 ]; then
    echo "❌ 診断に失敗しました。上記の問題を修正してください。"
    exit 1
fi

# Step 4: Start backend manually
echo ""
echo "4. バックエンドを起動中（手動モード）..."
echo "📝 バックエンドはフォアグラウンドで実行されます。フロントエンド用に別のターミナルを開いてください。"
echo "🔗 バックエンド URL: http://localhost:8000"
echo "🔗 ヘルスチェック: http://localhost:8000/health"
echo ""
echo "⏹ Ctrl+C でバックエンドを停止"
echo ""

cd backend
python main.py
