#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys
import traceback
from bedrock_agentcore.identity.auth import requires_access_token
from datetime import timedelta
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient

from utils import get_ssm_parameter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

gateway_access_token = None


@requires_access_token(
    provider_name=get_ssm_parameter(
        "/app/customersupportvpc/gateway/oauth2_provider_name"
    ),
    scopes=[],  # Optional unless required
    auth_flow="M2M",
)
async def _get_access_token_manually(access_token: str):
    global gateway_access_token
    gateway_access_token = access_token
    return access_token


async def connect_to_gateway(gateway_url: str, prompt: str):
    """Gateway に接続してプロンプトを送信する"""

    print(f"🔗 Gateway URL: {gateway_url}")
    print(gateway_access_token)
    # Set up MCP client
    client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {gateway_access_token}"},
            timeout=timedelta(seconds=120),
        )
    )

    try:
        with client:
            print("✅ Gateway に接続しました")

            # List available tools
            print("\n🔄 利用可能なツールを一覧表示中...")
            tools = client.list_tools_sync()

            print("\n📋 利用可能な Gateway ツール:")
            print("=" * 50)
            for tool in tools:
                print(f"🔧 {tool.tool_name}")
                # print(f"   Description: {tool.description}")
                if hasattr(tool, "input_schema") and tool.input_schema:
                    properties = tool.input_schema.get("properties", {})
                    if properties:
                        print(f"   パラメータ: {list(properties.keys())}")
                print()

            print(f"✅ {len(tools)} 個のツールが利用可能です。")

            # Create agent with tools and send prompt
            print("\n🤖 エージェントにプロンプトを送信中...")
            print(f"📝 プロンプト: {prompt}")
            print("=" * 50)

            print("\n🤖 エージェントの応答:")
            print("=" * 50)
            agent = Agent(tools=tools)
            agent(prompt)

    except Exception as e:
        logger.error(f"Gateway への接続中にエラーが発生しました: {e}")
        logger.error(f"トレースバック: {traceback.format_exc()}")
        print(f"❌ エラー: {e}")
        sys.exit(1)


def main():
    """プロンプトを使用して Gateway と対話する CLI ツール。"""

    parser = argparse.ArgumentParser(description="Gateway MCP CLI Tool")
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Prompt to send to the gateway agent"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Set logging level based on arguments
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    print("🚀 Gateway MCP CLI ツール")
    print("=" * 30)

    # Fetch access token first
    print("🔐 OAuth2 アクセストークンを取得中...")
    try:
        asyncio.run(_get_access_token_manually(access_token=""))
        print("✅ アクセストークンを正常に取得しました")
    except Exception as e:
        logger.error(f"アクセストークンの取得に失敗しました: {e}")
        print(f"❌ アクセストークンの取得に失敗しました: {e}")
        sys.exit(1)

    # Get gateway URL from SSM Parameter Store
    try:
        gateway_url = get_ssm_parameter(
            "/app/customersupportvpc/gateway/gateway_url"
        )
        print(f"🌐 Gateway URL: {gateway_url}")
    except Exception as e:
        logger.error(f"Gateway URL の読み取り中にエラーが発生しました: {e}")
        print(f"❌ SSM から Gateway URL を読み取る際にエラーが発生しました: {str(e)}")
        sys.exit(1)

    # Connect to gateway and send prompt
    try:
        asyncio.run(connect_to_gateway(gateway_url, args.prompt))
    except KeyboardInterrupt:
        print("\n👋 ユーザーによって中断されました")
    except Exception as e:
        logger.error(f"メイン処理で予期しないエラーが発生しました: {e}")
        logger.error(f"メインのトレースバック: {traceback.format_exc()}")
        print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
