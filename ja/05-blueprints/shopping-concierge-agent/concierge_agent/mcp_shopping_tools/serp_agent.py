import os
from typing import Any, Dict
from mcp.server import FastMCP
from serp_tools import search_products, generate_packing_list

REGION = os.getenv("AWS_REGION")
if not REGION:
    raise ValueError("AWS_REGION environment variable is required")

# MCP サーバーを作成
mcp = FastMCP(
    "Shopping Assistant Agent", host="0.0.0.0", stateless_http=True
)  # nosec B104:standard pattern for containerized MCP servers


@mcp.tool()
def search_products_tool(user_id: str, question: str) -> Dict[str, Any]:
    """
    ユーザーのクエリに一致する商品を Amazon で検索する。

    Args:
        user_id: ユーザーの一意識別子
        question: 商品情報をリクエストするユーザーのクエリテキスト

    Returns:
        'answer'、'asins'、'products' キーを含む辞書
    """
    return search_products(user_id, question)


@mcp.tool()
def generate_packing_list_tool(user_id: str, question: str) -> Dict[str, Any]:
    """
    旅行用の商品推奨付きパッキングリストを生成する。

    Args:
        user_id: ユーザーの一意識別子
        question: 旅行の説明（例: 「ハワイに 1 週間行きます」）

    Returns:
        'answer'、'asins'、'items' キーを含む辞書
    """
    return generate_packing_list(user_id, question)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
