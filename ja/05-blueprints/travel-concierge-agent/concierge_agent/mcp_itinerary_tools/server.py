"""
Itinerary Tools MCP サーバー

MCP プロトコル経由で旅程管理ツールを公開する。
エージェントロジックなし - 純粋なツール実装のみ。
"""

import os
import logging
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
    "Itinerary Tools", host="0.0.0.0", stateless_http=True
)  # nosec B104:standard pattern for containerized MCP serverss

# DynamoDB マネージャーを初期化
dynamodb_manager = None


def get_dynamodb_manager():
    """DynamoDB マネージャーインスタンスを取得または作成する。"""
    global dynamodb_manager
    if dynamodb_manager is None:
        dynamodb_manager = DynamoDBManager(region_name=REGION)
    return dynamodb_manager


# =============================================================================
# MCP ツール - 生のツール公開
# =============================================================================


@mcp.tool()
def itinerary_get(user_id: str) -> List[Dict[str, Any]]:
    """
    ユーザーの保存済み旅程を取得する。

    Args:
        user_id: ユーザー識別子

    Returns:
        旅程アイテムのリスト（フライト、ホテル、アクティビティ）
    """
    try:
        manager = get_dynamodb_manager()
        items = manager.get_itinerary_items(user_id)
        return items
    except Exception as e:
        logger.error(f"旅程の取得中にエラーが発生しました: {e}")
        return []


@mcp.tool()
def itinerary_save(
    user_id: str,
    item_type: str,
    title: str,
    date: str,
    details: str = "",
    location: str = "",
    price: str = "",
    time_of_day: str = "",
) -> Dict[str, Any]:
    """
    ユーザーの旅程にアイテムを保存する。

    Args:
        user_id: ユーザー識別子
        item_type: アイテムの種類（'flight'、'hotel'、'activity'、'restaurant'）
        title: アイテムのタイトル/名前
        date: YYYY-MM-DD 形式の日付
        details: 追加詳細
        location: 場所/住所
        price: 価格（該当する場合）
        time_of_day: 時間帯（'morning'、'afternoon'、'evening'）

    Returns:
        成功ステータスとメッセージ
    """
    try:
        manager = get_dynamodb_manager()

        itinerary_item = {
            "item_type": item_type,
            "title": title,
            "date": date,
            "details": details,
            "location": location,
            "price": price,
            "time_of_day": time_of_day,
        }

        manager.add_itinerary_item(user_id, itinerary_item)

        return {"success": True, "message": f"Added {title} to itinerary for {date}"}
    except Exception as e:
        logger.error(f"旅程アイテムの保存中にエラーが発生しました: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def itinerary_remove(user_id: str, item_id: str) -> Dict[str, Any]:
    """
    旅程からアイテムを削除する。

    Args:
        user_id: ユーザー識別子
        item_id: 削除するアイテムの ID

    Returns:
        成功ステータスとメッセージ
    """
    try:
        manager = get_dynamodb_manager()
        manager.remove_itinerary_item(user_id, item_id)

        return {"success": True, "message": "Item removed from itinerary"}
    except Exception as e:
        logger.error(f"旅程アイテムの削除中にエラーが発生しました: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def itinerary_clear(user_id: str) -> Dict[str, Any]:
    """
    ユーザーの旅程からすべてのアイテムをクリアする。

    Args:
        user_id: ユーザー識別子

    Returns:
        成功ステータスと削除されたアイテム数
    """
    try:
        manager = get_dynamodb_manager()
        items = manager.get_itinerary_items(user_id)

        if not items:
            return {
                "success": True,
                "items_removed": 0,
                "message": "Itinerary is already empty.",
            }

        for item in items:
            manager.remove_itinerary_item(user_id, item.get("id"))

        return {
            "success": True,
            "items_removed": len(items),
            "message": f"Removed {len(items)} items from itinerary.",
        }
    except Exception as e:
        logger.error(f"旅程のクリア中にエラーが発生しました: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def itinerary_update_date(user_id: str, item_id: str, new_date: str) -> Dict[str, Any]:
    """
    旅程アイテムの日付を更新する。

    Args:
        user_id: ユーザー識別子
        item_id: 更新するアイテムの ID
        new_date: YYYY-MM-DD 形式の新しい日付

    Returns:
        成功ステータスとメッセージ
    """
    try:
        from datetime import datetime

        try:
            datetime.strptime(new_date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "message": "Date must be in YYYY-MM-DD format"}

        manager = get_dynamodb_manager()
        manager.update_itinerary_item(user_id, item_id, {"date": new_date})

        return {"success": True, "message": f"Updated date to {new_date}"}
    except Exception as e:
        logger.error(f"日付の更新中にエラーが発生しました: {e}")
        return {"success": False, "message": str(e)}


# =============================================================================
# サーバー起動
# =============================================================================

if __name__ == "__main__":
    logger.info("Itinerary Tools MCP サーバーを起動中...")
    mcp.run(transport="streamable-http")
