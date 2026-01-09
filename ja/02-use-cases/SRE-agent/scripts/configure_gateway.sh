#!/bin/bash

# Configure Gateway Script for SRE Agent
# Manages gateway configuration and backend services

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# File paths
GATEWAY_URI_FILE="$PROJECT_ROOT/gateway/.gateway_uri"
ACCESS_TOKEN_FILE="$PROJECT_ROOT/gateway/.access_token"
AGENT_CONFIG_FILE="$PROJECT_ROOT/sre_agent/config/agent_config.yaml"
ENV_FILE="$PROJECT_ROOT/sre_agent/.env"

# Default gateway URI for reverse operation
DEFAULT_GATEWAY_URI="https://your-agentcore-gateway-endpoint.gateway.bedrock-agentcore.us-east-1.amazonaws.com"

# Function to show usage
show_usage() {
    echo "使用法: $0 [OPTIONS]"
    echo ""
    echo "オプション:"
    echo "  --cleanup       Gateway URI をデフォルトのプレースホルダーにリセット"
    echo "  --help, -h      このヘルプメッセージを表示"
    echo ""
    echo "説明:"
    echo "  このスクリプトは SRE Agent を実際の AgentCore Gateway を使用するように設定します。"
    echo "  gateway ディレクトリから Gateway URI とアクセストークンを読み取り、"
    echo "  設定ファイルを更新します。"
    echo ""
    echo "  通常操作:"
    echo "  1. 実行中のバックエンドサーバーを停止"
    echo "  2. 新しいアクセストークンを生成"
    echo "  3. EC2 インスタンスのプライベート IP を取得"
    echo "  4. SSL でバックエンドサーバーを起動"
    echo "  5. エージェント設定の Gateway URI を更新"
    echo "  6. .env ファイルのアクセストークンを更新"
    echo ""
    echo "  クリーンアップ操作 (--cleanup):"
    echo "  - Gateway URI をプレースホルダー値にリセット"
    echo "  - 開発/テストモードに便利"
}

# Function to check if file exists
check_file() {
    local file="$1"
    local description="$2"

    if [ ! -f "$file" ]; then
        echo "エラー: $file に $description が見つかりません"
        return 1
    fi
    return 0
}

# Function to update YAML file
update_gateway_uri_in_yaml() {
    local uri="$1"
    local config_file="$2"

    echo "$config_file の Gateway URI を更新中"
    
    # Use sed to update the gateway URI line
    if grep -q "^  uri:" "$config_file"; then
        # Update existing uri line
        sed -i "s|^  uri:.*|  uri: \"$uri\"|" "$config_file"
    else
        # Add uri line if gateway section exists
        if grep -q "^gateway:" "$config_file"; then
            sed -i "/^gateway:/a\\  uri: \"$uri\"" "$config_file"
        else
            # Add entire gateway section
            echo "" >> "$config_file"
            echo "# Gateway configuration" >> "$config_file"
            echo "gateway:" >> "$config_file"
            echo "  uri: \"$uri\"" >> "$config_file"
        fi
    fi

    echo "Gateway URI を更新しました: $uri"
}

# Function to update or create .env file
update_env_file() {
    local token="$1"
    local env_file="$2"

    echo "$env_file のアクセストークンを更新中"
    
    # Create .env file if it doesn't exist
    if [ ! -f "$env_file" ]; then
        echo "# SRE Agent Environment Variables" > "$env_file"
    fi
    
    # Update or add GATEWAY_ACCESS_TOKEN
    if grep -q "^GATEWAY_ACCESS_TOKEN=" "$env_file"; then
        # Update existing token
        sed -i "s|^GATEWAY_ACCESS_TOKEN=.*|GATEWAY_ACCESS_TOKEN=\"$token\"|" "$env_file"
    else
        # Add new token
        echo "GATEWAY_ACCESS_TOKEN=\"$token\"" >> "$env_file"
    fi

    echo ".env ファイルのアクセストークンを更新しました"
}

# Function to get EC2 instance private IP
get_private_ip() {
    echo "EC2 インスタンスのプライベート IP を取得中..."
    
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
      -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s)
    PRIVATE_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
      -s http://169.254.169.254/latest/meta-data/local-ipv4)

    if [ -z "$PRIVATE_IP" ]; then
        echo "プライベート IP アドレスの取得に失敗しました"
        exit 1
    fi

    echo "プライベート IP: $PRIVATE_IP"
}

# Function to stop backend servers
stop_backend() {
    echo "バックエンドサーバーを停止中..."
    if [ -f "$PROJECT_ROOT/backend/scripts/stop_demo_backend.sh" ]; then
        cd "$PROJECT_ROOT"
        bash backend/scripts/stop_demo_backend.sh
    else
        echo "警告: バックエンド停止スクリプトが見つかりません。続行します..."
    fi
}

# Function to start backend servers
start_backend() {
    echo "バックエンドサーバーを起動中..."

    # Check if SSL certificates exist
    SSL_KEY="/etc/letsencrypt/live/$(hostname -f)/privkey.pem"
    SSL_CERT="/etc/letsencrypt/live/$(hostname -f)/fullchain.pem"

    # Alternative SSL paths to check
    if [ ! -f "$SSL_KEY" ] || [ ! -f "$SSL_CERT" ]; then
        SSL_KEY="/opt/ssl/privkey.pem"
        SSL_CERT="/opt/ssl/fullchain.pem"
    fi

    if [ -f "$SSL_KEY" ] && [ -f "$SSL_CERT" ]; then
        echo "SSL 証明書が見つかりました。HTTPS で起動します"
        cd "$PROJECT_ROOT"
        echo "実行中: bash backend/scripts/start_demo_backend.sh --host \"$PRIVATE_IP\" --ssl-keyfile \"$SSL_KEY\" --ssl-certfile \"$SSL_CERT\""
        bash backend/scripts/start_demo_backend.sh --host "$PRIVATE_IP" --ssl-keyfile "$SSL_KEY" --ssl-certfile "$SSL_CERT"
    else
        echo "警告: SSL 証明書が見つかりません。HTTP で起動します"
        cd "$PROJECT_ROOT"
        echo "実行中: bash backend/scripts/start_demo_backend.sh --host \"$PRIVATE_IP\""
        bash backend/scripts/start_demo_backend.sh --host "$PRIVATE_IP"
    fi
}

# Function to generate new token
generate_token() {
    echo "新しいアクセストークンを生成中..."
    if [ -f "$PROJECT_ROOT/gateway/generate_token.sh" ]; then
        cd "$PROJECT_ROOT/gateway"
        bash generate_token.sh
    else
        echo "エラー: トークン生成スクリプトが見つかりません"
        exit 1
    fi
}

# Parse command line arguments
CLEANUP_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --cleanup)
            CLEANUP_MODE=true
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

echo "SRE Agent Gateway 設定スクリプト"
echo "=========================================="

if [ "$CLEANUP_MODE" = true ]; then
    echo "クリーンアップモードで実行中 - デフォルト設定にリセット"

    # Check if agent config file exists
    if ! check_file "$AGENT_CONFIG_FILE" "Agent 設定ファイル"; then
        exit 1
    fi

    # Update gateway URI to default
    update_gateway_uri_in_yaml "$DEFAULT_GATEWAY_URI" "$AGENT_CONFIG_FILE"

    # Remove or comment out access token from .env file
    if [ -f "$ENV_FILE" ]; then
        echo ".env ファイルからアクセストークンを削除中"
        if grep -q "^GATEWAY_ACCESS_TOKEN=" "$ENV_FILE"; then
            # Comment out the existing token line
            sed -i 's|^GATEWAY_ACCESS_TOKEN=.*|# GATEWAY_ACCESS_TOKEN=removed_in_reverse_mode|' "$ENV_FILE"
            echo ".env ファイルからアクセストークンを削除しました"
        else
            echo ".env ファイルにアクセストークンが見つかりませんでした"
        fi
    else
        echo ".env ファイルが見つかりませんでした"
    fi

    echo "設定をデフォルト（開発モード）にリセットしました"
    echo "Gateway URI を設定しました: $DEFAULT_GATEWAY_URI"
    echo ".env ファイルからアクセストークンを削除しました"

else
    echo "通常モードで実行中 - 本番 Gateway 用に設定"
    
    # Step 1: Stop running servers
    stop_backend
    
    # Step 2: Generate new token
    generate_token
    
    # Step 3: Get private IP
    get_private_ip
    
    # Step 4: Start backend servers
    start_backend
    
    # Step 5: Check required files
    echo "必要なファイルを確認中..."

    if ! check_file "$GATEWAY_URI_FILE" "Gateway URI ファイル"; then
        echo "gateway/.gateway_uri に AgentCore Gateway エンドポイントが含まれていることを確認してください"
        exit 1
    fi

    if ! check_file "$ACCESS_TOKEN_FILE" "アクセストークンファイル"; then
        echo "まず gateway/generate_token.sh を実行してアクセストークンを作成してください"
        exit 1
    fi

    if ! check_file "$AGENT_CONFIG_FILE" "Agent 設定ファイル"; then
        exit 1
    fi

    # Step 6: Read gateway URI and access token
    echo "設定ファイルを読み込み中..."

    GATEWAY_URI=$(cat "$GATEWAY_URI_FILE" | tr -d '\n\r' | xargs)
    ACCESS_TOKEN=$(cat "$ACCESS_TOKEN_FILE" | tr -d '\n\r' | xargs)

    if [ -z "$GATEWAY_URI" ]; then
        echo "エラー: Gateway URI が空です"
        exit 1
    fi

    if [ -z "$ACCESS_TOKEN" ]; then
        echo "エラー: アクセストークンが空です"
        exit 1
    fi

    echo "Gateway URI: $GATEWAY_URI"
    echo "アクセストークン: ${ACCESS_TOKEN:0:20}..." # Show first 20 chars only

    # Step 7: Update configuration files
    update_gateway_uri_in_yaml "$GATEWAY_URI" "$AGENT_CONFIG_FILE"
    update_env_file "$ACCESS_TOKEN" "$ENV_FILE"

    echo ""
    echo "設定が正常に完了しました！"
    echo "Gateway URI: $GATEWAY_URI"
    echo "更新されたファイル:"
    echo "   - $AGENT_CONFIG_FILE"
    echo "   - $ENV_FILE"
    echo ""
    echo "バックエンドサーバーは SSL で $PRIVATE_IP 上で実行中です"
    echo "SRE Agent が本番 Gateway 用に設定されました"
fi

echo ""
echo "スクリプトが完了しました！"