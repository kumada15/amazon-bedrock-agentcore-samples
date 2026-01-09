import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.responses import JSONResponse

# ロギングを設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/ping")
async def ping():
    logger.debug("Ping エンドポイントが呼び出されました")
    return JSONResponse({"status": "ok"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"Agent Runtime WebSocket 接続が確立されました: {websocket.client}")
    
    try:
        while True:
            try:
                # テキストメッセージの受信を試行
                message = await websocket.receive_text()
                logger.info(f"Agent Runtime がテキストを受信しました: {message}")
                await websocket.send_text(message)
            except Exception:
                # バイナリメッセージの受信を試行
                try:
                    data = await websocket.receive_bytes()
                    logger.info(f"Agent Runtime がバイナリを受信しました: {len(data)} バイト")
                    await websocket.send_bytes(data)
                except Exception:
                    # どちらも失敗した場合はループを終了
                    break
            
    except WebSocketDisconnect:
        logger.info(f"Agent Runtime WebSocket 接続が閉じられました: {websocket.client}")
    except Exception as e:
        logger.error(f"Agent Runtime WebSocket エラー: {e}")
        try:
            await websocket.close()
        except Exception:
            pass

async def run_server(host: str, port: int):
    """指定されたホストとポートでサーバーを実行する"""
    config = uvicorn.Config(
        app, 
        host=host, 
        port=port, 
        log_level="info",
        ws="websockets"  # websockets ライブラリを使用
    )
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    """Agent Runtime WebSocket エコーサーバーを両方のポートで実行"""
    host = os.environ.get("AGENT_RUNTIME_HOST", "0.0.0.0")
    
    logger.info(f"Agent Runtime WebSocket エコーサーバーを {host}:8080 および {host}:8081 で起動しています")
    
    # 両方のポートでサーバーを同時に実行
    await asyncio.gather(
        run_server(host, 8080)
    )

if __name__ == "__main__":
    asyncio.run(main())

