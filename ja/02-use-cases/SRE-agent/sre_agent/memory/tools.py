import json
import logging
from typing import List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .client import SREMemoryClient
from .strategies import (
    InfrastructureKnowledge,
    InvestigationSummary,
    UserPreference,
    _retrieve_infrastructure_knowledge,
    _retrieve_investigation_summaries,
    _retrieve_user_preferences,
    _save_infrastructure_knowledge,
    _save_investigation_summary,
    _save_user_preference,
)

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _sanitize_actor_id(actor_id: str) -> str:
    """actor_id を AWS Bedrock Memory の正規表現に準拠するようにサニタイズします: [a-zA-Z0-9][a-zA-Z0-9-_/]*"""
    # スペースをハイフンに置換し、元のケースを保持し、許可された文字のみを保持
    sanitized = actor_id.replace(" ", "-")
    # 英数字、ハイフン、アンダースコア、スラッシュのみを保持（ケースを保持）
    sanitized = "".join(c for c in sanitized if c.isalnum() or c in "-_/")
    # 英数字で始まることを確認
    if sanitized and not sanitized[0].isalnum():
        sanitized = "a" + sanitized
    return sanitized or "default-actor"


class SavePreferenceInput(BaseModel):
    """SavePreferenceTool の入力スキーマ。"""

    content: UserPreference = Field(description="ユーザー設定データ")
    context: str = Field(
        description="必須: この設定がキャプチャされた場所/理由を説明するコンテキスト"
    )
    actor_id: str = Field(description="メモリストレージ用のアクター ID")


class SaveInfrastructureInput(BaseModel):
    """SaveInfrastructureTool の入力スキーマ。"""

    content: InfrastructureKnowledge = Field(
        description="インフラストラクチャ知識データ"
    )
    context: str = Field(
        description="必須: この知識が発見された場所/理由を説明するコンテキスト"
    )
    actor_id: str = Field(description="メモリストレージ用のアクター ID")
    session_id: str = Field(
        description="必須: インフラストラクチャメモリストレージ用のセッション ID"
    )


class SaveInvestigationInput(BaseModel):
    """SaveInvestigationTool の入力スキーマ。"""

    content: InvestigationSummary = Field(description="調査サマリーデータ")
    context: str = Field(
        description="必須: 調査状況を説明するコンテキスト"
    )
    actor_id: str = Field(description="メモリストレージ用のアクター ID")
    session_id: str = Field(
        description="必須: 調査メモリストレージ用のセッション ID"
    )


class SavePreferenceTool(BaseTool):
    """ユーザー設定を長期メモリに保存するためのツール。"""

    name: str = "save_preference"
    description: str = """ユーザー設定を長期メモリに保存する。
    以下を記憶するために使用:
    - エスカレーション連絡先と通知チャネル
    - ワークフロー設定と運用スタイル
    - ユーザー固有の設定と構成

    必須フィールド:
    - content: UserPreference オブジェクト:
      - user_id: str（ユーザーの一意識別子）
      - preference_type: str（escalation、notification、workflow、style）
      - preference_value: dict（実際の設定データ）
    - context: str（必須 - この設定がキャプチャされた場所/理由を説明）
    - actor_id: str（必須 - エージェントの actor_id ではなく content.user_id の user_id を使用）

    重要: 設定の場合、actor_id は user_id（例: "Alice"）でなければなりません。
    これにより設定が正しいユーザー名前空間（/sre/users/{user_id}/preferences）に保存されます。
    """
    args_schema: Type[BaseModel] = SavePreferenceInput

    def __init__(self, memory_client: SREMemoryClient, **kwargs):
        super().__init__(**kwargs)
        # メモリクライアントをインスタンス属性として保存（Pydantic フィールドではない）
        object.__setattr__(self, "_memory_client", memory_client)

    @property
    def memory_client(self) -> SREMemoryClient:
        """Memory クライアントを取得します。"""
        return getattr(self, "_memory_client")

    def _run(
        self,
        content: UserPreference,
        context: str,
        actor_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """ユーザー設定を保存します。"""
        try:
            sanitized_actor_id = _sanitize_actor_id(actor_id)
            logger.info(
                f"save_preference called: context={context}, actor_id={actor_id} -> {sanitized_actor_id}, content={json.dumps(content.model_dump(), indent=2, default=str)}"
            )

            # 常にコンテキストを設定
            if not content.context:
                content.context = context

            success = _save_user_preference(
                self.memory_client, sanitized_actor_id, content
            )

            result = (
                f"Saved user preference: {content.preference_type} for user {content.user_id}"
                if success
                else f"Failed to save user preference: {content.preference_type}"
            )
            logger.info(f"save_preference result: {result}")
            return result

        except Exception as e:
            error_msg = f"Error saving user preference: {str(e)}"
            logger.error(f"save_preference exception: {error_msg}", exc_info=True)
            return error_msg


class SaveInfrastructureTool(BaseTool):
    """インフラストラクチャ知識を長期メモリに保存するためのツール。"""

    name: str = "save_infrastructure"
    description: str = """インフラストラクチャ知識を長期メモリに保存する。
    以下を記憶するために使用:
    - サービスの依存関係と関係性
    - インフラストラクチャパターンと設定
    - パフォーマンスベースラインとしきい値

    必須フィールド:
    - content: InfrastructureKnowledge オブジェクト:
      - service_name: str（サービスまたはインフラストラクチャコンポーネントの名前）
      - knowledge_type: str（dependency、pattern、config、baseline）
      - knowledge_data: dict（実際の知識データ）
      - confidence: float（オプション - 信頼度 0.0-1.0、デフォルト 0.8）
    - context: str（必須 - この知識が発見された場所/理由を説明）
    - actor_id: str（必須 - "sre-agent-{agent_name}" を使用）
    - session_id: str（必須 - インフラストラクチャメモリストレージ用のセッション ID）
    """
    args_schema: Type[BaseModel] = SaveInfrastructureInput

    def __init__(self, memory_client: SREMemoryClient, **kwargs):
        super().__init__(**kwargs)
        # メモリクライアントをインスタンス属性として保存（Pydantic フィールドではない）
        object.__setattr__(self, "_memory_client", memory_client)

    @property
    def memory_client(self) -> SREMemoryClient:
        """Memory クライアントを取得します。"""
        return getattr(self, "_memory_client")

    def _run(
        self,
        content: InfrastructureKnowledge,
        context: str,
        actor_id: str,
        session_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """インフラストラクチャ知識を保存します。"""
        try:
            sanitized_actor_id = _sanitize_actor_id(actor_id)
            logger.info(
                f"save_infrastructure called: context={context}, actor_id={actor_id} -> {sanitized_actor_id}, content={json.dumps(content.model_dump(), indent=2, default=str)}"
            )

            # 常にコンテキストを設定
            if not content.context:
                content.context = context

            success = _save_infrastructure_knowledge(
                self.memory_client, sanitized_actor_id, content, session_id
            )

            result = (
                f"Saved infrastructure knowledge: {content.knowledge_type} for {content.service_name}"
                if success
                else f"Failed to save infrastructure knowledge for {content.service_name}"
            )
            logger.info(f"save_infrastructure result: {result}")
            return result

        except Exception as e:
            error_msg = f"Error saving infrastructure knowledge: {str(e)}"
            logger.error(f"save_infrastructure exception: {error_msg}", exc_info=True)
            return error_msg


class SaveInvestigationTool(BaseTool):
    """調査サマリーを長期メモリに保存するためのツール。"""

    name: str = "save_investigation"
    description: str = """調査サマリーを長期メモリに保存する。
    以下を記憶するために使用:
    - 調査タイムラインと実行したアクション
    - 主要な発見事項と解決戦略
    - インシデントパターンと教訓

    必須フィールド:
    - content: InvestigationSummary オブジェクト:
      - incident_id: str（インシデントの一意識別子）
      - query: str（調査を開始した元のユーザークエリ）
      - timeline: list（オプション - 調査イベントのタイムライン）
      - actions_taken: list（オプション - 調査中に実行したアクションのリスト）
      - resolution_status: str（completed、ongoing、escalated）
      - key_findings: list（オプション - 調査からの主要な発見事項）
    - context: str（必須 - 調査状況を説明）
    - actor_id: str（必須 - "sre-agent-{agent_name}" を使用）
    - session_id: str（必須 - 調査メモリストレージ用のセッション ID）
    """
    args_schema: Type[BaseModel] = SaveInvestigationInput

    def __init__(self, memory_client: SREMemoryClient, **kwargs):
        super().__init__(**kwargs)
        # メモリクライアントをインスタンス属性として保存（Pydantic フィールドではない）
        object.__setattr__(self, "_memory_client", memory_client)

    @property
    def memory_client(self) -> SREMemoryClient:
        """Memory クライアントを取得します。"""
        return getattr(self, "_memory_client")

    def _run(
        self,
        content: InvestigationSummary,
        context: str,
        actor_id: str,
        session_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """調査サマリーを保存します。"""
        try:
            sanitized_actor_id = _sanitize_actor_id(actor_id)
            logger.info(
                f"save_investigation called: context={context}, actor_id={actor_id} -> {sanitized_actor_id}, content={json.dumps(content.model_dump(), indent=2, default=str)}"
            )

            # 常にコンテキストを設定
            if not content.context:
                content.context = context

            success = _save_investigation_summary(
                self.memory_client,
                sanitized_actor_id,
                content.incident_id,
                content,
                session_id,
            )

            result = (
                f"Saved investigation summary for incident {content.incident_id}"
                if success
                else f"Failed to save investigation summary for {content.incident_id}"
            )
            logger.info(f"save_investigation result: {result}")
            return result

        except Exception as e:
            error_msg = f"Error saving investigation summary: {str(e)}"
            logger.error(f"save_investigation exception: {error_msg}", exc_info=True)
            return error_msg


class RetrieveMemoryInput(BaseModel):
    """RetrieveMemoryTool の入力スキーマ。"""

    memory_type: str = Field(
        description="メモリの種類: 'preference'、'infrastructure'、または 'investigation'"
    )
    query: str = Field(description="関連するメモリを検索するための検索クエリ")
    actor_id: str = Field(description="メモリを検索するアクター ID")
    max_results: int = Field(
        description="返す結果の最大数", default=5
    )
    session_id: Optional[str] = Field(
        description="セッション ID（インフラストラクチャと調査メモリには必須）",
        default=None,
    )


class RetrieveMemoryTool(BaseTool):
    """SRE 運用中にメモリを取得するためのツール。"""

    name: str = "retrieve_memory"
    description: str = """長期メモリから関連情報を取得する。
    以下をクエリ:
    - 現在のコンテキストのユーザー設定（エスカレーション、通知、ワークフロー設定）
    - サービスに関するインフラストラクチャ知識（依存関係、パターン、ベースライン）
    - 過去の調査サマリー（類似問題、解決戦略）

    パラメータ:
    - memory_type: "preference"、"infrastructure"、または "investigation"
    - query: 関連メモリの検索用語
    - actor_id: 設定/調査には user_id、インフラストラクチャにはエージェント actor_id
    - max_results: 結果の最大数（デフォルト 5）
    - session_id: オプション - None の場合、全セッションを検索（プランニングに便利）
    """
    args_schema: Type[BaseModel] = RetrieveMemoryInput

    def __init__(
        self, memory_client: SREMemoryClient, user_id: Optional[str] = None, **kwargs
    ):
        super().__init__(**kwargs)
        # メモリクライアントをインスタンス属性として保存（Pydantic フィールドではない）
        object.__setattr__(self, "_memory_client", memory_client)
        # インフラストラクチャ/調査の取得用に user_id を保存
        object.__setattr__(self, "_user_id", user_id)

    @property
    def memory_client(self) -> SREMemoryClient:
        """Memory クライアントを取得します。"""
        return getattr(self, "_memory_client")

    @property
    def user_id(self) -> Optional[str]:
        """user_id を取得します。"""
        return getattr(self, "_user_id", None)

    def set_user_id(self, user_id: str) -> None:
        """このツールインスタンスの user_id を設定します。"""
        object.__setattr__(self, "_user_id", user_id)

    def _run(
        self,
        memory_type: str,
        query: str,
        actor_id: str,
        max_results: int = 5,
        session_id: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """クエリに基づいてメモリを取得します。"""
        try:
            # インフラストラクチャと調査メモリの場合、利用可能であれば user_id を使用
            if memory_type in ["infrastructure", "investigation"] and self.user_id:
                effective_actor_id = self.user_id
                logger.info(
                    f"retrieve_memory: Overriding actor_id for {memory_type} - using user_id={self.user_id} instead of {actor_id}"
                )
            else:
                effective_actor_id = actor_id

            sanitized_actor_id = _sanitize_actor_id(effective_actor_id)
            logger.info(
                f"retrieve_memory called: type={memory_type}, query='{query}', actor_id={actor_id} -> {sanitized_actor_id}, max_results={max_results}"
            )

            if memory_type == "preference":
                logger.info(
                    f"Retrieving user preferences for actor_id={sanitized_actor_id}"
                )
                preferences = _retrieve_user_preferences(
                    self.memory_client, sanitized_actor_id, query
                )

                # JSON シリアライズ用に辞書に変換
                results = [pref.model_dump() for pref in preferences[:max_results]]
                logger.info(
                    f"retrieve_memory found {len(results)} user preferences (limited to {max_results})"
                )
                return json.dumps(results, indent=2, default=str)

            elif memory_type == "infrastructure":
                # 渡された session_id パラメータを使用（None = クロスセッション検索、指定 = セッション固有検索）
                search_type = (
                    "cross-session search"
                    if session_id is None
                    else f"session-specific search (session: {session_id})"
                )
                logger.info(
                    f"Retrieving infrastructure knowledge for actor_id={sanitized_actor_id} ({search_type})"
                )
                knowledge = _retrieve_infrastructure_knowledge(
                    self.memory_client,
                    sanitized_actor_id,
                    query,
                    session_id=session_id,  # 渡されたパラメータを使用
                )

                # JSON シリアライズ用に辞書に変換
                results = [know.model_dump() for know in knowledge[:max_results]]
                logger.info(
                    f"retrieve_memory found {len(results)} infrastructure knowledge items (limited to {max_results})"
                )
                return json.dumps(results, indent=2, default=str)

            elif memory_type == "investigation":
                # 渡された session_id パラメータを使用（None = クロスセッション検索、指定 = セッション固有検索）
                search_type = (
                    "cross-session search"
                    if session_id is None
                    else f"session-specific search (session: {session_id})"
                )
                logger.info(
                    f"Retrieving investigation summaries for actor_id={sanitized_actor_id} ({search_type})"
                )
                summaries = _retrieve_investigation_summaries(
                    self.memory_client,
                    sanitized_actor_id,
                    query,
                    session_id=session_id,  # 渡されたパラメータを使用
                )

                # JSON シリアライズ用に辞書に変換
                results = [summary.model_dump() for summary in summaries[:max_results]]
                logger.info(
                    f"retrieve_memory found {len(results)} investigation summaries (limited to {max_results})"
                )
                return json.dumps(results, indent=2, default=str)

            else:
                error_result = {
                    "error": f"Unknown memory type: {memory_type}",
                    "supported_types": [
                        "preference",
                        "infrastructure",
                        "investigation",
                    ],
                }
                logger.warning(
                    f"retrieve_memory error: unknown memory type {memory_type}"
                )
                return json.dumps(error_result, indent=2)

        except Exception as e:
            error_result = {"error": f"Error retrieving {memory_type} memory: {str(e)}"}
            logger.error(
                f"retrieve_memory exception: {error_result['error']}", exc_info=True
            )
            return json.dumps(error_result, indent=2)


def create_memory_tools(memory_client: SREMemoryClient) -> List[BaseTool]:
    """エージェント用のメモリツールを作成します。

    Args:
        memory_client: Memory クライアントインスタンス
    """
    return [
        SavePreferenceTool(memory_client),
        SaveInfrastructureTool(memory_client),
        SaveInvestigationTool(memory_client),
        RetrieveMemoryTool(memory_client),
    ]


def update_memory_tools_user_id(memory_tools: List[BaseTool], user_id: str) -> None:
    """リスト内のすべての RetrieveMemoryTool インスタンスの user_id を更新します。

    Args:
        memory_tools: メモリツールのリスト
        user_id: 設定する user_id
    """
    for tool in memory_tools:
        if hasattr(tool, "name") and tool.name == "retrieve_memory":
            if hasattr(tool, "set_user_id"):
                tool.set_user_id(user_id)
