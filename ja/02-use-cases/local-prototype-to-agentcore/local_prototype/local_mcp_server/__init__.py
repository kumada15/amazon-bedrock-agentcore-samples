"""
LocalMCP MCP Server - プロジェクト管理と開発のためのモジュラー MCP サーバー
"""

from .config import SERVER_NAME, SERVER_VERSION

__version__ = SERVER_VERSION
__name__ = SERVER_NAME

__all__ = ['SERVER_NAME', 'SERVER_VERSION']
