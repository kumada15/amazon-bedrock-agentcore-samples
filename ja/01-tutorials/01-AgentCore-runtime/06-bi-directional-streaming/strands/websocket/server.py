import logging
import uvicorn
import os
import asyncio
import requests
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel
from strands_tools import calculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_credential_refresh_task = None


def get_imdsv2_token():
    """セキュアなメタデータアクセス用の IMDSv2 トークンを取得する"""
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
    """EC2 IMDS から IAM ロール認証情報を取得する（IMDSv2 を優先し、IMDSv1 にフォールバック）"""
    result = {
        "success": False,
        "credentials": None,
        "role_name": None,
        "method_used": None,
        "error": None,
    }

    try:
        token = get_imdsv2_token()
        headers = {"X-aws-ec2-metadata-token": token} if token else {}
        result["method_used"] = "IMDSv2" if token else "IMDSv1"

        role_response = requests.get(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            headers=headers,
            timeout=2,
        )

        if role_response.status_code != 200:
            result["error"] = (
                f"Failed to retrieve IAM role: HTTP {role_response.status_code}"
            )
            return result

        role_name = role_response.text.strip()
        result["role_name"] = role_name

        creds_response = requests.get(
            f"http://169.254.169.254/latest/meta-data/iam/security-credentials/{role_name}",
            headers=headers,
            timeout=2,
        )

        if creds_response.status_code != 200:
            result["error"] = (
                f"Failed to retrieve credentials: HTTP {creds_response.status_code}"
            )
            return result

        credentials = creds_response.json()
        result["success"] = True
        result["credentials"] = {
            "AccessKeyId": credentials.get("AccessKeyId"),
            "SecretAccessKey": credentials.get("SecretAccessKey"),
            "Token": credentials.get("Token"),
            "Expiration": credentials.get("Expiration"),
        }

    except Exception as e:
        result["error"] = str(e)

    return result


async def refresh_credentials_from_imds():
    """IMDS から認証情報を更新するバックグラウンドタスク"""
    logger.info("認証情報更新タスクを開始しています")

    while True:
        try:
            imds_result = get_credentials_from_imds()

            if imds_result["success"]:
                creds = imds_result["credentials"]

                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

                logger.info(f"✅ 認証情報を更新しました ({imds_result['method_used']})")

                try:
                    expiration = datetime.fromisoformat(
                        creds["Expiration"].replace("Z", "+00:00")
                    )
                    now = datetime.now(expiration.tzinfo)
                    time_until_expiration = (expiration - now).total_seconds()
                    refresh_interval = min(max(time_until_expiration - 300, 60), 3600)
                    logger.info(f"   次の更新まで {refresh_interval:.0f} 秒")
                except Exception:
                    refresh_interval = 3600

                await asyncio.sleep(refresh_interval)
            else:
                logger.error(f"認証情報の更新に失敗しました: {imds_result['error']}")
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("認証情報更新タスクがキャンセルされました")
            break
        except Exception as e:
            logger.error(f"認証情報更新中のエラー: {e}")
            await asyncio.sleep(300)


app = FastAPI(title="Strands BidiAgent WebSocket Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global _credential_refresh_task

    logger.info("🚀 サーバーを起動しています...")
    logger.info(f"📍 リージョン: {os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}")

    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        logger.info("✅ 環境変数から認証情報を使用しています（ローカルモード）")
    else:
        logger.info("🔄 EC2 IMDS から認証情報を取得しています...")
        imds_result = get_credentials_from_imds()

        if imds_result["success"]:
            creds = imds_result["credentials"]
            os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
            os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

            logger.info(f"✅ 認証情報を読み込みました ({imds_result['method_used']})")

            _credential_refresh_task = asyncio.create_task(
                refresh_credentials_from_imds()
            )
            logger.info("🔄 認証情報更新タスクを開始しました")
        else:
            logger.error(f"❌ 認証情報の取得に失敗しました: {imds_result['error']}")


@app.on_event("shutdown")
async def shutdown_event():
    global _credential_refresh_task

    logger.info("🛑 シャットダウンしています...")

    if _credential_refresh_task and not _credential_refresh_task.done():
        _credential_refresh_task.cancel()
        try:
            await _credential_refresh_task
        except asyncio.CancelledError:
            pass


@app.get("/ping")
async def ping():
    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health_check():
    return JSONResponse({"status": "healthy"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    voice_id = websocket.query_params.get("voice_id", "matthew")
    logger.info(f"接続元: {websocket.client}, ボイス: {voice_id}")

    try:
        model = BidiNovaSonicModel(
            region="us-east-1",
            model_id="amazon.nova-sonic-v1:0",
            provider_config={
                "audio": {
                    "input_sample_rate": 16000,
                    "output_sample_rate": 16000,
                    "voice": voice_id,
                }
            },
            tools=[calculator],
        )

        agent = BidiAgent(
            model=model,
            tools=[calculator],
            system_prompt="あなたは計算機ツールにアクセスできる親切なアシスタントです。",
        )

        await agent.run(inputs=[websocket.receive_json], outputs=[websocket.send_json])

    except WebSocketDisconnect:
        logger.info("クライアントが切断しました")
    except Exception as e:
        logger.error(f"エラー: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        logger.info("接続を閉じました")


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

    uvicorn.run(app, host=host, port=port)
