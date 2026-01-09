#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys
import traceback
import urllib.parse
from bedrock_agentcore.identity.auth import requires_access_token
from datetime import timedelta
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from utils import get_ssm_parameter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_mcp_client(provider_name, agent_arn):
    """指定されたパラメータで MCP クライアントを作成する"""

    # Extract runtime_id, region, and account_id from ARN
    # ARN format: arn:aws:bedrock-agentcore:region:account-id:runtime/runtime-id
    runtime_id = agent_arn.split('/')[-1]
    arn_parts = agent_arn.split(':')
    region = arn_parts[3]
    account_id = arn_parts[4]

    print(f"📋 AWSアカウントID: {account_id}")
    print(f"🌍 AWSリージョン: {region}")
    print(f"🤖 MCPランタイムID: {runtime_id}")

    @requires_access_token(
        provider_name=provider_name,
        scopes=[],
        auth_flow="M2M",
        into="bearer_token",
        force_authentication=True,
    )
    async def connect(bearer_token):
        print(f"Bearer トークンを受信しました: {bearer_token}")

        print(agent_arn)
        escaped_arn = urllib.parse.quote(agent_arn, safe="")
        mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"

        headers = {
            "authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }

        print(f"🔗 接続中: {mcp_url}")
        logger.info(f"エージェント ARN: {agent_arn}")
        logger.info(f"ヘッダー: {dict(headers)}")

        try:
            logger.info("ストリーマブル HTTP クライアントを作成中...")
            async with streamablehttp_client(
                    mcp_url,
                    headers,
                    timeout=timedelta(seconds=120),
                    terminate_on_close=False,
            ) as (read_stream, write_stream, _):
                logger.info("HTTP クライアントが正常に作成されました")
                logger.info("MCP クライアントセッションを作成中...")

                try:
                    async with ClientSession(read_stream, write_stream) as session:
                        print("🔄 MCPセッションを初期化中...")
                        logger.info("session.initialize() を呼び出し中...")
                        await session.initialize()
                        logger.info("セッションが正常に初期化されました")
                        print("✅ MCPセッションが初期化されました")

                        # List available tools
                        print("\n🔄 利用可能なツールを一覧表示中...")
                        logger.info("session.list_tools() を呼び出し中...")
                        tool_result = await session.list_tools()
                        logger.info(f"{len(tool_result.tools)} 個のツールを取得しました")

                        print("\n📋 利用可能なMCPツール:")
                        print("=" * 50)
                        for tool in tool_result.tools:
                            print(f"🔧 {tool.name}")
                            print(f"   Description: {tool.description}")
                            if hasattr(tool, "inputSchema") and tool.inputSchema:
                                properties = tool.inputSchema.get("properties", {})
                                if properties:
                                    print(f"   Parameters: {list(properties.keys())}")
                            print()

                        print(f"✅ {len(tool_result.tools)}個のツールが利用可能です。")

                        # Test some tools
                        print("\n🧪 MCPツールをテスト中:")
                        print("=" * 50)

                        test_cases = [
                            ("get_reviews", {"review_id": "1"}),
                            ("get_products", {"product_id": 1}),
                        ]

                        for tool_name, args in test_cases:
                            try:
                                print(f"\n➕ {tool_name}({args})をテスト中...")
                                logger.info(
                                    f"ツール {tool_name} を引数 {args} で呼び出し中"
                                )
                                result = await session.call_tool(
                                    name=tool_name, arguments=args
                                )
                                logger.info(f"ツール {tool_name} の戻り値: {result}")
                                if result.content:
                                    print(f"   Result: {result.content[0].text}")
                                else:
                                    print("   No content returned")
                            except Exception as e:
                                logger.error(f"ツール {tool_name} の呼び出し中にエラーが発生しました: {e}")
                                logger.error(f"トレースバック: {traceback.format_exc()}")
                                print(f"   Error: {e}")

                except Exception as session_e:
                    logger.error(f"MCP セッションでエラーが発生しました: {session_e}")
                    logger.error(f"セッショントレースバック: {traceback.format_exc()}")
                    raise session_e

        except Exception as e:
            logger.error(f"ストリーマブル HTTP クライアントでエラーが発生しました: {e}")
            logger.error(f"完全なトレースバック: {traceback.format_exc()}")
            print(f"❌ MCPサーバーへの接続エラー: {e}")

            # Print any nested exception details
            if hasattr(e, "__cause__") and e.__cause__:
                logger.error(f"原因: {e.__cause__}")
                logger.error(
                    f"原因のトレースバック: {traceback.format_exception(type(e.__cause__), e.__cause__, e.__cause__.__traceback__)}"
                )

            if hasattr(e, "__context__") and e.__context__:
                logger.error(f"コンテキスト: {e.__context__}")

            sys.exit(1)

    return connect


def main():
    parser = argparse.ArgumentParser(description="MCP DynamoDB CLI Tool")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Set logging level based on arguments
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    print("🚀 MCP DynamoDB CLIツール")
    print("=" * 30)

    # Get MCP Runtime ARN and Provider Name from SSM Parameter Store
    agent_arn = get_ssm_parameter("/app/customersupportvpc/mcp/mcp_runtime_arn")
    provider_name = get_ssm_parameter("/app/customersupportvpc/mcp/mcp_provider_name")

    print(f"🤖 MCPランタイムARN: {agent_arn}")
    print(f"🔐 OAuth2プロバイダー: {provider_name}")

    # Create and run the MCP client
    try:
        client = create_mcp_client(provider_name, agent_arn)
        asyncio.run(client())
    except KeyboardInterrupt:
        print("\n👋 ユーザーにより中断されました")
    except Exception as e:
        logger.error(f"メイン処理で予期しないエラーが発生しました: {e}")
        logger.error(f"メインのトレースバック: {traceback.format_exc()}")
        print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
