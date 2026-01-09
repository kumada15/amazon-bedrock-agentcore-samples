from mcp.server.fastmcp import FastMCP

mcp = FastMCP(host="127.0.0.1", stateless_http=True)


@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """2つの数値を加算する"""
    return a + b


@mcp.tool()
def multiply_numbers(a: int, b: int) -> int:
    """2つの数値を乗算する"""
    return a * b


@mcp.tool()
def greet_user(name: str) -> str:
    """名前でユーザーに挨拶する"""
    return f"Hello, {name}! Nice to meet you."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
