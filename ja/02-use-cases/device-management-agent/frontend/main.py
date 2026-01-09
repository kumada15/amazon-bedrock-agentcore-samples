"""
デバイス管理システム - フロントエンド Web アプリケーション

このモジュールは、FastAPI、WebSocket、および Amazon Cognito 認証を使用して、
デバイス管理システムの Web ベースユーザーインターフェースを実装します。
ユーザーが自然言語で IoT デバイスと対話できるチャット風インターフェースを提供します。

主な機能:
    - WebSocket を使用したリアルタイムチャットインターフェース
    - Amazon Cognito 認証統合
    - CSRF 保護付きセッション管理
    - Jinja2 テンプレートによるレスポンシブ Web デザイン
    - 安全なクロスオリジンリクエスト用の CORS 設定
    - エラーハンドリングとユーザーフレンドリーなメッセージング

アーキテクチャ:
    - FastAPI: Web フレームワークと API エンドポイント
    - WebSocket: Agent Runtime とのリアルタイム通信
    - Jinja2: HTML テンプレートレンダリング
    - Session Middleware: 安全なセッション管理
    - CORS Middleware: クロスオリジンリクエスト処理
    - 認証: Amazon Cognito OAuth 統合

ルート:
    GET /: メインチャットインターフェース（認証必須）
    GET /login: Amazon Cognito ログインページ
    GET /simple-login: 開発用シンプルログインフォーム
    POST /simple-login: シンプルログインの処理
    GET /auth/callback: OAuth コールバックハンドラー
    GET /logout: ユーザーログアウト
    WebSocket /ws/{client_id}: リアルタイムチャット通信

環境変数:
    HOST: サーバーホスト（デフォルト: 127.0.0.1）
    PORT: サーバーポート（デフォルト: 8000）
    CORS_ORIGINS: 許可される CORS オリジン
    COGNITO_*: Amazon Cognito 設定
    AGENT_ARN: Amazon Bedrock AgentCore ランタイム ARN

使用例:
    アプリケーションを実行:
    >>> python main.py
    >>> # http://localhost:8000 でアクセス
"""
import os
import json
import logging
import secrets
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import boto3

# 認証モジュールのインポート
from auth import get_login_url, exchange_code_for_tokens, validate_token, get_current_user, login_required

# 環境変数の読み込み
load_dotenv()

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI アプリの初期化
app = FastAPI(title="Device Management Chat Application")

# セキュアなランダムキーでセッションミドルウェアを追加
app.add_middleware(
    SessionMiddleware, 
    secret_key=secrets.token_urlsafe(32),
    max_age=3600  # 1 hour session
)

# CORS ミドルウェアの追加
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# テンプレートと静的ファイルのセットアップ
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 環境変数
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
AGENT_ARN = os.getenv("AGENT_ARN")

if not AGENT_ARN:
    logger.error("AGENT_ARN 環境変数が設定されていません")
    raise ValueError("AGENT_ARN environment variable is required")

# Pydantic モデル
class Message(BaseModel):
    """
    会話内のチャットメッセージを表します。

    Attributes:
        role (str): メッセージ送信者のロール（'user' または 'assistant'）
        content (str): メッセージの内容/テキスト
    """
    role: str
    content: str


class ChatRequest(BaseModel):
    """
    チャット API エンドポイント用のリクエストモデル。

    Attributes:
        messages (List[Message]): 会話内のメッセージリスト
    """
    messages: List[Message]


class ConnectionManager:
    """
    リアルタイムチャット機能用の WebSocket 接続を管理します。

    このクラスは、チャットインターフェース用の WebSocket 接続ライフサイクル、
    メッセージルーティング、およびセッション管理を処理します。各クライアント接続は
    一意の client_id で識別され、ランタイムセッション ID を通じて会話コンテキストを
    維持できます。

    Attributes:
        active_connections (Dict[str, WebSocket]): client_id から WebSocket へのマップ
        session_ids (Dict[str, str]): client_id から runtime_session_id へのマップ
    """

    def __init__(self):
        """空の接続プールでコネクションマネージャーを初期化します。"""
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_ids: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """
        新しい WebSocket 接続を受け入れ、クライアントを登録します。

        Args:
            websocket (WebSocket): 受け入れる WebSocket 接続
            client_id (str): クライアント接続の一意識別子
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.session_ids[client_id] = None

    def disconnect(self, client_id: str):
        """
        クライアントを切断し、関連するリソースをクリーンアップします。

        Args:
            client_id (str): 切断するクライアントの一意識別子
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.session_ids:
            del self.session_ids[client_id]

    async def send_message(self, message: str, client_id: str):
        """
        特定のクライアントにメッセージを送信します。

        Args:
            message (str): 送信するメッセージ
            client_id (str): 送信先クライアントの一意識別子
        """
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    def get_session_id(self, client_id: str) -> Optional[str]:
        """
        クライアントの現在のセッション ID を取得します。

        Args:
            client_id (str): クライアントの一意識別子

        Returns:
            Optional[str]: セッション ID、または設定されていない場合は None
        """
        return self.session_ids.get(client_id)

    def set_session_id(self, client_id: str, session_id: str):
        """
        クライアントのセッション ID を設定します。

        Args:
            client_id (str): クライアントの一意識別子
            session_id (str): 設定するセッション ID
        """
        self.session_ids[client_id] = session_id

manager = ConnectionManager()

def parse_streaming_response(content):
    """ストリーミングレスポンスコンテンツを解析して最終レスポンステキストを抽出します"""
    try:
        logger.debug(f"ストリーミングコンテンツを解析中: {len(content)} 文字")
        
        # 行ごとに分割して最終レスポンスを検索
        lines = content.strip().split('\n')
        final_response = ""
        accumulated_text = ""
        
        # 末尾から最終完了メッセージを検索
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
                
            try:
                # JSON として直接パースを試行（AgentCore レスポンス用）
                if line.startswith('{') and line.endswith('}'):
                    json_data = json.loads(line)
                # 'data: ' プレフィックス付きの SSE 形式を処理
                elif line.startswith('data: '):
                    json_str = line[6:].strip()
                    if not json_str:
                        continue
                    json_data = json.loads(json_str)
                else:
                    continue
                
                # まず最終完了レスポンスを検索
                if isinstance(json_data, dict):
                    # final_response 付きの complete タイプをチェック（最優先）
                    if json_data.get('type') == 'complete' and 'final_response' in json_data:
                        final_response = json_data['final_response']
                        logger.debug("complete タイプと final_response を検出しました")
                        break
                    
                    # 完全レスポンス付きのメッセージコンテンツをチェック
                    elif 'message' in json_data:
                        message = json_data['message']
                        if isinstance(message, dict) and 'content' in message:
                            content_list = message['content']
                            if isinstance(content_list, list):
                                text_parts = []
                                for item in content_list:
                                    if isinstance(item, dict) and 'text' in item:
                                        text_parts.append(item['text'])
                                if text_parts:
                                    candidate_response = ' '.join(text_parts)
                                    # 実質的なレスポンスの場合のみ使用（最終レスポンスの可能性が高い）
                                    if len(candidate_response) > 200:
                                        final_response = candidate_response
                        logger.debug("実質的なメッセージコンテンツを検出しました")
                                        break
                    
            except json.JSONDecodeError as e:
                logger.debug(f"JSON 行の解析に失敗しました: {line[:100]}... エラー: {e}")
                continue
            except Exception as e:
                logger.debug(f"行の処理中にエラーが発生しました: {e}")
                continue
        
        # 最終レスポンスが見つからない場合、テキストチャンクを累積
        if not final_response:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    if line.startswith('{') and line.endswith('}'):
                        json_data = json.loads(line)
                    elif line.startswith('data: '):
                        json_str = line[6:].strip()
                        if not json_str:
                            continue
                        json_data = json.loads(json_str)
                    else:
                        continue
                    
                    if isinstance(json_data, dict):
                        # ストリーミングテキストチャンクをチェック
                        if 'event' in json_data:
                            event = json_data['event']
                            if isinstance(event, dict):
                                # contentBlockDelta イベントを処理
                                if 'contentBlockDelta' in event:
                                    delta = event['contentBlockDelta']
                                    if isinstance(delta, dict) and 'delta' in delta:
                                        delta_data = delta['delta']
                                        if isinstance(delta_data, dict) and 'text' in delta_data:
                                            accumulated_text += delta_data['text']
                        
                        # チャンクデータをチェック
                        elif 'data' in json_data and isinstance(json_data['data'], str):
                            accumulated_text += json_data['data']
                        
                except json.JSONDecodeError:
                    continue
                except Exception:
                    continue
        
        # 見つかった最良のレスポンスを返す
        if final_response:
            logger.info(f"最終レスポンスを抽出しました: {len(final_response)} 文字")
            return final_response
        elif accumulated_text:
            logger.info(f"累積テキストを使用: {len(accumulated_text)} 文字")
            return accumulated_text
        else:
            logger.warning("ストリーミングデータにレスポンステキストが見つかりませんでした")
            return f"No parseable response found. Raw content sample: {content[:500]}..."
        
    except Exception as e:
        logger.error(f"ストリーミングレスポンスの解析中にエラーが発生しました: {str(e)}")
        return f"Error parsing response: {str(e)}"

def format_response_text(text):
    """UI での読みやすさを向上させるためにレスポンステキストをフォーマットします"""
    if not text:
        return ""
    
    try:
        # まずテキストをクリーンアップ
        text = text.strip()
        
        # JSON らしい場合は JSON としてパースを試行
        if (text.startswith('{') and text.endswith('}')) or \
           (text.startswith('[') and text.endswith(']')):
            try:
                parsed = json.loads(text)
                
                # デバイスリストの場合は見やすくフォーマット
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                    # デバイスリストらしいかチェック
                    if all('device_id' in item or 'name' in item for item in parsed):
                        result = "📱 **Device List:**\n\n"
                        for i, item in enumerate(parsed, 1):
                            name = item.get('name', 'Unknown Device')
                            device_id = item.get('device_id', item.get('id', 'Unknown ID'))
                            status = item.get('connection_status', item.get('status', 'Unknown'))
                            
                            # ステータス絵文字を追加
                            status_emoji = {
                                'Connected': '🟢',
                                'Disconnected': '🔴', 
                                'Updating': '🟡',
                                'Dormant': '🟠',
                                'Maintenance': '🔧'
                            }.get(status, '⚪')
                            
                            result += f"**{i}. {name}** {status_emoji}\n"
                            result += f"   • ID: `{device_id}`\n"
                            
                            if 'model' in item:
                                result += f"   • Model: {item['model']}\n"
                            if 'ip_address' in item:
                                result += f"   • IP: {item['ip_address']}\n"
                            if 'connection_status' in item:
                                result += f"   • Status: {item['connection_status']}\n"
                            if 'firmware_version' in item:
                                result += f"   • Firmware: {item['firmware_version']}\n"
                            if 'last_connected' in item:
                                # タイムスタンプを見やすくフォーマット
                                timestamp = item['last_connected']
                                if 'T' in timestamp:
                                    date_part = timestamp.split('T')[0]
                                    time_part = timestamp.split('T')[1].split('.')[0]
                                    result += f"   • Last Connected: {date_part} at {time_part}\n"
                                else:
                                    result += f"   • Last Connected: {timestamp}\n"
                            
                            result += "\n"
                        
                        return result.strip()
                
                # その他の JSON データはインデント付きで整形表示
                return f"```json\n{json.dumps(parsed, indent=2)}\n```"
                
            except json.JSONDecodeError:
                # 有効な JSON ではないため、通常のフォーマットを続行
                pass
        
        # エスケープ文字を置換
        text = text.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
        
        # 箇条書きを一貫してフォーマット
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
                
            # 番号付きリストを箇条書きに変換
            if line and len(line) > 2 and line[0].isdigit() and line[1:3] in ['. ', ') ']:
                line = '• ' + line.split('. ', 1)[1] if '. ' in line else '• ' + line.split(') ', 1)[1]
            
            # 箇条書きのフォーマットを統一
            elif line.startswith('- '):
                line = '• ' + line[2:]
            
            # キー値ペアを見やすくフォーマット
            elif ':' in line and not line.startswith('  ') and not line.startswith('•'):
                parts = line.split(':', 1)
                if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                    key = parts[0].strip()
                    value = parts[1].strip()
                    line = f"**{key}:** {value}"
            
            formatted_lines.append(line)
        
        result = '\n'.join(formatted_lines)
        
        # 過度な空白をクリーンアップ
        while '\n\n\n' in result:
            result = result.replace('\n\n\n', '\n\n')
        
        return result.strip()
        
    except Exception as e:
        logger.error(f"レスポンスのフォーマット中にエラーが発生しました: {str(e)}")
        return text  # フォーマット失敗時は元のテキストを返す

def create_agentcore_client(auth_token=None):
    """AgentCore クライアントと boto セッションを作成します"""
    # boto セッションを作成
    boto_session = boto3.Session(region_name=AWS_REGION)

    # bedrock-agentcore クライアントを作成
    agentcore_client = boto_session.client(
        'bedrock-agentcore',
        region_name=AWS_REGION
    )

    return agentcore_client

# ルート
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """ストリーミングサポート付きのリアルタイムチャット用 WebSocket エンドポイント"""
    await manager.connect(websocket, client_id)
    
    try:
        # AgentCore クライアントの作成
        agentcore_client = create_agentcore_client()
        
        while True:
            data = await websocket.receive_text()
            user_message = data.strip()
            
            if not user_message:
                await manager.send_message(json.dumps({"error": "Empty message"}), client_id)
                continue
            
            try:
                # このクライアントの現在のセッション ID を取得
                session_id = manager.get_session_id(client_id)

                # リトライロジック付きでエージェントを呼び出し
                from botocore.exceptions import ClientError

                max_retries = 3
                retry_delay = 1  # 1秒の遅延から開始
                
                for attempt in range(max_retries):
                    try:
                        if session_id is None:
                            # 会話の最初のメッセージ
                            logger.info("新しい会話をストリーミングで開始しています")
                            boto3_response = agentcore_client.invoke_agent_runtime(
                                agentRuntimeArn=AGENT_ARN,
                                qualifier="DEFAULT",
                                payload=json.dumps({"prompt": user_message})
                            )
                        else:
                            # 既存のセッション ID で会話を継続
                            logger.info(f"セッション ID で会話を継続: {session_id}")
                            boto3_response = agentcore_client.invoke_agent_runtime(
                                agentRuntimeArn=AGENT_ARN,
                                qualifier="DEFAULT",
                                payload=json.dumps({"prompt": user_message}),
                                runtimeSessionId=session_id
                            )
                        # 成功した場合、リトライループを抜ける
                        break
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'throttlingException' and attempt < max_retries - 1:
                            logger.warning(f"スロットリング例外が発生しました。{retry_delay} 秒後に再試行します...")
                            await manager.send_message(json.dumps({"status": "レート制限中です。{} 秒後に再試行します...".format(retry_delay)}), client_id)
                            import asyncio
                            await asyncio.sleep(retry_delay)
                            # 指数バックオフ
                            retry_delay *= 2
                        else:
                            # リトライ回数を使い切った場合、またはスロットリング例外でない場合は再スロー
                            raise
                
                # セッション ID を更新
                if isinstance(boto3_response, dict) and 'runtimeSessionId' in boto3_response:
                    new_session_id = boto3_response['runtimeSessionId']
                    logger.info(f"新しいセッション ID を受信しました: {new_session_id}")
                    manager.set_session_id(client_id, new_session_id)
                else:
                    logger.warning("レスポンスに runtimeSessionId がありません")
                    # 利用可能であれば既存のセッション ID を引き続き使用
                    new_session_id = session_id
                
                # AgentCore からのストリーミングレスポンス処理
                if isinstance(boto3_response, dict) and "response" in boto3_response:
                    try:
                        response_stream = boto3_response["response"]
                        logger.info(f"ストリーミングレスポンスを処理中、タイプ: {type(response_stream)}")

                        # StreamingBody の適切な処理
                        if hasattr(response_stream, 'read'):
                            content = response_stream.read()
                            if isinstance(content, bytes):
                                content = content.decode('utf-8')
                            
                            logger.debug(f"生のストリーミングコンテンツを受信しました: {len(content)} 文字")

                            # ストリーミングコンテンツを解析して最終レスポンスを抽出
                            final_response_text = parse_streaming_response(content)

                            if final_response_text:
                                # 完了メッセージを送信
                                await manager.send_message(json.dumps({
                                    "response": format_response_text(final_response_text),
                                    "sessionId": new_session_id,
                                    "complete": True
                                }), client_id)
                            else:
                                await manager.send_message(json.dumps({
                                    "error": "No valid response content found in streaming data"
                                }), client_id)
                        
                        else:
                            # フォールバック: 文字列に変換
                            content = str(response_stream)
                            final_response_text = parse_streaming_response(content)
                            
                            if final_response_text:
                                await manager.send_message(json.dumps({
                                    "response": format_response_text(final_response_text),
                                    "sessionId": new_session_id,
                                    "complete": True
                                }), client_id)
                            else:
                                await manager.send_message(json.dumps({
                                    "error": "No valid response content found"
                                }), client_id)
                            
                    except Exception as e:
                        logger.error(f'ストリーミングレスポンスの処理中にエラーが発生しました: {str(e)}')
                        await manager.send_message(json.dumps({
                            'error': f'Error processing streaming response: {str(e)}'
                        }), client_id)
                else:
                    # 非ストリーミングレスポンス処理にフォールバック
                    logger.warning('ストリーミングレスポンスが見つかりません。非ストリーミングにフォールバックします')
                    response_content = str(boto3_response)
                    formatted_response = format_response_text(response_content)
                    
                    await manager.send_message(json.dumps({
                        'response': formatted_response,
                        'sessionId': new_session_id
                    }), client_id)
                
            except Exception as e:
                error_message = str(e)
                logger.error(f'エージェントでのリクエスト処理中にエラーが発生しました: {error_message}')

                # 一般的な問題に対してより分かりやすいエラーメッセージを提供
                if 'throttlingException' in error_message:
                    error_message = 'リクエストが多すぎます。サービスは一時的にリクエストを制限しています。しばらくしてから再試行してください。'
                elif 'AccessDeniedException' in error_message:
                    error_message = 'アクセスが拒否されました。AWS 認証情報と権限を確認してください。'
                elif 'ValidationException' in error_message and 'runtimeSessionId' in error_message:
                    error_message = '無効なセッション ID です。新しい会話を開始します。'
                    manager.set_session_id(client_id, None)  # セッション ID をリセット
                
                await manager.send_message(json.dumps({
                    'error': f'Error processing request with agent: {error_message}'
                }), client_id)
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f'WebSocket エラー: {str(e)}')
        manager.disconnect(client_id)

# 認証ルート
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """認証されていない場合はログインに、認証済みの場合はチャットにリダイレクトするルートエンドポイント"""
    user = await get_current_user(request)
    if not user:
        # フォールバックとしてシンプルログインを最初に試行
        return RedirectResponse(url="/simple-login")
    return templates.TemplateResponse("chat.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Cognito 認証付きログインページ"""
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/")
    
    login_url = get_login_url()
    return templates.TemplateResponse("login.html", {"request": request, "login_url": login_url})

@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """Cognito 認証用のコールバックエンドポイント"""
    # 認証プロセスでエラーがあったか確認
    if error:
        error_msg = f"認証エラー: {error}"
        if error_description:
            error_msg += f" - {error_description}"
        logger.error(f"認証エラー: {error_msg}")
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "login_url": get_login_url(),
                "error": error_msg
            },
            status_code=400
        )
    
    # コードが提供されていない場合はエラーを返す
    if not code:
        logger.error("認証コードが提供されていません")
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request, 
                "login_url": get_login_url(),
                "error": "No authorization code provided"
            },
            status_code=400
        )
    
    try:
        # 認可コードをトークンと交換
        tokens = await exchange_code_for_tokens(code)

        # ID トークンを検証
        id_token = tokens["id_token"]
        claims = await validate_token(id_token)

        # ユーザー情報をセッションに保存
        request.session["user"] = {
            "sub": claims["sub"],
            "email": claims.get("email", ""),
            "name": claims.get("name", ""),
            "access_token": tokens["access_token"],
            "id_token": id_token
        }

        # メインページにリダイレクト
        return RedirectResponse(url="/")
    
    except Exception as e:
        logger.error(f"認証エラー: {str(e)}")
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request, 
                "login_url": get_login_url(),
                "error": str(e)
            },
            status_code=400
        )

@app.get("/logout")
async def logout(request: Request):
    """ログアウトエンドポイント"""
    # セッションをクリア
    request.session.clear()

    # レスポンスを作成し、すべての認証 Cookie をクリア
    response = RedirectResponse(url="/simple-login")
    response.delete_cookie("access_token")
    response.delete_cookie("simple_user")

    return response

@app.get("/profile")
async def profile(request: Request, user: dict = Depends(login_required)):
    """ユーザープロファイルエンドポイント"""
    return {"user": user}

@app.get("/simple-login", response_class=HTMLResponse)
async def simple_login_page(request: Request):
    """Cognito なしのシンプルログインページ"""
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/")

    # CSRF トークンを生成
    csrf_token = secrets.token_urlsafe(32)
    request.session["csrf_token"] = csrf_token

    return templates.TemplateResponse("simple_login.html", {"request": request, "csrf_token": csrf_token})

@app.post("/simple-login")
async def simple_login_submit(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    """シンプルログインフォームを処理します"""
    # CSRF トークンを検証
    session_csrf_token = request.session.get("csrf_token")
    if not session_csrf_token or csrf_token != session_csrf_token:
        raise HTTPException(status_code=403, detail="無効な CSRF トークンです")

    # 使用済みの CSRF トークンをクリア
    request.session.pop("csrf_token", None)

    # デモ用に任意のユーザー名/パスワードを受け入れ
    # 実際のアプリケーションでは、データベースまたは他の認証システムに対して検証します

    # ユーザー情報をセッションに保存
    request.session["user"] = {
        "sub": "simple-user-123",
        "email": username,
        "name": username,
        "access_token": "demo-token",
        "id_token": "demo-token"
    }

    # メインページにリダイレクト
    return RedirectResponse(url="/", status_code=303)  # 303 See Other は POST リダイレクトに使用

if __name__ == "__main__":
    import uvicorn
    import os
    host = os.getenv("HOST", "127.0.0.1")  # セキュリティのためデフォルトは localhost
    uvicorn.run("main:app", host=host, port=8000, reload=True)
