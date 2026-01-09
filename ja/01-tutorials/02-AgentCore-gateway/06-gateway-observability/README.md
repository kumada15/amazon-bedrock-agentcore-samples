AgentCore Gateway 可観測性チュートリアル
# Amazon CloudWatch と AWS CloudTrail を使用した AgentCore Gateway の可観測性設定

## 概要

可観測性は AgentCore Gateway の基本的な機能です。なぜなら、Gateway を通じてデプロイされた AI エージェントの機能とパフォーマンスに関する包括的なリアルタイムインサイトを提供するからです。リクエスト量、成功率、エラーパターン、ツール呼び出しのレイテンシ、認証イベントなどの主要なメトリクスをキャプチャおよび表示することで、可観測性機能により開発者と運用者はエージェントワークフローの健全性と効率を継続的に監視できます。このレベルの監視は、ユーザーエクスペリエンスやシステムの信頼性に影響を与える可能性のある異常やボトルネックを迅速に特定し、プロアクティブなトラブルシューティングとパフォーマンスチューニングを可能にします。

高レベルのメトリクスを超えて、AgentCore Gateway の可観測性は各エージェントのワークフローの詳細なトレーシングを提供します。ツールの呼び出しからモデル呼び出し、メモリ取得まで、すべてのアクションが OpenTelemetry 標準に準拠したスパンとトレースとして記録されます。このリッチなテレメトリデータにより、開発者はエージェントの内部意思決定プロセス（各ステップがどのように実行されたか、その所要時間を含む）を透明に把握できます。このような詳細なトレーサビリティは、複雑な障害や予期しない動作のデバッグに非常に価値があり、エンジニアがエラーや非効率の正確なポイントを掘り下げることができます。さらに、Amazon CloudWatch などの広く使用されているモニタリングプラットフォームと統合することで、これらの可観測性機能は統一されたアクセス可能な運用概要を実現します。

さらに、可観測性はエージェントアクティビティの監査証跡を提供することで、コンプライアンスとガバナンスの要件をサポートします。これはエンタープライズ環境にとって重要です。また、使用パターンを明らかにし、コスト削減や速度向上のためのエージェントワークフローの調整を支援することで、最適化を促進します。最終的に、これらの可観測性機能は AgentCore Gateway をブラックボックスインターフェースから、本番環境での信頼性が高く、スケーラブルで、パフォーマンスの高い AI エージェントデプロイメントをサポートする透明で管理可能なシステムに変換します。

## Amazon CloudWatch と AWS CloudTrail による可観測性

* Amazon CloudWatch は、AgentCore Gateway のリアルタイムパフォーマンスモニタリングと運用トラブルシューティングに焦点を当て、レイテンシ、エラー率、使用パターンの詳細なメトリクスとログを提供します。
* AWS CloudTrail は、Gateway に関連する API 呼び出しとユーザーアクションの完全な履歴を記録することで、セキュリティ、コンプライアンス、監査に焦点を当てています。

これらを組み合わせることで、本番環境で AgentCore Gateway を管理するための包括的な可観測性とガバナンスフレームワークを提供します。

![images/1-agentcore-gw-architecture.png]

#### AgentCore Gateway CloudWatch メトリクス

Gateway は以下のメトリクスを Amazon CloudWatch に公開します。これらは API 呼び出し、パフォーマンス、エラーに関する情報を提供します。

* **Invocations：** 各 Data Plane API に対して行われたリクエストの総数。レスポンスステータスに関係なく、各 API 呼び出しは1回の呼び出しとしてカウントされます。

* **Throttles：** サービスによってスロットリング（ステータスコード 429）されたリクエスト数。

* **SystemErrors：** 5xx ステータスコードで失敗したリクエスト数。

* **UserErrors：** 429 を除く 4xx ステータスコードで失敗したリクエスト数。

* **Latency：** サービスがリクエストを受信してから最初のレスポンストークンの送信を開始するまでの経過時間。つまり、初期レスポンス時間。

* **Duration：** リクエストを受信してから最終レスポンストークンを送信するまでの合計経過時間。リクエストの完全なエンドツーエンド処理時間を表します。

* **TargetExecutionTime：** Lambda / OpenAPI などを介してターゲットを実行するのにかかった合計時間。これにより、合計レイテンシに対するターゲットの寄与を判断できます。

* **TargetType：** 各タイプのターゲット（MCP、Lambda、OpenAPI）によって処理されたリクエストの総数。

#### AgentCore Gateway CloudWatch ベンダーログ

AgentCore は Gateway リソースについて以下の情報をログに記録します：

* Gateway リクエスト処理の開始と完了
* ターゲット設定のエラーメッセージ
* 認可ヘッダーが欠落または不正な MCP リクエスト
* 不正なリクエストパラメータ（tools、method）を持つ MCP リクエスト

AgentCore はログを Amazon CloudWatch、Amazon S3、または Firehose ストリームに出力できます。このチュートリアルでは CloudWatch に焦点を当てます。

AWS コンソールで AgentCore Gateway Log Delivery の下に Amazon CloudWatch Logs を追加すると、これらのログはデフォルトのロググループ **/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/{gateway_id}** に保存されます。/**aws/vendedlogs/** で始まるカスタムロググループも設定できます。

#### AgentCore Gateway CloudWatch トレーシング

Amazon Bedrock AgentCore Gateway でトレーシングを有効にすると、AI エージェントとそれらが対話するツールの動作とパフォーマンスに関する深いインサイトが得られます。リクエストが Gateway を通過する際の完全な実行パスをキャプチャし、複雑なエージェントワークフローの効果的なデバッグ、最適化、監査に不可欠です。

* **トレース - トップレベルコンテナ**

  * 完全なインタラクションコンテキストを表す
  * エージェント呼び出しから始まる完全な実行パスをキャプチャ
  * インタラクション全体で複数のエージェント呼び出しを含む場合がある
  * ワークフロー全体の最も広い視野を提供

* **リクエスト - 個々のエージェント呼び出し**

  * トレース内の単一のリクエスト/レスポンスサイクルを表す
  * 各エージェント呼び出しは新しいリクエストを作成
  * エージェントへの1回の完全な呼び出しとそのレスポンスをキャプチャ
  * 単一のトレース内に複数のリクエストが存在可能

* **スパン - 個別の作業単位**

  * リクエスト内の特定の測定可能な操作を表す
  * 以下のような詳細なステップをキャプチャ：
    * コンポーネント初期化
    * ツール実行
    * API 呼び出し
    * 処理ステップ
  * 所要時間分析のための正確な開始/終了タイムスタンプを持つ

これら3つの可観測性コンポーネント間の関係は以下のように視覚化できます：

  トレース（最高レベル）- 完全なユーザー会話またはインタラクションコンテキストを表す

  リクエスト（中間レベル）- トレース内の個々のリクエスト/レスポンスサイクルを表す

  スパン（最低レベル）- リクエスト内の特定の操作またはステップを表す

          Trace 1
          ├── Request 1.1
          │   ├── Span 1.1.1
          │   ├── Span 1.1.2
          │   └── Span 1.1.3
          ├── Request 1.2
          │   ├── Span 1.2.1
          │   ├── Span 1.2.2
          │   └── Span 1.2.3
          └── Request 1.N

          Trace 2
          ├── Request 2.1
          │   ├── Span 2.1.1
          │   ├── Span 2.1.2
          │   └── Span 2.1.3
          ├── Request 2.2
          │   ├── Span 2.2.1
          │   ├── Span 2.2.2
          │   └── Span 2.2.3
          └── Request 2.N



#### AgentCore Gateway CloudTrail

AgentCore Gateway は AWS CloudTrail と完全に統合されており、Gateway インフラストラクチャ内の **API アクティビティ** と運用イベントを追跡するための包括的なログ記録とモニタリング機能を提供します。

CloudTrail は AgentCore Gateway に対して2つの異なるタイプのイベントをキャプチャします
* 管理イベントは自動的に記録され、Gateway リソースの作成、更新、削除などのコントロールプレーン操作をキャプチャします
* データイベントは、Gateway 上または Gateway 内で実行されたリソース操作（データプレーン操作とも呼ばれる）に関する情報を提供し、デフォルトでは記録されないため明示的に有効にする必要がある高ボリュームアクティビティです

CloudTrail は Gateway コンソールからの呼び出しと Gateway API へのコード呼び出しを含む、Gateway へのすべての API 呼び出しをイベントとしてキャプチャします。CloudTrail によって収集された情報を使用して、Gateway に対して行われたリクエスト、リクエストを行った人物、リクエストが行われた時刻、追加の詳細を判断できます[3]。管理イベントは、AWS アカウント内のリソースで実行された管理操作（コントロールプレーン操作とも呼ばれる）に関する情報を提供します。

## チュートリアル概要

これらのチュートリアルでは、AgentCore Gateway の可観測性をカバーします。


| 情報                 | 詳細                                                      |
|:---------------------|:----------------------------------------------------------|
| チュートリアルタイプ  | インタラクティブ                                           |
| AgentCore コンポーネント | AgentCore Gateway、Amazon CloudWatch、AWS CloudTrail     |
| エージェントフレームワーク | Strands Agents                                         |
| Gateway ターゲットタイプ | AWS Lambda                                              |
| Inbound Auth IdP     | Amazon Cognito                                            |
| Outbound Auth        | AWS IAM                                                   |
| LLM モデル           | Anthropic Claude Sonnet 4.0                               |
| チュートリアル構成    | CloudWatch、CloudTrail を使用した AgentCore Gateway 可観測性 |
| チュートリアル分野    | クロスバーティカル                                         |
| 例の複雑さ           | 簡単                                                       |
| 使用 SDK             | boto3                                                      |

#### チュートリアル詳細

* このチュートリアルでは、Bedrock AgentCore Gateway を作成し、Lambda をターゲットタイプとして2つのツール（get_order と update_order）を追加します。
* 送信先として CloudWatch を持つログ配信グループを作成し、ベンダーログを観察します。
* Amazon CloudWatch Tracing を有効にし、ベンダーログで見つかったトレース ID を Traces / Spans に接続してより深く掘り下げます。
* Strands Agent で AgentCore Runtime を作成し、Spans をウォークスルーします。
* CloudTrail 管理イベントとデータイベントを設定し、いくつかの例を確認します。

### リソース

* [AgentCore が生成する Gateway 可観測性データ](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-gateway-metrics.html)
* [AgentCore Gateway のログ送信先とトレーシングを有効にする](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html#observability-configure-cloudwatch)
* [CloudTrail を使用した AgentCore Gateway API 呼び出しのログ記録](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-cloudtrail.html)
* [AgentCore CloudWatch メトリクスとアラームの設定](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-advanced-observability-metrics.html)
* [CloudTrail を使用した Gateway API 呼び出しのログ記録](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-cloudtrail.html)
* [可観測性の概念](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-telemetry.html)

