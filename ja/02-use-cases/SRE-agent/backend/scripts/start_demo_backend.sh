#!/bin/bash
# Start all demo backend servers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"

# Default SSL certificate paths (can be overridden)
SSL_KEYFILE="${SSL_KEYFILE:-}"
SSL_CERTFILE="${SSL_CERTFILE:-}"
HOST="${HOST:-localhost}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ssl-keyfile)
            SSL_KEYFILE="$2"
            shift 2
            ;;
        --ssl-certfile)
            SSL_CERTFILE="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --help|-h)
            echo "使用法: $0 [--host HOSTNAME] [--ssl-keyfile PATH] [--ssl-certfile PATH]"
            echo "  --host HOSTNAME       バインドするホスト名 (デフォルト: localhost)"
            echo "  --ssl-keyfile PATH    SSL 秘密鍵ファイルのパス"
            echo "  --ssl-certfile PATH   SSL 証明書ファイルのパス"
            echo ""
            echo "環境変数:"
            echo "  HOST                  バインドするホスト名"
            echo "  SSL_KEYFILE           SSL 秘密鍵ファイルのパス"
            echo "  SSL_CERTFILE          SSL 証明書ファイルのパス"
            echo ""
            echo "重要: SSL を使用する場合は、証明書が指定されたホスト名に対して有効であることを確認してください。"
            exit 0
            ;;
        *)
            echo "不明な引数: $1"
            echo "使用法については --help を使用してください"
            exit 1
            ;;
    esac
done

echo "🚀 SRE エージェント デモバックエンドを起動中..."

# 正しいディレクトリにいるか確認
if [ ! -d "$BACKEND_DIR/data" ]; then
    echo "❌ バックエンドのデータディレクトリが見つかりません。backend/ ディレクトリから実行してください"
    exit 1
fi

# Create logs directory
mkdir -p "$PROJECT_ROOT/logs"

# Prepare server arguments
SERVER_ARGS="--host '$HOST'"
if [ -n "$SSL_KEYFILE" ] && [ -n "$SSL_CERTFILE" ]; then
    SERVER_ARGS="$SERVER_ARGS --ssl-keyfile '$SSL_KEYFILE' --ssl-certfile '$SSL_CERTFILE'"
    echo "🔒 SSL 証明書を使用:"
    echo "   ホスト: $HOST"
    echo "   鍵: $SSL_KEYFILE"
    echo "   証明書: $SSL_CERTFILE"
    echo "⚠️  重要: SSL 証明書がホスト名 '$HOST' に対して有効であることを確認してください"
else
    echo "🌐 SSL なしで実行中 (HTTP モード)"
    echo "   ホスト: $HOST"
fi

# 適切なサーバー実装を使用して FastAPI サーバーを起動
echo "📊 FastAPI サーバーを起動中..."

# servers ディレクトリに移動
cd "$BACKEND_DIR/servers"

# K8s API サーバー (ポート 8011)
echo "🏗️  Kubernetes API サーバーをポート 8011 で起動中..."
nohup bash -c "python3 k8s_server.py $SERVER_ARGS" > "$PROJECT_ROOT/logs/k8s_server.log" 2>&1 &

# Logs API サーバー (ポート 8012)
echo "📋 Logs API サーバーをポート 8012 で起動中..."
nohup bash -c "python3 logs_server.py $SERVER_ARGS" > "$PROJECT_ROOT/logs/logs_server.log" 2>&1 &

# Metrics API サーバー (ポート 8013)
echo "📈 Metrics API サーバーをポート 8013 で起動中..."
nohup bash -c "python3 metrics_server.py $SERVER_ARGS" > "$PROJECT_ROOT/logs/metrics_server.log" 2>&1 &

# Runbooks API サーバー (ポート 8014)
echo "📚 Runbooks API サーバーをポート 8014 で起動中..."
nohup bash -c "python3 runbooks_server.py $SERVER_ARGS" > "$PROJECT_ROOT/logs/runbooks_server.log" 2>&1 &

# Wait a moment for servers to start
sleep 2

# Determine protocol for display
if [ -n "$SSL_KEYFILE" ] && [ -n "$SSL_CERTFILE" ]; then
    PROTOCOL="https"
else
    PROTOCOL="http"
fi

echo "✅ デモバックエンドが正常に起動しました！"
echo "📊 K8s API: $PROTOCOL://$HOST:8011"
echo "📋 Logs API: $PROTOCOL://$HOST:8012"
echo "📈 Metrics API: $PROTOCOL://$HOST:8013"
echo "📚 Runbooks API: $PROTOCOL://$HOST:8014"
echo ""
echo "📝 ログは $PROJECT_ROOT/logs/ に書き込まれています"
echo "🛑 すべてのサーバーを停止するには './scripts/stop_demo_backend.sh' を使用してください"