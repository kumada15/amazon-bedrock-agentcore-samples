import logging
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from bedrock_agentcore import BedrockAgentCoreApp

# ロギングを設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env ファイルから環境変数を読み込む
load_dotenv()

APP_NAME = "HostAgentA2A"

app = BedrockAgentCoreApp()

session_service = InMemorySessionService()

root_agent = None


@app.entrypoint
async def call_agent(payload: dict, context):
    global root_agent

    session_id = context.session_id
    logger.info(f"session_id: {session_id} でリクエストを受信しました")

    actor_id = context.request_headers[
        "x-amzn-bedrock-agentcore-runtime-custom-actorid"
    ]

    if not actor_id:
        raise Exception("Actor id is not is not set")

    if not session_id:
        raise Exception("Context session_id is not set")

    if not root_agent:
        # ワークロード ID が利用可能になるようにエントリーポイント内でエージェント作成をインポート
        from agent import get_agent_and_card

        logger.info("ルートエージェントを初期化し、エージェントカードを解決中...")
        # ルートエージェントを一度作成 - LazyClientFactory は各 A2A 呼び出し時に
        # 現在のイベントループコンテキストで新しい httpx クライアントを作成
        try:
            root_agent, agents_cards = await get_agent_and_card(
                session_id=session_id, actor_id=actor_id
            )
            logger.info(
                f"Root Agent の初期化に成功しました。Agent カード: {list(agents_cards.keys())}"
            )
        except Exception as e:
            logger.error(f"Root Agent の初期化に失敗しました: {e}", exc_info=True)
            raise

        yield agents_cards

    query = payload.get("prompt")
    logger.info(f"クエリを処理中: {query}")

    if not query:
        raise KeyError("'prompt' field is required in payload")

    in_memory_session = session_service.get_session_sync(
        app_name=APP_NAME, user_id=actor_id, session_id=session_id
    )

    if not in_memory_session:
        # セッションが存在しない場合、作成する
        _ = session_service.create_session_sync(
            app_name=APP_NAME, user_id=actor_id, session_id=session_id
        )

    runner = Runner(
        agent=root_agent, app_name=APP_NAME, session_service=session_service
    )

    content = types.Content(role="user", parts=[types.Part(text=query)])

    # 呼び出し間でイベントループを適切に維持するために非同期実行を使用
    async for event in runner.run_async(
        user_id=actor_id, session_id=session_id, new_message=content
    ):
        yield event


if __name__ == "__main__":
    app.run()  # Ready to run on Bedrock AgentCore
