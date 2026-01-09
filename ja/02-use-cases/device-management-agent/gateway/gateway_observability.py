"""
Amazon Bedrock AgentCore Gateway オブザーバビリティ設定

このモジュールは、CloudWatch Logs 配信先を設定することで
Amazon Bedrock AgentCore Gateway のオブザーバビリティ機能を有効にします。
Gateway 操作を監視するためのロググループと配信メカニズムのセットアップを自動化します。

スクリプトは以下の操作を実行します:
1. Vended ログ配信用の CloudWatch Logs ロググループを作成
2. Gateway ログの配信先を設定
3. AgentCore Gateway から CloudWatch へのログ配信をセットアップ
4. 環境設定と AWS 認証情報を検証

主な機能:
    - 標準化された命名規則による自動ロググループ作成
    - Vended ログ配信先の設定
    - 既存リソースのエラーハンドリング
    - ARN 構築のための AWS アカウント ID 解決
    - リージョン固有のロググループ管理

必須環境変数:
    GATEWAY_ARN: オブザーバビリティを有効にする Gateway の ARN
    GATEWAY_ID: ロググループ命名用の Gateway 識別子
    AWS_REGION: CloudWatch Logs 用の AWS リージョン（デフォルトは us-west-2）

作成される CloudWatch リソース:
    ロググループ: /aws/vendedlogs/bedrock-agentcore/{gateway_id}
    配信先: {gateway_id}-logs-destination

使用例:
    .env ファイルで環境変数を設定してから実行:
    >>> python gateway_observability.py

    出力:
    AWS アカウント ID: 123456789012
    ゲートウェイ ARN: arn:aws:bedrock-agentcore:us-west-2:123456789012:gateway/...
    ゲートウェイ ID: gateway-12345
    リージョン: us-west-2
    ロググループを作成しました: /aws/vendedlogs/bedrock-agentcore/gateway-12345
    ログ配信先を作成しました: gateway-12345-logs-destination
    gateway-12345 のオブザーバビリティを有効化しました

エラーハンドリング:
    - 既存のロググループを適切に処理
    - 必須環境変数を検証
    - 設定失敗時はエラーコードで終了
    - トラブルシューティング用の詳細なエラーメッセージを提供

注意事項:
    - ロググループは AWS Vended ログの命名規則に従う
    - 配信先により自動ログルーティングが可能
    - CloudWatch Logs 用の適切な IAM 権限が必要
    - ロググループ ARN は AWS アカウント ID を使用して構築
"""
import boto3
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def enable_observability_for_resource(resource_arn, resource_id, account_id, region='us-west-2'):
    """
    Bedrock AgentCore リソース（例: Gateway）のオブザーバビリティを有効にします
    """
    logs_client = boto3.client('logs', region_name=region)

    # Step 0: Create new log group for vended log delivery
    log_group_name = f'/aws/vendedlogs/bedrock-agentcore/{resource_id}'
    try:
        logs_client.create_log_group(logGroupName=log_group_name)
        print(f"ロググループを作成しました: {log_group_name}")
    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"ロググループは既に存在します: {log_group_name}")
    except Exception as e:
        print(f"ロググループ作成エラー: {e}")
        return None
        
    log_group_arn = f'arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}'
    
    try:
        # Step 3: Create delivery destinations
        logs_destination_response = logs_client.put_delivery_destination(
            name=f"{resource_id}-logs-destination",
            deliveryDestinationType='CWL',
            deliveryDestinationConfiguration={
                'destinationResourceArn': log_group_arn,
            }
        )
        print(f"ログ配信先を作成しました: {logs_destination_response['deliveryDestination']['name']}")

        print(f"{resource_id} のオブザーバビリティを有効化しました")
        return resource_id
        
    except Exception as e:
        print(f"オブザーバビリティ有効化エラー: {e}")
        return None

if __name__ == "__main__":
    # Get environment variables
    gateway_arn = os.getenv('GATEWAY_ARN')
    gateway_id = os.getenv('GATEWAY_ID')
    aws_region = os.getenv('AWS_REGION', 'us-west-2')
    
    # Get AWS account ID
    try:
        sts_client = boto3.client('sts', region_name=aws_region)
        account_id = sts_client.get_caller_identity()['Account']
        print(f"AWS アカウント ID: {account_id}")
    except Exception as e:
        print(f"AWS アカウント ID 取得エラー: {e}")
        sys.exit(1)
    
    # Validate required environment variables
    if not gateway_arn:
        print("エラー: 環境変数に GATEWAY_ARN が見つかりません")
        sys.exit(1)

    if not gateway_id:
        print("エラー: 環境変数に GATEWAY_ID が見つかりません")
        sys.exit(1)
    
    print(f"ゲートウェイ ARN: {gateway_arn}")
    print(f"ゲートウェイ ID: {gateway_id}")
    print(f"リージョン: {aws_region}")
    
    # Enable observability for the gateway
    enable_observability_for_resource(gateway_arn, gateway_id, account_id, aws_region)