"""
デバイス管理システム - DynamoDB テーブルモデルと初期化

このモジュールは、デバイス管理システム用の DynamoDB テーブルスキーマを定義し、
初期化関数を提供します。適切なキースキーマ、インデックス、およびプロビジョニングされた
スループット設定を持つ5つの DynamoDB テーブルを作成・管理します。

このモジュールが管理するもの:
- 全5つの DynamoDB テーブルのテーブルスキーマ定義
- プライマリキーとソートキーの設定
- 効率的なクエリのための Global Secondary Index（GSI）
- プロビジョニングされたスループット設定
- テーブルの作成と初期化
- datetime と Decimal 処理のヘルパー関数

DynamoDB テーブル:

    1. Devices テーブル:
       - プライマリキー: device_id（String、HASH）
       - 属性: name、model、firmware_version、connection_status、
              ip_address、mac_address、last_connected
       - 目的: デバイスインベントリとステータス情報の保存

    2. DeviceSettings テーブル:
       - プライマリキー: device_id（String、HASH）
       - ソートキー: setting_key（String、RANGE）
       - 属性: setting_value、last_updated
       - 目的: デバイス設定（キーバリューペア）の保存

    3. WifiNetworks テーブル:
       - プライマリキー: device_id（String、HASH）
       - ソートキー: network_id（String、RANGE）
       - 属性: ssid、security_type、enabled、channel、
              signal_strength、last_updated
       - 目的: デバイスごとの WiFi ネットワーク設定の保存

    4. Users テーブル:
       - プライマリキー: user_id（String、HASH）
       - GSI 1: EmailIndex（email を HASH として）
       - GSI 2: UsernameIndex（username を HASH として）
       - 属性: username、email、first_name、last_name、role、
              created_at、last_login
       - 目的: ユーザーアカウントとプロファイルの保存

    5. UserActivities テーブル:
       - プライマリキー: user_id（String、HASH）
       - ソートキー: timestamp（String、RANGE）
       - GSI: ActivityTypeIndex（activity_type を HASH、timestamp を RANGE として）
       - 属性: activity_type、description、ip_address
       - 目的: ユーザーアクティビティログと監査証跡の保存

主な機能:
    - 効率的なクエリのための複合プライマリキー
    - 代替アクセスパターンのための Global Secondary Index
    - プロビジョニングされたスループット（テーブルは 5 RCU/5 WCU、GSI は 2 RCU/2 WCU）
    - アクティブ状態になるまで待機する自動テーブル作成
    - 冪等な初期化（既存テーブルはスキップ）
    - データ型変換のヘルパー関数

Global Secondary Index:

    EmailIndex（Users テーブル）:
    - パーティションキー: email
    - 目的: メールアドレスでユーザーをクエリ
    - ユースケース: ログイン、メールでのユーザー検索

    UsernameIndex（Users テーブル）:
    - パーティションキー: username
    - 目的: ユーザー名でユーザーをクエリ
    - ユースケース: ユーザー検索、ユーザー名の検証

    ActivityTypeIndex（UserActivities テーブル）:
    - パーティションキー: activity_type
    - ソートキー: timestamp
    - 目的: タイプと時間範囲でアクティビティをクエリ
    - ユースケース: アクティビティレポート、セキュリティ監査

ヘルパー関数:

    datetime_to_iso(dt):
    - datetime オブジェクトを ISO 8601 文字列に変換
    - DynamoDB の datetime 保存要件に対応
    - datetime でない場合は元の値を返す

    json_dumps(obj):
    - Decimal 処理付きの JSON シリアライゼーション
    - DynamoDB Decimal 型用に DecimalEncoder を使用
    - Decimal を float に変換して JSON 互換性を確保

    get_dynamodb_resource():
    - boto3 DynamoDB リソースを作成
    - us-west-2 リージョン用に設定
    - テーブル操作用のリソースを返す

テーブル作成関数:

    create_devices_table():
    - device_id をプライマリキーとして Devices テーブルを作成
    - テーブルオブジェクトを返す

    create_device_settings_table():
    - 複合キーで DeviceSettings テーブルを作成
    - device_id（HASH）+ setting_key（RANGE）
    - テーブルオブジェクトを返す

    create_wifi_networks_table():
    - 複合キーで WifiNetworks テーブルを作成
    - device_id（HASH）+ network_id（RANGE）
    - テーブルオブジェクトを返す

    create_users_table():
    - user_id をプライマリキーとして Users テーブルを作成
    - EmailIndex と UsernameIndex の GSI を含む
    - テーブルオブジェクトを返す

    create_user_activities_table():
    - 複合キーで UserActivities テーブルを作成
    - user_id（HASH）+ timestamp（RANGE）
    - ActivityTypeIndex GSI を含む
    - テーブルオブジェクトを返す

    init_db():
    - 存在しないテーブルを全て初期化
    - テーブルがアクティブになるまで待機
    - 成功時は True、失敗時は False を返す
    - 冪等（複数回実行しても安全）

環境変数:
    AWS_REGION: DynamoDB 用の AWS リージョン（デフォルトは us-west-2）

使用方法:
    テーブルを初期化:
    >>> from dynamodb_models import init_db
    >>> init_db()

    スクリプトとして実行:
    >>> python dynamodb_models.py

    ヘルパー関数を使用:
    >>> from dynamodb_models import datetime_to_iso, json_dumps
    >>> iso_string = datetime_to_iso(datetime.now())
    >>> json_string = json_dumps({"value": Decimal("123.45")})

出力:
    テーブル Devices を作成中...
    テーブル DeviceSettings を作成中...
    テーブル WifiNetworks を作成中...
    テーブル Users を作成中...
    テーブル UserActivities を作成中...
    テーブルを作成しました: Devices, DeviceSettings, WifiNetworks, Users, UserActivities
    DynamoDB テーブルが正常に初期化されました。

プロビジョニングされたスループット:
    - テーブル: 5 Read Capacity Units、5 Write Capacity Units
    - GSI: 2 Read Capacity Units、2 Write Capacity Units
    - 開発とテストに適している
    - 本番環境ではオンデマンド課金を検討

データ型:
    - 文字列: device_id、setting_key、ssid、email など
    - 数値: Decimal として保存（DynamoDB 要件）
    - ブール値: enabled ステータス
    - タイムスタンプ: ISO 8601 文字列（YYYY-MM-DDTHH:MM:SS）

注意事項:
    - 一貫性のため常に us-west-2 リージョンを使用
    - テーブルはプロビジョニングされたキャパシティモードで作成
    - GSI により代替キーでの効率的なクエリが可能
    - テーブル作成完了まで待機してから戻る
    - 既存のテーブルはスキップ（エラーなし）
    - DynamoDB 用の適切な IAM 権限が必要
"""
import boto3
import datetime
from decimal import Decimal
import json

# DynamoDB 接続の設定
# 常に us-west-2 の AWS DynamoDB を使用
aws_region = 'us-west-2'

# DynamoDB リソースの初期化
def get_dynamodb_resource():
    """環境に基づいて DynamoDB リソースを取得します"""
    return boto3.resource('dynamodb', region_name=aws_region)

# テーブル名の定義
DEVICES_TABLE = 'Devices'
DEVICE_SETTINGS_TABLE = 'DeviceSettings'
WIFI_NETWORKS_TABLE = 'WifiNetworks'
USERS_TABLE = 'Users'
USER_ACTIVITIES_TABLE = 'UserActivities'

# datetime を ISO 形式文字列に変換するヘルパー関数
def datetime_to_iso(dt):
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return dt

# DynamoDB 用の Decimal シリアライズを処理するヘルパー関数
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def json_dumps(obj):
    return json.dumps(obj, cls=DecimalEncoder)

# テーブル作成関数
def create_devices_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=DEVICES_TABLE,
        KeySchema=[
            {'AttributeName': 'device_id', 'KeyType': 'HASH'}  # Partition key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'device_id', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_device_settings_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=DEVICE_SETTINGS_TABLE,
        KeySchema=[
            {'AttributeName': 'device_id', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'setting_key', 'KeyType': 'RANGE'}  # Sort key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'device_id', 'AttributeType': 'S'},
            {'AttributeName': 'setting_key', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_wifi_networks_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=WIFI_NETWORKS_TABLE,
        KeySchema=[
            {'AttributeName': 'device_id', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'network_id', 'KeyType': 'RANGE'}  # Sort key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'device_id', 'AttributeType': 'S'},
            {'AttributeName': 'network_id', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_users_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=USERS_TABLE,
        KeySchema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'}  # Partition key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'email', 'AttributeType': 'S'},
            {'AttributeName': 'username', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'EmailIndex',
                'KeySchema': [
                    {'AttributeName': 'email', 'KeyType': 'HASH'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2}
            },
            {
                'IndexName': 'UsernameIndex',
                'KeySchema': [
                    {'AttributeName': 'username', 'KeyType': 'HASH'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2}
            }
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

def create_user_activities_table():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.create_table(
        TableName=USER_ACTIVITIES_TABLE,
        KeySchema=[
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}  # Sort key
        ],
        AttributeDefinitions=[
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'S'},
            {'AttributeName': 'activity_type', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'ActivityTypeIndex',
                'KeySchema': [
                    {'AttributeName': 'activity_type', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2}
            }
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    return table

# すべてのテーブルを初期化
def init_db():
    """存在しない場合は DynamoDB テーブルを初期化します"""
    try:
        dynamodb = get_dynamodb_resource()
        # テーブルが存在するか確認
        existing_tables = [table.name for table in dynamodb.tables.all()]
        
        tables_to_create = [
            (DEVICES_TABLE, create_devices_table),
            (DEVICE_SETTINGS_TABLE, create_device_settings_table),
            (WIFI_NETWORKS_TABLE, create_wifi_networks_table),
            (USERS_TABLE, create_users_table),
            (USER_ACTIVITIES_TABLE, create_user_activities_table)
        ]
        
        created_tables = []
        for table_name, create_func in tables_to_create:
            if table_name not in existing_tables:
                table = create_func()
                print(f"テーブル {table_name} を作成中...")
                table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
                created_tables.append(table_name)
        
        if created_tables:
            print(f"テーブルを作成しました: {', '.join(created_tables)}")
        else:
            print("すべてのテーブルは既に存在します")
            
        return True
    except Exception as e:
        print(f"データベース初期化エラー: {str(e)}")
        return False

if __name__ == "__main__":
    init_db()
    print("DynamoDB テーブルが正常に初期化されました。")
