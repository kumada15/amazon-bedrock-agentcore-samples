import os
import logging
from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
import json
import traceback

# ローカルモジュールをインポート
from prompt_manager import get_prompt
from dynamodb_manager import DynamoDBManager
from cart_subagent import cart_manager
from shopping_subagent import shopping_assistant

# ログ設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# ローカル開発用に CORS を有効化
app.cors_allow_origins = ["http://localhost:3000", "http://localhost:5173"]
app.cors_allow_methods = ["GET", "POST", "OPTIONS"]
app.cors_allow_headers = ["Content-Type", "Authorization"]

REGION = os.getenv("AWS_REGION")
MEMORY_ID = os.getenv("MEMORY_ID")

# Bedrock モデルを初期化 - ルーティング/調整用の Claude 4.5 Sonnet
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    temperature=0.1,
)


def get_user_profile_data(user_id: str) -> str:
    """プロンプト用にフォーマットされたユーザープロファイルデータを取得する"""
    try:
        manager = DynamoDBManager(region_name=REGION)
        profile = manager.get_user_profile(user_id)

        if not profile:
            return "User profile not available"

        # プロファイル情報を抽出
        profile_parts = []

        # 重要: まず userId を含める - これはユーザーの一意の識別子
        if profile.get("userId"):
            profile_parts.append(
                f"User ID (use this for all tool calls): {profile['userId']}"
            )

        if profile.get("name"):
            profile_parts.append(f"Name: {profile['name']}")

        if profile.get("email"):
            profile_parts.append(f"Email: {profile['email']}")

        if profile.get("address"):
            profile_parts.append(f"Address: {profile['address']}")

        if profile.get("notes"):
            profile_parts.append(f"Notes: {profile['notes']}")

        if profile.get("preferences"):
            preferences = profile["preferences"]
            if isinstance(preferences, str):
                try:
                    prefs = json.loads(preferences)
                    profile_parts.append(f"Preferences: {json.dumps(prefs)}")
                except json.JSONDecodeError:
                    profile_parts.append(f"Preferences: {preferences}")
            else:
                profile_parts.append(f"Preferences: {preferences}")

        if profile.get("onboardingCompleted"):
            profile_parts.append(
                f"Onboarding completed: {profile['onboardingCompleted']}"
            )

        if profile_parts:
            profile_text = f", Profile: {'; '.join(profile_parts)}"
        else:
            profile_text = ", Profile: Basic user profile available"

        return profile_text

    except Exception as e:
        logger.error(f"ユーザープロファイルの取得中にエラーが発生しました: {e}")
        return "User profile not available"


def create_supervisor_agent(user_id: str, session_id: str) -> Agent:
    """AgentCore メモリセッションマネージャーでスーパーバイザーエージェントを作成する"""
    # ユーザープロファイルデータを取得
    try:
        user_profile = get_user_profile_data(user_id)
        logger.info(f"{user_id} のユーザープロファイルを取得しました: {user_profile[:200]}...")
    except Exception as e:
        logger.warning(f"{user_id} のユーザープロファイルを取得できませんでした: {e}")
        user_profile = "User profile not available"

    # ベースプロンプトを取得し、ユーザープロファイルコンテキストを追加
    base_prompt = get_prompt("travel_agent_supervisor").format(
        user_profile=user_profile
    )

    # AgentCore Memory 統合を設定
    agentcore_memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID, session_id=session_id, actor_id=f"supervisor-{user_id}"
    )

    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=agentcore_memory_config, region_name=REGION
    )

    logger.info("セッションマネージャーを使用してスーパーバイザーエージェントを作成中...")

    # カートとショッピングサブエージェントでエージェントを作成
    agent = Agent(
        name="supervisor_agent",
        system_prompt=base_prompt,
        tools=[cart_manager, shopping_assistant],
        model=bedrock_model,
        session_manager=session_manager,
        trace_attributes={
            "user.id": user_id,
            "session.id": session_id,
        },
    )
    logger.info("エージェントを cart と shopping サブエージェントで作成しました")

    logger.info("スーパーバイザーエージェントをセッションマネージャーで正常に作成しました")
    return agent


@app.entrypoint
async def agent_stream(payload):
    """セッションマネージャーを使用したスーパーバイザーエージェントのメインエントリーポイント"""
    user_query = payload.get("prompt")
    user_id = payload.get("user_id")
    session_id = payload.get("session_id")

    if not all([user_query, user_id, session_id]):
        yield {
            "status": "error",
            "error": "Missing required fields: prompt, user_id, or session_id",
        }
        return

    try:
        logger.info(
            f"ユーザー: {user_id}, セッション: {session_id} のストリーミング呼び出しを開始"
        )
        logger.info(f"クエリ: {user_query}")

        agent = create_supervisor_agent(user_id, session_id)

        # 真のトークンレベルストリーミング用にエージェントの stream_async メソッドを使用
        async for event in agent.stream_async(user_query):
            yield event

    except Exception as e:
        logger.error(f"agent_stream でエラーが発生しました: {e}")
        traceback.print_exc()
        yield {"status": "error", "error": str(e)}


if __name__ == "__main__":
    app.run()
