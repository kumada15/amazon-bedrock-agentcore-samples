"""
AWS Systems Manager Parameter Store ユーティリティ

このモジュールは、設定パラメータを取得するために AWS Systems Manager Parameter Store
と対話するための関数を提供します。パラメータは '/agentcore-data-analyst-assistant/'
プレフィックスの後にパラメータ名を付けて保存されます。

パラメータ:
- SECRET_ARN: データベース認証情報を含む AWS Secrets Manager シークレットの ARN
- AURORA_RESOURCE_ARN: Aurora Serverless クラスターの ARN
- DATABASE_NAME: 接続するデータベースの名前
- MEMORY_ID: 会話コンテキスト管理用の AgentCore Memory ID
- QUESTION_ANSWERS_TABLE: クエリ結果を保存する DynamoDB テーブル
- MAX_RESPONSE_SIZE_BYTES: クエリレスポンスの最大サイズ（バイト単位、デフォルト: 25600）
"""

import boto3
import os
from botocore.exceptions import ClientError

# SSM パラメータパスプレフィックス用のプロジェクト ID
PROJECT_ID = os.environ.get("PROJECT_ID", "agentcore-data-analyst-assistant")


def get_ssm_client():
    """
    デフォルトの AWS 設定を使用して SSM クライアントを作成して返す。

    Returns:
        boto3.client: SSM クライアント
    """
    return boto3.client("ssm")


def get_ssm_parameter(param_name):
    """
    AWS Systems Manager Parameter Store からパラメータを取得する。

    Args:
        param_name: プロジェクトプレフィックスなしのパラメータ名

    Returns:
        str: パラメータの値

    Raises:
        ClientError: パラメータの取得中にエラーが発生した場合
    """
    client = get_ssm_client()
    full_param_name = f"/{PROJECT_ID}/{param_name}"

    try:
        response = client.get_parameter(Name=full_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        print("\n" + "=" * 70)
        print("❌ SSM パラメータ取得エラー")
        print("=" * 70)
        print(f"📋 パラメータ: {full_param_name}")
        print(f"💥 エラー: {e}")
        print("=" * 70 + "\n")
        raise


def load_config():
    """
    SSM からすべての必須設定パラメータを読み込む。

    Returns:
        dict: すべてのパラメータを含む設定辞書

    Note:
        必須パラメータが見つからない場合は ValueError を発生させます。
        オプションパラメータが見つからない場合は None またはデフォルト値に設定されます。
    """
    # 読み込むパラメータを定義
    param_keys = [
        "SECRET_ARN",
        "AURORA_RESOURCE_ARN",
        "DATABASE_NAME",
        "QUESTION_ANSWERS_TABLE",
        "MAX_RESPONSE_SIZE_BYTES",
        "MEMORY_ID",
    ]

    config = {}

    # 各パラメータを読み込み
    for key in param_keys:
        try:
            value = get_ssm_parameter(key)
            # 特定のパラメータは int に変換
            if key in ["MAX_RESPONSE_SIZE_BYTES"]:
                config[key] = int(value)
            else:
                config[key] = value
        except ClientError:
            # MAX_RESPONSE_SIZE_BYTES が見つからない場合はデフォルト値を使用
            if key == "MAX_RESPONSE_SIZE_BYTES":
                config[key] = 25600
            # オプションパラメータが見つからない場合は None に設定
            elif key in ["QUESTION_ANSWERS_TABLE"]:
                config[key] = None
            # 必須パラメータの場合は例外を発生
            elif key in [
                "SECRET_ARN",
                "AURORA_RESOURCE_ARN",
                "DATABASE_NAME",
                "MEMORY_ID",
            ]:
                raise ValueError(
                    f"必須の SSM パラメータ /{PROJECT_ID}/{key} が見つかりません"
                )

    return config
