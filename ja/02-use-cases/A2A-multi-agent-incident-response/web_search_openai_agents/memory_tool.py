# OpenAI Agents 用のメモリツール
# MonitoringMemoryHooks 機能に基づく

import logging
import time
from typing import Dict, Optional
from bedrock_agentcore.memory import MemoryClient
from agents import function_tool

logger = logging.getLogger(__name__)


class AgentMemoryTools:
    """MonitoringMemoryHooks 機能に基づく OpenAI エージェント用のメモリツール"""

    def __init__(
        self, memory_id: str, client: MemoryClient, actor_id: str, session_id: str
    ):
        # これらは Bedrock AgentCore のメモリを作成するために必要な変数
        # メモリクライアント、アクター、セッション、名前空間など
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id
        self.namespaces = self._get_namespaces()

    def _get_namespaces(self) -> Dict:
        """メモリ戦略の名前空間マッピングを取得する。
        ここでは、メモリ内の異なる名前空間に基づいて
        マッピング戦略を取得する。
        """
        try:
            strategies = self.client.get_memory_strategies(self.memory_id)
            return {i["type"]: i["namespaces"][0] for i in strategies}
        except Exception as e:
            logger.error(f"namespace の取得に失敗しました: {e}")
            return {}

    def create_memory_tools(self):
        """エージェント用のすべてのメモリ関連ツールを作成して返す"""

        # ツール関数のクロージャで self をキャプチャ
        memory_id = self.memory_id
        client = self.client
        actor_id = self.actor_id
        session_id = self.session_id
        namespaces = self.namespaces

        @function_tool
        def retrieve_monitoring_context(
            query: str, context_type: Optional[str] = None, top_k: int = 3
        ) -> str:
            """セマンティック検索を使用してメモリから監視コンテキストを取得する。

            Args:
                query: 関連するコンテキストを見つけるための検索クエリ
                context_type: 検索する特定のコンテキストタイプ（オプション）（例：'UserPreference', 'SemanticMemory'）
                top_k: 返すトップ結果の数（デフォルト：3）

            Returns:
                取得したコンテキストを含む文字列
            """
            try:
                all_context = []

                # 特定のコンテキストタイプが要求された場合、その名前空間のみを検索
                if context_type and context_type in namespaces:
                    search_namespaces = {context_type: namespaces[context_type]}
                else:
                    # すべての名前空間を検索
                    search_namespaces = namespaces

                for ctx_type, namespace in search_namespaces.items():
                    # 指定された名前空間があればメモリを取得
                    memories = client.retrieve_memories(
                        memory_id=memory_id,
                        namespace=namespace.format(actorId=actor_id),
                        query=query,
                        top_k=top_k,
                    )

                    for memory in memories:
                        if isinstance(memory, dict):
                            content = memory.get("content", {})
                            if isinstance(content, dict):
                                text = content.get("text", "").strip()
                                if text:
                                    all_context.append(f"[{ctx_type.upper()}] {text}")

                if all_context:
                    context_text = "\n".join(all_context)
                    logger.info(
                        f"クエリ '{query}' に対して {len(all_context)} 件のコンテキストを取得しました"
                    )
                    return context_text
                else:
                    return "クエリに関連するコンテキストが見つかりませんでした。"

            except Exception as e:
                logger.error(f"監視コンテキストの取得に失敗しました: {e}")
                return f"コンテキスト取得エラー: {str(e)}"

        @function_tool
        def save_interaction_to_memory(
            user_message: str, assistant_response: str
        ) -> str:
            """ユーザーとアシスタントのインタラクションをメモリに保存する。

            Args:
                user_message: ユーザーのメッセージ/クエリ
                assistant_response: アシスタントの応答

            Returns:
                成功または失敗を示すステータスメッセージ
            """
            try:
                # ここで、指定されたメモリ ID、アクター ID、セッション ID に対して
                # メモリを保存するメモリイベントを作成
                client.create_event(
                    memory_id=memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[
                        (user_message, "USER"),
                        (assistant_response, "ASSISTANT"),
                    ],
                )
                logger.info("Memory へのインタラクション保存に成功しました")
                return "インタラクションを Memory に正常に保存しました。"

            except Exception as e:
                logger.error(f"Memory へのインタラクション保存に失敗しました: {e}")
                return f"インタラクション保存エラー: {str(e)}"

        @function_tool
        def get_recent_conversation_history(k_turns: int = 5) -> str:
            """メモリから最近の会話履歴を取得する。

            Args:
                k_turns: 取得する最近の会話ターンの数（デフォルト：5）

            Returns:
                最近の会話履歴を含む文字列
            """
            try:
                # これは指定されたメモリ ID、アクター ID、セッション ID の会話履歴を一覧表示
                # 取得する最近の会話ターンの数を指定
                recent_turns = client.get_last_k_turns(
                    memory_id=memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    k=k_turns,
                )

                if recent_turns:
                    context_messages = []
                    for turn in recent_turns:
                        for message in turn:
                            role = message["role"]
                            content = message["content"]["text"]
                            context_messages.append(f"{role}: {content}")

                    context = "\n".join(context_messages)
                    logger.info(f"{len(recent_turns)} 件の会話ターンを取得しました")
                    return context
                else:
                    return "最近の会話履歴が見つかりませんでした。"

            except Exception as e:
                logger.error(f"会話履歴の取得に失敗しました: {e}")
                return f"履歴取得エラー: {str(e)}"

        @function_tool
        def save_custom_memory(
            content: str, memory_type: str = "SemanticMemory"
        ) -> str:
            """カスタムコンテンツを特定のメモリタイプに保存する。

            Args:
                content: メモリに保存するコンテンツ
                memory_type: 保存先のメモリタイプ（デフォルト："SemanticMemory"）

            Returns:
                成功または失敗を示すステータスメッセージ
            """
            try:
                # カスタムコンテンツ用の単一メッセージイベントを作成
                client.create_event(
                    memory_id=memory_id,
                    actor_id=actor_id,
                    session_id=f"{session_id}_custom_{int(time.time())}",
                    messages=[(content, "ASSISTANT")],
                )
                logger.info(f"{memory_type} へのカスタムコンテンツ保存に成功しました")
                return f"カスタムコンテンツを {memory_type} に正常に保存しました。"

            except Exception as e:
                logger.error(f"カスタムコンテンツの保存に失敗しました: {e}")
                return f"カスタムコンテンツ保存エラー: {str(e)}"

        @function_tool
        def search_memory_by_namespace(
            query: str, namespace_type: str, top_k: int = 5
        ) -> str:
            """特定の名前空間タイプ内でメモリを検索する。

            Args:
                query: 検索クエリ
                namespace_type: 検索する名前空間タイプ
                top_k: 返す結果の数

            Returns:
                検索結果を含む文字列
            """
            try:
                if namespace_type not in namespaces:
                    available = ", ".join(namespaces.keys())
                    return f"無効な名前空間タイプです。利用可能なタイプ: {available}"

                namespace = namespaces[namespace_type]
                memories = client.retrieve_memories(
                    memory_id=memory_id,
                    namespace=namespace.format(actorId=actor_id),
                    query=query,
                    top_k=top_k,
                )

                results = []
                for memory in memories:
                    if isinstance(memory, dict):
                        content = memory.get("content", {})
                        if isinstance(content, dict):
                            text = content.get("text", "").strip()
                            if text:
                                results.append(text)

                if results:
                    return (
                        f"{namespace_type} で {len(results)} 件の結果が見つかりました:\n"
                        + "\n---\n".join(results)
                    )
                else:
                    return f"クエリ '{query}' に対して {namespace_type} で結果が見つかりませんでした"

            except Exception as e:
                logger.error(f"Memory の検索に失敗しました: {e}")
                return f"Memory 検索エラー: {str(e)}"

        # すべてのツールを返す
        return [
            # ここで、以下のメモリツールを作成
            # 取得メモリツールは、指定されたアクター（この場合、アクターはユーザーまたはエージェント）の
            # 名前空間全体で戦略に基づいてメモリを取得するために使用
            retrieve_monitoring_context,
            # これは指定されたアクターとセッションに対してメモリイベントを作成
            save_interaction_to_memory,
            # これは特定のセッションでアクターの最近の会話から「k」個の会話ターンを取得
            get_recent_conversation_history,
            save_custom_memory,
            search_memory_by_namespace,
        ]


# 特定のエージェント用にメモリツールを作成するファクトリ関数
def create_memory_tools(
    memory_id: str, client: MemoryClient, actor_id: str, session_id: str
):
    """オーケストレーターエージェント用のメモリツールを作成する"""
    memory_tools = AgentMemoryTools(memory_id, client, actor_id, session_id)
    return memory_tools.create_memory_tools()
