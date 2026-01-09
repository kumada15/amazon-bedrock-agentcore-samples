"""
Lab 01 用の障害注入関数
SRE トレーニング用の 3 つの一般的なインフラ障害を実装
"""

import boto3
import json
import time
from typing import Dict
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from .ssm_helper import get_stack_resources

# 元の設定のグローバルストレージ（将来のロールバック用）
original_configs = {}


def initialize_fault_injection(region_name: str, profile_name: str = None) -> Dict[str, str]:
    """
    インフラリソース ID を取得して障害注入を初期化

    Args:
        region_name: AWS リージョン
        profile_name: AWS プロファイル名（オプション）

    Returns:
        リソース識別子の辞書
    """
    print("SSM パラメータストアからインフラリソースを取得中...")
    resources = get_stack_resources(region_name, profile_name)

    if len(resources) > 0:
        print(f"{len(resources)} 件のリソース識別子の取得に成功しました")
    else:
        print("リソースを取得できませんでした - CloudFormation スタックがデプロイされていない可能性があります")

    return resources

def _update_single_table(dynamodb, table_name: str) -> tuple:
    """
    単一の DynamoDB テーブルを低キャパシティの PROVISIONED モードに更新。
    並列実行用に設計。

    Returns:
        tuple: (table_name, success, original_billing_mode_or_error)
    """
    try:
        # Store original billing mode for potential rollback
        print(f"テーブルを処理中: {table_name}")
        table_info = dynamodb.describe_table(TableName=table_name)
        original_billing_mode = table_info['Table']['BillingModeSummary']['BillingMode']
        print(f"  元の課金モード: {original_billing_mode}")

        # Convert to provisioned capacity with dangerously low limits
        print(f"  最小キャパシティで PROVISIONED モードに変換中...")
        dynamodb.update_table(
            TableName=table_name,
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,   # Extremely low - guaranteed to throttle
                'WriteCapacityUnits': 1   # Extremely low - guaranteed to throttle
            }
        )
        
        # Wait for table update to complete
        print(f"  {table_name} の更新完了を待機中...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(
            TableName=table_name,
            WaiterConfig={
                'Delay': 2,        # Check every 2 seconds (reduced from 5)
                'MaxAttempts': 90  # 3 minutes max
            }
        )

        print(f"{table_name} の更新に成功しました")
        return (table_name, True, original_billing_mode)

    except Exception as table_error:
        print(f"{table_name} の更新に失敗しました: {table_error}")
        return (table_name, False, str(table_error))


def inject_dynamodb_throttling(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    テーブルを低キャパシティの PROVISIONED モードに変換して DynamoDB スロットリングを注入。
    これは、テーブルキャパシティがアプリケーションのワークロードに対して不十分で、
    ProvisionedThroughputExceededException エラーが発生する一般的な本番環境の問題をシミュレートします。

    Args:
        resources: get_stack_resources() からのリソース識別子の辞書
        region_name: AWS リージョン
        profile_name: AWS プロファイル名（オプション）

    Returns:
        成功/失敗を示すブール値
    """
    try:
        # Get list of DynamoDB table names from resources
        table_keys = [key for key in resources.keys() if key.endswith('_table_name') and 'crm' in key]
        
        if not table_keys:
            print("リソースに DynamoDB テーブル名が見つかりません")
            return False
        
        # Create DynamoDB client
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            dynamodb = session.client('dynamodb')
        else:
            dynamodb = boto3.client('dynamodb', region_name=region_name)
        
        print(f"\n{len(table_keys)} 件の DynamoDB テーブルを変更します")
        print(f"高速化のためテーブルを並列処理中...")
        print(f"\n{'='*60}")
        
        success_count = 0
        failed_tables = []
        
        # Extract table names
        table_names = [resources.get(key) for key in table_keys if resources.get(key)]
        
        if not table_names:
            print("有効なテーブル名が見つかりません")
            return False
        
        # Process tables concurrently
        max_workers = min(len(table_names), 10)  # Limit to 10 concurrent operations
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all table updates
            future_to_table = {
                executor.submit(_update_single_table, dynamodb, table_name): table_name
                for table_name in table_names
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_table):
                table_name, success, result = future.result()
                
                if success:
                    # Store original config for rollback
                    original_configs[f'dynamodb_billing_mode_{table_name}'] = result
                    success_count += 1
                else:
                    failed_tables.append(table_name)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"概要: {success_count}/{len(table_names)} テーブルの更新に成功しました")
        if failed_tables:
            print(f"失敗したテーブル: {', '.join(failed_tables)}")
        print(f"{'='*60}")

        return success_count > 0

    except Exception as e:
        print(f"DynamoDB スロットリング注入に失敗しました: {e}")
        return False
    



def inject_iam_permissions(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    DynamoDB の Allow ポリシーを Deny ポリシーに置き換えて IAM 権限の問題を注入

    過度に制限的なセキュリティポリシーまたは誤ったポリシー変更により、
    アプリケーションが必要な AWS リソースにアクセスできなくなる、
    一般的な本番環境の問題をシミュレートします。

    Args:
        resources: get_stack_resources() からのリソース識別子の辞書
        region_name: AWS リージョン
        profile_name: AWS プロファイル名（オプション）

    Returns:
        成功/失敗を示すブール値
    """
    try:
        ec2_role_name = resources.get('ec2_role_name')

        if not ec2_role_name:
            print("リソースに EC2 ロール名が見つかりません")
            return False

        # Create IAM client
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            iam = session.client('iam')
        else:
            iam = boto3.client('iam', region_name=region_name)

        print(f"\nターゲット IAM ロール: {ec2_role_name}")

        # Store original policy for potential rollback
        print("元の DynamoDB ポリシーをバックアップ中...")
        try:
            original_policy = iam.get_role_policy(
                RoleName=ec2_role_name,
                PolicyName='DynamoDBAccess'
            )
            original_configs['dynamodb_policy'] = original_policy['PolicyDocument']
            print("  元のポリシーをバックアップしました（編集済み）")
        except ClientError:
            print("  元のポリシーをバックアップできませんでした（存在しない可能性があります）")

        # Create a restrictive policy that denies DynamoDB access
        print("\n制限的な IAM ポリシーを適用中...")
        print("  技術詳細:")
        print("  - 既存の 'Allow' ステートメントを 'Deny' ステートメントに置き換え")
        print("  - アプリケーションが使用する主要な DynamoDB 操作を対象")
        print("  - Deny ポリシーは Allow ポリシーよりも優先（明示的な拒否が優先）")
        print("  - データベース操作で即座に AccessDenied エラーが発生")

        restricted_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Action": [
                        "dynamodb:PutItem",
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem"
                    ],
                    "Resource": "*"
                }
            ]
        }

        iam.put_role_policy(
            RoleName=ec2_role_name,
            PolicyName='DynamoDBAccess',
            PolicyDocument=json.dumps(restricted_policy)
        )

        return True

    except Exception as e:
        print(f"IAM 権限注入に失敗しました: {e}")
        return False


def inject_nginx_crash(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    AWS Systems Manager 経由で nginx プロセスを強制終了して nginx クラッシュを注入

    メモリリーク、セグメンテーションフォールト、またはリソース枯渇によりサービスがクラッシュし、
    ALB ヘルスチェックが失敗する、一般的な本番環境の問題をシミュレートします。

    Args:
        resources: get_stack_resources() からのリソース識別子の辞書
        region_name: AWS リージョン
        profile_name: AWS プロファイル名（オプション）

    Returns:
        成功/失敗を示すブール値
    """
    try:
        nginx_instance_id = resources.get('nginx_instance_id')

        if not nginx_instance_id:
            print("リソースに Nginx インスタンス ID が見つかりません")
            return False

        # Create SSM client
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            ssm = session.client('ssm')
        else:
            ssm = boto3.client('ssm', region_name=region_name)

        print(f"\nターゲット EC2 インスタンス: {nginx_instance_id}")
        print("\nnginx プロセスを強制終了してサービスクラッシュをシミュレート中...")
        print("  技術詳細:")
        print("  - 'pkill -9 nginx' を使用して nginx プロセスを強制終了")
        print("  - 本番環境で一般的なクラッシュ（メモリリーク、セグメントフォールトなど）をシミュレート")
        print("  - ALB ヘルスチェックは /health にアクセスしようとすると 'connection refused' を受け取る")
        print("  - 3回連続で失敗後（90秒）、ターゲットは異常としてマークされる")

        # Kill nginx process to simulate crash
        crash_script = '''
echo "Current nginx process status:"
sudo systemctl status nginx --no-pager -l || echo "Nginx not running"

echo -e "\\nKilling nginx process to simulate service crash..."
sudo pkill -9 nginx

echo -e "\\nWaiting 5 seconds..."
sleep 5

echo -e "\\nService status after crash:"
sudo systemctl status nginx --no-pager -l || echo "Nginx crashed (as expected)"

echo -e "\\nProcess check:"
ps aux | grep nginx | grep -v grep || echo "No nginx processes running"
'''

        print("\nAWS Systems Manager 経由でクラッシュシミュレーションを実行中...")

        response = ssm.send_command(
            InstanceIds=[nginx_instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': [crash_script]},
            Comment="SRE Workshop Lab-01: Simulate nginx service crash"
        )

        command_id = response['Command']['CommandId']
        print(f"  コマンド ID: {command_id}")

        # Wait for command to complete
        print("  クラッシュシミュレーションの完了を待機中...")
        time.sleep(10)

        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=nginx_instance_id
        )

        if result['Status'] == 'Success':
            return True
        else:
            print(f"  コマンドが失敗しました: {result['Status']}")
            if result.get('StandardErrorContent'):
                print(f"  エラー: {result['StandardErrorContent']}")
            return False

    except Exception as e:
        print(f"Nginx クラッシュ注入に失敗しました: {e}")
        return False


def inject_nginx_timeout(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    プロキシタイムアウトを短すぎる値に設定して nginx タイムアウト設定ミスを注入

    リバースプロキシのタイムアウトがバックエンドの応答時間を考慮しておらず、
    502 Bad Gateway エラーが発生する、一般的な本番環境の問題をシミュレートします。

    Args:
        resources: get_stack_resources() からのリソース識別子の辞書
        region_name: AWS リージョン
        profile_name: AWS プロファイル名（オプション）

    Returns:
        成功/失敗を示すブール値
    """
    try:
        nginx_instance_id = resources.get('nginx_instance_id')

        if not nginx_instance_id:
            print("リソースに Nginx インスタンス ID が見つかりません")
            return False

        # Create SSM client
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            ssm = session.client('ssm')
        else:
            ssm = boto3.client('ssm', region_name=region_name)

        print(f"\nターゲット EC2 インスタンス: {nginx_instance_id}")
        print("\nnginx タイムアウト設定ミスを注入中...")
        print("  技術詳細:")
        print("  - proxy_read_timeout を 1 秒に設定（短すぎる）")
        print("  - 1秒以上かかるバックエンドクエリでタイムアウトが発生")
        print("  - タイムアウト時に Nginx は 502 Bad Gateway を返す")
        print("  - タイムアウトがバックエンド SLA と一致しない場合の一般的な問題")

        timeout_script = '''
#!/bin/bash
set -e

# Backup original nginx.conf
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup

# Update nginx.conf with short timeouts
sudo sed -i 's/proxy_connect_timeout [0-9]*s;/proxy_connect_timeout 1s;/' /etc/nginx/nginx.conf
sudo sed -i 's/proxy_send_timeout [0-9]*s;/proxy_send_timeout 1s;/' /etc/nginx/nginx.conf
sudo sed -i 's/proxy_read_timeout [0-9]*s;/proxy_read_timeout 1s;/' /etc/nginx/nginx.conf

# Test configuration
sudo nginx -t

# Reload nginx to apply changes
sudo systemctl reload nginx

echo "Nginx timeout misconfiguration injected successfully"
'''

        print("\nAWS Systems Manager 経由でタイムアウト注入を実行中...")

        response = ssm.send_command(
            InstanceIds=[nginx_instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': [timeout_script]},
            Comment="SRE Workshop Lab-01: Inject nginx timeout misconfiguration"
        )

        command_id = response['Command']['CommandId']
        print(f"  コマンド ID: {command_id}")

        # Wait for command to complete
        print("  注入の完了を待機中...")
        time.sleep(10)

        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=nginx_instance_id
        )

        if result['Status'] == 'Success':
            return True
        else:
            print(f"  コマンドが失敗しました: {result['Status']}")
            if result.get('StandardErrorContent'):
                print(f"  エラー: {result['StandardErrorContent']}")
            return False

    except Exception as e:
        print(f"Nginx タイムアウト注入に失敗しました: {e}")
        return False