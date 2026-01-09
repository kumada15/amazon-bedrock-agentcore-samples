"""
カートツール MCP サーバー

MCP プロトコルを介してカート管理ツールを公開します。
エージェントロジックなし - 純粋なツール実装のみ。
"""

import os
import time
import boto3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from mcp.server import FastMCP
from dynamodb_manager import DynamoDBManager

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION")
if not REGION:
    raise ValueError("AWS_REGION environment variable is required")

# MCP サーバーを作成
mcp = FastMCP(
    "Cart Tools", host="0.0.0.0", stateless_http=True
)  # nosec B104:standard pattern for containerized MCP serverss

# DynamoDB マネージャーを初期化
dynamodb_manager = None


def get_dynamodb_manager():
    """DynamoDB マネージャーインスタンスを取得または作成する"""
    global dynamodb_manager
    if dynamodb_manager is None:
        dynamodb_manager = DynamoDBManager(region_name=REGION)
    return dynamodb_manager


# =============================================================================
# MCP ツール - 生のツール公開
# =============================================================================


@mcp.tool()
def get_cart(user_id: str) -> List[Dict[str, Any]]:
    """
    指定されたユーザーの現在のショッピングカートアイテムを取得する。

    Args:
        user_id: カートを取得するユーザー ID

    Returns:
        list: 各辞書がカートアイテムを表す辞書のリスト
    """
    try:
        manager = get_dynamodb_manager()
        items = manager.get_wishlist_items(user_id)

        # Group items by unique identifier
        item_groups = {}
        for item in items:
            item_type = item.get("item_type", "product")

            if item_type == "product":
                key = item.get("asin", "")
            elif item_type == "hotel":
                key = item.get("hotel_id", "")
            elif item_type == "flight":
                key = item.get("flight_id", "")
            else:
                key = item.get("id", "")

            if key not in item_groups:
                item_groups[key] = []
            item_groups[key].append(item)

        # Build cart items
        cart_items = []
        for key, group in item_groups.items():
            latest = max(group, key=lambda x: x.get("createdAt", ""))

            item_type = latest.get("item_type", "product")

            # Determine the identifier based on item type
            if item_type == "product":
                identifier = latest.get("asin", "")
            elif item_type == "hotel":
                identifier = latest.get("hotel_id", "")
            elif item_type == "flight":
                identifier = latest.get("flight_id", "")
            else:
                identifier = latest.get("id", "")

            cart_item = {
                "id": latest.get("id"),
                "identifier": identifier,  # Add this for easy removal
                "item_type": item_type,
                "title": latest.get("title", ""),
                "price": latest.get("price", ""),
                "quantity": len(group),
                "details": {},
            }

            if item_type == "product":
                cart_item["details"] = {
                    "asin": latest.get("asin", ""),
                    "reviews": latest.get("reviews", ""),
                    "url": latest.get("url", ""),
                }
            elif item_type == "hotel":
                cart_item["details"] = {
                    "hotel_id": latest.get("hotel_id", ""),
                    "city_code": latest.get("city_code", ""),
                    "rating": latest.get("rating", ""),
                    "amenities": latest.get("amenities", ""),
                }
            elif item_type == "flight":
                cart_item["details"] = {
                    "flight_id": latest.get("flight_id", ""),
                    "origin": latest.get("origin", ""),
                    "destination": latest.get("destination", ""),
                    "departure_date": latest.get("departure_date", ""),
                    "airline": latest.get("airline", ""),
                }

            cart_items.append(cart_item)

        cart_items.sort(key=lambda x: (x["item_type"], x.get("identifier", "")))
        return cart_items

    except Exception as e:
        raise Exception(f"Error getting cart: {str(e)}")


@mcp.tool()
def add_to_cart(user_id: str, items: List[Dict[str, Any]]) -> None:
    """ユーザーのショッピングカートに複数のアイテムを追加する"""
    try:
        if not isinstance(items, list):
            raise TypeError("items must be a list")

        if not items:
            raise ValueError("items list cannot be empty")

        required_fields = ["asin", "title", "price"]
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise TypeError(f"Item at index {i} must be a dictionary")

            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                raise ValueError(
                    f"Item at index {i} is missing required fields: {missing_fields}"
                )

        manager = get_dynamodb_manager()

        for item in items:
            # Preserve item_type if already set (e.g., 'hotel', 'flight'), otherwise default to 'product'
            item_with_type = {"item_type": "product", **item}
            manager.add_wishlist_item(user_id, item_with_type)

    except Exception as e:
        raise Exception(f"Error adding items to cart: {str(e)}")


@mcp.tool()
def add_hotel_to_cart(user_id: str, hotels: List[Dict[str, Any]]) -> None:
    """
    ユーザーのカートにホテルを追加する。

    Args:
        user_id: ユーザー識別子
        hotels: ホテル辞書のリスト。各辞書には以下が必須:
            - title (str): ホテル名（必須）
            - price (str): 1泊あたりの料金（必須、例: "$150" または "$150/night"）
            - hotel_id (str): 一意のホテル識別子（必須）
            - city_code (str): 都市/場所コード（必須）
            - rating (str): ホテルの星評価（オプション）
            - amenities (str): カンマ区切りのアメニティ（オプション）

    Example:
        hotels = [{
            "title": "Grand Hotel",
            "price": "$150/night",
            "hotel_id": "hotel_12345",
            "city_code": "NYC",
            "rating": "4",
            "amenities": "WiFi, Pool"
        }]
    """
    try:
        if not isinstance(hotels, list):
            raise TypeError("hotels must be a list")

        if not hotels:
            raise ValueError("hotels list cannot be empty")

        # Validate required fields BEFORE adding
        required_fields = ["title", "price", "hotel_id", "city_code"]
        for i, hotel in enumerate(hotels):
            if not isinstance(hotel, dict):
                raise TypeError(f"Hotel at index {i} must be a dictionary")

            missing_fields = [
                field
                for field in required_fields
                if field not in hotel or not hotel[field]
            ]
            if missing_fields:
                raise ValueError(
                    f"Hotel at index {i} ('{hotel.get('title', 'unknown')}') is missing REQUIRED fields: {missing_fields}. "
                    f"ALL hotels MUST include: title, price, hotel_id, city_code"
                )

        manager = get_dynamodb_manager()

        for hotel in hotels:
            price = hotel["price"]
            if "/" in price:
                price = price.split("/")[0].strip()

            hotel_item = {
                "asin": "",
                "item_type": "hotel",
                "title": hotel["title"],
                "price": price,
                "hotel_id": hotel["hotel_id"],
                "city_code": hotel["city_code"],
                "rating": hotel.get("rating", ""),
                "amenities": hotel.get("amenities", ""),
                "reviews": "",
                "url": "",
            }
            manager.add_wishlist_item(user_id, hotel_item)

    except Exception as e:
        raise Exception(f"Error adding hotels to cart: {str(e)}")


@mcp.tool()
def add_flight_to_cart(user_id: str, flights: List[Dict[str, Any]]) -> None:
    """
    ユーザーのカートにフライトを追加する。

    Args:
        user_id: ユーザー識別子
        flights: フライト辞書のリスト。各辞書には以下が必須:
            - title (str): フライトの説明（必須）
            - price (str): フライト料金（必須、例: "$350"）
            - flight_id (str): 一意のフライトオファー ID（必須）
            - origin (str): 出発空港コード（必須）
            - destination (str): 到着空港コード（必須）
            - departure_date (str): 出発日 YYYY-MM-DD（必須）
            - airline (str): 航空会社名/コード（オプション）

    Example:
        flights = [{
            "title": "NYC to LAX - Direct",
            "price": "$350",
            "flight_id": "flight_xyz789",
            "origin": "JFK",
            "destination": "LAX",
            "departure_date": "2025-12-25",
            "airline": "Delta"
        }]
    """
    try:
        if not isinstance(flights, list):
            raise TypeError("flights must be a list")

        if not flights:
            raise ValueError("flights list cannot be empty")

        # Validate required fields BEFORE adding
        required_fields = [
            "title",
            "price",
            "flight_id",
            "origin",
            "destination",
            "departure_date",
        ]
        for i, flight in enumerate(flights):
            if not isinstance(flight, dict):
                raise TypeError(f"Flight at index {i} must be a dictionary")

            missing_fields = [
                field
                for field in required_fields
                if field not in flight or not flight[field]
            ]
            if missing_fields:
                raise ValueError(
                    f"Flight at index {i} ('{flight.get('title', 'unknown')}') is missing REQUIRED fields: {missing_fields}. "
                    f"ALL flights MUST include: title, price, flight_id, origin, destination, departure_date"
                )

        manager = get_dynamodb_manager()

        for flight in flights:
            flight_item = {
                "asin": "",
                "item_type": "flight",
                "title": flight["title"],
                "price": flight["price"],
                "flight_id": flight["flight_id"],
                "origin": flight["origin"],
                "destination": flight["destination"],
                "departure_date": flight["departure_date"],
                "airline": flight.get("airline", ""),
                "reviews": "",
                "url": "",
            }
            manager.add_wishlist_item(user_id, flight_item)

    except Exception as e:
        raise Exception(f"Error adding flights to cart: {str(e)}")


@mcp.tool()
def remove_from_cart(
    user_id: str, identifiers: List[str], item_type: str = "product"
) -> None:
    """
    識別子によってユーザーのショッピングカートから特定のアイテムを削除する。

    get_cart() の結果から 'identifier' フィールドを使用します。
    商品の場合: ASIN を使用
    ホテルの場合: hotel_id を使用
    フライトの場合: flight_id を使用

    Args:
        user_id: ユーザー ID
        identifiers: 識別子のリスト（ASIN、hotel_id、または flight_id）
        item_type: アイテムタイプ - 'product'、'hotel'、または 'flight'
    """
    try:
        if not isinstance(identifiers, list):
            raise TypeError("identifiers must be a list")

        if not identifiers:
            raise ValueError("identifiers list cannot be empty")

        manager = get_dynamodb_manager()
        total_removed = 0

        all_items = manager.get_wishlist_items(user_id)

        for identifier in identifiers:
            items_to_remove = []

            if item_type == "product":
                items_to_remove = [
                    item for item in all_items if item.get("asin") == identifier.strip()
                ]
            elif item_type == "hotel":
                items_to_remove = [
                    item
                    for item in all_items
                    if item.get("hotel_id") == identifier.strip()
                ]
            elif item_type == "flight":
                items_to_remove = [
                    item
                    for item in all_items
                    if item.get("flight_id") == identifier.strip()
                ]

            for item in items_to_remove:
                manager.wishlist_table.delete_item(Key={"id": item["id"]})
                total_removed += 1

    except Exception as e:
        raise Exception(f"Error removing items from cart: {str(e)}")


@mcp.tool()
def clear_cart(user_id: str) -> Dict[str, Any]:
    """ユーザーのショッピングカートからすべてのアイテムを削除する"""
    try:
        manager = get_dynamodb_manager()
        cart_items = manager.get_wishlist_items(user_id)

        if not cart_items:
            return {
                "success": True,
                "items_removed": 0,
                "message": "Cart is already empty.",
            }

        # Delete all items
        for item in cart_items:
            manager.wishlist_table.delete_item(Key={"id": item["id"]})

        return {
            "success": True,
            "items_removed": len(cart_items),
            "message": f"Successfully removed {len(cart_items)} items from cart.",
        }

    except Exception as e:
        return {"success": False, "message": f"Error clearing cart: {str(e)}"}


@mcp.tool()
def request_purchase_confirmation(user_id: str) -> Dict[str, Any]:
    """購入概要を準備し、ユーザーに確認を求める"""
    try:
        manager = get_dynamodb_manager()
        cart_items = manager.get_wishlist_items(user_id)

        if not cart_items:
            return {
                "requires_confirmation": False,
                "success": False,
                "message": "Your cart is empty. Add items before purchasing.",
            }

        total_amount = 0.0
        for item in cart_items:
            price_str = item.get("price", "0")
            qty = item.get("qty", 1)

            # Remove currency symbols and commas
            price_str = price_str.replace("$", "").replace(",", "").strip()

            # Handle "per night" or other rate descriptions (e.g., "$120/night")
            # Take only the numeric part before any slash
            if "/" in price_str:
                price_str = price_str.split("/")[0].strip()

            try:
                item_price = float(price_str)
                # Multiply by quantity (for products) or number of duplicate entries
                total_amount += item_price * qty
            except ValueError:
                # If price parsing fails, log it but continue
                logger.warning(
                    f"アイテム {item.get('title', 'unknown')} の価格 '{item.get('price', '0')}' を解析できませんでした"
                )

        profile = manager.get_user_profile(user_id)
        if not profile or not profile.get("preferences"):
            return {
                "requires_confirmation": False,
                "success": False,
                "message": "No payment method found. Please add a payment card first.",
            }

        preferences = profile.get("preferences", {})
        if isinstance(preferences, str):
            preferences = json.loads(preferences)

        primary_card = preferences.get("payment", {}).get("primaryCard", {})
        if not primary_card or not primary_card.get("vProvisionedTokenId"):
            return {
                "requires_confirmation": False,
                "success": False,
                "message": "No payment method found. Please add a payment card first.",
            }

        card_type = primary_card.get("type", "Card")
        last_four = primary_card.get("cardNumber", "****")

        return {
            "requires_confirmation": True,
            "total_amount": total_amount,
            "total_items": len(cart_items),
            "payment_method": f"{card_type} ending in {last_four}",
            "message": f"Ready to purchase {len(cart_items)} items for ${total_amount:.2f} using {card_type} ending in {last_four}. Please confirm to proceed.",
        }

    except Exception as e:
        return {
            "requires_confirmation": False,
            "success": False,
            "message": f"Error preparing purchase: {str(e)}",
        }


@mcp.tool()
def confirm_purchase(user_id: str) -> Dict[str, Any]:
    """ユーザーが確認した後に購入を実行する"""
    try:
        manager = get_dynamodb_manager()
        cart_items = manager.get_wishlist_items(user_id)

        if not cart_items:
            return {"success": False, "message": "Your cart is empty."}

        total_amount = 0.0
        for item in cart_items:
            price_str = item.get("price", "0")
            qty = item.get("qty", 1)

            # Remove currency symbols and commas
            price_str = price_str.replace("$", "").replace(",", "").strip()

            # Handle "per night" or other rate descriptions (e.g., "$120/night")
            # Take only the numeric part before any slash
            if "/" in price_str:
                price_str = price_str.split("/")[0].strip()

            try:
                item_price = float(price_str)
                # Multiply by quantity (for products) or number of duplicate entries
                total_amount += item_price * qty
            except ValueError:
                # If price parsing fails, log it but continue
                logger.warning(
                    f"アイテム {item.get('title', 'unknown')} の価格 '{item.get('price', '0')}' を解析できませんでした"
                )

        profile = manager.get_user_profile(user_id)
        preferences = profile.get("preferences", {})
        if isinstance(preferences, str):
            preferences = json.loads(preferences)

        primary_card = preferences.get("payment", {}).get("primaryCard", {})
        card_type = primary_card.get("type", "Card")
        last_four = primary_card.get("cardNumber", "****")

        # Generate order ID
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d')}-{user_id[:8].upper()}"

        # Clear cart after successful purchase
        for item in cart_items:
            manager.wishlist_table.delete_item(Key={"id": item["id"]})

        return {
            "success": True,
            "order_id": order_id,
            "total_amount": total_amount,
            "items_count": len(cart_items),
            "payment_method": f"{card_type} ending in {last_four}",
            "message": f"Purchase completed successfully! Order ID: {order_id}.",
        }

    except Exception as e:
        return {"success": False, "message": f"Purchase failed: {str(e)}"}


@mcp.tool()
def send_purchase_confirmation_email(
    order_id: str,
    recipient_email: str,
    total_amount: str,
    items_count: int,
    payment_method: str,
) -> Dict[str, Any]:
    """AWS SES を介して購入確認メールを送信する"""
    try:
        ses = boto3.client("ses", region_name=REGION)

        subject = f"Order Confirmation - {order_id}"
        body_html = f"""
        <html>
        <body>
            <h2>Thank you for your purchase!</h2>
            <p>Your order has been confirmed.</p>
            <p><strong>Order ID:</strong> {order_id}</p>
            <p><strong>Total Amount:</strong> ${total_amount}</p>
            <p><strong>Items:</strong> {items_count}</p>
            <p><strong>Payment Method:</strong> {payment_method}</p>
        </body>
        </html>
        """

        response = ses.send_email(
            Source="noreply@example.com",
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": body_html}},
            },
        )

        return {
            "success": True,
            "message_id": response["MessageId"],
            "message": f"Confirmation email sent to {recipient_email}",
        }

    except Exception as e:
        return {"success": False, "message": f"Failed to send email: {str(e)}"}


@mcp.tool()
def onboard_card(
    user_id: str,
    card_number: str,
    expiration_date: str,
    cvv: str,
    card_type: str = "Visa",
    is_primary: bool = True,
) -> Dict[str, Any]:
    """新しいカードを登録し、詳細をユーザープロファイルに保存する"""
    try:
        manager = get_dynamodb_manager()

        # Mock tokenization (replace with real Visa integration)
        token_id = f"vptoken_{user_id}_{int(time.time())}"
        last_four = card_number[-4:]

        profile = manager.get_user_profile(user_id)
        preferences = profile.get("preferences", {})
        if isinstance(preferences, str):
            preferences = json.loads(preferences)

        if "payment" not in preferences:
            preferences["payment"] = {}

        card_data = {
            "vProvisionedTokenId": token_id,
            "type": card_type,
            "cardNumber": last_four,
            "expiryMonth": (
                expiration_date.split("/")[0] if "/" in expiration_date else ""
            ),
            "expiryYear": (
                expiration_date.split("/")[1] if "/" in expiration_date else ""
            ),
            "cvv": "***",
        }

        if is_primary:
            preferences["payment"]["primaryCard"] = card_data
        else:
            preferences["payment"]["backupCard"] = card_data

        manager.update_user_profile(user_id, {"preferences": preferences})

        return {
            "success": True,
            "vProvisionedTokenId": token_id,
            "message": f"{card_type} ending in {last_four} added successfully",
            "card_type": card_type,
            "last_four": last_four,
        }

    except Exception as e:
        return {"success": False, "message": f"Error onboarding card: {str(e)}"}


@mcp.tool()
def get_visa_iframe_config(user_id: str) -> Dict[str, Any]:
    """セキュアなカード登録用の Visa iframe 設定を取得する"""
    try:
        return {
            "success": True,
            "iframe_url": "",
            "config": {"user_id": user_id, "environment": "sandbox"},
        }
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


@mcp.tool()
def check_user_has_payment_card(user_id: str) -> Dict[str, Any]:
    """
    ユーザーが支払いカード（プライマリまたはバックアップ）を登録しているか確認する。

    Args:
        user_id: 確認するユーザー ID

    Returns:
        dict: {
            'has_card': bool,
            'has_primary': bool,
            'has_backup': bool,
            'card_info': dict or None（下4桁、タイプなど）
        }
    """
    try:
        manager = get_dynamodb_manager()
        user_profile = manager.get_user_profile(user_id)

        if not user_profile:
            return {
                "has_card": False,
                "has_primary": False,
                "has_backup": False,
                "card_info": None,
                "message": "User profile not found",
            }

        preferences = user_profile.get("preferences")
        if isinstance(preferences, str):
            preferences = json.loads(preferences)

        payment = preferences.get("payment", {}) if preferences else {}
        primary_card = payment.get("primaryCard")
        backup_card = payment.get("backupCard")

        has_primary = primary_card is not None and primary_card.get(
            "vProvisionedTokenId"
        )
        has_backup = backup_card is not None and backup_card.get("vProvisionedTokenId")

        card_info = None
        if has_primary:
            card_info = {
                "type": primary_card.get("type", "Card"),
                "last_four": primary_card.get("lastFour")
                or primary_card.get("cardNumber", "****"),
                "is_primary": True,
            }
        elif has_backup:
            card_info = {
                "type": backup_card.get("type", "Card"),
                "last_four": backup_card.get("lastFour")
                or backup_card.get("cardNumber", "****"),
                "is_primary": False,
            }

        result = {
            "has_card": has_primary or has_backup,
            "has_primary": has_primary,
            "has_backup": has_backup,
            "card_info": card_info,
        }

        # Automatically include ui_actions based on card status
        # This ensures UI always gets the right button, regardless of agent behavior
        if not result["has_card"]:
            # No card → Show ADD_CARD button
            result["ui_actions"] = [
                {
                    "type": "show_button",
                    "action": "ADD_CARD",
                    "label": "💳 Add Payment Card",
                }
            ]
        else:
            # Has card → Show CONFIRM_PURCHASE button (agent can proceed with purchase)
            result["ui_actions"] = [
                {
                    "type": "show_button",
                    "action": "CONFIRM_PURCHASE",
                    "label": "✅ Confirm Purchase",
                }
            ]

        return result

    except Exception as e:
        logger.error(f"支払いカードの確認中にエラーが発生しました: {e}")
        return {
            "has_card": False,
            "has_primary": False,
            "has_backup": False,
            "card_info": None,
            "error": str(e),
            # Show ADD_CARD button on error (assume no card)
            "ui_actions": [
                {
                    "type": "show_button",
                    "action": "ADD_CARD",
                    "label": "💳 Add Payment Card",
                }
            ],
        }


# =============================================================================
# サーバー起動
# =============================================================================

if __name__ == "__main__":
    logger.info("Cart Tools MCP サーバーを起動中...")
    mcp.run(transport="streamable-http")
