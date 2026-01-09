"""
Gateway 呼び出しを許可するために Lambda 関数にリソースベースの権限を追加
これは Gateway 呼び出しの問題に対する最も一般的な修正です
"""

import boto3
import json


def add_lambda_permissions():
    """Gateway が Lambda 関数を呼び出すための権限を追加"""

    print("🔧 Gateway 用の Lambda 権限を追加中\n")
    print("=" * 70)

    # Gateway 設定を読み込み
    with open("gateway_config.json", "r") as f:
        gateway_config = json.load(f)

    region = gateway_config["region"]
    gateway_arn = gateway_config["gateway_arn"]
    gateway_account = gateway_arn.split(":")[4]

    print(f"ゲートウェイ ARN: {gateway_arn}\n")

    # Lambda クライアントを初期化
    lambda_client = boto3.client("lambda", region_name=region)

    # 更新する Lambda 関数
    functions = ["ApplicationTool", "RiskModelTool", "ApprovalTool"]

    for function_name in functions:
        print(f"🔧 {function_name}:")

        try:
            # 関数が存在するか確認
            lambda_client.get_function(FunctionName=function_name)

            # 権限の追加を試みる
            try:
                lambda_client.add_permission(
                    FunctionName=function_name,
                    StatementId="AllowAgentCoreGateway",
                    Action="lambda:InvokeFunction",
                    Principal="bedrock-agentcore.amazonaws.com",
                    SourceArn=gateway_arn,
                )
                print("   ✅ 権限を追加しました")

            except lambda_client.exceptions.ResourceConflictException:
                print("   ℹ️  権限は既に存在します")

                # 削除して再追加することで更新を試みる
                try:
                    lambda_client.remove_permission(
                        FunctionName=function_name, StatementId="AllowAgentCoreGateway"
                    )

                    lambda_client.add_permission(
                        FunctionName=function_name,
                        StatementId="AllowAgentCoreGateway",
                        Action="lambda:InvokeFunction",
                        Principal="bedrock-agentcore.amazonaws.com",
                        SourceArn=gateway_arn,
                    )
                    print("   ✅ 権限を更新しました")

                except Exception as update_error:
                    print(f"   ⚠️  権限を更新できませんでした: {update_error}")

        except lambda_client.exceptions.ResourceNotFoundException:
            print(f"   ❌ アカウント {gateway_account} に関数が見つかりません")
            print("   → 先に Lambda をデプロイしてください")

        except Exception as e:
            print(f"   ❌ エラー: {e}")

        print()

    print("=" * 70)
    print("\n✅ 権限の更新が完了しました!")
    print("\n次のステップ:")
    print("1. Gateway の呼び出しをテスト")
    print("2. まだ失敗する場合は、Lambda 関数の CloudWatch ログを確認")
    print("3. Gateway の IAM ロールに lambda:InvokeFunction 権限があることを確認")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    add_lambda_permissions()
