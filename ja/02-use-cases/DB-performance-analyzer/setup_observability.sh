#!/bin/bash
set -e

echo "=== AgentCore Gateway オブザーバビリティをセットアップ中 ==="

# Make script executable
chmod +x scripts/enable_observability.sh

# Enable CloudWatch Transaction Search and configure log groups
echo "CloudWatch Transaction Search を有効化し、ロググループを設定中..."
./scripts/enable_observability.sh

echo "=== AgentCore Gateway オブザーバビリティセットアップ完了 ==="
echo "オブザーバビリティデータを表示するには、CloudWatch コンソールを開き、以下に移動してください:"
echo "  - Application Signals > Transaction search"
echo "  - Log groups > /aws/vendedlogs/bedrock-agentcore/<resource-id>"
echo "  - X-Ray > Traces"