"""
Lambda ターゲット付きの Gateway を作成して設定を保存するセットアップスクリプト

使用方法:
    python setup-gateway.py [--region REGION] [--role-arn ROLE_ARN]

オプション:
    --region REGION      AWS リージョン（現在のセッションリージョンまたは us-east-1 がデフォルト）
    --role-arn ROLE_ARN  信頼関係を持つ IAM ロール ARN（提供されない場合は作成されます）

このスクリプトは以下を行います:
1. サンプルの Refund Lambda 関数を作成（提供されていない場合）
2. OAuth 認証付きの Amazon Bedrock AgentCore Gateway を作成
3. Lambda をターゲットとして Gateway にアタッチ
4. 設定を gateway_config.json に保存

Gateway が既に存在する場合（gateway_config.json から）、再利用されます。
"""

import argparse
import json
import logging
import time
import zipfile
import tempfile
import os
from pathlib import Path
import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient


# Refund Lambda 関数コード（Node.js）
REFUND_LAMBDA_CODE = """
console.log('Loading function');

export const handler = async (event, context) => {
    console.log('event =', JSON.stringify(event));
    console.log('context =', JSON.stringify(context));
    
    var response = undefined;
    
    if (event.body !== undefined) {
        console.log('event.body =', event.body);
        const body = JSON.parse(event.body);
        response = {"status": "Done", "amount": body.amount, "orderId": body.orderId};
    } else {
        // For Gateway direct invocation
        response = {"status": "Done", "amount": event.amount, "orderId": event.orderId};
        return response;
    }
    
    console.log('response =', JSON.stringify(response));
    return {"statusCode": 200, "body": JSON.stringify(response)};
};
"""

# Gateway ターゲット用の Refund ツールスキーマ
REFUND_TOOL_SCHEMA = [
    {
        "name": "refund",
        "description": (
            "Processes customer refunds by validating the refund amount, "
            "customer ID, and reason. Returns a refund ID and confirmation "
            "details upon successful processing."
        ),
        "inputSchema": {
            "type": "object",
            "description": "Input parameters for processing a customer refund",
            "properties": {
                "amount": {
                    "type": "integer",
                    "description": "The refund amount in USD (must be positive)",
                },
                "orderId": {
                    "type": "string",
                    "description": "Unique identifier for the customer requesting the refund",
                },
            },
            "required": ["amount", "orderId"],
        },
    }
]


def load_existing_config() -> dict | None:
    """既存の gateway_config.json が存在し有効な Gateway 情報を持つ場合に読み込む"""
    config_path = Path("gateway_config.json")
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 設定に必要な Gateway フィールドがあるか確認（プレースホルダーでない）
        if config.get("gateway_id") and "<" not in config.get("gateway_id", "<"):
            return config
    except (json.JSONDecodeError, IOError):
        pass

    return None


def get_existing_gateway(
    region: str, gateway_id: str = None, gateway_name: str = None
) -> dict | None:
    """ID または名前で Gateway が存在するか確認し、詳細を返す"""
    boto_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # まず ID で試す
    if gateway_id:
        try:
            gateway = boto_client.get_gateway(gatewayIdentifier=gateway_id)
            if gateway and gateway.get("status") in ["READY", "ACTIVE"]:
                return gateway
        except Exception as exc:
            print(f"  ゲートウェイID {gateway_id} を取得できませんでした: {exc}")

    # 名前で検索を試みる
    if gateway_name:
        try:
            response = boto_client.list_gateways()
            for gw in response.get("items", []):
                if gw.get("name") == gateway_name and gw.get("status") in [
                    "READY",
                    "ACTIVE",
                ]:
                    # 完全な Gateway 詳細を取得
                    full_gw = boto_client.get_gateway(gatewayIdentifier=gw["gatewayId"])
                    return full_gw
        except Exception as exc:
            print(f"  名前でゲートウェイを検索できませんでした: {exc}")

    return None


def get_existing_target(region: str, gateway_id: str, target_name: str) -> dict | None:
    """指定された名前のターゲットが Gateway に存在するか確認"""
    boto_client = boto3.client("bedrock-agentcore-control", region_name=region)

    try:
        response = boto_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        targets = response.get("items", [])
        print(f"  ゲートウェイに {len(targets)} 件の既存ターゲットが見つかりました")
        for target in targets:
            print(f"    - {target.get('name')} (ID: {target.get('targetId')})")
            if target.get("name") == target_name:
                return target
    except Exception as exc:
        print(f"  ゲートウェイターゲットを一覧できませんでした: {exc}")

    return None


def create_refund_lambda(region: str, function_name: str = "RefundLambda") -> str:
    """
    Refund Lambda 関数を作成または更新します。

    Args:
        region: AWS リージョン
        function_name: Lambda 関数の名前

    Returns:
        Lambda 関数の ARN
    """
    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)
    sts_client = boto3.client("sts", region_name=region)

    account_id = sts_client.get_caller_identity()["Account"]

    print(f"\n📦 返金Lambda関数をセットアップ中: {function_name}")
    print("-" * 60)

    # デプロイパッケージを作成（index.mjs を含む zip ファイル）
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
        zip_path = tmp_file.name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # ES モジュールサポートのために .mjs 拡張子を使用
            zipf.writestr("index.mjs", REFUND_LAMBDA_CODE.strip())

    try:
        with open(zip_path, "rb") as f:
            zip_content = f.read()

        # まず既存の関数の更新を試みる
        try:
            lambda_client.update_function_code(
                FunctionName=function_name, ZipFile=zip_content
            )
            print(f"✓ 既存のLambda関数を更新しました: {function_name}")

            # 更新の完了を待機
            waiter = lambda_client.get_waiter("function_updated_v2")
            waiter.wait(FunctionName=function_name)

            response = lambda_client.get_function(FunctionName=function_name)
            return response["Configuration"]["FunctionArn"]

        except lambda_client.exceptions.ResourceNotFoundException:
            # IAM ロール付きの新しい関数を作成
            role_name = f"{function_name}-execution-role"
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

            # 必要に応じて IAM ロールを作成
            try:
                iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(
                        {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {"Service": "lambda.amazonaws.com"},
                                    "Action": "sts:AssumeRole",
                                }
                            ],
                        }
                    ),
                    Description="Execution role for RefundLambda function",
                )
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                )
                print(f"✓ IAMロールを作成しました: {role_name}")
                print("  ⏳ IAMロールの伝播を待機中 (10秒)...")
                time.sleep(10)
            except iam_client.exceptions.EntityAlreadyExistsException:
                print(f"  IAMロールは既に存在します: {role_name}")

            # Node.js 20.x ランタイムで Lambda 関数を作成
            response = lambda_client.create_function(
                FunctionName=function_name,
                Runtime="nodejs20.x",
                Role=role_arn,
                Handler="index.handler",
                Code={"ZipFile": zip_content},
                Description="Sample refund processing Lambda for AgentCore Policy tutorial",
                Timeout=30,
                MemorySize=128,
            )
            print(f"✓ Lambda関数を作成しました: {function_name}")

            # 関数がアクティブになるのを待機
            waiter = lambda_client.get_waiter("function_active_v2")
            waiter.wait(FunctionName=function_name)

            return response["FunctionArn"]

    finally:
        os.remove(zip_path)


def get_default_region() -> str:
    """現在のセッションまたは環境からデフォルトの AWS リージョンを取得"""
    session = boto3.Session()
    return session.region_name or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def setup_gateway(region: str = None, role_arn: str = None):
    """
    Lambda ターゲットとポリシーエンジン付きの AgentCore Gateway をセットアップします。

    Args:
        region: AWS リージョン（デフォルトはセッションリージョンまたは us-east-1）
        role_arn: 信頼関係を持つ IAM ロール ARN（提供されない場合は作成されます）
    """
    # 提供されたリージョンを使用するかデフォルトを取得
    if not region:
        region = get_default_region()

    print("\n🚀 AgentCore Gatewayをセットアップ中...")
    print(f"リージョン:      {region}\n")

    # クライアントを初期化
    client = GatewayClient(region_name=region)
    client.logger.setLevel(logging.INFO)

    # このチュートリアルで使用する Gateway とターゲット名
    gateway_name = "TestGWforPolicyEngine"
    target_name = "RefundToolTarget"
    lambda_function_name = "RefundLambda"

    # 既存の設定または Gateway を確認
    existing_config = load_existing_config()
    gateway = None
    cognito_response = None
    lambda_arn = None

    if existing_config:
        print("📋 既存のgateway_config.jsonを検出")
        gateway_id = existing_config.get("gateway_id")

        # 既存の Gateway の取得を試みる
        print(f"  ゲートウェイ '{gateway_id}' が存在するか確認中...")
        gateway = get_existing_gateway(region, gateway_id=gateway_id)

        if gateway:
            print(
                f"✓ 既存のゲートウェイを再利用: {gateway.get('gatewayUrl', gateway_id)}\n"
            )
            # 利用可能な場合は既存の client_info を再利用
            if existing_config.get("client_info"):
                cognito_response = {"client_info": existing_config["client_info"]}

            # Lambda ARN が設定に保存されているか確認
            lambda_arn = existing_config.get("lambda_arn")
        else:
            print(f"  ゲートウェイ '{gateway_id}' が見つからないか準備ができていません。\n")

    # まだ Gateway がない場合、名前で存在するか確認
    if not gateway:
        print(f"🔍 '{gateway_name}' という名前の既存ゲートウェイを確認中...")
        gateway = get_existing_gateway(region, gateway_name=gateway_name)
        if gateway:
            print(f"✓ 既存のゲートウェイを検出: {gateway.get('gatewayUrl')}\n")

    # Lambda 関数を作成または取得
    if not lambda_arn:
        print("\n" + "=" * 60)
        print("ステップ1: 返金Lambda関数のセットアップ")
        print("=" * 60)
        lambda_arn = create_refund_lambda(region, lambda_function_name)
        print(f"✓ Lambda ARN: {lambda_arn}\n")
    else:
        print(f"\n✓ 既存のLambda ARNを使用: {lambda_arn}\n")

    # 既存の client_info がない場合は OAuth 認可サーバーを作成
    if not cognito_response:
        print("=" * 60)
        print("ステップ2: OAuth認証サーバーの作成")
        print("=" * 60)
        cognito_response = client.create_oauth_authorizer_with_cognito("TestGateway")
        print("✓ 認証サーバーを作成しました\n")

    # 既存の Gateway がない場合は作成
    if not gateway:
        print("=" * 60)
        print("ステップ3: ゲートウェイの作成")
        print("=" * 60)
        gateway = client.create_mcp_gateway(
            name=gateway_name,
            role_arn=role_arn,
            authorizer_config=cognito_response.get("authorizer_config"),
            enable_semantic_search=True,
        )
        print(f"✓ ゲートウェイを作成しました: {gateway['gatewayUrl']}\n")
    else:
        print("=" * 60)
        print("ステップ3: ゲートウェイ作成をスキップ（既存を再利用）")
        print("=" * 60 + "\n")

    # ターゲットが既に存在するか確認し、存在しない場合は追加
    print("=" * 60)
    print("ステップ4: Lambdaターゲットの追加")
    print("=" * 60)

    gateway_id = gateway.get("gatewayId")
    print(f"  ゲートウェイID: {gateway_id}")
    print(f"  ターゲット名: {target_name}")
    print(f"  Lambda ARN: {lambda_arn}")

    existing_target = get_existing_target(region, gateway_id, target_name)

    if existing_target:
        print(f"✓ Lambdaターゲット '{target_name}' は既に存在、再利用します")
        print(f"  ターゲットID: {existing_target.get('targetId')}")
        lambda_target = {"gatewayArn": gateway.get("gatewayArn")}
    else:
        print(f"  ターゲット '{target_name}' が見つかりません、作成中...")
        try:
            lambda_target = client.create_mcp_gateway_target(
                gateway=gateway,
                name=target_name,
                target_type="lambda",
                target_payload={
                    "lambdaArn": lambda_arn,
                    "toolSchema": {"inlinePayload": REFUND_TOOL_SCHEMA},
                },
                credentials=None,
            )
            print(f"✓ Lambdaターゲット '{target_name}' を作成しゲートウェイにアタッチしました\n")
        except Exception as exc:
            error_str = str(exc)
            if (
                "ConflictException" in str(type(exc).__name__)
                or "already exists" in error_str
            ):
                print(f"✓ Lambdaターゲット '{target_name}' は既に存在、再利用します\n")
                lambda_target = {"gatewayArn": gateway.get("gatewayArn")}
            else:
                print(f"✗ ターゲット作成エラー: {exc}")
                raise

    # 設定を保存
    config = {
        "gateway_url": gateway.get("gatewayUrl"),
        "gateway_id": gateway.get("gatewayId"),
        "gateway_arn": lambda_target.get("gatewayArn") or gateway.get("gatewayArn"),
        "region": region,
        "client_info": cognito_response.get("client_info"),
        "lambda_arn": lambda_arn,
    }

    with open("gateway_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("\n" + "=" * 60)
    print("✅ ゲートウェイのセットアップが完了しました！")
    print("=" * 60)
    print(f"ゲートウェイ URL: {config['gateway_url']}")
    print(f"ゲートウェイ ID: {config['gateway_id']}")
    print(f"ゲートウェイ ARN: {config['gateway_arn']}")
    print(f"Lambda ARN:      {config['lambda_arn']}")
    print("\n設定をgateway_config.jsonに保存しました")
    print("=" * 60)

    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Setup AgentCore Gateway with Lambda target for Policy tutorial"
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="AWS region (defaults to current session region or us-east-1)",
    )
    parser.add_argument(
        "--role-arn",
        type=str,
        default=None,
        help="IAM role ARN with trust relationship (creates one if not provided)",
    )

    args = parser.parse_args()
    setup_gateway(region=args.region, role_arn=args.role_arn)
