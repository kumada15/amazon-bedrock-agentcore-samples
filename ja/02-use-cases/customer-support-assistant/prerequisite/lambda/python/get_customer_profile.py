import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError
import logging
import re

# Setting logger
logging.basicConfig(
    format="[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")
smm_client = boto3.client("ssm")

# Get customer profile table name from Parameter Store
customer_table = smm_client.get_parameter(
    Name="/app/customersupport/dynamodb/customer_profile_table_name",
    WithDecryption=False,
)
customer_table_name = customer_table["Parameter"]["Value"]


def ensure_customer_table_exists():
    """DynamoDB 顧客プロファイルテーブルが存在しない場合は作成する。"""
    try:
        table = dynamodb.Table(customer_table_name)
        table.load()
        return table
    except ClientError as e:
        raise e


def validate_email(email: str) -> bool:
    """メールアドレスの形式を検証する。"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """電話番号の形式を検証する。"""
    # Phone number validation pattern
    pattern = r"^\d{10,15}$"

    # Remove extra characters from phone
    cleaned_phone = re.sub(r"[\s\-\$\+]", "", phone)

    # Check if it's a valid phone number (10-15 digits)
    return bool(re.match(pattern, cleaned_phone))


def format_address(address_dict: dict) -> str:
    """住所辞書を読みやすい文字列にフォーマットする。"""
    if not address_dict or not isinstance(address_dict, dict):
        return "No address on file"

    parts = []
    if address_dict.get("street"):
        parts.append(address_dict["street"])
    if address_dict.get("city"):
        parts.append(address_dict["city"])
    if address_dict.get("state"):
        parts.append(address_dict["state"])
    if address_dict.get("zip_code"):
        parts.append(address_dict["zip_code"])
    if address_dict.get("country"):
        parts.append(address_dict["country"])

    return ", ".join(parts) if parts else "Incomplete address"


def get_tier_emoji(tier: str) -> str:
    """顧客ティアに対応する絵文字を取得する。"""
    tier_emojis = {"Standard": "🥉", "Gold": "🥇", "Premium": "💎", "VIP": "👑"}
    return tier_emojis.get(tier, "👤")


def format_preferences(prefs: dict) -> str:
    """コミュニケーション設定をフォーマットする。"""
    if not prefs or not isinstance(prefs, dict):
        return "No preferences set"

    enabled = []
    if prefs.get("email", False):
        enabled.append("Email")
    if prefs.get("sms", False):
        enabled.append("SMS")
    if prefs.get("phone", False):
        enabled.append("Phone")

    return ", ".join(enabled) if enabled else "No communication preferences set"


def get_customer_profile(
    customer_id: str = None, email: str = None, phone: str = None
) -> str:
    """
    顧客 ID、メールアドレス、または電話番号を使用して顧客プロファイル情報を取得する。

    Args:
        customer_id (str, optional): 一意の顧客識別子（例：CUST001）。
        email (str, optional): 検索用の顧客メールアドレス。
        phone (str, optional): 検索用の顧客電話番号（フォーマット有無問わず）。

    Returns:
        str: 個人情報、連絡先情報、購入履歴、サポート設定を含むフォーマット済み顧客プロファイル情報。

    Raises:
        ValueError: 有効な検索条件が指定されていないか、形式が無効な場合。
        ClientError: DynamoDB 操作に問題がある場合。
    """
    logger.info(
        json.dumps(
            {
                "customer_id": customer_id,
                "email": email,
                "phone": phone,
                "timestamp": datetime.now().isoformat(),
            },
            indent=2,
        )
    )

    # Validate input parameters
    if not any([customer_id, email, phone]):
        raise ValueError(
            "Must provide at least one search parameter: customer_id, email, or phone"
        )

    # Validate formats
    if email and not validate_email(email):
        raise ValueError("Invalid email format")

    if phone and not validate_phone(phone):
        raise ValueError("Invalid phone number format")
    try:
        table = ensure_customer_table_exists()
        customer_item = None
        search_method = ""

        # Search by customer_id (primary key - most efficient)
        if customer_id:
            search_method = "Customer ID"
            response = table.get_item(Key={"customer_id": customer_id.upper()})
            if "Item" in response:
                customer_item = response["Item"]

            print(customer_item)

        # Search by email using GSI
        elif email:
            search_method = "Email"
            response = table.query(
                IndexName="email-index",
                KeyConditionExpression="email = :email",
                ExpressionAttributeValues={":email": email.lower()},
            )
            if response["Items"]:
                customer_item = response["Items"][0]

        # Search by phone using GSI
        elif phone:
            search_method = "Phone"
            # Normalize phone number for search
            normalized_phone = re.sub(r"[\s\-$$]", "", phone)
            if not normalized_phone.startswith("+"):
                normalized_phone = (
                    "+1-" + normalized_phone if len(normalized_phone) == 10 else phone
                )

            response = table.query(
                IndexName="phone-index",
                KeyConditionExpression="phone = :phone",
                ExpressionAttributeValues={":phone": normalized_phone},
            )
            if response["Items"]:
                customer_item = response["Items"][0]

        # Customer not found
        if not customer_item:
            not_found_response = [
                "❌ Customer Profile Not Found",
                "=============================",
                f"🔍 Search Method: {search_method}",
                f"🔍 Search Value: {customer_id or email or phone}",
                "",
                "This customer was not found in our database.",
                "Please verify the information and try again.",
                "",
                "Possible reasons:",
                "• Customer may not be registered in our system",
                "• Information may have been entered incorrectly",
                "• Customer may have requested account deletion",
                "",
                "You can:",
                "• Try searching with different information (email, phone, customer ID)",
                "• Create a new customer profile if this is a new customer",
                "• Contact the customer to verify their information",
            ]
            return "\n".join(not_found_response)

        # Extract customer information
        customer_id_value = customer_item.get("customer_id", "Unknown")
        first_name = customer_item.get("first_name", "Unknown")
        last_name = customer_item.get("last_name", "Unknown")
        email_value = customer_item.get("email", "Not provided")
        phone_value = customer_item.get("phone", "Not provided")
        address = customer_item.get("address", {})
        date_of_birth = customer_item.get("date_of_birth", "Not provided")
        registration_date = customer_item.get("registration_date", "Unknown")
        tier = customer_item.get("tier", "Standard")
        communication_prefs = customer_item.get("communication_preferences", {})
        support_cases = customer_item.get("support_cases_count", 0)
        total_purchases = customer_item.get("total_purchases", 0)
        lifetime_value = customer_item.get("lifetime_value", 0.0)
        notes = customer_item.get("notes", "No notes on file")

        # Calculate customer tenure
        try:
            reg_date = datetime.strptime(registration_date, "%Y-%m-%d")
            tenure_days = (datetime.now() - reg_date).days
            tenure_years = tenure_days // 365
            tenure_months = (tenure_days % 365) // 30
        except:
            tenure_years = 0
            tenure_months = 0

        # Format customer profile
        tier_emoji = get_tier_emoji(tier)
        formatted_address = format_address(address)
        formatted_prefs = format_preferences(communication_prefs)

        profile_info = [
            "👤 Customer Profile Information",
            "===============================",
            f"🆔 Customer ID: {customer_id_value}",
            f"👤 Name: {first_name} {last_name}",
            f"{tier_emoji} Tier: {tier}",
            "",
            "📞 Contact Information:",
            f"   📧 Email: {email_value}",
            f"   📱 Phone: {phone_value}",
            f"   🏠 Address: {formatted_address}",
            "",
            "📊 Account Details:",
            f"   📅 Registration Date: {registration_date}",
            f"   🎂 Date of Birth: {date_of_birth}",
            f"   ⏱️ Customer Since: {tenure_years} years, {tenure_months} months",
            "",
            "💼 Purchase History:",
            f"   🛒 Total Purchases: {total_purchases}",
            f"   💰 Lifetime Value: ${lifetime_value:,.2f}",
            (
                f"   🎯 Average Order: ${(lifetime_value / total_purchases):,.2f}"
                if total_purchases > 0
                else "   🎯 Average Order: $0.00"
            ),
            "",
            "🎧 Support Information:",
            f"   📞 Support Cases: {support_cases}",
            f"   💬 Communication Preferences: {formatted_prefs}",
            "",
            "📝 Account Notes:",
            f"   {notes}",
            "",
        ]

        # Add customer tier benefits
        if tier == "Premium" or tier == "VIP":
            profile_info.extend(
                [
                    "🌟 Premium Benefits:",
                    "   • Priority customer support",
                    "   • Extended warranty coverage",
                    "   • Free expedited shipping",
                    "   • Exclusive product access",
                    "",
                ]
            )
        elif tier == "Gold":
            profile_info.extend(
                [
                    "🥇 Gold Benefits:",
                    "   • Priority support queue",
                    "   • Extended return period",
                    "   • Exclusive offers and discounts",
                    "",
                ]
            )

        # Add recommendations based on profile
        recommendations = []
        if support_cases > 3:
            recommendations.append(
                "⚠️  High support case count - consider proactive outreach"
            )

        if lifetime_value > 2000:
            recommendations.append("💎 High-value customer - prioritize satisfaction")

        if tenure_years >= 2:
            recommendations.append("🎉 Loyal customer - consider loyalty rewards")

        if total_purchases == 0:
            recommendations.append(
                "🆕 New customer - provide excellent first experience"
            )

        if recommendations:
            profile_info.extend(
                [
                    "💡 Support Recommendations:",
                    *[f"   {rec}" for rec in recommendations],
                    "",
                ]
            )

        # Add quick actions
        profile_info.extend(
            [
                "⚡ Quick Actions Available:",
                "   • Check warranty status for customer products",
                "   • View purchase history and invoices",
                "   • Update contact information or preferences",
                "   • Create new support case",
                "   • Send promotional offers (if opted in)",
            ]
        )
        return "\n".join(profile_info)

    except ClientError as e:
        logger.error("DynamoDB エラー:", e)
        raise Exception(
            f"Failed to retrieve customer profile: {e.response['Error']['Message']}"
        )
    except Exception as e:
        logger.error("予期しないエラー:", str(e))
        raise Exception(f"Failed to retrieve customer profile: {str(e)}")
