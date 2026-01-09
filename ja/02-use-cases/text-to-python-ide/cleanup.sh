#!/bin/bash

# Cleanup script for AgentCore Code Interpreter

echo "🧹 AgentCore Code Interpreter をクリーンアップ中..."

# Stop running processes
echo "⏹ 実行中のプロセスを停止中..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Clean up log files
echo "📄 ログファイルをクリーンアップ中..."
rm -f backend.log frontend.log *.pid

# Clean up temporary files
echo "🗑 一時ファイルをクリーンアップ中..."
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true

# Clean up frontend build files
echo "🌐 フロントエンドビルドファイルをクリーンアップ中..."
rm -rf frontend/build
rm -rf frontend/.eslintcache

# Clean up node_modules (optional - uncomment if needed)
echo "📦 node_modules をクリーンアップ中..."
rm -rf frontend/node_modules

# Clean up Python virtual environment (optional - uncomment if needed)
echo "🐍 仮想環境をクリーンアップ中..."
rm -rf venv

echo "✅ クリーンアップ完了！"
echo ""
echo "アプリケーションを再起動するには:"
echo "  1. ./setup.sh を実行 (venv または node_modules を削除した場合)"
echo "  2. ./start.sh を実行"
