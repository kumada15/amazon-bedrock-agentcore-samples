# AgentCore Runtime での MCP サーバーのホスティング

## 概要

このセッションでは、Amazon Bedrock AgentCore Runtime で MCP ツールをホストする方法を説明します。

Amazon Bedrock AgentCore Python SDK を使用して、エージェント関数を Amazon Bedrock AgentCore 互換の MCP サーバーとしてラップします。
MCP サーバーの詳細を処理するため、エージェントのコア機能に集中できます。

Amazon Bedrock AgentCore Python SDK は、エージェントまたはツールコードを AgentCore Runtime で実行するために準備します。

コードを AgentCore の標準化された HTTP プロトコルまたは MCP プロトコルコントラクトに変換し、従来のリクエスト/レスポンスパターン（HTTP プロトコル）の直接 REST API エンドポイント通信、またはツールおよびエージェントサーバー用の Model Context Protocol（MCP プロトコル）を可能にします。

ツールをホストする場合、Amazon Bedrock AgentCore Python SDK は [Stateless Streamable HTTP] トランスポートプロトコルを `MCP-Session-Id` ヘッダーで[セッション分離](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#session-management)のために実装します。サーバーは、プラットフォームが生成する Mcp-Session-Id ヘッダーを拒否しないステートレス操作をサポートする必要があります。
MCP サーバーはポート `8000` でホストされ、1つの呼び出しパス `mcp-POST` を提供します。このインタラクションエンドポイントは MCP RPC メッセージを受信し、ツールの機能を通じて処理します。レスポンスのコンテンツタイプとして application/json と text/event-stream の両方をサポートします。

AgentCore プロトコルを MCP に設定すると、AgentCore Runtime は MCP サーバーコンテナがパス `0.0.0.0:8000/mcp` にあることを期待します。これは公式の MCP サーバー SDK のほとんどでサポートされているデフォルトパスです。

AgentCore Runtime では、デフォルトでセッション分離を提供し、ヘッダーのないリクエストに対して自動的に Mcp-Session-Id ヘッダーを追加するため、ステートレスな streamable-http サーバーをホストする必要があります。これにより、MCP クライアントは同じ Bedrock AgentCore Runtime セッション ID への接続の継続性を持つことができます。

`InvokeAgentRuntime` API のペイロードは完全にパススルーであるため、MCP などのプロトコルの RPC メッセージを簡単にプロキシできます。

このチュートリアルでは以下を学びます：

* ツールを持つ MCP サーバーの作成方法
* サーバーをローカルでテストする方法
* サーバーを AWS にデプロイする方法
* デプロイしたサーバーを呼び出す方法

### チュートリアル詳細

| 情報                | 詳細                                                      |
|:--------------------|:----------------------------------------------------------|
| チュートリアルタイプ | ツールのホスティング                                       |
| ツールタイプ        | MCP サーバー                                               |
| チュートリアル構成   | AgentCore Runtime でのツールホスティング。MCP サーバーの作成 |
| チュートリアル分野   | クロスバーティカル                                         |
| 例の複雑さ          | 簡単                                                       |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK および MCP Client       |

### チュートリアルアーキテクチャ
このチュートリアルでは、既存の MCP サーバーを AgentCore Runtime にデプロイする方法を説明します。

デモンストレーション目的で、`add_numbers`、`multiply_numbers`、`greet_users` の3つのツールを持つ非常にシンプルな MCP サーバーを使用します。

![MCP architecture](images/hosting_mcp_server.png)

### チュートリアルの主な機能

* MCP サーバーのホスティング
