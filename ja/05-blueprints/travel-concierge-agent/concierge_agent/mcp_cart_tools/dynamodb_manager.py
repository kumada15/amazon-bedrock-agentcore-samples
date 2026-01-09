import os
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DynamoDBManager:
    """カート/ウィッシュリスト操作およびユーザー管理用の DynamoDB クライアント"""

    def __init__(self, region_name: str = None):
        self.region_name = region_name or os.environ.get("AWS_REGION")

        # DynamoDB リソースとクライアントを初期化
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
        self.dynamodb_client = boto3.client("dynamodb", region_name=self.region_name)

        # テーブル名 - 環境変数で上書き可能
        self.user_profile_table_name = os.environ.get("USER_PROFILE_TABLE_NAME")
        self.wishlist_table_name = os.environ.get("WISHLIST_TABLE_NAME")

        # テーブル参照を取得
        self.user_profile_table = self.dynamodb.Table(self.user_profile_table_name)
        self.wishlist_table = self.dynamodb.Table(self.wishlist_table_name)

        logger.info(f"DynamoDB Manager をリージョン {self.region_name} で初期化しました")
        logger.info(
            f"UserProfile テーブル: {self.user_profile_table_name}, Wishlist テーブル: {self.wishlist_table_name}"
        )

    def get_wishlist_items(self, user_id: str):
        """GSI を使用してユーザーのウィッシュリストアイテムをすべて取得する"""
        try:
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
        """自動生成された ID でウィッシュリストに単一アイテムを追加する"""
        try:
            import uuid

            now = datetime.now(timezone.utc).isoformat()

            wishlist_item = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "asin": item.get("asin", ""),
                "title": item["title"],
                "price": item["price"],
                "reviews": item.get("reviews", ""),
                "url": item.get("url", ""),
                "item_type": item.get("item_type", "product"),
                "createdAt": now,
                "updatedAt": now,
            }

            # タイプ固有のフィールドを追加
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

    def get_user_profile(self, user_id: str):
        """UserProfile テーブルからユーザープロファイルを取得する"""
        try:
            response = self.user_profile_table.get_item(Key={"id": user_id})

            if "Item" in response:
                profile = response["Item"]
                logger.info(f"ユーザープロファイルを取得しました: {user_id}")
                return profile

            # id で見つからない場合は、userId フィールドでスキャンを試行
            response = self.user_profile_table.scan(
                FilterExpression="userId = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
            )

            items = response.get("Items", [])
            if items:
                profile = items[0]
                logger.info(f"userId スキャンでユーザープロファイルを取得しました: {user_id}")
                return profile
            else:
                logger.info(f"ユーザープロファイルが見つかりません: {user_id}")
                return None

        except ClientError as e:
            logger.error(f"ユーザープロファイルの取得中にエラーが発生しました: {e}")
            raise
