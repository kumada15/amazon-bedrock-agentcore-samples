"""
アプリケーションコンテキストモデル
"""

from dataclasses import dataclass


@dataclass
class AppContext:
    """サーバー状態を管理するアプリケーションコンテキスト"""
    projects_created: int = 0
    commands_executed: int = 0
