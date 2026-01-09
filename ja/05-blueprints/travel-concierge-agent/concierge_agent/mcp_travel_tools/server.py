"""
Travel Tools MCP サーバー

MCP プロトコル経由で旅行関連ツールを公開する。
エージェントロジックなし - 純粋なツール実装のみ。
"""

import os
import logging
import boto3
from typing import Optional
from mcp.server import FastMCP

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境設定
REGION = os.getenv("AWS_REGION")
if not REGION:
    raise ValueError("AWS_REGION environment variable is required")

# AWS クライアントを初期化
ssm_client = boto3.client("ssm", region_name=REGION)

# MCP サーバーを作成
mcp = FastMCP(
    "Travel Tools", host="0.0.0.0", stateless_http=True
)  # nosec B104:standard pattern for containerized MCP serverss


def get_ssm_parameter(parameter_name: str) -> str | None:
    """SSM パラメータストアからパラメータを取得する。"""
    try:
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.warning(f"SSM パラメータ {parameter_name} を取得できませんでした: {e}")
        return None


def load_api_keys():
    """SSM から API キーを読み込み、環境変数として設定する。"""
    keys = {
        "OPENWEATHER_API_KEY": "/concierge-agent/travel/openweather-api-key",
        # "TAVILY_API_KEY": "/concierge-agent/travel/tavily-api-key",
        "SERP_API_KEY": "/concierge-agent/travel/serp-api-key",
        "GOOGLE_MAPS_KEY": "/concierge-agent/travel/google-maps-key",
        # "AMADEUS_PUBLIC": "/concierge-agent/travel/amadeus-public",
        # "AMADEUS_SECRET": "/concierge-agent/travel/amadeus-secret",
    }

    for env_var, ssm_param in keys.items():
        if not os.getenv(env_var):
            value = get_ssm_parameter(ssm_param)
            if value:
                os.environ[env_var] = value
                logger.info(f"SSM から {env_var} を読み込みました")
            else:
                logger.warning(f"{env_var} が設定されていません")


# ツールをインポートする前に API キーを読み込む
load_api_keys()

# API キーが読み込まれた後にツールをインポート
from tools import (  # noqa: E402
    serp_search_tool,
    serp_hotel_search,
    # get_flight_offers,
    serp_flight_search,
    # get_hotel_data,
    google_places_search,
)


# =============================================================================
# MCP ツール - 生のツール公開
# =============================================================================

# @mcp.tool()
# def travel_get_weather(city: str) -> str:
#     """
#     Get 5-day weather forecast for a city.

#     Args:
#         city: City name (e.g., "Paris", "Tokyo", "New York")

#     Returns:
#         Weather forecast with daily temperatures and conditions.
#     """
#     return get_weather(city)


@mcp.tool()
def travel_search(query: str) -> str:
    """
    旅行関連情報をインターネットで検索する。

    Args:
        query: 検索クエリ（例: "ローマのおすすめレストラン"、"東京旅行のヒント"）

    Returns:
        タイトル、スニペット、ソース URL を含む検索結果。
    """
    return serp_search_tool(query)


# @mcp.tool()
# def travel_get_flights(
#     origin: str,
#     destination: str,
#     departure_date: str,
#     adults: int = 1,
#     max_price: int = 400,
#     currency: str = "USD"
# ) -> dict:
#     """
#     Search for flight offers between two cities.

#     Args:
#         origin: Origin airport IATA code (e.g., "BOS", "JFK", "LAX")
#         destination: Destination airport IATA code (e.g., "PAR", "ROM", "TYO")
#         departure_date: Departure date in YYYY-MM-DD format (e.g., "2025-12-25")
#         adults: Number of adult passengers (default: 1)
#         max_price: Maximum price filter (default: 400)
#         currency: Currency code (default: "USD")

#     Returns:
#         Flight offers with pricing and schedule details.
#     """
#     return get_flight_offers(origin, destination, departure_date, adults, max_price, currency)


# @mcp.tool()
# def travel_get_hotels(
#     city_code: str,
#     ratings: str = "4,5",
#     amenities: str = "AIR_CONDITIONING"
# ) -> dict:
#     """
#     Search for hotels in a city.

#     Args:
#         city_code: City IATA code (e.g., "ROM", "NYC", "PAR", "MAD", "BOS")
#         ratings: Hotel star ratings to filter (e.g., "3,4,5" for 3+ stars)
#         amenities: Amenities filter. Options: SWIMMING_POOL, SPA, FITNESS_CENTER,
#                    AIR_CONDITIONING, RESTAURANT, PARKING, PETS_ALLOWED, WIFI, etc.

#     Returns:
#         Hotel listings with names, ratings, and amenities.
#     """
#     return get_hotel_data(city_code, ratings, amenities)


@mcp.tool()
def travel_places_search(query: str) -> dict:
    """
    Google Places を使用して場所、レストラン、観光スポットを検索する。

    Args:
        query: 検索クエリ（例: "東京のおすすめ寿司屋"、
               "エッフェル塔近くの美術館"、"シアトルのカフェ"）

    Returns:
        名前、住所、評価、Google Maps リンクを含む場所情報。
    """
    return google_places_search(query)


@mcp.tool()
def travel_hotel_search(query: str, check_in_date: str, check_out_date: str) -> str:
    """
    SerpAPI 経由で Google Hotels を使用してホテルを検索する。

    Args:
        query: ホテル検索クエリ（例: "パリの高級ホテル"、
               "タイムズスクエア近くのホテル"、"マイアミのビーチフロントホテル"）
        check_in_date: YYYY-MM-DD 形式のチェックイン日（例: "2025-12-20"）
        check_out_date: YYYY-MM-DD 形式のチェックアウト日（例: "2025-12-25"）

    Returns:
        評価、価格、アメニティ、予約リンクを含むフォーマット済みホテル結果。
    """
    return serp_hotel_search(query, check_in_date, check_out_date)


@mcp.tool()
def travel_flight_search(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: Optional[str] = None,
) -> str:
    """
    SerpAPI 経由で Google Flights を使用してフライトを検索する。

    Args:
        departure_id: 出発空港コード（例: "DCA"、"JFK"、"LAX"）
        arrival_id: 到着空港コード（例: "LGA"、"SFO"、"ORD"）
        outbound_date: YYYY-MM-DD 形式の出発日（例: "2025-12-20"）
        return_date: YYYY-MM-DD 形式の復路日（オプション、片道の場合は省略）

    Returns:
        価格、所要時間、乗り継ぎ、炭素排出量を含むフォーマット済みフライト結果。
    """
    return serp_flight_search(departure_id, arrival_id, outbound_date, return_date)


# =============================================================================
# サーバー起動
# =============================================================================

if __name__ == "__main__":
    logger.info("Travel Tools MCP サーバーを起動中...")
    mcp.run(transport="streamable-http")
