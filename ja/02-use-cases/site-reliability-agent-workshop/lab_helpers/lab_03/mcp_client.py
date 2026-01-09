#!/usr/bin/env python3
"""
Lab 03: MCP Client Helper

AgentCore Gateway に接続し、Cognito JWT 認証を使用して
MCP ツールを呼び出すためのシンプルな MCP クライアントを提供します。

主な機能:
- Cognito JWT 認証
- MCP プロトコル（initialize、tools/list、tools/call）
- Gateway 接続管理
- ツール呼び出しのためのシンプルなインターフェース

使用方法:
    from lab_helpers.lab_03.mcp_client import MCPClient

    client = MCPClient(gateway_url, cognito_token)
    client.initialize()
    tools = client.list_tools()
    result = client.call_tool("tool_name", {"arg": "value"})
"""

import requests
import json
from typing import Dict, List, Any, Optional


class MCPClient:
    """
    AgentCore Gateway に接続するための MCP クライアント。

    このクライアントは以下を処理します:
    - Cognito トークンによる JWT 認証
    - MCP プロトコル（JSON-RPC 2.0）
    - セッションの初期化
    - ツールの検出と呼び出し
    """

    def __init__(self, gateway_url: str, access_token: str, timeout: int = 900):
        """
        MCP クライアントを初期化。

        Args:
            gateway_url: Gateway MCP エンドポイント URL
            access_token: Cognito JWT アクセストークン
            timeout: リクエストタイムアウト（秒）（デフォルト: 300）
        """
        self.gateway_url = gateway_url
        self.access_token = access_token
        self.timeout = timeout
        self.request_id = 0
        self.initialized = False
        self.server_info = {}

    def _next_request_id(self) -> int:
        """JSON-RPC 用の次のリクエスト ID を生成"""
        self.request_id += 1
        return self.request_id

    def _mcp_request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Gateway に MCP JSON-RPC リクエストを送信。

        Args:
            method: MCP メソッド名（例: "initialize"、"tools/list"、"tools/call"）
            params: メソッドパラメータ（オプション）

        Returns:
            辞書形式の JSON-RPC レスポンス

        Raises:
            requests.HTTPError: HTTP リクエストが失敗した場合
            ValueError: レスポンスにエラーが含まれる場合
        """
        request_payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method
        }

        if params is not None:
            request_payload["params"] = params

        response = requests.post(
            self.gateway_url,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            },
            json=request_payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        result = response.json()

        # JSON-RPC エラーをチェック
        if 'error' in result:
            error = result['error']
            raise ValueError(f"MCP Error [{error.get('code')}]: {error.get('message')}")

        return result

    def initialize(self, client_name: str = "aiml301-mcp-client",
                   client_version: str = "1.0.0") -> Dict[str, Any]:
        """
        Gateway との MCP セッションを初期化。

        他の MCP 操作を行う前に、これを呼び出す必要があります。

        Args:
            client_name: クライアントアプリケーション名
            client_version: クライアントバージョン文字列

        Returns:
            initialize レスポンスからのサーバー情報

        Example:
            >>> client.initialize()
            {'name': 'aiml301-remediation-gateway', 'version': '1.0.0'}
        """
        print("🚀 Initializing MCP session...")

        response = self._mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": client_name,
                    "version": client_version
                }
            }
        )

        print(f"  📋 Response: {response}")

        if 'result' in response:
            self.server_info = response['result'].get('serverInfo', {})
            self.initialized = True

            print(f"  ✅ Session initialized")
            print(f"     Server: {self.server_info.get('name', 'Unknown')}")
            print(f"     Version: {self.server_info.get('version', 'Unknown')}")

            return self.server_info
        else:
            raise RuntimeError(f"Initialize failed: {response}")
            raise ValueError("Initialize failed: No result in response")

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Gateway から利用可能なすべての MCP ツールを一覧表示。

        Returns:
            名前、説明、スキーマを含むツール定義のリスト

        Example:
            >>> tools = client.list_tools()
            >>> print(f"{len(tools)} 個のツールが見つかりました")
            >>> for tool in tools:
            >>>     print(f"  - {tool['name']}: {tool['description']}")
        """
        if not self.initialized:
            raise RuntimeError("Client not initialized. Call initialize() first.")

        print("\n🔧 Listing available tools...")

        response = self._mcp_request(method="tools/list", params={})

        if 'result' in response:
            tools = response['result'].get('tools', [])
            print(f"  ✅ Found {len(tools)} tool(s)")

            for i, tool in enumerate(tools, 1):
                tool_name = tool.get('name', 'unnamed')
                # 説明の最初の行を取得
                description = tool.get('description', 'No description')
                first_line = description.split('\n')[0]
                print(f"     {i}. {tool_name}")
                print(f"        {first_line[:80]}...")

            return tools
        else:
            raise ValueError("List tools failed: No result in response")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        引数を指定して MCP ツールを呼び出し。

        Args:
            tool_name: 呼び出すツールの名前
            arguments: 辞書形式のツール引数

        Returns:
            ツール実行結果

        Example:
            >>> result = client.call_tool(
            ...     "ddgs_search",
            ...     {"query": "AWS Bedrock features", "max_results": 3}
            ... )
            >>> print(result)
        """
        if not self.initialized:
            raise RuntimeError("Client not initialized. Call initialize() first.")

        print(f"\n🔨 Calling tool: {tool_name}")
        print(f"   Arguments: {json.dumps(arguments, indent=2)}")

        response = self._mcp_request(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments
            }
        )

        if 'result' in response:
            result = response['result']
            # print(f"  ✅ Tool execution successful")

            # コンテンツの抽出と表示を試行
            if 'content' in result:
                for content_item in result['content']:
                    if content_item.get('type') == 'text':
                        try:
                            # より見やすい表示のために JSON としてパースを試行
                            text_content = content_item['text']
                            parsed = json.loads(text_content)
                            print(f"\n  📋 Result:")
                            print(f"     {json.dumps(parsed, indent=6)}")
                        except (json.JSONDecodeError, KeyError):
                            print(f"\n  📋 Result: {content_item['text']}")

            return result
        else:
            raise ValueError("Tool call failed: No result in response")

    def close(self):
        """MCP セッションを閉じる（必要に応じてクリーンアップ）"""
        self.initialized = False
        print("\n✅ MCP session closed")


def create_mcp_client(gateway_url: str, cognito_token: str) -> MCPClient:
    """
    MCP クライアントを作成・初期化するファクトリ関数。

    Args:
        gateway_url: Gateway MCP エンドポイント URL
        cognito_token: Cognito JWT アクセストークン

    Returns:
        初期化済みの MCPClient インスタンス

    Example:
        >>> from lab_helpers.lab_03.mcp_client import create_mcp_client
        >>> client = create_mcp_client(gateway_url, token)
        >>> tools = client.list_tools()
    """
    client = MCPClient(gateway_url, cognito_token)
    client.initialize()
    return client
