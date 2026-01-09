#!/usr/bin/env python3

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, field_validator

from .agent_state import AgentState
from .constants import SREConstants
from .llm_utils import create_llm_with_error_handling
from .memory import create_conversation_memory_manager
from .memory.client import SREMemoryClient
from .memory.config import _load_memory_config
from .memory.hooks import MemoryHookProvider
from .memory.tools import create_memory_tools
from .output_formatter import create_formatter
from .prompt_loader import prompt_loader


def _get_user_from_env() -> str:
    """環境変数から user_id を取得します。

    Returns:
        USER_ID 環境変数からの user_id、またはデフォルト値
    """
    user_id = os.getenv("USER_ID")
    if user_id:
        logger.info(f"環境変数から user_id を使用しています: {user_id}")
        return user_id
    else:
        # Fallback to default user_id
        default_user_id = SREConstants.agents.default_user_id
        logger.warning(
            f"USER_ID not set in environment, using default: {default_user_id}"
        )
        return default_user_id


def _get_session_from_env(mode: str) -> str:
    """環境変数から session_id を取得するか、新しく生成します。

    Args:
        mode: 自動生成時のプレフィックス（"interactive" または "prompt"）

    Returns:
        SESSION_ID 環境変数からの session_id、または自動生成された値
    """
    session_id = os.getenv("SESSION_ID")
    if session_id:
        logger.info(f"環境変数から session_id を使用しています: {session_id}")
        return session_id
    else:
        # Auto-generate session_id
        auto_session_id = f"{mode}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(
            f"SESSION_ID not set in environment, auto-generated: {auto_session_id}"
        )
        return auto_session_id


# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

# Enable HTTP and MCP protocol logs for debugging
# Comment out the following lines to suppress these logs if needed
# mcp_loggers = ["streamable_http", "mcp.client.streamable_http", "httpx", "httpcore"]
#
# for logger_name in mcp_loggers:
#     mcp_logger = logging.getLogger(logger_name)
#     mcp_logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _json_serializer(obj):
    """デフォルトの JSON コードでシリアライズできないオブジェクト用の JSON シリアライザ。"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


class InvestigationPlan(BaseModel):
    """スーパーバイザーが作成した調査計画。

    Attributes:
        steps: 実行される 3-5 個の調査ステップのリスト
        agents_sequence: 呼び出すエージェントのシーケンス
        complexity: 計画の複雑さ（"simple" または "complex"）
        auto_execute: 自動実行するかユーザー承認を求めるか
        reasoning: 調査アプローチの簡単な説明
    """

    steps: List[str] = Field(
        description="List of 3-5 investigation steps to be executed"
    )

    @field_validator("steps", mode="before")
    @classmethod
    def validate_steps(cls, v):
        """必要に応じて文字列のステップをリストに変換する。

        Args:
            v: 検証する値（文字列またはリスト）

        Returns:
            ステップのリスト
        """
        if isinstance(v, str):
            # Split by numbered lines and clean up
            import re

            lines = v.strip().split("\n")
            steps = []
            for line in lines:
                line = line.strip()
                if line:
                    # Remove numbering like "1.", "2.", etc.
                    clean_line = re.sub(r"^\d+\.\s*", "", line)
                    if clean_line:
                        steps.append(clean_line)
            return steps
        return v

    agents_sequence: List[str] = Field(
        description="Sequence of agents to invoke (kubernetes_agent, logs_agent, metrics_agent, runbooks_agent)"
    )
    complexity: Literal["simple", "complex"] = Field(
        description="Whether this plan is simple (auto-execute) or complex (needs approval)"
    )
    auto_execute: bool = Field(
        description="Whether to execute automatically or ask for user approval"
    )
    reasoning: str = Field(
        description="Brief explanation of the investigation approach"
    )


class RouteDecision(BaseModel):
    """スーパーバイザーによるルーティング決定。

    Attributes:
        next: ルーティング先のエージェント、または完了時は "FINISH"
        reasoning: このルーティング決定が行われた理由の簡単な説明
    """

    next: Literal[
        "kubernetes_agent", "logs_agent", "metrics_agent", "runbooks_agent", "FINISH"
    ] = Field(description="The next agent to route to, or FINISH if done")
    reasoning: str = Field(
        description="Brief explanation of why this routing decision was made"
    )


def _read_supervisor_prompt() -> str:
    """ファイルからスーパーバイザーのシステムプロンプトを読み込む。

    Returns:
        スーパーバイザーのシステムプロンプト文字列
    """
    try:
        prompt_path = (
            Path(__file__).parent
            / "config"
            / "prompts"
            / "supervisor_multi_agent_prompt.txt"
        )
        if prompt_path.exists():
            return prompt_path.read_text().strip()
    except Exception as e:
        logger.warning(f"Supervisor プロンプトファイルを読み取れませんでした: {e}")

    # Fallback to supervisor fallback prompt file
    try:
        fallback_path = (
            Path(__file__).parent
            / "config"
            / "prompts"
            / "supervisor_fallback_prompt.txt"
        )
        if fallback_path.exists():
            return fallback_path.read_text().strip()
    except Exception as e:
        logger.warning(f"Supervisor フォールバックプロンプトファイルを読み取れませんでした: {e}")

    # Final hardcoded fallback if files not found
    return (
        "You are the Supervisor Agent orchestrating a team of specialized SRE agents."
    )


def _read_planning_prompt() -> str:
    """ファイルからプランニングプロンプトを読み込む。

    Returns:
        プランニングプロンプト文字列
    """
    try:
        prompt_path = (
            Path(__file__).parent
            / "config"
            / "prompts"
            / "supervisor_planning_prompt.txt"
        )
        if prompt_path.exists():
            return prompt_path.read_text().strip()
    except Exception as e:
        logger.warning(f"計画プロンプトファイルを読み取れませんでした: {e}")

    # フォールバックプランニングプロンプト
    return """最大2-3ステップのシンプルで焦点を絞った調査計画を作成してください。
以下のフィールドを含むJSON形式で計画を作成してください:
- steps: 3-5個の調査ステップのリスト
- agents_sequence: 呼び出すエージェントのリスト (kubernetes_agent, logs_agent, metrics_agent, runbooks_agent)
- complexity: "simple" または "complex"
- auto_execute: true または false
- reasoning: 調査アプローチの簡潔な説明"""


class SupervisorAgent:
    """メモリ機能を備えて他のエージェントをオーケストレーションするスーパーバイザーエージェント。

    このエージェントは調査計画の作成、エージェントへのルーティング、
    および複数のエージェントからのレスポンスの集約を担当する。

    Attributes:
        llm_provider: LLM プロバイダー（"bedrock" など）
        llm: LLM インスタンス
        system_prompt: システムプロンプト
        formatter: 出力フォーマッター
        memory_config: メモリ設定
        memory_client: メモリクライアント
        memory_hooks: メモリフックプロバイダー
        conversation_manager: 会話メモリマネージャー
        memory_tools: メモリツールのリスト
        planning_agent: プランニング用の ReAct エージェント
    """

    def __init__(
        self,
        llm_provider: str = "bedrock",
        force_delete_memory: bool = False,
        **llm_kwargs,
    ):
        self.llm_provider = llm_provider
        self.llm = self._create_llm(**llm_kwargs)
        self.system_prompt = _read_supervisor_prompt()
        self.formatter = create_formatter(llm_provider=llm_provider)

        # メモリシステムを初期化
        self.memory_config = _load_memory_config()
        if self.memory_config.enabled:
            # Bedrock の場合、llm_kwargs から region を使用（提供されている場合）
            memory_region = llm_kwargs.get("region_name", self.memory_config.region) if llm_provider == "bedrock" else self.memory_config.region
            self.memory_client = SREMemoryClient(
                memory_name=self.memory_config.memory_name,
                region=memory_region,
                force_delete=force_delete_memory,
            )
            self.memory_hooks = MemoryHookProvider(self.memory_client)
            self.conversation_manager = create_conversation_memory_manager(
                self.memory_client
            )

            # スーパーバイザーエージェント用のメモリツールを作成
            self.memory_tools = create_memory_tools(self.memory_client)

            # 監視付きプランニング用のメモリツール付き ReAct エージェントを作成
            self.planning_agent = create_react_agent(self.llm, self.memory_tools)
            logger.info(
                f"Memory system initialized for supervisor agent with {len(self.memory_tools)} memory tools"
            )
        else:
            self.memory_client = None
            self.memory_hooks = None
            self.conversation_manager = None
            self.memory_tools = []
            self.planning_agent = None
            logger.info("メモリシステムが無効です")

    def _create_llm(self, **kwargs):
        """改善されたエラーハンドリングを備えた LLM インスタンスを作成する。

        Args:
            **kwargs: LLM 作成に渡す追加のキーワード引数

        Returns:
            LLM インスタンス
        """
        return create_llm_with_error_handling(self.llm_provider, **kwargs)

    async def retrieve_memory(
        self,
        memory_type: str,
        query: str,
        actor_id: str,
        max_results: int = 5,
        session_id: Optional[str] = None,
    ) -> str:
        """retrieve_memory ツールを使用して長期メモリから情報を取得する。

        Args:
            memory_type: 取得するメモリのタイプ
            query: 検索クエリ
            actor_id: アクター ID
            max_results: 返す結果の最大数
            session_id: オプションのセッション ID

        Returns:
            取得したメモリ情報の文字列
        """
        if not self.memory_tools:
            return "Memory system not enabled"

        # Find the retrieve_memory tool
        retrieve_tool = None
        for tool in self.memory_tools:
            if tool.name == "retrieve_memory":
                retrieve_tool = tool
                break

        if not retrieve_tool:
            return "Retrieve memory tool not available"

        try:
            logger.info(
                f"Supervisor using retrieve_memory tool: type={memory_type}, query='{query}', actor_id={actor_id}"
            )
            result = retrieve_tool._run(
                memory_type=memory_type,
                query=query,
                actor_id=actor_id,
                max_results=max_results,
                session_id=session_id,
            )
            return result
        except Exception as e:
            logger.error(f"メモリの取得中にエラーが発生しました: {e}", exc_info=True)
            return f"メモリの取得中にエラーが発生しました: {str(e)}"

    async def create_investigation_plan(self, state: AgentState) -> InvestigationPlan:
        """メモリコンテキストを使用してユーザーのクエリに対する調査計画を作成する。

        Args:
            state: 現在のエージェント状態

        Returns:
            作成された調査計画
        """
        current_query = state.get("current_query", "No query provided")
        user_id = state.get("user_id", SREConstants.agents.default_user_id)
        incident_id = state.get("incident_id")

        # Update memory tools with the current user_id
        if self.memory_tools:
            from .memory.tools import update_memory_tools_user_id

            update_memory_tools_user_id(self.memory_tools, user_id)
            logger.info(f"user_id でメモリツールを更新しました: {user_id}")
        # Use user_id as actor_id for investigation memory retrieval (consistent with storage)
        actor_id = state.get(
            "user_id", state.get("actor_id", SREConstants.agents.default_actor_id)
        )
        session_id = state.get("session_id")

        # Retrieve memory context if memory system is enabled
        memory_context_text = ""
        if self.memory_client:
            try:
                logger.info(
                    f"Retrieving memory context for user_id={user_id}, query='{current_query}'"
                )

                # Get memory context from hooks
                if not session_id:
                    raise ValueError(
                        "session_id is required for memory retrieval but not found in state"
                    )

                memory_context = self.memory_hooks.on_investigation_start(
                    query=current_query,
                    user_id=user_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    incident_id=incident_id,
                )

                # Store memory context in state
                state["memory_context"] = memory_context

                # Log user preferences for debugging (they're stored in memory_context)
                user_prefs = memory_context.get("user_preferences", [])
                logger.debug(
                    f"Stored {len(user_prefs)} user preferences in memory_context during planning"
                )
                logger.debug(
                    f"User preferences being stored in memory_context: {user_prefs}"
                )

                # Format memory context for prompt
                pref_count = len(memory_context.get("user_preferences", []))
                infrastructure_by_agent = memory_context.get(
                    "infrastructure_by_agent", {}
                )
                total_knowledge = sum(
                    len(memories) for memories in infrastructure_by_agent.values()
                )
                investigation_count = len(memory_context.get("past_investigations", []))

                if memory_context.get("user_preferences"):
                    memory_context_text += f"\nRelevant User Preferences:\n{json.dumps(memory_context['user_preferences'], indent=2, default=_json_serializer)}\n"

                if infrastructure_by_agent:
                    memory_context_text += (
                        "\nRelevant Infrastructure Knowledge (organized by agent):\n"
                    )
                    for agent_id, agent_memories in infrastructure_by_agent.items():
                        memory_context_text += (
                            f"\n  From {agent_id} ({len(agent_memories)} items):\n"
                        )
                        memory_context_text += f"{json.dumps(agent_memories, indent=4, default=_json_serializer)}\n"

                if memory_context.get("past_investigations"):
                    memory_context_text += f"\nSimilar Past Investigations:\n{json.dumps(memory_context['past_investigations'], indent=2, default=_json_serializer)}\n"

                logger.info(
                    f"Retrieved memory context for planning: {pref_count} preferences, {total_knowledge} knowledge items from {len(infrastructure_by_agent)} agents, {investigation_count} past investigations"
                )

                if pref_count + total_knowledge + investigation_count == 0:
                    logger.info(
                        "No relevant memories found - this may be the first interaction or a new topic"
                    )

            except Exception as e:
                logger.error(f"メモリコンテキストの取得に失敗しました: {e}", exc_info=True)
                memory_context_text = ""

        # Enhanced planning prompt that instructs the agent to use memory tools
        planning_instructions = _read_planning_prompt()
        # Replace placeholders manually to avoid issues with JSON braces in the prompt
        formatted_planning_instructions = planning_instructions.replace(
            "{user_id}", user_id
        )
        if session_id:
            formatted_planning_instructions = formatted_planning_instructions.replace(
                "{session_id}", session_id
            )

        planning_prompt = f"""{self.system_prompt}

User's query: {current_query}
{memory_context_text}

{formatted_planning_instructions}"""

        if self.planning_agent and self.memory_tools:
            # Use planning agent with memory tools
            try:
                # Create messages for the planning agent
                messages = [
                    SystemMessage(content=planning_prompt),
                    HumanMessage(
                        content=f"Create an investigation plan for: {current_query}"
                    ),
                ]

                # Use the planning agent with memory tools
                plan_response = await self.planning_agent.ainvoke(
                    {"messages": messages}
                )

                # Extract the final message content
                if plan_response and "messages" in plan_response:
                    final_message = plan_response["messages"][-1]
                    plan_text = final_message.content

                    # Always log the complete planning agent response
                    logger.info(f"計画エージェントの元レスポンス: {plan_text}")

                    # Try to extract JSON from the response
                    import re

                    # Look for JSON in the response - try multiple patterns
                    json_patterns = [
                        r'\{[^{}]*"steps"[^{}]*"agents_sequence"[^{}]*"complexity"[^{}]*"auto_execute"[^{}]*"reasoning"[^{}]*\}',  # Specific pattern for our structure
                        r'\{.*?"steps".*?\}',  # Broader pattern
                        r"\{.*\}",  # Most general pattern
                    ]

                    json_content = None
                    for pattern in json_patterns:
                        json_match = re.search(pattern, plan_text, re.DOTALL)
                        if json_match:
                            json_content = json_match.group()
                            logger.info(
                                f"Extracted JSON content using pattern: {json_content}"
                            )
                            break

                    if json_content:
                        try:
                            # Clean up the JSON content
                            json_content = json_content.strip()
                            plan_json = json.loads(json_content)
                            logger.info(f"JSON を正常にパースしました: {plan_json}")
                            plan = InvestigationPlan(**plan_json)
                            logger.info(
                                "Successfully created InvestigationPlan from JSON"
                            )
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}")
                            logger.error(f"Failed JSON content: {json_content}")
                            logger.warning(
                                "Could not parse JSON from planning agent response, using fallback"
                            )
                            plan = InvestigationPlan(
                                steps=[
                                    "Investigate the reported issue",
                                    "Analyze findings and provide recommendations",
                                ],
                                agents_sequence=["metrics_agent", "logs_agent"],
                                complexity="simple",
                                auto_execute=True,
                                reasoning="Default investigation plan due to JSON parsing error",
                            )
                        except Exception as e:
                            logger.error(f"InvestigationPlan の作成中にエラーが発生しました: {e}")
                            logger.error(f"Plan JSON was: {plan_json}")
                            logger.warning(
                                "Could not create InvestigationPlan from parsed JSON, using fallback"
                            )
                            plan = InvestigationPlan(
                                steps=[
                                    "Investigate the reported issue",
                                    "Analyze findings and provide recommendations",
                                ],
                                agents_sequence=["metrics_agent", "logs_agent"],
                                complexity="simple",
                                auto_execute=True,
                                reasoning="Default investigation plan due to validation error",
                            )
                    else:
                        # Fallback to basic plan if JSON parsing fails
                        logger.warning(
                            "Could not find JSON pattern in planning agent response, using fallback"
                        )
                        logger.warning(f"レスポンス内容: {plan_text}")
                        plan = InvestigationPlan(
                            steps=[
                                "Investigate the reported issue",
                                "Analyze findings and provide recommendations",
                            ],
                            agents_sequence=["metrics_agent", "logs_agent"],
                            complexity="simple",
                            auto_execute=True,
                            reasoning="Default investigation plan due to no JSON found",
                        )
                else:
                    raise ValueError("No response from planning agent")

            except Exception as e:
                logger.error(
                    f"Error using planning agent with memory tools: {e}", exc_info=True
                )
                # Fallback to structured output without tools
                structured_llm = self.llm.with_structured_output(InvestigationPlan)
                plan = await structured_llm.ainvoke(
                    [
                        SystemMessage(content=planning_prompt),
                        HumanMessage(content=current_query),
                    ]
                )
        else:
            # Fallback to structured output without memory tools
            structured_llm = self.llm.with_structured_output(InvestigationPlan)
            plan = await structured_llm.ainvoke(
                [
                    SystemMessage(content=planning_prompt),
                    HumanMessage(content=current_query),
                ]
            )

        logger.info(
            f"Created investigation plan: {len(plan.steps)} steps, complexity: {plan.complexity}"
        )

        # Store conversation in memory
        if self.conversation_manager and user_id and session_id:
            try:
                # Get supervisor display name with fallback
                supervisor_name = getattr(SREConstants.agents, "supervisor", None)
                if supervisor_name:
                    supervisor_display_name = supervisor_name.display_name
                else:
                    supervisor_display_name = "Supervisor Agent"

                messages_to_store = [
                    (current_query, "USER"),
                    (
                        f"[Agent: {supervisor_display_name}]\nInvestigation Plan:\n{self._format_plan_markdown(plan)}",
                        "ASSISTANT",
                    ),
                ]

                success = self.conversation_manager.store_conversation_batch(
                    messages=messages_to_store,
                    user_id=user_id,
                    session_id=session_id,
                    agent_name=supervisor_display_name,
                )

                if success:
                    logger.info("スーパーバイザー: 計画会話を正常に保存しました")
                else:
                    logger.warning("スーパーバイザー: 計画会話の保存に失敗しました")

            except Exception as e:
                logger.error(
                    f"Supervisor: Error storing planning conversation: {e}",
                    exc_info=True,
                )

        return plan

    def _format_plan_markdown(self, plan: InvestigationPlan) -> str:
        """調査計画を適切なフォーマットの Markdown として整形する。

        Args:
            plan: 整形する調査計画

        Returns:
            Markdown 形式の計画文字列
        """
        plan_text = "## 🔍 Investigation Plan\n\n"

        # Add steps with proper numbering and formatting
        for i, step in enumerate(plan.steps, 1):
            plan_text += f"**{i}.** {step}\n\n"

        # Add metadata
        plan_text += f"**📊 Complexity:** {plan.complexity.title()}\n"
        plan_text += f"**🤖 Auto-execute:** {'Yes' if plan.auto_execute else 'No'}\n"
        if plan.reasoning:
            plan_text += f"**💭 Reasoning:** {plan.reasoning}\n"

        # Add agents involved
        if plan.agents_sequence:
            agents_list = ", ".join(
                [agent.replace("_", " ").title() for agent in plan.agents_sequence]
            )
            plan_text += f"**👥 Agents involved:** {agents_list}\n"

        return plan_text

    async def route(self, state: AgentState) -> Dict[str, Any]:
        """次にどのエージェントがクエリを処理すべきかを決定する。

        Args:
            state: 現在のエージェント状態

        Returns:
            次のエージェントとメタデータを含む辞書
        """
        agents_invoked = state.get("agents_invoked", [])

        # Check if we have an existing plan
        existing_plan = state.get("metadata", {}).get("investigation_plan")

        if not existing_plan:
            # First time - create investigation plan
            plan = await self.create_investigation_plan(state)

            # Check if we should auto-approve the plan (defaults to False if not set)
            auto_approve = state.get("auto_approve_plan", False)

            if not plan.auto_execute and not auto_approve:
                # Complex plan - present to user for approval
                plan_text = self._format_plan_markdown(plan)
                return {
                    "next": "FINISH",
                    "metadata": {
                        **state.get("metadata", {}),
                        "investigation_plan": plan.model_dump(),
                        "routing_reasoning": f"Created investigation plan. Complexity: {plan.complexity}",
                        "plan_pending_approval": True,
                        "plan_text": plan_text,
                    },
                    # Preserve memory context in state
                    "memory_context": state.get("memory_context", {}),
                }
            else:
                # Simple plan - start execution
                next_agent = (
                    plan.agents_sequence[0] if plan.agents_sequence else "FINISH"
                )
                plan_text = self._format_plan_markdown(plan)
                return {
                    "next": next_agent,
                    "metadata": {
                        **state.get("metadata", {}),
                        "investigation_plan": plan.model_dump(),
                        "routing_reasoning": f"Executing plan step 1: {plan.steps[0] if plan.steps else 'Start'}",
                        "plan_step": 0,
                        "plan_text": plan_text,
                        "show_plan": True,
                    },
                    # Preserve memory context in state
                    "memory_context": state.get("memory_context", {}),
                }
        else:
            # Continue executing existing plan
            plan = InvestigationPlan(**existing_plan)
            current_step = state.get("metadata", {}).get("plan_step", 0)

            # Check if plan is complete
            if current_step >= len(plan.agents_sequence) or not agents_invoked:
                next_step = current_step
            else:
                next_step = current_step + 1

            if next_step >= len(plan.agents_sequence):
                # Plan complete
                return {
                    "next": "FINISH",
                    "metadata": {
                        **state.get("metadata", {}),
                        "routing_reasoning": "Investigation plan completed. Presenting results.",
                        "plan_step": next_step,
                    },
                    # Preserve memory context in state
                    "memory_context": state.get("memory_context", {}),
                }
            else:
                # Continue with next agent in plan
                next_agent = plan.agents_sequence[next_step]
                step_description = (
                    plan.steps[next_step]
                    if next_step < len(plan.steps)
                    else f"Execute {next_agent}"
                )

                return {
                    "next": next_agent,
                    "metadata": {
                        **state.get("metadata", {}),
                        "routing_reasoning": f"Executing plan step {next_step + 1}: {step_description}",
                        "plan_step": next_step,
                    },
                    # Preserve memory context in state
                    "memory_context": state.get("memory_context", {}),
                }

    async def aggregate_responses(self, state: AgentState) -> Dict[str, Any]:
        """複数のエージェントからのレスポンスを集約して最終レスポンスを生成する。

        Args:
            state: 各エージェントの結果を含む現在のエージェント状態

        Returns:
            最終レスポンスと次のステップを含む辞書
        """
        agent_results = state.get("agent_results", {})
        metadata = state.get("metadata", {})

        # Check if this is a plan approval request
        if metadata.get("plan_pending_approval"):
            plan = metadata.get("investigation_plan", {})
            query = state.get("current_query", "Investigation") or "Investigation"

            # Use enhanced formatting for plan approval
            try:
                approval_response = self.formatter.format_plan_approval(plan, query)
            except Exception as e:
                logger.warning(
                    f"Failed to use enhanced formatting: {e}, falling back to plain text"
                )
                plan_text = metadata.get("plan_text", "")
                approval_response = f"""## Investigation Plan

I've analyzed your query and created the following investigation plan:

{plan_text}

**Complexity:** {plan.get("complexity", "unknown").title()}
**Reasoning:** {plan.get("reasoning", "Standard investigation approach")}

This plan will help systematically investigate your issue. Would you like me to proceed with this plan, or would you prefer to modify it?

You can:
- Type "proceed" or "yes" to execute the plan
- Type "modify" to suggest changes
- Ask specific questions about any step"""

            return {"final_response": approval_response, "next": "FINISH"}

        if not agent_results:
            return {"final_response": "No agent responses to aggregate."}

        # Use enhanced formatting for investigation results
        query = state.get("current_query", "Investigation") or "Investigation"
        plan = metadata.get("investigation_plan")

        # Get user preferences from memory_context (not directly from state)
        user_preferences = []
        if "memory_context" in state:
            memory_ctx = state["memory_context"]
            user_preferences = memory_ctx.get("user_preferences", [])
            logger.debug(
                f"Memory context found with {len(user_preferences)} user preferences"
            )
        else:
            logger.debug("state 内に memory_context が見つかりません")

        logger.info(
            f"Retrieved user preferences from memory_context for aggregation: {len(user_preferences)} items"
        )
        logger.debug(f"Full state keys available: {list(state.keys())}")

        try:
            # Try enhanced formatting first
            final_response = self.formatter.format_investigation_response(
                query=query,
                agent_results=agent_results,
                metadata=metadata,
                plan=plan,
                user_preferences=user_preferences,
            )
        except Exception as e:
            logger.warning(
                f"Failed to use enhanced formatting: {e}, falling back to LLM aggregation"
            )

            # Fallback to LLM-based aggregation
            try:
                # Get system message from prompt loader
                system_prompt = prompt_loader.load_prompt(
                    "supervisor_aggregation_system"
                )

                # Determine if this is plan-based or standard aggregation
                is_plan_based = plan is not None

                # Prepare template variables
                query = (
                    state.get("current_query", "No query provided")
                    or "No query provided"
                )
                agent_results_json = json.dumps(
                    agent_results, indent=2, default=_json_serializer
                )
                auto_approve_plan = state.get("auto_approve_plan", False) or False

                # Use the user_preferences we already retrieved
                user_preferences_json = (
                    json.dumps(user_preferences, indent=2, default=_json_serializer)
                    if user_preferences
                    else ""
                )

                if is_plan_based:
                    current_step = metadata.get("plan_step", 0)
                    total_steps = len(plan.get("steps", []))
                    plan_json = json.dumps(
                        plan.get("steps", []), indent=2, default=_json_serializer
                    )

                    aggregation_prompt = (
                        prompt_loader.get_supervisor_aggregation_prompt(
                            is_plan_based=True,
                            query=query,
                            agent_results=agent_results_json,
                            auto_approve_plan=auto_approve_plan,
                            current_step=current_step + 1,
                            total_steps=total_steps,
                            plan=plan_json,
                            user_preferences=user_preferences_json,
                        )
                    )
                else:
                    aggregation_prompt = (
                        prompt_loader.get_supervisor_aggregation_prompt(
                            is_plan_based=False,
                            query=query,
                            agent_results=agent_results_json,
                            auto_approve_plan=auto_approve_plan,
                            user_preferences=user_preferences_json,
                        )
                    )

            except Exception as e:
                logger.error(f"集計プロンプトの読み込み中にエラーが発生しました: {e}")
                # Fallback to simple prompt
                system_prompt = "あなたは技術調査結果を明確かつプロフェッショナルに提示する専門家です。"
                aggregation_prompt = f"Summarize these findings: {json.dumps(agent_results, indent=2, default=_json_serializer)}"

            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=aggregation_prompt),
                ]
            )

            final_response = response.content

        # Store final response conversation in memory
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        if (
            self.conversation_manager
            and user_id
            and session_id
            and not metadata.get("plan_pending_approval")
        ):
            try:
                # Store the final aggregated response
                # Get supervisor display name with fallback
                supervisor_name = getattr(SREConstants.agents, "supervisor", None)
                if supervisor_name:
                    supervisor_display_name = supervisor_name.display_name
                else:
                    supervisor_display_name = "Supervisor Agent"

                messages_to_store = [
                    (
                        f"[Agent: {supervisor_display_name}]\n{final_response}",
                        "ASSISTANT",
                    )
                ]

                success = self.conversation_manager.store_conversation_batch(
                    messages=messages_to_store,
                    user_id=user_id,
                    session_id=session_id,
                    agent_name=supervisor_display_name,
                )

                if success:
                    logger.info(
                        "Supervisor: Successfully stored final response conversation"
                    )
                else:
                    logger.warning(
                        "Supervisor: Failed to store final response conversation"
                    )

            except Exception as e:
                logger.error(
                    f"Supervisor: Error storing final response conversation: {e}",
                    exc_info=True,
                )

        # Save investigation summary to memory if enabled
        if self.memory_client and not metadata.get("plan_pending_approval"):
            try:
                incident_id = state.get("incident_id", "auto-generated")
                agents_used = state.get("agents_invoked", [])
                logger.debug(
                    f"Saving investigation summary for incident_id={incident_id}, agents_used={agents_used}"
                )

                # Use user_id as actor_id for investigation summaries (consistent with conversation memory)
                actor_id = state.get(
                    "user_id",
                    state.get("actor_id", SREConstants.agents.default_actor_id),
                )
                self.memory_hooks.on_investigation_complete(
                    state=state, final_response=final_response, actor_id=actor_id
                )
                logger.info(
                    f"Saved investigation summary to memory for incident {incident_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to save investigation summary: {e}", exc_info=True
                )

        return {"final_response": final_response, "next": "FINISH"}
