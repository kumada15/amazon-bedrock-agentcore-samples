#!/usr/bin/env python3

import logging
from typing import Any, Dict, List, Literal

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph

from .agent_nodes import (
    create_kubernetes_agent,
    create_logs_agent,
    create_metrics_agent,
    create_runbooks_agent,
)
from .agent_state import AgentState
from .constants import SREConstants
from .supervisor import SupervisorAgent

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _should_continue(state: AgentState) -> Literal["supervisor", "FINISH"]:
    """続行するか終了するかを決定します。"""
    next_agent = state.get("next", "FINISH")

    if next_agent == "FINISH":
        return "FINISH"

    # 既にこのエージェントを呼び出したかどうかを確認（ループを回避）
    agents_invoked = state.get("agents_invoked", [])
    if next_agent in agents_invoked and not state.get("requires_collaboration", False):
        logger.warning(f"エージェント {next_agent} は既に呼び出されています、ループを回避して終了します")
        return "FINISH"

    return "supervisor"


def _route_supervisor(state: AgentState) -> str:
    """スーパーバイザーから適切なエージェントへルーティングするか、終了します。"""
    next_agent = state.get("next", "FINISH")

    if next_agent == "FINISH":
        return "aggregate"

    # Map to actual node names - handle both old short names and new full names
    agent_map = {
        "kubernetes": "kubernetes_agent",
        "logs": "logs_agent",
        "metrics": "metrics_agent",
        "runbooks": "runbooks_agent",
        # Also handle the new full names directly
        "kubernetes_agent": "kubernetes_agent",
        "logs_agent": "logs_agent",
        "metrics_agent": "metrics_agent",
        "runbooks_agent": "runbooks_agent",
    }

    return agent_map.get(next_agent, "aggregate")


async def _prepare_initial_state(state: AgentState) -> Dict[str, Any]:
    """ユーザーのクエリで初期状態を準備します。"""
    messages = state.get("messages", [])

    # Extract the current query from the last human message
    current_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            current_query = msg.content
            break

    return {
        "current_query": current_query,
        "agent_results": {},
        "agents_invoked": [],
        "requires_collaboration": False,
        "metadata": {},
    }


def build_multi_agent_graph(
    tools: List[BaseTool],
    llm_provider: str = "bedrock",
    force_delete_memory: bool = False,
    export_graph: bool = False,
    graph_output_path: str = "./docs/sre_agent_architecture.md",
    **llm_kwargs,
) -> StateGraph:
    """マルチエージェント協調グラフを構築します。

    Args:
        tools: 利用可能なすべてのツールのリスト
        llm_provider: 使用する LLM プロバイダー
        force_delete_memory: 既存のメモリを強制削除するかどうか
        export_graph: グラフを Mermaid ダイアグラムとしてエクスポートするかどうか
        graph_output_path: エクスポートされた Mermaid ダイアグラムの保存パス（デフォルト: ./docs/sre_agent_architecture.md）
        **llm_kwargs: LLM 用の追加引数

    Returns:
        マルチエージェント協調用のコンパイル済み StateGraph
    """
    logger.info("マルチエージェント協調グラフを構築中")

    # Create the state graph
    workflow = StateGraph(AgentState)

    # Create supervisor
    supervisor = SupervisorAgent(
        llm_provider=llm_provider, force_delete_memory=force_delete_memory, **llm_kwargs
    )

    # Create agent nodes with filtered tools and metadata from constants
    kubernetes_agent = create_kubernetes_agent(
        tools,
        agent_metadata=SREConstants.agents.agents["kubernetes"],
        llm_provider=llm_provider,
        **llm_kwargs,
    )
    logs_agent = create_logs_agent(
        tools,
        agent_metadata=SREConstants.agents.agents["logs"],
        llm_provider=llm_provider,
        **llm_kwargs,
    )
    metrics_agent = create_metrics_agent(
        tools,
        agent_metadata=SREConstants.agents.agents["metrics"],
        llm_provider=llm_provider,
        **llm_kwargs,
    )
    runbooks_agent = create_runbooks_agent(
        tools,
        agent_metadata=SREConstants.agents.agents["runbooks"],
        llm_provider=llm_provider,
        **llm_kwargs,
    )

    # Add nodes to the graph
    workflow.add_node("prepare", _prepare_initial_state)
    workflow.add_node("supervisor", supervisor.route)
    workflow.add_node("kubernetes_agent", kubernetes_agent)
    workflow.add_node("logs_agent", logs_agent)
    workflow.add_node("metrics_agent", metrics_agent)
    workflow.add_node("runbooks_agent", runbooks_agent)
    workflow.add_node("aggregate", supervisor.aggregate_responses)

    # Set entry point
    workflow.set_entry_point("prepare")

    # Add edges from prepare to supervisor
    workflow.add_edge("prepare", "supervisor")

    # Add conditional edges from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        _route_supervisor,
        {
            "kubernetes_agent": "kubernetes_agent",
            "logs_agent": "logs_agent",
            "metrics_agent": "metrics_agent",
            "runbooks_agent": "runbooks_agent",
            "aggregate": "aggregate",
        },
    )

    # Add edges from agents back to supervisor
    workflow.add_edge("kubernetes_agent", "supervisor")
    workflow.add_edge("logs_agent", "supervisor")
    workflow.add_edge("metrics_agent", "supervisor")
    workflow.add_edge("runbooks_agent", "supervisor")

    # Add edge from aggregate to END
    workflow.add_edge("aggregate", END)

    # Compile the graph
    compiled_graph = workflow.compile()

    # Export graph visualization if requested
    if export_graph:
        try:
            # Create docs directory if it doesn't exist
            from pathlib import Path
            output_path = Path(graph_output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get the Mermaid representation of the graph
            mermaid_diagram = compiled_graph.get_graph().draw_mermaid()
            
            # Save to file
            with open(graph_output_path, "w") as f:
                f.write("# SRE Agent Architecture\n\n")
                f.write("```mermaid\n")
                f.write(mermaid_diagram)
                f.write("\n```\n")
            
            logger.info(f"グラフアーキテクチャ（Mermaid）をエクスポートしました: {graph_output_path}")
            print(f"✅ グラフアーキテクチャ（Mermaid ダイアグラム）をエクスポートしました: {graph_output_path}")
        except Exception as e:
            logger.error(f"グラフのエクスポートに失敗しました: {e}")
            print(f"❌ グラフのエクスポートに失敗しました: {e}")

    logger.info("マルチエージェント協調グラフが正常に構築されました")
    return compiled_graph
