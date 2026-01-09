import logging
from datetime import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from .client import SREMemoryClient

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class ConversationMessage(BaseModel):
    """自動メモリストレージ用の会話メッセージモデル。"""

    content: str = Field(description="The message content")
    role: str = Field(description="Message role: USER, ASSISTANT, or TOOL")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this message was created"
    )
    agent_name: Optional[str] = Field(
        default=None,
        description="Name of the agent that generated this message (if applicable)",
    )
    session_id: Optional[str] = Field(
        default=None, description="Session identifier for grouping messages"
    )


class ConversationMemoryManager:
    """AgentCore Memory を通じた自動会話追跡のマネージャー。"""

    def __init__(self, memory_client: SREMemoryClient):
        self.memory_client = memory_client
        logger.info("ConversationMemoryManager を初期化しました")

    def store_conversation_message(
        self,
        content: str,
        role: str,
        user_id: str,
        session_id: str,
        agent_name: Optional[str] = None,
    ) -> bool:
        """
        create_event を使用して会話メッセージをメモリに保存します。

        Args:
            content: メッセージ内容
            role: USER、ASSISTANT、または TOOL
            user_id: create_event の actor_id として使用するユーザー ID
            session_id: セッション識別子（必須）
            agent_name: エージェント名（該当する場合）

        Returns:
            bool: 成功ステータス
        """
        try:
            if not user_id:
                raise ValueError("user_id is required for conversation message storage")
            if not session_id:
                raise ValueError(
                    "session_id is required for conversation message storage"
                )

            # 会話メッセージモデルを作成（検証用）
            ConversationMessage(
                content=content, role=role, agent_name=agent_name, session_id=session_id
            )

            logger.info(
                f"会話メッセージを保存中: role={role}, user_id={user_id}, session_id={session_id}, agent={agent_name}, content_length={len(content)}"
            )

            # AgentCore メモリ用にメッセージをタプルとしてフォーマット
            message_tuple = (content, role)

            # user_id を actor_id として AgentCore の create_event を使用
            result = self.memory_client.client.create_event(
                memory_id=self.memory_client.memory_id,
                actor_id=user_id,  # 指定どおり user_id を actor_id として使用
                session_id=session_id,  # 提供された session_id を使用
                messages=[message_tuple],  # AgentCore はタプルのリストを期待
            )

            event_id = result.get("eventId", "unknown")
            logger.info(
                f"会話メッセージの保存に成功しました (event_id: {event_id})"
            )
            return True

        except Exception as e:
            logger.error(f"会話メッセージの保存に失敗しました: {e}", exc_info=True)
            return False

    def store_conversation_batch(
        self,
        messages: List[Tuple[str, str]],
        user_id: str,
        session_id: str,
        agent_name: Optional[str] = None,
    ) -> bool:
        """
        単一の create_event 呼び出しで複数の会話メッセージを保存します。

        Args:
            messages: (content, role) タプルのリスト
            user_id: actor_id として使用するユーザー ID
            session_id: セッション識別子（必須）
            agent_name: エージェント名（該当する場合）

        Returns:
            bool: 成功ステータス
        """
        try:
            if not user_id:
                raise ValueError("user_id is required for conversation batch storage")
            if not session_id:
                raise ValueError(
                    "session_id is required for conversation batch storage"
                )
            if not messages:
                logger.warning("store_conversation_batch にメッセージが提供されていません")
                return True

            logger.info(
                f"会話バッチを保存中: {len(messages)} メッセージ, user_id={user_id}, session_id={session_id}, agent={agent_name}"
            )

            # 最大コンテンツ長制限を超えるメッセージを切り詰める
            from ..constants import SREConstants

            max_content_length = SREConstants.memory.max_content_length
            truncated_messages = []

            for content, role in messages:
                if len(content) > max_content_length:
                    # コンテンツを切り詰めて警告メッセージを追加
                    truncated_content = (
                        content[: max_content_length - 100]
                        + "\n\n[TRUNCATED: Content exceeded maximum length limit]"
                    )
                    truncated_messages.append((truncated_content, role))
                    logger.warning(
                        f"メッセージ内容を {len(content)} 文字から {len(truncated_content)} 文字に切り詰めました: user_id={user_id}, session_id={session_id}"
                    )
                else:
                    truncated_messages.append((content, role))

            # メッセージのバッチで AgentCore の create_event を使用
            result = self.memory_client.client.create_event(
                memory_id=self.memory_client.memory_id,
                actor_id=user_id,  # 指定どおり user_id を actor_id として使用
                session_id=session_id,  # 提供された session_id を使用
                messages=truncated_messages,  # AgentCore はタプルのリストを期待
            )

            event_id = result.get("eventId", "unknown")
            logger.info(
                f"{len(messages)} メッセージの会話バッチを保存しました (event_id: {event_id})"
            )
            return True

        except Exception as e:
            logger.error(f"会話バッチの保存に失敗しました: {e}", exc_info=True)
            return False


def create_conversation_memory_manager(
    memory_client: SREMemoryClient,
) -> ConversationMemoryManager:
    """会話メモリマネージャーインスタンスを作成します。"""
    return ConversationMemoryManager(memory_client)
