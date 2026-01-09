from strands import Agent, tool
from strands_tools import calculator # calculator ツールをインポート
import argparse
import json
from strands.models.litellm import LiteLLMModel
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

os.environ["AZURE_API_KEY"] = "<YOUR_API_KEY>"
os.environ["AZURE_API_BASE"] = "<YOUR_API_BASE>"
os.environ["AZURE_API_VERSION"] = "<YOUR_API_VERSION>"

# カスタムツールを作成
@tool
def weather():
    """ 天気を取得 """ # ダミー実装
    return "sunny"

model = "azure/gpt-4.1-mini"
litellm_model = LiteLLMModel(
    model_id=model, params={"max_tokens": 32000, "temperature": 0.7}
)


agent = Agent(
    model=litellm_model,
    tools=[calculator, weather],
    system_prompt="あなたは親切なアシスタントです。簡単な計算と天気を教えることができます。"
)


@app.entrypoint
def strands_agent_open_ai(payload):
    """
    ペイロードでエージェントを呼び出す
    """
    user_input = payload.get("prompt")
    print("ユーザー入力:", user_input)
    response = agent(user_input)
    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
