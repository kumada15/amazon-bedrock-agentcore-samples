#!/usr/bin/env python3
import asyncio
import websockets
import sys
import json
import argparse
import logging
import os

# Import from root-level websocket_helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from websocket_helpers import prepare_connection

logging.basicConfig(level=logging.DEBUG)
websockets_logger = logging.getLogger('websockets')
websockets_logger.setLevel(logging.DEBUG)

async def test_websocket(runtime_arn, session_id, auth_type='headers'):
    uri, headers = prepare_connection(runtime_arn, auth_type, session_id)

    try:
        async with websockets.connect(uri, additional_headers=headers, open_timeout=130, ping_interval=20, ping_timeout=10) as websocket:
            print("WebSocket接続完了")

            test_message = {"msg": "Hello, World! Echo Test"}
            await websocket.send(json.dumps(test_message))
            print(f"送信: {test_message}")

            response = await websocket.recv()
            print(f"受信: {response}")

            if json.loads(response) == test_message:
                print("エコーテスト成功")
                return True
            else:
                print("エコーテスト失敗")
                return False

    except websockets.exceptions.InvalidStatus as e:
        # https://websockets.readthedocs.io/en/stable/reference/exceptions.html#websockets.exceptions.InvalidStatus
        print(f"WebSocketハンドシェイクが失敗しました。ステータスコード: {e.response.status_code}")
        print(f"レスポンスヘッダー: {e.response.headers}")
        print(f"レスポンスボディ: {e.response.body.decode()}")
        return False
    except Exception as e:
        print("エラー: " + str(e))
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='WebSocket echo client')
    parser.add_argument('--runtime-arn', required=True, help='Runtime ARN for the WebSocket connection')
    parser.add_argument('--session-id', help='Session ID (auto-generated if not provided)')
    parser.add_argument('--auth-type', choices=['headers', 'query', 'oauth'], default='headers', 
                       help='Authentication type: headers (SigV4 headers), query (SigV4 query parameters), or oauth (Bearer token)')
    args = parser.parse_args()
    
    success = asyncio.run(test_websocket(args.runtime_arn, args.session_id, args.auth_type))
    sys.exit(0 if success else 1)
