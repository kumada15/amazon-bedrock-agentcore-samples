"""
デバイス管理システム - AWS Lambda 関数

このモジュールは、デバイス管理システムのコアバックエンド機能を
AWS Lambda 関数として実装します。Amazon DynamoDB 操作を通じて
IoT デバイス、WiFi ネットワーク、ユーザー、およびアクティビティを
管理するための MCP（Model Context Protocol）ツールを提供します。

Lambda 関数は全てのデバイス管理操作の実行エンジンとして機能し、
Amazon Bedrock AgentCore Gateway からリクエストを受信し、
MCP プロトコル仕様に従ってフォーマットされたレスポンスを返します。

実装されている MCP ツール:
    - list_devices: ステータスと設定を含む全デバイスを取得
    - get_device_settings: 特定デバイスの詳細設定を取得
    - list_wifi_networks: デバイスに設定された WiFi ネットワークを一覧表示
    - list_users: システム内の全ユーザーを取得
    - query_user_activity: 時間範囲内のユーザーアクティビティをクエリ
    - update_wifi_ssid: WiFi ネットワークの SSID を更新
    - update_wifi_security: WiFi ネットワークのセキュリティタイプを更新

DynamoDB テーブル:
    - Devices: デバイスインベントリとステータス情報
    - DeviceSettings: デバイス設定
    - WifiNetworks: デバイスごとの WiFi ネットワーク設定
    - Users: ユーザーアカウントとプロファイル
    - UserActivities: ユーザーアクティビティログと監査証跡

環境変数:
    AWS_REGION: DynamoDB アクセス用の AWS リージョン（デフォルトは us-west-2）

エラーハンドリング:
    全ての関数は、デバッグとユーザーフィードバック用に適切な HTTP ステータスコード
    と説明的なエラーメッセージを含む標準化されたエラーレスポンスを返します。

Lambda イベントの例:
    {
        "tool_name": "list_devices",
        "parameters": {}
    }

レスポンスの例:
    {
        "statusCode": 200,
        "body": [{"device_id": "DG-001", "name": "Device 1", ...}]
    }
"""
import json
import datetime
import logging
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

# ロギングの設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def datetime_to_iso(dt):
    """
    datetime オブジェクトを ISO 形式の文字列に変換します。

    Args:
        dt: datetime オブジェクトまたは他の値

    Returns:
        str: 入力が datetime の場合は ISO 形式の datetime 文字列、それ以外は元の値
    """
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return dt


class DecimalEncoder(json.JSONEncoder):
    """
    DynamoDB Decimal 型を処理するためのカスタム JSON エンコーダー。

    DynamoDB は数値をデフォルトでは JSON シリアライズ可能ではない
    Decimal オブジェクトとして返します。このエンコーダーは Decimal
    オブジェクトを JSON シリアライゼーション用に float に変換します。
    """

    def default(self, o):
        """
        Decimal オブジェクト用のデフォルト JSON エンコーディングをオーバーライドします。

        Args:
            o: エンコードするオブジェクト

        Returns:
            float: オブジェクトが Decimal の場合は float として返す
            Any: それ以外はデフォルトの JSON エンコーディングを使用
        """
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


def json_dumps(obj):
    """
    Decimal 処理付きでオブジェクトを JSON シリアライズします。

    Args:
        obj: シリアライズするオブジェクト

    Returns:
        str: Decimal オブジェクトが float に変換された JSON 文字列
    """
    return json.dumps(obj, cls=DecimalEncoder)


def get_dynamodb_resource():
    """
    データベース操作用の DynamoDB リソースを初期化して返します。

    Returns:
        boto3.resource: us-west-2 リージョン用に設定された DynamoDB リソース

    Note:
        デプロイ間の一貫性のため常に us-west-2 リージョンを使用します。
        Lambda 実行ロールに適切な DynamoDB 権限があることを前提としています。
    """
    aws_region = 'us-west-2'
    return boto3.resource('dynamodb', region_name=aws_region)

# テーブル名の定義
DEVICES_TABLE = 'Devices'
DEVICE_SETTINGS_TABLE = 'DeviceSettings'
WIFI_NETWORKS_TABLE = 'WifiNetworks'
USERS_TABLE = 'Users'
USER_ACTIVITIES_TABLE = 'UserActivities'

# デバイス操作
def get_device(device_id):
    """ID でデバイスを取得します"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(DEVICES_TABLE)
    response = table.get_item(Key={'device_id': device_id})
    return response.get('Item')

def list_devices(limit=100):
    """全てのデバイスを一覧表示します"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(DEVICES_TABLE)
    response = table.scan(Limit=limit)
    return response.get('Items', [])

# デバイス設定操作
def get_device_setting(device_id, setting_key):
    """特定のデバイス設定を取得します"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(DEVICE_SETTINGS_TABLE)
    response = table.get_item(Key={
        'device_id': device_id,
        'setting_key': setting_key
    })
    return response.get('Item')

def list_device_settings(device_id):
    """デバイスの全設定を一覧表示します"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(DEVICE_SETTINGS_TABLE)
    response = table.query(
        KeyConditionExpression=Key('device_id').eq(device_id)
    )
    return response.get('Items', [])

# WiFi ネットワーク操作
def list_wifi_networks(device_id):
    """デバイスの全 WiFi ネットワークを一覧表示します"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(WIFI_NETWORKS_TABLE)
    response = table.query(
        KeyConditionExpression=Key('device_id').eq(device_id)
    )
    return response.get('Items', [])

def update_wifi_network(device_id, network_id, update_data):
    """WiFi ネットワークを更新します"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(WIFI_NETWORKS_TABLE)
    
    # datetime オブジェクトを ISO 形式文字列に変換
    if 'last_updated' in update_data and update_data['last_updated']:
        update_data['last_updated'] = datetime_to_iso(update_data['last_updated'])
    else:
        update_data['last_updated'] = datetime_to_iso(datetime.datetime.utcnow())

    # DynamoDB 用に float を Decimal に変換
    if 'signal_strength' in update_data and update_data['signal_strength'] is not None:
        update_data['signal_strength'] = Decimal(str(update_data['signal_strength']))
    
    # 更新式を構築
    update_expression = "SET "
    expression_attribute_values = {}
    expression_attribute_names = {}
    
    for key, value in update_data.items():
        if key not in ['device_id', 'network_id']:  # Skip the primary keys
            update_expression += f"#{key} = :{key}, "
            expression_attribute_values[f":{key}"] = value
            expression_attribute_names[f"#{key}"] = key
    
    # 末尾のカンマとスペースを削除
    update_expression = update_expression[:-2]
    
    response = table.update_item(
        Key={'device_id': device_id, 'network_id': network_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ExpressionAttributeNames=expression_attribute_names,
        ReturnValues="ALL_NEW"
    )
    
    return response.get('Attributes')

def update_wifi_ssid(device_id, network_id, ssid):
    """WiFi ネットワークの SSID を更新します"""
    return update_wifi_network(device_id, network_id, {'ssid': ssid})

def update_wifi_security(device_id, network_id, security_type):
    """WiFi ネットワークのセキュリティタイプを更新します"""
    return update_wifi_network(device_id, network_id, {'security_type': security_type})

# ユーザー操作
def list_users(limit=100):
    """全てのユーザーを一覧表示します"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USERS_TABLE)
    response = table.scan(Limit=limit)
    return response.get('Items', [])

# ユーザーアクティビティ操作
def query_user_activity(start_date, end_date, user_id=None, activity_type=None, limit=100):
    """期間内のユーザーアクティビティをクエリします"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_ACTIVITIES_TABLE)
    
    # datetime オブジェクトを ISO 形式文字列に変換
    if isinstance(start_date, datetime.datetime):
        start_date = datetime_to_iso(start_date)

    if isinstance(end_date, datetime.datetime):
        end_date = datetime_to_iso(end_date)

    if user_id:
        # user_id と時間範囲でクエリ
        key_condition = Key('user_id').eq(user_id) & Key('timestamp').between(start_date, end_date)
        
        filter_expression = None
        if activity_type:
            filter_expression = Attr('activity_type').eq(activity_type)
        
        if filter_expression:
            response = table.query(
                KeyConditionExpression=key_condition,
                FilterExpression=filter_expression,
                Limit=limit
            )
        else:
            response = table.query(
                KeyConditionExpression=key_condition,
                Limit=limit
            )
    elif activity_type:
        # GSI を使用して activity_type と時間範囲でクエリ
        response = table.query(
            IndexName='ActivityTypeIndex',
            KeyConditionExpression=Key('activity_type').eq(activity_type) & Key('timestamp').between(start_date, end_date),
            Limit=limit
        )
    else:
        # 時間範囲フィルターでスキャン
        response = table.scan(
            FilterExpression=Attr('timestamp').between(start_date, end_date),
            Limit=limit
        )
    
    return response.get('Items', [])

# MCP Tool implementations
def tool_get_device_settings(device_id):
    """
    Device API からデバイスの設定を取得します

    Args:
        device_id: 設定を取得するデバイスの ID

    Returns:
        デバイス設定情報
    """
    try:
        device = get_device(device_id)
        
        if not device:
            return {"error": f"Device not found: {device_id}"}
        
        settings = list_device_settings(device_id)
        
        result = {
            "device_id": device["device_id"],
            "device_name": device["name"],
            "model": device["model"],
            "firmware_version": device["firmware_version"],
            "connection_status": device["connection_status"],
            "settings": {}
        }
        
        for setting in settings:
            result["settings"][setting["setting_key"]] = setting["setting_value"]
        
        return result
    except Exception as e:
        logger.error(f"get_device_settings でエラーが発生しました: {str(e)}")
        return {"error": str(e)}

def tool_list_devices(limit=25):
    """
    デバイスリモート管理システムのデバイスを一覧表示します

    Args:
        limit: 返すデバイスの最大数（デフォルト: 25）

    Returns:
        詳細情報を含むデバイスのリスト
    """
    try:
        devices = list_devices(limit)
        return devices
    except Exception as e:
        logger.error(f"list_devices でエラーが発生しました: {str(e)}")
        return {"error": str(e)}

def tool_list_wifi_networks(device_id):
    """
    特定のデバイスの全 WiFi ネットワークを一覧表示します

    Args:
        device_id: WiFi ネットワークを取得するデバイスの ID

    Returns:
        詳細情報を含む WiFi ネットワークのリスト
    """
    try:
        device = get_device(device_id)
        
        if not device:
            return {"error": f"Device not found: {device_id}"}
        
        networks = list_wifi_networks(device_id)
        
        return {
            "device_id": device["device_id"],
            "device_name": device["name"],
            "wifi_networks": networks
        }
    except Exception as e:
        logger.error(f"list_wifi_networks でエラーが発生しました: {str(e)}")
        return {"error": str(e)}

def tool_list_users(limit=100):
    """
    Device API からアカウント内のユーザーを一覧表示します

    Args:
        limit: 返すユーザーの最大数（デフォルト: 100）

    Returns:
        ユーザーのリスト
    """
    try:
        users = list_users(limit)
        return users
    except Exception as e:
        logger.error(f"list_users でエラーが発生しました: {str(e)}")
        return {"error": str(e)}

def tool_query_user_activity(start_date, end_date, user_id=None, activity_type=None, limit=100):
    """
    期間内のユーザーアクティビティをクエリします

    Args:
        start_date: ISO 形式の開始日（YYYY-MM-DDTHH:MM:SS）
        end_date: ISO 形式の終了日（YYYY-MM-DDTHH:MM:SS）
        user_id: アクティビティをフィルタリングするオプションのユーザー ID
        activity_type: フィルタリングするオプションのアクティビティタイプ
        limit: 返すアクティビティの最大数（デフォルト: 100）

    Returns:
        ユーザーアクティビティのリスト
    """
    try:
        activities = query_user_activity(start_date, end_date, user_id, activity_type, limit)
        return activities
    except Exception as e:
        logger.error(f"query_user_activity でエラーが発生しました: {str(e)}")
        return {"error": str(e)}

def tool_update_wifi_ssid(device_id, network_id, ssid):
    """
    デバイス上の WiFi ネットワークの SSID を更新します

    Args:
        device_id: デバイスの ID
        network_id: WiFi ネットワークの ID
        ssid: WiFi ネットワークの新しい SSID

    Returns:
        SSID 更新操作の結果
    """
    try:
        # SSID の長さを検証（1〜32文字）
        if len(ssid) < 1 or len(ssid) > 32:
            return {"error": "SSID must be between 1 and 32 characters"}
        
        result = update_wifi_ssid(device_id, network_id, ssid)
        return result
    except Exception as e:
        logger.error(f"update_wifi_ssid でエラーが発生しました: {str(e)}")
        return {"error": str(e)}

def tool_update_wifi_security(device_id, network_id, security_type):
    """
    デバイス上の WiFi ネットワークのセキュリティタイプを更新します

    Args:
        device_id: デバイスの ID
        network_id: WiFi ネットワークの ID
        security_type: WiFi ネットワークの新しいセキュリティタイプ（wpa2-psk、wpa3-psk、open、wpa-psk、wep、enterprise）

    Returns:
        セキュリティタイプ更新操作の結果
    """
    try:
        # セキュリティタイプを検証
        valid_security_types = ["wpa2-psk", "wpa3-psk", "open", "wpa-psk", "wep", "enterprise"]
        if security_type not in valid_security_types:
            return {"error": f"Invalid security type. Must be one of: {', '.join(valid_security_types)}"}
        
        result = update_wifi_security(device_id, network_id, security_type)
        return result
    except Exception as e:
        logger.error(f"update_wifi_security でエラーが発生しました: {str(e)}")
        return {"error": str(e)}

# Lambda ハンドラー
def lambda_handler(event, context):
    """
    AWS Lambda ハンドラー関数

    Args:
        event: Lambda イベントデータ
        context: Lambda コンテキスト

    Returns:
        Lambda レスポンス
    """
    try:
        # 受信リクエストをパース
        logger.info(f"イベントを受信しました: {json.dumps(event)}")
        
        # イベントからツール名を抽出
        tool_name = event['action_name']
        result = None
        
        # tool_name に基づいて適切な関数を呼び出し
        if tool_name == 'get_device_settings':
            device_id = event['device_id']
            result = tool_get_device_settings(device_id)
        
        elif tool_name == 'list_devices':
            limit = event.get('limit', 25)
            result = tool_list_devices(limit)
        
        elif tool_name == 'list_wifi_networks':
            device_id = event['device_id']
            result = tool_list_wifi_networks(device_id)
        
        elif tool_name == 'list_users':
            limit = event.get('limit', 100)
            result = tool_list_users(limit)
        
        elif tool_name == 'query_user_activity':
            start_date = event['start_date']
            end_date = event['end_date']
            user_id = event.get('user_id')
            activity_type = event.get('activity_type')
            limit = event.get('limit', 50)
            result = tool_query_user_activity(start_date, end_date, user_id, activity_type, limit)
        
        elif tool_name == 'update_wifi_ssid':
            device_id = event['device_id']
            network_id = event['network_id']
            ssid = event['ssid']
            result = tool_update_wifi_ssid(device_id, network_id, ssid)
        
        elif tool_name == 'update_wifi_security':
            device_id = event['device_id']
            network_id = event['network_id']
            security_type = event['security_type']
            result = tool_update_wifi_security(device_id, network_id, security_type)
        
        else:
            available_tools = [
                'get_device_settings', 
                'list_devices', 
                'list_wifi_networks', 
                'list_users', 
                'query_user_activity', 
                'update_wifi_ssid', 
                'update_wifi_security'
            ]
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f"Unknown tool: {tool_name}",
                    'available_tools': available_tools
                })
            }
        
        # 結果を返す
        return {
            'statusCode': 200,
            'body': json_dumps(result)
        }
    
    except Exception as e:
        logger.error(f"リクエスト処理中にエラーが発生しました: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f"Internal server error: {str(e)}"
            })
        }
