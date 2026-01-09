#!/bin/bash

# Simple DIY Agent test with AWS credentials
echo "🧪 AWS 認証情報付きシンプル DIY エージェントテスト..."

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
docker stop test-diy-simple 2>/dev/null || true
docker rm test-diy-simple 2>/dev/null || true

# Build fresh image with current configuration
echo "🔨 現在の設定で新しい DIY エージェントイメージをビルド中..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
DEPLOYMENT_DIR="$PROJECT_ROOT/agentcore-runtime/deployment"

cd "$DEPLOYMENT_DIR"
docker build --platform linux/arm64 -t agentcore-diy-agent:latest -f Dockerfile.diy ../../ > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ 最新の設定で新しいイメージをビルドしました"
else
    echo "❌ イメージのビルドに失敗しました"
    exit 1
fi

# Run container with AWS credentials
echo "🚀 AWS 認証情報付きで DIY エージェントを起動中..."
docker run -d \
  --name test-diy-simple \
  -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
  -e AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  agentcore-diy-agent:latest

# Wait for startup
echo "⏳ エージェントの起動を待機中..."
sleep 5

# Test simple prompt that should work with local tools
echo ""
echo "🧪 シンプルな時刻リクエストでテスト中:"
echo "================================"

cat > /tmp/test_time_request.json << 'EOF'
{
  "prompt": "What is the current time?",
  "session_id": "test-time-123",
  "actor_id": "user"
}
EOF

# Extract just the text content from streaming response
echo "レスポンス:"
curl -s -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d @/tmp/test_time_request.json | \
  grep '"type":"text_delta"' | \
  sed 's/.*"content":"\([^"]*\)".*/\1/' | \
  tr -d '\n'

echo ""
echo ""
echo "🧪 AWS 環境変数チェックでテスト中:"
echo "================================"

cat > /tmp/test_env_request.json << 'EOF'
{
  "prompt": "Can you tell me what AWS region environment variable is set? Use the get_current_time tool first to show you're working, then check if any AWS-related information is available to you.",
  "session_id": "test-env-123",
  "actor_id": "user"
}
EOF

echo "レスポンス:"
curl -s -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d @/tmp/test_env_request.json | \
  grep '"type":"text_delta"' | \
  sed 's/.*"content":"\([^"]*\)".*/\1/' | \
  tr -d '\n'

echo ""
echo ""
echo "🎉 シンプルテスト完了！"
echo "================================"
echo "コンテナログ全文を表示するには:"
echo "  docker logs test-diy-simple"
echo ""
echo "テストコンテナを停止するには:"
echo "  docker stop test-diy-simple && docker rm test-diy-simple"