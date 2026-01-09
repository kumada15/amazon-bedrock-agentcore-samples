#!/usr/bin/env python3
"""
AgentCore チャットボットクライアント

AgentCore Runtime に接続して会話するシンプルなチャットボットクライアント。
機能:
- 設定ファイルからのランタイム選択
- Okta トークン認証
- ローカル会話履歴管理
- 現在のメッセージのみをランタイムに送信（全履歴ではない）
- 詳細なリクエスト/レスポンスログ用のデバッグモード
"""

# ============================================================================
# IMPORTS
# ============================================================================

import requests
import json
import uuid
import sys
import os
import yaml
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import urllib.parse

# ============================================================================
# CLASSES
# ============================================================================

class AgentCoreClient:
    """AgentCore Runtime と通信するクライアント"""
    
    # ========================================================================
    # INITIALIZATION & CONFIGURATION
    # ========================================================================
    
    def __init__(self, config_path: str = None, debug: bool = False, local_mode: bool = False):
        """設定を使用してクライアントを初期化する"""
        self.local_mode = local_mode
        self.session_token = None
        self.selected_runtime = None
        self.conversation_history = []
        # Generate session ID once at client startup for conversation continuity across runtime switches
        self.session_id = f"session_{uuid.uuid4().hex}_{os.getpid()}"
        self.debug = debug
        
        if not local_mode:
            # Standard AgentCore mode - load full configuration
            # Add project root to path for shared config manager
            project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
            sys.path.insert(0, project_root)
            
            from shared.config_manager import AgentCoreConfigManager
            
            self.config_manager = AgentCoreConfigManager()
            self.agentcore_config = self.config_manager.get_merged_config()
            self.token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.okta_token')
        else:
            # Local testing mode - minimal configuration
            self.config_manager = None
            self.agentcore_config = {
                'runtime': {
                    'diy_agent': {'arn': 'local-diy-agent', 'name': 'Local DIY Agent'},
                    'sdk_agent': {'arn': 'local-sdk-agent', 'name': 'Local SDK Agent'}
                },
                'agents': {'payload_formats': {'diy': 'direct', 'sdk': 'direct'}},
                'client': {'default_agent': 'diy'}
            }
            self.token_file = None
        
    def _should_show_detailed_errors(self, error_message: str = "") -> bool:
        """詳細なエラー情報を表示すべきかどうかを判断する"""
        # Always show details in debug mode
        if self.debug:
            return True
        # Show details for authentication/authorization errors even in non-debug mode
        auth_errors = ["403", "401", "Unauthorized", "Forbidden", "AccessDenied", "Authorizer error"]
        return any(err in str(error_message) for err in auth_errors)
        
    def _reload_config(self):
        """設定マネージャーから設定を再読み込みする"""
        try:
            self.agentcore_config = self.config_manager.get_merged_config()
        except Exception as e:
            print(f"❌ 設定の再読み込み中にエラー: {e}")
            sys.exit(1)
    
    def _get_runtime_url(self, agent_type: str) -> str:
        """エージェントタイプの Runtime URL を取得する"""
        if self.local_mode:
            # Local testing mode - connect to localhost Docker container
            return "http://localhost:8080/invocations"
        
        # Standard AgentCore mode
        if agent_type == "sdk":
            runtime_arn = self.agentcore_config['runtime']['sdk_agent']['arn']
        elif agent_type == "diy":
            runtime_arn = self.agentcore_config['runtime']['diy_agent']['arn']
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        if not runtime_arn:
            raise ValueError(f"Runtime ARN not configured for {agent_type} agent")
        
        # URL encode the runtime ARN
        escaped_runtime_arn = urllib.parse.quote(runtime_arn, safe='')
        region = self.agentcore_config['aws']['region']
        
        return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_runtime_arn}/invocations?qualifier=DEFAULT"
    
    def _get_payload(self, message: str, agent_type: str, session_id: str = None, actor_id: str = "user") -> Dict[str, Any]:
        """セッションサポート付きでエージェントタイプのペイロードフォーマットを取得する"""
        payload_format = self.agentcore_config['agents']['payload_formats'][agent_type]
        
        base_payload = {
            "prompt": message,
            "session_id": session_id,
            "actor_id": actor_id
        }
        
        if payload_format == "direct":
            return base_payload
        elif payload_format == "wrapped":
            return {"payload": json.dumps(base_payload)}
        else:
            raise ValueError(f"Unknown payload format: {payload_format}")
    
    # ========================================================================
    # RUNTIME MANAGEMENT
    # ========================================================================
    
    def display_available_runtimes(self) -> List[str]:
        """利用可能なランタイムを表示し、その名前を返す"""
        if self.local_mode:
            print("\n📦 ローカルテストモード:")
            print("=" * 40)
            print("1. DIY エージェント")
            print(f"   名前: Local DIY Agent")
            print(f"   URL: http://localhost:8080")
            print(f"   ステータス: ✅ 利用可能 (Docker コンテナ稼働中の場合)")
            print("2. SDK エージェント")
            print(f"   名前: Local SDK Agent")
            print(f"   URL: http://localhost:8080")
            print(f"   ステータス: ✅ 利用可能 (Docker コンテナ稼働中の場合)")
            return ['diy', 'sdk']
        
        # Standard AgentCore mode
        print("\n📦 利用可能な AgentCore ランタイム:")
        print("=" * 40)
        
        runtime_names = []
        runtime_config = self.agentcore_config.get('runtime', {})
        
        # Check for DIY agent
        if 'diy_agent' in runtime_config:
            diy = runtime_config['diy_agent']
            if diy.get('arn'):
                runtime_names.append('diy')
                print(f"1. DIY エージェント")
                print(f"   名前: {diy.get('name', 'N/A')}")
                if self.debug:
                    print(f"   ARN: {diy.get('arn', 'N/A')}")
                print(f"   ステータス: ✅ 利用可能")
            else:
                print(f"1. DIY エージェント")
                print(f"   ステータス: ❌ 未デプロイ")

        # Check for SDK agent
        if 'sdk_agent' in runtime_config:
            sdk = runtime_config['sdk_agent']
            if sdk.get('arn'):
                runtime_names.append('sdk')
                print(f"2. SDK エージェント")
                print(f"   名前: {sdk.get('name', 'N/A')}")
                if self.debug:
                    print(f"   ARN: {sdk.get('arn', 'N/A')}")
                print(f"   ステータス: ✅ 利用可能")
            else:
                print(f"2. SDK エージェント")
                print(f"   ステータス: ❌ 未デプロイ")

        if not runtime_names:
            print("❌ デプロイ済みのランタイムが見つかりません")
            return []
            
        return runtime_names
    
    def select_runtime(self) -> bool:
        """ユーザーが接続するランタイムを選択できるようにする"""
        available_runtimes = self.display_available_runtimes()
        
        if not available_runtimes:
            return False
        
        print(f"\n🎯 ランタイムを選択:")
        while True:
            try:
                if 'diy' in available_runtimes and 'sdk' in available_runtimes:
                    choice = input("選択してください (1: DIY, 2: SDK): ").strip()
                    if choice == '1':
                        self.selected_runtime = 'diy'
                        break
                    elif choice == '2':
                        self.selected_runtime = 'sdk'
                        break
                    else:
                        print("❌ 無効な選択です。1 または 2 を入力してください。")
                elif 'diy' in available_runtimes:
                    self.selected_runtime = 'diy'
                    print("🎯 選択済み: DIY エージェント (唯一の利用可能なランタイム)")
                    break
                elif 'sdk' in available_runtimes:
                    self.selected_runtime = 'sdk'
                    print("🎯 選択済み: SDK エージェント (唯一の利用可能なランタイム)")
                    break
            except KeyboardInterrupt:
                print("\n\n👋 さようなら！")
                return False

        runtime_info = self.agentcore_config['runtime'][f'{self.selected_runtime}_agent']
        print(f"✅ 接続先: {runtime_info.get('name', 'Unknown')}")
        print(f"🔗 セッション ID: {self.session_id}")
        
        return True
    
    # ========================================================================
    # AUTHENTICATION & TOKEN MANAGEMENT
    # ========================================================================
    
    def _decode_jwt_payload(self, token: str) -> Optional[Dict[str, Any]]:
        """検証なしで JWT ペイロードをデコードする（有効期限チェック用）"""
        try:
            # JWT format: header.payload.signature
            parts = token.split('.')
            if len(parts) != 3:
                return None
            
            # Decode the payload (second part)
            payload = parts[1]
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            decoded_bytes = base64.urlsafe_b64decode(payload)
            return json.loads(decoded_bytes)
        except Exception:
            return None
    
    def _is_token_valid(self, token: str) -> bool:
        """JWT トークンがまだ有効かどうかを確認する（期限切れでないか）"""
        payload = self._decode_jwt_payload(token)
        if not payload:
            return False
        
        # Check expiration
        exp = payload.get('exp')
        if not exp:
            return False
        
        # Add 60 second buffer before expiration
        current_time = datetime.now(timezone.utc).timestamp()
        return (exp - 60) > current_time
    
    def _save_token(self, token: str):
        """トークンをローカルファイルに保存する"""
        try:
            token_data = {
                'token': token,
                'saved_at': datetime.now(timezone.utc).isoformat()
            }
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            # Set file permissions to be readable only by owner
            os.chmod(self.token_file, 0o600)
        except Exception as e:
            print(f"⚠️  警告: トークンを保存できませんでした: {e}")
    
    def _load_saved_token(self) -> Optional[str]:
        """以前保存されたトークンが存在し有効であれば読み込む"""
        try:
            if not os.path.exists(self.token_file):
                return None
            
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            token = token_data.get('token')
            if not token:
                return None
            
            if self._is_token_valid(token):
                return token
            else:
                # Token expired, remove the file
                os.remove(self.token_file)
                return None
                
        except Exception:
            # If there's any issue reading the token, remove the file
            try:
                if os.path.exists(self.token_file):
                    os.remove(self.token_file)
            except:
                pass
            return None
    
    def get_okta_token(self) -> bool:
        """Okta トークンを取得する - まず保存済みトークンを試し、必要に応じてプロンプトを表示する"""
        print(f"\n🔐 認証")

        # Try to load saved token first
        saved_token = self._load_saved_token()
        if saved_token:
            payload = self._decode_jwt_payload(saved_token)
            if payload:
                exp_time = datetime.fromtimestamp(payload.get('exp', 0), timezone.utc)
                print(f"✅ 保存済みトークンを使用中 (有効期限: {exp_time.strftime('%Y-%m-%d %H:%M:%S UTC')})")
                self.session_token = saved_token
                return True

        # No valid saved token, prompt for new one
        print("🔑 Okta JWT トークンを入力してください:")

        try:
            token = input("トークン: ").strip()
            if not token:
                print("❌ トークンは空にできません")
                return False

            # Validate token format and expiration
            if not self._is_token_valid(token):
                payload = self._decode_jwt_payload(token)
                if payload:
                    exp_time = datetime.fromtimestamp(payload.get('exp', 0), timezone.utc)
                    print(f"❌ トークンが期限切れまたは無効です (期限切れ: {exp_time.strftime('%Y-%m-%d %H:%M:%S UTC')})")
                else:
                    print("❌ 無効なトークン形式です")
                return False

            # Save the valid token
            self._save_token(token)
            self.session_token = token

            payload = self._decode_jwt_payload(token)
            exp_time = datetime.fromtimestamp(payload.get('exp', 0), timezone.utc)
            print(f"✅ トークンを保存しセッションに格納しました (有効期限: {exp_time.strftime('%Y-%m-%d %H:%M:%S UTC')})")
            return True

        except KeyboardInterrupt:
            print("\n\n👋 さようなら！")
            return False
    
    def clear_saved_token(self):
        """保存済みトークンファイルをクリアする"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print("🗑️  保存済みトークンをクリアしました")
            else:
                print("ℹ️  クリアする保存済みトークンがありません")
        except Exception as e:
            print(f"❌ トークンのクリア中にエラー: {e}")
    
    # ========================================================================
    # CORE COMMUNICATION
    # ========================================================================

    def chat(self, message: str, agent_type: str = None, okta_token: str = None) -> str:
        """エージェントにメッセージを送信しレスポンスを取得する"""
        import time
        
        # Start timing
        start_time = time.time()
        
        # Use selected runtime or default agent if not specified
        if agent_type is None:
            agent_type = self.selected_runtime or self.agentcore_config['client']['default_agent']
        
        # In local mode, skip token requirement
        if not self.local_mode:
            # Use session token if available
            if okta_token is None:
                okta_token = self.session_token
                
            if okta_token is None:
                raise ValueError("Okta token must be provided")
        
        # Get runtime URL and prepare request
        url = self._get_runtime_url(agent_type)
        payload = self._get_payload(message, agent_type, self.session_id, "user")
        trace_id = str(uuid.uuid4())
        
        # Build headers based on mode
        headers = {
            'Content-Type': 'application/json',
            'X-Amzn-Trace-Id': f'trace-{trace_id[:10]}',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': self.session_id or trace_id
        }
        
        # Add authorization header only in non-local mode
        if not self.local_mode:
            headers['Authorization'] = f'Bearer {okta_token}'
        
        # DEBUG: Log request details
        if self.debug:
            print("\n" + "="*80)
            print("[DEBUG] OUTGOING REQUEST:")
            print(f"[DEBUG] URL: {url}")
            print(f"[DEBUG] Method: POST")
            print(f"[DEBUG] Headers:")
            for key, value in headers.items():
                if key == 'Authorization':
                    print(f"[DEBUG]   {key}: Bearer {value[7:15]}...{value[-10:]}")
                else:
                    print(f"[DEBUG]   {key}: {value}")
            print(f"[DEBUG] Payload:")
            print(f"[DEBUG]   {json.dumps(payload, indent=2)}")
            print("="*80)
        
        try:
            # Record request sent time
            request_sent_time = time.time()
            
            # Add timeout for better error handling
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=900)
            
            # Record first response time (headers received)
            first_response_time = time.time()
            
            # DEBUG: Log response details
            if self.debug:
                print("\n" + "="*80)
                print("[DEBUG] INCOMING RESPONSE:")
                print(f"[DEBUG] Status Code: {response.status_code}")
                print(f"[DEBUG] Response Headers:")
                for key, value in response.headers.items():
                    print(f"[DEBUG]   {key}: {value}")
                print(f"[DEBUG] Time to first response: {first_response_time - request_sent_time:.3f}s")
                print("="*80)
            
            if response.status_code != 200:
                error_text = ""
                try:
                    error_text = response.text
                except Exception as read_error:
                    error_text = f"<Could not read response text: {read_error}>"
                
                if self.debug:
                    print(f"\n[DEBUG] ERROR RESPONSE BODY:")
                    print(f"[DEBUG] {error_text}")
                    print("="*80)
                
                raise Exception(f"HTTP {response.status_code}: {error_text}")
            
            # Handle different response types
            content_type = response.headers.get("content-type", "")
            
            if "text/event-stream" in content_type:
                 # Server-Sent Events streaming (test commands)
                 response_text = self._handle_streaming_response(response, agent_type, start_time, first_response_time)
            elif "text/plain" in content_type:
                 # Plain text streaming (regular agent responses)
                 response_text = self._handle_plain_text_streaming(response, agent_type, start_time, first_response_time)
            else:
                print(response)
                 # Non-streaming response (fallback)
                response_text = response.text
                end_time = time.time()
                total_time = end_time - start_time
                
                if self.debug:
                     print(f"\n[DEBUG] NON-STREAMING RESPONSE:")
                     print(f"[DEBUG] Content-Type: {content_type}")
                     print(f"[DEBUG] Response: {response_text}")
                     print(f"[DEBUG] Total time: {total_time:.3f}s")
                     print("="*80)
                
                 # Display the response if it's not empty
                if response_text.strip():
                     print(f"🤖 {agent_type.upper()}: {response_text}")
                     print(f"⏱️  レスポンス時間: {total_time:.3f}秒")
                else:
                     print(f"🤖 {agent_type.upper()}: <空のレスポンス>")
                     print(f"⏱️  レスポンス時間: {total_time:.3f}秒")
            
            # Process and print the response
            return response_text
                
        except Exception as e:
            end_time = time.time()
            total_time = end_time - start_time
            
            if self.debug:
                print(f"\n[DEBUG] EXCEPTION OCCURRED:")
                print(f"[DEBUG] Exception Type: {type(e).__name__}")
                print(f"[DEBUG] Exception Message: {str(e)}")
                print(f"[DEBUG] Time before exception: {total_time:.3f}s")
                import traceback
                print(f"[DEBUG] Full Traceback:")
                print(traceback.format_exc())
                print("="*80)
            # Preserve the original exception details for better error reporting
            raise Exception(f"{agent_type} エージェントとの通信中にエラーが発生しました: {str(e)}")
    
    # ========================================================================
    # CONVERSATION MANAGEMENT
    # ========================================================================
    
    def add_to_history(self, user_message: str, agent_response: str):
        """メッセージのやり取りをローカル会話履歴に追加する"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conversation_history.append({
            'timestamp': timestamp,
            'user': user_message,
            'agent': agent_response,
            'runtime': self.selected_runtime
        })
    
    def display_conversation_history(self):
        """会話履歴を表示する"""
        if not self.conversation_history:
            print("📝 まだ会話履歴がありません")
            return

        print(f"\n📜 会話履歴 ({len(self.conversation_history)} 件のメッセージ)")
        print("=" * 60)
        
        for i, exchange in enumerate(self.conversation_history, 1):
            print(f"\n[{exchange['timestamp']}] Exchange #{i}")
            print(f"👤 You: {exchange['user']}")
            print(f"🤖 {exchange['runtime'].upper()}: {exchange['agent']}")
    
    def display_memory_stats(self):
        """Memory 使用量とセッション情報を表示する"""
        print(f"\n🧠 メモリとセッション情報")
        print("=" * 40)
        print(f"セッション ID: {self.session_id or '未開始'}")
        print(f"選択中のランタイム: {self.selected_runtime or 'なし'}")
        print(f"ローカル履歴数: {len(self.conversation_history)}")
        print(f"メモリサポート: エージェントランタイム (bedrock-agentcore) で利用可能")

        if self.session_id:
            print(f"\nℹ️  エージェントメモリはセッション ID を使用してサーバー側で管理されています")
            print(f"   このセッションの以前の会話は自動的に")
            print(f"   エージェントレスポンスのコンテキストに含まれます。")
        else:
            print(f"\n⚠️  アクティブなセッションがありません - メモリトラッキングは利用できません")
    
    # ========================================================================
    # USER INTERFACE & INTERACTION
    # ========================================================================
    
    def chat_loop(self):
        """メインチャット会話ループ"""
        print(f"\n💬 チャットセッションを開始しました")
        print(f"🔗 セッション ID: {self.session_id}")
        print(f"🐛 デバッグモード: {'オン' if self.debug else 'オフ'}")
        print("'quit', 'exit' と入力するか、Ctrl+C でセッションを終了")
        print("'switch' と入力してランタイムを変更")
        print("'token' と入力して認証トークンを更新")
        print("'clear-token' と入力して保存済みトークンをクリア")
        print("'debug' と入力してデバッグモードを切り替え (ARN と詳細ログを表示)")
        print("'test' または 'ping' と入力してエージェント接続をテスト")
        print("'mcp test' と入力して MCP ゲートウェイ接続をテスト")
        print("-" * 50)
        
        while True:
            try:
                user_input = input(f"\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    break
                elif user_input.lower() == 'history':
                    self.display_conversation_history()
                    continue
                elif user_input.lower() == 'switch':
                    if self.select_runtime():
                        continue
                    else:
                        break
                elif user_input.lower() == 'token':
                    if self.get_okta_token():
                        continue
                    else:
                        break
                elif user_input.lower() == 'clear-token':
                    self.clear_saved_token()
                    continue
                elif user_input.lower() == 'memory-stats':
                    self.display_memory_stats()
                    continue
                elif user_input.lower() == 'debug':
                    self.debug = not self.debug
                    print(f"🐛 デバッグモード {'有効' if self.debug else '無効'}")
                    continue
                elif user_input.lower() in ['test', 'ping']:
                    # Simple connectivity test
                    try:
                        response = self.chat("ping")
                        if response:
                            print("✅ エージェント接続テスト成功")
                        else:
                            print("❌ エージェント接続テスト失敗 - 空のレスポンス")
                    except Exception as test_error:
                        print(f"❌ エージェント接続テスト失敗: {test_error}")
                        if self._should_show_detailed_errors(str(test_error)):
                            import traceback
                            print(f"\n🔍 Full error traceback:")
                            print(traceback.format_exc())
                            print("=" * 60)
                    continue
                elif not user_input:
                    continue
                
                # Send message to runtime
                try:
                    response = self.chat(user_input)
                    if response:
                        # Note: response is already printed during streaming in _handle_streaming_response
                        self.add_to_history(user_input, response)
                    else:
                        print("❌ ランタイムからレスポンスを取得できませんでした - レスポンスがありません")
                except Exception as chat_error:
                    print(f"❌ チャットエラー: {chat_error}")
                    if self._should_show_detailed_errors(str(chat_error)):
                        import traceback
                        print(f"\n🔍 Full error traceback:")
                        print(traceback.format_exc())
                        print("=" * 60)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ 予期しないエラー: {e}")
                if self._should_show_detailed_errors(str(e)):
                    import traceback
                    print(f"\n🔍 Full error traceback:")
                    print(traceback.format_exc())
                    print("=" * 60)
        
        print(f"\n👋 チャットセッションを終了しました。合計やり取り数: {len(self.conversation_history)}")
    
    def run_interactive_mode(self):
        """チャットボットクライアントをインタラクティブモードで実行する"""
        mode_text = "Local Testing Mode" if self.local_mode else "AgentCore Chatbot Client"
        print(f"🤖 {mode_text}")
        print("=" * 30)
        
        # Step 1: Select runtime
        if not self.select_runtime():
            return
        
        # Step 2: Get Okta token (skip in local mode)
        if not self.local_mode:
            if not self.get_okta_token():
                return
        else:
            print("🏠 ローカルモード: 認証をスキップ")
        
        # Step 3: Start chat session
        self.chat_loop()
    
    # ------------------------------------------------------------------------
    # STREAMING RESPONSE HANDLERS (Part of Core Communication)
    # ------------------------------------------------------------------------
    
    def _handle_plain_text_streaming(self, response, agent_type: str, start_time: float, first_response_time: float) -> str:
        """DIY エージェントからのプレーンテキストストリーミングレスポンスを処理する"""
        import time
        
        content = []
        first_chunk_time = None
        last_chunk_time = None
        
        print(f"🤖 {agent_type.upper()}: ", end="" if not self.debug else "\n", flush=True)
        
        if self.debug:
            print("\n" + "="*80)
            print("[DEBUG] PLAIN TEXT STREAMING RESPONSE:")
            print(f"[DEBUG] Agent Type: {agent_type}")
            print(f"[DEBUG] Status Code: {response.status_code}")
            print(f"[DEBUG] Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"[DEBUG] All Headers: {dict(response.headers)}")
            print(f"[DEBUG] Time to first response: {first_response_time - start_time:.3f}s")
            print("="*80)
        
        try:
            chunk_count = 0
            total_bytes = 0
            
            # Show raw response info
            if self.debug:
                print(f"[DEBUG] Starting to read response stream...")
                print(f"[DEBUG] Response encoding: {response.encoding}")
                print(f"[DEBUG] Response apparent encoding: {response.apparent_encoding}")
            
            for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
                if chunk:
                    current_time = time.time()
                    if first_chunk_time is None:
                        first_chunk_time = current_time
                    last_chunk_time = current_time
                    
                    chunk_count += 1
                    total_bytes += len(chunk.encode('utf-8'))
                    
                    if self.debug:
                        print(f"[DEBUG] Chunk #{chunk_count}: {repr(chunk)} (bytes: {len(chunk.encode('utf-8'))}, time: {current_time - start_time:.3f}s)")
                    
                    # Stream character by character for real-time display
                    if not self.debug:
                        print(chunk, end="", flush=True)
                    content.append(chunk)
            
            # Calculate timing metrics
            end_time = time.time()
            total_time = end_time - start_time
            time_to_first_chunk = first_chunk_time - start_time if first_chunk_time else 0
            streaming_duration = last_chunk_time - first_chunk_time if first_chunk_time and last_chunk_time else 0
            
            # If no chunks received, check raw response
            if chunk_count == 0:
                if self.debug:
                    print(f"[DEBUG] No chunks received! Checking raw response...")
                    try:
                        raw_content = response.content
                        print(f"[DEBUG] Raw response content: {raw_content}")
                        print(f"[DEBUG] Raw response text: {response.text}")
                    except Exception as raw_error:
                        print(f"[DEBUG] Error reading raw response: {raw_error}")
            
            if self.debug:
                print(f"\n[DEBUG] PLAIN TEXT STREAMING COMPLETE:")
                print(f"[DEBUG] Total chunks processed: {chunk_count}")
                print(f"[DEBUG] Total bytes received: {total_bytes}")
                print(f"[DEBUG] Final content length: {len(''.join(content))}")
                print(f"[DEBUG] Final content: {repr(''.join(content))}")
                print(f"[DEBUG] TIMING BREAKDOWN:")
                print(f"[DEBUG]   Total time: {total_time:.3f}s")
                print(f"[DEBUG]   Time to first response: {first_response_time - start_time:.3f}s")
                print(f"[DEBUG]   Time to first chunk: {time_to_first_chunk:.3f}s")
                print(f"[DEBUG]   Streaming duration: {streaming_duration:.3f}s")
                print("="*80)
                if content:
                    print(f"🤖 {agent_type.upper()}: {''.join(content)}")
                else:
                    print(f"🤖 {agent_type.upper()}: [NO CONTENT RECEIVED]")
            else:
                if not content:
                    print("\n❌ ランタイムからレスポンスを取得できませんでした")
                else:
                    print()  # New line after streaming is complete
            
            # Show timing information (always show, not just in debug mode)
            if content:
                print(f"⏱️  レスポンス時間: {total_time:.3f}秒 (最初のチャンク: {time_to_first_chunk:.3f}秒, ストリーミング: {streaming_duration:.3f}秒)")
            else:
                print(f"⏱️  レスポンス時間: {total_time:.3f}秒 (コンテンツを受信しませんでした)")
            
        except Exception as e:
            end_time = time.time()
            total_time = end_time - start_time
            error_msg = f"❌ ストリーミングエラー: {str(e)}"
            if self.debug:
                print(f"\n[DEBUG] PLAIN TEXT STREAMING ERROR: {error_msg}")
                print(f"[DEBUG] Exception type: {type(e)}")
                print(f"[DEBUG] Total time before error: {total_time:.3f}s")
                import traceback
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
                print("="*80)
            else:
                print(f"\n{error_msg}")
                print(f"⏱️  エラー発生までの時間: {total_time:.3f}秒")
            content.append(error_msg)

        return ''.join(content)

    def _handle_streaming_response(self, response, agent_type: str, start_time: float, first_response_time: float) -> str:
        """Server-Sent Events ストリーミングレスポンスを処理する（テストコマンド用）"""
        import time
        
        content = []
        first_chunk_time = None
        last_chunk_time = None
        
        print(f"🤖 {agent_type.upper()}: ", end="" if not self.debug else "\n", flush=True)
        
        if self.debug:
            print("\n" + "="*80)
            print("[DEBUG] SSE STREAMING RESPONSE PROCESSING:")
            print(f"[DEBUG] Agent Type: {agent_type}")
            print(f"[DEBUG] Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"[DEBUG] Time to first response: {first_response_time - start_time:.3f}s")
            print("="*80)
        
        line_count = 0
        try:
            for line in response.iter_lines(decode_unicode=True):
                current_time = time.time()
                if first_chunk_time is None and line and line.startswith("data: "):
                    first_chunk_time = current_time
                if line and line.startswith("data: "):
                    last_chunk_time = current_time
                
                line_count += 1
                
                if self.debug:
                    print(f"\n[DEBUG] Raw Line #{line_count}: {repr(line)} (time: {current_time - start_time:.3f}s)")
                
                if line and line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    
                    if self.debug:
                        print(f"[DEBUG] Extracted Data: {repr(data)}")
                    
                    text_content = self._extract_text_from_sse_data(data, agent_type)
                    
                    # Stream the content in real-time
                    if text_content:
                        if self.debug:
                            print(f"[DEBUG] Streaming text content: {repr(text_content)}")
                        if not self.debug:
                            print(text_content, end="", flush=True)
                        content.append(text_content)
                    elif self.debug:
                        print(f"[DEBUG] No text content extracted from this chunk")
                elif self.debug and line:
                    print(f"[DEBUG] Non-data line: {repr(line)}")
        
        except Exception as e:
            end_time = time.time()
            total_time = end_time - start_time
            error_msg = f"❌ SSE ストリーミングエラー: {str(e)}"
            if self.debug:
                print(f"\n[DEBUG] SSE STREAMING ERROR: {error_msg}")
                print(f"[DEBUG] Total time before error: {total_time:.3f}s")
                print("="*80)
            else:
                print(f"\n{error_msg}")
                print(f"⏱️  エラー発生までの時間: {total_time:.3f}秒")
            content.append(error_msg)
        
        # Calculate timing metrics
        end_time = time.time()
        total_time = end_time - start_time
        time_to_first_chunk = first_chunk_time - start_time if first_chunk_time else 0
        streaming_duration = last_chunk_time - first_chunk_time if first_chunk_time and last_chunk_time else 0
        
        if self.debug:
            print(f"\n[DEBUG] SSE STREAMING COMPLETE:")
            print(f"[DEBUG] Total lines processed: {line_count}")
            print(f"[DEBUG] Content chunks collected: {len(content)}")
            print(f"[DEBUG] Final content: {repr(''.join(content))}")
            print(f"[DEBUG] TIMING BREAKDOWN:")
            print(f"[DEBUG]   Total time: {total_time:.3f}s")
            print(f"[DEBUG]   Time to first response: {first_response_time - start_time:.3f}s")
            print(f"[DEBUG]   Time to first chunk: {time_to_first_chunk:.3f}s")
            print(f"[DEBUG]   Streaming duration: {streaming_duration:.3f}s")
            print("="*80)
            print(f"🤖 {agent_type.upper()}: {''.join(content)}")
        else:
            print()  # New line after streaming is complete
        
        # Show timing information (always show, not just in debug mode)
        if content:
            print(f"⏱️  レスポンス時間: {total_time:.3f}秒 (最初のチャンク: {time_to_first_chunk:.3f}秒, ストリーミング: {streaming_duration:.3f}秒)")
        else:
            print(f"⏱️  レスポンス時間: {total_time:.3f}秒 (コンテンツを受信しませんでした)")

        return ''.join(content)
    
    def _extract_text_from_sse_data(self, data: str, agent_type: str) -> str:
        """Server-Sent Events データからテキストコンテンツを抽出する"""
        text_content = None
        
        try:
            event_data = json.loads(data)
            
            if self.debug:
                print(f"[DEBUG] Parsed SSE Event Data: {json.dumps(event_data, indent=2)}")
            
            if agent_type == "diy":
                # DIY agent SSE format - handle refactored agent response
                if 'content' in event_data and event_data.get('type') == 'text_delta':
                    # Extract text from content field (main text chunks)
                    text_content = event_data['content']
                    if self.debug:
                        print(f"[DEBUG] Extracted text from content field: {repr(text_content)}")
                elif 'message' in event_data:
                    text_content = event_data['message']
                elif 'error' in event_data:
                    text_content = f"❌ {event_data['error']}"
                elif 'status' in event_data and event_data['status'] == 'error':
                    text_content = event_data.get('message', 'Unknown error')
                elif 'event' in event_data:
                    # Parse Strands agent events from refactored DIY agent
                    event_str = str(event_data['event'])
                    
                    # Try to extract text from contentBlockDelta events
                    if 'contentBlockDelta' in event_str and 'text' in event_str:
                        import re
                        # Updated pattern to match the new format
                        delta_pattern = r"'text':\s*'([^']*?)'"
                        delta_match = re.search(delta_pattern, event_str)
                        if delta_match:
                            text_content = delta_match.group(1)
                            if self.debug:
                                print(f"[DEBUG] Extracted text from contentBlockDelta: {repr(text_content)}")
                    
                    # Also try to parse if it's a dict-like string representation
                    elif 'contentBlockDelta' in event_str:
                        try:
                            # Try to evaluate the string as a Python dict
                            import ast
                            parsed_event = ast.literal_eval(event_str)
                            if isinstance(parsed_event, dict) and 'event' in parsed_event:
                                content_block = parsed_event['event'].get('contentBlockDelta', {})
                                delta = content_block.get('delta', {})
                                if 'text' in delta:
                                    text_content = delta['text']
                                    if self.debug:
                                        print(f"[DEBUG] Extracted text from parsed dict: {repr(text_content)}")
                        except (ValueError, SyntaxError) as parse_error:
                            if self.debug:
                                print(f"[DEBUG] Could not parse event string as dict: {parse_error}")
            else:
                # SDK agent SSE format
                if isinstance(event_data, dict):
                    event = event_data.get('event', {})
                    if 'contentBlockDelta' in event:
                        delta = event['contentBlockDelta'].get('delta', {})
                        if 'text' in delta:
                            text_content = delta['text']
                            
        except json.JSONDecodeError:
            # If it's not JSON, treat as plain text
            if data.strip() and not data.startswith('{'):
                text_content = data.strip()
                if self.debug:
                    print(f"[DEBUG] Using as plain text: {repr(text_content)}")
        
        return text_content or ""

# ============================================================================
# MODULE FUNCTIONS
# ============================================================================

def main():
    """インタラクティブモードとコマンドラインモードの両方をサポートするメイン CLI インターフェース"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentCore Chatbot Client")
    parser.add_argument("--agent", choices=["sdk", "diy"], help="Agent type to use (if not provided, will prompt)")
    parser.add_argument("--token", help="Okta JWT token (if not provided, will prompt)")
    parser.add_argument("--message", help="Message to send (if not provided, enters interactive mode)")
    parser.add_argument("--interactive", action="store_true", help="Force interactive mode with runtime selection")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging (shows ARNs and detailed requests/responses)")
    parser.add_argument("--local", action="store_true", help="Local testing mode - connect to localhost:8080 without authentication")
    
    args = parser.parse_args()
    
    client = AgentCoreClient(debug=args.debug, local_mode=args.local)
    
    # Local mode or interactive mode
    if args.local or args.interactive or (not args.local and (not args.agent or not args.token)):
        client.run_interactive_mode()
        return
    
    # Command-line mode with all parameters provided (non-local mode)
    if args.message:
        # Single message mode
        try:
            response = client.chat(args.message, args.agent, args.token)
            print(f"\n{args.agent.upper()} Agent Response:")
            print("=" * 50)
            print(response)
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        # Simple chat mode with specified agent and token
        client.session_token = args.token
        client.selected_runtime = args.agent
        
        mode_text = "ローカルテスト" if args.local else "AgentCore チャットボットクライアント"
        print(f"🤖 {mode_text} - {args.agent.upper()} エージェント")
        print("'quit' または 'exit' で終了")
        print("=" * 50)
        
        while True:
            try:
                message = input("\n👤 You: ").strip()
                if message.lower() in ['quit', 'exit']:
                    break
                if message:
                    response = client.chat(message, args.agent, args.token)
                    print(f"\n🤖 {args.agent.upper()}: {response}")
                    client.add_to_history(message, response)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ エラー: {e}")

        print(f"\n👋 チャットセッションを終了しました。合計やり取り数: {len(client.conversation_history)}")

if __name__ == "__main__":
    main()