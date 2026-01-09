"""異なるタイムゾーンの現在時刻を取得するためのツール。"""

import logging
from datetime import datetime
from typing import Any

import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _validate_timezone(
    timezone: str,
) -> pytz.tzinfo.BaseTzInfo:
    """タイムゾーンを検証してタイムゾーンオブジェクトを返します。

    Args:
        timezone: 検証するタイムゾーン名

    Returns:
        タイムゾーンオブジェクト

    Raises:
        ValueError: タイムゾーンが無効な場合
    """
    try:
        tz = pytz.timezone(timezone)
        return tz
    except pytz.exceptions.UnknownTimeZoneError as e:
        logger.error(f"不明なタイムゾーン: {timezone}")
        raise ValueError(
            f"Unknown timezone: {timezone}. "
            f"Please use a valid timezone name like 'America/New_York' or 'Europe/London'"
        ) from e


def get_time(
    timezone: str,
) -> dict[str, Any]:
    """指定されたタイムゾーンの現在時刻を取得します。

    Args:
        timezone: タイムゾーン名（例: 'America/New_York'、'Europe/London'）

    Returns:
        タイムゾーン、フォーマットされた時刻、日付、ISO 形式を含む
        現在時刻情報の辞書

    Raises:
        ValueError: タイムゾーンが空または無効な場合
    """
    if not timezone or not isinstance(timezone, str):
        logger.error(f"無効なタイムゾーンパラメータ: {timezone}")
        raise ValueError("Timezone must be a non-empty string")

    timezone_normalized = timezone.strip()

    if not timezone_normalized:
        logger.error("正規化後のタイムゾーンが空")
        raise ValueError("Timezone cannot be empty")

    logger.info(f"タイムゾーンの時刻を取得中: {timezone_normalized}")

    # Validate and get timezone
    tz = _validate_timezone(timezone_normalized)

    # Get current time in timezone
    current_time = datetime.now(tz)

    result = {
        "timezone": timezone_normalized,
        "time": current_time.strftime("%I:%M:%S %p"),
        "date": current_time.strftime("%Y-%m-%d"),
        "day_of_week": current_time.strftime("%A"),
        "iso_format": current_time.isoformat(),
    }

    logger.info(f"{timezone_normalized} の時刻: {result['date']} {result['time']}")

    return result
