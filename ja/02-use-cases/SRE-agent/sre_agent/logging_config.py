#!/usr/bin/env python3

import logging
import os
from typing import Optional


def _configure_http_loggers(debug_enabled: bool = False) -> None:
    """デバッグ設定に基づいて HTTP クライアントロガーを設定する。"""
    http_loggers = [
        "httpx",
        "httpcore",
        "streamable_http",
        "mcp.client.streamable_http",
        "anthropic._client",
        "anthropic._base_client",
    ]

    for logger_name in http_loggers:
        http_logger = logging.getLogger(logger_name)
        if debug_enabled:
            http_logger.setLevel(logging.DEBUG)
        else:
            http_logger.setLevel(logging.WARNING)


def configure_logging(debug: Optional[bool] = None) -> bool:
    """デバッグ設定に基づいて basicConfig でロギングを設定する。

    Args:
        debug: デバッグロギングを有効にする。None の場合、DEBUG 環境変数を確認する。

    Returns:
        bool: デバッグロギングが有効かどうか
    """
    # デバッグ設定を決定

    if debug is None:
        debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # デバッグ設定に基づいてログレベルを設定
    log_level = logging.DEBUG if debug else logging.INFO

    # basicConfig でロギングを設定
    logging.basicConfig(
        level=log_level,
        # ログメッセージフォーマットを定義
        format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
    )

    # HTTP ロガーを設定
    _configure_http_loggers(debug)

    # MCP ロガーを設定
    mcp_logger = logging.getLogger("mcp")
    if debug:
        mcp_logger.setLevel(logging.DEBUG)
    else:
        mcp_logger.setLevel(logging.WARNING)

    return debug


def should_show_debug_traces() -> bool:
    """デバッグトレースを表示すべきかを確認する。"""
    return os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
