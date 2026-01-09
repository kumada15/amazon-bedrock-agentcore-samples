#!/usr/bin/env python3

import boto3
import json

def test_multi_agent():
    """マルチエージェントシステムをテスト"""

    # CloudFormation 出力から Runtime ARN を取得
    cf_client = boto3.client('cloudformation', region_name='us-east-1')
    
    try:
        response = cf_client.describe_stacks(StackName='MultiAgentDemo')
        outputs = response['Stacks'][0]['Outputs']
        
        agent1_arn = None
        agent2_arn = None
        
        for output in outputs:
            if output['OutputKey'] == 'Agent1RuntimeArn':
                agent1_arn = output['OutputValue']
            elif output['OutputKey'] == 'Agent2RuntimeArn':
                agent2_arn = output['OutputValue']
        
        print(f"Agent1 (オーケストレーター) ARN: {agent1_arn}")
        print(f"Agent2 (スペシャリスト) ARN: {agent2_arn}")

    except Exception as e:
        print(f"スタック出力の取得エラー: {e}")
        return
    
    # bedrock-agentcore クライアントを作成
    agentcore_client = boto3.client('bedrock-agentcore', region_name='us-east-1')
    
    # テスト1: 簡単なクエリ（Agent1 が直接処理）
    print("\n" + "="*60)
    print("テスト1: 簡単な挨拶（Agent1が直接処理）")
    print("="*60)
    
    try:
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent1_arn,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": "Hello, how are you?"})
        )

        print("レスポンスを受信:")
        print(f"Content Type: {response.get('contentType', 'N/A')}")
        
        # レスポンスを処理
        if response.get('contentType') == 'application/json':
            response_body = response['response'].read()
            result = json.loads(response_body.decode('utf-8'))
            print(f"結果: {json.dumps(result, indent=2)}")
        else:
            print("レスポンスボディ:")
            for chunk in response['response']:
                print(chunk.decode('utf-8'))

    except Exception as e:
        print(f"Agent1の簡単なクエリテストでエラー: {e}")

    # テスト2: 複雑なクエリ（Agent2 への委譲をトリガー）
    print("\n" + "="*60)
    print("テスト2: 複雑な分析（Agent1がAgent2に委譲）")
    print("="*60)
    
    try:
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent1_arn,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": "Provide a detailed analysis of the benefits and drawbacks of serverless architecture"})
        )

        print("レスポンスを受信:")
        print(f"Content Type: {response.get('contentType', 'N/A')}")

        # レスポンスを処理
        if response.get('contentType') == 'application/json':
            response_body = response['response'].read()
            result = json.loads(response_body.decode('utf-8'))
            print(f"結果: {json.dumps(result, indent=2)}")
        else:
            print("レスポンスボディ:")
            for chunk in response['response']:
                print(chunk.decode('utf-8'))

    except Exception as e:
        print(f"Agent1の複雑なクエリテストでエラー: {e}")

    # テスト3: Agent2 の直接テスト
    print("\n" + "="*60)
    print("テスト3: Agent2の直接テスト（スペシャリスト）")
    print("="*60)
    
    try:
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent2_arn,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": "Explain quantum computing in detail"})
        )

        print("レスポンスを受信:")
        print(f"Content Type: {response.get('contentType', 'N/A')}")

        # レスポンスを処理
        if response.get('contentType') == 'application/json':
            response_body = response['response'].read()
            result = json.loads(response_body.decode('utf-8'))
            print(f"結果: {json.dumps(result, indent=2)}")
        else:
            print("レスポンスボディ:")
            for chunk in response['response']:
                print(chunk.decode('utf-8'))

    except Exception as e:
        print(f"Agent2の直接テストでエラー: {e}")

if __name__ == "__main__":
    test_multi_agent()
