"""
Visa プロキシサーバー用 Lambda ハンドラー

Mangum アダプターを使用して Flask アプリケーションを AWS Lambda 互換にラップする。
"""

import json
import traceback

# モジュールレベルで変数を初期化
_handler = None
_init_error = None

# Flask アプリをインポートして初期化を試行
try:
    from mangum import Mangum
    from asgiref.wsgi import WsgiToAsgi
    from server import app

    # Mangum 互換性のため Flask WSGI アプリを ASGI に変換
    asgi_app = WsgiToAsgi(app)

    # ASGI アプリを Mangum でラップして Lambda ハンドラーを作成
    _handler = Mangum(asgi_app, lifespan="off")
    print("✅ Lambdaハンドラーの初期化に成功しました")

except Exception as e:
    _init_error = str(e)
    print(f"❌ ハンドラー読み込み時の致命的エラー: {_init_error}")
    print(traceback.format_exc())


def handler(event, context):
    """
    エラーキャッチと CORS サポート付きの Lambda ハンドラー
    Lambda が見つけられるようモジュールレベルで定義する必要がある
    """
    # 初期化が失敗したかチェック
    if _handler is None:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
            "body": json.dumps(
                {
                    "error": "Lambda initialization failed",
                    "message": _init_error or "Unknown initialization error",
                }
            ),
        }

    # 通常のリクエスト処理
    try:
        print(f"Lambdaがイベントで呼び出されました: {json.dumps(event)}")
        response = _handler(event, context)

        # レスポンスに CORS ヘッダーが存在することを確認
        if "headers" not in response:
            response["headers"] = {}

        # CORS ヘッダーがまだ存在しない場合は追加（Flask-CORS が追加するはず）
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
        for header, value in cors_headers.items():
            if header not in response["headers"]:
                response["headers"][header] = value

        print(f"Lambdaレスポンス: {json.dumps(response)}")
        return response

    except Exception as e:
        print(f"Lambdaハンドラーでエラー発生: {str(e)}")
        print(traceback.format_exc())

        # CORS ヘッダー付きでエラーレスポンスを返す
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
            "body": json.dumps({"error": "Internal server error", "message": str(e)}),
        }
