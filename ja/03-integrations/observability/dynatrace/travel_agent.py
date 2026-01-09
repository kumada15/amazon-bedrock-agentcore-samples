import os
from strands import Agent, tool
from strands_tools import calculator  # Import the calculator tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# Create a custom tool
@tool
def weather():
    """天気を取得します"""  # ダミー実装
    return "sunny"


model_id = os.getenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-3-7-sonnet-20250219-v1:0")
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    tools=[calculator, weather],
    system_prompt="あなたは親切なアシスタントです。簡単な数学の計算や天気を教えることができます。",
)

@app.entrypoint
def strands_agent_bedrock(payload):
    """
    ペイロードを使用してエージェントを呼び出します
    """
    user_input = payload.get("prompt")
    response = agent(user_input)
    return response.message["content"][0]["text"]
