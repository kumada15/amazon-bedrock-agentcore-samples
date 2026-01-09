"""
動作するコードからのすべての修正を統合した統一 S3 DataSource。
保存先: competitive-intelligence-agent/utils/s3_datasource.py
"""

import os
import sys
import json
import time
import tempfile
import shutil
import gzip
import io
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import boto3
from rich.console import Console

console = Console()


class UnifiedS3DataSource:
    """
    すべての修正を統合した統一 S3 データソース:
    - セッション ID の重複を避けた正しい S3 パス構築
    - メタデータからの適切なタイムスタンプ解析
    - 録画が不完全な場合のフォールバックイベント作成
    - 直接セッションアクセスと検出の両方をサポート
    """
    
    def __init__(self, bucket: str, prefix: str, session_id: Optional[str] = None):
        """
        S3 データソースを初期化する。

        Args:
            bucket: S3 バケット名
            prefix: S3 プレフィックス（セッション ID なし）
            session_id: オプションのセッション ID。指定しない場合は検出を試みる
        """
        self.s3_client = boto3.client('s3')
        self.bucket = bucket
        self.prefix = prefix.rstrip('/')
        self.session_id = session_id
        self.temp_dir = Path(tempfile.mkdtemp(prefix='bedrock_agentcore_replay_'))
        
        # Fix: Build the full prefix correctly
        if session_id:
            # Only append session_id if prefix doesn't already contain it
            if prefix and not prefix.endswith(session_id):
                self.full_prefix = f"{prefix}/{session_id}"
            elif prefix:
                # Prefix already contains session_id, don't duplicate
                self.full_prefix = prefix
            else:
                # No prefix, just use session_id
                self.full_prefix = session_id
        else:
            # Try to discover session from prefix
            self.session_id = self._discover_session()
            if self.session_id:
                self.full_prefix = f"{prefix}/{self.session_id}" if prefix else self.session_id
            else:
                self.full_prefix = prefix
        
        console.print(f"[cyan]S3 DataSource を初期化しました[/cyan]")
        console.print(f"  バケット: {bucket}")
        console.print(f"  プレフィックス: {prefix}")
        console.print(f"  セッション: {self.session_id}")
        console.print(f"  フルパス: s3://{bucket}/{self.full_prefix}/")
    
    def cleanup(self):
        """一時ファイルをクリーンアップする"""
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
    
    def _discover_session(self) -> Optional[str]:
        """S3 プレフィックスから最新のセッション ID を検出する"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=self.prefix,
                Delimiter='/'
            )
            
            if 'CommonPrefixes' in response:
                # Get all session directories
                sessions = []
                for prefix_info in response['CommonPrefixes']:
                    session_path = prefix_info['Prefix'].rstrip('/')
                    session_id = session_path.split('/')[-1]
                    sessions.append(session_id)
                
                if sessions:
                    # Return the latest (last) session
                    latest = sorted(sessions)[-1]
                    console.print(f"[green]セッションを検出しました: {latest}[/green]")
                    return latest
            
            # Alternative: Look for metadata.json files
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=self.prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if 'metadata.json' in obj['Key']:
                        # Extract session ID from path
                        parts = obj['Key'].split('/')
                        for i, part in enumerate(parts):
                            if i > 0 and parts[i-1] == self.prefix.split('/')[-1]:
                                console.print(f"[green]メタデータからセッションを発見しました: {part}[/green]")
                                return part
            
        except Exception as e:
            console.print(f"[yellow]セッションを検出できませんでした: {e}[/yellow]")

        return None
    
    def list_recordings(self) -> List[Dict]:
        """すべてのタイムスタンプ解析修正を含む録画一覧を取得する"""
        recordings = []
        
        if not self.session_id:
            console.print("[yellow]セッション ID がありません[/yellow]")
            return recordings
        
        try:
            # Fetch metadata
            metadata = self._get_metadata()
            
            # Parse timestamp with all the fixes from your working code
            timestamp = self._parse_timestamp(metadata)
            
            # Get duration
            duration = metadata.get('duration', 0) or metadata.get('durationMs', 0) or 0
            
            # Get event count
            event_count = metadata.get('eventCount', 0) or metadata.get('totalEvents', 0) or 0
            
            # Create recording entry
            recordings.append({
                'id': self.session_id,
                'sessionId': self.session_id,
                'timestamp': timestamp,
                'date': datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'events': event_count,
                'duration': duration
            })
            
        except Exception as e:
            console.print(f"[yellow]録画一覧の取得エラー: {e}[/yellow]")
            # Return fallback recording
            recordings.append(self._create_fallback_recording())
        
        return recordings
    
    def download_recording(self, recording_id: str) -> Optional[Dict]:
        """S3 から録画をダウンロードして処理する"""
        console.print(f"[cyan]録画をダウンロード中: {recording_id}[/cyan]")
        
        recording_dir = self.temp_dir / recording_id
        recording_dir.mkdir(exist_ok=True)
        
        try:
            # Get metadata
            metadata = self._get_metadata()
            
            # List all objects in session directory
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=self.full_prefix
            )
            
            if 'Contents' not in response:
                console.print(f"[yellow]セッション内にファイルが見つかりません[/yellow]")
                return self._create_fallback_recording_data()
            
            # Find batch files
            batch_files = [
                obj['Key'] for obj in response['Contents']
                if obj['Key'].endswith('.gz') or 'batch-' in obj['Key']
            ]
            
            console.print(f"{len(batch_files)} 件のバッチファイルが見つかりました")
            
            # Process batch files
            all_events = []
            for key in batch_files:
                try:
                    console.print(f"[dim]処理中: {key.split('/')[-1]}[/dim]")
                    response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
                    
                    # Read and decompress
                    with gzip.GzipFile(fileobj=io.BytesIO(response['Body'].read())) as gz:
                        content = gz.read().decode('utf-8')
                        
                        # Parse JSON lines
                        for line in content.splitlines():
                            if line.strip():
                                try:
                                    event = json.loads(line)
                                    # Validate event structure
                                    if 'type' in event and 'timestamp' in event:
                                        all_events.append(event)
                                except json.JSONDecodeError:
                                    continue
                    
                except Exception as e:
                    console.print(f"[yellow]{key} の処理エラー: {e}[/yellow]")
            
            console.print(f"[green]✅ {len(all_events)} 件のイベントを読み込みました[/green]")
            
            # If no events or too few, create fallback
            if len(all_events) < 2:
                console.print("[yellow]イベントが不足しています、フォールバックを使用します[/yellow]")
                return self._create_fallback_recording_data()
            
            return {
                'metadata': metadata,
                'events': all_events
            }
            
        except Exception as e:
            console.print(f"[red]録画のダウンロードエラー: {e}[/red]")
            return self._create_fallback_recording_data()
    
    def _get_metadata(self) -> Dict:
        """エラー処理付きで S3 からメタデータを取得する"""
        try:
            metadata_key = f"{self.full_prefix}/metadata.json"
            response = self.s3_client.get_object(Bucket=self.bucket, Key=metadata_key)
            metadata = json.loads(response['Body'].read().decode('utf-8'))
            console.print(f"[dim]✅ メタデータを取得しました[/dim]")
            return metadata
        except Exception as e:
            console.print(f"[yellow]メタデータが見つかりません: {e}[/yellow]")
            return {}
    
    def _parse_timestamp(self, metadata: Dict) -> int:
        """すべてのエッジケースを処理してメタデータからタイムスタンプを解析する"""
        # Default to current time
        timestamp = int(time.time() * 1000)
        
        if 'startTime' in metadata:
            start_time = metadata['startTime']
            
            try:
                if isinstance(start_time, str):
                    # Handle ISO format
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp() * 1000)
                elif isinstance(start_time, (int, float)):
                    timestamp = int(start_time)
                    # Check if it's in seconds instead of milliseconds
                    if timestamp < 1000000000000:  # Before year 2001 in ms
                        timestamp = timestamp * 1000
            except Exception as e:
                console.print(f"[yellow]タイムスタンプを解析できませんでした: {e}[/yellow]")
        
        return timestamp
    
    def _create_fallback_recording(self) -> Dict:
        """フォールバック録画エントリを作成する"""
        return {
            'id': self.session_id or 'unknown',
            'sessionId': self.session_id or 'unknown',
            'timestamp': int(time.time() * 1000),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'events': 0,
            'duration': 0
        }
    
    def _create_fallback_recording_data(self) -> Dict:
        """
        実際の録画が利用できない場合に最小限のイベントでフォールバック録画データを作成する。

        目的:
        1. **グレースフルデグラデーション**: S3 録画が不完全または破損している場合、
        リプレイビューアが完全にクラッシュしないようにする。

        2. **開発/テスト**: 開発中は録画がまだ利用できない場合がある。
        これによりリプレイビューアインターフェースのテストが可能になる。

        3. **部分的な失敗**: 録画のアップロードが部分的に失敗した場合（ネットワークの問題、
        S3 の権限）、ユーザーは引き続きリプレイビューアにアクセスできる。

        4. **ユーザーエクスペリエンス**: エラーを表示する代わりに、録画が利用できない
        ことを説明するメッセージを含む最小限のインターフェースを表示する。

        5. **デバッグ**: 録画が失敗したときを特定するのに役立つ - ユーザーがフォールバック
        メッセージを見た場合、S3 のアップロードと権限を確認する必要があることがわかる。

        Returns:
            録画が利用できないことについての情報メッセージを表示するページを作成する
            最小限の有効な rrweb イベントを含む Dict。
        """
        timestamp = int(time.time() * 1000)
        
        # Create minimal valid events for rrweb player
        events = [
            {
                "type": 2,  # Meta event
                "timestamp": timestamp,
                "data": {
                    "href": "https://example.com",
                    "width": 1280,
                    "height": 720
                }
            },
            {
                "type": 4,  # Full snapshot
                "timestamp": timestamp + 100,
                "data": {
                    "node": {
                        "type": 1,
                        "childNodes": [{
                            "type": 2,
                            "tagName": "html",
                            "attributes": {},
                            "childNodes": [{
                                "type": 2,
                                "tagName": "body",
                                "attributes": {
                                    "style": "font-family: sans-serif; padding: 40px; text-align: center;"
                                },
                                "childNodes": [{
                                    "type": 3,
                                    "textContent": "録画データが利用できません - アップロードの遅延または権限の問題が原因の可能性があります"
                                }]
                            }]
                        }]
                    }
                }
            }
        ]
        
        return {
            'metadata': {'fallback': True},
            'events': events
        }