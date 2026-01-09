import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from strands import Agent
from strands_tools import file_read, file_write, editor

agent = Agent(tools=[file_read, file_write, editor])

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    """エージェント呼び出しハンドラー"""
    user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    result = agent(user_message)
    print("コンテキスト:\n-------\n", context)
    print("結果:\n*******\n", result)
    return {"result": result.message}

app.run()