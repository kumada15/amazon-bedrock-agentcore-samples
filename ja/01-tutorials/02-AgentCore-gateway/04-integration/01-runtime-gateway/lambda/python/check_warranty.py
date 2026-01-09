import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError
import logging
import re

# ロガーを設定
logging.basicConfig(
    format="[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# DynamoDB リソースを初期化
dynamodb = boto3.resource("dynamodb")
smm_client = boto3.client("ssm")

# パラメータストアから保証テーブル名を取得
warranty_table = smm_client.get_parameter(
    Name="/app/customersupport/dynamodb/warranty_table_name", WithDecryption=False
)
warranty_table_name = warranty_table["Parameter"]["Value"]


def ensure_warranty_table_exists():
    """DynamoDB 保証テーブルが存在しない場合は作成します。"""
    try:
        table = dynamodb.Table(warranty_table_name)
        table.load()
        return table
    except ClientError as e:
        raise e


def validate_serial_number(serial_number: str) -> bool:
    """シリアル番号のフォーマットを検証します。"""
    pattern = r"^[A-Z0-9]{8,20}$"
    return bool(re.match(pattern, serial_number.upper()))


def calculate_days_remaining(end_date: str) -> int:
    """保証期限までの残り日数を計算します。"""
    try:
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        today = datetime.now()
        delta = end_date_obj - today
        return delta.days
    except ValueError:
        return 0


def get_warranty_status_text(days_remaining: int) -> str:
    """残り日数に基づいて保証状態テキストを取得します。"""
    if days_remaining > 30:
        return "✅ Active"
    elif days_remaining > 0:
        return "⚠️ Expiring Soon"
    else:
        return "❌ Expired"


def check_warranty_status(serial_number: str, customer_email: str = None) -> str:
    """
    シリアル番号を使用して製品の保証状態を確認します。

    Args:
        serial_number (str): 製品シリアル番号（8-20文字の英数字）。
        customer_email (str, optional): 確認用の顧客メールアドレス。

    Returns:
        str: カバレッジ詳細と有効期限を含むフォーマット済み保証状態情報。

    Raises:
        ValueError: シリアル番号のフォーマットが無効な場合。
        ClientError: DynamoDB 操作に問題がある場合。
    """
    logger.info(
        json.dumps(
            {
                "serial_number": serial_number,
                "customer_email": customer_email,
                "timestamp": datetime.now().isoformat(),
            },
            indent=2,
            default=str,
        )
    )

    if not validate_serial_number(serial_number):
        raise ValueError("シリアル番号は8-20文字の英数字である必要があります")

    serial_number = serial_number.upper()

    try:
        table = ensure_warranty_table_exists()

        response = table.get_item(Key={"serial_number": serial_number})

        if "Item" not in response:
            not_found_response = [
                "❌ Warranty Not Found",
                "====================",
                f"🔍 Serial Number: {serial_number}",
                "",
                "This serial number was not found in our warranty database.",
                "Please verify the serial number and try again.",
                "",
                "If you believe this is an error, please contact our support team",
                "with your purchase receipt for assistance.",
            ]
            return "\n".join(not_found_response)

        warranty_item = response["Item"]

        # 保証情報を抽出
        product_name = warranty_item.get("product_name", "Unknown Product")
        purchase_date = warranty_item.get("purchase_date", "Unknown")
        warranty_end_date = warranty_item.get("warranty_end_date", "Unknown")
        warranty_type = warranty_item.get("warranty_type", "Standard")
        customer_name = warranty_item.get("customer_name", "Unknown")
        coverage_details = warranty_item.get(
            "coverage_details", "Standard coverage applies"
        )

        # 残り日数を計算
        days_remaining = (
            calculate_days_remaining(warranty_end_date)
            if warranty_end_date != "Unknown"
            else 0
        )
        status_text = get_warranty_status_text(days_remaining)

        # 保証情報をフォーマット
        warranty_info = [
            "🛡️ Warranty Status Information",
            "===============================",
            f"📱 Product: {product_name}",
            f"🔢 Serial Number: {serial_number}",
            f"👤 Customer: {customer_name}",
            f"📅 Purchase Date: {purchase_date}",
            f"⏰ Warranty End Date: {warranty_end_date}",
            f"📋 Warranty Type: {warranty_type}",
            f"🔍 Status: {status_text}",
            "",
        ]

        # 残り日数の情報を追加
        if days_remaining > 0:
            warranty_info.append(f"📆 Days Remaining: {days_remaining} days")
        elif days_remaining == 0:
            warranty_info.append("📆 Warranty expires today!")
        else:
            warranty_info.append(f"📆 Expired {abs(days_remaining)} days ago")

        warranty_info.extend(["", "🔧 Coverage Details:", f"   {coverage_details}", ""])

        # 状態に基づいた推奨事項を追加
        if days_remaining > 30:
            warranty_info.append(
                "✨ Your warranty is active. Contact support for any issues."
            )
        elif days_remaining > 0:
            warranty_info.extend(
                [
                    "⚠️  Your warranty is expiring soon!",
                    "   Consider purchasing extended warranty coverage.",
                ]
            )
        else:
            warranty_info.extend(
                [
                    "❌ Your warranty has expired.",
                    "   Extended warranty options may be available.",
                    "   Contact support for repair service pricing.",
                ]
            )

        logger.info(json.dumps(warranty_item, indent=2, default=str))
        return "\n".join(warranty_info)

    except ClientError as e:
        logger.error("DynamoDB エラー:", e)
        raise Exception(
            f"保証状況の確認に失敗しました: {e.response['Error']['Message']}"
        )
    except Exception as e:
        logger.error("予期しないエラー:", str(e))
        raise Exception(f"Failed to check warranty status: {str(e)}")
