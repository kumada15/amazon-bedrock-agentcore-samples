#!/usr/bin/env python3
import argparse
import os
import sys
import webbrowser
import json
import secrets
import string
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Import from root-level websocket_helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from websocket_helpers import create_presigned_url


class SonicClientHandler(BaseHTTPRequestHandler):
    """Nova Sonic クライアントを提供する HTTP リクエストハンドラー"""

    # 接続詳細を保存するクラス変数
    websocket_url = None
    session_id = None
    is_presigned = False
    
    # URL 再生成用の設定を保存
    runtime_arn = None
    region = None
    service = None
    expires = None
    qualifier = None
    
    def log_message(self, format, *args):
        """よりクリーンなロギングを提供するためにオーバーライド"""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")
    
    def do_GET(self):
        """GET リクエストを処理"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/' or parsed_path.path == '/index.html':
            self.serve_client_page()
        elif parsed_path.path == '/api/connection':
            self.serve_connection_info()
        else:
            self.send_error(404, "File not found")
    
    def do_POST(self):
        """POST リクエストを処理"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/regenerate':
            self.regenerate_url()
        else:
            self.send_error(404, "Endpoint not found")
    
    def serve_client_page(self):
        """事前設定された接続で HTML クライアントを提供"""
        try:
            # HTML テンプレートを読み込み
            html_path = os.path.join(os.path.dirname(__file__), 'sonic-client.html')
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 提供されている場合は WebSocket URL を挿入
            if self.websocket_url:
                html_content = html_content.replace(
                    'id="websocketUrl" placeholder="ws://localhost:8081/ws" value="ws://localhost:8081/ws"',
                    f'id="websocketUrl" placeholder="ws://localhost:8081/ws" value="{self.websocket_url}"'
                )
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Content-Length', len(html_content.encode()))
            self.end_headers()
            self.wfile.write(html_content.encode())
            
        except FileNotFoundError:
            self.send_error(404, "sonic-client.html not found")
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def serve_connection_info(self):
        """接続情報を JSON として提供"""
        response = {
            "websocket_url": self.websocket_url or "ws://localhost:8081/ws",
            "session_id": self.session_id,
            "is_presigned": self.is_presigned,
            "can_regenerate": self.runtime_arn is not None,
            "status": "ok" if self.websocket_url else "no_connection"
        }
        
        response_json = json.dumps(response, indent=2)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', len(response_json.encode()))
        self.end_headers()
        self.wfile.write(response_json.encode())
    
    def regenerate_url(self):
        """署名付き URL を再生成"""
        try:
            if not self.runtime_arn:
                error_response = {
                    "status": "error",
                    "message": "Cannot regenerate URL - not using presigned URL mode"
                }
                response_json = json.dumps(error_response)
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Content-Length', len(response_json.encode()))
                self.end_headers()
                self.wfile.write(response_json.encode())
                return
            
            # 新しい署名付き URL を生成
            base_url = f"wss://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{self.runtime_arn}/ws?qualifier={self.qualifier}"
            
            new_url = create_presigned_url(
                base_url,
                region=self.region,
                service=self.service,
                expires=self.expires
            )
            
            # クラス変数を更新
            SonicClientHandler.websocket_url = new_url
            
            response = {
                "status": "ok",
                "websocket_url": new_url,
                "expires_in": self.expires,
                "message": "URL regenerated successfully"
            }
            
            response_json = json.dumps(response, indent=2)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())
            
            print(f"✅ 署名付きURLを再生成しました（{self.expires}秒後に期限切れ）")
            
        except Exception as e:
            error_response = {
                "status": "error",
                "message": str(e)
            }
            response_json = json.dumps(error_response)
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())


def main():
    parser = argparse.ArgumentParser(
        description='Start web service for Nova Sonic WebSocket client',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local WebSocket server (no authentication)
  python web_service.py --ws-url ws://localhost:8081/ws
  
  # AWS Bedrock with presigned URL
  python web_service.py --runtime-arn arn:aws:bedrock:us-west-2:123456789012:agent/AGENTID
  
  # Specify custom port
  python web_service.py --runtime-arn arn:aws:bedrock:us-west-2:123456789012:agent/AGENTID --port 8080
  
  # Custom region
  python web_service.py --runtime-arn arn:aws:bedrock:us-west-2:123456789012:agent/AGENTID \\
    --region us-east-1
"""
    )
    
    parser.add_argument(
        '--runtime-arn',
        help='Runtime ARN for AWS Bedrock connection (e.g., arn:aws:bedrock:region:account:agent/id)'
    )
    
    parser.add_argument(
        '--ws-url',
        help='WebSocket server URL for local connections (e.g., ws://localhost:8081/ws)'
    )
    

    
    parser.add_argument(
        '--region',
        default=os.getenv('AWS_REGION'),
        help='AWS region (required if using --runtime-arn, from AWS_REGION env var)'
    )
    
    parser.add_argument(
        '--service',
        default='bedrock-agentcore',
        help='AWS service name (default: bedrock-agentcore)'
    )
    
    parser.add_argument(
        '--expires',
        type=int,
        default=3600,
        help='URL expiration time in seconds for presigned URLs (default: 3600 = 1 hour)'
    )
    
    parser.add_argument(
        '--qualifier',
        default='DEFAULT',
        help='Runtime qualifier (default: DEFAULT)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Web server port (default: 8000)'
    )
    
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not automatically open browser'
    )
    
    args = parser.parse_args()
    
    # 引数を検証
    if not args.runtime_arn and not args.ws_url:
        parser.error("Either --runtime-arn or --ws-url must be specified")
    
    if args.runtime_arn and args.ws_url:
        parser.error("Cannot specify both --runtime-arn and --ws-url")
    
    # AWS Bedrock 接続に必要なパラメータを検証
    if args.runtime_arn:
        if not args.region:
            parser.error("--region or AWS_REGION env var is required when using --runtime-arn")
    
    print("=" * 70)
    print("🎙️ Nova Sonicクライアント Webサービス")
    print("=" * 70)
    
    websocket_url = None
    session_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
    is_presigned = False
    
    try:
        # AWS Bedrock 用の署名付き URL を生成
        if args.runtime_arn:
            base_url = f"wss://bedrock-agentcore.{args.region}.amazonaws.com/runtimes/{args.runtime_arn}/ws?qualifier={args.qualifier}"
            
            print(f"📡 ベースURL: {base_url}")
            print(f"🔑 ランタイムARN: {args.runtime_arn}")
            print(f"🌍 リージョン: {args.region}")
            print(f"🆔 セッションID: {session_id}")
            print(f"⏰ URLの有効期限: {args.expires}秒（{args.expires/60:.1f}分）")
            print()
            print("🔐 署名付きURLを生成中...")
            
            websocket_url = create_presigned_url(
                base_url,
                region=args.region,
                service=args.service,
                expires=args.expires
            )
            is_presigned = True
            print("✅ 署名付きURLの生成に成功しました!")

        # ローカル接続用に提供された WebSocket URL を使用
        else:
            websocket_url = args.ws_url
            print(f"🔗 WebSocket URL: {websocket_url}")
            print("💡 ローカルWebSocket接続を使用中（認証なし）")

        print(f"🌐 Webサーバーポート: {args.port}")
        print()
        
        # ハンドラークラスに接続詳細を設定
        SonicClientHandler.websocket_url = websocket_url
        SonicClientHandler.session_id = session_id
        SonicClientHandler.is_presigned = is_presigned
        
        # URL 再生成用の設定を保存
        if args.runtime_arn:
            SonicClientHandler.runtime_arn = args.runtime_arn
            SonicClientHandler.region = args.region
            SonicClientHandler.service = args.service
            SonicClientHandler.expires = args.expires
            SonicClientHandler.qualifier = args.qualifier
        
        # Web サーバーを起動
        server_address = ('', args.port)
        httpd = HTTPServer(server_address, SonicClientHandler)
        
        server_url = f"http://localhost:{args.port}"
        
        print("=" * 70)
        print("🌐 Webサーバー起動")
        print("=" * 70)
        print(f"📍 サーバーURL: {server_url}")
        print(f"🔗 クライアントページ: {server_url}/")
        print(f"📊 APIエンドポイント: {server_url}/api/connection")
        print()
        if is_presigned:
            print("💡 署名付きWebSocket URLがクライアントに設定されています")
        else:
            print("💡 WebSocket URLがクライアントに設定されています")
        print("💡 Ctrl+Cでサーバーを停止")
        print("=" * 70)
        print()

        # ブラウザを自動的に開く
        if not args.no_browser:
            print("🌐 ブラウザを開いています...")
            webbrowser.open(server_url)
            print()
        
        # サービスを開始
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        print("\n\n👋 サーバーをシャットダウン中...")
        return 0
    except Exception as e:
        print(f"\n❌ エラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
