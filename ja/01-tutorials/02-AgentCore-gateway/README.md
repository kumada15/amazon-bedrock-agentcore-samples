# Amazon Bedrock AgentCore Gateway

## 概要
Bedrock AgentCore Gateway は、既存のAPIとLambda関数を、インフラや hosting を管理することなく、フルマネージドのMCPサーバーに変換する方法を提供します。お客様は既存のAPIのOpenAPI仕様またはSmithyモデルを持ち込むか、ツールをフロントエンドとするLambda関数を追加できます。Gateway はこれらすべてのツールに統一された Model Context Protocol（MCP）インターフェースを提供します。Gateway は、受信リクエストとターゲットリソースへの送信接続の両方に対して安全なアクセス制御を確保するために、二重認証モデルを採用しています。このフレームワークは2つの主要コンポーネントで構成されています：ゲートウェイターゲットへのアクセスを試みるユーザーを検証・認可するInbound Auth、および認証されたユーザーに代わってゲートウェイがバックエンドリソースに安全に接続できるようにするOutbound Auth です。これらの認証メカニズムが一緒になって、ユーザーとターゲットリソース間の安全なブリッジを作成し、IAM認証情報とOAuthベースの認証フローの両方をサポートします。Gateway はMCPのStreamable HTTP transport接続をサポートしています。

![仕組み](images/gateway-end-end-overview.png)

## 概念の定義

始める前に、Amazon Bedrock AgentCore Gateway を使い始めるためのいくつかの重要な概念を定義しましょう：

* **Amazon Bedrock AgentCore Gateway**：お客様が標準MCP操作（listTools、invokeTool など）を実行するためにMCPクライアントで呼び出すことができるHTTPエンドポイント。boto3などのAWS SDKを使用してこのAgentCore Gatewayを呼び出すこともできます。
* **Bedrock AgentCore Gateway Target**：お客様がAgentCore Gatewayにターゲットをアタッチするために使用するリソース。現在、AgentCore Gatewayのターゲットとして以下のタイプがサポートされています：
    * Lambda ARN
    * API仕様 → OpenAPI、Smithy
* **MCP Transport**：クライアント（LLMを使用するアプリケーション）とMCPサーバー間でメッセージがどのように移動するかを定義するメカニズム。現在、AgentCore Gateway は `Streamable HTTP connections` のみをトランスポートとしてサポートしています。

## 仕組み

![仕組み](images/gateway_how_does_it_work.png)

## インバウンドとアウトバウンドの認可
Bedrock AgentCore Gateway は、インバウンドとアウトバウンドの認証を通じて安全な接続を提供します。インバウンド認証では、AgentCore Gateway は呼び出し時に渡されたOAuthトークンを分析して、ゲートウェイ内のツールへのアクセスを許可または拒否します。ツールが外部リソースにアクセスする必要がある場合、AgentCore Gateway はAPI Key、IAM、またはOAuth Tokenを介したアウトバウンド認証を使用して、外部リソースへのアクセスを許可または拒否できます。

インバウンド認可フローでは、エージェントまたはMCPクライアントがAgentCore Gateway内のMCPツールを呼び出し、OAuthアクセストークン（ユーザーのIdPから生成）を追加します。AgentCore Gateway はOAuthアクセストークンを検証し、インバウンド認可を実行します。

AgentCore Gateway で実行されているツールが外部リソースにアクセスする必要がある場合、OAuthはGatewayターゲットのリソース資格情報プロバイダーを使用して下流リソースの資格情報を取得します。AgentCore Gateway は認可資格情報を呼び出し元に渡して、下流APIへのアクセスを取得します。

![安全なアクセス](images/gateway_secure_access.png)

### MCP認可とGateway

Amazon Bedrock AgentCore Gateway は、受信MCPツール呼び出しの認可について[MCP認可仕様](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)に準拠しています。

![安全なアクセス](images/oauth-flow-gateway.png)

### AgentCore GatewayとAgentCore Identityの統合

![AgentCore Identity と Gateway](images/end-end-auth-gateway.png)

### ツールの検索
Amazon Bedrock AgentCore Gateway には、自然言語クエリを通じてエージェントや開発者が最も関連性の高いツールを見つけるのを支援する、強力な組み込みセマンティック検索機能も含まれています。これにより、ツール選択のためにエージェントに渡す**コンテキストを削減**できます。この検索機能は、セマンティックマッチングのためにベクトル埋め込みを活用するプリビルドツールとして実装されています。ユーザーはCreateGateway API経由でオプトインすることで、Gateway作成時にこの機能を有効にできます。有効にすると、後続のCreateTarget操作で自動的にターゲットのツールのベクトル埋め込みが生成されます。このプロセス中、埋め込みが生成されている間、CreateTargetレスポンスのSTATUSフィールドは「UPDATING」を示します。

![ツール検索](images/gateway_tool_search.png)

### チュートリアルの詳細


| 項目               | 詳細                                                      |
|:-------------------|:----------------------------------------------------------|
| チュートリアルタイプ | インタラクティブ                                          |
| AgentCore コンポーネント | AgentCore Gateway、AgentCore Identity                   |
| エージェントフレームワーク | Strands Agents                                          |
| LLMモデル          | Anthropic Claude Haiku 4.5、Amazon Nova Pro               |
| チュートリアル内容 | AgentCore Gateway の作成と呼び出し                        |
| チュートリアル分野 | クロスバーティカル                                        |
| 難易度             | 簡単                                                      |
| 使用SDK           | boto3                                                     |

## チュートリアルアーキテクチャ

### チュートリアルの主な機能

#### 安全なツールアクセス

Amazon Bedrock AgentCore Gateway は、受信MCPツール呼び出しの認可について[MCP認可仕様](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)に準拠しています。
Amazon Bedrock AgentCore Gateway はまた、Gatewayからの送信呼び出しの認可をサポートするために2つのオプションを提供しています：
* API Keyを使用する、または
* OAuthアクセストークンを使用する
Amazon Bedrock AgentCore Identity の資格情報プロバイダーAPIを使用して認可を設定し、AgentCore Gatewayターゲットにアタッチできます。
各ターゲット（AWS Lambda、Smithy、OpenAPI）は資格情報プロバイダーにアタッチできます。

#### 統合

Bedrock AgentCore Gateway は以下と統合されます：
* Bedrock AgentCore Identity
* Bedrock AgentCore Runtime

### ユースケース

* MCPツールを呼び出すリアルタイムインタラクティブエージェント
* 異なるIdPを使用したインバウンド＆アウトバウンド認可
* AWS Lambda関数、Open API、SmithyモデルのMCP化
* MCPツールの検出

### メリット

* Gateway はAIエージェント開発とデプロイを簡素化するいくつかの主要なメリットを提供します：インフラ管理不要
* ホスティングの心配がないフルマネージドサービス。Amazon Bedrock AgentCore がすべてのインフラを自動的に処理します。
* 統一インターフェース：すべてのツールに対する単一のMCPプロトコルにより、エージェントコードで複数のAPIフォーマットと認証メカニズムを管理する複雑さが排除されます。
* 組み込み認証：OAuthと資格情報管理がトークンのライフサイクル、更新、安全な保存を追加の開発努力なしに処理します。
* 自動スケーリング：手動介入やキャパシティプランニングなしに、需要に基づいて自動的にスケールし、変動するワークロードを処理します。
* エンタープライズセキュリティ：暗号化、アクセス制御、監査ログを含むエンタープライズグレードのセキュリティ機能により、安全なツールアクセスを確保します。

## チュートリアル概要

これらのチュートリアルでは、以下の機能をカバーします：

- [AWS Lambda関数をMCPツールに変換](01-transform-lambda-into-mcp-tools)
- [APIをMCPツールに変換](02-transform-apis-into-mcp-tools)
- [MCPツールの検出](03-discover-mcp-tools)
