import asyncio
import os
from bedrock_agentcore.identity.auth import requires_api_key
from strands import Agent
from strands.models.openai import OpenAIModel
from strands_tools import calculator
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Global agent variable
agent = None

@requires_api_key(
    provider_name="openai-apikey-provider" # replace with your own credential provider name
)
async def need_api_key(*, api_key: str):
    print("非同期関数でAPIキーを受信しました")
    os.environ["OPENAI_API_KEY"] = api_key

def create_model():
    """APIキーを使用してOpenAIモデルを作成します"""
    return OpenAIModel(
        client_args={
            "api_key": os.environ.get("OPENAI_API_KEY"), 
        },
        model_id="gpt-4o",
        params={
            "max_tokens": 1000,
            "temperature": 0.7,
        }
    )

app = BedrockAgentCoreApp()

@app.entrypoint
async def strands_agent_open_ai(payload):
    """
    ペイロードを使用してエージェントを呼び出します
    """
    global agent
    
    print(f"エントリーポイントが呼び出されました")
    
    # Get API key if not already set in environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("APIキーの取得を試行中...")
        try:
            await need_api_key(api_key="")
            print("APIキーを取得し、環境変数に設定しました")
        except Exception as e:
            print(f"APIキーの取得エラー: {e}")
            raise
    else:
        print("APIキーは既に環境変数に設定されています")
    
    # Initialize agent after API key is set
    if agent is None:
        print("APIキーを使用してエージェントを初期化中...")
        model = create_model()
        agent = Agent(model=model, tools=[calculator])
    user_input = payload.get("prompt")
    print(f"ユーザー入力: {user_input}")
    
    try:
        response = agent(user_input)
        print(f"エージェントの応答: {response}")
        return response.message['content'][0]['text']
    except Exception as e:
        print(f"エージェント処理中のエラー: {e}")
        raise

if __name__ == "__main__":
    app.run()