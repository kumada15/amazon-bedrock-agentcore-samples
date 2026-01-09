from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

def create_basic_agent() -> Agent:
    """シンプルな機能を持つ基本エージェントを作成"""
    system_prompt = """あなたは親切なアシスタントです。質問に明確かつ簡潔に回答してください。"""

    return Agent(
        system_prompt=system_prompt,
        name="BasicAgent"
    )

@app.entrypoint
async def invoke(payload=None):
    """エージェントのメインエントリポイント"""
    try:
        # ペイロードからクエリを取得
        query = payload.get("prompt", "Hello, how are you?") if payload else "Hello, how are you?"

        # エージェントを作成して使用
        agent = create_basic_agent()
        response = agent(query)

        return {
            "status": "success",
            "response": response.message['content'][0]['text']
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    app.run()
