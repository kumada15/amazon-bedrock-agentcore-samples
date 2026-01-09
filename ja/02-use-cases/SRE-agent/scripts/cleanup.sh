#!/bin/bash

# Cleanup Script for SRE Agent
# Deletes AgentCore Gateway, Gateway Targets, and Agent Runtime

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values - can be overridden with environment variables or arguments
DEFAULT_GATEWAY_NAME="sre-agent-gateway"
DEFAULT_RUNTIME_NAME="sre-agent"
DEFAULT_REGION="us-east-1"

# Parse command line arguments
GATEWAY_NAME="${GATEWAY_NAME:-$DEFAULT_GATEWAY_NAME}"
RUNTIME_NAME="${RUNTIME_NAME:-$DEFAULT_RUNTIME_NAME}"
REGION="${REGION:-$DEFAULT_REGION}"
FORCE_DELETE=false

# Function to read gateway name from config.yaml
read_gateway_name_from_config() {
    local config_file="$PROJECT_ROOT/gateway/config.yaml"
    
    if [ -f "$config_file" ]; then
        # Extract gateway_name from YAML, handling quoted and unquoted values
        local gateway_name=$(grep "^gateway_name:" "$config_file" | cut -d':' -f2- | sed 's/^[ \t]*//' | sed 's/^"\([^"]*\)".*/\1/' | sed 's/[ \t]*#.*//')
        if [ -n "$gateway_name" ]; then
            echo "$gateway_name"
            return 0
        fi
    fi
    
    # Return empty string if not found
    echo ""
    return 1
}

# Function to show usage
show_usage() {
    echo "使用法: $0 [OPTIONS]"
    echo ""
    echo "オプション:"
    echo "  --gateway-name NAME     削除する Gateway 名 (デフォルト: gateway/config.yaml から自動検出)"
    echo "  --runtime-name NAME     削除する Runtime 名 (デフォルト: $DEFAULT_RUNTIME_NAME)"
    echo "  --region REGION         AWS リージョン (デフォルト: $DEFAULT_REGION)"
    echo "  --force                 確認プロンプトをスキップ"
    echo "  --help, -h              このヘルプメッセージを表示"
    echo ""
    echo "環境変数:"
    echo "  GATEWAY_NAME           デフォルトの Gateway 名を上書き"
    echo "  RUNTIME_NAME           デフォルトの Runtime 名を上書き"
    echo "  REGION                 デフォルトの AWS リージョンを上書き"
    echo ""
    echo "説明:"
    echo "  このスクリプトは SRE Agent の AWS リソースを完全にクリーンアップします:"
    echo "  1. バックエンドサーバーを停止"
    echo "  2. すべての Gateway ターゲットを削除"
    echo "  3. AgentCore Gateway を削除"
    echo "  4. メモリリソースを削除"
    echo "  5. AgentCore Runtime を削除"
    echo "  6. 生成されたファイルを削除"
    echo ""
    echo "例:"
    echo "  $0                                          # デフォルトを使用"
    echo "  $0 --gateway-name my-gateway --force       # カスタム Gateway、プロンプトなし"
    echo "  GATEWAY_NAME=test-gw $0                     # 環境変数を使用"
}

# Function to confirm deletion
confirm_deletion() {
    if [ "$FORCE_DELETE" = true ]; then
        return 0
    fi

    echo "警告: 以下の AWS リソースが完全に削除されます:"
    echo "   - Gateway: $GATEWAY_NAME"
    echo "   - Runtime: $RUNTIME_NAME"
    echo "   - メモリリソース (存在する場合)"
    echo "   - リージョン: $REGION"
    echo ""
    echo "   この操作は元に戻せません！"
    echo ""
    read -p "続行しますか？ ('yes' と入力して確認): " confirmation

    if [ "$confirmation" != "yes" ]; then
        echo "ユーザーによりクリーンアップがキャンセルされました"
        exit 1
    fi
}

# Function to stop backend servers
stop_backend_servers() {
    echo "バックエンドサーバーを停止中..."
    if [ -f "$PROJECT_ROOT/backend/scripts/stop_demo_backend.sh" ]; then
        cd "$PROJECT_ROOT"
        bash backend/scripts/stop_demo_backend.sh || echo "警告: バックエンド停止スクリプトが失敗したか、サーバーが実行されていません"
    else
        echo "警告: バックエンド停止スクリプトが見つかりません。続行します..."
    fi
}

# Function to delete gateway and targets
delete_gateway() {
    echo "AgentCore Gateway とターゲットを削除中..."
    
    # Use the gateway deletion functionality from main.py
    cd "$PROJECT_ROOT/gateway"
    
    # Check if gateway exists and delete it
    python3 -c "
import sys
import boto3
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Import the deletion functions from main.py
sys.path.append('.')
from main import _check_gateway_exists, _delete_gateway

try:
    client = boto3.client('bedrock-agentcore-control', region_name='$REGION')
    
    # Check if gateway exists
    gateway_id = _check_gateway_exists(client, '$GATEWAY_NAME')
    
    if gateway_id:
        print(f'🗑️  Deleting gateway: $GATEWAY_NAME (ID: {gateway_id})')
        _delete_gateway(client, gateway_id)
        print('✅ Gateway and all targets deleted successfully')
    else:
        print('ℹ️  Gateway \"$GATEWAY_NAME\" not found, skipping deletion')
        
except ClientError as e:
    print(f'❌ Failed to delete gateway: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error deleting gateway: {e}')
    sys.exit(1)
"
}

# Function to delete agent runtime
delete_agent_runtime() {
    echo "AgentCore Runtime を削除中..."
    
    # Use the runtime deletion functionality from deploy_agent_runtime.py
    cd "$PROJECT_ROOT/deployment"
    
    python3 -c "
import sys
import boto3
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Import the deletion functions from deploy_agent_runtime.py
sys.path.append('.')
from deploy_agent_runtime import _get_agent_runtime_id_by_name, _delete_agent_runtime

try:
    client = boto3.client('bedrock-agentcore-control', region_name='$REGION')
    
    # Get runtime ID by name
    runtime_id = _get_agent_runtime_id_by_name(client, '$RUNTIME_NAME')
    
    if runtime_id:
        print(f'🗑️  Deleting runtime: $RUNTIME_NAME (ID: {runtime_id})')
        success = _delete_agent_runtime(client, runtime_id)
        if success:
            print('✅ Agent runtime deleted successfully')
        else:
            print('❌ Failed to delete agent runtime')
            sys.exit(1)
    else:
        print('ℹ️  Runtime \"$RUNTIME_NAME\" not found, skipping deletion')
        
except ClientError as e:
    print(f'❌ Failed to delete runtime: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error deleting runtime: {e}')
    sys.exit(1)
"
}

# Function to delete memory resources
delete_memory() {
    echo "メモリリソースを削除中..."

    cd "$PROJECT_ROOT"

    # Check if .memory_id file exists
    if [ ! -f ".memory_id" ]; then
        echo ".memory_id ファイルが見つかりません。メモリ削除をスキップします"
        return 0
    fi

    MEMORY_ID=$(cat .memory_id | tr -d '\n\r' | xargs)
    if [ -z "$MEMORY_ID" ]; then
        echo "警告: Memory ID ファイルが空です。メモリ削除をスキップします"
        return 0
    fi

    echo "メモリリソースを削除中: $MEMORY_ID"
    
    # Use the memory deletion functionality from manage_memories.py
    python3 -c "
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path('.')
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    from bedrock_agentcore.memory import MemoryClient
    
    memory_id = '$MEMORY_ID'
    
    print(f'🗑️  Deleting memory resource: {memory_id}')
    memory_client = MemoryClient(region_name='$REGION')
    
    result = memory_client.delete_memory_and_wait(
        memory_id=memory_id, max_wait=300, poll_interval=10
    )
    
    print('✅ Memory resource deleted successfully')
    
except ImportError as e:
    print(f'⚠️  Could not import memory client: {e}')
    print('ℹ️  Memory deletion skipped - ensure dependencies are installed')
except Exception as e:
    print(f'❌ Failed to delete memory resource: {e}')
    # Don't exit with error as this shouldn't stop the cleanup process
    print('⚠️  Continuing with cleanup despite memory deletion failure')
"
}

# Function to clean up generated files
cleanup_local_files() {
    echo "生成されたファイルをクリーンアップ中..."

    cd "$PROJECT_ROOT"

    # Remove gateway files
    if [ -f "gateway/.gateway_uri" ]; then
        rm -f gateway/.gateway_uri
        echo "gateway/.gateway_uri を削除しました"
    fi

    if [ -f "gateway/.access_token" ]; then
        rm -f gateway/.access_token
        echo "gateway/.access_token を削除しました"
    fi

    # Remove agent runtime files
    if [ -f "deployment/.agent_arn" ]; then
        rm -f deployment/.agent_arn
        echo "deployment/.agent_arn を削除しました"
    fi

    # Remove memory ID file
    if [ -f ".memory_id" ]; then
        rm -f .memory_id
        echo ".memory_id を削除しました"
    fi

}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --gateway-name)
            GATEWAY_NAME="$2"
            shift 2
            ;;
        --runtime-name)
            RUNTIME_NAME="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --force)
            FORCE_DELETE=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "不明な引数: $1"
            echo "使用法については --help を使用してください"
            exit 1
            ;;
    esac
done

# Try to auto-detect gateway name from config if not explicitly set
if [ "$GATEWAY_NAME" = "$DEFAULT_GATEWAY_NAME" ]; then
    CONFIG_GATEWAY_NAME=$(read_gateway_name_from_config)
    if [ -n "$CONFIG_GATEWAY_NAME" ]; then
        GATEWAY_NAME="$CONFIG_GATEWAY_NAME"
    fi
fi

# Main execution
echo "SRE Agent クリーンアップスクリプト"
echo "=========================="
echo ""
echo "設定:"
echo "  Gateway 名: $GATEWAY_NAME"
if [ -n "$CONFIG_GATEWAY_NAME" ] && [ "$GATEWAY_NAME" = "$CONFIG_GATEWAY_NAME" ]; then
    echo "    (gateway/config.yaml から自動検出)"
fi
echo "  Runtime 名: $RUNTIME_NAME"
echo "  リージョン: $REGION"
echo ""

# Confirm deletion unless --force is used
confirm_deletion

echo "クリーンアップ処理を開始..."
echo ""

# Step 1: Stop backend servers
stop_backend_servers
echo ""

# Step 2: Delete gateway and targets
delete_gateway
echo ""

# Step 3: Delete memory resources
delete_memory
echo ""

# Step 4: Delete agent runtime
delete_agent_runtime
echo ""

# Step 5: Clean up generated files
cleanup_local_files
echo ""

echo "クリーンアップが正常に完了しました！"
echo ""
echo "実行されたアクションの概要:"
echo "   - バックエンドサーバーを停止しました"
echo "   - AgentCore Gateway とすべてのターゲットを削除しました"
echo "   - メモリリソースを削除しました"
echo "   - AgentCore Runtime を削除しました"
echo "   - 生成されたファイルを削除しました"
echo ""
echo "すべての SRE Agent AWS リソースが削除されました。"