from .agent import CustomerSupport
from contextvars import ContextVar
from typing import Optional
import asyncio


class CustomerSupportContext:
    """カスタマーサポートアシスタント用コンテキストマネージャー"""

    # エージェント呼び出しをまたいで保持されるトークンのグローバル状態
    _google_token: Optional[str] = None
    _gateway_token: Optional[str] = None
    _response_queue: Optional[asyncio.Queue] = None
    _agent: Optional[CustomerSupport] = None
    
    # アプリケーション状態用のコンテキスト変数
    _google_token_ctx: ContextVar[Optional[str]] = ContextVar(
        "google_token", default=None
    )
    _gateway_token_ctx: ContextVar[Optional[str]] = ContextVar(
        "gateway_token", default=None
    )
    _response_queue_ctx: ContextVar[Optional[asyncio.Queue]] = ContextVar(
        "response_queue", default=None
    )
    _agent_ctx: ContextVar[Optional[CustomerSupport]] = ContextVar(
        "agent", default=None
    )

    @classmethod
    def get_google_token_ctx(
        cls,
    ) -> Optional[str]:
        # まずグローバル状態から取得を試み、呼び出し間の永続性を確保
        if cls._google_token:
            return cls._google_token
        try:
            return cls._google_token_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_google_token_ctx(cls, token: str) -> None:
        # グローバル状態とコンテキスト変数の両方を設定
        cls._google_token = token
        cls._google_token_ctx.set(token)

    @classmethod
    def get_response_queue_ctx(
        cls,
    ) -> Optional[asyncio.Queue]:
        # まずグローバル状態から取得を試み、呼び出し間の永続性を確保
        if cls._response_queue:
            return cls._response_queue
        try:
            return cls._response_queue_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_response_queue_ctx(cls, queue: asyncio.Queue) -> None:
        # グローバル状態とコンテキスト変数の両方を設定
        cls._response_queue = queue
        cls._response_queue_ctx.set(queue)

    @classmethod
    def get_gateway_token_ctx(
        cls,
    ) -> Optional[str]:
        # まずグローバル状態から取得を試み、呼び出し間の永続性を確保
        if cls._gateway_token:
            return cls._gateway_token
        try:
            return cls._gateway_token_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_gateway_token_ctx(cls, token: str) -> None:
        # グローバル状態とコンテキスト変数の両方を設定
        cls._gateway_token = token
        cls._gateway_token_ctx.set(token)

    @classmethod
    def get_agent_ctx(
        cls,
    ) -> Optional[CustomerSupport]:
        # まずグローバル状態から取得を試み、呼び出し間の永続性を確保
        if cls._agent:
            return cls._agent
        try:
            return cls._agent_ctx.get()
        except LookupError:
            return None

    @classmethod
    def set_agent_ctx(cls, agent: CustomerSupport) -> None:
        # グローバル状態とコンテキスト変数の両方を設定
        cls._agent = agent
        cls._agent_ctx.set(agent)
