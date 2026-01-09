import logging

from pydantic import BaseModel, Field

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class MemoryConfig(BaseModel):
    """SRE Agent メモリシステムの設定。"""

    enabled: bool = Field(default=True, description="Enable memory system")
    memory_name: str = Field(
        default="sre_agent_memory", description="Base name for memory instances"
    )
    region: str = Field(
        default="us-east-1", description="AWS region for memory storage"
    )

    # Retention settings
    preferences_retention_days: int = Field(
        default=90, description="Days to retain user preferences"
    )
    infrastructure_retention_days: int = Field(
        default=30, description="Days to retain infrastructure knowledge"
    )
    investigation_retention_days: int = Field(
        default=60, description="Days to retain investigation summaries"
    )

    # Feature flags
    auto_capture_preferences: bool = Field(
        default=True, description="Automatically capture user preferences"
    )
    auto_capture_infrastructure: bool = Field(
        default=True, description="Automatically capture infrastructure patterns"
    )
    auto_generate_summaries: bool = Field(
        default=True, description="Automatically generate investigation summaries"
    )


def _load_memory_config() -> MemoryConfig:
    """デフォルト値でメモリ設定を読み込みます。"""
    try:
        return MemoryConfig()
    except Exception as e:
        logger.warning(f"メモリ設定の読み込みに失敗しました: {e}、デフォルト値を使用します")
        return MemoryConfig()
