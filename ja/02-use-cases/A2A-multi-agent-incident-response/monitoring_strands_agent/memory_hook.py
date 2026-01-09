# メモリクライアントをインポート
import logging
from typing import Dict, List
from bedrock_agentcore.memory import MemoryClient
from strands.hooks import (
    AgentInitializedEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
    AfterInvocationEvent,
)

# セットアップ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


# 取得設定クラス
class RetrievalConfig:
    """メモリ取得の設定"""

    def __init__(self, top_k: int = 3, relevance_score: float = 0.2):
        self.top_k = top_k
        self.relevance_score = relevance_score


# 長期メモリサポート付きの監視メモリフックを作成
class MonitoringMemoryHooks(HookProvider):
    """監視エージェント用のメモリフック - 長期メモリで拡張"""

    def __init__(
        self, memory_id: str, client: MemoryClient, actor_id: str, session_id: str
    ):
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id

        # 異なるメモリ名前空間の取得設定を定義
        # これらは CloudFormation のメモリ戦略名前空間と一致する
        self.retrieval_config = {
            "/technical-issues/{actorId}": RetrievalConfig(
                top_k=3, relevance_score=0.3
            ),
            "/knowledge/{actorId}": RetrievalConfig(top_k=5, relevance_score=0.2),
        }

    def retrieve_monitoring_context(self, event: MessageAddedEvent):
        """クエリ処理前に長期監視コンテキストを取得する"""
        messages = event.agent.messages
        if (
            messages[-1]["role"] == "user"
            and "toolResult" not in messages[-1]["content"][0]
        ):
            user_query = messages[-1]["content"][0]["text"]

            try:
                # 異なる長期メモリ名前空間を検索
                relevant_memories = []

                for namespace_template, config in self.retrieval_config.items():
                    # 実際のアクター ID で名前空間テンプレートを解決
                    resolved_namespace = namespace_template.format(
                        actorId=self.actor_id
                    )

                    # この名前空間からメモリを取得
                    memories = self.client.retrieve_memories(
                        memory_id=self.memory_id,
                        namespace=resolved_namespace,
                        query=user_query,
                        top_k=config.top_k,
                    )

                    # 関連性スコアでフィルタリング
                    filtered_memories = [
                        memory
                        for memory in memories
                        if memory.get("score", 0) >= config.relevance_score
                    ]

                    relevant_memories.extend(filtered_memories)
                    logger.info(
                        f"{resolved_namespace} で {len(filtered_memories)} 個の関連メモリが見つかりました"
                    )

                # メモリが見つかった場合、エージェントのシステムプロンプトにコンテキストを注入
                if relevant_memories:
                    context_text = self._format_context(relevant_memories)
                    original_prompt = event.agent.system_prompt
                    enhanced_prompt = f"{original_prompt}\n\n<memory-context>\n{context_text}\n</memory-context>\n"

                    event.agent.system_prompt = enhanced_prompt
                    logger.info(
                        f"✅ エージェントコンテキストに {len(relevant_memories)} 個の長期メモリを注入しました"
                    )

            except Exception as e:
                logger.error(f"監視コンテキストの取得に失敗しました: {e}")

    def _format_context(self, memories: List[Dict]) -> str:
        """取得した長期メモリをエージェントコンテキスト用にフォーマットする"""
        context_lines = []
        for i, memory in enumerate(memories[:5], 1):  # Limit to top 5
            content = memory.get("content", {})
            if isinstance(content, dict):
                text = content.get("text", "No content available").strip()
            else:
                text = str(content)
            score = memory.get("score", 0)
            context_lines.append(f"{i}. (Score: {score:.2f}) {text[:200]}...")

        return "\n".join(context_lines)

    def save_monitoring_interaction(self, event: AfterInvocationEvent):
        """監視インタラクションを短期会話メモリに保存する"""
        try:
            messages = event.agent.messages
            if len(messages) >= 2 and messages[-1]["role"] == "assistant":
                # 最後のユーザークエリとエージェントの応答を取得
                user_query = None
                agent_response = None

                for msg in reversed(messages):
                    if msg["role"] == "assistant" and not agent_response:
                        agent_response = msg["content"][0]["text"]
                    elif (
                        msg["role"] == "user"
                        and not user_query
                        and "toolResult" not in msg["content"][0]
                    ):
                        user_query = msg["content"][0]["text"]
                        break

                if user_query and agent_response:
                    # create_event を使用して短期会話メモリに保存
                    result = self.client.create_event(
                        memory_id=self.memory_id,
                        actor_id=self.actor_id,
                        session_id=self.session_id,
                        messages=[(user_query, "USER"), (agent_response, "ASSISTANT")],
                    )
                    event_id = result.get("eventId", "unknown")
                    logger.info(
                        f"✅ 短期メモリに監視インタラクションを保存しました - Event ID: {event_id}"
                    )

        except Exception as e:
            logger.error(f"監視インタラクションの保存に失敗しました: {e}")

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """エージェント開始時に最近の会話履歴を読み込む"""
        try:
            # メモリから最後の 5 つの会話ターンを読み込む
            recent_turns = self.client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                k=5,
            )

            if recent_turns:
                # コンテキスト用に会話履歴をフォーマット
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = message["role"]
                        content = message["content"]["text"]
                        context_messages.append(f"{role}: {content}")

                context = "\n".join(context_messages)
                # エージェントのシステムプロンプトにコンテキストを追加
                event.agent.system_prompt += (
                    f"\n\n<recent-conversation>:\n{context}\n</recent-conversation>\n"
                )
                logger.info(f"✅ {len(recent_turns)} 個の会話ターンをロードしました")

        except Exception as e:
            logger.error(f"Memory ロードエラー: {e}")

    def register_hooks(self, registry: HookRegistry) -> None:
        """
        監視メモリフックを登録する

        メモリアーキテクチャ:
        - 短期: create_event() で会話ターンを保存（60日後に期限切れ）
        - 長期: retrieve_memories() でセマンティック/カスタム戦略の名前空間を検索
          - /technical-issues/{actorId}: 抽出プロンプト付きの CustomMemoryStrategy
          - /knowledge/{actorId}: 一般的なファクト用の SemanticMemoryStrategy

        CustomMemoryStrategy は CloudFormation で定義された抽出プロンプトを使用して
        会話から監視ファクトを自動的に抽出する。
        """
        registry.add_callback(MessageAddedEvent, self.retrieve_monitoring_context)
        registry.add_callback(AfterInvocationEvent, self.save_monitoring_interaction)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        logger.info(
            "✅ 長期メモリサポート付きで監視メモリフックが登録されました"
        )
