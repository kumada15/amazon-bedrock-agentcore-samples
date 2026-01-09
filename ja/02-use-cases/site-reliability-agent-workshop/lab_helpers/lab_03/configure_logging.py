#!/usr/bin/env python3
"""
AgentCore Runtime 用 CloudWatch Logs 配信の設定

AgentCore Runtime のコンテナログ（stdout/stderr）を CloudWatch に
流すための CloudWatch Logs 配信を設定する機能を提供するモジュール。

AWS ドキュメントに基づく:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html
- https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutDeliverySource.html
"""

import boto3
import time
from typing import Dict, Optional


def configure_runtime_logging(
    runtime_arn: str,
    runtime_id: str,
    region: str = "us-west-2",
    log_type: str = "APPLICATION_LOGS"
) -> Dict[str, str]:
    """
    AgentCore Runtime 用の CloudWatch Logs 配信を設定。

    この関数は完全なロギングパイプラインをセットアップします:
    1. CloudWatch Log Group を作成
    2. Delivery Source を作成（Runtime ARN にリンク）
    3. Delivery Destination を作成（Log Group にリンク）
    4. Delivery を作成（Source から Destination へリンク）

    Args:
        runtime_arn: AgentCore Runtime の完全な ARN
        runtime_id: Runtime ID（ARN の最後のセグメント）
        region: AWS リージョン（デフォルト: us-west-2）
        log_type: ログの種類（デフォルト: APPLICATION_LOGS）
                  有効な値: APPLICATION_LOGS、USAGE_LOGS、TRACES

    Returns:
        以下を含む辞書:
        - log_group_name: 作成されたロググループ名
        - delivery_source_arn: Delivery Source の ARN
        - delivery_destination_arn: Delivery Destination の ARN
        - delivery_id: Delivery の ID
        - delivery_status: Delivery のステータス

    Raises:
        Exception: 重要なステップが失敗した場合

    Example:
        >>> result = configure_runtime_logging(
        ...     runtime_arn="arn:aws:bedrock-agentcore:us-west-2:123:runtime/my-runtime-ABC",
        ...     runtime_id="my-runtime-ABC",
        ...     region="us-west-2"
        ... )
        >>> print(f"ログの場所: {result['log_group_name']}")
    """

    print("\n" + "=" * 80)
    print("🔧 Configuring CloudWatch Logs Delivery for AgentCore Runtime")
    print("=" * 80)

    # AWS クライアントを初期化
    logs_client = boto3.client('logs', region_name=region)

    # Runtime ARN から AWS アカウント ID を取得
    account_id = runtime_arn.split(':')[4]

    # 派生設定
    log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"

    # 名前を 60 文字以内に保つために runtime_id の最後の 12 文字を抽出
    # AWS API は delivery source/destination 名を 60 文字以下に要求
    short_id = runtime_id.split('-')[-1]  # Gets the unique suffix (e.g., "V5wJhp4zqq")
    delivery_source_name = f"aiml301-lab03-src-{short_id}"
    delivery_destination_name = f"aiml301-lab03-dst-{short_id}"

    print(f"\n📋 Configuration:")
    print(f"  Runtime ARN: {runtime_arn}")
    print(f"  Runtime ID: {runtime_id}")
    print(f"  Log Group: {log_group_name}")
    print(f"  Region: {region}")
    print(f"  Log Type: {log_type}")

    result = {
        'log_group_name': log_group_name,
        'delivery_source_arn': None,
        'delivery_destination_arn': None,
        'delivery_id': None,
        'delivery_status': None
    }

    # Step 1: Create Log Group
    print("\n📋 Step 1: Creating CloudWatch Log Group...")
    try:
        logs_client.create_log_group(logGroupName=log_group_name)
        print(f"  ✅ Created log group: {log_group_name}")
    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  ℹ️  Log group already exists: {log_group_name}")
    except Exception as e:
        print(f"  ⚠️  Warning: {e}")

    # Step 2: Create Delivery Source
    print("\n📋 Step 2: Creating Delivery Source...")
    try:
        response = logs_client.put_delivery_source(
            name=delivery_source_name,
            resourceArn=runtime_arn,
            logType=log_type,
            tags={
                'Project': 'AIML301',
                'Lab': 'Lab-03',
                'ManagedBy': 'Workshop'
            }
        )

        result['delivery_source_arn'] = response['deliverySource']['arn']
        print(f"  ✅ Created delivery source")
        print(f"     ARN: {result['delivery_source_arn']}")
        print(f"     Name: {delivery_source_name}")

    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  ℹ️  Delivery source already exists: {delivery_source_name}")
        response = logs_client.get_delivery_source(name=delivery_source_name)
        result['delivery_source_arn'] = response['deliverySource']['arn']
        print(f"     ARN: {result['delivery_source_arn']}")
    except Exception as e:
        print(f"  ❌ Failed to create delivery source: {e}")
        raise

    # Step 3: Create Delivery Destination
    print("\n📋 Step 3: Creating Delivery Destination...")
    try:
        response = logs_client.put_delivery_destination(
            name=delivery_destination_name,
            deliveryDestinationConfiguration={
                'destinationResourceArn': f"arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}"
            },
            tags={
                'Project': 'AIML301',
                'Lab': 'Lab-03',
                'ManagedBy': 'Workshop'
            }
        )

        result['delivery_destination_arn'] = response['deliveryDestination']['arn']
        print(f"  ✅ Created delivery destination")
        print(f"     ARN: {result['delivery_destination_arn']}")
        print(f"     Target: {log_group_name}")

    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  ℹ️  Delivery destination already exists: {delivery_destination_name}")
        response = logs_client.get_delivery_destination(name=delivery_destination_name)
        result['delivery_destination_arn'] = response['deliveryDestination']['arn']
        print(f"     ARN: {result['delivery_destination_arn']}")
    except Exception as e:
        print(f"  ❌ Failed to create delivery destination: {e}")
        raise

    # Step 4: Create Delivery (Link Source to Destination)
    print("\n📋 Step 4: Creating Delivery (linking source to destination)...")
    try:
        response = logs_client.create_delivery(
            deliverySourceName=delivery_source_name,
            deliveryDestinationArn=result['delivery_destination_arn'],
            tags={
                'Project': 'AIML301',
                'Lab': 'Lab-03',
                'ManagedBy': 'Workshop'
            }
        )

        result['delivery_id'] = response['delivery']['id']
        print(f"  ✅ Created delivery")
        print(f"     ID: {result['delivery_id']}")
        print(f"     ARN: {response['delivery']['arn']}")

    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  ℹ️  Delivery already exists for this source")
        # Find existing delivery
        response = logs_client.describe_deliveries()
        for delivery in response.get('deliveries', []):
            if delivery.get('deliverySourceName') == delivery_source_name:
                result['delivery_id'] = delivery['id']
                print(f"     ID: {result['delivery_id']}")
                break
    except Exception as e:
        print(f"  ⚠️  Warning creating delivery: {e}")
        print("  ℹ️  Delivery may already exist - continuing...")

    # Step 5: Verify Delivery Status
    print("\n📋 Step 5: Verifying delivery status...")
    time.sleep(2)  # Allow AWS to propagate changes

    try:
        response = logs_client.describe_deliveries()

        for delivery in response.get('deliveries', []):
            if delivery.get('deliverySourceName') == delivery_source_name:
                result['delivery_status'] = delivery.get('deliveryStatus', 'UNKNOWN')
                print(f"  ✅ Delivery Status: {result['delivery_status']}")
                print(f"     Source: {delivery.get('deliverySourceName')}")
                print(f"     Destination: {delivery.get('deliveryDestinationArn')}")

                if result['delivery_status'] == 'ENABLED':
                    print("\n  🎉 Delivery is ENABLED - logs should flow to CloudWatch!")
                break

    except Exception as e:
        print(f"  ⚠️  Could not verify delivery status: {e}")

    print("\n" + "=" * 80)
    print("✅ CloudWatch Logs Delivery Configuration Complete")
    print("=" * 80)
    print(f"\n📊 View logs at: {log_group_name}")
    print(f"\n💻 Command to tail logs:")
    print(f"   aws logs tail {log_group_name} --follow --region {region}")
    print()

    return result


def cleanup_runtime_logging(
    runtime_id: str,
    region: str = "us-west-2"
) -> bool:
    """
    Runtime の CloudWatch Logs 配信設定をクリーンアップ。

    以下を削除します:
    - Delivery（source と destination 間のリンク）
    - Delivery Source
    - Delivery Destination
    - Log Group（オプション、デフォルトではコメントアウト）

    Args:
        runtime_id: Runtime ID（ARN の最後のセグメント）
        region: AWS リージョン（デフォルト: us-west-2）

    Returns:
        クリーンアップが成功した場合は True、そうでない場合は False
    """

    print("\n" + "=" * 80)
    print("🧹 Cleaning up CloudWatch Logs Delivery Configuration")
    print("=" * 80)

    logs_client = boto3.client('logs', region_name=region)

    # configure_runtime_logging と同じ命名規則を使用
    short_id = runtime_id.split('-')[-1]
    delivery_source_name = f"aiml301-lab03-src-{short_id}"
    delivery_destination_name = f"aiml301-lab03-dst-{short_id}"
    log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"

    success = True

    # Step 1: Delete Delivery
    print(f"\n📋 Step 1: Deleting delivery for source: {delivery_source_name}...")
    try:
        response = logs_client.describe_deliveries()
        delivery_id = None

        for delivery in response.get('deliveries', []):
            if delivery.get('deliverySourceName') == delivery_source_name:
                delivery_id = delivery['id']
                break

        if delivery_id:
            logs_client.delete_delivery(id=delivery_id)
            print(f"  ✅ Deleted delivery: {delivery_id}")
        else:
            print(f"  ℹ️  No delivery found for source: {delivery_source_name}")

    except Exception as e:
        print(f"  ⚠️  Error deleting delivery: {e}")
        success = False

    # Step 2: Delete Delivery Source
    print(f"\n📋 Step 2: Deleting delivery source: {delivery_source_name}...")
    try:
        logs_client.delete_delivery_source(name=delivery_source_name)
        print(f"  ✅ Deleted delivery source: {delivery_source_name}")
    except logs_client.exceptions.ResourceNotFoundException:
        print(f"  ℹ️  Delivery source not found: {delivery_source_name}")
    except Exception as e:
        print(f"  ⚠️  Error deleting delivery source: {e}")
        success = False

    # Step 3: Delete Delivery Destination
    print(f"\n📋 Step 3: Deleting delivery destination: {delivery_destination_name}...")
    try:
        logs_client.delete_delivery_destination(name=delivery_destination_name)
        print(f"  ✅ Deleted delivery destination: {delivery_destination_name}")
    except logs_client.exceptions.ResourceNotFoundException:
        print(f"  ℹ️  Delivery destination not found: {delivery_destination_name}")
    except Exception as e:
        print(f"  ⚠️  Error deleting delivery destination: {e}")
        success = False

    # ステップ 4: Log Group を削除（オプション - デフォルトではコメントアウト）
    # クリーンアップ中にロググループを削除したい場合はコメントを外す
    print(f"\n📋 Step 4: Deleting log group: {log_group_name}...")
    try:
         logs_client.delete_log_group(logGroupName=log_group_name)
         print(f"  ✅ Deleted log group: {log_group_name}")
    except logs_client.exceptions.ResourceNotFoundException:
         print(f"  ℹ️  Log group not found: {log_group_name}")
    except Exception as e:
         print(f"  ⚠️  Error deleting log group: {e}")
         success = False

    print("\n" + "=" * 80)
    if success:
        print("✅ Cleanup Complete")
    else:
        print("⚠️  Cleanup completed with warnings")
    print("=" * 80)
    print()

    return success


if __name__ == "__main__":
    # 使用例
    import sys

    if len(sys.argv) < 3:
        print("使用方法:")
        print("  ロギングの設定:")
        print("    python configure_logging.py <runtime_arn> <runtime_id>")
        print()
        print("  ロギングのクリーンアップ:")
        print("    python configure_logging.py cleanup <runtime_id>")
        sys.exit(1)

    if sys.argv[1] == "cleanup":
        runtime_id = sys.argv[2]
        cleanup_runtime_logging(runtime_id)
    else:
        runtime_arn = sys.argv[1]
        runtime_id = sys.argv[2]
        configure_runtime_logging(runtime_arn, runtime_id)
