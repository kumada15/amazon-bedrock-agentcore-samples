#!/usr/bin/env python3
"""
スタンドアロン Session リプレイビューア

このスクリプトは、新しい Browser セッションを作成せずに、S3 に保存された
Bedrock Agentcore Browser 録画を表示できます。

使用方法:
    python3 view_recordings.py --bucket BUCKET_NAME --prefix PREFIX [--session SESSION_ID] [--port PORT]

例:
    python3 view_recordings.py --bucket session-record-test-123456789012 --prefix replay-data

環境変数:
    AWS_REGION          - AWS リージョン（デフォルト: us-west-2）
    AWS_PROFILE         - 認証情報に使用する AWS プロファイル（オプション）
"""

import os
import sys
import time
import json
import uuid
import tempfile
import threading
import webbrowser
import socket
import signal
import shutil
import gzip
import io
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

import boto3
from rich.console import Console
from rich.panel import Panel

# Create console
console = Console()

# Direct import from session_replay_viewer in the same folder
from session_replay_viewer import SessionReplayViewer, SessionReplayHandler

# インポートの問題を避けるため、このスクリプト内で CustomS3DataSource を直接定義
class CustomS3DataSource:
    """既知の構造を持つ S3 録画用のカスタムデータソース"""

    def __init__(self, bucket, prefix, session_id):
        self.s3_client = boto3.client('s3')
        self.bucket = bucket
        self.prefix = prefix
        self.session_id = session_id
        self.session_prefix = f"{prefix}/{session_id}"
        self.temp_dir = Path(tempfile.mkdtemp(prefix='bedrock_agentcore_replay_'))
        
    def cleanup(self):
        """一時ファイルをクリーンアップする"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def list_recordings(self):
        """録画を直接リストする"""
        recordings = []
        
        # Fetch metadata to get details about the recording
        metadata = {}
        try:
            metadata_key = f"{self.session_prefix}/metadata.json"
            print(f"メタデータを取得中: {metadata_key}")
            response = self.s3_client.get_object(Bucket=self.bucket, Key=metadata_key)
            metadata = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✅ Found metadata: {metadata}")
        except Exception as e:
            print(f"⚠️ Could not get metadata: {e}")
        
        # List batch files to count events
        batch_files = []
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=f"{self.session_prefix}/batch-"
        )
        
        if 'Contents' in response:
            batch_files = [obj['Key'] for obj in response['Contents']]
            print(f"✅ Found {len(batch_files)} batch files")
        
        # Create a recording entry
        timestamp = int(time.time() * 1000)  # Default to now
        duration = 0
        event_count = 0
        
        # Parse the timestamp correctly
        if 'startTime' in metadata:
            try:
                # Handle ISO format
                if isinstance(metadata['startTime'], str):
                    dt = datetime.fromisoformat(metadata['startTime'].replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp() * 1000)
                else:
                    timestamp = metadata['startTime']
            except Exception as e:
                print(f"⚠️ Error parsing startTime: {e}")
                
        # Try different duration fields
        if 'duration' in metadata:
            duration = metadata['duration']
        elif 'durationMs' in metadata:
            duration = metadata['durationMs']
            
        # Try different event count fields
        if 'eventCount' in metadata:
            event_count = metadata['eventCount']
        elif 'totalEvents' in metadata:
            event_count = metadata['totalEvents']
        
        # Use correct datetime formatting
        date_string = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        
        recordings.append({
            'id': self.session_id,
            'sessionId': self.session_id,
            'timestamp': timestamp,
            'date': date_string,
            'events': event_count,
            'duration': duration
        })
        
        return recordings
    
    def download_recording(self, recording_id):
        """S3 から録画をダウンロードする"""
        print(f"録画をダウンロード中: {recording_id}")
        
        recording_dir = self.temp_dir / recording_id
        recording_dir.mkdir(exist_ok=True)
        
        try:
            # Get metadata
            metadata = {}
            try:
                metadata_key = f"{self.session_prefix}/metadata.json"
                response = self.s3_client.get_object(Bucket=self.bucket, Key=metadata_key)
                metadata = json.loads(response['Body'].read().decode('utf-8'))
                print(f"✅ Downloaded metadata: {metadata}")
            except Exception as e:
                print(f"⚠️ No metadata found: {e}")
            
            # Get batch files from metadata if possible
            batch_files = []
            if 'batches' in metadata and isinstance(metadata['batches'], list):
                for batch in metadata['batches']:
                    if 'file' in batch:
                        batch_files.append(f"{self.session_prefix}/{batch['file']}")
            
            # If no batch files found in metadata, look for them directly
            if not batch_files:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=f"{self.session_prefix}/batch-"
                )
                
                if 'Contents' in response:
                    batch_files = [obj['Key'] for obj in response['Contents']]
            
            all_events = []
            print(f"{len(batch_files)} 個のバッチファイルを処理中: {batch_files}")
            
            for key in batch_files:
                try:
                    print(f"バッチファイルをダウンロード中: {key}")
                    response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
                    
                    # Try to read as gzipped JSON lines
                    with gzip.GzipFile(fileobj=io.BytesIO(response['Body'].read())) as gz:
                        content = gz.read().decode('utf-8')
                        print(f"{len(content)} バイトのコンテンツを読み込みました")
                        
                        # Process each line as a JSON event
                        for line in content.splitlines():
                            if line.strip():
                                try:
                                    event = json.loads(line)
                                    # Validate event
                                    if 'type' in event and 'timestamp' in event:
                                        all_events.append(event)
                                    else:
                                        print(f"⚠️ Skipping invalid event (missing required fields)")
                                except json.JSONDecodeError as je:
                                    print(f"⚠️ Invalid JSON in line: {line[:50]}...")
                                    
                        print(f"  Added {len(all_events)} events")
                                    
                except Exception as e:
                    print(f"⚠️ Error processing file {key}: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"✅ Loaded {len(all_events)} events")
            
            # If no events were loaded, create sample events
            if len(all_events) < 2:
                print("⚠️ Insufficient events, creating sample events for testing")
                all_events = [
                    {"type": 2, "timestamp": timestamp, "data": {"href": "https://example.com", "width": 1280, "height": 720}} 
                    for timestamp in range(int(time.time() * 1000), int(time.time() * 1000) + 10000, 1000)
                ]
                # Add a minimal DOM snapshot event
                all_events.append({
                    "type": 4, 
                    "timestamp": int(time.time() * 1000) + 1000,
                    "data": {
                        "node": {
                            "type": 1,
                            "childNodes": [
                                {"type": 2, "tagName": "html", "attributes": {}, "childNodes": [
                                    {"type": 2, "tagName": "body", "attributes": {}, "childNodes": [
                                        {"type": 3, "textContent": "Sample content"}
                                    ]}
                                ]}
                            ]
                        }
                    }
                })
            
            # Return the parsed recording
            return {
                'metadata': metadata,
                'events': all_events
            }
            
        except Exception as e:
            print(f"❌ Error downloading recording: {e}")
            import traceback
            traceback.print_exc()
            return None

# このスクリプト内で CustomSessionReplayHandler を直接定義
class CustomSessionReplayHandler(SessionReplayHandler):
    """Session リプレイビューア用のカスタム HTTP リクエストハンドラ"""

    def serve_recordings_list(self):
        """録画のリストを返す - HTML レスポンスの問題を修正"""
        try:
            recordings = self.data_source.list_recordings()
            response = json.dumps(recordings)
            
            # Debug output to see what we're returning
            print(f"録画リストを提供中: {response[:100]}...")
            
            # Ensure proper content type and headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            # Add CORS headers to prevent issues
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.end_headers()
            
            # Write the response as bytes
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            print(f"❌ Error in serve_recordings_list: {e}")
            import traceback
            traceback.print_exc()
            
            # Return a proper error response as JSON with empty recordings array
            error_response = json.dumps({
                "error": str(e),
                "recordings": []
            })
            self.send_response(200)  # Use 200 so client can process the error
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(error_response)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(error_response.encode('utf-8'))
    
    def download_and_serve_recording(self, recording_id):
        """録画をダウンロードして提供する - HTML レスポンスの問題を修正"""
        try:
            recording_data = self.data_source.download_recording(recording_id)
            
            if recording_data:
                response = json.dumps({
                    'success': True,
                    'data': recording_data
                })
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(response.encode('utf-8'))
            else:
                error_response = json.dumps({
                    'success': False,
                    'error': 'Recording not found'
                })
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(error_response)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(error_response.encode('utf-8'))
                
        except Exception as e:
            print(f"❌ Error in download_and_serve_recording: {e}")
            import traceback
            traceback.print_exc()
            
            error_response = json.dumps({
                'success': False,
                'error': str(e)
            })
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(error_response)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(error_response.encode('utf-8'))
    
    def do_OPTIONS(self):
        """CORS プリフライト用の OPTIONS リクエストを処理する"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

# このスクリプト内で CustomSessionReplayViewer を直接定義
class CustomSessionReplayViewer(SessionReplayViewer):
    def start(self):
        """カスタムハンドラを使用してリプレイビューアサーバーを起動する"""
        # Ensure viewer directory exists
        self.viewer_path.mkdir(parents=True, exist_ok=True)
        
        # Find available port
        port = self.find_available_port()
        
        # Create request handler
        def handler_factory(*args, **kwargs):
            return CustomSessionReplayHandler(self.data_source, self.viewer_path, *args, **kwargs)
        
        # Start server
        self.server = HTTPServer(('', port), handler_factory)
        
        # Start in thread
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        url = f"http://localhost:{port}"
        
        console.print(Panel(
            f"[bold cyan]Session Replay Viewer Running[/bold cyan]\n\n"
            f"URL: [link]{url}[/link]\n\n"
            f"[yellow]Press Ctrl+C to stop[/yellow]",
            title="Ready",
            border_style="green"
        ))
        
        # Open browser
        webbrowser.open(url)
        
        # Handle shutdown
        def signal_handler(sig, frame):
            console.print("\n[yellow]Shutting down...[/yellow]")
            self.server.shutdown()
            if hasattr(self.data_source, 'cleanup'):
                self.data_source.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

def main():
    parser = argparse.ArgumentParser(description="Standalone Session Replay Viewer")
    parser.add_argument("--bucket", required=True, help="S3 bucket name containing recordings")
    parser.add_argument("--prefix", required=True, help="S3 prefix where recordings are stored")
    parser.add_argument("--session", help="Specific session ID to view (optional)")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the viewer on (default: 8080)")
    parser.add_argument("--profile", help="AWS profile to use (optional)")
    args = parser.parse_args()
    
    # Use specified AWS profile if provided
    if args.profile:
        print(f"AWS プロファイルを使用: {args.profile}")
        boto3.setup_default_session(profile_name=args.profile)
        
    # Create S3 client to check bucket
    s3 = boto3.client('s3')
    
    try:
        # Check if bucket exists and we have access
        s3.head_bucket(Bucket=args.bucket)
        print(f"✅ Connected to bucket: {args.bucket}")
    except Exception as e:
        print(f"❌ Error accessing bucket {args.bucket}: {e}")
        sys.exit(1)
    
    # If no specific session provided, find the latest one
    if not args.session:
        print(f"s3://{args.bucket}/{args.prefix}/ 内のセッションを検索中")
        try:
            response = s3.list_objects_v2(
                Bucket=args.bucket,
                Prefix=args.prefix
            )
            
            if 'Contents' not in response:
                print("S3 ロケーションにオブジェクトが見つかりません")
                sys.exit(1)
                
            # Get all unique directory names that contain metadata.json
            session_dirs = set()
            
            for obj in response['Contents']:
                key = obj['Key']
                if 'metadata.json' in key:
                    # Extract the session directory from the path
                    session_dir = key.split('/')[-2]
                    session_dirs.add(session_dir)
                    print(f"メタデータを持つセッションを発見: {session_dir}")
            
            if not session_dirs:
                print("metadata.json を含むセッションディレクトリが見つかりません")
                sys.exit(1)
                
            # Sort the session directories to find the latest one
            session_dirs = sorted(list(session_dirs))
            args.session = session_dirs[-1]
            print(f"最新のセッションを使用: {args.session}")
            
        except Exception as e:
            print(f"❌ Error listing sessions: {e}")
            sys.exit(1)
    
    # Create data source for the specific session
    data_source = CustomS3DataSource(
        bucket=args.bucket,
        prefix=args.prefix,
        session_id=args.session
    )
    
    # Start the viewer
    print(f"🎬 Starting session replay viewer for: {args.session}")
    print(f"  Bucket: {args.bucket}")
    print(f"  Prefix: {args.prefix}")
    viewer = CustomSessionReplayViewer(data_source=data_source, port=args.port)
    viewer.start()  # This will block until Ctrl+C

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user")
        sys.exit(0)
