"""
AgentCore Memory 統合用 ShortTermMemoryHook

このモジュールは、Amazon Bedrock AgentCore Memory を使用して
Strands エージェントの短期メモリを自動管理する再利用可能なフックプロバイダーを提供します。

機能:
- エージェント初期化時の自動会話履歴読み込み
- メッセージ追加時の自動メッセージ永続化
- アプリケーションコンテキスト注入のサポート
- エラーハンドリングとロギング
"""

import logging
from typing import Optional, List, Dict, Any

from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import MessageRole

# ロガーを設定
logger = logging.getLogger(__name__)


class ShortTermMemoryHook(HookProvider):
    """
    Strands エージェント用の自動メモリ管理フック。

    このフックプロバイダーは、Amazon Bedrock AgentCore Memory を Strands エージェントと統合し、
    手動介入なしでシームレスな会話履歴の読み込みと永続化を提供します。

    主な機能:
    - エージェント初期化時に最近の会話ターンを読み込み
    - 各エージェント呼び出し後にメッセージを自動保存
    - コンテキスト注入のためのアプリケーション固有情報の抽出
    - メモリ検索とエラーケースの適切な処理

    Args:
        memory_client: AgentCore Memory 操作用の MemoryClient インスタンス
        memory_id: AgentCore Memory リソースの ID
        context_keywords: アプリケーションコンテキストを識別するためのキーワードリスト（オプション）
        max_context_turns: 読み込む最近のターンの最大数（デフォルト: 5）
        branch_name: 使用するメモリブランチ名（デフォルト: "main"）

    Example:
        >>> memory_client = MemoryClient(region_name='us-west-2')
        >>> memory_hook = ShortTermMemoryHook(memory_client, memory_id="xyz-123")
        >>> agent = Agent(
        ...     hooks=[memory_hook],
        ...     model="global.anthropic.claude-sonnet-4-20250514-v1:0",
        ...     state={"actor_id": "user-123", "session_id": "session-456"}
        ... )
    """

    def __init__(
        self,
        memory_client: MemoryClient,
        memory_id: str,
        context_keywords: Optional[List[str]] = None,
        max_context_turns: int = 5,
        branch_name: str = "main"
    ):
        """ShortTermMemoryHook を初期化。"""
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.max_context_turns = max_context_turns
        self.branch_name = branch_name

        # アプリケーションコンテキスト識別用のデフォルトキーワード
        self.context_keywords = context_keywords or [
            'Stack Name:',
            'EC2 Instance:',
            'Database:',
            'Application:',
            'Service:',
            'Configuration:',
            'Error:',
            'Status:',
            'Memory:',
            'CPU:'
        ]

        logger.debug(
            f"ShortTermMemoryHook initialized with memory_id={memory_id}, "
            f"max_context_turns={max_context_turns}"
        )

    def on_agent_initialized(self, event: AgentInitializedEvent) -> None:
        """
        Load recent conversation history when agent initializes.

        This method is called when a Strands agent is initialized. It retrieves
        recent conversation turns from memory and injects them into the agent's
        system prompt as context, prioritizing application-specific information.

        Args:
            event: AgentInitializedEvent containing the agent instance
        """
        try:
            # エージェント状態からアクターとセッションの識別子を抽出
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")

            if not actor_id or not session_id:
                logger.warning(
                    "Cannot load memory: Missing actor_id or session_id in agent state. "
                    f"actor_id={actor_id}, session_id={session_id}"
                )
                return

            logger.debug(
                f"Loading memory for actor_id={actor_id}, session_id={session_id}"
            )

            # メモリから最近の会話ターンを取得
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=session_id,
                k=self.max_context_turns,
                branch_name=self.branch_name
            )

            if recent_turns:
                context = self._build_context_from_turns(recent_turns)
                event.agent.system_prompt += f"\n\n{context}\n\nUse this information for additional background context."
                logger.info(
                    f"✅ Loaded {len(recent_turns)} conversation turns into agent context "
                    f"(actor_id={actor_id})"
                )
            else:
                logger.info(
                    f"No previous conversation history found for actor_id={actor_id}"
                )

        except Exception as e:
            logger.error(
                f"Failed to load conversation history: {type(e).__name__}: {str(e)}",
                exc_info=True
            )

    def on_message_added(self, event: MessageAddedEvent) -> None:
        """
        Automatically persist messages to memory.

        This method is called whenever a new message is added to the agent's
        message history (user input or agent response). The message is persisted
        to AgentCore Memory for later retrieval.

        Args:
            event: MessageAddedEvent containing the agent and new message
        """
        try:
            # エージェント状態を抽出
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")

            if not actor_id or not session_id:
                logger.warning(
                    "Cannot save message: Missing actor_id or session_id in agent state"
                )
                return

            # 最新のメッセージを取得
            messages = event.agent.messages
            if not messages:
                logger.warning("永続化するメッセージが見つかりません")
                return

            latest_message = messages[-1]
            message_role = latest_message.get("role", "unknown")

            # メッセージからテキストコンテンツを抽出
            message_content = latest_message.get("content", [])
            if isinstance(message_content, list) and message_content:
                message_text = message_content[0].get("text", "")
            else:
                message_text = str(message_content)

            # 空のメッセージをスキップ（テキストが空の場合はメモリに永続化しない）
            if not message_text or not message_text.strip():
                logger.debug(f"空のメッセージをスキップ (role={message_role}) - 永続化するコンテンツがありません")
                return

            # メモリに保存
            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=session_id,
                messages=[(message_text, message_role)]
            )

            logger.debug(
                f"✅ Persisted message (role={message_role}, length={len(message_text)}) "
                f"for actor_id={actor_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to persist message to memory: {type(e).__name__}: {str(e)}",
                exc_info=True
            )

    def register_hooks(self, registry: HookRegistry) -> None:
        """
        Register hooks with the Strands agent hook registry.

        This method is called by the Strands framework to register this hook provider's
        callbacks with the agent's event system.

        Args:
            registry: HookRegistry instance to register callbacks with
        """
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        logger.debug("ShortTermMemoryHook コールバックが HookRegistry に登録されました")

    def _build_context_from_turns(self, turns: List[List[Dict[str, Any]]]) -> str:
        """
        Build context string from conversation turns.

        Extracts application-specific information and recent conversation history,
        prioritizing structured information (application details) for better context.

        Args:
            turns: List of conversation turns, each containing a list of messages

        Returns:
            Formatted context string for injection into system prompt
        """
        context_messages = []
        application_info = []

        # 各ターンを処理して情報を抽出
        for turn in turns:
            for message in turn:
                role = message.get('role', '').lower()
                content = message.get('content', {})

                # 異なるコンテンツ形式を処理
                if isinstance(content, dict):
                    text = content.get('text', '')
                elif isinstance(content, str):
                    text = content
                else:
                    text = str(content)

                # キーワードに基づいてアプリケーション情報を抽出
                is_application_info = any(
                    keyword in text for keyword in self.context_keywords
                )

                if is_application_info and role == 'assistant':
                    application_info.append(text)
                else:
                    context_messages.append(f"{role.title()}: {text}")

        # アプリケーション情報を優先して最終コンテキストを構築
        context_parts = []

        if application_info:
            context_parts.append("APPLICATION INFORMATION:")
            context_parts.extend(application_info)

        if context_messages:
            if application_info:
                context_parts.append("\nRECENT CONVERSATION:")
            # 最近の会話メッセージのみを含める（最後の6件）
            context_parts.extend(context_messages[-6:])

        return "\n".join(context_parts)
