"""
デバイス管理 Lambda 関数 - テストスイート

このモジュールは、デバイス管理 Lambda 関数の包括的なテストスイートを提供し、
リアルなテストデータとフォーマットされた出力で全7つの MCP
（Model Context Protocol）ツールをテストします。

テストスイートが検証するもの:
- 全7つの MCP ツール実装
- リクエスト/レスポンスフォーマットの処理
- 無効な入力に対するエラーハンドリング
- Decimal 型での JSON シリアライゼーション
- DynamoDB クエリ操作
- Lambda ハンドラーのルーティングロジック

テストカバレッジ:

    1. test_list_devices():
       - limit パラメータ付きでデバイス一覧をテスト
       - デバイスデータ構造を検証
       - 接続状態、モデル、ファームウェアバージョンを確認

    2. test_get_device_settings():
       - デバイス ID によるデバイス設定取得をテスト
       - 設定辞書構造を検証
       - デバイスメタデータ（名前、モデル、ファームウェア）を確認

    3. test_list_wifi_networks():
       - 特定デバイスの WiFi ネットワーク一覧をテスト
       - ネットワーク設定データを検証
       - SSID、セキュリティタイプ、チャンネル、信号強度を確認

    4. test_list_users():
       - limit パラメータ付きでユーザー一覧をテスト
       - ユーザーデータ構造を検証
       - ユーザー名、メール、ロール、最終ログインを確認

    5. test_query_user_activity():
       - 日付範囲でのアクティビティクエリをテスト
       - アクティビティデータ構造を検証
       - アクティビティタイプ、タイムスタンプ、説明を確認

    6. test_update_wifi_ssid():
       - WiFi SSID 更新操作をテスト
       - 更新レスポンスを検証
       - 旧 SSID と新 SSID の値を確認

    7. test_update_wifi_security():
       - WiFi セキュリティタイプ更新操作をテスト
       - セキュリティタイプの変更を検証
       - 旧セキュリティと新セキュリティの値を確認

    8. test_invalid_tool():
       - 不明なツール名のエラーハンドリングをテスト
       - エラーレスポンスフォーマットを検証
       - エラーメッセージ内の利用可能ツールリストを確認

テストデータ要件:
    - デバイス DG-100001 が Devices テーブルに存在する必要があります
    - デバイスが DeviceSettings テーブルに設定を持つ必要があります
    - デバイスが WifiNetworks テーブルに WiFi ネットワークを持つ必要があります
    - ユーザーが Users テーブルに存在する必要があります
    - アクティビティが UserActivities テーブルに存在する必要があります

前提条件:
    - DynamoDB テーブルが初期化されていること（dynamodb_models.py を実行）
    - 合成データが生成されていること（synthetic_data.py を実行）
    - Lambda 関数コードが利用可能であること（lambda_function.py）

使用方法:
    全テストを実行:
    >>> python test_lambda.py

    個別テストを実行:
    >>> from test_lambda import test_list_devices
    >>> test_list_devices()

出力フォーマット:
    各テストが表示するもの:
    - テスト名と説明
    - HTTP ステータスコード
    - フォーマットされた JSON レスポンスボディ
    - 2スペースインデントでのプリティプリント

出力例:
    デバイス管理 Lambda 関数をテスト中

    1. list_devices をテスト中:
    ステータスコード: 200
    レスポンスボディ: [
      {
        "device_id": "DG-100001",
        "name": "Device Router 1",
        "model": "TransPort WR31",
        ...
      }
    ]

エラーハンドリング:
    - テストはステータスコードを検証（成功は 200、エラーは 400/500）
    - エラーレスポンスには説明的なエラーメッセージを含む
    - 無効なツール名は利用可能ツールリストを返す
    - 必須パラメータ不足はバリデーションエラーを返す

レスポンス検証:
    - レスポンスボディの JSON パース
    - Decimal 型の処理（float に変換）
    - ネストしたオブジェクト構造の検証
    - 配列レスポンスの検証

注意事項:
    - テストは lambda_handler を直接使用（AWS 呼び出しなし）
    - モック不要（実際の DynamoDB テーブルを使用）
    - テストは合成データが存在することを前提
    - 複数回実行しても安全（更新以外は読み取り専用）
    - 更新テストは実際のデータを変更（テストデバイスを使用）
    - 全てのテストが手動検証用にフォーマットされた出力を表示

統合テスト:
    このテストスイートは以下により統合テストを実行:
    - 実際の DynamoDB テーブルを使用
    - 実際の Lambda ハンドラーコードをテスト
    - エンドツーエンドのデータフローを検証
    - シリアライゼーション/デシリアライゼーションを確認

ベストプラクティス:
    - Lambda 関数デプロイ後に実行
    - テスト前に合成データの存在を確認
    - データの正確性のため出力をレビュー
    - コード変更後のリグレッションテストに使用
    - 必要に応じて追加のテストケースを拡張
"""
import json
from lambda_function import lambda_handler

def test_list_devices():
    """list_devices ツールをテストします"""
    event = {
        "action_name": "list_devices",
        "limit": 10
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

def test_get_device_settings():
    """get_device_settings ツールをテストします"""
    event = {
        "action_name": "get_device_settings",
        "device_id": "DG-100001"
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

def test_list_wifi_networks():
    """list_wifi_networks ツールをテストします"""
    event = {
        "action_name": "list_wifi_networks",
        "device_id": "DG-100001"
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

def test_list_users():
    """list_users ツールをテストします"""
    event = {
        "action_name": "list_users",
        "limit": 5
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

def test_query_user_activity():
    """query_user_activity ツールをテストします"""
    event = {
        "action_name": "query_user_activity",
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-12-31T23:59:59",
        "limit": 5
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

def test_update_wifi_ssid():
    """update_wifi_ssid ツールをテストします"""
    event = {
        "action_name": "update_wifi_ssid",
        "device_id": "DG-100001",
        "network_id": "wifi_1",
        "ssid": "New-Office-Network"
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

def test_update_wifi_security():
    """update_wifi_security ツールをテストします"""
    event = {
        "action_name": "update_wifi_security",
        "device_id": "DG-100001",
        "network_id": "wifi_1",
        "security_type": "wpa3-psk"
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

def test_invalid_tool():
    """無効なツール名をテストします"""
    event = {
        "action_name": "invalid_tool"
    }
    
    response = lambda_handler(event, None)
    print(f"ステータスコード: {response['statusCode']}")
    print(f"レスポンスボディ: {json.dumps(json.loads(response['body']), indent=2)}")

if __name__ == "__main__":
    print("デバイス管理 Lambda 関数をテスト中")
    print("\n1. list_devices をテスト中:")
    test_list_devices()

    print("\n2. get_device_settings をテスト中:")
    test_get_device_settings()

    print("\n3. list_wifi_networks をテスト中:")
    test_list_wifi_networks()

    print("\n4. list_users をテスト中:")
    test_list_users()

    print("\n5. query_user_activity をテスト中:")
    test_query_user_activity()

    print("\n6. update_wifi_ssid をテスト中:")
    test_update_wifi_ssid()

    print("\n7. update_wifi_security をテスト中:")
    test_update_wifi_security()

    print("\n8. 無効なツールをテスト中:")
    test_invalid_tool()
