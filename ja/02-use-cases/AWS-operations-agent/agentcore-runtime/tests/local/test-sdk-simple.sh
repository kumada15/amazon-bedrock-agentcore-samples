#!/bin/bash

# Simple SDK Agent test with AWS credentials
echo "🧪 AWS 認証情報付きシンプル SDK エージェントテスト..."

# Get current AWS credentials
AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)
AWS_SESSION_TOKEN=$(aws configure get aws_session_token)
AWS_DEFAULT_REGION=$(aws configure get region || echo "us-east-1")

# Check if we have credentials
if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "❌ AWS 認証情報が見つかりません。先に 'aws configure' を実行してください。"
    exit 1
fi

echo "✅ アカウントの AWS 認証情報を検出しました: $(aws sts get-caller-identity --query Account --output text)"

# Stop any existing container
docker stop test-sdk-simple 2>/dev/null || true
docker rm test-sdk-simple 2>/dev/null || true

# Build fresh image with current configuration
echo "🔨 現在の設定で新しい SDK エージェントイメージをビルド中..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
DEPLOYMENT_DIR="$PROJECT_ROOT/agentcore-runtime/deployment"

cd "$DEPLOYMENT_DIR"
docker build --platform linux/arm64 -t agentcore-sdk-agent:latest -f Dockerfile.sdk ../../ > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ 最新の設定で新しいイメージをビルドしました"
else
    echo "❌ イメージのビルドに失敗しました"
    exit 1
fi

# Run container with AWS credentials
echo "🚀 AWS 認証情報付きで SDK エージェントを起動中..."
docker run -d \
  --name test-sdk-simple \
  -p 8081:8080 \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
  -e AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  agentcore-sdk-agent:latest

# Wait for startup
echo "⏳ エージェントの起動を待機中..."
sleep 8

# Check if container is running
if ! docker ps | grep -q test-sdk-simple; then
    echo "❌ コンテナの起動に失敗しました。ログを確認中..."
    docker logs test-sdk-simple
    exit 1
fi

# Test ping endpoint first
echo "🏓 ping エンドポイントをテスト中..."
ping_response=$(curl -s http://localhost:8081/ping)
if [[ $ping_response == *"healthy"* ]]; then
    echo "✅ Ping 成功: $ping_response"
else
    echo "❌ Ping 失敗: $ping_response"
    echo "📋 コンテナログ:"
    docker logs test-sdk-simple | tail -20
    exit 1
fi

# Test simple prompt that should work with local tools
echo ""
echo "🧪 シンプルな時刻リクエストでテスト中:"
echo "================================"

# Create a simple test payload for SDK agent (BedrockAgentCoreApp format)
cat > /tmp/test_sdk_time_request.json << 'EOF'
{
  "prompt": "What is the current time?",
  "session_id": "test-time-123",
  "actor_id": "user"
}
EOF

echo "リクエストペイロード:"
cat /tmp/test_sdk_time_request.json
echo ""

# SDK agent uses /invocations endpoint but might have different response format
echo "レスポンス:"
response=$(curl -s -X POST http://localhost:8081/invocations \
  -H "Content-Type: application/json" \
  -d @/tmp/test_sdk_time_request.json)

echo "$response"

echo ""
echo ""
echo "🧪 基本的なツール使用でテスト中:"
echo "================================"

cat > /tmp/test_sdk_tool_request.json << 'EOF'
{
  "prompt": "Please use the get_current_time tool to show me the time, then echo back the message 'SDK Agent is working!'",
  "session_id": "test-tool-123",
  "actor_id": "user"  
}
EOF

echo "リクエストペイロード:"
cat /tmp/test_sdk_tool_request.json
echo ""

echo "レスポンス:"
response=$(curl -s -X POST http://localhost:8081/invocations \
  -H "Content-Type: application/json" \
  -d @/tmp/test_sdk_tool_request.json)

echo "$response"

echo ""
echo ""
echo "📋 コンテナ起動ログ:"
echo "================================"
docker logs test-sdk-simple | head -30

echo ""
echo "📋 最近のコンテナログ:"
echo "================================"
docker logs test-sdk-simple | tail -20

echo ""
echo "🎉 シンプルテスト完了！"
echo "================================"
echo "SDK エージェントコンテナ詳細:"
echo "  コンテナ: test-sdk-simple"
echo "  ポート: 8081"
echo "  エンドポイント: http://localhost:8081"
echo ""
echo "コンテナログ全文を表示するには:"
echo "  docker logs test-sdk-simple"
echo ""
echo "テストコンテナを停止するには:"
echo "  docker stop test-sdk-simple && docker rm test-sdk-simple"