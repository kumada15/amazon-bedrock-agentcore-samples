#!/usr/bin/env python3
"""
Logs Manager - AgentCore Runtime の CloudWatch ログを取得する
"""

import boto3
import json
import sys
import os
from datetime import datetime, timedelta

class LogsManager:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.logs_client = boto3.client('logs', region_name=region)
        
    def get_runtime_logs(self, runtime_id, tail_lines=50):
        """Runtime の CloudWatch ログを取得する"""
        try:
            # The log group name pattern for AgentCore runtimes
            log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"
            
            print(f"🔍 ランタイムのログを取得中: {runtime_id}")
            print(f"📋 CloudWatch から最新のログを取得中...")
            
            # Get log streams
            streams_response = self.logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=5
            )
            
            log_streams = streams_response.get('logStreams', [])
            if not log_streams:
                print(f"❌ ランタイム {runtime_id} のログストリームが見つかりません")
                return
            
            # Get logs from the most recent stream
            latest_stream = log_streams[0]
            stream_name = latest_stream['logStreamName']
            
            # Calculate time range (last hour)
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            # Get log events
            events_response = self.logs_client.get_log_events(
                logGroupName=log_group_name,
                logStreamName=stream_name,
                startTime=int(start_time.timestamp() * 1000),
                endTime=int(end_time.timestamp() * 1000),
                limit=tail_lines
            )
            
            events = events_response.get('events', [])
            
            if not events:
                print(f"❌ ランタイム {runtime_id} の最新のログイベントが見つかりません")
                return
            
            # Display logs
            for event in events[-tail_lines:]:  # Show last N lines
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                message = event['message'].strip()
                print(f"{timestamp}: {message}")
                
        except Exception as e:
            print(f"❌ ログ取得中にエラー: {e}")
            
            # Try alternative log group patterns
            alternative_patterns = [
                f"/aws/bedrock/agentcore/{runtime_id}",
                f"/aws/agentcore/runtime/{runtime_id}",
                f"/aws/bedrock/{runtime_id}"
            ]
            
            for pattern in alternative_patterns:
                try:
                    print(f"🔍 代替ロググループを試行中: {pattern}")
                    streams_response = self.logs_client.describe_log_streams(
                        logGroupName=pattern,
                        orderBy='LastEventTime',
                        descending=True,
                        limit=1
                    )
                    print(f"✅ ロググループが見つかりました: {pattern}")
                    break
                except:
                    continue
            else:
                print("❌ 一致するロググループが見つかりませんでした")

def main():
    if len(sys.argv) < 3:
        print("使用方法:")
        print("  python3 logs_manager.py logs <runtime_id> [tail_lines]")
        sys.exit(1)

    manager = LogsManager()
    command = sys.argv[1]

    if command == "logs" and len(sys.argv) > 2:
        runtime_id = sys.argv[2]
        tail_lines = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        manager.get_runtime_logs(runtime_id, tail_lines)
    else:
        print("無効なコマンドまたは引数が不足しています")
        sys.exit(1)

if __name__ == "__main__":
    main()