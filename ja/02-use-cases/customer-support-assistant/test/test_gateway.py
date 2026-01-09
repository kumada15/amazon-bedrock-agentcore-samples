#!/usr/bin/python

import asyncio
import click
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.utils import get_ssm_parameter

gateway_access_token = None


@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/cognito_provider"),
    scopes=[],  # Optional unless required
    auth_flow="M2M",
)
async def _get_access_token_manually(*, access_token: str):
    global gateway_access_token
    gateway_access_token = access_token
    return access_token


@click.command()
@click.option("--prompt", "-p", default=None, help="MCP エージェントに送信するプロンプト。指定しない場合は、利用可能なツールの一覧のみ表示します。")
def main(prompt: str):
    """MCP Agent と対話するための CLI ツール。デフォルトではツールを一覧表示し、プロンプトが指定された場合は送信する。"""

    # アクセストークンを取得
    asyncio.run(_get_access_token_manually(access_token=""))

    # SSM パラメータからゲートウェイ設定を読み込み
    try:
        gateway_url = get_ssm_parameter("/app/customersupport/agentcore/gateway_url")
    except Exception as e:
        print(f"❌ SSMからのゲートウェイURL読み取りエラー: {str(e)}")
        sys.exit(1)

    print(f"ゲートウェイエンドポイント - MCP URL: {gateway_url}")

    # MCP クライアントをセットアップ
    client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {gateway_access_token}"},
        )
    )

    with client:
        tools = client.list_tools_sync()

        # プロンプトが提供されていない場合のみ詳細なツール仕様を表示
        if prompt is None:
            print(f"\n📋 利用可能なツール ({len(tools)}):")
            print("-" * 60)
            for i, tool in enumerate(tools, 1):
                # Try to get tool spec from the tool object
                tool_spec = None
                if hasattr(tool, 'tool_spec'):
                    tool_spec = tool.tool_spec
                elif hasattr(tool, 'spec'):
                    tool_spec = tool.spec
                elif hasattr(tool, 'tool'):
                    tool_spec = tool.tool

                if tool_spec:
                    # 仕様からツール情報を抽出
                    tool_name = tool_spec.get('name', f'ツール {i}')
                    tool_desc = tool_spec.get('description', '説明なし')

                    print(f"\n{i}. {tool_name}")
                    print(f"   説明: {tool_desc}")

                    # 入力スキーマがあれば表示
                    if 'inputSchema' in tool_spec:
                        print(f"   入力スキーマ:")
                        import json
                        print(f"   {json.dumps(tool_spec['inputSchema'], indent=6)}")
                else:
                    # フォールバック: 利用可能な属性を表示
                    print(f"\n{i}. ツールオブジェクト属性:")
                    for attr in dir(tool):
                        if not attr.startswith('_'):
                            try:
                                value = getattr(tool, attr)
                                if not callable(value):
                                    print(f"   {attr}: {value}")
                            except:
                                pass
            print("-" * 60)
            print()
            print("ℹ️  プロンプトが指定されていません。--prompt を使用してエージェントにクエリを送信してください。")
            return

        # エージェントにプロンプトを送信
        agent = Agent(tools=tools)
        response = agent(prompt)
        print(str(response))


if __name__ == "__main__":
    main()
