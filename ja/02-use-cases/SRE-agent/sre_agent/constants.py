#!/usr/bin/env python3

import logging

from pydantic import BaseModel, Field

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class ModelConfig(BaseModel):
    """モデル設定定数。"""

    # Anthropic model IDs
    anthropic_model_id: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Default Anthropic Claude model ID",
    )

    # Amazon Bedrock model IDs
    bedrock_model_id: str = Field(
        default="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        description="Default Amazon Bedrock Claude model ID",
    )

    # Model parameters
    default_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Default temperature for LLM generation",
    )

    default_max_tokens: int = Field(
        default=4096,
        ge=1,
        le=100000,
        description="Default max tokens for agent responses",
    )

    output_formatter_max_tokens: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Max tokens for output formatter LLM calls",
    )


class AWSConfig(BaseModel):
    """AWS 設定定数。"""

    default_region: str = Field(default="us-east-1", description="Default AWS region")

    bedrock_endpoint_url: str = Field(
        default="https://bedrock-agentcore-control.us-east-1.amazonaws.com",
        description="Amazon Bedrock AgentCore control endpoint URL",
    )

    credential_provider_endpoint_url: str = Field(
        default="https://bedrock-agentcore-control.us-east-1.amazonaws.com",
        description="AWS credential provider endpoint URL",
    )


class TimeoutConfig(BaseModel):
    """タイムアウト設定定数。"""

    graph_execution_timeout_seconds: int = Field(
        default=600,
        ge=1,
        le=3600,
        description="Maximum time to wait for graph execution (10 minutes)",
    )

    mcp_tools_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum time to wait for MCP tools loading",
    )


class PromptConfig(BaseModel):
    """プロンプト設定定数。"""

    prompts_directory: str = Field(
        default="config/prompts",
        description="Directory containing prompt template files",
    )

    agent_prompt_files: dict[str, str] = Field(
        default={
            "kubernetes": "kubernetes_agent_prompt.txt",
            "logs": "logs_agent_prompt.txt",
            "metrics": "metrics_agent_prompt.txt",
            "runbooks": "runbooks_agent_prompt.txt",
        },
        description="Mapping of agent types to their prompt files",
    )

    supervisor_prompt_files: dict[str, str] = Field(
        default={
            "plan_aggregation": "supervisor_plan_aggregation.txt",
            "standard_aggregation": "supervisor_standard_aggregation.txt",
            "system": "supervisor_aggregation_system.txt",
        },
        description="Supervisor aggregation prompt files",
    )

    output_formatter_prompt_files: dict[str, str] = Field(
        default={
            "executive_summary_system": "executive_summary_system.txt",
            "executive_summary_user_template": "executive_summary_user_template.txt",
        },
        description="Output formatter prompt files",
    )

    base_prompt_file: str = Field(
        default="agent_base_prompt.txt",
        description="Base prompt template used by all agents",
    )

    enable_prompt_caching: bool = Field(
        default=True, description="Whether to enable LRU caching for prompt loading"
    )

    max_cache_size: int = Field(
        default=32,
        ge=1,
        le=128,
        description="Maximum number of prompts to cache in memory",
    )


class ApplicationConfig(BaseModel):
    """アプリケーション設定定数。"""

    agent_model_name: str = Field(
        default="sre-multi-agent", description="Model name returned in API responses"
    )

    default_output_dir: str = Field(
        default="./reports",
        description="Default directory for saving investigation reports",
    )

    conversation_state_file: str = Field(
        default=".multi_agent_conversation_state.json",
        description="Filename for saving conversation state",
    )

    spinner_chars: list[str] = Field(
        default=["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        description="Characters used for spinner animation",
    )


class AgentMetadata(BaseModel):
    """単一エージェントのメタデータ。"""

    actor_id: str = Field(description="Unique actor ID for memory operations")
    display_name: str = Field(description="Human-readable agent name")
    description: str = Field(description="Agent capabilities description")
    agent_type: str = Field(description="Agent type for prompt loading")


class MemoryConfig(BaseModel):
    """メモリシステム設定定数。"""

    # Query constants for comprehensive memory retrieval
    user_preferences_query: str = Field(
        default="user settings communication escalation notification reporting workflow preferences",
        description="Natural language query to retrieve all user preferences including communication, escalation, notification, reporting, and workflow preferences",
    )

    # Memory retrieval limits
    max_preferences_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of preference memories to retrieve",
    )

    max_infrastructure_results: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of infrastructure knowledge memories to retrieve",
    )

    max_investigation_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of past investigation memories to retrieve",
    )

    # Content length limits for memory storage
    max_content_length: int = Field(
        default=9000,
        ge=1000,
        le=10000,
        description="Maximum character length for conversation content stored in memory",
    )


class AgentsConstant(BaseModel):
    """SRE システム用のエージェント固有定数。"""

    default_actor_id: str = Field(
        default="sre-agent",
        description="Default actor ID used for saving and retrieving memories",
    )

    default_user_id: str = Field(
        default="default-sre-user",
        description="Default user ID for memory operations when no user is specified",
    )

    session_prefix: str = Field(
        default="sre-session", description="Prefix used for session IDs"
    )

    memory_types: dict[str, str] = Field(
        default={
            "preferences": "preferences",
            "infrastructure": "infrastructure",
            "investigations": "investigations",
        },
        description="Memory type identifiers",
    )

    # Agent metadata for consistent identity management
    agents: dict[str, AgentMetadata] = Field(
        default={
            "kubernetes": AgentMetadata(
                actor_id="kubernetes-agent",
                display_name="Kubernetes Infrastructure Agent",
                description="Manages Kubernetes cluster operations and monitoring",
                agent_type="kubernetes",
            ),
            "logs": AgentMetadata(
                actor_id="logs-agent",
                display_name="Application Logs Agent",
                description="Handles application log analysis and searching",
                agent_type="logs",
            ),
            "metrics": AgentMetadata(
                actor_id="metrics-agent",
                display_name="Performance Metrics Agent",
                description="Provides application performance and resource metrics",
                agent_type="metrics",
            ),
            "runbooks": AgentMetadata(
                actor_id="runbooks-agent",
                display_name="Operational Runbooks Agent",
                description="Provides operational procedures and troubleshooting guides",
                agent_type="runbooks",
            ),
            "supervisor": AgentMetadata(
                actor_id="supervisor-agent",
                display_name="Supervisor Agent",
                description="Orchestrates investigation planning and coordinates multiple specialized agents",
                agent_type="supervisor",
            ),
        },
        description="Metadata for all agents in the system",
    )


class SREConstants:
    """SRE エージェントシステムの中央設定定数。

    このクラスは、SRE エージェントアプリケーション全体で使用されるすべての設定定数に
    アクセスするための集中的な方法を提供します。バリデーションと型安全性のために
    Pydantic モデルを使用しています。

    Usage:
        from .constants import SREConstants

        # モデル設定にアクセス
        model_id = SREConstants.model.anthropic_model_id
        temperature = SREConstants.model.default_temperature

        # AWS 設定にアクセス
        region = SREConstants.aws.default_region

        # タイムアウト設定にアクセス
        timeout = SREConstants.timeouts.graph_execution_timeout_seconds

        # プロンプト設定にアクセス
        prompts_dir = SREConstants.prompts.prompts_directory
        agent_files = SREConstants.prompts.agent_prompt_files

        # アプリケーション設定にアクセス
        output_dir = SREConstants.app.default_output_dir
    """

    model: ModelConfig = ModelConfig()
    aws: AWSConfig = AWSConfig()
    timeouts: TimeoutConfig = TimeoutConfig()
    prompts: PromptConfig = PromptConfig()
    app: ApplicationConfig = ApplicationConfig()
    agents: AgentsConstant = AgentsConstant()
    memory: MemoryConfig = MemoryConfig()

    @classmethod
    def get_model_config(cls, provider: str, **kwargs) -> dict:
        """特定のプロバイダー用のモデル設定を取得します。

        Args:
            provider: LLM プロバイダー（"anthropic" または "bedrock"）
            **kwargs: 追加の設定オーバーライド

        Returns:
            モデル設定を含む辞書
        """
        if provider == "anthropic":
            return {
                "model_id": kwargs.get("model_id", cls.model.anthropic_model_id),
                "max_tokens": kwargs.get("max_tokens", cls.model.default_max_tokens),
                "temperature": kwargs.get("temperature", cls.model.default_temperature),
            }
        elif provider == "bedrock":
            return {
                "model_id": kwargs.get("model_id", cls.model.bedrock_model_id),
                "region_name": kwargs.get("region_name", cls.aws.default_region),
                "max_tokens": kwargs.get("max_tokens", cls.model.default_max_tokens),
                "temperature": kwargs.get("temperature", cls.model.default_temperature),
            }
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @classmethod
    def get_output_formatter_config(cls, provider: str, **kwargs) -> dict:
        """出力フォーマッター用のモデル設定を取得します。

        Args:
            provider: LLM プロバイダー（"anthropic" または "bedrock"）
            **kwargs: 追加の設定オーバーライド

        Returns:
            出力フォーマッターのモデル設定を含む辞書
        """
        config = cls.get_model_config(provider, **kwargs)
        # Override max_tokens for output formatter
        config["max_tokens"] = kwargs.get(
            "max_tokens", cls.model.output_formatter_max_tokens
        )
        return config

    @classmethod
    def get_prompt_config(cls) -> PromptConfig:
        """プロンプト設定を取得します。

        Returns:
            すべてのプロンプト設定を含む PromptConfig インスタンス
        """
        return cls.prompts


# Convenience instance for easy access
constants = SREConstants()

# Legacy support - individual constants for backward compatibility if needed
ANTHROPIC_MODEL_ID = constants.model.anthropic_model_id
BEDROCK_MODEL_ID = constants.model.bedrock_model_id
DEFAULT_TEMPERATURE = constants.model.default_temperature
DEFAULT_MAX_TOKENS = constants.model.default_max_tokens
DEFAULT_AWS_REGION = constants.aws.default_region
GRAPH_EXECUTION_TIMEOUT_SECONDS = constants.timeouts.graph_execution_timeout_seconds
AGENT_MODEL_NAME = constants.app.agent_model_name
DEFAULT_OUTPUT_DIR = constants.app.default_output_dir
DEFAULT_ACTOR_ID = constants.agents.default_actor_id
