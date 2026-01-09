import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from bedrock_agentcore.memory import MemoryClient

from .config import _load_memory_config

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class SREMemoryClient:
    """SRE 運用向けにカスタマイズされた AgentCore Memory クライアントのラッパー。"""

    def __init__(
        self,
        memory_name: str = "sre_agent_memory",
        region: str = "us-east-1",
        force_delete: bool = False,
    ):
        self.client = MemoryClient(region_name=region)
        self.memory_name = memory_name
        self.config = _load_memory_config()
        self.memory_ids = {}
        self.force_delete = force_delete
        self._initialize_memories()

    def _initialize_memories(self):
        """異なるメモリ戦略を初期化します。"""
        try:
            logger.info(f"メモリシステムを初期化中: {self.memory_name}")

            # Check for existing memory first
            existing_memory = self._find_existing_memory()

            if existing_memory and not self.force_delete:
                # 既存のメモリを使用
                self.memory_id = existing_memory["id"]
                logger.info(
                    f"既存のメモリを使用: {self.memory_id} (name: {existing_memory['name']})"
                )
                logger.info(
                    f"メモリステータス: {existing_memory.get('status', 'unknown')}"
                )

                # Write memory ID to file for helper scripts
                self._write_memory_id_to_file()

                # ストラテジーが既に設定されているかチェック
                existing_strategies = existing_memory.get("strategies", [])
                strategy_count = len(existing_strategies)

                if strategy_count >= 3:  # 3 つのストラテジーを期待
                    logger.info(
                        f"{strategy_count} 個の既存ストラテジーを発見 - メモリは既に設定済みです"
                    )
                    # すべてのストラテジーが ACTIVE かチェック
                    creating_count = sum(
                        1 for s in existing_strategies if s.get("status") == "CREATING"
                    )
                    if creating_count > 0:
                        logger.warning(
                            f"{creating_count} 個のストラテジーがまだ CREATING 状態です - メモリシステムが完全に動作していない可能性があります"
                        )
                    return  # Memory is already configured
                else:
                    logger.info(
                        f"{strategy_count} 個のストラテジーを発見、3 個を期待 - 不足分を追加します"
                    )
                    # 存在するストラテジーを確認
                    existing_names = {s.get("name") for s in existing_strategies}
                    logger.info(f"既存のストラテジー名: {existing_names}")
            else:
                if existing_memory and self.force_delete:
                    logger.warning(
                        f"強制削除が有効 - 既存のメモリを削除中: {existing_memory['id']}"
                    )
                    try:
                        self.client.delete_memory(existing_memory["id"])
                        logger.info("メモリ削除の完了を待機中...")
                        import time

                        time.sleep(5)  # 削除完了を待機
                    except Exception as e:
                        logger.error(f"既存のメモリ削除に失敗しました: {e}")

                # 新しいメモリを作成
                max_retention = max(
                    self.config.preferences_retention_days,
                    self.config.infrastructure_retention_days,
                    self.config.investigation_retention_days,
                )
                logger.info(f"{max_retention} 日間保持でメモリを作成中")

                base_memory = self.client.create_memory(
                    name=self.memory_name,
                    description="SRE Agent long-term memory system",
                    event_expiry_days=max_retention,
                )
                self.memory_id = base_memory["id"]
                logger.info(f"新しいメモリを作成しました: {self.memory_id}")

                # ヘルパースクリプト用にメモリ ID をファイルに書き込み
                self._write_memory_id_to_file()

            # 追加が必要なストラテジーを確認（部分的な設定の場合）
            existing_names = set()
            if existing_memory:
                existing_strategies = existing_memory.get("strategies", [])
                existing_names = {s.get("name") for s in existing_strategies}
                logger.info(f"既存のストラテジー名: {existing_names}")

            # ユーザー設定ストラテジーが存在しない場合は追加
            if "user_preferences" not in existing_names:
                logger.info("ユーザー設定ストラテジーを追加中...")
                self.client.add_user_preference_strategy_and_wait(
                    memory_id=self.memory_id,
                    name="user_preferences",
                    description="User preferences for escalation, notification, and workflows",
                    namespaces=["/sre/users/{actorId}/preferences"],
                )
                logger.info("ユーザー設定ストラテジーを追加しました")
            else:
                logger.info("ユーザー設定ストラテジーは既に存在します、スキップします")

            # インフラストラクチャ知識ストラテジー（セマンティック）が存在しない場合は追加
            if "infrastructure_knowledge" not in existing_names:
                logger.info("インフラストラクチャ知識ストラテジーを追加中...")
                self.client.add_semantic_strategy_and_wait(
                    memory_id=self.memory_id,
                    name="infrastructure_knowledge",
                    description="Infrastructure knowledge including dependencies and patterns",
                    namespaces=["/sre/infrastructure/{actorId}/{sessionId}"],
                )
                logger.info("インフラストラクチャ知識ストラテジーを追加しました")
            else:
                logger.info(
                    "インフラストラクチャ知識ストラテジーは既に存在します、スキップします"
                )

            # 調査サマリーストラテジーが存在しない場合は追加
            if "investigation_summaries" not in existing_names:
                logger.info("調査サマリーストラテジーを追加中...")
                self.client.add_summary_strategy_and_wait(
                    memory_id=self.memory_id,
                    name="investigation_summaries",
                    description="Investigation summaries with timeline and findings",
                    namespaces=["/sre/investigations/{actorId}/{sessionId}"],
                )
                logger.info("調査サマリーストラテジーを追加しました")
            else:
                logger.info("調査サマリーストラテジーは既に存在します、スキップします")
            logger.info(f"メモリシステムの初期化が完了しました: {self.memory_name}")

        except Exception as e:
            logger.error(f"メモリの初期化に失敗しました: {e}", exc_info=True)
            # 開発環境では完全な失敗なく続行
            # 本番環境では例外を発生させることを推奨
            self.memory_id = None
            logger.warning("メモリシステムはオフラインモードで動作します")

    def save_event(
        self,
        memory_type: str,
        actor_id: str,
        event_data: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> bool:
        """create_event API を使用してイベントをメモリに保存します。

        actor_id は常に必須です。session_id は infrastructure と investigations の
        メモリタイプでは必須ですが、preferences ではオプションです。
        """
        if not self.memory_id:
            logger.warning("メモリシステムが初期化されていません、保存をスキップします")
            return False

        if not actor_id:
            raise ValueError("actor_id is required for save_event")

        # Validate session_id based on memory type
        if memory_type in ["infrastructure", "investigations"] and not session_id:
            raise ValueError(f"session_id is required for {memory_type} memory type")

        try:
            # Add detailed traces for debugging
            logger.info("=== SAVE_EVENT トレース開始 ===")
            logger.info("入力パラメータ:")
            logger.info(f"  memory_type: {memory_type}")
            logger.info(f"  actor_id: {actor_id}")
            logger.info(f"  session_id: {session_id}")
            logger.info(f"  memory_id: {self.memory_id}")
            logger.info(f"  event_data: {event_data}")

            # Convert event data to message format
            messages = [
                (str(event_data), "ASSISTANT")  # Store as assistant message
            ]

            logger.info("create_event を呼び出し中:")
            logger.info(f"  memory_id: {self.memory_id}")
            logger.info(f"  actor_id: {actor_id}")
            logger.info(f"  session_id: {session_id}")
            logger.info(f"  messages: {messages}")

            # For preferences, use a default session_id since the API requires it
            # but the namespace doesn't use it
            actual_session_id = session_id if session_id else "preferences-default"

            result = self.client.create_event(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=actual_session_id,
                messages=messages,
            )

            event_id = result.get("eventId", "unknown")
            logger.info(f"create_event 結果: {result}")
            logger.info("=== SAVE_EVENT トレース終了 ===")
            logger.info(
                f"{memory_type} イベントを保存しました: {actor_id} (event_id: {event_id})"
            )
            logger.info(f"イベントデータサイズ: {len(str(event_data))} 文字")
            return True

        except Exception as e:
            logger.error(
                f"{memory_type} イベントの保存に失敗しました: {actor_id}: {e}", exc_info=True
            )
            return False

    def retrieve_memories(
        self,
        memory_type: str,
        actor_id: str,
        query: str,
        max_results: int = 10,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """retrieve_memories API を使用してメモリを取得します。"""
        if not self.memory_id:
            logger.warning("メモリシステムが初期化されていません、空の結果を返します")
            return []

        try:
            # Get appropriate namespace (session_id only needed for infrastructure/investigations)
            namespace = self._get_namespace(memory_type, actor_id, session_id)

            logger.info(
                f"{memory_type} メモリを取得中: actor_id={actor_id}, namespace={namespace}, query='{query}'"
            )

            result = self.client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=namespace,
                query=query,
                top_k=max_results,
            )

            logger.info(
                f"{actor_id} の {memory_type} メモリを {len(result)} 件取得しました"
            )
            if result:
                logger.debug(
                    f"最初の結果のキー: {list(result[0].keys()) if result else 'N/A'}"
                )
                # Log the actual memory contents for debugging (debug level to reduce noise)
                logger.debug(
                    f"{actor_id} のすべての {len(result)} 件の {memory_type} メモリレコード:"
                )
                for i, memory in enumerate(result):
                    logger.debug(f"Memory {i + 1}: {memory}")
                    if "content" in memory:
                        logger.debug(f"Memory {i + 1} content: {memory['content']}")
                    else:
                        logger.debug(f"Memory {i + 1} has no 'content' field")

            return result

        except Exception as e:
            logger.error(
                f"{actor_id} の {memory_type} メモリの取得に失敗しました: {e}",
                exc_info=True,
            )
            return []

    def _get_namespace(
        self, memory_type: str, actor_id: str, session_id: Optional[str] = None
    ) -> str:
        """メモリタイプとアクターに適した名前空間を取得します。

        メモリ初期化で定義された名前空間テンプレートに基づいて：
        - preferences: /sre/users/{actorId}/preferences (sessionId なし - 常にユーザー全体)
        - infrastructure: /sre/infrastructure/{actorId}/{sessionId} (セッション固有) または
                         /sre/infrastructure/{actorId} (session_id=None の場合はクロスセッション)
        - investigations: /sre/investigations/{actorId}/{sessionId} (セッション固有) または
                         /sre/investigations/{actorId} (session_id=None の場合はクロスセッション)

        Args:
            memory_type: メモリタイプ（preferences, infrastructure, investigations）
            actor_id: アクター識別子（ユーザーまたはエージェント）
            session_id: セッション識別子。None の場合、infrastructure/investigations のクロスセッション検索を有効にします
        """
        if memory_type == "preferences":
            # Preferences are always user-wide, ignore session_id
            return f"/sre/users/{actor_id}/preferences"
        elif memory_type == "infrastructure":
            if session_id is None:
                # Cross-session search: use base namespace to search across all sessions
                return f"/sre/infrastructure/{actor_id}"
            else:
                # Session-specific search: include session_id in namespace
                return f"/sre/infrastructure/{actor_id}/{session_id}"
        elif memory_type == "investigations":
            if session_id is None:
                # Cross-session search: use base namespace to search across all sessions
                return f"/sre/investigations/{actor_id}"
            else:
                # Session-specific search: include session_id in namespace
                return f"/sre/investigations/{actor_id}/{session_id}"
        else:
            return f"/sre/default/{actor_id}"

    def _find_existing_memory(self) -> Optional[Dict[str, Any]]:
        """名前で既存のメモリを検索します。"""
        try:
            logger.info(f"既存のメモリを検索中: {self.memory_name}")
            memories = self.client.list_memories(max_results=100)

            for memory in memories:
                memory_id = memory.get("id", "")
                # Check if memory ID starts with our memory name (since name field might not be returned)
                if memory_id.startswith(f"{self.memory_name}-"):
                    logger.info(
                        f"既存のメモリを発見: {memory_id} (ステータス: {memory.get('status')})"
                    )
                    # Get full memory details since list might not include all fields
                    try:
                        from bedrock_agentcore.memory import MemoryControlPlaneClient

                        cp_client = MemoryControlPlaneClient(
                            region_name=self.client.gmcp_client._client_config.region_name
                        )
                        full_memory = cp_client.get_memory(memory_id)
                        return full_memory
                    except Exception as e:
                        logger.warning(f"メモリの詳細取得に失敗しました: {e}")
                        # Return what we have
                        memory["id"] = memory_id
                        return memory

            logger.info(
                f"名前プレフィックス '{self.memory_name}' の既存メモリは見つかりませんでした"
            )
            return None

        except Exception as e:
            logger.warning(f"メモリ一覧の取得に失敗しました: {e}")
            return None

    def _write_memory_id_to_file(self) -> None:
        """ヘルパースクリプト用にメモリ ID を .memory_id ファイルに書き込みます。"""
        try:
            # Write to project root only (where manage_memories.py expects it)
            project_root = Path(__file__).parent.parent.parent
            memory_id_file = project_root / ".memory_id"

            memory_id_file.write_text(self.memory_id)
            logger.info(f"メモリ ID {self.memory_id} を {memory_id_file} に書き込みました")

        except Exception as e:
            logger.warning(f"メモリ ID のファイル書き込みに失敗しました: {e}")
