#!/bin/bash

# Integrated Start Script for AgentCore Code Interpreter
# Includes automatic setup if dependencies are missing

echo "🚀 AgentCore Code Interpreter - アプリケーションを起動中"
echo "============================================================"

# Function to check if setup is needed
check_setup_needed() {
    local setup_needed=false

    # Check virtual environment
    if [ ! -d "venv" ]; then
        echo "📦 仮想環境が見つかりません"
        setup_needed=true
    fi

    # Check Python dependencies
    if [ -d "venv" ]; then
        source venv/bin/activate
        if ! python -c "import strands, bedrock_agentcore, fastapi" 2>/dev/null; then
            echo "📦 Python 依存関係が不足しています"
            setup_needed=true
        fi
        deactivate 2>/dev/null || true
    fi

    # Check frontend dependencies
    if [ ! -d "frontend/node_modules" ]; then
        echo "📦 フロントエンド依存関係が見つかりません"
        setup_needed=true
    fi

    # Check .env file
    if [ ! -f ".env" ]; then
        echo "⚙️  設定ファイル (.env) が見つかりません"
        setup_needed=true
    fi

    if [ "$setup_needed" = true ]; then
        return 0  # Setup needed
    else
        return 1  # Setup not needed
    fi
}

# Function to run setup
run_setup() {
    echo "🔧 自動セットアップを実行中..."

    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 が必要ですがインストールされていません。Python 3.8 以上をインストールしてください。"
        exit 1
    fi

    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        echo "❌ Node.js が必要ですがインストールされていません。Node.js 16 以上をインストールしてください。"
        exit 1
    fi

    # Create virtual environment for Python backend
    if [ ! -d "venv" ]; then
        echo "📦 Python 仮想環境を作成中..."
        python3 -m venv venv
    fi

    source venv/bin/activate

    # Install Python dependencies
    echo "📦 Python 依存関係をインストール中..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q

    # Install Node.js dependencies for frontend
    if [ ! -d "frontend/node_modules" ]; then
        echo "📦 Node.js 依存関係をインストール中..."
        cd frontend
        npm install --silent
        cd ..
    fi

    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        echo "⚙️  .env ファイルを作成中..."
        if [ -f .env.example ]; then
            cp .env.example .env
        else
            cat > .env << EOF
# AWS Configuration (choose one method)
AWS_PROFILE=default
AWS_REGION=us-east-1

# Application Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
REACT_APP_API_URL=http://localhost:8000
EOF
        fi
        echo "📝 .env ファイルで AWS 認証情報を設定してください"
    fi

    # Run setup verification
    echo "✅ セットアップを検証中..."
    if python tests/verify_setup.py > /dev/null 2>&1; then
        echo "✅ セットアップ検証に成功しました"
    else
        echo "⚠️  セットアップ検証に警告がありました（続行します）"
    fi

    deactivate
    echo "✅ セットアップが正常に完了しました"
}

# Function to check if backend is ready
check_backend() {
    local max_attempts=30
    local attempt=1

    echo "🔍 バックエンドの準備を待機中..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ バックエンドの準備ができました！"
            return 0
        fi

        if [ $attempt -eq 1 ]; then
            echo "⏳ バックエンドを起動中..."
        elif [ $((attempt % 5)) -eq 0 ]; then
            echo "⏳ まだ待機中... (${attempt}秒)"
        fi

        sleep 2
        attempt=$((attempt + 1))
    done

    echo "❌ 60秒後もバックエンドの起動に失敗しました"
    echo "🔧 ログを確認: tail -f backend.log"
    echo "🔧 診断を実行: python tests/verify_setup.py"
    return 1
}

# Function to start backend
start_backend() {
    echo "🚀 バックエンドサーバーを起動中..."

    # Kill any existing backend processes
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2

    # Start backend
    (
        source venv/bin/activate
        cd backend

        # Check if main.py exists
        if [ ! -f "main.py" ]; then
            echo "❌ backend/main.py が見つかりません"
            exit 1
        fi

        # Start the backend with error logging
        python main.py 2>&1 | tee ../backend.log &
        BACKEND_PID=$!
        echo $BACKEND_PID > ../backend.pid
        echo "📝 バックエンドが PID: $BACKEND_PID で起動しました"
    )
}

# Function to start frontend
start_frontend() {
    echo "🚀 フロントエンドサーバーを起動中..."

    # Kill any existing frontend processes
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    sleep 2

    cd frontend

    # Check if package.json exists
    if [ ! -f "package.json" ]; then
        echo "❌ frontend/package.json が見つかりません"
        exit 1
    fi

    # Start the frontend
    npm start 2>&1 | tee ../frontend.log &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../frontend.pid
    echo "📝 フロントエンドが PID: $FRONTEND_PID で起動しました"
    cd ..
}

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 サーバーをシャットダウン中..."

    # Kill backend
    if [ -f backend.pid ]; then
        BACKEND_PID=$(cat backend.pid)
        kill $BACKEND_PID 2>/dev/null || true
        rm -f backend.pid
    fi

    # Kill frontend
    if [ -f frontend.pid ]; then
        FRONTEND_PID=$(cat frontend.pid)
        kill $FRONTEND_PID 2>/dev/null || true
        rm -f frontend.pid
    fi

    # Kill any remaining processes on ports
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true

    echo "✅ クリーンアップ完了"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    # Check if setup is needed and run it
    if check_setup_needed; then
        echo "🔧 セットアップが必要です。自動セットアップを実行中..."
        run_setup
        echo ""
    else
        echo "✅ セットアップを確認しました。アプリケーションを起動中..."
    fi

    # Start backend
    start_backend

    # Wait for backend to be ready
    if ! check_backend; then
        echo "❌ バックエンドなしでフロントエンドを起動できません"
        cleanup
        exit 1
    fi

    # Start frontend
    start_frontend

    echo ""
    echo "🎉 アプリケーションが正常に起動しました！"
    echo "📊 バックエンド:  http://localhost:8000"
    echo "🌐 フロントエンド: http://localhost:3000"
    echo ""
    echo "📋 ログ:"
    echo "   バックエンド:  tail -f backend.log"
    echo "   フロントエンド: tail -f frontend.log"
    echo ""
    echo "Ctrl+C でアプリケーションを停止"
    echo ""

    # Wait for user interrupt
    while true; do
        sleep 1
    done
}

# Run main function
main
