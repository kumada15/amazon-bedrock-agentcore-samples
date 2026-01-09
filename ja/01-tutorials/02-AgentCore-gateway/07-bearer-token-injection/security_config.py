"""
Bearer token インジェクションデモ用のセキュリティ設定とバリデーションユーティリティ。

このモジュールは、Bearer token と API リクエストの安全な処理を保証するための
セキュリティに特化した設定とバリデーション関数を提供します。
"""

import re
import os
from typing import Dict, Any, Optional
from urllib.parse import urlparse


class SecurityConfig:
    """セキュリティ設定の定数とバリデーションメソッド。"""

    # 最大リクエストボディサイズ（1MB）
    MAX_REQUEST_BODY_SIZE = 1024 * 1024

    # 最大トークン長
    MAX_TOKEN_LENGTH = 2048

    # 許可されるツール名パターン（英数字、ハイフン、アンダースコア）
    TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    # 必須セキュリティヘッダー
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    # API レート制限
    DEFAULT_RATE_LIMIT = 100
    DEFAULT_BURST_LIMIT = 200
    DEFAULT_DAILY_QUOTA = 1000

    @staticmethod
    def validate_bearer_token(token: str) -> bool:
        """
        Bearer token のフォーマットと長さを検証します。

        Args:
            token: 検証する Bearer token

        Returns:
            トークンが有効な場合は True、そうでない場合は False
        """
        if not token or not isinstance(token, str):
            return False

        # 'Bearer ' プレフィックスが存在する場合は削除
        if token.startswith("Bearer "):
            token = token[7:]

        # 長さをチェック
        if len(token) > SecurityConfig.MAX_TOKEN_LENGTH:
            return False

        # 基本的なフォーマット検証（base64 形式の文字）
        if not re.match(r"^[A-Za-z0-9+/=_-]+$", token):
            return False

        return True

    @staticmethod
    def validate_tool_name(tool_name: str) -> bool:
        """
        ツール名のフォーマットを検証します。

        Args:
            tool_name: 検証するツール名

        Returns:
            ツール名が有効な場合は True、そうでない場合は False
        """
        if not tool_name or not isinstance(tool_name, str):
            return False

        if len(tool_name) > 100:  # 適切な長さ制限
            return False

        return bool(SecurityConfig.TOOL_NAME_PATTERN.match(tool_name))

    @staticmethod
    def validate_url(url: str, require_https: bool = True) -> bool:
        """
        URL のフォーマットとセキュリティ要件を検証します。

        Args:
            url: 検証する URL
            require_https: HTTPS プロトコルを必須とするかどうか

        Returns:
            URL が有効な場合は True、そうでない場合は False
        """
        if not url or not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url)

            if require_https and parsed.scheme != "https":
                return False

            if not parsed.netloc:
                return False

            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        機密情報を削除してログ出力用にデータをサニタイズします。

        Args:
            data: サニタイズするデータ辞書

        Returns:
            サニタイズされたデータ辞書
        """
        sensitive_keys = {
            "token",
            "password",
            "secret",
            "key",
            "authorization",
            "x-asana-token",
            "bearer",
            "api_key",
            "access_token",
        }

        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = SecurityConfig.sanitize_log_data(value)
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def get_environment_config() -> Dict[str, str]:
        """
        セキュリティ関連の環境設定を取得します。

        Returns:
            環境設定の辞書
        """
        return {
            "DEMO_USERNAME": os.environ.get("DEMO_USERNAME", "testuser"),
            "DEMO_SECRET_NAME": os.environ.get(
                "DEMO_SECRET_NAME", "asana_integration_demo_agent"
            ),
            "ROLE_NAME": os.environ.get(
                "ROLE_NAME", "AgentCoreGwyAsanaIntegrationRole"
            ),
            "POLICY_NAME": os.environ.get(
                "POLICY_NAME", "AgentCoreGwyAsanaIntegrationPolicy"
            ),
            "MAX_REQUEST_SIZE": os.environ.get(
                "MAX_REQUEST_SIZE", str(SecurityConfig.MAX_REQUEST_BODY_SIZE)
            ),
            "RATE_LIMIT": os.environ.get(
                "RATE_LIMIT", str(SecurityConfig.DEFAULT_RATE_LIMIT)
            ),
        }


def validate_request_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    受信リクエストペイロードのセキュリティ問題を検証します。

    Args:
        payload: 検証するリクエストペイロード

    Returns:
        (is_valid, error_message) のタプル
    """
    if not isinstance(payload, dict):
        return False, "ペイロードは辞書である必要があります"

    # tool_name を検証
    tool_name = payload.get("tool_name")
    if not SecurityConfig.validate_tool_name(tool_name):
        return False, "無効な tool_name フォーマットです"

    # 文字列フィールドに疑わしいコンテンツが含まれていないか検証
    string_fields = ["name", "notes", "project", "task_gid", "workspace"]
    for field in string_fields:
        value = payload.get(field)
        if value is not None:
            if not isinstance(value, str):
                return False, f"フィールド {field} は文字列である必要があります"

            if len(value) > 1000:  # 適切な長さ制限
                return False, f"フィールド {field} が長すぎます"

            # 基本的な XSS 防止
            if any(char in value for char in ["<", ">", '"', "'"]):
                return False, f"フィールド {field} に無効な文字が含まれています"

    return True, None


def create_secure_response_headers() -> Dict[str, str]:
    """
    セキュアな HTTP レスポンスヘッダーを作成します。

    Returns:
        セキュリティヘッダーの辞書
    """
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Headers": "Content-Type,X-Asana-Token,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }

    # セキュリティヘッダーを追加
    headers.update(SecurityConfig.SECURITY_HEADERS)

    # 注意: 本番環境では CORS オリジンを制限してください
    # デモ目的のため、すべてのオリジンを許可しています
    headers["Access-Control-Allow-Origin"] = "*"

    return headers
