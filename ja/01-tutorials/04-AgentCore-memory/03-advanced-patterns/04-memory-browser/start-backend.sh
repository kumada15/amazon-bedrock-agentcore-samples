#!/bin/bash

# AgentCore Memory Dashboard Backend の起動
echo "🚀 AgentCore Memory Dashboard Backend を起動しています..."

# 正しいディレクトリにいるか確認
if [ ! -f "backend/app.py" ]; then
    echo "❌ エラー: backend/app.py が見つかりません。agentcore-memory-dashboard ディレクトリからこのスクリプトを実行してください。"
    exit 1
fi

# 仮想環境が存在しない場合は作成
if [ ! -d "backend/venv" ]; then
    echo "📦 Python 仮想環境を作成しています..."
    cd backend
    python3 -m venv venv
    cd ..
fi

# 仮想環境をアクティブ化
echo "🔧 仮想環境をアクティブ化しています..."
source backend/venv/bin/activate

# 依存関係をインストール
echo "📦 Python 依存関係をインストールしています..."
cd backend
pip install -r requirements.txt

# bedrock-agentcore が利用可能か確認
echo "🔍 AgentCore Memory SDK を確認しています..."
python -c "
try:
    from bedrock_agentcore.memory import MemoryClient
    print('✅ bedrock-agentcore SDK が利用可能です')
except ImportError:
    print('⚠️  bedrock-agentcore SDK が見つかりません')
    print('   バックエンドは開発用にモックデータを使用します')
    print('   インストールするには: pip install bedrock-agentcore')
"

# バックエンドサーバーを起動
echo "🚀 FastAPI バックエンドサーバーを起動しています..."
echo "📍 バックエンドは http://localhost:8000 でアクセスできます"
echo "📖 API ドキュメントは http://localhost:8000/docs でアクセスできます"
echo ""
echo "サーバーを停止するには Ctrl+C を押してください"

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
