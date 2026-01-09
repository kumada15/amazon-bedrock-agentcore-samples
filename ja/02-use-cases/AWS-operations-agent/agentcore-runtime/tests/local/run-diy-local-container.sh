#!/bin/bash

# Local DIY Agent Test Runner
# This script builds and runs the DIY agent locally for testing

# Get the AgentCore project directory (go up 3 levels from tests/local to reach AgentCore root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTCORE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "🚀 ローカル DIY エージェントをビルドして実行中..."
echo "📁 AgentCore ルート: $AGENTCORE_ROOT"
echo ""

# Verify we're in the right directory
if [[ ! -d "$AGENTCORE_ROOT/agentcore-runtime" ]]; then
    echo "❌ エラー: $AGENTCORE_ROOT に agentcore-runtime ディレクトリが見つかりません"
    echo "   期待される構造: $AGENTCORE_ROOT/agentcore-runtime"
    exit 1
fi

# Change to AgentCore root for Docker build context
cd "$AGENTCORE_ROOT"

# Build the Docker image
echo "🔨 Docker イメージをビルド中..."
docker build -f ./agentcore-runtime/deployment/Dockerfile.diy -t agentcore-diy:latest .

if [[ $? -ne 0 ]]; then
    echo "❌ Docker ビルドに失敗しました"
    exit 1
fi

echo "✅ Docker イメージのビルドに成功しました"
echo ""

# Stop and remove existing container if it exists
echo "🧹 既存のコンテナをクリーンアップ中..."
docker stop local-diy-agent-test 2>/dev/null || true
docker rm local-diy-agent-test 2>/dev/null || true

# Run the container
echo "🚀 DIY エージェントコンテナを起動中..."
docker run -d \
    --name local-diy-agent-test \
    --network local-mcp-test \
    -p 8080:8080 \
    -e AWS_ACCESS_KEY_ID="$(aws configure get aws_access_key_id)" \
    -e AWS_SECRET_ACCESS_KEY="$(aws configure get aws_secret_access_key)" \
    -e AWS_SESSION_TOKEN="$(aws configure get aws_session_token)" \
    -e AWS_DEFAULT_REGION="$(aws configure get region)" \
    -e MCP_HOST="local-mcp-server-test" \
    agentcore-diy:latest

if [[ $? -eq 0 ]]; then
    echo "✅ DIY エージェントコンテナの起動に成功しました"
    echo ""
    echo "📋 コンテナ詳細:"
    echo "   • 名前: local-diy-agent-test"
    echo "   • ポート: 8080"
    echo "   • ネットワーク: local-mcp-test"
    echo "   • イメージ: agentcore-diy:latest"
    echo ""
    echo "🔗 エージェントをテスト:"
    echo "   curl -X POST http://localhost:8080/invocations \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"prompt\": \"こんにちは！\", \"session_id\": \"test\", \"actor_id\": \"user\"}'"
    echo ""
    echo "📊 ログを監視:"
    echo "   docker logs -f local-diy-agent-test"
    echo ""
    echo "🛑 コンテナを停止:"
    echo "   docker stop local-diy-agent-test"
else
    echo "❌ DIY エージェントコンテナの起動に失敗しました"
    exit 1
fi
