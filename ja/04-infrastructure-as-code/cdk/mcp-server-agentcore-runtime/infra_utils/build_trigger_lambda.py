import boto3
import json
import logging
import time
import urllib3

# 注意: cfnresponse は CloudFormation のインライン Lambda コードでのみ利用可能です。
# CDK で Code.from_asset() を使用する場合、独自のコピーを含める必要があります。
# これは AWS 提供の標準 cfnresponse モジュールを直接埋め込んだものです。

class cfnresponse:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    
    @staticmethod
    def send(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None):
        responseUrl = event['ResponseURL']
        print(responseUrl)

        responseBody = {
            'Status': responseStatus,
            'Reason': reason or "See the details in CloudWatch Log Stream: {}".format(context.log_stream_name),
            'PhysicalResourceId': physicalResourceId or context.log_stream_name,
            'StackId': event['StackId'],
            'RequestId': event['RequestId'],
            'LogicalResourceId': event['LogicalResourceId'],
            'NoEcho': noEcho,
            'Data': responseData
        }

        json_responseBody = json.dumps(responseBody)
        print("レスポンスボディ:")
        print(json_responseBody)

        headers = {
            'content-type': '',
            'content-length': str(len(json_responseBody))
        }

        try:
            http = urllib3.PoolManager()
            response = http.request('PUT', responseUrl, headers=headers, body=json_responseBody)
            print("ステータスコード:", response.status)
        except Exception as e:
            print("send(..) http.request(..)の実行に失敗しました:", e)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info('Received event: %s', json.dumps(event))
    
    try:
        if event['RequestType'] == 'Delete':
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            return
            
        project_name = event['ResourceProperties']['ProjectName']
        
        codebuild = boto3.client('codebuild')
        
        # ビルドを開始
        response = codebuild.start_build(projectName=project_name)
        build_id = response['build']['id']
        logger.info(f"ビルドを開始しました: {build_id}")
        
        # 完了を待機
        max_wait_time = context.get_remaining_time_in_millis() / 1000 - 30
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait_time:
                cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': 'Build timeout'})
                return
                
            build_response = codebuild.batch_get_builds(ids=[build_id])
            build_status = build_response['builds'][0]['buildStatus']
            
            if build_status == 'SUCCEEDED':
                logger.info(f"ビルド {build_id} が成功しました")
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {'BuildId': build_id})
                return
            elif build_status in ['FAILED', 'FAULT', 'STOPPED', 'TIMED_OUT']:
                logger.error(f"ビルド {build_id} がステータス {build_status} で失敗しました")
                cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': f'Build failed: {build_status}'})
                return
                
            logger.info(f"ビルド {build_id} のステータス: {build_status}")
            time.sleep(30)
            
    except Exception as e:
        logger.error('Error: %s', str(e))
        cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': str(e)})
