"""
AgentCore Memory 統合用 ShortTermMemoryHook

このモジュールは、Amazon Bedrock AgentCore Memory を使用して
Strands エージェントの短期メモリを自動的に管理する再利用可能なフックプロバイダーを提供します。

機能:
- エージェント初期化時の会話履歴の自動読み込み
- メッセージ追加時の自動永続化
- アプリケーションコンテキスト注入のサポート
- エラー処理とロギング
"""

import logging
from typing import Optional, List, Dict, Any

from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import MessageRole

# ロガーの設定
logger = logging.getLogger(__name__)


class ShortTermMemoryHook(HookProvider):
    """
    Strands エージェント用の自動メモリ管理フック。

    このフックプロバイダーは Amazon Bedrock AgentCore Memory を Strands エージェントと統合し、
    手動介入なしでシームレスな会話履歴の読み込みと永続化を提供します。

    主な機能:
    - エージェント初期化時に最近の会話ターンを読み込み
    - 各エージェント呼び出し後にメッセージを自動保存
    - コンテキスト注入のためのアプリケーション固有情報の抽出
    - メモリ検索とエラーケースを適切に処理

    Args:
        memory_client: AgentCore Memory 操作用の MemoryClient インスタンス
        memory_id: AgentCore Memory リソースの ID
        context_keywords: アプリケーションコンテキストを識別するためのキーワードリスト（オプション）
        max_context_turns: 読み込む最近のターンの最大数（デフォルト: 5）
        branch_name: 使用する Memory ブランチ名（デフォルト: "main"）

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

        # アプリケーションコンテキストを識別するためのデフォルトキーワード
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
        エージェント初期化時に最近の会話履歴を読み込み。

        このメソッドは Strands エージェントが初期化されたときに呼び出されます。
        メモリから最近の会話ターンを取得し、アプリケーション固有の情報を優先して
        エージェントのシステムプロンプトにコンテキストとして注入します。

        Args:
            event: エージェントインスタンスを含む AgentInitializedEvent
        """
        try:
            # エージェントの状態からアクターとセッションの識別子を抽出
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
        メッセージを自動的にメモリに永続化。

        このメソッドは、エージェントのメッセージ履歴に新しいメッセージが追加されるたびに
        呼び出されます（ユーザー入力またはエージェント応答）。メッセージは後で取得できるよう
        AgentCore Memory に永続化されます。

        Args:
            event: エージェントと新しいメッセージを含む MessageAddedEvent
        """
        try:
            # エージェントの状態を抽出
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
                logger.debug(f"空のメッセージをスキップ中（role={message_role}）- 永続化するコンテンツがありません")
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
        Strands エージェントのフックレジストリにフックを登録。

        このメソッドは Strands フレームワークによって呼び出され、このフックプロバイダーの
        コールバックをエージェントのイベントシステムに登録します。

        Args:
            registry: コールバックを登録する HookRegistry インスタンス
        """
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        logger.debug("ShortTermMemoryHook コールバックが HookRegistry に登録されました")

    def _build_context_from_turns(self, turns: List[List[Dict[str, Any]]]) -> str:
        """
        会話ターンからコンテキスト文字列を構築。

        アプリケーション固有の情報と最近の会話履歴を抽出し、
        より良いコンテキストのために構造化された情報（アプリケーション詳細）を優先します。

        Args:
            turns: 会話ターンのリスト、各ターンはメッセージのリストを含む

        Returns:
            システムプロンプトに注入するためのフォーマット済みコンテキスト文字列
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
            # Include only recent conversation messages (last 6)
            context_parts.extend(context_messages[-6:])

        return "\n".join(context_parts)
