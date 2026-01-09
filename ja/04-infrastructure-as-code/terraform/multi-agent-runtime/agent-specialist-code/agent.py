from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

def create_specialist_agent() -> Agent:
    """特定の分析タスクを処理するスペシャリストエージェントを作成"""
    system_prompt = """あなたはスペシャリスト分析エージェントです。
    データ分析と詳細なインサイトの提供を専門としています。
    質問されたら、具体的な詳細を含む徹底的で論理的なレスポンスを提供してください。
    回答の正確性と完全性に注力してください。"""

    return Agent(
        system_prompt=system_prompt,
        name="SpecialistAgent"
    )

@app.entrypoint
async def invoke(payload=None):
    """スペシャリストエージェントのメインエントリポイント"""
    try:
        # ペイロードからクエリを取得
        query = payload.get("prompt", "Hello") if payload else "Hello"

        # スペシャリストエージェントを作成して使用
        agent = create_specialist_agent()
        response = agent(query)

        return {
            "status": "success",
            "agent": "specialist",
            "response": response.message['content'][0]['text']
        }

    except Exception as e:
        return {
            "status": "error",
            "agent": "specialist",
            "error": str(e)
        }

if __name__ == "__main__":
    app.run()
