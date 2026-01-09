import asyncio
import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from strands import Agent
from strands_tools import calculator

# コールバックハンドラーなしでエージェントを初期化
agent = Agent(
    tools=[calculator],
    callback_handler=None
)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def agent_invocation(payload, context):
    """ストリーミングサポート付きのエージェント呼び出しハンドラー"""
    user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    
    print("コンテキスト:\n-------\n", context)
    print("メッセージを処理中:\n*******\n", user_message)
    
    # エージェントストリームを取得
    agent_stream = agent.stream_async(user_message)

    async for event in agent_stream:
        yield event

if __name__ == "__main__":
    app.run()
