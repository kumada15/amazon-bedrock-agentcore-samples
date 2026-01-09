"""
Lab 01 用の障害注入関数
SRE トレーニング用の3つの一般的なインフラストラクチャ障害を実装
"""

import boto3
import json
import time
from typing import Dict
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from .ssm_helper import get_stack_resources

# 元の設定を保存するグローバルストレージ（将来のロールバック用）
original_configs = {}


def initialize_fault_injection(region_name: str, profile_name: str = None) -> Dict[str, str]:
    """
    Initialize fault injection by retrieving infrastructure resource IDs

    Args:
        region_name: AWS region
        profile_name: AWS profile name (optional)

    Returns:
        Dictionary of resource identifiers
    """
    print("SSM Parameter Store からインフラストラクチャリソースを取得中...")
    resources = get_stack_resources(region_name, profile_name)

    if len(resources) > 0:
        print(f"✅ {len(resources)} 件のリソース識別子を正常に取得しました")
    else:
        print("❌ リソースが取得されませんでした - CloudFormation スタックがデプロイされていない可能性があります")

    return resources

def _update_single_table(dynamodb, table_name: str) -> tuple:
    """
    Update a single DynamoDB table to PROVISIONED mode with low capacity.
    Designed for parallel execution.
    
    Returns:
        tuple: (table_name, success, original_billing_mode_or_error)
    """
    try:
        # 潜在的なロールバック用に元の課金モードを保存
        print(f"テーブルを処理中: {table_name}")
        table_info = dynamodb.describe_table(TableName=table_name)
        original_billing_mode = table_info['Table']['BillingModeSummary']['BillingMode']
        print(f"  元の課金モード: {original_billing_mode}")

        # 危険なほど低い制限でプロビジョンドキャパシティに変換
        print(f"  最小キャパシティで PROVISIONED モードに変換中...")
        dynamodb.update_table(
            TableName=table_name,
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,   # 非常に低い - スロットリングが確実に発生
                'WriteCapacityUnits': 1   # 非常に低い - スロットリングが確実に発生
            }
        )

        # テーブル更新が完了するまで待機
        print(f"  {table_name} の更新が完了するまで待機中...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(
            TableName=table_name,
            WaiterConfig={
                'Delay': 2,        # 2秒ごとにチェック（5秒から短縮）
                'MaxAttempts': 90  # 最大3分
            }
        )

        print(f"✅ {table_name} を正常に更新しました")
        return (table_name, True, original_billing_mode)

    except Exception as table_error:
        print(f"❌ {table_name} の更新に失敗しました: {table_error}")
        return (table_name, False, str(table_error))


def inject_dynamodb_throttling(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    Inject DynamoDB throttling by converting tables to PROVISIONED mode with low capacity.
    This simulates a common production issue where table capacity is insufficient for
    the application workload, causing ProvisionedThroughputExceededException errors.
    
    Args:
        resources: Dictionary of resource identifiers from get_stack_resources()
        region_name: AWS region
        profile_name: AWS profile name (optional)
    
    Returns:
        Boolean indicating success/failure
    """
    try:
        # リソースから DynamoDB テーブル名のリストを取得
        table_keys = [key for key in resources.keys() if key.endswith('_table_name') and 'crm' in key]

        if not table_keys:
            print("❌ リソースに DynamoDB テーブル名が見つかりません")
            return False

        # DynamoDB クライアントを作成
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            dynamodb = session.client('dynamodb')
        else:
            dynamodb = boto3.client('dynamodb', region_name=region_name)
        
        print(f"\n変更する DynamoDB テーブルを {len(table_keys)} 件発見しました")
        print(f"高速実行のためテーブルを並列処理中...")
        print(f"\n{'='*60}")
        
        success_count = 0
        failed_tables = []
        
        # テーブル名を抽出
        table_names = [resources.get(key) for key in table_keys if resources.get(key)]

        if not table_names:
            print("❌ 有効なテーブル名が見つかりません")
            return False

        # テーブルを並列処理
        max_workers = min(len(table_names), 10)  # 同時操作を10に制限

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # すべてのテーブル更新を送信
            future_to_table = {
                executor.submit(_update_single_table, dynamodb, table_name): table_name
                for table_name in table_names
            }
            
            # 完了した結果を収集
            for future in as_completed(future_to_table):
                table_name, success, result = future.result()

                if success:
                    # ロールバック用に元の設定を保存
                    original_configs[f'dynamodb_billing_mode_{table_name}'] = result
                    success_count += 1
                else:
                    failed_tables.append(table_name)

        # サマリー
        print(f"\n{'='*60}")
        print(f"サマリー: {success_count}/{len(table_names)} テーブルを正常に更新しました")
        if failed_tables:
            print(f"失敗したテーブル: {', '.join(failed_tables)}")
        print(f"{'='*60}")
        
        return success_count > 0
        
    except Exception as e:
        print(f"❌ DynamoDB スロットリング注入に失敗しました: {e}")
        return False
    



def inject_iam_permissions(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    Inject IAM permission issues by replacing DynamoDB Allow policy with Deny policy

    This simulates a common production issue where overly restrictive security policies
    or accidental policy changes prevent applications from accessing required AWS resources.

    Args:
        resources: Dictionary of resource identifiers from get_stack_resources()
        region_name: AWS region
        profile_name: AWS profile name (optional)

    Returns:
        Boolean indicating success/failure
    """
    try:
        ec2_role_name = resources.get('ec2_role_name')

        if not ec2_role_name:
            print("❌ リソースに EC2 ロール名が見つかりません")
            return False

        # IAM クライアントを作成
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            iam = session.client('iam')
        else:
            iam = boto3.client('iam', region_name=region_name)

        print(f"\n対象 IAM ロール: {ec2_role_name}")

        # 潜在的なロールバック用に元のポリシーを保存
        print("元の DynamoDB ポリシーをバックアップ中...")
        try:
            original_policy = iam.get_role_policy(
                RoleName=ec2_role_name,
                PolicyName='DynamoDBAccess'
            )
            original_configs['dynamodb_policy'] = original_policy['PolicyDocument']
            print("  ✅ 元のポリシーをバックアップしました（編集済み）")
        except ClientError:
            print("  ⚠️  元のポリシーをバックアップできませんでした（存在しない可能性があります）")

        # DynamoDB アクセスを拒否する制限的なポリシーを作成
        print("\n制限的な IAM ポリシーを適用中...")
        print("  技術的詳細:")
        print("  - 既存の 'Allow' ステートメントを 'Deny' ステートメントに置き換え")
        print("  - アプリケーションで使用される主要な DynamoDB 操作を対象")
        print("  - Deny ポリシーはすべての Allow ポリシーをオーバーライド（明示的な拒否が優先）")
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
        print(f"❌ IAM 権限注入に失敗しました: {e}")
        return False


def inject_nginx_crash(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    Inject nginx crash by killing the nginx process via AWS Systems Manager

    This simulates a common production issue where services crash due to memory leaks,
    segmentation faults, or resource exhaustion, causing ALB health check failures.

    Args:
        resources: Dictionary of resource identifiers from get_stack_resources()
        region_name: AWS region
        profile_name: AWS profile name (optional)

    Returns:
        Boolean indicating success/failure
    """
    try:
        nginx_instance_id = resources.get('nginx_instance_id')

        if not nginx_instance_id:
            print("❌ リソースに Nginx インスタンス ID が見つかりません")
            return False

        # SSM クライアントを作成
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            ssm = session.client('ssm')
        else:
            ssm = boto3.client('ssm', region_name=region_name)

        print(f"\n対象 EC2 インスタンス: {nginx_instance_id}")
        print("\nnginx プロセスを強制終了してサービスクラッシュをシミュレート中...")
        print("  技術的詳細:")
        print("  - 'pkill -9 nginx' を使用して nginx プロセスを強制終了")
        print("  - 本番環境で一般的なクラッシュをシミュレート（メモリリーク、セグフォルトなど）")
        print("  - ALB ヘルスチェックが /health に到達しようとすると 'connection refused' を取得")
        print("  - 3回連続の失敗（90秒）後、ターゲットが unhealthy としてマークされる")

        # nginx プロセスを強制終了してクラッシュをシミュレート
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

        # コマンドの完了を待機
        print("  クラッシュシミュレーションの完了を待機中...")
        time.sleep(10)

        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=nginx_instance_id
        )

        if result['Status'] == 'Success':
            return True
        else:
            print(f"  ❌ コマンドが失敗しました: {result['Status']}")
            if result.get('StandardErrorContent'):
                print(f"  エラー: {result['StandardErrorContent']}")
            return False

    except Exception as e:
        print(f"❌ Nginx クラッシュ注入に失敗しました: {e}")
        return False


def inject_nginx_timeout(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    Inject nginx timeout misconfiguration by setting proxy timeouts too short

    This simulates a common production issue where reverse proxy timeouts don't
    account for backend response times, causing 502 Bad Gateway errors.

    Args:
        resources: Dictionary of resource identifiers from get_stack_resources()
        region_name: AWS region
        profile_name: AWS profile name (optional)

    Returns:
        Boolean indicating success/failure
    """
    try:
        nginx_instance_id = resources.get('nginx_instance_id')

        if not nginx_instance_id:
            print("❌ リソースに Nginx インスタンス ID が見つかりません")
            return False

        # SSM クライアントを作成
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            ssm = session.client('ssm')
        else:
            ssm = boto3.client('ssm', region_name=region_name)

        print(f"\n対象 EC2 インスタンス: {nginx_instance_id}")
        print("\nnginx タイムアウト設定ミスを注入中...")
        print("  技術的詳細:")
        print("  - proxy_read_timeout を 1秒に設定（短すぎる）")
        print("  - 1秒以上かかるバックエンドクエリはタイムアウトを引き起こす")
        print("  - タイムアウト発生時に Nginx は 502 Bad Gateway を返す")
        print("  - タイムアウトがバックエンド SLA と一致しない場合によくある問題")

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

        # コマンドの完了を待機
        print("  注入の完了を待機中...")
        time.sleep(10)

        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=nginx_instance_id
        )

        if result['Status'] == 'Success':
            return True
        else:
            print(f"  ❌ コマンドが失敗しました: {result['Status']}")
            if result.get('StandardErrorContent'):
                print(f"  エラー: {result['StandardErrorContent']}")
            return False

    except Exception as e:
        print(f"❌ Nginx タイムアウト注入に失敗しました: {e}")
        return False