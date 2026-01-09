import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from agents import Agent, Runner
from prompt import SYSTEM_PROMPT
from tools import _get_memory_tools, web_search_impl

# .env ファイルから環境変数を読み込む
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable")

MODEL_ID = os.getenv("MODEL_ID", "gpt-4o-2024-08-06")
MEMORY_ID = os.getenv("MEMORY_ID")
if not MEMORY_ID:
    raise RuntimeError("Missing MEMORY_ID environment variable")


def create_agent(session_id: str, actor_id: str):
    memory_tools = _get_memory_tools(
        memory_id=MEMORY_ID, session_id=session_id, actor_id=actor_id
    )
    logger.info(f"メモリツールを追加予定: {memory_tools}")

    agent_tools = [web_search_impl] + memory_tools

    return Agent(
        name="WebSearch_Agent",
        instructions=SYSTEM_PROMPT,
        model=MODEL_ID,
        tools=agent_tools,
    )


async def _call_agent_stream(agent, prompt: str):
    """
    OpenAI Agents SDK Runner を使用してストリーミングでエージェントを呼び出す。
    ストリーミングイベントと最終結果を yield する。
    """
    try:
        logger.info(f"📝 プロンプトでエージェントを呼び出し中: {prompt[:100]}...")
        logger.info(f"🤖 エージェントタイプ: {type(agent)}")
        logger.info(
            f"🤖 エージェント名: {agent.name if hasattr(agent, 'name') else 'unknown'}"
        )

        # 適切な OpenAI Agents SDK Runner をストリーミングで使用
        logger.info("🏃 ストリーミング実行を開始")

        result = Runner.run_streamed(agent, input=prompt)

        async for event in result.stream_events():
            # 各ストリーミングイベントを yield
            yield {"event": event}

        # ストリーミング完了後、最終結果を yield
        logger.info("✅ エージェントストリーミングが完了しました")

    except Exception as e:
        logger.error(f"❌ エージェント実行中にエラー: {str(e)}", exc_info=True)
        yield {"error": str(e)}
