import asyncio
import json
import logging
import os
import uvicorn
import requests
from requests.exceptions import RequestException
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from s2s_session_manager import S2sSessionManager

# Configure logging
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


# Global variable to track credential refresh task
credential_refresh_task = None


def get_imdsv2_token():
    """
    セキュアなメタデータアクセス用の IMDSv2 トークンを取得する。

    Returns:
        str: IMDSv2 トークン、または IMDSv2 が利用できない場合は None
    """
    try:
        response = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=2,
        )
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return None


def get_credentials_from_imds():
    """
    環境メタデータサービスから IAM ロール認証情報を手動で取得する。

    このユーティリティメソッドは、boto3 を使用せずに IMDS から直接認証情報を取得します。
    IMDSv1 と IMDSv2 の両方の方式を試行します。

    Returns:
        dict: 認証情報またはエラー情報を含む辞書
    """
    result = {
        "success": False,
        "credentials": None,
        "role_name": None,
        "method_used": None,
        "error": None,
    }

    try:
        # Try IMDSv2 first
        token = get_imdsv2_token()
        headers = {}

        if token:
            headers["X-aws-ec2-metadata-token"] = token
            result["method_used"] = "IMDSv2"
        else:
            result["method_used"] = "IMDSv1"

        # Get the IAM role name
        role_response = requests.get(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            headers=headers,
            timeout=2,
        )

        if role_response.status_code != 200:
            result["error"] = (
                f"Failed to retrieve IAM role name: HTTP {role_response.status_code}"
            )
            return result

        role_name = role_response.text.strip()
        result["role_name"] = role_name

        # Get the credentials for the role
        creds_response = requests.get(
            f"http://169.254.169.254/latest/meta-data/iam/security-credentials/{role_name}",
            headers=headers,
            timeout=2,
        )

        if creds_response.status_code != 200:
            result["error"] = (
                f"Failed to retrieve credentials for role {role_name}: HTTP {creds_response.status_code}"
            )
            return result

        # Parse the credentials
        credentials = creds_response.json()

        result["success"] = True
        result["credentials"] = {
            "AccessKeyId": credentials.get("AccessKeyId"),
            "SecretAccessKey": credentials.get("SecretAccessKey"),
            "Token": credentials.get("Token"),
            "Expiration": credentials.get("Expiration"),
            "Code": credentials.get("Code"),
            "Type": credentials.get("Type"),
            "LastUpdated": credentials.get("LastUpdated"),
        }

    except RequestException as e:
        result["error"] = f"Request exception: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"

    return result


async def refresh_credentials_from_imds():
    """
    IMDS から定期的に認証情報を更新し、環境変数を更新するバックグラウンドタスク。
    これにより、EnvironmentCredentialsResolver が常に新しい認証情報を持つことが保証されます。
    """
    logger.info("認証情報更新バックグラウンドタスクを開始しています")

    while True:
        try:
            # Fetch credentials from IMDS
            imds_result = get_credentials_from_imds()

            if imds_result["success"]:
                creds = imds_result["credentials"]

                # Update environment variables
                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

                logger.info("✅ IMDS から認証情報を更新しました")

                # Parse expiration time and calculate refresh interval
                # Refresh 5 minutes before expiration
                try:
                    expiration = datetime.fromisoformat(
                        creds["Expiration"].replace("Z", "+00:00")
                    )
                    now = datetime.now(expiration.tzinfo)
                    time_until_expiration = (expiration - now).total_seconds()

                    # Refresh 5 minutes (300 seconds) before expiration, or in 1 hour if expiration is far away
                    refresh_interval = min(max(time_until_expiration - 300, 60), 3600)
                    logger.info(f"   次の更新まで {refresh_interval:.0f} 秒")
                except Exception as e:
                    logger.warning(
                        f"有効期限の解析に失敗しました。デフォルトの1時間更新を使用します: {e}"
                    )
                    refresh_interval = 3600

                # Wait until next refresh
                await asyncio.sleep(refresh_interval)
            else:
                logger.error(
                    f"IMDS からの認証情報更新に失敗しました: {imds_result['error']}"
                )
                # Retry in 5 minutes on failure
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("認証情報更新タスクがキャンセルされました")
            break
        except Exception as e:
            logger.error(f"認証情報更新タスクでエラーが発生しました: {e}", exc_info=True)
            # Retry in 5 minutes on error
            await asyncio.sleep(300)


# Create FastAPI app
app = FastAPI(title="Nova Sonic S2S WebSocket Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global credential_refresh_task

    logger.info("🚀 アプリケーションを起動しています...")
    logger.info(f"📍 AWS リージョン: {os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}")

    # Check if credentials are already in environment (local mode)
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        logger.info("✅ 環境変数から認証情報を使用しています（ローカルモード）")
        logger.info("   認証情報更新タスクは開始されません")
    else:
        # Try to fetch credentials from IMDS and start refresh task
        logger.info("🔄 ENV IMDS から認証情報を取得しています...")

        imds_result = get_credentials_from_imds()

        if imds_result["success"]:
            creds = imds_result["credentials"]

            # Set initial credentials in environment
            os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
            os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

            logger.info("✅ IMDS から初期認証情報を読み込みました")

            # Start background task to refresh credentials
            credential_refresh_task = asyncio.create_task(
                refresh_credentials_from_imds()
            )
            logger.info("🔄 認証情報更新バックグラウンドタスクを開始しました")
        else:
            logger.error(
                f"❌ IMDS からの認証情報取得に失敗しました: {imds_result['error']}"
            )
            logger.error(
                "   認証情報がないため、アプリケーションが正常に動作しない可能性があります"
            )


@app.on_event("shutdown")
async def shutdown_event():
    global credential_refresh_task

    logger.info("🛑 アプリケーションをシャットダウンしています...")

    # Cancel credential refresh task if running
    if credential_refresh_task and not credential_refresh_task.done():
        logger.info("認証情報更新タスクを停止しています...")
        credential_refresh_task.cancel()
        try:
            await credential_refresh_task
        except asyncio.CancelledError:
            pass
        logger.info("認証情報更新タスクを停止しました")


@app.get("/health")
@app.get("/")
async def health_check():
    logger.info("ヘルスチェックリクエストを受信しました")
    return JSONResponse({"status": "healthy"})


@app.get("/ping")
async def ping():
    logger.debug("Ping エンドポイントが呼び出されました")
    return JSONResponse({"status": "ok"})


@app.get("/credentials/info")
async def credential_info():
    """認証情報設定に関する情報を取得する（デバッグ用）"""
    # Determine credential source
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        credential_source = "Environment Variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)"
        mode = "local"
        note = "Using static credentials from environment variables"
    else:
        credential_source = "ENV IMDS (IMDSv2 preferred, falls back to IMDSv1)"
        mode = "ec2"
        note = "Credentials are automatically refreshed from IMDS by background task"

    return JSONResponse(
        {
            "status": "ok",
            "mode": mode,
            "credential_source": credential_source,
            "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            "note": note,
        }
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info(f"WebSocket 接続試行元: {websocket.client}")
    logger.debug(f"ヘッダー: {websocket.headers}")

    # Accept the WebSocket connection
    await websocket.accept()
    logger.info("WebSocket 接続を受け入れました")

    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    stream_manager = None
    forward_task = None

    try:
        # Main message processing loop
        while True:
            try:
                message = await websocket.receive_text()
                logger.debug("クライアントからメッセージを受信しました")

                try:
                    data = json.loads(message)

                    # Handle wrapped body format
                    if "body" in data:
                        data = json.loads(data["body"])

                    if "event" not in data:
                        logger.warning("イベントフィールドのないメッセージを受信しました")
                        continue

                    event_type = list(data["event"].keys())[0]

                    # Handle session start - create new stream manager
                    if event_type == "sessionStart":
                        logger.info("新しいセッションを開始しています")

                        # Clean up existing session if any
                        if stream_manager:
                            logger.info("既存のセッションをクリーンアップしています")
                            await stream_manager.close()
                        if forward_task and not forward_task.done():
                            forward_task.cancel()
                            try:
                                await forward_task
                            except asyncio.CancelledError:
                                pass

                        # Create a new stream manager for this connection
                        stream_manager = S2sSessionManager(
                            model_id="amazon.nova-2-sonic-v1:0", region=aws_region
                        )

                        # Initialize the Bedrock stream
                        await stream_manager.initialize_stream()
                        logger.info("ストリームの初期化に成功しました")

                        # Start a task to forward responses from Bedrock to the WebSocket
                        forward_task = asyncio.create_task(
                            forward_responses(websocket, stream_manager)
                        )

                        # Now send the sessionStart event to Bedrock
                        await stream_manager.send_raw_event(data)
                        logger.info(
                            f"SessionStart イベントを Bedrock に送信しました {json.dumps(data)}"
                        )

                        # Continue to next iteration to process next event
                        continue

                    # Handle session end - clean up resources
                    elif event_type == "sessionEnd":
                        logger.info("セッションを終了しています")

                        if stream_manager:
                            await stream_manager.close()
                            stream_manager = None
                        if forward_task and not forward_task.done():
                            forward_task.cancel()
                            try:
                                await forward_task
                            except asyncio.CancelledError:
                                pass
                            forward_task = None

                        # Continue to next iteration
                        continue

                    # Process events if we have an active stream manager
                    if stream_manager and stream_manager.is_active:
                        # Store prompt name and content names if provided
                        if event_type == "promptStart":
                            stream_manager.prompt_name = data["event"]["promptStart"][
                                "promptName"
                            ]
                        elif (
                            event_type == "contentStart"
                            and data["event"]["contentStart"].get("type") == "AUDIO"
                        ):
                            stream_manager.audio_content_name = data["event"][
                                "contentStart"
                            ]["contentName"]

                        # Handle audio input separately (queue-based processing)
                        if event_type == "audioInput":
                            prompt_name = data["event"]["audioInput"]["promptName"]
                            content_name = data["event"]["audioInput"]["contentName"]
                            audio_base64 = data["event"]["audioInput"]["content"]

                            # Add to the audio queue for async processing
                            stream_manager.add_audio_chunk(
                                prompt_name, content_name, audio_base64
                            )
                        else:
                            # Send other events directly to Bedrock
                            await stream_manager.send_raw_event(data)
                    elif event_type not in ["sessionStart", "sessionEnd"]:
                        logger.warning(
                            f"イベント {event_type} を受信しましたが、アクティブなストリームマネージャーがありません"
                        )

                except json.JSONDecodeError as e:
                    logger.error(f"WebSocket から無効な JSON を受信しました: {e}")
                    try:
                        await websocket.send_json(
                            {"type": "error", "message": "Invalid JSON format"}
                        )
                    except Exception:
                        pass
                except Exception as exp:
                    logger.error(
                        f"WebSocket メッセージの処理中にエラーが発生しました: {exp}", exc_info=True
                    )
                    try:
                        await websocket.send_json(
                            {"type": "error", "message": str(exp)}
                        )
                    except Exception:
                        pass

            except WebSocketDisconnect as e:
                logger.info(f"WebSocket 切断: {websocket.client}")
                logger.info(
                    f"切断の詳細: code={getattr(e, 'code', 'N/A')}, reason={getattr(e, 'reason', 'N/A')}"
                )
                if stream_manager and stream_manager.is_active:
                    logger.info(
                        "WebSocket 切断時に Bedrock ストリームがまだアクティブでした"
                    )
                break
            except Exception as e:
                logger.error(f"WebSocket エラー: {e}", exc_info=True)
                break

    except Exception as e:
        logger.error(f"WebSocket ハンドラエラー: {e}", exc_info=True)
        try:
            await websocket.send_json(
                {"type": "error", "message": "WebSocket handler error"}
            )
        except Exception:
            pass
    finally:
        # Clean up resources
        logger.info("WebSocket 接続リソースをクリーンアップしています")

        if stream_manager:
            await stream_manager.close()
        if forward_task and not forward_task.done():
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass

        try:
            await websocket.close()
        except Exception as e:
            logger.error(f"WebSocket を閉じる際のエラー: {e}")

        logger.info("接続を閉じました")


def split_large_event(response, max_size=16000):
    """
    content フィールドを分割して大きなイベントを小さなチャンクに分割する。
    オーディオイベントの場合、ノイズを避けるためにサンプル境界で分割されるようにする。
    送信するイベントのリストを返す。
    """
    event = json.dumps(response)
    event_size = len(event.encode("utf-8"))

    # If event is small enough, return as-is
    if event_size <= max_size:
        return [response]

    # Get event type and data
    if "event" not in response:
        return [response]

    event_type = list(response["event"].keys())[0]
    event_data = response["event"][event_type]

    # Only split events that have a 'content' field (audioOutput, textOutput, etc.)
    if "content" not in event_data:
        logger.warning(
            f"イベント {event_type} は大きい ({event_size} バイト) ですが、分割するコンテンツフィールドがありません"
        )
        return [response]

    content = event_data["content"]

    # Calculate how much content we can fit per chunk
    # Create a template event to measure overhead
    template_event = response.copy()
    template_event["event"] = {event_type: event_data.copy()}
    template_event["event"][event_type]["content"] = ""
    overhead = len(json.dumps(template_event).encode("utf-8"))

    # Calculate max content size per chunk (leave some margin)
    max_content_size = max_size - overhead - 100

    # For audio events, align to sample boundaries
    # Base64 encoding: 4 chars = 3 bytes of binary data
    # PCM 16-bit: 2 bytes per sample
    # Must align to multiples of 4 chars for valid base64 (no padding issues)
    if event_type == "audioOutput":
        # Align to 4-char boundaries for complete base64 groups
        # This ensures each chunk is valid base64 without padding issues
        alignment = 4
        max_content_size = (max_content_size // alignment) * alignment
        logger.debug(
            f"オーディオ分割: チャンクサイズを {max_content_size} 文字に揃えました (base64 境界)"
        )

    # Split content into chunks
    chunks = []
    for i in range(0, len(content), max_content_size):
        chunk_content = content[i : i + max_content_size]

        # For base64 content, ensure proper padding if needed
        if event_type == "audioOutput":
            # Each chunk should be a multiple of 4 chars (already aligned above)
            # But verify and add padding if somehow needed
            remainder = len(chunk_content) % 4
            if remainder != 0:
                # This shouldn't happen due to alignment, but just in case
                padding_needed = 4 - remainder
                chunk_content += "=" * padding_needed
                logger.warning(f"オーディオチャンクに {padding_needed} パディング文字を追加しました")

        # Create new event with chunked content
        chunk_event = response.copy()
        chunk_event["event"] = {event_type: event_data.copy()}
        chunk_event["event"][event_type]["content"] = chunk_content

        chunks.append(chunk_event)

    logger.info(
        f"{event_type} イベント ({event_size} バイト) を {len(chunks)} チャンクに分割しました"
    )
    return chunks


async def forward_responses(websocket: WebSocket, stream_manager):
    """Bedrock からのレスポンスを WebSocket クライアントに転送する"""
    try:
        while True:
            # Get next response from the output queue
            response = await stream_manager.output_queue.get()

            # Send to WebSocket
            try:
                # Check if event needs to be split
                event = json.dumps(response)
                event_size = len(event.encode("utf-8"))

                # Get event type for logging
                event_type = (
                    list(response.get("event", {}).keys())[0]
                    if "event" in response
                    else "unknown"
                )

                # Split large events
                if event_size > 10000:
                    logger.warning(
                        f"!!!! 大きな {event_type} イベントを検出しました (サイズ: {event_size} バイト) - 分割中..."
                    )
                    events_to_send = split_large_event(response, max_size=10000)
                else:
                    events_to_send = [response]

                # Send all chunks
                for idx, event_chunk in enumerate(events_to_send):
                    chunk_json = json.dumps(event_chunk)
                    chunk_size = len(chunk_json.encode("utf-8"))

                    await websocket.send_text(chunk_json)

                    if len(events_to_send) > 1:
                        logger.info(
                            f"{event_type} チャンク {idx + 1}/{len(events_to_send)} をクライアントに転送しました (サイズ: {chunk_size} バイト)"
                        )
                    else:
                        logger.info(
                            f"{event_type} をクライアントに転送しました (サイズ: {chunk_size} バイト)"
                        )

            except Exception as e:
                logger.error(f"クライアントへのレスポンス送信エラー: {e}", exc_info=True)
                # Check if it's a connection error that should break the loop
                error_str = str(e).lower()
                if "closed" in error_str or "disconnect" in error_str:
                    logger.info("WebSocket 接続が閉じられました。転送タスクを停止しています")
                    break
                # For other errors, log but continue trying
                logger.warning("エラーにもかかわらずレスポンスの転送を続行しています")
    except asyncio.CancelledError:
        logger.debug("レスポンス転送タスクがキャンセルされました")
    except Exception as e:
        logger.error(f"レスポンス転送エラー: {e}", exc_info=True)
    finally:
        logger.info("レスポンス転送タスクが終了しました")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nova Sonic S2S WebSocket Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if args.debug:
        DEBUG = True
        logging.getLogger().setLevel(logging.DEBUG)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

    logger.info(f"Nova Sonic S2S WebSocket サーバーを {host}:{port} で起動しています")

    try:
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("ユーザーによりサーバーが停止されました")
    except Exception as e:
        logger.error(f"サーバーエラー: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
