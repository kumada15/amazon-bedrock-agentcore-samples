"""天気情報を取得するためのツール。"""

import logging
import random
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Mock weather data for demonstration
MOCK_WEATHER_DATA: dict[str, dict[str, Any]] = {
    "new york": {"temperature": 72, "conditions": "Partly Cloudy", "humidity": 65},
    "london": {"temperature": 59, "conditions": "Rainy", "humidity": 80},
    "tokyo": {"temperature": 68, "conditions": "Clear", "humidity": 55},
    "paris": {"temperature": 64, "conditions": "Cloudy", "humidity": 70},
    "sydney": {"temperature": 75, "conditions": "Sunny", "humidity": 60},
    "berlin": {"temperature": 61, "conditions": "Partly Cloudy", "humidity": 68},
    "mumbai": {"temperature": 86, "conditions": "Humid", "humidity": 85},
    "toronto": {"temperature": 66, "conditions": "Clear", "humidity": 58},
    "singapore": {"temperature": 88, "conditions": "Humid", "humidity": 90},
    "dubai": {"temperature": 95, "conditions": "Sunny", "humidity": 45},
}


def _generate_random_weather() -> dict[str, Any]:
    """不明な都市用のランダムな天気データを生成します。

    Returns:
        ランダムな天気情報を含む辞書
    """
    conditions_list = ["Sunny", "Cloudy", "Partly Cloudy", "Rainy", "Clear"]
    temperature = random.randint(50, 95)  # nosec B311
    humidity = random.randint(40, 90)  # nosec B311
    conditions = random.choice(conditions_list)  # nosec B311

    return {
        "temperature": temperature,
        "conditions": conditions,
        "humidity": humidity,
    }


def get_weather(
    city: str,
) -> dict[str, Any]:
    """都市の現在の天気情報を取得します。

    Args:
        city: 天気を取得する都市の名前

    Returns:
        気温、天気状況、湿度を含む天気情報の辞書

    Raises:
        ValueError: 都市名が空または無効な場合
    """
    if not city or not isinstance(city, str):
        logger.error(f"無効な都市パラメータ: {city}")
        raise ValueError("City name must be a non-empty string")

    city_normalized = city.strip().lower()

    if not city_normalized:
        logger.error("正規化後の都市名が空")
        raise ValueError("City name cannot be empty")

    logger.info(f"都市の天気を取得中: {city_normalized}")

    # Get weather data from mock data or generate random
    if city_normalized in MOCK_WEATHER_DATA:
        weather_data = MOCK_WEATHER_DATA[city_normalized]
        logger.debug(f"{city_normalized} のモック天気データを発見")
    else:
        weather_data = _generate_random_weather()
        logger.debug(f"{city_normalized} のランダム天気データを生成")

    result = {
        "city": city.title(),
        "temperature_f": weather_data["temperature"],
        "conditions": weather_data["conditions"],
        "humidity_percent": weather_data["humidity"],
    }

    logger.info(f"{city.title()} の天気: {result['temperature_f']}°F, {result['conditions']}")

    return result
