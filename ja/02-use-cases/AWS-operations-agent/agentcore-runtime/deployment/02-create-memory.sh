#!/bin/bash

# AgentCore Memory Resource Creation
# Creates memory resource for conversation storage and retrieval

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "🧠 AgentCore メモリリソースを作成中..."
echo "========================================"

# Load configuration
if [ -f "$PROJECT_ROOT/config/static-config.yaml" ]; then
    MEMORY_NAME=$(yq eval '.memory.name' "$PROJECT_ROOT/config/static-config.yaml" 2>/dev/null || echo "bac-agent-memory")
    MEMORY_DESCRIPTION=$(yq eval '.memory.description' "$PROJECT_ROOT/config/static-config.yaml" 2>/dev/null || echo "BAC Agent conversation memory storage")
    EVENT_EXPIRY_DAYS=$(yq eval '.memory.event_expiry_days' "$PROJECT_ROOT/config/static-config.yaml" 2>/dev/null || echo "90")
    REGION=$(yq eval '.aws.region' "$PROJECT_ROOT/config/static-config.yaml" 2>/dev/null || echo "us-east-1")
else
    echo "⚠️ 設定ファイルが見つかりません。デフォルト値を使用します"
    MEMORY_NAME="bac-agent-memory"
    MEMORY_DESCRIPTION="BAC Agent conversation memory storage"
    EVENT_EXPIRY_DAYS="90"
    REGION="us-east-1"
fi

echo "📋 メモリ設定:"
echo "   • 名前: $MEMORY_NAME"
echo "   • 説明: $MEMORY_DESCRIPTION"
echo "   • イベント有効期限: $EVENT_EXPIRY_DAYS 日"
echo "   • リージョン: $REGION"
echo ""

# Check if memory already exists
echo "🔍 既存のメモリリソースを確認中..."
EXISTING_MEMORY=$(python3 -c "
import json
from bedrock_agentcore.memory import MemoryClient

try:
    client = MemoryClient(region_name='$REGION')
    memories = client.list_memories()
    
    for memory in memories:
        if memory.get('name') == '$MEMORY_NAME':
            print(json.dumps(memory, default=str))
            exit(0)
    
    print('null')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    exit(1)
" 2>/dev/null)

if [ "$EXISTING_MEMORY" != "null" ] && [ -n "$EXISTING_MEMORY" ]; then
    echo "✅ メモリリソースは既に存在します"
    MEMORY_ID=$(echo "$EXISTING_MEMORY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('id', ''))")
    MEMORY_STATUS=$(echo "$EXISTING_MEMORY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', ''))")
    
    echo "   • メモリ ID: $MEMORY_ID"
    echo "   • ステータス: $MEMORY_STATUS"

    if [ "$MEMORY_STATUS" != "AVAILABLE" ] && [ "$MEMORY_STATUS" != "ACTIVE" ]; then
        echo "⚠️ メモリリソースは存在しますが利用できません (ステータス: $MEMORY_STATUS)"
        echo "   メモリが利用可能になるまで待機中..."
        
        # Wait for memory to be ready
        python3 -c "
from bedrock_agentcore.memory import MemoryClient
import time

client = MemoryClient(region_name='$REGION')
memory_id = '$MEMORY_ID'

print('⏳ Waiting for memory resource to be ready...')
for i in range(60):  # Wait up to 5 minutes
    try:
        memories = client.list_memories()
        for memory in memories:
            if memory.get('id') == memory_id:
                status = memory.get('status', '')
                if status in ['AVAILABLE', 'ACTIVE']:
                    print(f'✅ Memory resource is now {status}')
                    exit(0)
                else:
                    print(f'   Status: {status} (attempt {i+1}/60)')
                    time.sleep(5)
                    break
    except Exception as e:
        print(f'   Error checking status: {e}')
        time.sleep(5)

print('❌ Memory resource did not become available within timeout')
exit(1)
"
    fi
else
    echo "🚀 新しいメモリリソースを作成中..."
    
    # Create memory resource with basic configuration
    MEMORY_RESULT=$(python3 -c "
import json
import sys
from bedrock_agentcore.memory import MemoryClient

try:
    client = MemoryClient(region_name='$REGION')
    
    # Create memory resource first (we can add strategies later)
    memory = client.create_memory(
        name='$MEMORY_NAME',
        description='$MEMORY_DESCRIPTION',
        event_expiry_days=$EVENT_EXPIRY_DAYS
    )
    
    print(json.dumps(memory, default=str))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    exit(1)
")
    
    if [ $? -eq 0 ]; then
        MEMORY_ID=$(echo "$MEMORY_RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('id', ''))")
        echo "✅ メモリリソースの作成に成功しました"
        echo "   • メモリ ID: $MEMORY_ID"

        # Wait for memory to be available
        echo "⏳ メモリリソースが利用可能になるまで待機中..."
        python3 -c "
from bedrock_agentcore.memory import MemoryClient
import time

client = MemoryClient(region_name='$REGION')
memory_id = '$MEMORY_ID'

for i in range(60):  # Wait up to 5 minutes
    try:
        memories = client.list_memories()
        for memory in memories:
            if memory.get('id') == memory_id:
                status = memory.get('status', '')
                if status in ['AVAILABLE', 'ACTIVE']:
                    print(f'✅ Memory resource is {status} and ready')
                    exit(0)
                else:
                    print(f'   Status: {status} (attempt {i+1}/60)')
                    time.sleep(5)
                    break
    except Exception as e:
        print(f'   Error checking status: {e}')
        time.sleep(5)

print('❌ Memory resource did not become available within timeout')
exit(1)
"
    else
        echo "❌ メモリリソースの作成に失敗しました"
        echo "$MEMORY_RESULT"
        exit 1
    fi
fi

# Update dynamic configuration with memory ID
echo ""
echo "📝 動的設定を更新中..."

# Ensure dynamic config exists
if [ ! -f "$PROJECT_ROOT/config/dynamic-config.yaml" ]; then
    echo "# Dynamic configuration generated by deployment scripts" > "$PROJECT_ROOT/config/dynamic-config.yaml"
fi

# Update or add memory section
python3 -c "
import yaml
import sys
from datetime import datetime

config_file = '$PROJECT_ROOT/config/dynamic-config.yaml'

try:
    # Load existing config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f) or {}
    
    # Update memory section with comprehensive details
    config['memory'] = {
        'id': '$MEMORY_ID',
        'name': '$MEMORY_NAME', 
        'region': '$REGION',
        'status': 'available',
        'event_expiry_days': $EVENT_EXPIRY_DAYS,
        'created_at': datetime.now().isoformat(),
        'description': '$MEMORY_DESCRIPTION'
    }
    
    # Write updated config maintaining existing structure
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
    
    print('✅ Dynamic configuration updated with memory details')
    print(f'   • Memory ID: $MEMORY_ID')
    print(f'   • Memory Name: $MEMORY_NAME')
    print(f'   • Region: $REGION')
    print(f'   • Event Expiry: $EVENT_EXPIRY_DAYS days')
    
except Exception as e:
    print(f'❌ Failed to update configuration: {e}')
    sys.exit(1)
"

# Fix quote consistency: Convert single quotes to double quotes for empty strings
# This ensures compatibility with other deployment scripts that expect double quotes
echo "📝 dynamic-config.yaml のクォート一貫性を確保中..."
sed -i '' "s/: ''/: \"\"/g" "$PROJECT_ROOT/config/dynamic-config.yaml"

# Fix the scopes array format to maintain consistency (remove YAML list format and use JSON array)
# First remove any existing "- api" line under scopes
sed -i '' '/^  scopes:$/,/^[^ ]/ { /^  - api$/d; }' "$PROJECT_ROOT/config/dynamic-config.yaml"
# Then ensure scopes line has the proper JSON array format
sed -i '' 's/^  scopes:$/  scopes: ["api"]/' "$PROJECT_ROOT/config/dynamic-config.yaml"

# Verify memory resource is accessible
echo ""
echo "🧪 メモリリソースへのアクセスをテスト中..."
python3 -c "
from bedrock_agentcore.memory import MemoryClient

try:
    client = MemoryClient(region_name='$REGION')
    memories = client.list_memories()
    
    memory_found = False
    for memory in memories:
        if memory.get('id') == '$MEMORY_ID':
            memory_found = True
            status = memory.get('status', 'unknown')
            strategies = memory.get('strategies', [])
            
            print(f'✅ Memory resource verified:')
            print(f'   • ID: {memory.get(\"id\")}')
            print(f'   • Name: {memory.get(\"name\")}')
            print(f'   • Status: {status}')
            print(f'   • Strategies: {len(strategies)} configured')
            
            if strategies:
                for i, strategy in enumerate(strategies):
                    strategy_type = strategy.get('type', 'unknown')
                    print(f'     - Strategy {i+1}: {strategy_type}')
            
            break
    
    if not memory_found:
        print('❌ Memory resource not found in list')
        exit(1)
        
except Exception as e:
    print(f'❌ Failed to verify memory resource: {e}')
    exit(1)
"

echo ""
echo "🎉 AgentCore メモリリソースのセットアップ完了！"
echo "==========================================="
echo "✅ メモリ ID: $MEMORY_ID"
echo "✅ 設定を更新: config/dynamic-config.yaml"
echo "✅ メモリリソースはエージェントで使用可能です"
echo ""
echo "📋 概要:"
echo "   • エージェントは会話コンテキストの保存と取得が可能になりました"
echo "   • 自動ストラテジーは設定なし - 純粋な会話ストレージ"
echo "   • イベントは $EVENT_EXPIRY_DAYS 日後に期限切れになります"
echo "   • DIY と SDK の両方のエージェントがこのメモリリソースを使用します"
echo ""
echo "🔍 後でメモリステータスを確認するには:"
echo "   aws bedrock-agentcore-control list-memories --region $REGION"