#!/bin/bash

# SDK Agent test with MCP Gateway integration
echo "🧪 SDK エージェント → MCP Gateway → Lambda ツール → AWS サービス (エンドツーエンド) をテスト中"

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
echo "🌍 リージョン: $AWS_DEFAULT_REGION"

# Stop any existing container
docker stop test-sdk-mcp 2>/dev/null || true
docker rm test-sdk-mcp 2>/dev/null || true

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
echo "🚀 MCP テスト用に AWS 認証情報付きで SDK エージェントを起動中..."
docker run -d \
  --name test-sdk-mcp \
  -p 8081:8080 \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
  -e AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  agentcore-sdk-agent:latest

# Wait for startup and OAuth/MCP initialization
echo "⏳ エージェントの起動と OAuth/MCP 初期化を待機中..."
sleep 15

# Check if container is running
if ! docker ps | grep -q test-sdk-mcp; then
    echo "❌ コンテナの起動に失敗しました。ログを確認中..."
    docker logs test-sdk-mcp
    exit 1
fi

# Check container logs for OAuth and MCP initialization
echo "📋 エージェントの初期化を確認中..."
docker logs test-sdk-mcp | grep -E "(OAuth|MCP|Gateway|M2M|token|✅|❌)" | tail -15

# Test ping endpoint
echo ""
echo "🏓 ping エンドポイントをテスト中..."
ping_response=$(curl -s http://localhost:8081/ping)
if [[ $ping_response == *"healthy"* ]]; then
    echo "✅ Ping 成功: $ping_response"
else
    echo "❌ Ping 失敗: $ping_response"
fi

echo ""
echo "🧪 MCP Gateway 経由で S3 バケット一覧をテスト中:"
echo "========================================"

# Create test request for S3 buckets (simpler than EC2)
cat > /tmp/test_sdk_s3_request.json << 'EOF'
{
  "prompt": "Can you list my S3 buckets? Please show their names and creation dates. Use the MCP gateway tools to get this information from AWS.",
  "session_id": "test-s3-mcp-123",
  "actor_id": "user"
}
EOF

echo "リクエスト: MCP Gateway 経由で S3 バケットを一覧表示"
echo "期待されるフロー: SDK エージェント → OAuth M2M トークン → MCP Gateway → Lambda ツール → AWS S3 API"
echo ""

# Make request with extended timeout for MCP calls
echo "レスポンス (SDK エージェント形式):"
echo "===================="
timeout 90s curl -s -X POST http://localhost:8081/invocations \
  -H "Content-Type: application/json" \
  -d @/tmp/test_sdk_s3_request.json

echo ""
echo ""
echo "🧪 MCP Gateway 経由で EC2 インスタンス一覧をテスト中:"
echo "========================================"

# Create test request for EC2 instances
cat > /tmp/test_sdk_ec2_request.json << 'EOF'
{
  "prompt": "Can you list all currently running EC2 instances in my AWS account? Please show their instance IDs, types, and states. Use the MCP gateway tools to get this information from AWS.",
  "session_id": "test-ec2-mcp-123", 
  "actor_id": "user"
}
EOF

echo "リクエスト: MCP Gateway 経由で実行中の EC2 インスタンスを一覧表示"
echo ""

echo "レスポンス (SDK エージェント形式):"
echo "===================="
timeout 90s curl -s -X POST http://localhost:8081/invocations \
  -H "Content-Type: application/json" \
  -d @/tmp/test_sdk_ec2_request.json

echo ""
echo ""
echo "📋 コンテナログ全文 (起動時):"
echo "========================================"
docker logs test-sdk-mcp | head -50

echo ""
echo "📋 コンテナログ全文 (最近):"
echo "========================================"
docker logs test-sdk-mcp | tail -50

echo ""
echo "🎯 テスト分析:"
echo "================="
echo "✅ M2M トークンが正常に取得されたか確認"
echo "✅ MCP Gateway 接続が確立されたか確認"
echo "✅ Lambda ツールが呼び出されたか確認"
echo "✅ AWS API 呼び出しが成功したか確認"
echo "✅ 結果がエージェントに返されたか確認"

echo ""
echo "🔍 さらにデバッグするには:"
echo "  - コンテナログを確認: docker logs test-sdk-mcp"
echo "  - CloudWatch で Lambda ログを確認: bac-mcp-function"
echo "  - AgentCore コンソールで Gateway ログを確認"
echo ""
echo "🧹 クリーンアップするには:"
echo "  docker stop test-sdk-mcp && docker rm test-sdk-mcp"