# MCP サーバーを AgentCore Gateway に統合

## 概要
Amazon Bedrock AgentCore Gateway は、既存の REST API や AWS Lambda 関数と並んで、MCP サーバーをネイティブターゲットとしてサポートするようになりました。この機能強化により、組織は MCP サーバー実装を統一されたインターフェースを通じて統合でき、MCP サーバーごとにカスタムクライアントコードを書く必要がなくなります。Gateway は、ツール管理、認証、ルーティングを一元化することで、複数のチームとサーバーにまたがる AI エージェントデプロイメントのスケーリングにおける主要なエンタープライズ課題に対処します。

Gateway は、ツール検出を簡素化し、セキュリティプロトコルを標準化し、数十から数百の MCP サーバーにスケーリングする際の運用の複雑さを軽減する集中管理フレームワークを採用しています。この統一されたアプローチにより、企業は単一のインターフェースを通じて AI エージェントインフラストラクチャを効率的に管理しながら、一貫したセキュリティと運用標準を維持でき、複数の個別のゲートウェイの必要性を排除し、全体的なメンテナンス負担を軽減します。

![How does it work](images/mcp-server-target.png)

### AgentCore Gateway での MCP サーバーのツール定義の更新
SynchronizeGateway API は、慎重に調整された一連のステップを通じて、MCP サーバーターゲットからのツールのオンデマンド同期を可能にします。運用管理者が AgentCore Gateway への SynchronizeGateway API 呼び出しを行うことでプロセスを開始し、ツール定義を更新する非同期操作を起動します。この制御は、MCP サーバー設定を変更した後に特に価値があります。

OAuth 認証されたターゲットの場合、AgentCore Gateway はまず AgentCore Identity サービスと通信して認証情報を取得および検証します。Identity サービスは OAuth リソース認証情報プロバイダーとして機能し、必要なトークンを返します。この段階で認証情報の検証が失敗した場合、同期プロセスは即座に終了し、ターゲットは FAILED 状態に移行します。

認証が成功すると（または認証なしで設定されたターゲットの場合は即座に）、Gateway は MCP サーバーとのセッションを初期化し、安全な接続を確立します。Gateway は tools/list 機能を使用してページネーションされた呼び出しを行い、パフォーマンスとリソース利用を最適化するために100個のバッチでツールを処理します。

ツールが取得されると、Gateway は他のターゲットとの名前の競合を防ぐためにターゲット固有のプレフィックスを追加してツール定義を正規化します。この正規化プロセスは、元の MCP サーバー定義からの重要なメタデータを保持しながら一貫性を維持します。プロセス全体を通じて、Gateway はシステムの安定性を確保するためにターゲットごとに10,000ツールの厳格な制限を適用します。API は、不整合な状態につながる可能性のある同時変更を防ぐために、同期中に楽観的ロックを実装しています。キャッシュされたツール定義により、同期間の ListTools 操作で一貫した高パフォーマンスが確保されます。

![How does it work](images/mcp-server-target-explicit-sync.png)

### ツールスキーマの暗黙的同期
CreateGatewayTarget および UpdateGatewayTarget 操作中、AgentCore Gateway は明示的な SynchronizeGateway API とは異なるツールスキーマを自動的に同期します。この組み込み同期により、新規または更新された MCP ターゲットは即座に使用可能になり、データの一貫性が維持されます。これにより、作成/更新操作は他のターゲットタイプと比較して遅くなりますが、READY としてマークされたターゲットが有効なツール定義を持ち、未検証のツール定義を持つターゲットからの問題を防ぐことが保証されます。

![How does it work](images/mcp-server-target-implicit-sync.png)

### チュートリアル詳細


| 情報                 | 詳細                                                               |
|:---------------------|:------------------------------------------------------------------|
| チュートリアルタイプ  | インタラクティブ                                                   |
| AgentCore コンポーネント | AgentCore Gateway、AgentCore Identity、AgentCore Runtime         |
| エージェントフレームワーク | Strands Agents                                                 |
| Gateway ターゲットタイプ | MCP サーバー                                                     |
| Inbound Auth IdP     | Amazon Cognito（他も使用可能）                                    |
| Outbound Auth        | Amazon Cognito（他も使用可能）                                    |
| LLM モデル           | Anthropic Claude Sonnet 4                                         |
| チュートリアル構成    | MCP ターゲットを持つ AgentCore Gateway の作成とツールの同期        |
| チュートリアル分野    | クロスバーティカル                                                 |
| 例の複雑さ           | 簡単                                                               |
| 使用 SDK             | boto3                                                              |

## チュートリアルアーキテクチャ

### チュートリアルの主な機能

* MCP サーバーを AgentCore Gateway に統合
* 明示的および暗黙的同期を実行してツール定義を更新

## チュートリアル概要

これらのチュートリアルでは、以下の機能をカバーします：

- [MCP サーバーを AgentCore Gateway に統合](01-mcp-server-target.ipynb)
- [明示的および暗黙的同期を実行してツール定義を更新](02-mcp-target-synchronization.ipynb)

