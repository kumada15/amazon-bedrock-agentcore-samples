import os
import logging
import boto3
from typing import Any, Dict
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)


def get_ssm_parameter(parameter_name: str, region: str) -> str:
    """
    SSM Parameter Store からパラメータを取得する。

    Args:
        parameter_name: SSM パラメータ名
        region: AWS リージョン

    Returns:
        パラメータ値
    """
    ssm = boto3.client("ssm", region_name=region)
    try:
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        raise ValueError(f"SSM parameter not found: {parameter_name}")
    except Exception as e:
        raise ValueError(f"Failed to retrieve SSM parameter {parameter_name}: {e}")


def get_serpapi_key() -> str:
    """
    AWS SSM Parameter Store から SerpAPI キーを取得する。

    Returns:
        SerpAPI キー
    """
    region = os.getenv("AWS_REGION", "us-east-1")
    return get_ssm_parameter("/concierge-agent/shopping/serp-api-key", region)


def search_amazon_products(query: str, max_results: int = 10) -> Dict[str, Any]:
    """
    SerpAPI を使用して Amazon で商品を検索する。

    Args:
        query: 商品検索クエリ
        max_results: 返す結果の最大数

    Returns:
        商品情報を含む検索結果の辞書
    """
    try:
        api_key = get_serpapi_key()

        # SerpAPI を使用して Amazon を検索
        params = {
            "engine": "amazon",
            "amazon_domain": "amazon.com",
            "k": query,
            "api_key": api_key,
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        # 商品情報を抽出
        products = []
        organic_results = results.get("organic_results", [])[:max_results]

        for product in organic_results:
            product_info = {
                "asin": product.get("asin", ""),
                "title": product.get("title", ""),
                "link": product.get("link", ""),
                "price": (
                    product.get("price", {}).get("value", 0)
                    if isinstance(product.get("price"), dict)
                    else product.get("price", "N/A")
                ),
                "rating": product.get("rating", 0),
                "reviews": product.get("reviews", 0),
                "thumbnail": product.get("thumbnail", ""),
            }
            products.append(product_info)

        return {"success": True, "products": products, "total_results": len(products)}

    except Exception as e:
        logger.error(f"Amazon 商品検索中にエラーが発生しました: {e}")
        return {"success": False, "error": str(e), "products": [], "total_results": 0}


def search_products(user_id: str, question: str) -> Dict[str, Any]:
    """
    SerpAPI 経由で Amazon の商品を検索してユーザーの商品検索リクエストを処理する。

    Args:
        user_id: 商品検索対象ユーザーの一意識別子
        question: 商品情報をリクエストするユーザーのクエリテキスト

    Returns:
        Dict: 検索結果を含む 'product_list' という辞書
            - 'answer': 見つかった商品の説明またはエラーメッセージ
            - 'asins': 見つかった ASIN のリスト
            - 'products': 商品詳細のリスト
    """
    try:
        logger.info(f"ユーザー {user_id} の商品検索を処理中: {question}")

        # 商品を検索
        search_results = search_amazon_products(question)

        if not search_results["success"]:
            return {
                "answer": f"Product search failed: {search_results.get('error', 'Unknown error')}",
                "asins": [],
                "products": [],
            }

        products = search_results["products"]
        asins = [p["asin"] for p in products if p.get("asin")]

        if not products:
            return {
                "answer": "検索条件に一致する商品が見つかりませんでした。",
                "asins": [],
                "products": [],
            }

        # レスポンスを構築
        answer = f"'{question}' に一致する商品が {len(products)} 件見つかりました:\n\n"
        for i, product in enumerate(products, 1):
            price_str = (
                f"${product['price']}"
                if isinstance(product["price"], (int, float))
                else product["price"]
            )
            answer += f"{i}. {product['title']}\n"
            answer += f"   価格: {price_str}\n"
            if product.get("rating"):
                answer += f"   評価: {product['rating']}/5 ({product.get('reviews', 0)} 件のレビュー)\n"
            answer += f"   ASIN: {product['asin']}\n"
            answer += f"   リンク: {product['link']}\n\n"

        return {"answer": answer.strip(), "asins": asins, "products": products}

    except Exception as e:
        logger.error(f"single_productsearch でエラーが発生しました: {e}")
        return {
            "answer": f"商品検索中にエラーが発生しました: {str(e)}",
            "asins": [],
            "products": [],
        }


def generate_packing_list(user_id: str, question: str) -> Dict[str, Any]:
    """
    商品推奨付きパッキングリストを生成するユーザーリクエストを処理する。
    AI を使用してパッキングリストを生成し、SerpAPI を使用して
    各アイテムの Amazon 商品推奨を検索する。

    Args:
        user_id: 商品検索対象ユーザーの一意識別子
        question: パッキングリストをリクエストするユーザーのクエリテキスト（例: 「ハワイに1週間行きます」）

    Returns:
        Dict: packing_list と呼ばれる結果を含む辞書
            - 'answer': 商品推奨付きのフォーマット済みパッキングリスト
            - 'asins': パッキングリストアイテムと ASIN のマッピング辞書
            - 'items': 商品詳細付きパッキングリストアイテムのリスト
    """
    try:
        logger.info(f"ユーザー {user_id} のパッキングリストを生成中: {question}")

        # クエリに基づいて一般的なパッキングリストカテゴリを定義
        # これは簡略化されたアプローチ - 本番環境では LLM を使用してこれを生成する可能性がある
        packing_items = []

        # 質問から旅行コンテキストを抽出
        question_lower = question.lower()

        # 誰もが必要とする基本的なパッキングアイテム
        base_items = ["travel backpack", "toiletry bag", "phone charger"]

        # コンテキスト固有のアイテムを追加
        if any(
            word in question_lower for word in ["beach", "hawaii", "tropical", "ocean"]
        ):
            packing_items.extend(
                [
                    "sunscreen SPF 50",
                    "beach towel",
                    "swimsuit",
                    "flip flops",
                    "sunglasses",
                ]
            )
        elif any(word in question_lower for word in ["ski", "snow", "winter", "cold"]):
            packing_items.extend(
                [
                    "winter jacket",
                    "thermal underwear",
                    "ski goggles",
                    "gloves",
                    "beanie",
                ]
            )
        elif any(word in question_lower for word in ["hiking", "camping", "outdoor"]):
            packing_items.extend(
                [
                    "hiking boots",
                    "water bottle",
                    "first aid kit",
                    "flashlight",
                    "sleeping bag",
                ]
            )
        elif any(word in question_lower for word in ["business", "work", "conference"]):
            packing_items.extend(
                ["business casual clothes", "laptop bag", "power bank", "notebook"]
            )
        else:
            # Generic travel items
            packing_items.extend(["travel pillow", "luggage tags", "packing cubes"])

        packing_items = base_items + packing_items

        # Search for products for each packing item
        results = []
        asins_dict = {}

        answer = f"Packing list for: {question}\n\n"

        for item in packing_items[:7]:  # Limit to 7 items to avoid too many API calls
            logger.info(f"商品を検索中: {item}")
            search_results = search_amazon_products(item, max_results=3)

            if search_results["success"] and search_results["products"]:
                products = search_results["products"]
                item_asins = [p["asin"] for p in products if p.get("asin")]
                asins_dict[item] = item_asins

                answer += f"📦 {item.title()}\n"
                answer += "   Recommended products:\n"

                for i, product in enumerate(products[:3], 1):
                    price_str = (
                        f"${product['price']}"
                        if isinstance(product["price"], (int, float))
                        else product["price"]
                    )
                    answer += f"   {i}. {product['title'][:60]}...\n"
                    answer += f"      Price: {price_str}"
                    if product.get("rating"):
                        answer += f" | Rating: {product['rating']}/5"
                    answer += f"\n      ASIN: {product['asin']}\n"

                answer += "\n"

                results.append({"item": item, "products": products})

        if not results:
            return {
                "answer": "Unable to generate packing list with product recommendations at this time.",
                "asins": {},
                "items": [],
            }

        return {"answer": answer.strip(), "asins": asins_dict, "items": results}

    except Exception as e:
        logger.error(f"generate_packinglist_with_productASINS でエラーが発生しました: {e}")
        return {
            "answer": f"An error occurred while generating packing list: {str(e)}",
            "asins": {},
            "items": [],
        }
