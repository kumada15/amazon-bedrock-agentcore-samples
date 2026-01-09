"""
AWS SigV4 署名付き StreamableHTTP クライアントトランスポート

このモジュールは MCP StreamableHTTPTransport を拡張し、AWS IAM で認証する
MCP サーバーとの認証用に AWS SigV4 リクエスト署名を追加します。
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Generator

import httpx
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from mcp.client.streamable_http import (
    GetSessionIdCallback,
    StreamableHTTPTransport,
    streamablehttp_client,
)
from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from mcp.shared.message import SessionMessage


class SigV4HTTPXAuth(httpx.Auth):
    """AWS SigV4 でリクエストに署名する HTTPX Auth クラス"""

    def __init__(
        self,
        credentials: Credentials,
        service: str,
        region: str,
    ):
        self.credentials = credentials
        self.service = service
        self.region = region
        self.signer = SigV4Auth(credentials, service, region)

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """リクエストに SigV4 で署名し、署名をリクエストヘッダーに追加する"""

        # Create an AWS request
        headers = dict(request.headers)
        # Header 'connection' = 'keep-alive' is not used in calculating the request
        # signature on the server-side, and results in a signature mismatch if included
        headers.pop("connection", None)  # Remove if present, ignore if not

        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )

        # Sign the request with SigV4
        self.signer.add_auth(aws_request)

        # Add the signature header to the original request
        request.headers.update(dict(aws_request.headers))

        yield request


class StreamableHTTPTransportWithSigV4(StreamableHTTPTransport):
    """
    AWS SigV4 署名サポート付き Streamable HTTP クライアントトランスポート

    このトランスポートは、Lambda 関数 URL や API Gateway の背後にあるサーバーなど、
    AWS IAM を使用して認証する MCP サーバーとの通信を可能にします。
    """

    def __init__(
        self,
        url: str,
        credentials: Credentials,
        service: str,
        region: str,
        headers: dict[str, str] | None = None,
        timeout: float | timedelta = 30,
        sse_read_timeout: float | timedelta = 60 * 5,
    ) -> None:
        """SigV4 署名付き StreamableHTTP トランスポートを初期化する。

        Args:
            url: エンドポイント URL。
            credentials: 署名用の AWS 認証情報。
            service: AWS サービス名（例: 'lambda'）。
            region: AWS リージョン（例: 'us-east-1'）。
            headers: リクエストに含めるオプションのヘッダー。
            timeout: 通常操作用の HTTP タイムアウト。
            sse_read_timeout: SSE 読み取り操作用のタイムアウト。
        """
        # Initialize parent class with SigV4 auth handler
        super().__init__(
            url=url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            auth=SigV4HTTPXAuth(credentials, service, region),
        )

        self.credentials = credentials
        self.service = service
        self.region = region


@asynccontextmanager
async def streamablehttp_client_with_sigv4(
    url: str,
    credentials: Credentials,
    service: str,
    region: str,
    headers: dict[str, str] | None = None,
    timeout: float | timedelta = 30,
    sse_read_timeout: float | timedelta = 60 * 5,
    terminate_on_close: bool = True,
    httpx_client_factory: McpHttpClientFactory = create_mcp_http_client,
) -> AsyncGenerator[
    tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
        GetSessionIdCallback,
    ],
    None,
]:
    """
    SigV4 認証付き Streamable HTTP 用クライアントトランスポート。

    このトランスポートは、Lambda 関数 URL や API Gateway の背後にあるサーバーなど、
    AWS IAM を使用して認証する MCP サーバーとの通信を可能にします。

    Yields:
        以下を含むタプル:
            - read_stream: サーバーからメッセージを読み取るためのストリーム
            - write_stream: サーバーにメッセージを送信するためのストリーム
            - get_session_id_callback: 現在のセッション ID を取得する関数
    """

    async with streamablehttp_client(
        url=url,
        headers=headers,
        timeout=timeout,
        sse_read_timeout=sse_read_timeout,
        terminate_on_close=terminate_on_close,
        httpx_client_factory=httpx_client_factory,
        auth=SigV4HTTPXAuth(credentials, service, region),
    ) as result:
        yield result
