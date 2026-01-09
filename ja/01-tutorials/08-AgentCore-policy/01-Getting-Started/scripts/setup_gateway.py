"""
保険引受用の Lambda ターゲット付き Gateway を作成するセットアップスクリプト
deploy_lambdas.py で Lambda 関数をデプロイした後に実行してください
"""

import json
import logging
import sys
import time
from pathlib import Path
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient


def load_config():
    """既存の config.json を読み込む"""
    config_file = Path(__file__).parent.parent / "config.json"

    if not config_file.exists():
        print("❌ エラー: config.json が見つかりません!")
        print(f"   期待される場所: {config_file}")
        print("\n   最初に deploy_lambdas.py を実行して Lambda 関数を作成してください")
        sys.exit(1)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f), config_file
    except Exception as exc:
        print(f"❌ config.json の読み取りエラー: {exc}")
        sys.exit(1)


def setup_gateway():
    """保険引受 Lambda ターゲットで AgentCore Gateway をセットアップ"""

    # 設定
    region = "us-east-1"

    print("🚀 保険引受用の AgentCore Gateway をセットアップ中...")
    print(f"リージョン:      {region}\n")

    # 既存の設定を読み込み
    print("📦 設定を読み込み中...")
    existing_config, config_file = load_config()
    lambda_config = existing_config.get("lambdas", {})

    if not lambda_config:
        print("❌ config.json に Lambda 関数が見つかりません")
        sys.exit(1)

    print("✅ Lambda 関数が見つかりました:")
    for name, arn in lambda_config.items():
        print(f"   • {name}: {arn}")
    print()

    # クライアントを初期化
    print("🔧 AgentCore クライアントを初期化中...")
    client = GatewayClient(region_name=region)
    client.logger.setLevel(logging.INFO)

    # ステップ 1: OAuth 認可サーバーを作成
    print("\n📝 ステップ 1: OAuth 認可サーバーを作成中...")
    cognito_response = client.create_oauth_authorizer_with_cognito(
        "InsuranceUnderwritingGateway"
    )
    print("✅ 認可サーバーを作成しました")

    # ステップ 2: Gateway を作成（ロールは自動作成されます）
    print("\n📝 ステップ 2: AgentCore Gateway を作成中...")
    gateway = client.create_mcp_gateway(
        name="GW-Insurance-Underwriting",
        role_arn=None,  # Let the toolkit create the role
        authorizer_config=cognito_response["authorizer_config"],
        enable_semantic_search=True,
    )
    print(f"✅ Gateway を作成しました: {gateway['gatewayUrl']}")

    # 自動作成されたロールの IAM 権限を修正
    print("\n📝 ステップ 2.1: IAM 権限を設定中...")
    client.fix_iam_permissions(gateway)
    print("⏳ IAM の伝播を待機中 (30秒)...")
    time.sleep(30)
    print("✅ IAM 権限を設定しました")

    # ステップ 3: Lambda ターゲットを追加
    print("\n📝 ステップ 3: Lambda ターゲットを追加中...")

    # スキーマ付きの Lambda 関数を定義
    lambda_functions = []

    # ApplicationTool - ステージ 1: 申請書提出
    if "ApplicationTool" in lambda_config:
        lambda_functions.append(
            {
                "name": "ApplicationTool",
                "arn": lambda_config["ApplicationTool"],
                "schema": [
                    {
                        "name": "create_application",
                        "description": "Create insurance application with geographic and eligibility validation",
                        "inputSchema": {
                            "type": "object",
                            "description": "Input parameters for insurance application creation",
                            "properties": {
                                "applicant_region": {
                                    "type": "string",
                                    "description": "Customer's geographic region (US, CA, UK, EU, APAC, etc.)",
                                },
                                "coverage_amount": {
                                    "type": "integer",
                                    "description": "Requested insurance coverage amount",
                                },
                            },
                            "required": ["applicant_region", "coverage_amount"],
                        },
                    }
                ],
            }
        )

    # RiskModelTool - ステージ 3: 外部スコアリング統合
    if "RiskModelTool" in lambda_config:
        lambda_functions.append(
            {
                "name": "RiskModelTool",
                "arn": lambda_config["RiskModelTool"],
                "schema": [
                    {
                        "name": "invoke_risk_model",
                        "description": "Invoke external risk scoring model with governance controls",
                        "inputSchema": {
                            "type": "object",
                            "description": "Input parameters for risk model invocation",
                            "properties": {
                                "API_classification": {
                                    "type": "string",
                                    "description": "API classification (public, internal, restricted)",
                                },
                                "data_governance_approval": {
                                    "type": "boolean",
                                    "description": "Whether data governance has approved model usage",
                                },
                            },
                            "required": [
                                "API_classification",
                                "data_governance_approval",
                            ],
                        },
                    }
                ],
            }
        )

    # ApprovalTool - ステージ 7: 上席承認
    if "ApprovalTool" in lambda_config:
        lambda_functions.append(
            {
                "name": "ApprovalTool",
                "arn": lambda_config["ApprovalTool"],
                "schema": [
                    {
                        "name": "approve_underwriting",
                        "description": "Approve high-value or high-risk underwriting decisions",
                        "inputSchema": {
                            "type": "object",
                            "description": "Input parameters for underwriting approval",
                            "properties": {
                                "claim_amount": {
                                    "type": "integer",
                                    "description": "Insurance claim/coverage amount",
                                },
                                "risk_level": {
                                    "type": "string",
                                    "description": "Risk level assessment (low, medium, high, critical)",
                                },
                            },
                            "required": ["claim_amount", "risk_level"],
                        },
                    }
                ],
            }
        )

    # 各 Lambda ターゲットを Gateway に追加
    gateway_arn = None
    for lambda_func in lambda_functions:
        print(f"\n   🔧 {lambda_func['name']} ターゲットを追加中...")

        try:
            target = client.create_mcp_gateway_target(
                gateway=gateway,
                name=f"{lambda_func['name']}Target",
                target_type="lambda",
                target_payload={
                    "lambdaArn": lambda_func["arn"],
                    "toolSchema": {"inlinePayload": lambda_func["schema"]},
                },
                credentials=None,
            )

            if gateway_arn is None:
                gateway_arn = target.get("gatewayArn")

            print(f"   ✅ {lambda_func['name']} ターゲットを正常に追加しました")

        except Exception as e:
            print(f"   ❌ {lambda_func['name']} ターゲットの追加エラー: {e}")

    # ステップ 4: Gateway 情報で既存の config.json を更新
    print("\n📝 ステップ 4: Gateway 情報で config.json を更新中...")

    # 既存の設定に Gateway 設定を追加
    existing_config["gateway"] = {
        "gateway_url": gateway["gatewayUrl"],
        "gateway_id": gateway["gatewayId"],
        "gateway_arn": gateway_arn or gateway.get("gatewayArn"),
        "gateway_name": "GW-Insurance-Underwriting",
        "client_info": cognito_response["client_info"],
    }

    # 更新した設定を config.json に書き戻し
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(existing_config, f, indent=2)

    print("\n" + "=" * 70)
    print("✅ GATEWAY セットアップ完了!")
    print("=" * 70)
    print("Gateway 名: GW-Insurance-Underwriting")
    print(f"ゲートウェイ URL: {gateway['gatewayUrl']}")
    print(f"ゲートウェイ ID: {gateway['gatewayId']}")
    print(f"ゲートウェイ ARN: {existing_config['gateway']['gateway_arn']}")
    print(f"\n追加されたターゲット: {len(lambda_functions)}")
    for func in lambda_functions:
        print(f"   • {func['name']}")
    print(f"\n設定を更新しました: {config_file}")
    print("=" * 70)

    return existing_config


if __name__ == "__main__":
    setup_gateway()
