from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
import logging
import os
from agent import MonitoringAgent

logger = logging.getLogger(__name__)


class MonitoringAgentExecutor(AgentExecutor):
    """
    Strands ベースの監視エージェント用の Agent Executor
    """

    def __init__(self):
        """Executor を初期化する"""
        self._agent = None
        self._active_tasks = {}
        logger.info("MonitoringAgentExecutor を初期化しました")

    async def _get_agent(self, session_id: str, actor_id: str, workload_token: str):
        """エージェントインスタンスを取得または作成する"""
        if self._agent is None:
            logger.info("監視エージェントを作成中...")

            # Get configuration from environment
            memory_id = os.getenv("MEMORY_ID")
            model_id = os.getenv(
                "MODEL_ID", "global.anthropic.claude-sonnet-4-20250514-v1:0"
            )
            region_name = os.getenv("MCP_REGION")

            if not memory_id or not region_name:
                raise RuntimeError(
                    "Missing required environment variables: MEMORY_ID or MCP_REGION"
                )

            # Create agent instance
            self._agent = MonitoringAgent(
                memory_id=memory_id,
                model_id=model_id,
                region_name=region_name,
                actor_id=actor_id,
                session_id=session_id,
                workload_token=workload_token,
            )
            logger.info("監視エージェントを正常に作成しました")

        return self._agent

    async def _execute_streaming(
        self,
        agent,
        user_message: str,
        updater: TaskUpdater,
        task_id: str,
        session_id: str,
    ) -> None:
        """ストリーミングでエージェントを実行し、タスクステータスを段階的に更新する。"""
        accumulated_text = ""

        try:
            # Use the agent's stream method
            async for event in agent.stream(user_message, session_id):
                # Check if task was cancelled
                if not self._active_tasks.get(task_id, False):
                    logger.info(f"タスク {task_id} はストリーミング中にキャンセルされました")
                    return

                # Handle error events
                if "error" in event:
                    error_msg = event.get("content", "Unknown error")
                    logger.error(f"ストリームでエラー: {error_msg}")
                    raise Exception(error_msg)

                # Stream content updates
                content = event.get("content", "")
                if content and not event.get("is_task_complete", False):
                    accumulated_text += content
                    # Send incremental update
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            accumulated_text,
                            updater.context_id,
                            updater.task_id,
                        ),
                    )

            # Add final result as artifact
            if accumulated_text:
                await updater.add_artifact(
                    [Part(root=TextPart(text=accumulated_text))],
                    name="agent_response",
                )

            await updater.complete()

        except Exception as e:
            logger.error(f"ストリーミング実行でエラー: {e}", exc_info=True)
            raise

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        指定されたリクエストコンテキストに対してエージェントのロジックを実行する。
        """
        # Extract required headers
        session_id = None
        actor_id = None
        workload_token = None

        if context.call_context:
            headers = context.call_context.state.get("headers", {})
            session_id = headers.get("x-amzn-bedrock-agentcore-runtime-session-id")
            actor_id = headers.get("x-amzn-bedrock-agentcore-runtime-custom-actorid")
            workload_token = headers.get(
                "x-amzn-bedrock-agentcore-runtime-workload-accesstoken"
            )

        if not actor_id:
            logger.error("アクター ID が設定されていません")
            raise ServerError(error=InvalidParamsError())

        if not session_id:
            logger.error("セッション ID が設定されていません")
            raise ServerError(error=InvalidParamsError())

        if not workload_token:
            logger.error("ワークロードトークンが設定されていません")
            raise ServerError(error=InvalidParamsError())

        # Get or create task
        task = context.current_task
        if not task:
            logger.info("現在のタスクがありません、新しいタスクを作成します")
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        task_id = context.task_id

        try:
            logger.info(f"タスク {task.id} を実行中")

            # Extract user input
            user_message = context.get_user_input()
            if not user_message:
                logger.error("コンテキスト内にユーザーメッセージが見つかりません")
                raise ServerError(error=InvalidParamsError())

            logger.info(f"ユーザーメッセージ: '{user_message}'")

            # Get the agent instance
            agent = await self._get_agent(session_id, actor_id, workload_token)

            # Mark task as active
            self._active_tasks[task_id] = True

            # Execute the agent
            logger.info("エージェントを呼び出し中...")
            await self._execute_streaming(
                agent, user_message, updater, task_id, session_id
            )

            logger.info(f"タスク {task_id} が正常に完了しました")

        except ServerError:
            # Re-raise ServerError as-is
            raise
        except Exception as e:
            logger.error(f"タスク {task_id} の実行でエラー: {e}", exc_info=True)
            raise ServerError(error=InternalError()) from e
        finally:
            # Clean up task from active tasks
            self._active_tasks.pop(task_id, None)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        進行中のタスクのキャンセルをエージェントにリクエストする。
        """
        task_id = context.task_id
        logger.info(f"タスク {task_id} をキャンセル中")

        try:
            # Mark task as cancelled
            self._active_tasks[task_id] = False

            task = context.current_task
            if task:
                updater = TaskUpdater(event_queue, task.id, task.context_id)
                await updater.cancel()
                logger.info(f"タスク {task_id} のキャンセルに成功しました")
            else:
                logger.warning(f"task_id {task_id} のタスクが見つかりません")

        except Exception as e:
            logger.error(f"タスク {task_id} のキャンセルでエラー: {e}", exc_info=True)
            raise ServerError(error=InternalError()) from e
