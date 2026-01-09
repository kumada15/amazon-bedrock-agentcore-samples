from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
import logging

# ロギングを設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("autogen_agent")

print(1)
# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/quickstart.html を参考
# モデルクライアントを定義します。`ChatCompletionClient` インターフェースを
# 実装する他のモデルクライアントも使用できます。
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# モデルクライアントを定義します。`ChatCompletionClient` インターフェースを
# 実装する他のモデルクライアントも使用できます。
model_client = OpenAIChatCompletionClient(
    model="gpt-4o",
)

print(2)

# エージェントが使用できるシンプルな関数ツールを定義します。
# この例では、デモンストレーション用のダミー天気ツールを使用します。
async def get_weather(city: str) -> str:
    """指定された都市の天気を取得します。"""
    print("ツール")
    return f"The weather in {city} is 73 degrees and Sunny."


# モデル、ツール、システムメッセージ、リフレクションを有効にした AssistantAgent を定義します。
# システムメッセージは自然言語でエージェントに指示を与えます。
agent = AssistantAgent(
    name="weather_agent",
    model_client=model_client,
    tools=[get_weather],
    system_message="あなたは親切なアシスタントです。",
    reflect_on_tool_use=True,
    model_client_stream=True,  # モデルクライアントからのストリーミングトークンを有効化
)

print(4)

# エージェントを実行し、メッセージをコンソールにストリーミングします。


from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def main(payload):
    logger.debug("エージェントの実行を開始")
    print(5)
    
    try:
        # ペイロードからプロンプトを取得、またはデフォルトを使用
        prompt = payload.get("prompt", "Hello! What can you help me with?")
        logger.debug(f"プロンプトを処理中: {prompt}")
        
        # エージェントを実行
        result = await Console(agent.run_stream(task=prompt))
        logger.debug(f"エージェントの結果タイプ: {type(result)}")
        print(result)
        
        # JSON シリアライズのため最後のメッセージコンテンツを抽出
        if result and hasattr(result, 'messages') and result.messages:
            last_message = result.messages[-1]
            logger.debug(f"最後のメッセージ: {last_message}")
            if hasattr(last_message, 'content'):
                response = {"result": last_message.content}
                logger.debug(f"レスポンスを返却: {response}")
                return response
        
        # コンテンツを抽出できない場合のフォールバック
        logger.warning("結果からコンテンツを抽出できませんでした")
        return {"result": "レスポンスが生成されませんでした"}
    except Exception as e:
        logger.error(f"メインハンドラーでのエラー: {e}", exc_info=True)
        return {"result": f"エラー: {str(e)}"}
    finally:
        # モデルクライアントへの接続を常に終了する
        logger.debug("モデルクライアント接続を終了中")
        # await model_client.close() ## Runtime でスティッキーセッションを使用している場合はクライアントを閉じないでください。そうしないと `RuntimeError: Cannot send a request, as the client has been closed.` エラーが発生します 

app.run()
