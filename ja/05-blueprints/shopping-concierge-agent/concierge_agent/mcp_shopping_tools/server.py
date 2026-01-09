"""
Shopping Tools MCP サーバー

SerpAPI を使用して MCP プロトコル経由でショッピング/商品検索ツールを公開します。
エージェントロジックなし - 純粋なツール実装のみ。
"""

import os
import logging
from typing import Dict, Any
from mcp.server import FastMCP
from serp_tools import search_products, generate_packing_list

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION")
if not REGION:
    raise ValueError("AWS_REGION environment variable is required")

# MCP サーバーを作成
mcp = FastMCP(
    "Shopping Tools", host="0.0.0.0", stateless_http=True
)  # nosec B104:standard pattern for containerized MCP servers


# =============================================================================
# MCP ツール - 生のツール公開
# =============================================================================


@mcp.tool()
def single_productsearch(user_id: str, question: str) -> Dict[str, Any]:
    """
    SerpAPI を使用してユーザーのクエリに基づいて Amazon で商品を検索する。

    Args:
        user_id: ユーザー識別子
        question: 商品検索クエリ（例: 「防水ハイキングブーツ」）

    Returns:
        ASIN、商品詳細、およびフォーマット済み回答を含む商品検索結果
    """
    return search_products(user_id, question)


@mcp.tool()
def generate_packinglist_with_productASINS(
    user_id: str, question: str
) -> Dict[str, Any]:
    """
    SerpAPI を使用して旅行用の商品推奨付きパッキングリストを生成する。

    Args:
        user_id: ユーザー識別子
        question: パッキングリストの旅行詳細（例: 「ハワイ 5 日間のビーチバケーション」）

    Returns:
        商品推奨、ASIN、およびフォーマット済み回答を含むパッキングリスト
    """
    return generate_packing_list(user_id, question)


# =============================================================================
# サーバー起動
# =============================================================================

if __name__ == "__main__":
    logger.info("Shopping Tools MCP サーバーを起動中...")
    mcp.run(transport="streamable-http")
