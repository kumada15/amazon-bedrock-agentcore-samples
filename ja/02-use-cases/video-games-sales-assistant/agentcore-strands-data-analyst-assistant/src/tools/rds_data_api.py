"""
RDS Data API ユーティリティ

このモジュールは、RDS Data API を使用して Amazon Aurora Serverless PostgreSQL
データベースと対話するための関数を提供します。設定の読み込み、クエリの実行、
結果のフォーマットを処理します。

設定は AWS Systems Manager Parameter Store から以下の必須パラメータで読み込まれます:
- SECRET_ARN: データベース認証情報を含む AWS Secrets Manager シークレットの ARN
- AURORA_RESOURCE_ARN: Aurora Serverless クラスターの ARN
- DATABASE_NAME: 接続するデータベースの名前

オプションパラメータ:
- MAX_RESPONSE_SIZE_BYTES: レスポンスの最大サイズ（バイト単位、デフォルト: 25600）
"""

import boto3
import json
from botocore.exceptions import ClientError
from decimal import Decimal
from src.utils import load_config

# SSM パラメータから設定を読み込み
try:
    CONFIG = load_config()
except Exception as e:
    print("\n" + "=" * 70)
    print("❌ 設定読み込みエラー")
    print("=" * 70)
    print(f"💥 SSM からの設定読み込みエラー: {e}")
    print("=" * 70 + "\n")
    CONFIG = {}


def validate_configuration():
    """
    すべての必須設定パラメータが存在することを検証する。

    Raises:
        ValueError: 必須の設定パラメータが不足している場合
    """
    required_params = ["SECRET_ARN", "AURORA_RESOURCE_ARN", "DATABASE_NAME"]
    missing_params = [
        param for param in required_params if param not in CONFIG or not CONFIG[param]
    ]

    if missing_params:
        raise ValueError(
            f"Missing required configuration parameters: {', '.join(missing_params)}"
        )


def get_rds_data_client():
    """
    デフォルトの AWS 設定を使用して RDS Data API クライアントを作成して返す。

    Returns:
        boto3.client: RDS Data API クライアント
    """
    return boto3.client("rds-data")


def execute_statement(
    sql_query: str, aurora_resource_arn: str, secret_arn: str, database_name: str
):
    """
    RDS Data API を使用して SQL ステートメントを実行する。

    Args:
        sql_query: 実行する SQL クエリ文字列
        aurora_resource_arn: Aurora Serverless クラスターの ARN
        secret_arn: データベース認証情報を含むシークレットの ARN
        database_name: 接続するデータベースの名前

    Returns:
        dict: RDS Data API からのレスポンス
    """
    client = get_rds_data_client()

    try:
        response = client.execute_statement(
            resourceArn=aurora_resource_arn,
            secretArn=secret_arn,
            database=database_name,
            sql=sql_query,
            includeResultMetadata=True,
        )
        print("\n" + "=" * 70)
        print("✅ SQL ステートメントが正常に実行されました")
        print("=" * 70)
        print(f"🗄️  データベース: {database_name}")
        print(f"📊 クエリ長: {len(sql_query)} 文字")
        print("=" * 70 + "\n")
        return response
    except ClientError as e:
        print("\n" + "=" * 70)
        print("❌ SQL 実行エラー")
        print("=" * 70)
        print(f"🗄️  データベース: {database_name}")
        print(f"💥 エラー: {e}")
        print("=" * 70 + "\n")
        return {"error": str(e)}


def get_size(string: str) -> int:
    """
    UTF-8 でエンコードした際の文字列のサイズ（バイト単位）を計算する。

    Args:
        string: サイズを計測する文字列

    Returns:
        int: 文字列のサイズ（バイト単位）
    """
    return len(string.encode("utf-8"))


def run_sql_query(sql_query: str) -> str:
    """
    RDS Data API を使用して SQL クエリを実行し、結果を JSON として返す。

    この関数はデータベースへの接続、クエリの実行、結果のフォーマットを処理します。
    特殊なデータ型（Decimal、date）は JSON 用に適切に変換されます。
    結果サイズが MAX_RESPONSE_SIZE_BYTES を超える場合、切り詰められます。

    Args:
        sql_query: 実行する SQL クエリ文字列

    Returns:
        str: クエリ結果またはエラー情報を含む JSON 文字列
    """
    print("\n" + "=" * 70)
    print("🔍 SQL クエリ実行")
    print("=" * 70)
    print(f"📝 クエリ: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}")
    print("=" * 70)
    try:
        # Validate configuration parameters before proceeding
        validate_configuration()

        response = execute_statement(
            sql_query,
            CONFIG["AURORA_RESOURCE_ARN"],
            CONFIG["SECRET_ARN"],
            CONFIG["DATABASE_NAME"],
        )

        if "error" in response:
            return json.dumps(
                {
                    "error": f"Something went wrong executing the query: {response['error']}"
                }
            )

        print("\n" + "=" * 50)
        print("✅ クエリ処理完了")
        print("=" * 50)
        print(f"📊 取得レコード数: {len(response.get('records', []))}")
        print("=" * 50 + "\n")

        records = []
        records_to_return = []
        message = ""

        # Process the response from RDS Data API
        if "records" in response:
            column_metadata = response.get("columnMetadata", [])
            column_names = [col.get("name") for col in column_metadata]

            for row in response["records"]:
                record = {}
                for i, value in enumerate(row):
                    # RDS Data API returns values as dictionaries with type indicators
                    # e.g., {"stringValue": "value"}, {"longValue": 123}, etc.
                    for value_type, actual_value in value.items():
                        if value_type == "numberValue" and isinstance(
                            actual_value, Decimal
                        ):
                            record[column_names[i]] = float(actual_value)
                        elif (
                            value_type == "stringValue"
                            and column_metadata[i].get("typeName") == "date"
                        ):
                            record[column_names[i]] = actual_value  # Already a string
                        else:
                            record[column_names[i]] = actual_value
                records.append(record)

            max_response_size = CONFIG.get("MAX_RESPONSE_SIZE_BYTES", 25600)
            if get_size(json.dumps(records)) > max_response_size:
                for item in records:
                    if get_size(json.dumps(records_to_return)) <= max_response_size:
                        records_to_return.append(item)
                message = (
                    f"The data is too large, it has been truncated from "
                    f"{len(records)} to {len(records_to_return)} rows."
                )
            else:
                records_to_return = records

        if message != "":
            return json.dumps({"result": records_to_return, "message": message})
        else:
            return json.dumps({"result": records_to_return})

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})
