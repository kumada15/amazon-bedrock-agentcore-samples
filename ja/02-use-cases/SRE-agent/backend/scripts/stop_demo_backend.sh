#!/bin/bash
# Stop all demo backend servers

set -e

echo "SRE Agent デモバックエンドを停止中..."

# Find and kill all demo server processes (k8s, logs, metrics, runbooks servers)
DEMO_PIDS=$(pgrep -f "_server\.py" || echo "")

if [ -z "$DEMO_PIDS" ]; then
    echo "デモバックエンドプロセスが見つかりませんでした"
    exit 0
fi

echo "デモバックエンドプロセスが見つかりました: $DEMO_PIDS"

# Show which processes we're killing
echo "停止するプロセス:"
for PID in $DEMO_PIDS; do
    PROCESS_NAME=$(ps -p "$PID" -o comm= 2>/dev/null || echo "unknown")
    echo "  - PID $PID ($PROCESS_NAME)"
done

# Graceful shutdown
for PID in $DEMO_PIDS; do
    echo "プロセス $PID に SIGTERM を送信中"
    kill -TERM "$PID" 2>/dev/null || echo "警告: プロセス $PID は既に終了しています"
done

# Wait for graceful shutdown
sleep 2

# Force kill if still running
REMAINING_PIDS=$(pgrep -f "_server\.py" || echo "")
if [ -n "$REMAINING_PIDS" ]; then
    echo "残りのプロセスを強制終了中: $REMAINING_PIDS"
    for PID in $REMAINING_PIDS; do
        kill -KILL "$PID" 2>/dev/null || echo "警告: プロセス $PID は既に終了しています"
    done
fi

echo "デモバックエンドが正常に停止しました"