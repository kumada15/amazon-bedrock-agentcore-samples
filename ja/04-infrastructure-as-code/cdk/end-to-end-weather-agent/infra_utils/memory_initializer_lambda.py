import json
import boto3
import logging
import urllib3
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def send_response(event, context, response_status, response_data=None, physical_resource_id=None, reason=None):
    """CloudFormation にレスポンスを送信"""
    response_data = response_data or {}
    physical_resource_id = physical_resource_id or context.log_stream_name
    reason = reason or f"See CloudWatch Log Stream: {context.log_stream_name}"
    
    response_body = {
        'Status': response_status,
        'Reason': reason,
        'PhysicalResourceId': physical_resource_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data
    }
    
    json_response_body = json.dumps(response_body)
    
    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }
    
    try:
        http = urllib3.PoolManager()
        response = http.request('PUT', event['ResponseURL'], body=json_response_body, headers=headers)
        logger.info(f"CloudFormation レスポンスを送信しました: {response.status}")
    except Exception as e:
        logger.error(f"CloudFormation レスポンスの送信に失敗しました: {e}")

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    ユーザーの設定で AgentCore Memory を初期化する Lambda 関数
    """
    try:
        logger.info(f"メモリ初期化イベント: {json.dumps(event)}")
        
        request_type = event.get('RequestType')
        memory_id = event['ResourceProperties']['MemoryId']
        region = event['ResourceProperties']['Region']
        
        if request_type == 'Create':
            logger.info(f"リージョン {region} でメモリ {memory_id} を初期化中")
            
            # 動作している CloudFormation テンプレートと一致するアクティビティ設定
            activity_preferences = {
                "good_weather": ["hiking", "beach volleyball", "outdoor picnic", "cycling", "rock climbing"],
                "ok_weather": ["walking tours", "outdoor dining", "park visits", "sightseeing", "farmers markets"],
                "poor_weather": ["indoor museums", "shopping", "restaurants", "movie theaters", "art galleries"]
            }
            
            # blob に保存するため JSON 文字列に変換
            activity_preferences_json = json.dumps(activity_preferences)
            
            # 現在のタイムスタンプを取得
            timestamp = datetime.utcnow().isoformat() + 'Z'
            
            # bedrock-agentcore クライアントを初期化
            client = boto3.client('bedrock-agentcore', region_name=region)
            
            response = client.create_event(
                memoryId=memory_id,
                actorId="user123",
                sessionId="session456",
                eventTimestamp=timestamp,
                payload=[
                    {
                        'blob': activity_preferences_json,
                    }
                ]
            )
            
            logger.info(f"メモリイベントを正常に作成しました: {response}")
            
            send_response(event, context, 'SUCCESS', {
                'MemoryId': memory_id,
                'Status': 'INITIALIZED'
            }, f"memory-init-{memory_id}")
            
        elif request_type in ['Update', 'Delete']:
            logger.info(f"{request_type} リクエストを処理中 - 操作は不要です")
            send_response(event, context, 'SUCCESS', {}, 
                         event.get('PhysicalResourceId', f"memory-init-{memory_id}"))
            
    except Exception as e:
        logger.error(f"メモリの初期化エラー: {str(e)}")
        send_response(event, context, 'FAILED', {}, 
                     event.get('PhysicalResourceId', 'memory-init-failed'), str(e))
