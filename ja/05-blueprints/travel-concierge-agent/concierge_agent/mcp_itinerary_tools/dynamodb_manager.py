import os
import uuid
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DynamoDBManager:
    """旅程操作用の DynamoDB クライアント。"""

    def __init__(self, region_name: str = None):
        self.region_name = region_name or os.environ.get("AWS_REGION")

        # Initialize DynamoDB resource
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)

        # Table names from environment variables
        self.user_profile_table_name = os.environ.get("USER_PROFILE_TABLE_NAME")
        self.itinerary_table_name = os.environ.get("ITINERARY_TABLE_NAME")

        # Get table references
        self.user_profile_table = self.dynamodb.Table(self.user_profile_table_name)
        self.itinerary_table = self.dynamodb.Table(self.itinerary_table_name)

        logger.info(f"DynamoDB Manager をリージョン {self.region_name} で初期化しました")
        logger.info(f"Itinerary テーブル: {self.itinerary_table_name}")

    def get_itinerary_items(self, user_id: str):
        """GSI を使用してユーザーの全旅程アイテムを取得する。"""
        try:
            response = self.itinerary_table.query(
                IndexName="itinerariesByUser_id",
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
            )

            items = response.get("Items", [])
            logger.info(f"ユーザー {user_id} の旅程アイテムを {len(items)} 件取得しました")
            return items

        except ClientError as e:
            logger.error(f"旅程アイテムの取得中にエラーが発生しました: {e}")
            raise

    def add_itinerary_item(self, user_id: str, item: dict):
        """旅程にアイテムを追加する。"""
        try:
            now = datetime.now(timezone.utc).isoformat()

            itinerary_item = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": item.get("item_type", item.get("type", "activity")),
                "title": item.get("title", ""),
                "date": item.get("date", ""),
                "time_of_day": item.get("time_of_day", ""),
                "details": item.get("details", ""),
                "location": item.get("location", ""),
                "price": item.get("price", ""),
                "createdAt": now,
                "updatedAt": now,
            }

            self.itinerary_table.put_item(Item=itinerary_item)
            logger.info(
                f"ユーザー {user_id} の旅程に '{item.get('title')}' を追加しました"
            )
            return itinerary_item

        except ClientError as e:
            logger.error(f"旅程アイテムの追加中にエラーが発生しました: {e}")
            raise

    def remove_itinerary_item(self, user_id: str, item_id: str):
        """旅程からアイテムを削除する。"""
        try:
            self.itinerary_table.delete_item(Key={"id": item_id})
            logger.info(f"ユーザー {user_id} の旅程アイテム {item_id} を削除しました")

        except ClientError as e:
            logger.error(f"旅程アイテムの削除中にエラーが発生しました: {e}")
            raise

    def update_itinerary_item(self, user_id: str, item_id: str, updates: dict):
        """旅程アイテムを更新する。"""
        try:
            now = datetime.now(timezone.utc).isoformat()

            # Build update expression
            update_parts = []
            expr_values = {":updatedAt": now}
            expr_names = {}

            for key, value in updates.items():
                safe_key = f"#{key}"
                expr_names[safe_key] = key
                expr_values[f":{key}"] = value
                update_parts.append(f"{safe_key} = :{key}")

            update_parts.append("updatedAt = :updatedAt")
            update_expression = "SET " + ", ".join(update_parts)

            self.itinerary_table.update_item(
                Key={"id": item_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names if expr_names else None,
            )
            logger.info(f"ユーザー {user_id} の旅程アイテム {item_id} を更新しました")

        except ClientError as e:
            logger.error(f"旅程アイテムの更新中にエラーが発生しました: {e}")
            raise

    def get_user_profile(self, user_id: str):
        """UserProfile テーブルからユーザープロファイルを取得する。"""
        try:
            response = self.user_profile_table.get_item(Key={"id": user_id})

            if "Item" in response:
                return response["Item"]
            return None

        except ClientError as e:
            logger.error(f"ユーザープロファイルの取得中にエラーが発生しました: {e}")
            raise
