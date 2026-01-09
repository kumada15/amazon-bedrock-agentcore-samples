import boto3
import os
import json

# 環境変数を取得
REGION = os.environ.get('AWS_REGION')

# agentcore クライアントを作成
agentcore_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

try:
    # Gateway を一覧表示
    print("既存の Gateway を一覧表示中...")
    gateways = agentcore_client.list_gateways()

    # Gateway の詳細を表示
    for gateway in gateways.get('gateways', []):
        gateway_id = gateway.get('gatewayId')
        gateway_name = gateway.get('name')
        gateway_arn = gateway.get('gatewayArn')
        
        print(f"Gateway ID: {gateway_id}")
        print(f"Gateway 名: {gateway_name}")
        print(f"Gateway ARN: {gateway_arn}")
        print("-" * 50)
        
        # 対象の Gateway の場合、詳細を保存
        if gateway_name == "DB-Performance-Analyzer-Gateway":
            print(f"対象の Gateway を検出: {gateway_name}")

            # Gateway エンドポイントを構築
            gateway_endpoint = f"https://{gateway_id}.gateway.bedrock-agentcore.{REGION}.amazonaws.com"

            # Gateway 設定をファイルに保存
            with open('gateway_config.json', 'w') as f:
                json.dump({
                    "GATEWAY_ID": gateway_id,
                    "GATEWAY_ARN": gateway_arn,
                    "GATEWAY_ENDPOINT": gateway_endpoint
                }, f)
            
            print("Gateway 設定を gateway_config.json に保存しました")

    if not gateways.get('gateways'):
        print("Gateway が見つかりません")

except Exception as e:
    print(f"Gateway 一覧取得エラー: {e}")
    exit(1)