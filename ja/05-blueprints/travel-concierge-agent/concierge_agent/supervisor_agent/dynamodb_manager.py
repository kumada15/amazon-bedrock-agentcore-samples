import os
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DynamoDBManager:
    """カート/ウィッシュリスト操作およびユーザー管理用の DynamoDB クライアント。"""

    def __init__(self, region_name: str = None):
        self.region_name = region_name or os.environ.get("AWS_REGION")

        # Initialize DynamoDB resource and client
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
        self.dynamodb_client = boto3.client("dynamodb", region_name=self.region_name)

        # Table names - can be overridden via environment variables
        # Updated to use UserProfile table name to match AppSync schema
        self.user_profile_table_name = os.environ.get("USER_PROFILE_TABLE_NAME")
        self.wishlist_table_name = os.environ.get("WISHLIST_TABLE_NAME")

        # Get table references
        self.user_profile_table = self.dynamodb.Table(self.user_profile_table_name)
        self.wishlist_table = self.dynamodb.Table(self.wishlist_table_name)

        logger.info(f"DynamoDB Manager をリージョン {self.region_name} で初期化しました")
        logger.info(
            f"UserProfile テーブル: {self.user_profile_table_name}, Wishlist テーブル: {self.wishlist_table_name}"
        )

    def get_wishlist_items(self, user_id: str):
        """GSI を使用してユーザーの全ウィッシュリストアイテムを取得する。"""
        try:
            # Use query with GSI for better performance
            response = self.wishlist_table.query(
                IndexName="wishlistsByUser_id",
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
            )

            items = response.get("Items", [])
            logger.info(f"ユーザー {user_id} のウィッシュリストアイテムを {len(items)} 件取得しました")
            return items

        except ClientError as e:
            logger.error(f"ウィッシュリストアイテムの取得中にエラーが発生しました: {e}")
            raise

    def add_wishlist_item(self, user_id: str, item: dict):
        """自動生成 ID でウィッシュリストに単一アイテムを追加する。"""
        try:
            import uuid

            now = datetime.now(timezone.utc).isoformat()

            wishlist_item = {
                "id": str(uuid.uuid4()),  # Auto-generate UUID for primary key
                "user_id": user_id,  # User identifier (attribute)
                "asin": item.get("asin", ""),
                "title": item["title"],
                "price": item["price"],
                "reviews": item.get("reviews", ""),
                "url": item.get("url", ""),
                "item_type": item.get("item_type", "product"),
                "createdAt": now,  # Use Amplify standard field name
                "updatedAt": now,  # Use Amplify standard field name
            }

            # Add type-specific fields
            if item.get("item_type") == "hotel":
                wishlist_item.update(
                    {
                        "hotel_id": item.get("hotel_id", ""),
                        "city_code": item.get("city_code", ""),
                        "rating": item.get("rating", ""),
                        "amenities": item.get("amenities", ""),
                    }
                )
            elif item.get("item_type") == "flight":
                wishlist_item.update(
                    {
                        "flight_id": item.get("flight_id", ""),
                        "origin": item.get("origin", ""),
                        "destination": item.get("destination", ""),
                        "departure_date": item.get("departure_date", ""),
                        "airline": item.get("airline", ""),
                    }
                )

            self.wishlist_table.put_item(Item=wishlist_item)
            logger.info(
                f"ユーザー {user_id} のウィッシュリストに {wishlist_item['item_type']} アイテムを追加しました"
            )

        except ClientError as e:
            logger.error(f"ウィッシュリストアイテムの追加中にエラーが発生しました: {e}")
            raise

    def remove_wishlist_items_by_asin(self, user_id: str, asin: str):
        """ユーザーの特定 ASIN を持つ全アイテムを削除する。"""
        try:
            # Use query with GSI to find items with this ASIN for the user
            response = self.wishlist_table.query(
                IndexName="wishlistsByUser_id",
                KeyConditionExpression="user_id = :user_id",
                FilterExpression="asin = :asin",
                ExpressionAttributeValues={":user_id": user_id, ":asin": asin},
            )

            items_to_delete = response.get("Items", [])

            # Delete each item using the id (primary key)
            for item in items_to_delete:
                self.wishlist_table.delete_item(Key={"id": item["id"]})

            logger.info(
                f"ユーザー {user_id} の ASIN {asin} のアイテムを {len(items_to_delete)} 件削除しました"
            )
            return len(items_to_delete)

        except ClientError as e:
            logger.error(f"ウィッシュリストアイテムの削除中にエラーが発生しました: {e}")
            raise

    # User Profile Management Methods

    def get_user_profile(self, user_id: str):
        """UserProfile テーブルからユーザープロファイルを取得する。"""
        try:
            # First try to get by id (primary key)
            response = self.user_profile_table.get_item(Key={"id": user_id})

            if "Item" in response:
                profile = response["Item"]
                logger.info(f"ユーザープロファイルを取得しました: {user_id}")
                return profile

            # If not found by id, try scanning for userId field
            response = self.user_profile_table.scan(
                FilterExpression="userId = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
            )

            items = response.get("Items", [])
            if items:
                profile = items[0]  # Get the first match
                logger.info(f"userId スキャンでユーザープロファイルを取得しました: {user_id}")
                return profile
            else:
                logger.info(f"ユーザープロファイルが見つかりません: {user_id}")
                return None

        except ClientError as e:
            logger.error(f"ユーザープロファイルの取得中にエラーが発生しました: {e}")
            raise

    def update_itinerary_item_date(
        self, user_id: str, identifier: str, item_type: str, new_date: str
    ):
        """
        旅程アイテム（フライト/ホテル）の日付フィールドを更新する。

        Args:
            user_id: ユーザー ID
            identifier: フライトの場合は flight_id、ホテルの場合は hotel_id
            item_type: アイテムの種類（'flight' または 'hotel'）
            new_date: YYYY-MM-DD 形式の新しい日付

        Returns:
            int: 更新されたアイテムの数
        """
        try:
            # Get all items for the user
            response = self.wishlist_table.query(
                IndexName="wishlistsByUser_id",
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
            )

            items = response.get("Items", [])
            updated_count = 0

            # Filter items by type and identifier
            for item in items:
                should_update = False

                if item.get("item_type") == item_type:
                    if item_type == "flight" and item.get("flight_id") == identifier:
                        should_update = True
                    elif item_type == "hotel" and item.get("hotel_id") == identifier:
                        should_update = True

                if should_update:
                    # Update the item
                    update_expression = "SET updatedAt = :updated"
                    expression_values = {
                        ":updated": datetime.now(timezone.utc).isoformat()
                    }

                    # Add date field based on item type
                    if item_type == "flight":
                        update_expression += ", departure_date = :date"
                        expression_values[":date"] = new_date
                    elif item_type == "hotel":
                        # For hotels, we'll use check_in_date field
                        update_expression += ", check_in_date = :date"
                        expression_values[":date"] = new_date

                    self.wishlist_table.update_item(
                        Key={"id": item["id"]},
                        UpdateExpression=update_expression,
                        ExpressionAttributeValues=expression_values,
                    )
                    updated_count += 1
                    logger.info(f"アイテム {item['id']} の {item_type} の日付を更新しました")

            return updated_count

        except ClientError as e:
            logger.error(f"旅程アイテムの日付更新中にエラーが発生しました: {e}")
            raise
