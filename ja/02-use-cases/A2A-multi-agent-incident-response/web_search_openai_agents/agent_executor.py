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
from agent import _call_agent_stream, create_agent
from openai.types.responses import ResponseTextDeltaEvent
import logging

logger = logging.getLogger(__name__)


class WebSearchAgentExecutor(AgentExecutor):
    """
    OpenAI ベースの Web 検索エージェントをラップする Agent Executor
    A2A サーバー互換性のため
    """

    def __init__(self):
        """Executor を初期化する"""
        self._agent = None
        self._active_tasks = {}
        logger.info("WebSearchAgentExecutor を初期化しました")

    async def _get_agent(self, session_id: str, actor_id: str):
        """エージェントを遅延初期化して返す"""
        if self._agent is None:
            logger.info("Web 検索エージェントを作成中...")
            self._agent = create_agent(session_id=session_id, actor_id=actor_id)
            logger.info("Web 検索エージェントを正常に作成しました")
        return self._agent

    async def _execute_streaming(
        self, agent, user_message: str, updater: TaskUpdater, task_id: str
    ) -> None:
        """ストリーミングでエージェントを実行し、タスクステータスを段階的に更新する。"""
        accumulated_text = ""

        try:
            async for stream_event in _call_agent_stream(agent, user_message):
                # タスクがキャンセルされたかどうかを確認
                if not self._active_tasks.get(task_id, False):
                    logger.info(f"タスク {task_id} はストリーミング中にキャンセルされました")
                    return

                # エラーイベントを処理
                if "error" in stream_event:
                    error_msg = stream_event["error"]
                    logger.error(f"ストリームでエラー: {error_msg}")
                    raise Exception(error_msg)

                # ストリーミングイベントを処理
                if "event" in stream_event:
                    event = stream_event["event"]
                    event_type = getattr(event, "type", None)
                    logger.info(f"ストリームイベントタイプ: {event_type}")

                    # ResponseTextDeltaEvent を含む raw_response_event のみを処理
                    if event_type == "raw_response_event" and isinstance(
                        event.data, ResponseTextDeltaEvent
                    ):
                        text_chunk = event.data.delta
                        if text_chunk:
                            accumulated_text += text_chunk
                            logger.debug(f"テキストデルタ: {text_chunk}")
                            # インクリメンタル更新を送信
                            await updater.update_status(
                                TaskState.working,
                                new_agent_text_message(
                                    accumulated_text,
                                    updater.context_id,
                                    updater.task_id,
                                ),
                            )

                    # デバッグ用に他のイベントタイプをログに記録するが、処理はしない
                    else:
                        logger.debug(f"イベントタイプを無視: {event_type}")

            # 最終結果をアーティファクトとして追加
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
        # ヘッダーからセッション ID とアクター ID を抽出
        session_id = None

        if context.call_context:
            headers = context.call_context.state.get("headers", {})
            session_id = headers.get("x-amzn-bedrock-agentcore-runtime-session-id")
            actor_id = headers.get("x-amzn-bedrock-agentcore-runtime-custom-actorid")
        if not actor_id:
            logger.error("セッション ID が設定されていません")
            raise Exception(error=InvalidParamsError())

        if not session_id:
            logger.error("アクター ID が設定されていません")
            raise ServerError(error=InvalidParamsError())

        # タスクを取得または作成
        task = context.current_task
        if not task:
            logger.info("現在のタスクがありません、新しいタスクを作成します")
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        task_id = context.task_id

        try:
            logger.info(f"タスク {task.id} を実行中")

            # ユーザー入力を抽出
            user_message = context.get_user_input()
            if not user_message:
                logger.error("コンテキスト内にユーザーメッセージが見つかりません")
                raise ServerError(error=InvalidParamsError())

            logger.info(f"ユーザーメッセージ: '{user_message}'")

            # エージェントインスタンスを取得
            agent = await self._get_agent(session_id=session_id, actor_id=actor_id)

            # タスクをアクティブとしてマーク
            self._active_tasks[task_id] = True

            # エージェントのレスポンスをストリーミング
            logger.info("ストリーミングでエージェントを呼び出し中...")
            await self._execute_streaming(agent, user_message, updater, task_id)

            logger.info(f"タスク {task_id} が正常に完了しました")

        except ServerError:
            # ServerError はそのまま再スロー
            raise
        except Exception as e:
            logger.error(f"タスク {task_id} の実行でエラー: {e}", exc_info=True)
            raise ServerError(error=InternalError()) from e
        finally:
            # アクティブタスクからタスクをクリーンアップ
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
            # タスクをキャンセル済みとしてマーク
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
