#!/usr/bin/env python3
"""
デプロイ済み MCP サーバーのテストスクリプト
MCP Python クライアントライブラリを使用してサーバーと適切に通信
"""

import asyncio
import sys
from datetime import timedelta
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def extract_region_from_arn(arn):
    """エージェント Runtime ARN から AWS リージョンを抽出

    ARN 形式: arn:aws:bedrock-agentcore:REGION:account:runtime/id

    Args:
        arn: エージェント Runtime ARN 文字列

    Returns:
        str: AWS リージョンコード

    Raises:
        ValueError: ARN 形式が無効またはリージョンを抽出できない場合
    """
    try:
        parts = arn.split(':')
        if len(parts) < 4:
            raise ValueError(
                f"Invalid ARN format: {arn}\n"
                f"Expected format: arn:aws:bedrock-agentcore:REGION:account:runtime/id"
            )
        
        region = parts[3]
        if not region:
            raise ValueError(
                f"Region not found in ARN: {arn}\n"
                f"Expected format: arn:aws:bedrock-agentcore:REGION:account:runtime/id"
            )
        
        return region
        
    except IndexError:
        raise ValueError(
            f"Invalid ARN format: {arn}\n"
            f"Expected format: arn:aws:bedrock-agentcore:REGION:account:runtime/id"
        )


async def test_mcp_server(agent_arn, bearer_token, region):
    """デプロイ済み MCP サーバーをテスト"""

    # URL 用に ARN をエンコード
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }

    print(f"接続先: {mcp_url}")
    print()

    try:
        async with streamablehttp_client(
            mcp_url, headers, timeout=timedelta(seconds=120), terminate_on_close=False
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                print("🔄 MCPセッションを初期化中...")
                await session.initialize()
                print("✓ MCPセッションの初期化完了\n")

                print("🔄 利用可能なツールを取得中...")
                tool_result = await session.list_tools()

                print("\n📋 利用可能なMCPツール:")
                print("=" * 50)
                for tool in tool_result.tools:
                    print(f"🔧 {tool.name}: {tool.description}")

                print("\n🧪 MCPツールをテスト中:")
                print("=" * 50)

                # add_numbers をテスト
                print("\n➕ add_numbers(5, 3)をテスト中...")
                add_result = await session.call_tool(
                    name="add_numbers", arguments={"a": 5, "b": 3}
                )
                print(f"   結果: {add_result.content[0].text}")

                # multiply_numbers をテスト
                print("\n✖️  multiply_numbers(4, 7)をテスト中...")
                multiply_result = await session.call_tool(
                    name="multiply_numbers", arguments={"a": 4, "b": 7}
                )
                print(f"   結果: {multiply_result.content[0].text}")

                # greet_user をテスト
                print("\n👋 greet_user('Alice')をテスト中...")
                greet_result = await session.call_tool(
                    name="greet_user", arguments={"name": "Alice"}
                )
                print(f"   結果: {greet_result.content[0].text}")

                print("\n✅ MCPツールのテストが完了しました！")

    except Exception as e:
        print(f"❌ エラー: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print("使用方法: python test_mcp_server.py <agent_arn> <bearer_token> [region]")
        print("\nリージョンはオプションです - 指定しない場合はARNから抽出されます")
        print("\n例:")
        print(
            "  python test_mcp_server.py arn:aws:bedrock-agentcore:<region>:... eyJraWQiOiJ..."
        )
        sys.exit(1)

    agent_arn = sys.argv[1]
    bearer_token = sys.argv[2]

    # ARN からリージョンを抽出するか、指定されたリージョンを使用
    if len(sys.argv) > 3:
        region = sys.argv[3]
        print(f"指定されたリージョンを使用: {region}")
    else:
        try:
            region = extract_region_from_arn(agent_arn)
            print(f"ARNからリージョンを抽出: {region}")
        except ValueError as e:
            print(f"\n❌ エラー: {e}\n")
            sys.exit(1)

    asyncio.run(test_mcp_server(agent_arn, bearer_token, region))


if __name__ == "__main__":
    main()
