from strands import Agent, tool
from strands_tools import calculator # Import the calculator tool
import argparse
import json
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.models import BedrockModel
import asyncio
from datetime import datetime

app = BedrockAgentCoreApp()

# カスタムツールを作成
@tool
def weather():
    """ 天気を取得 """ # ダミー実装
    return "sunny"

@tool
def get_time():
    """ 現在時刻を取得 """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[
        calculator, weather, get_time
    ],
    system_prompt="""あなたは親切なアシスタントです。簡単な計算、
    天気の確認、現在時刻の提供ができます。"""
)

@app.entrypoint
async def strands_agent_bedrock_streaming(payload):
    """
    ストリーミング機能を使用してエージェントを呼び出す
    この関数は、非同期ジェネレーターを使用して
    AgentCore Runtimeでストリーミングレスポンスを実装する方法を示します
    """
    user_input = payload.get("prompt")
    print("ユーザー入力:", user_input)

    try:
        # 利用可能になった各チャンクをストリーム
        async for event in agent.stream_async(user_input):
            if "data" in event:
                yield event["data"]

    except Exception as e:
        # ストリーミングコンテキストでエラーを適切に処理
        error_response = {"error": str(e), "type": "stream_error"}
        print(f"ストリーミングエラー: {error_response}")
        yield error_response

if __name__ == "__main__":
    app.run()
