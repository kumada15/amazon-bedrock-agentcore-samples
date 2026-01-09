import boto3
import time
from botocore.exceptions import ClientError


def deploy_stack(stack_name, template_file, region, cf_client):
    """
    カスタマーサポート Lambda 用の CloudFormation スタックをデプロイまたは更新し、出力を返します。

    Args:
        stack_name (str): CloudFormation スタック名
        template_file (str): CloudFormation テンプレート YAML ファイルへのパス
        region (str): AWS リージョン
        cf_client: Boto3 CloudFormation クライアント

    Returns:
        tuple: (lambda_arn, gateway_role_arn, runtime_execution_role_arn)
    """

    # テンプレートファイルを読み込み
    try:
        with open(template_file, "r") as f:
            template_body = f.read()
        print(f"✅ テンプレートファイルを正常に読み込みました: {template_file}")
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ テンプレートファイルが見つかりません: {template_file}")
    except Exception as e:
        raise Exception(f"❌ テンプレートファイルの読み込みエラー: {str(e)}")

    # スタックが存在するか確認
    stack_exists = False
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stack_status = response["Stacks"][0]["StackStatus"]
        stack_exists = True
        print(f"📋 スタック '{stack_name}' が存在します、状態: {stack_status}")

        # スタックが失敗状態か確認
        if stack_status in ["CREATE_FAILED", "ROLLBACK_COMPLETE", "ROLLBACK_FAILED"]:
            print(
                f"⚠️  スタックは {stack_status} 状態です。先に削除が必要な場合があります。"
            )

    except ClientError as e:
        if "does not exist" in str(e):
            print(f"🆕 スタック '{stack_name}' は存在しません。新規スタックを作成します...")
        else:
            raise

    try:
        if stack_exists:
            # 既存スタックを更新
            print(f"🔄 スタック '{stack_name}' を更新中...")
            response = cf_client.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
                Tags=[
                    {"Key": "Application", "Value": "CustomerSupport"},
                    {"Key": "ManagedBy", "Value": "CloudFormation"},
                ],
            )
            print(f"✅ スタック更新を開始しました。スタック ID: {response['StackId']}")
            waiter = cf_client.get_waiter("stack_update_complete")
            wait_message = "スタック更新の完了を待機中"

        else:
            # 新規スタックを作成
            print(f"🚀 スタック '{stack_name}' を作成中...")
            response = cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
                Tags=[
                    {"Key": "Application", "Value": "CustomerSupport"},
                    {"Key": "ManagedBy", "Value": "CloudFormation"},
                ],
                OnFailure="ROLLBACK",
            )
            print(f"✅ スタック作成を開始しました。スタック ID: {response['StackId']}")
            waiter = cf_client.get_waiter("stack_create_complete")
            wait_message = "スタック作成の完了を待機中"

        # 進捗状況を表示しながらスタック操作の完了を待機
        print(f"⏳ {wait_message}...")
        print("   以下を作成するため、数分かかる場合があります:")
        print("   - DynamoDB テーブル (WarrantyTable, CustomerProfileTable)")
        print("   - IAM ロール (AgentCore, Gateway, Lambda ロール)")
        print("   - Lambda 関数 (CustomerSupportLambda, PopulateDataFunction)")
        print("   - 合成データを投入するカスタムリソース")

        waiter.wait(
            StackName=stack_name,
            WaiterConfig={
                "Delay": 15,  # Check every 15 seconds
                "MaxAttempts": 120,  # Wait up to 30 minutes
            },
        )
        print("✅ スタック操作が正常に完了しました！")

    except ClientError as e:
        error_message = str(e)

        if "No updates are to be performed" in error_message:
            print("ℹ️  更新は不要です - スタックは既に最新です。")
        elif "ValidationError" in error_message:
            print(f"❌ 検証エラー: {error_message}")
            raise
        else:
            print(f"❌ スタック操作中のエラー: {error_message}")
            # デバッグ用にスタックイベントを取得
            try:
                print("\n📋 最近のスタックイベント:")
                events = cf_client.describe_stack_events(StackName=stack_name)
                for event in events["StackEvents"][:5]:
                    if "FAILED" in event.get("ResourceStatus", ""):
                        print(
                            f"   ❌ {event['LogicalResourceId']}: {event.get('ResourceStatusReason', 'No reason provided')}"
                        )
            except Exception:
                pass
            raise
    except Exception as e:
        print(f"❌ 予期しないエラー: {str(e)}")
        raise

    # スタック出力を取得
    print("\n📤 スタック出力を取得中...")
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0].get("Outputs", [])

        if not outputs:
            raise Exception(
                "❌ スタックに出力が見つかりません。スタックが正常に作成されなかった可能性があります。"
            )

        # テンプレートに基づいて特定の出力を抽出
        lambda_arn = None
        gateway_role_arn = None
        runtime_execution_role_arn = None

        for output in outputs:
            key = output["OutputKey"]
            value = output["OutputValue"]

            if key == "CustomerSupportLambdaArn":
                lambda_arn = value
                print(f"   ✅ Lambda ARN: {value}")
            elif key == "GatewayAgentCoreRoleArn":
                gateway_role_arn = value
                print(f"   ✅ Gateway Role ARN: {value}")
            elif key == "AgentCoreRuntimeExecutionRoleArn":
                runtime_execution_role_arn = value
                print(f"   ✅ Runtime Execution Role ARN: {value}")

        # 必要な出力がすべて見つかったか確認
        missing_outputs = []
        if not lambda_arn:
            missing_outputs.append("CustomerSupportLambdaArn")
        if not gateway_role_arn:
            missing_outputs.append("GatewayAgentCoreRoleArn")
        if not runtime_execution_role_arn:
            missing_outputs.append("AgentCoreRuntimeExecutionRoleArn")

        if missing_outputs:
            raise Exception(
                f"❌ 必要な出力が不足しています: {', '.join(missing_outputs)}"
            )

        print("\n🎉 スタックのデプロイが正常に完了しました！")
        print(f"   スタック名: {stack_name}")
        print(f"   リージョン: {region}")

        return lambda_arn, gateway_role_arn, runtime_execution_role_arn

    except ClientError as e:
        print(f"❌ スタック出力の取得エラー: {str(e)}")
        raise
    except Exception as e:
        print(f"❌ スタック出力の処理エラー: {str(e)}")
        raise


def delete_stack(stack_name, region, cf_client, wait=True):
    """
    CloudFormation スタックとそのすべてのリソースを削除します。

    Args:
        stack_name (str): 削除する CloudFormation スタック名
        region (str): AWS リージョン
        cf_client: Boto3 CloudFormation クライアント
        wait (bool): 削除完了を待機するかどうか（デフォルト: True）

    Returns:
        bool: 削除が成功した場合は True、それ以外は False
    """

    print(f"🗑️  スタックの削除を準備中: {stack_name}")
    print(f"   リージョン: {region}")
    print("=" * 80)

    # スタックが存在するか確認
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stack_status = response["Stacks"][0]["StackStatus"]
        print(f"📋 現在のスタック状態: {stack_status}")

        # スタックが既に削除中か確認
        if stack_status == "DELETE_IN_PROGRESS":
            print("⏳ スタック削除は既に進行中...")
            if wait:
                return _wait_for_deletion(stack_name, cf_client)
            return True

        # スタックが失敗状態か確認
        if stack_status == "DELETE_FAILED":
            print(
                "⚠️  スタックは DELETE_FAILED 状態です。削除を再試行します..."
            )

    except ClientError as e:
        if "does not exist" in str(e):
            print(f"ℹ️  スタック '{stack_name}' は存在しません。削除するものはありません。")
            return True
        else:
            print(f"❌ スタック状態の確認エラー: {str(e)}")
            raise

    # 報告用に削除前のリソースを取得
    try:
        print("\n📦 削除されるリソース:")
        resources = cf_client.list_stack_resources(StackName=stack_name)
        resource_summary = {}

        for resource in resources["StackResourceSummaries"]:
            resource_type = resource["ResourceType"]
            logical_id = resource["LogicalResourceId"]
            physical_id = resource.get("PhysicalResourceId", "N/A")

            if resource_type not in resource_summary:
                resource_summary[resource_type] = []
            resource_summary[resource_type].append(
                {"logical": logical_id, "physical": physical_id}
            )

        for resource_type, items in sorted(resource_summary.items()):
            print(f"\n   {resource_type}:")
            for item in items:
                print(f"      - {item['logical']}")
                if resource_type == "AWS::DynamoDB::Table":
                    print(
                        f"        ⚠️  テーブル: {item['physical']} (すべてのデータが削除されます)"
                    )
                elif resource_type == "AWS::Lambda::Function":
                    print(f"        🔧 関数: {item['physical']}")
                elif resource_type == "AWS::IAM::Role":
                    print(f"        🔐 ロール: {item['physical']}")

        # DynamoDB テーブルにデータがあるか確認
        dynamodb_tables = resource_summary.get("AWS::DynamoDB::Table", [])
        if dynamodb_tables:
            print(
                f"\n⚠️  警告: {len(dynamodb_tables)} 件の DynamoDB テーブルとすべてのデータが削除されます！"
            )
            dynamodb = boto3.client("dynamodb", region_name=region)
            for table in dynamodb_tables:
                try:
                    table_name = table["physical"]
                    response = dynamodb.scan(
                        TableName=table_name, Select="COUNT", Limit=1
                    )
                    if response["Count"] > 0:
                        print(f"      ⚠️  {table_name} にはデータがあります！")
                except Exception:
                    pass

    except ClientError as e:
        print(f"⚠️  リソースを一覧できませんでした: {str(e)}")

    # 削除の確認
    print("\n" + "=" * 80)
    print("⚠️  この操作は取り消せません！")
    print("=" * 80)

    # スタック削除を開始
    try:
        print("\n🚀 スタック削除を開始中...")
        cf_client.delete_stack(StackName=stack_name)
        print("✅ 削除リクエストが正常に送信されました")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "ValidationError" and "does not exist" in error_message:
            print(f"ℹ️  スタック '{stack_name}' は存在しません。")
            return True
        else:
            print(f"❌ スタック削除開始エラー: {error_message}")
            return False

    # リクエストされた場合は削除を待機
    if wait:
        return _wait_for_deletion(stack_name, cf_client)
    else:
        print("\nℹ️  スタック削除を開始しましたが、完了を待機しません。")
        return True


def _wait_for_deletion(stack_name, cf_client, max_wait_minutes=30):
    """
    スタック削除の完了を待機する内部関数。

    Args:
        stack_name (str): スタック名
        cf_client: CloudFormation クライアント
        max_wait_minutes (int): 最大待機時間（分）

    Returns:
        bool: 削除が正常に完了した場合は True
    """
    print("\n⏳ スタック削除の完了を待機中...")
    print(f"   最大 {max_wait_minutes} 分かかる場合があります")
    print("   15秒ごとに状態を確認中...")

    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    check_interval = 15
    last_status = None
    dots = 0

    try:
        while True:
            elapsed = time.time() - start_time

            if elapsed > max_wait_seconds:
                print(
                    f"\n⚠️  タイムアウト: スタック削除が {max_wait_minutes} 分以上かかりました"
                )
                print("   現在の状態は AWS コンソールで確認してください")
                return False

            try:
                response = cf_client.describe_stacks(StackName=stack_name)
                current_status = response["Stacks"][0]["StackStatus"]

                # 状態が変化した場合は表示
                if current_status != last_status:
                    print(f"\n   状態: {current_status}")
                    last_status = current_status
                    dots = 0
                else:
                    # 進捗を示すドットを表示
                    print(".", end="", flush=True)
                    dots += 1
                    if dots >= 20:
                        print()
                        dots = 0

                # 削除失敗を確認
                if current_status == "DELETE_FAILED":
                    print("\n❌ スタック削除に失敗しました！")
                    _print_deletion_errors(stack_name, cf_client)
                    return False

                # まだ削除中
                if current_status == "DELETE_IN_PROGRESS":
                    time.sleep(check_interval)
                    continue

                # 予期しない状態
                print(f"\n⚠️  予期しない状態: {current_status}")
                return False

            except ClientError as e:
                if "does not exist" in str(e):
                    # スタックが正常に削除された
                    print(f"\n✅ スタック '{stack_name}' が正常に削除されました！")
                    elapsed_minutes = elapsed / 60
                    print(f"   合計時間: {elapsed_minutes:.1f} 分")
                    return True
                else:
                    # その他のエラー
                    print(f"\n❌ スタック状態確認エラー: {str(e)}")
                    return False

    except KeyboardInterrupt:
        print("\n\n⚠️  削除監視がユーザーによって中断されました")
        print("   スタック削除はバックグラウンドで継続されます")
        return False


def _print_deletion_errors(stack_name, cf_client):
    """
    スタック削除失敗の詳細エラーメッセージを表示する内部関数。
    """
    try:
        print("\n📋 削除失敗の詳細:")
        events = cf_client.describe_stack_events(StackName=stack_name)

        failed_events = [
            event
            for event in events["StackEvents"]
            if "FAILED" in event.get("ResourceStatus", "")
        ]

        if failed_events:
            for event in failed_events[:10]:  # Show last 10 failed events
                resource_type = event.get("ResourceType", "Unknown")
                logical_id = event.get("LogicalResourceId", "Unknown")
                reason = event.get("ResourceStatusReason", "No reason provided")

                print(f"\n   ❌ {resource_type} - {logical_id}")
                print(f"      理由: {reason}")

        print("\n💡 トラブルシューティングのヒント:")
        print("   1. 一部のリソースに削除を妨げる依存関係がある可能性があります")
        print("   2. DynamoDB テーブルの削除保護が有効になっていないか確認してください")
        print("   3. Lambda 関数が呼び出し中でないか確認してください")
        print("   4. 数分後にスタックの削除を再試行してください")

    except Exception as e:
        print(f"   エラー詳細を取得できませんでした: {str(e)}")


# ============================================================================
# 使用例
# ============================================================================

if __name__ == "__main__":
    import boto3

    # 初期化
    session = boto3.Session()
    region = session.region_name
    stack_name = "customer-support-lambda-stack"
    template_file = "cloudformation/customer_support_lambda.yaml"
    cf_client = boto3.client("cloudformation", region_name=region)

    print("=" * 80)
    print("CLOUDFORMATION スタック管理")
    print("=" * 80)

    # CloudFormation スタックをデプロイ
    print("\n🚀 スタックをデプロイ中...")
    print("=" * 80)

    try:
        lambda_arn, gateway_role_arn, runtime_execution_role_arn = deploy_stack(
            stack_name=stack_name,
            template_file=template_file,
            region=region,
            cf_client=cf_client,
        )

        print("\n" + "=" * 80)
        print("📋 デプロイサマリー")
        print("=" * 80)
        print("\n🔧 Lambda 関数 ARN:")
        print(f"   {lambda_arn}")
        print("\n🔐 Gateway ロール ARN:")
        print(f"   {gateway_role_arn}")
        print("\n🔐 Runtime 実行ロール ARN:")
        print(f"   {runtime_execution_role_arn}")

    except Exception as e:
        print(f"\n❌ デプロイに失敗しました: {str(e)}")
        exit(1)

    # オプション: スタックを削除するにはコメントを解除
    # print("\n\n🗑️  スタックを削除中...")
    # print("=" * 80)
    #
    # success = delete_stack(
    #     stack_name=stack_name,
    #     region=region,
    #     cf_client=cf_client,
    #     wait=True
    # )
    #
    # if success:
    #     print("\n🎉 スタックが正常に削除されました！")
    # else:
    #     print("\n❌ スタック削除に失敗しました")
