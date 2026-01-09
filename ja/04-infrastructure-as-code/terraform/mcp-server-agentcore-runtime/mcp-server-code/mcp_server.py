from mcp.server.fastmcp import FastMCP

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """2つの数値を加算"""
    return a + b

@mcp.tool()
def multiply_numbers(a: int, b: int) -> int:
    """2つの数値を乗算"""
    return a * b

@mcp.tool()
def greet_user(name: str) -> str:
    """名前でユーザーに挨拶"""
    return f"Hello, {name}! Nice to meet you."

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
