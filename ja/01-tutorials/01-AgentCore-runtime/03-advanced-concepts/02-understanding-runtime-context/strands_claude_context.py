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
    system_prompt="""
    あなたは親切なアシスタントです。簡単な計算、
    天気の確認、現在時刻の提供ができます。
    常にユーザーの名前を確認することから始めてください。
    """
)

def get_user_name(user_id):
    users = {
        "1": "Maira",
        "2": "Mani",
        "3": "Mark",
        "4": "Ishan",
        "5": "Dhawal"
    }
    return users[user_id]

@app.entrypoint
def strands_agent_bedrock_handling_context(payload, context):
    """
    コンテキスト処理とセッション管理を示すAgentCore Runtimeエントリーポイント。

    Args:
        payload: ユーザーデータとリクエスト情報を含む入力ペイロード
        context: セッションと実行情報を含むランタイムコンテキストオブジェクト

    Returns:
        str: コンテキスト情報を組み込んだエージェントのレスポンス
    """
    user_input = payload.get("prompt")
    user_id = payload.get("user_id")
    user_name = get_user_name(user_id)

    # ランタイムコンテキスト情報にアクセス
    print("=== ランタイムコンテキスト情報 ===")
    print("ユーザーID:", user_id)
    print("ユーザー名:", user_name)
    print("ユーザー入力:", user_input)
    print("ランタイムセッションID:", context.session_id)
    print("コンテキストオブジェクトタイプ:", type(context))
    print("=== コンテキスト情報終了 ===")

    # コンテキスト情報を含むパーソナライズされたプロンプトを作成
    prompt = f"""私の名前は{user_name}です。リクエストは次のとおりです: {user_input}

    追加コンテキスト: これはセッション {context.session_id} です。
    私の名前を確認して、サポートをお願いします。"""

    response = agent(prompt)
    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
