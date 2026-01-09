#!/usr/bin/env python3
"""Claude Code SDK のクイックスタート例。"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

app = BedrockAgentCoreApp()


async def basic_example(prompt):
    """基本的な例 - シンプルな質問。

    Args:
        prompt: Claude に送信するプロンプト

    Yields:
        Claude からのメッセージ
    """
    print("=== 基本的な例 ===")

    async for message in query(prompt=prompt):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        yield message
    print()


async def with_options_example(prompt):
    """カスタムオプション付きの例。

    Args:
        prompt: Claude に送信するプロンプト

    Yields:
        Claude からのメッセージ
    """
    print("=== オプション付きの例 ===")

    options = ClaudeAgentOptions(
        system_prompt="あなたは物事を簡潔に説明する親切なアシスタントです。",
        max_turns=1,
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        yield message
    print()


async def with_tools_example(prompt):
    """ツールを使用する例。

    Args:
        prompt: Claude に送信するプロンプト

    Yields:
        Claude からのメッセージ
    """
    print("=== ツール使用の例 ===")

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write"],
        system_prompt="あなたは親切なファイルアシスタントです。",
    )

    async for message in query(
        prompt=prompt,
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        elif isinstance(message, ResultMessage) and message.total_cost_usd > 0:
            print(f"\nCost: ${message.total_cost_usd:.4f}")
        yield message
    print()


async def main(prompt, mode):
    """モードに基づいて適切な例を実行する。

    Args:
        prompt: Claude に送信するプロンプト
        mode: 実行する例のモード（1、2、または 3）

    Yields:
        選択した例からのメッセージ
    """

    if mode == 1:
        async for message in basic_example(prompt):
            yield message
    elif mode == 2:
        async for message in with_options_example(prompt):
            yield message
    elif mode == 3:
        async for message in with_tools_example(prompt):
            yield message
    else:
        yield "Input prompt and mode in [1,2,3]"


@app.entrypoint
async def run_main(payload):
    print("ペイロードを受信しました")
    print(payload)

    print("エージェントに送信中:")
    async for message in main(payload["prompt"], payload["mode"]):
        yield message


if __name__ == "__main__":
    app.run()
