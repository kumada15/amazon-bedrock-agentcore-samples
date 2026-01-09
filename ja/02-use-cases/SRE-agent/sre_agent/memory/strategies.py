import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _infer_preference_type(categories: List[str]) -> str:
    """カテゴリから設定タイプを推測します。"""
    if not categories:
        return "general"

    # カテゴリを設定タイプにマッピング
    category_mapping = {
        "escalation": "escalation",
        "notification": "notification",
        "notifications": "notification",
        "workflow": "workflow",
        "communication": "style",
        "business": "style",
        "automation": "workflow",
    }

    # 最初にマッチするカテゴリを返すか、最初のカテゴリにデフォルト
    for category in categories:
        if category.lower() in category_mapping:
            return category_mapping[category.lower()]

    # 最初のカテゴリまたはデフォルトにフォールバック
    return categories[0].lower() if categories else "general"


class UserPreference(BaseModel):
    """ユーザー設定メモリモデル。"""

    user_id: str = Field(description="Unique identifier for the user")
    preference_type: str = Field(
        description="Type of preference: escalation, notification, workflow, style"
    )
    preference_value: Dict[str, Any] = Field(description="The actual preference data")
    context: Optional[str] = Field(
        default=None, description="Context where this preference was captured"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this preference was recorded"
    )


class InfrastructureKnowledge(BaseModel):
    """インフラストラクチャ知識メモリモデル。"""

    service_name: str = Field(
        description="Name of the service or infrastructure component"
    )
    knowledge_type: str = Field(
        description="Type of knowledge: dependency, pattern, config, baseline"
    )
    knowledge_data: Dict[str, Any] = Field(description="The actual knowledge data")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence level in this knowledge (0.0-1.0)",
    )
    context: Optional[str] = Field(
        default=None, description="Context where this knowledge was discovered"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this knowledge was captured"
    )


class InvestigationSummary(BaseModel):
    """調査サマリーメモリモデル。"""

    incident_id: str = Field(description="Unique identifier for the incident")
    query: str = Field(description="Original user query that started the investigation")
    timeline: List[Dict[str, Any]] = Field(
        default_factory=list, description="Timeline of investigation events"
    )
    actions_taken: List[str] = Field(
        default_factory=list, description="List of actions taken during investigation"
    )
    resolution_status: str = Field(
        description="Status of the investigation: completed, ongoing, escalated"
    )
    key_findings: List[str] = Field(
        default_factory=list, description="Key findings from the investigation"
    )
    context: Optional[str] = Field(
        default=None, description="Context describing the investigation circumstances"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this summary was created"
    )


def _save_user_preference(client, user_id: str, preference: UserPreference) -> bool:
    """ユーザー設定をメモリに保存します。"""
    try:
        logger.info(
            f"ユーザー設定を保存中: type={preference.preference_type}, user_id={user_id}"
        )
        success = client.save_event(
            memory_type="preferences",
            actor_id=user_id,
            event_data=preference.model_dump(),
        )
        if success:
            logger.info(
                f"ユーザー {user_id} の {preference.preference_type} 設定を保存しました"
            )
        else:
            logger.warning(
                f"ユーザー {user_id} の {preference.preference_type} 設定の保存に失敗しました"
            )
        return success
    except Exception as e:
        logger.error(f"ユーザー設定の保存に失敗しました: {e}", exc_info=True)
        return False


def _retrieve_user_preferences(
    client, user_id: str, query: str
) -> List[UserPreference]:
    """関連するユーザー設定を取得します。"""
    try:
        logger.info(f"ユーザー設定を取得中: user_id={user_id}, query='{query}'")
        memories = client.retrieve_memories(
            memory_type="preferences", actor_id=user_id, query=query
        )
        logger.info(f"ストレージから {len(memories)} 件の設定メモリを取得しました")

        # 注: メモリコンテンツ構造を解析する必要あり
        preferences = []
        for i, mem in enumerate(memories):
            try:
                # メモリ構造からコンテンツを抽出
                content = mem.get("content", {})

                # データが "text" フィールドにあるネストされたコンテンツ構造を処理
                if isinstance(content, dict) and "text" in content:
                    # "text" フィールド内の JSON 文字列を解析
                    text_data = content["text"]
                    if isinstance(text_data, str):
                        preference_data = json.loads(text_data)

                        # 保存形式を UserPreference モデルに合わせて変換
                        transformed_preference = {
                            "user_id": user_id,
                            "preference_type": _infer_preference_type(
                                preference_data.get("categories", [])
                            ),
                            "preference_value": {
                                "preference": preference_data.get("preference", ""),
                                "categories": preference_data.get("categories", []),
                            },
                            "context": preference_data.get("context", ""),
                            "timestamp": mem.get("createdAt", datetime.utcnow()),
                        }

                        preferences.append(UserPreference(**transformed_preference))
                    else:
                        logger.warning(
                            f"Expected string in 'text' field but got {type(text_data)}"
                        )

                elif isinstance(content, dict):
                    # 直接解析を試行（後方互換性）
                    preferences.append(UserPreference(**content))

                elif isinstance(content, str):
                    # JSON として解析を試行
                    data = json.loads(content)
                    preferences.append(UserPreference(**data))

            except Exception as e:
                logger.warning(f"設定メモリ {i} の解析に失敗しました: {e}")
                logger.debug(f"失敗した設定メモリ {i} の内容: {mem}")
                continue

        logger.info(
            f"{user_id} の解析済みユーザー設定を {len(preferences)} 件取得しました"
        )
        return preferences
    except Exception as e:
        logger.error(f"ユーザー設定の取得に失敗しました: {e}", exc_info=True)
        return []


def _save_infrastructure_knowledge(
    client, actor_id: str, knowledge: InfrastructureKnowledge, session_id: str
) -> bool:
    """インフラストラクチャ知識をメモリに保存します。"""
    try:
        logger.info(
            f"インフラストラクチャ知識を保存中: type={knowledge.knowledge_type}, service={knowledge.service_name}, confidence={knowledge.confidence}, actor_id={actor_id}"
        )
        success = client.save_event(
            memory_type="infrastructure",
            actor_id=actor_id,
            event_data=knowledge.model_dump(),
            session_id=session_id,
        )
        if success:
            logger.info(
                f"アクター {actor_id} によるサービス {knowledge.service_name} の {knowledge.knowledge_type} 知識を保存しました"
            )
        else:
            logger.warning(
                f"アクター {actor_id} によるサービス {knowledge.service_name} の {knowledge.knowledge_type} 知識の保存に失敗しました"
            )
        return success
    except Exception as e:
        logger.error(f"インフラストラクチャ知識の保存に失敗しました: {e}", exc_info=True)
        return False


def _retrieve_infrastructure_knowledge(
    client, actor_id: str, query: str, session_id: str = None
) -> List[InfrastructureKnowledge]:
    """関連するインフラストラクチャ知識を取得します。"""
    try:
        memories = client.retrieve_memories(
            memory_type="infrastructure",
            actor_id=actor_id,
            query=query,
            session_id=session_id,
        )
        # メモリコンテンツ構造を解析
        knowledge_items = []
        for mem in memories:
            try:
                content = mem.get("content", {})

                # データが "text" フィールドにあるネストされたコンテンツ構造を処理
                if isinstance(content, dict) and "text" in content:
                    text_data = content["text"]
                    if isinstance(text_data, str):
                        try:
                            # まず JSON として解析を試行（構造化形式）
                            data = json.loads(text_data)
                            knowledge_items.append(InfrastructureKnowledge(**data))
                        except json.JSONDecodeError:
                            # JSON でない場合、プレーンテキストのインフラストラクチャ知識として処理
                            logger.debug(
                                f"Infrastructure memory stored as plain text, converting: {text_data[:100]}..."
                            )
                            knowledge_items.append(
                                InfrastructureKnowledge(
                                    service_name="general",
                                    knowledge_type="investigation",
                                    knowledge_data={
                                        "description": text_data,
                                        "source": "memory",
                                    },
                                )
                            )
                    else:
                        logger.warning(
                            f"'text' フィールドに文字列を期待しましたが、{type(text_data)} を受け取りました"
                        )

                elif isinstance(content, dict):
                    # 直接解析を試行（後方互換性）
                    knowledge_items.append(InfrastructureKnowledge(**content))

                elif isinstance(content, str):
                    try:
                        # まず JSON として解析を試行
                        data = json.loads(content)
                        knowledge_items.append(InfrastructureKnowledge(**data))
                    except json.JSONDecodeError:
                        # JSON でない場合、プレーンテキストとして処理
                        logger.debug(
                            f"インフラストラクチャメモリがプレーンテキスト文字列として保存されています。変換中: {content[:100]}..."
                        )
                        knowledge_items.append(
                            InfrastructureKnowledge(
                                service_name="general",
                                knowledge_type="investigation",
                                knowledge_data={
                                    "description": content,
                                    "source": "memory",
                                },
                            )
                        )

            except Exception as e:
                logger.warning(f"インフラストラクチャメモリの解析に失敗しました: {e}")
                logger.debug(f"失敗したインフラストラクチャメモリの内容: {mem}")
                continue
        return knowledge_items
    except Exception as e:
        logger.error(f"インフラストラクチャ知識の取得に失敗しました: {e}")
        return []


def _save_investigation_summary(
    client,
    actor_id: str,
    incident_id: str,
    summary: InvestigationSummary,
    session_id: str,
) -> bool:
    """調査サマリーをメモリに保存します。"""
    try:
        logger.info(
            f"調査サマリーを保存中: incident_id={incident_id}, actor_id={actor_id}, session_id={session_id}, status={summary.resolution_status}, actions_count={len(summary.actions_taken)}, findings_count={len(summary.key_findings)}"
        )
        logger.info(
            f"インシデント incident_id={incident_id} の調査サマリー全文:\n{json.dumps(summary.model_dump(), indent=2, default=str)}"
        )
        success = client.save_event(
            memory_type="investigations",
            actor_id=actor_id,
            event_data=summary.model_dump(),
            session_id=session_id,
        )
        if success:
            logger.info(
                f"actor_id={actor_id} のインシデント {incident_id} の調査サマリーを保存しました (ステータス: {summary.resolution_status})"
            )
        else:
            logger.warning(
                f"インシデント {incident_id} の調査サマリー保存に失敗しました"
            )
        return success
    except Exception as e:
        logger.error(f"調査サマリーの保存に失敗しました: {e}", exc_info=True)
        return False


def _retrieve_investigation_summaries(
    client, actor_id: str, query: str, session_id: str = None
) -> List[InvestigationSummary]:
    """関連する調査サマリーを取得します。"""
    try:
        memories = client.retrieve_memories(
            memory_type="investigations",
            actor_id=actor_id,
            query=query,
            session_id=session_id,
        )
        # メモリコンテンツ構造を解析
        summaries = []
        for mem in memories:
            try:
                content = mem.get("content", {})

                # データが "text" フィールドにあるネストされたコンテンツ構造を処理
                if isinstance(content, dict) and "text" in content:
                    text_data = content["text"]

                    # XML 形式のサマリーかどうかをチェック
                    if isinstance(text_data, str) and text_data.strip().startswith(
                        "<summary>"
                    ):
                        # XML サマリーから主要情報を抽出
                        import re

                        # トピック名を抽出
                        topic_match = re.search(r'<topic name="([^"]+)">', text_data)
                        topic_name = (
                            topic_match.group(1)
                            if topic_match
                            else "Unknown Investigation"
                        )

                        # テキストから主要情報を抽出
                        # 注: タイムスタンプは現在使用されていないが、将来の拡張のためにパターンを保持

                        # メインコンテンツを抽出
                        content_match = re.search(
                            r"<topic[^>]*>(.*?)</topic>", text_data, re.DOTALL
                        )
                        main_content = (
                            content_match.group(1).strip()
                            if content_match
                            else text_data
                        )

                        # 抽出した情報からサマリーオブジェクトを作成
                        investigation_summary = InvestigationSummary(
                            incident_id=mem.get(
                                "memoryRecordId", f"mem-{actor_id}-{hash(text_data)}"
                            ),
                            query=topic_name,
                            resolution_status="completed",  # Assume completed since it's in memory
                            key_findings=[
                                main_content[:500] + "..."
                                if len(main_content) > 500
                                else main_content
                            ],
                            context=f"Retrieved from memory: {topic_name}",
                            timestamp=mem.get("createdAt", datetime.utcnow()),
                        )
                        summaries.append(investigation_summary)

                    elif isinstance(text_data, str):
                        # JSON 解析を試行
                        try:
                            data = json.loads(text_data)
                            summaries.append(InvestigationSummary(**data))
                        except json.JSONDecodeError:
                            logger.warning(
                                f"調査メモリのテキストを JSON として解析できませんでした: {text_data[:100]}..."
                            )

                elif isinstance(content, dict):
                    # 直接解析を試行（後方互換性）
                    summaries.append(InvestigationSummary(**content))

                elif isinstance(content, str):
                    # JSON として解析を試行
                    data = json.loads(content)
                    summaries.append(InvestigationSummary(**data))

            except Exception as e:
                logger.warning(f"調査メモリの解析に失敗しました: {e}")
                logger.debug(f"失敗した調査メモリの内容: {mem}")
                continue
        return summaries
    except Exception as e:
        logger.error(f"調査サマリーの取得に失敗しました: {e}")
        return []
