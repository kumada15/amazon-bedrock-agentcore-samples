#!/usr/bin/env python3

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from .agent_state import AgentState
from .constants import SREConstants

# Import logging config
from .logging_config import configure_logging
from .multi_agent_langgraph import create_multi_agent_system

# Configure logging based on DEBUG environment variable
# This ensures debug mode works even when not run via __main__
if not logging.getLogger().handlers:
    # Check if DEBUG is already set in environment
    debug_from_env = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    configure_logging(debug_from_env)


# Custom filter to exclude /ping endpoint logs
class PingEndpointFilter(logging.Filter):
    def filter(self, record):
        # Filter out GET /ping requests from access logs
        if hasattr(record, "getMessage"):
            message = record.getMessage()
            if '"GET /ping HTTP/' in message:
                return False
        return True


# Configure uvicorn access logger to filter out ping requests
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(PingEndpointFilter())

logger = logging.getLogger(__name__)

# Simple FastAPI app
app = FastAPI(title="SRE Agent Runtime", version="1.0.0")


# Simple request/response models
class InvocationRequest(BaseModel):
    input: Dict[str, Any]


class InvocationResponse(BaseModel):
    output: Dict[str, Any]


# Global variables for agent state
agent_graph = None
tools: list[BaseTool] = []


async def initialize_agent():
    """CLI と同じ方法で SRE エージェントシステムを初期化します。"""
    global agent_graph, tools

    if agent_graph is not None:
        return  # Already initialized

    try:
        logger.info("SRE エージェントシステムを初期化中...")

        # Get provider from environment variable with bedrock as default
        provider = os.getenv("LLM_PROVIDER", "bedrock").lower()

        # Validate provider
        if provider not in ["anthropic", "bedrock"]:
            logger.warning(f"無効なプロバイダー '{provider}'、'bedrock' にデフォルト設定します")
            provider = "bedrock"

        logger.info(f"環境変数 LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'NOT_SET')}")
        logger.info(f"LLM プロバイダーを使用: {provider}")
        logger.info(f"プロバイダー {provider} で create_multi_agent_system を呼び出し中")

        # Create multi-agent system using the same function as CLI
        agent_graph, tools = await create_multi_agent_system(provider)

        logger.info(
            f"SRE エージェントシステムが {len(tools)} 個のツールで正常に初期化されました"
        )

    except Exception as e:
        from .llm_utils import LLMAccessError, LLMAuthenticationError, LLMProviderError

        if isinstance(e, (LLMAuthenticationError, LLMAccessError, LLMProviderError)):
            logger.error(f"LLM プロバイダーエラー: {e}")
            print(f"\n❌ {type(e).__name__}:")
            print(str(e))
            print("\n💡 LLM_PROVIDER 環境変数を設定してプロバイダーを切り替えてください:")
            other_provider = "anthropic" if provider == "bedrock" else "bedrock"
            print(f"   export LLM_PROVIDER={other_provider}")
        else:
            logger.error(f"SRE エージェントシステムの初期化に失敗しました: {e}")
        raise


@app.on_event("startup")
async def startup_event():
    """起動時にエージェントを初期化します。"""
    await initialize_agent()


@app.post("/invocations", response_model=InvocationResponse)
async def invoke_agent(request: InvocationRequest):
    """メインのエージェント呼び出しエンドポイント。"""
    global agent_graph, tools

    logger.info("呼び出しリクエストを受信しました")

    try:
        # Ensure agent is initialized
        await initialize_agent()

        # Extract user prompt
        user_prompt = request.input.get("prompt", "")
        if not user_prompt:
            raise HTTPException(
                status_code=400,
                detail="No prompt found in input. Please provide a 'prompt' key in the input.",
            )

        logger.info(f"クエリを処理中: {user_prompt}")

        # Extract session_id and user_id from request
        session_id = request.input.get("session_id", "")
        user_id = request.input.get("user_id", "default_user")

        logger.info(f"セッション ID: {session_id}, ユーザー ID: {user_id}")

        # Create initial state exactly like the CLI does
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_prompt)],
            "next": "supervisor",
            "agent_results": {},
            "current_query": user_prompt,
            "metadata": {},
            "requires_collaboration": False,
            "agents_invoked": [],
            "final_response": None,
            "auto_approve_plan": True,  # Always auto-approve plans in runtime mode
            "session_id": session_id,  # Required for memory retrieval
            "user_id": user_id,  # Required for user personalization
        }

        # Process through the agent graph exactly like the CLI
        final_response = ""

        logger.info("エージェントグラフの実行を開始")

        async for event in agent_graph.astream(initial_state):
            for node_name, node_output in event.items():
                logger.info(f"ノードを処理中: {node_name}")

                # Log key events from each node
                if node_name == "supervisor":
                    next_agent = node_output.get("next", "")
                    metadata = node_output.get("metadata", {})
                    logger.info(f"Supervisor が {next_agent} にルーティング中")
                    if metadata.get("routing_reasoning"):
                        logger.info(
                            f"ルーティングの理由: {metadata['routing_reasoning']}"
                        )

                elif node_name in [
                    "kubernetes_agent",
                    "logs_agent",
                    "metrics_agent",
                    "runbooks_agent",
                ]:
                    agent_results = node_output.get("agent_results", {})
                    logger.info(f"{node_name} が結果を返して完了しました")

                # Capture final response from aggregate node
                elif node_name == "aggregate":
                    final_response = node_output.get("final_response", "")
                    logger.info("集約ノードが完了し、最終レスポンスをキャプチャしました")

        if not final_response:
            logger.warning("エージェントグラフから最終レスポンスを受信できませんでした")
            final_response = (
                "リクエストの処理中に問題が発生しました。もう一度お試しください。"
            )
        else:
            logger.info(f"最終レスポンスの長さ: {len(final_response)} 文字")

        # Simple response format
        response_data = {
            "message": final_response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": SREConstants.app.agent_model_name,
        }

        logger.info("エージェントリクエストを正常に処理しました")
        logger.info("呼び出しレスポンスを返しています")
        return InvocationResponse(output=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"エージェント処理が失敗しました: {e}")
        logger.exception("完全な例外の詳細:")
        raise HTTPException(
            status_code=500, detail=f"Agent processing failed: {str(e)}"
        )


@app.get("/ping")
async def ping():
    """ヘルスチェックエンドポイント。"""
    return {"status": "healthy"}


async def invoke_sre_agent_async(prompt: str, provider: str = "anthropic") -> str:
    """
    SRE エージェントを呼び出すためのプログラマティックインターフェース。

    Args:
        prompt: ユーザーのプロンプト/クエリ
        provider: LLM プロバイダー（"anthropic" または "bedrock"）

    Returns:
        エージェントのレスポンス（文字列）
    """
    try:
        # Create the multi-agent system
        graph, tools = await create_multi_agent_system(provider=provider)

        # Create initial state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=prompt)],
            "next": "supervisor",
            "agent_results": {},
            "current_query": prompt,
            "metadata": {},
            "requires_collaboration": False,
            "agents_invoked": [],
            "final_response": None,
        }

        # Execute and get final response
        final_response = ""
        async for event in graph.astream(initial_state):
            for node_name, node_output in event.items():
                if node_name == "aggregate":
                    final_response = node_output.get("final_response", "")

        return final_response or "リクエストの処理中に問題が発生しました。"

    except Exception as e:
        logger.error(f"エージェント呼び出しが失敗しました: {e}")
        raise


def invoke_sre_agent(prompt: str, provider: str = "anthropic") -> str:
    """
    invoke_sre_agent_async の同期ラッパー。

    Args:
        prompt: ユーザーのプロンプト/クエリ
        provider: LLM プロバイダー（"anthropic" または "bedrock"）

    Returns:
        エージェントのレスポンス（文字列）
    """
    return asyncio.run(invoke_sre_agent_async(prompt, provider))


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="SRE Agent Runtime")
    parser.add_argument(
        "--provider",
        choices=["anthropic", "bedrock"],
        default=os.getenv("LLM_PROVIDER", "bedrock"),
        help="LLM provider to use (default: bedrock)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and trace output",
    )

    args = parser.parse_args()

    # Configure logging based on debug flag
    from .logging_config import configure_logging

    debug_enabled = configure_logging(args.debug)

    # Set environment variables
    os.environ["LLM_PROVIDER"] = args.provider
    os.environ["DEBUG"] = "true" if debug_enabled else "false"

    logger.info(f"プロバイダー {args.provider} で SRE エージェント Runtime を起動中")
    if debug_enabled:
        logger.info("デバッグログが有効になりました")
    uvicorn.run(app, host=args.host, port=args.port)
