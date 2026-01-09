#!/usr/bin/env python3

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from .agent_state import AgentState
from .constants import AgentMetadata
from .llm_utils import create_llm_with_error_handling
from .memory import SREMemoryClient, create_conversation_memory_manager
from .prompt_loader import prompt_loader

# Logging will be configured by the main entry point
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_agent_config() -> Dict[str, Any]:
    """YAML ファイルからエージェント設定を読み込みます。"""
    config_path = Path(__file__).parent / "config" / "agent_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _create_llm(provider: str = "bedrock", **kwargs):
    """改善されたエラーハンドリングを備えた LLM インスタンスを作成します。"""
    return create_llm_with_error_handling(provider, **kwargs)


def _filter_tools_for_agent(
    all_tools: List[BaseTool], agent_name: str, config: Dict[str, Any]
) -> List[BaseTool]:
    """エージェント設定に基づいてツールをフィルタリングします。"""
    agent_config = config["agents"].get(agent_name, {})
    allowed_tools = agent_config.get("tools", [])

    # Also include global tools
    global_tools = config.get("global_tools", [])
    allowed_tools.extend(global_tools)

    # Filter tools based on their names
    filtered_tools = []
    for tool in all_tools:
        tool_name = getattr(tool, "name", "")
        # Remove any prefix from tool name for matching
        base_tool_name = tool_name.split("___")[-1] if "___" in tool_name else tool_name

        if base_tool_name in allowed_tools:
            filtered_tools.append(tool)

    logger.info(f"エージェント {agent_name} は {len(filtered_tools)} 個のツールにアクセスできます")

    # デバッグ: このエージェントに追加されるツールを表示
    logger.info(f"エージェント {agent_name} のツール名:")
    for tool in filtered_tools:
        tool_name = getattr(tool, "name", "unknown")
        tool_description = getattr(tool, "description", "No description")
        # Extract just the first line of description for cleaner logging
        description_first_line = (
            tool_description.split("\n")[0].strip()
            if tool_description
            else "No description"
        )
        logger.info(f"  - {tool_name}: {description_first_line}")

    # デバッグ: 許可されたツールと利用可能なツールを表示
    logger.debug(f"エージェント {agent_name} の許可されたツール: {allowed_tools}")
    all_tool_names = [getattr(tool, "name", "unknown") for tool in all_tools]
    logger.debug(f"エージェント {agent_name} の利用可能なツール: {all_tool_names}")

    return filtered_tools


class BaseAgentNode:
    """すべてのエージェントノードの基底クラス。"""

    def __init__(
        self,
        name: str,
        description: str,
        tools: List[BaseTool],
        llm_provider: str = "bedrock",
        agent_metadata: AgentMetadata = None,
        **llm_kwargs,
    ):
        # Use agent_metadata if provided, otherwise fall back to individual parameters
        if agent_metadata:
            self.name = agent_metadata.display_name
            self.description = agent_metadata.description
            self.actor_id = agent_metadata.actor_id
            self.agent_type = agent_metadata.agent_type
        else:
            # Backward compatibility - use provided name/description
            self.name = name
            self.description = description
            self.actor_id = None  # No actor_id available in legacy mode
            self.agent_type = "unknown"

        self.tools = tools
        self.llm_provider = llm_provider
        self.llm_kwargs = llm_kwargs  # Store for later use in memory client creation

        logger.info(
            f"{self.name} を初期化中 - LLM プロバイダー: {llm_provider}, actor_id: {self.actor_id}, ツール: {[tool.name for tool in tools]}"
        )
        self.llm = _create_llm(llm_provider, **llm_kwargs)

        # Create the react agent
        self.agent = create_react_agent(self.llm, self.tools)

    def _get_system_prompt(self) -> str:
        """プロンプトローダーを使用してこのエージェントのシステムプロンプトを取得します。"""
        try:
            # Determine agent type based on name
            agent_type = self._get_agent_type()

            # Use prompt loader to get complete prompt
            return prompt_loader.get_agent_prompt(
                agent_type=agent_type,
                agent_name=self.name,
                agent_description=self.description,
            )
        except Exception as e:
            logger.error(f"エージェント {self.name} のプロンプト読み込みエラー: {e}")
            # 読み込み失敗時は基本プロンプトにフォールバック
            return f"You are the {self.name}. {self.description}"

    def _get_agent_type(self) -> str:
        """エージェントメタデータに基づいてエージェントタイプを決定するか、名前解析にフォールバックします。"""
        # Use agent_type from metadata if available
        if hasattr(self, "agent_type") and self.agent_type != "unknown":
            return self.agent_type

        # Fallback to name-based detection for backward compatibility
        name_lower = self.name.lower()

        if "kubernetes" in name_lower:
            return "kubernetes"
        elif "logs" in name_lower or "application" in name_lower:
            return "logs"
        elif "metrics" in name_lower or "performance" in name_lower:
            return "metrics"
        elif "runbooks" in name_lower or "operational" in name_lower:
            return "runbooks"
        else:
            logger.warning(f"エージェントの不明なタイプ: {self.name}")
            return "unknown"

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """現在の状態を処理し、更新された状態を返します。"""
        try:
            # Get the last user message
            messages = state["messages"]

            # Create a focused query for this agent
            agent_prompt = (
                f"As the {self.name}, help with: {state.get('current_query', '')}"
            )

            # If auto_approve_plan is set, add instruction to not ask follow-up questions
            if state.get("auto_approve_plan", False):
                agent_prompt += "\n\nIMPORTANT: Provide a complete, actionable response without asking any follow-up questions. Do not ask if the user wants more details or if they would like you to investigate further."

            # We'll collect all messages and the final response
            all_messages = []
            agent_response = ""

            # Initialize conversation memory manager for automatic message tracking
            conversation_manager = None
            user_id = state.get("user_id")
            if user_id:
                try:
                    # Get region from llm_kwargs if available
                    region = self.llm_kwargs.get("region_name", "us-east-1") if self.llm_provider == "bedrock" else "us-east-1"
                    memory_client = SREMemoryClient(region=region)
                    conversation_manager = create_conversation_memory_manager(
                        memory_client
                    )
                    logger.info(
                        f"{self.name} - ユーザー {user_id} の会話メモリマネージャーを初期化しました"
                    )
                except Exception as e:
                    logger.warning(
                        f"{self.name} - 会話メモリマネージャーの初期化に失敗しました: {e}"
                    )
            else:
                logger.info(
                    f"{self.name} - state に user_id が見つかりません、会話メモリをスキップします"
                )

            # Add system prompt and user prompt
            system_message = SystemMessage(content=self._get_system_prompt())
            user_message = HumanMessage(content=agent_prompt)

            # タイムアウト付きでエージェント実行をストリーミングしてツール呼び出しをキャプチャ
            logger.info(f"{self.name} - エージェント実行を開始")

            try:
                # Add timeout to prevent infinite hanging (120 seconds)
                timeout_seconds = 120

                async def execute_agent():
                    nonlocal agent_response  # スコープの問題を修正 - 外部変数へのアクセスを許可
                    chunk_count = 0
                    logger.info(
                        f"{self.name} - エージェントを実行中: {[system_message] + messages + [user_message]}"
                    )
                    async for chunk in self.agent.astream(
                        {"messages": [system_message] + messages + [user_message]}
                    ):
                        chunk_count += 1
                        logger.info(
                            f"{self.name} - チャンク #{chunk_count} を処理中: {list(chunk.keys())}"
                        )

                        if "agent" in chunk:
                            agent_step = chunk["agent"]
                            if "messages" in agent_step:
                                for msg in agent_step["messages"]:
                                    all_messages.append(msg)
                                    # 実行中のツール呼び出しをログ
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        logger.info(
                                            f"{self.name} - エージェントが {len(msg.tool_calls)} 個のツール呼び出しを実行中"
                                        )
                                        for tc in msg.tool_calls:
                                            tool_name = tc.get("name", "unknown")
                                            tool_args = tc.get("args", {})
                                            tool_id = tc.get("id", "unknown")
                                            logger.info(
                                                f"{self.name} - ツール呼び出し: {tool_name} (id: {tool_id})"
                                            )
                                            logger.debug(
                                                f"{self.name} - ツール引数: {tool_args}"
                                            )
                                    # Always capture the latest content from AIMessages
                                    if (
                                        hasattr(msg, "content")
                                        and hasattr(msg, "__class__")
                                        and "AIMessage" in str(msg.__class__)
                                    ):
                                        agent_response = msg.content
                                        logger.info(
                                            f"{self.name} - エージェントレスポンスをキャプチャ: {agent_response[:100]}... (合計: {len(str(agent_response))} 文字)"
                                        )

                        elif "tools" in chunk:
                            tools_step = chunk["tools"]
                            logger.info(
                                f"{self.name} - ツールチャンクを受信、{len(tools_step.get('messages', []))} 件のメッセージを処理中"
                            )
                            if "messages" in tools_step:
                                for msg in tools_step["messages"]:
                                    all_messages.append(msg)
                                    # Log tool executions
                                    if hasattr(msg, "tool_call_id"):
                                        tool_name = getattr(msg, "name", "unknown")
                                        tool_call_id = getattr(
                                            msg, "tool_call_id", "unknown"
                                        )
                                        content_preview = (
                                            str(msg.content)[:200]
                                            if hasattr(msg, "content")
                                            else "No content"
                                        )
                                        logger.info(
                                            f"{self.name} - ツールレスポンスを受信: {tool_name} (id: {tool_call_id}), 内容: {content_preview}..."
                                        )
                                        logger.debug(
                                            f"{self.name} - 完全なツールレスポンス: {msg.content if hasattr(msg, 'content') else 'コンテンツなし'}"
                                        )

                logger.info(
                    f"{self.name} - タイムアウト {timeout_seconds} 秒でエージェントを実行中"
                )
                await asyncio.wait_for(execute_agent(), timeout=timeout_seconds)
                logger.info(f"{self.name} - エージェント実行が完了しました")

            except asyncio.TimeoutError:
                logger.error(
                    f"{self.name} - エージェント実行が {timeout_seconds} 秒後にタイムアウトしました"
                )
                agent_response = f"エージェント実行が {timeout_seconds} 秒後にタイムアウトしました。エージェントがツール呼び出しまたは LLM レスポンスでスタックしている可能性があります。"

            except Exception as e:
                logger.error(f"{self.name} - エージェント実行が失敗しました: {e}")
                logger.exception("完全な例外の詳細:")
                agent_response = f"エージェント実行が失敗しました: {str(e)}"

            # デバッグ: キャプチャした内容を確認
            logger.info(
                f"{self.name} - キャプチャしたレスポンスの長さ: {len(agent_response) if agent_response else 0}"
            )
            if agent_response:
                logger.info(f"{self.name} - 完全なレスポンス: {str(agent_response)}")

            # Store conversation messages in memory after agent response
            if conversation_manager and user_id and agent_response:
                try:
                    # Store the user query and agent response as conversation messages
                    messages_to_store = [
                        (agent_prompt, "USER"),
                        (
                            f"[Agent: {self.name}]\n{agent_response}",
                            "ASSISTANT",
                        ),  # Include agent name in message content
                    ]

                    # Also capture tool execution results as TOOL messages
                    tool_names = []
                    for msg in all_messages:
                        if hasattr(msg, "tool_call_id") and hasattr(msg, "content"):
                            tool_content = str(msg.content)[
                                :500
                            ]  # Limit tool message length
                            tool_name = getattr(msg, "name", "unknown")
                            tool_names.append(tool_name)
                            messages_to_store.append(
                                (
                                    f"[Agent: {self.name}] [Tool: {tool_name}]\n{tool_content}",
                                    "TOOL",
                                )
                            )

                    # Count message types
                    user_count = len([m for m in messages_to_store if m[1] == "USER"])
                    assistant_count = len(
                        [m for m in messages_to_store if m[1] == "ASSISTANT"]
                    )
                    tool_count = len([m for m in messages_to_store if m[1] == "TOOL"])

                    # 保存前にメッセージの内訳をログ
                    logger.info(
                        f"{self.name} - メッセージ内訳: {user_count} USER, {assistant_count} ASSISTANT, {tool_count} TOOL メッセージ"
                    )
                    if tool_names:
                        logger.info(
                            f"{self.name} - 呼び出されたツール: {', '.join(tool_names)}"
                        )
                    else:
                        logger.info(f"{self.name} - ツール呼び出しなし")

                    # Store the conversation batch
                    success = conversation_manager.store_conversation_batch(
                        messages=messages_to_store,
                        user_id=user_id,
                        session_id=state.get("session_id"),  # Use session_id from state
                        agent_name=self.name,
                    )

                    if success:
                        logger.info(
                            f"{self.name} - {len(messages_to_store)} 件の会話メッセージを正常に保存しました"
                        )
                    else:
                        logger.warning(
                            f"{self.name} - 会話メッセージの保存に失敗しました"
                        )

                except Exception as e:
                    logger.error(
                        f"{self.name} - 会話メッセージの保存中にエラーが発生しました: {e}",
                        exc_info=True,
                    )

            # Process agent response for pattern extraction and memory capture
            if user_id and agent_response:
                try:
                    # Check if memory hooks are available through the memory client
                    from .memory.hooks import MemoryHookProvider

                    # Use the SREMemoryClient that's already imported at the top
                    # Get region from llm_kwargs if available
                    region = self.llm_kwargs.get("region_name", "us-east-1") if self.llm_provider == "bedrock" else "us-east-1"
                    memory_client = SREMemoryClient(region=region)
                    memory_hooks = MemoryHookProvider(memory_client)

                    # Create response object for hooks
                    response_obj = {
                        "content": agent_response,
                        "tool_calls": [
                            {
                                "name": getattr(msg, "name", "unknown"),
                                "content": str(getattr(msg, "content", "")),
                            }
                            for msg in all_messages
                            if hasattr(msg, "tool_call_id")
                        ],
                    }

                    # Call on_agent_response hook to extract patterns
                    memory_hooks.on_agent_response(
                        agent_name=self.name, response=response_obj, state=state
                    )

                    logger.info(
                        f"{self.name} - メモリパターン抽出用にエージェントレスポンスを処理しました"
                    )

                except Exception as e:
                    logger.warning(
                        f"{self.name} - メモリパターンのエージェントレスポンス処理に失敗しました: {e}"
                    )

            # Update state with streaming info
            return {
                "agent_results": {
                    **state.get("agent_results", {}),
                    self.name: agent_response,
                },
                "agents_invoked": state.get("agents_invoked", []) + [self.name],
                "messages": messages + all_messages,
                "metadata": {
                    **state.get("metadata", {}),
                    f"{self.name.replace(' ', '_')}_trace": all_messages,
                },
            }

        except Exception as e:
            logger.error(f"{self.name} でエラーが発生しました: {e}")
            return {
                "agent_results": {
                    **state.get("agent_results", {}),
                    self.name: f"Error: {str(e)}",
                },
                "agents_invoked": state.get("agents_invoked", []) + [self.name],
            }


def create_kubernetes_agent(
    tools: List[BaseTool], agent_metadata: AgentMetadata = None, **kwargs
) -> BaseAgentNode:
    """Kubernetes インフラストラクチャエージェントを作成します。"""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "kubernetes_agent", config)

    return BaseAgentNode(
        name="Kubernetes Infrastructure Agent",  # Fallback for backward compatibility
        description="Manages Kubernetes cluster operations and monitoring",  # Fallback
        tools=filtered_tools,
        agent_metadata=agent_metadata,
        **kwargs,
    )


def create_logs_agent(
    tools: List[BaseTool], agent_metadata: AgentMetadata = None, **kwargs
) -> BaseAgentNode:
    """アプリケーションログエージェントを作成します。"""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "logs_agent", config)

    return BaseAgentNode(
        name="Application Logs Agent",  # Fallback for backward compatibility
        description="Handles application log analysis and searching",  # Fallback
        tools=filtered_tools,
        agent_metadata=agent_metadata,
        **kwargs,
    )


def create_metrics_agent(
    tools: List[BaseTool], agent_metadata: AgentMetadata = None, **kwargs
) -> BaseAgentNode:
    """パフォーマンスメトリクスエージェントを作成します。"""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "metrics_agent", config)

    return BaseAgentNode(
        name="Performance Metrics Agent",  # Fallback for backward compatibility
        description="Provides application performance and resource metrics",  # Fallback
        tools=filtered_tools,
        agent_metadata=agent_metadata,
        **kwargs,
    )


def create_runbooks_agent(
    tools: List[BaseTool], agent_metadata: AgentMetadata = None, **kwargs
) -> BaseAgentNode:
    """運用ランブックエージェントを作成します。"""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "runbooks_agent", config)

    return BaseAgentNode(
        name="Operational Runbooks Agent",  # Fallback for backward compatibility
        description="Provides operational procedures and troubleshooting guides",  # Fallback
        tools=filtered_tools,
        agent_metadata=agent_metadata,
        **kwargs,
    )
