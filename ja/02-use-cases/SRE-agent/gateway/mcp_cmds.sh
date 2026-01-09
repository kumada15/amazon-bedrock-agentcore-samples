#!/bin/bash

# MCP Commands Script
# This script contains various MCP commands for testing AgentCore Gateway

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "MCP Gateway コマンド"
echo "==================="
echo ""

# Check if required files exist in script directory
if [ ! -f "${SCRIPT_DIR}/.access_token" ]; then
    echo "エラー: ${SCRIPT_DIR} に .access_token ファイルが見つかりません"
    echo "まず generate_token.py または create_gateway.sh を実行してください"
    exit 1
fi

if [ ! -f "${SCRIPT_DIR}/.gateway_uri" ]; then
    echo "エラー: ${SCRIPT_DIR} に .gateway_uri ファイルが見つかりません"
    echo "まず create_gateway.sh を実行して Gateway を作成してください"
    exit 1
fi

echo ".access_token と .gateway_uri ファイルが見つかりました"
echo ""
# List available tools
echo "利用可能なツールを一覧表示中..."
TOOLS_RESPONSE=$(curl -vvv -sS --request POST --header 'Content-Type: application/json' \
--header "Authorization: Bearer $(cat ${SCRIPT_DIR}/.access_token)" \
--data '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}' \
"$(cat ${SCRIPT_DIR}/.gateway_uri)/mcp")

echo "$TOOLS_RESPONSE" | jq .

# Parse and display tool summary
echo ""
echo "ツール概要:"
echo "================"

# Extract tools array and count
TOOLS_COUNT=$(echo "$TOOLS_RESPONSE" | jq -r '.result.tools | length // 0')
echo "検出されたツール数: $TOOLS_COUNT"

if [ "$TOOLS_COUNT" -gt 0 ]; then
    echo ""
    echo "ツール名:"
    # Extract and display each tool name
    echo "$TOOLS_RESPONSE" | jq -r '.result.tools[]?.name // empty' | while IFS= read -r tool_name; do
        if [ -n "$tool_name" ]; then
            echo "   - $tool_name"
        fi
    done
else
    echo "レスポンスにツールが見つかりませんでした"
fi

echo ""

# Extract and call a specific tool - get_pod_status
echo "get_pod_status ツールをテスト中:"
echo "================================"

# Extract the get_pod_status tool name from the tools list
GET_POD_STATUS_TOOL=$(echo "$TOOLS_RESPONSE" | jq -r '.result.tools[]? | select(.name | contains("get_pod_status")) | .name // empty' | head -1)

if [ -n "$GET_POD_STATUS_TOOL" ]; then
    echo "ツールが見つかりました: $GET_POD_STATUS_TOOL"
    echo ""

    # Call get_pod_status with parameters based on OpenAPI spec
    # Parameters: namespace (optional), pod_name (optional)
    echo "namespace='production' で $GET_POD_STATUS_TOOL を呼び出し中..."
    
    POD_STATUS_RESPONSE=$(curl -vvv -sS --request POST --header 'Content-Type: application/json' \
    --header "Authorization: Bearer $(cat ${SCRIPT_DIR}/.access_token)" \
    --data '{
      "jsonrpc": "2.0",
      "id": 3,
      "method": "tools/call",
      "params": {
        "name": "'"$GET_POD_STATUS_TOOL"'",
        "arguments": {
          "namespace": "production"
        }
      }
    }' \
    "$(cat ${SCRIPT_DIR}/.gateway_uri)/mcp")

    echo "レスポンス:"
    echo "$POD_STATUS_RESPONSE" | jq .

    # Try another call with a specific pod name
    echo ""
    echo "pod_name='web-app-deployment-5c8d7f9b6d-k2n8p' で $GET_POD_STATUS_TOOL を呼び出し中..."
    
    SPECIFIC_POD_RESPONSE=$(curl -sS --request POST --header 'Content-Type: application/json' \
    --header "Authorization: Bearer $(cat ${SCRIPT_DIR}/.access_token)" \
    --data '{
      "jsonrpc": "2.0",
      "id": 4,
      "method": "tools/call",
      "params": {
        "name": "'"$GET_POD_STATUS_TOOL"'",
        "arguments": {
          "pod_name": "web-app-deployment-5c8d7f9b6d-k2n8p"
        }
      }
    }' \
    "$(cat ${SCRIPT_DIR}/.gateway_uri)/mcp")

    echo "レスポンス:"
    echo "$SPECIFIC_POD_RESPONSE" | jq .
else
    echo "get_pod_status ツールがツール一覧に見つかりませんでした"
fi

echo ""

# Extract and call a specific tool - get_performance_metrics
echo "get_performance_metrics ツールをテスト中:"
echo "========================================"

# Extract the get_performance_metrics tool name from the tools list
GET_PERFORMANCE_METRICS_TOOL=$(echo "$TOOLS_RESPONSE" | jq -r '.result.tools[]? | select(.name | contains("get_performance_metrics")) | .name // empty' | head -1)

if [ -n "$GET_PERFORMANCE_METRICS_TOOL" ]; then
    echo "ツールが見つかりました: $GET_PERFORMANCE_METRICS_TOOL"
    echo ""

    # Test 1: Call get_performance_metrics with metric_type='response_time' and service
    echo "metric_type='response_time' と service='web-service' で $GET_PERFORMANCE_METRICS_TOOL を呼び出し中..."
    
    PERF_METRICS_RESPONSE_1=$(curl -sS --request POST --header 'Content-Type: application/json' \
    --header "Authorization: Bearer $(cat ${SCRIPT_DIR}/.access_token)" \
    --data '{
      "jsonrpc": "2.0",
      "id": 5,
      "method": "tools/call",
      "params": {
        "name": "'"$GET_PERFORMANCE_METRICS_TOOL"'",
        "arguments": {
          "metric_type": "response_time",
          "service": "web-service"
        }
      }
    }' \
    "$(cat ${SCRIPT_DIR}/.gateway_uri)/mcp")

    echo "レスポンス:"
    echo "$PERF_METRICS_RESPONSE_1" | jq .

    # Test 2: Call get_performance_metrics with metric_type='memory_usage' and time range
    echo ""
    echo "metric_type='memory_usage' と時間範囲で $GET_PERFORMANCE_METRICS_TOOL を呼び出し中..."
    
    PERF_METRICS_RESPONSE_2=$(curl -sS --request POST --header 'Content-Type: application/json' \
    --header "Authorization: Bearer $(cat ${SCRIPT_DIR}/.access_token)" \
    --data '{
      "jsonrpc": "2.0",
      "id": 6,
      "method": "tools/call",
      "params": {
        "name": "'"$GET_PERFORMANCE_METRICS_TOOL"'",
        "arguments": {
          "metric_type": "memory_usage",
          "start_time": "2024-01-15T14:00:00Z",
          "end_time": "2024-01-15T15:00:00Z"
        }
      }
    }' \
    "$(cat ${SCRIPT_DIR}/.gateway_uri)/mcp")

    echo "レスポンス:"
    echo "$PERF_METRICS_RESPONSE_2" | jq .

    # Test 3: Call get_performance_metrics with metric_type='throughput' with service and time range
    echo ""
    echo "metric_type='throughput'、service='api-service' と時間範囲で $GET_PERFORMANCE_METRICS_TOOL を呼び出し中..."
    
    PERF_METRICS_RESPONSE_3=$(curl -sS --request POST --header 'Content-Type: application/json' \
    --header "Authorization: Bearer $(cat ${SCRIPT_DIR}/.access_token)" \
    --data '{
      "jsonrpc": "2.0",
      "id": 7,
      "method": "tools/call",
      "params": {
        "name": "'"$GET_PERFORMANCE_METRICS_TOOL"'",
        "arguments": {
          "metric_type": "throughput",
          "service": "api-service",
          "start_time": "2024-01-15T13:00:00Z",
          "end_time": "2024-01-15T14:00:00Z"
        }
      }
    }' \
    "$(cat ${SCRIPT_DIR}/.gateway_uri)/mcp")

    echo "レスポンス:"
    echo "$PERF_METRICS_RESPONSE_3" | jq .
else
    echo "get_performance_metrics ツールがツール一覧に見つかりませんでした"
fi

echo ""
