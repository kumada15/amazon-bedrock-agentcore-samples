# 基本的な Strands Agent ストリーミングの例。
# ローカルでテストするには、`uv run agent.py` を実行してから
# curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "こんにちは！"}'

import argparse
import asyncio
import datetime
import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator

app = BedrockAgentCoreApp()


@tool
def weather():
    """天気を取得します"""
    return "sunny"


model_id = "us.amazon.nova-pro-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[calculator, weather],
    system_prompt="あなたは親切なアシスタントです。簡単な数学の計算や天気を教えることができます。",
)


@app.entrypoint
async def strands_agent_bedrock(payload):
    """
    ペイロードを使用してエージェントを呼び出します
    """
    user_input = payload.get("prompt")
    agent_stream = agent.stream_async(user_input)
    tool_name = None
    try:
        async for event in agent_stream:

            if (
                "current_tool_use" in event
                and event["current_tool_use"].get("name") != tool_name
            ):
                tool_name = event["current_tool_use"]["name"]
                yield f"\n\n🔧 Using tool: {tool_name}\n\n"

            if "data" in event:
                tool_name = None
                yield event["data"]
    except Exception as e:
        yield f"Error: {str(e)}"


if __name__ == "__main__":
    app.run()
