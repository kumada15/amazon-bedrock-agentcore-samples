
from pydantic_ai.agent import Agent, RunContext

from datetime import datetime
import json
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic_ai.models.bedrock import BedrockConverseModel

app = BedrockAgentCoreApp()

model = BedrockConverseModel('global.anthropic.claude-haiku-4-5-20251001-v1:0')
dummy_agent = Agent(
    model=model,
    system_prompt="あなたは親切なアシスタントです。質問に回答するために利用可能なツールを使用してください。"

)

@dummy_agent.tool  
def get_current_date(ctx: RunContext[datetime]):
  print("現在の日付を取得中...")
  current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  return current_date


@dummy_agent.tool
def get_weather(ctx: RunContext[str]):
        # Simulated weather data
  return f"Sunny"

@app.entrypoint
def pydantic_bedrock_claude_main(payload):
  """
   Invoke the agent with a payload
  """
  user_input = payload.get("prompt")
  result = dummy_agent.run_sync(user_input)
  print(result.output)
  return result.output


if __name__ == "__main__":
    app.run()
