
from strands import Agent, tool
import argparse
import json
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    system_prompt="あなたは親切な技術サポートアシスタントです。技術的なトラブルシューティングやプログラミングに関するユーザーの質問に対応できます。"
)

@app.entrypoint
def strands_agent_bedrock(payload):
    """
    ペイロードでエージェントを呼び出す
    """
    user_input = payload.get("prompt")
    print("ユーザー入力:", user_input)
    response = agent(user_input)
    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
