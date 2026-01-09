#!/usr/bin/env python3
"""
Lab 02: MCP クライアントヘルパー

AgentCore Gateway に接続し、Cognito JWT 認証で
MCP ツールを呼び出すためのシンプルな MCP クライアントを提供します。

主な機能:
- Cognito JWT 認証
- MCP プロトコル (initialize, tools/list, tools/call)
- Gateway 接続管理
- ツール呼び出しのシンプルなインターフェース

使用方法:
    from lab_helpers.lab_02.mcp_client import MCPClient

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
    - MCP プロトコル (JSON-RPC 2.0)
    - セッション初期化
    - ツールの検出と呼び出し
    """

    def __init__(self, gateway_url: str, access_token: str, timeout: int = 900):
        """
        MCP クライアントを初期化。

        Args:
            gateway_url: Gateway MCP エンドポイント URL
            access_token: Cognito JWT アクセストークン
            timeout: リクエストタイムアウト（秒）（デフォルト: 30）
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
            method: MCP メソッド名 (例: "initialize", "tools/list", "tools/call")
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

    def initialize(self, client_name: str = "aiml301-diagnostics-mcp-client",
                   client_version: str = "1.0.0") -> Dict[str, Any]:
        """
        Gateway との MCP セッションを初期化。

        他の MCP 操作の前にこれを呼び出す必要があります。

        Args:
            client_name: クライアントアプリケーション名
            client_version: クライアントバージョン文字列

        Returns:
            初期化レスポンスからのサーバー情報

        Example:
            >>> client.initialize()
            {'name': 'aiml301-diagnostics-gateway', 'version': '1.0.0'}
        """
        print("MCP セッションを初期化中...")

        response = self._mcp_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": client_name,
                    "version": client_version
                }
            }
        )

        if 'result' in response:
            self.server_info = response['result'].get('serverInfo', {})
            self.initialized = True

            print(f"  セッションを初期化しました")
            print(f"     サーバー: {self.server_info.get('name', 'Unknown')}")
            print(f"     バージョン: {self.server_info.get('version', 'Unknown')}")

            return self.server_info
        else:
            raise ValueError("初期化に失敗しました: レスポンスに結果がありません")

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
            raise RuntimeError("クライアントが初期化されていません。先に initialize() を呼び出してください。")

        print("\n利用可能なツールを一覧表示中...")

        response = self._mcp_request(method="tools/list", params={})

        if 'result' in response:
            tools = response['result'].get('tools', [])
            print(f"  {len(tools)} 個のツールが見つかりました")

            for i, tool in enumerate(tools, 1):
                tool_name = tool.get('name', 'unnamed')
                # 説明の最初の行を取得
                description = tool.get('description', 'No description')
                first_line = description.split('\n')[0]
                print(f"     {i}. {tool_name}")
                print(f"        {first_line[:80]}...")

            return tools
        else:
            raise ValueError("ツール一覧の取得に失敗しました: レスポンスに結果がありません")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        引数を指定して MCP ツールを呼び出す。

        Args:
            tool_name: 呼び出すツールの名前
            arguments: 辞書形式のツール引数

        Returns:
            ツール実行結果

        Example:
            >>> result = client.call_tool(
            ...     "strands-diagnostics-agent___invoke_diagnostics_agent",
            ...     {"query": "主な問題は何ですか？"}
            ... )
            >>> print(result)
        """
        if not self.initialized:
            raise RuntimeError("クライアントが初期化されていません。先に initialize() を呼び出してください。")

        print(f"\nツールを呼び出し中: {tool_name}")
        print(f"   引数: {json.dumps(arguments, indent=2)}")

        response = self._mcp_request(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments
            }
        )

        if 'result' in response:
            result = response['result']
            print(f"  ツール実行が成功しました")

            # コンテンツの抽出と表示を試みる
            if 'content' in result:
                for content_item in result['content']:
                    if content_item.get('type') == 'text':
                        try:
                            # より良い表示のために JSON としてパースを試みる
                            text_content = content_item['text']
                            parsed = json.loads(text_content)
                            print(f"\n  結果:")
                            print(f"     {json.dumps(parsed, indent=6)}")
                        except (json.JSONDecodeError, KeyError):
                            print(f"\n  結果: {content_item['text'][:500]}...")

            return result
        else:
            raise ValueError("ツール呼び出しに失敗しました: レスポンスに結果がありません")

    def close(self):
        """MCP セッションを閉じる（必要に応じてクリーンアップ）"""
        self.initialized = False
        print("\nMCP セッションを閉じました")


def create_mcp_client(gateway_url: str, cognito_token: str) -> MCPClient:
    """
    MCP クライアントを作成して初期化するファクトリ関数。

    Args:
        gateway_url: Gateway MCP エンドポイント URL
        cognito_token: Cognito JWT アクセストークン

    Returns:
        初期化された MCPClient インスタンス

    Example:
        >>> from lab_helpers.lab_02.mcp_client import create_mcp_client
        >>> client = create_mcp_client(gateway_url, token)
        >>> tools = client.list_tools()
    """
    client = MCPClient(gateway_url, cognito_token)
    client.initialize()
    return client
