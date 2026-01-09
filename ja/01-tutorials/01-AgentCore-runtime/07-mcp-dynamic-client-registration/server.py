from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """2つの数値を足し算"""
    return a + b

@mcp.tool()
def multiply_numbers(a: int, b: int) -> int:
    """2つの数値を掛け算"""
    return a * b

@mcp.tool()
def greet_user(name: str) -> str:
    """ユーザーを名前で挨拶"""
    return f"Hello, {name}! Nice to meet you."

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
