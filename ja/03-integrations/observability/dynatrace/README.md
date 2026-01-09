# Amazon Bedrock AgentのDynatrace統合

このサンプルには、[Bedrock AgentCore Agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)を基盤として構築されたパーソナルアシスタントエージェントのデモが含まれています。


## 前提条件

- Python 3.9以上
- Dynatraceアカウント
- 適切な権限を持つAWSアカウント
- 以下のAWSサービスへのアクセス：
   - Amazon Bedrock


## Dynatraceインストルメンテーション

> [!TIP]
> 詳細なセットアップ手順、設定オプション、高度なユースケースについては、[Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started)を参照してください。

Bedrock AgentCoreには、[Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)サポートが標準で組み込まれています。
そのため、Dynatrace AI Observabilityにデータを送信するための[OpenTelemetry SDK](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md#sdk)を登録するだけです。

このプロセスを簡素化し、すべての複雑さを[dynatrace.py](./dynatrace.py)内に隠蔽しています。
Dynatraceテナントにデータを送信するには、`OTEL_ENDPOINT`環境変数に[OTLP](https://docs.dynatrace.com/docs/shortlink/otel-getstarted-otlpexport)を取り込むためのDynatrace URLを設定できます。例：`https://wkf10640.live.dynatrace.com/api/v2/otlp`

APIアクセストークンは、ファイルシステムの`/etc/secrets/dynatrace_otel`から読み取られるか、環境変数`DT_TOKEN`から読み取られます。


## 使用方法

### AWS認証情報の設定

[Amazon Bedrock AgentCoreドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)に従って、適切なポリシーを持つAWSロールを設定してください。
その後、ターミナルで以下のコマンドを実行して、環境変数にAWS認証情報を設定できます：


```bash
export AWS_ACCESS_KEY_ID==your_api_key
export AWS_SECRET_ACCESS_KEY==your_secret_key
export AWS_REGION=your_region
```

このサンプルで使用するモデル`eu.anthropic.claude-3-7-sonnet-20250219-v1:0`へのアクセス権がアカウントにあることを確認してください。モデルへのアクセスを有効にする方法については、[Amazon Bedrockドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-permissions.html)を参照してください。
環境変数`BEDROCK_MODEL_ID`を設定することで、使用するモデルを変更できます。

### Dynatraceトークンの設定

15日間の[Dynatrace無料トライアル](https://www.dynatrace.com/signup/)を作成してください。
数分後、テナントにリダイレクトされます。URLは`https://wkf10640.apps.dynatrace.com/`のようになります。
`wkf10640`という値は、後で必要になる環境IDです。

その後、アクセストークンを作成できます：

1. Dynatraceで、**Access Tokens**に移動します。**Access Tokens**を見つけるには、**Ctrl/Cmd+K**を押して**Access Tokens**を検索して選択します。
2. **Access Tokens**で、**Generate new token**を選択します。
3. 新しいトークンの**Token name**を入力します。
4. 新しいトークンに以下の権限を付与します：
5. 以下のスコープをすべて検索して選択します。
    * **Ingest OpenTelemetry traces** (`openTelemetryTrace.ingest`)
    * **Ingest logs** (`logs.ingest`)
    * **Read metrics** (`metrics.read`)
6. **Generate token**を選択します。
7. 生成されたトークンをクリップボードにコピーします。将来使用するためにパスワードマネージャーにトークンを保存してください。


その後、ターミナルで以下のコマンドを実行して、環境変数にDynatrace情報を設定できます：

```bash
export DT_TOKEN==your_access_token
export OTEL_ENDPOINT==https://{your-environment-id}.live.dynatrace.com/api/v2/otlp
```


### アプリの実行

以下のコマンドでサンプルを開始できます：`uv run main.py`
これにより、ポート`8080`でリッスンするHTTPサーバーが作成され、エージェントの要件を処理するための必須エンドポイント`/invocations`が実装されます。

これでエージェントのデプロイ準備が完了しました。ベストプラクティスは、コードをコンテナとしてパッケージ化し、CI/CDパイプラインとIaCを使用してECRにプッシュすることです。
[こちら](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/runtime_with_strands_and_bedrock_models.ipynb)のガイドに従って、完全なステップバイステップのチュートリアルを確認できます。

以下のコマンドでエージェントと対話できます：

```bash
curl -X POST http://127.0.0.1:8080/invocations --data '{"prompt": "What is the weather now?"}'
```

これで、Dynatrace上でBedrock AgentCore Agentsの完全なオブザーバビリティが利用可能になりました

![Tracing](./dynatrace.png)
