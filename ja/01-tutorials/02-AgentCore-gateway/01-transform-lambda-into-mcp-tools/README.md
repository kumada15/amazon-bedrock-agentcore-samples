# Gateway 用の Lambda 関数ツールの実装

## 概要
Bedrock AgentCore Gateway は、既存の Lambda 関数をインフラやホスティングを管理することなく、フルマネージドの MCP サーバーに変換する方法を提供します。顧客は既存の AWS Lambda 関数を持ち込むか、ツールのフロントエンドとして新しい Lambda 関数を追加できます。Gateway はこれらすべてのツールに統一された Model Context Protocol（MCP）インターフェースを提供します。Gateway は、受信リクエストとターゲットリソースへのアウトバウンド接続の両方に対して安全なアクセス制御を確保するデュアル認証モデルを採用しています。このフレームワークは2つの主要コンポーネントで構成されています：Inbound Auth（ゲートウェイターゲットにアクセスしようとするユーザーを検証および認可）と Outbound Auth（認証されたユーザーに代わってゲートウェイがバックエンドリソースに安全に接続できるようにする）。これらの認証メカニズムが一緒になって、ユーザーとターゲットリソース間の安全なブリッジを作成し、IAM 認証情報と OAuth ベースの認証フローの両方をサポートします。

![How does it work](images/lambda-iam-gateway.png)

![How does it work](images/lambda-gw-iam-inbound.png)


### Lambda コンテキストオブジェクトの理解
Gateway が Lambda 関数を呼び出すとき、context.client_context オブジェクトを通じて特別なコンテキスト情報を渡します。このコンテキストには呼び出しに関する重要なメタデータが含まれており、関数はこれを使用してリクエストの処理方法を決定できます。
context.client_context.custom オブジェクトで以下のプロパティが利用可能です：
* bedrockagentcoreEndpointId：リクエストを受信した Gateway エンドポイントの ID。
* bedrockagentcoreTargetId：リクエストを関数にルーティングした Gateway ターゲットの ID。
* bedrockagentcoreMessageVersion：リクエストに使用されるメッセージフォーマットのバージョン。
* bedrockagentcoreToolName：呼び出されるツールの名前。Lambda 関数が複数のツールを実装する場合に特に重要です。
* bedrockagentcoreSessionId：現在の呼び出しのセッション ID。同じセッション内の複数のツール呼び出しを相関させるために使用できます。

Lambda 関数コードでこれらのプロパティにアクセスして、どのツールが呼び出されているかを判断し、関数の動作をカスタマイズできます。

![How does it work](images/lambda-context-object.png)

### レスポンス形式とエラー処理

Lambda 関数は、Gateway が解釈してクライアントに返すことができるレスポンスを返す必要があります。レスポンスは以下の構造を持つ JSON オブジェクトである必要があります：statusCode フィールドは操作の結果を示す HTTP ステータスコードである必要があります：
* 200：成功
* 400：不正なリクエスト（クライアントエラー）
* 500：内部サーバーエラー

body フィールドは文字列、またはより複雑なレスポンスを表す JSON 文字列のいずれかになります。構造化されたレスポンスを返したい場合は、JSON 文字列にシリアライズする必要があります。

### エラー処理
適切なエラー処理は、クライアントに意味のあるフィードバックを提供するために重要です。Lambda 関数は例外をキャッチし、適切なエラーレスポンスを返す必要があります。

### テスト

注意：```__context__``` フィールドは、Gateway によって呼び出されたときに関数に渡される実際のイベントの一部ではありません。コンテキストオブジェクトをシミュレートするテスト目的でのみ使用されます。
Lambda コンソールでテストする場合、シミュレートされたコンテキストを処理するように関数を変更する必要があります。このアプローチにより、Gateway ターゲットとしてデプロイする前に、異なるツール名と入力パラメータで Lambda 関数をテストできます。

### クロスアカウント Lambda アクセス

Lambda 関数が Gateway とは異なる AWS アカウントにある場合、Gateway が関数を呼び出せるように、Lambda 関数にリソースベースのポリシーを設定する必要があります。以下はポリシーの例です：

```
{
  "Version": "2012-10-17",
  "Id": "default",
  "Statement": [
    {
      "Sid": "cross-account-access",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/GatewayExecutionRole"
      },
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-west-2:987654321098:function:MyLambdaFunction"
    }
  ]
}
```
このポリシーでは：
- 123456789012 は Gateway がデプロイされているアカウント ID
- GatewayExecutionRole は Gateway が使用する IAM ロール
- 987654321098 は Lambda 関数がデプロイされているアカウント ID
- MyLambdaFunction は Lambda 関数の名前

このポリシーを追加すると、異なるアカウントにあっても、Gateway ターゲット設定で Lambda 関数 ARN を指定できます。

### チュートリアル詳細


| 情報                 | 詳細                                                      |
|:---------------------|:----------------------------------------------------------|
| チュートリアルタイプ  | インタラクティブ                                           |
| AgentCore コンポーネント | AgentCore Gateway、AgentCore Identity、AWS IAM          |
| エージェントフレームワーク | Strands Agents                                         |
| LLM モデル           | Anthropic Claude Haiku 4.5、Amazon Nova Pro               |
| チュートリアル構成    | AgentCore Gateway の作成と AgentCore Gateway の呼び出し    |
| チュートリアル分野    | クロスバーティカル                                         |
| 例の複雑さ           | 簡単                                                       |
| 使用 SDK             | boto3                                                      |

## チュートリアルアーキテクチャ

### チュートリアルの主な機能

* Lambda 関数を MCP ツールに公開
* OAuth と IAM を使用したツール呼び出しのセキュア化

## チュートリアル概要

これらのチュートリアルでは、以下の機能をカバーします：

- [OAuth Inbound Auth で AWS Lambda 関数を MCP ツールに変換](01-gateway-target-lambda-oauth.ipynb)

- [AWS IAM Inbound Auth で AWS Lambda 関数を MCP ツールに変換](02-gateway-target-lambda-iam.ipynb)
