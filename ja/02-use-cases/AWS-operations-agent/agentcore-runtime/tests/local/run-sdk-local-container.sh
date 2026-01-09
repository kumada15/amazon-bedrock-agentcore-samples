#!/bin/bash

# Local SDK Agent Test Runner
# This script builds and runs the SDK agent locally for testing

# Get the AgentCore project directory (go up 3 levels from tests/local to reach AgentCore root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTCORE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "🚀 ローカル SDK エージェントをビルドして実行中..."
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
echo "🔨 SDK Docker イメージをビルド中..."
docker build -f ./agentcore-runtime/deployment/Dockerfile.sdk -t agentcore-sdk:latest .

if [[ $? -ne 0 ]]; then
    echo "❌ Docker ビルドに失敗しました"
    exit 1
fi

echo "✅ Docker イメージのビルドに成功しました"
echo ""

# Stop and remove existing container if it exists
echo "🧹 既存のコンテナをクリーンアップ中..."
docker stop local-sdk-agent-test 2>/dev/null || true
docker rm local-sdk-agent-test 2>/dev/null || true

# Run the container
echo "🚀 SDK エージェントコンテナを起動中..."
docker run -d \
    --name local-sdk-agent-test \
    --network local-mcp-test \
    -p 8080:8080 \
    -e AWS_ACCESS_KEY_ID="$(aws configure get aws_access_key_id)" \
    -e AWS_SECRET_ACCESS_KEY="$(aws configure get aws_secret_access_key)" \
    -e AWS_SESSION_TOKEN="$(aws configure get aws_session_token)" \
    -e AWS_DEFAULT_REGION="$(aws configure get region)" \
    -e MCP_HOST="local-mcp-server-test" \
    agentcore-sdk:latest

if [[ $? -eq 0 ]]; then
    echo "✅ SDK エージェントコンテナの起動に成功しました"
    echo ""
    echo "📋 コンテナ詳細:"
    echo "   • 名前: local-sdk-agent-test"
    echo "   • ポート: 8080"
    echo "   • ネットワーク: local-mcp-test"
    echo "   • イメージ: agentcore-sdk:latest"
    echo ""
    echo "🔗 エージェントをテスト:"
    echo "   curl -X POST http://localhost:8080/invocations \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"prompt\": \"こんにちは！\", \"session_id\": \"test\", \"actor_id\": \"user\"}'"
    echo ""
    echo "📊 ログを監視:"
    echo "   docker logs -f local-sdk-agent-test"
    echo ""
    echo "🛑 コンテナを停止:"
    echo "   docker stop local-sdk-agent-test"
    echo ""
    echo "💡 注意: SDK エージェントは BedrockAgentCoreApp フレームワークを使用しています"
    echo "   レスポンス形式は DIY エージェントと異なる場合があります"
else
    echo "❌ SDK エージェントコンテナの起動に失敗しました"
    exit 1
fi
