# Amazon Bedrock Agent と OpenLIT の統合

このサンプルには、[OpenLIT](https://openlit.io) オブザーバビリティを備えた [Bedrock AgentCore Agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) 上に構築されたパーソナルアシスタントエージェントのデモが含まれています。


## 前提条件

- Python 3.11 以上
- セルフホスト OpenLIT
- 適切な権限を持つ AWS アカウント
- 以下の AWS サービスへのアクセス：
   - Amazon Bedrock


## OpenLIT インストゥルメンテーション

> [!TIP]
> 詳細なセットアップ手順、設定オプション、高度なユースケースについては、[OpenLIT ドキュメント](https://docs.openlit.io/latest/openlit/quickstart-ai-observability)を参照してください。

Bedrock AgentCore には[オブザーバビリティ](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)サポートが標準で備わっています。
したがって、OpenLIT で完全な LLM とエージェントオブザーバビリティを実現するには、[OpenTelemetry SDK](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md#sdk) を登録するだけで済みます。

このプロセスを簡素化し、すべての複雑さを [openlit_config.py](./openlit_config.py) 内に隠しています。
OpenLIT にデータを送信するには、OTEL_ENDPOINT 環境変数を OTLP を取り込む OpenLIT URL で設定できます。例：http://127.0.0.1:4318。

### 設定オプション

`OTEL_ENDPOINT` 環境変数を OpenLIT OTLP エンドポイントで設定します。OpenLIT はオープンソースのセルフホストソリューションであるため、**認証や OTLP ヘッダーは不要です**：

```bash
export OTEL_ENDPOINT=http://your-openlit-host:4318
```


## 使用方法

### AWS キーの設定

[Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)に従って、正しいポリシーで AWS ロールを設定してください。
その後、ターミナルで以下のコマンドを実行して、環境変数に AWS キーを設定できます：

```bash
export AWS_ACCESS_KEY_ID=your_api_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=your_region
```

このサンプルで使用するモデル `us.anthropic.claude-3-7-sonnet-20250219-v1:0` にアカウントがアクセスできることを確認してください。モデルへのアクセスを有効にする方法については、[Amazon Bedrock ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-permissions.html)を参照してください。
環境変数 `BEDROCK_MODEL_ID` を設定して、使用するモデルを変更できます。

### OpenLIT のセットアップ

続行する前に、テレメトリデータを受信するために OpenLIT をデプロイする必要があります。以下のデプロイオプションのいずれかを選択してください：

#### オプション 1: Docker デプロイ（テスト用最速）

Docker Compose を使用して OpenLIT をデプロイ - 開始するための最も簡単なアプローチ：

```bash
# OpenLIT リポジトリをクローン
git clone https://github.com/openlit/openlit.git
cd openlit

# OpenLIT サービスを起動
docker compose up -d
```

これにより、OpenLIT が以下で起動します：
- UI は `http://localhost:3000` でアクセス可能
- OTEL エンドポイントは `http://localhost:4318`

エージェントが OpenLIT にアクセスするには、エージェントが到達できるマシンにデプロイしてください：
1. パブリック IP を持つ EC2 インスタンスまたはコンテナサービスにデプロイ（必要な場合）
2. ポート 4318 がアクセス可能であることを確認（インバウンドトラフィックを許可するようにセキュリティグループを設定）
3. 設定で適切なエンドポイント URL を使用

#### オプション 2: Kubernetes デプロイ（本番環境対応）

本番環境では、Helm を使用して Kubernetes に OpenLIT をデプロイ：

```bash
# OpenLIT Helm リポジトリを追加
helm repo add openlit https://openlit.github.io/helm-charts
helm repo update

# OpenLIT をインストール
helm install openlit openlit/openlit
```

**デフォルト設定:**
- デフォルトで、OpenLIT はパブリック IP を持つ LoadBalancer サービスを作成
- OTEL エンドポイントは `http://<load-balancer-ip>:4318` でアクセス可能
- UI は `http://<load-balancer-ip>:3000` でアクセス可能

**VPC/プライベート設定:**

OpenLIT を VPC 内でプライベートに保つことを好む場合（本番環境では推奨）：

```bash
# ClusterIP の場合（内部のみ）
helm install openlit openlit/openlit \
  --set service.type=ClusterIP

# AWS 内部ロードバランサーの場合
helm install openlit openlit/openlit \
  --set service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-internal"="true"
```

VPC デプロイメントでは、以下を確認してください：
- エージェントと OpenLIT が通信できる（同じ VPC、VPC ピアリング、または Transit Gateway）
- セキュリティグループがポート 4318 でエージェントと OpenLIT 間のトラフィックを許可
- 内部エンドポイントを使用（例：`http://openlit.default.svc.cluster.local:4318` または内部ロードバランサー DNS）

#### OTEL エンドポイントの設定

OpenLIT がデプロイされたら、エンドポイントで環境変数を設定します：

```bash
# 例：
# パブリック IP を持つ Docker：
export OTEL_ENDPOINT=http://<ec2-public-ip>:4318

# パブリック LoadBalancer を持つ Kubernetes：
export OTEL_ENDPOINT=http://<load-balancer-ip>:4318

# VPC/内部の Kubernetes：
export OTEL_ENDPOINT=http://<internal-dns-or-ip>:4318
```

> **注意**: OpenLIT はオープンソースのセルフホストソリューションであり、デフォルトではテレメトリを送信するための認証や API キーは不要ですが、設定することは可能です。OTLP エンドポイントのみが必要です。

詳細なデプロイ手順については、[OpenLIT インストールガイド](https://docs.openlit.io/latest/openlit/installation)を参照してください。

### オプション設定

アプリケーション名と環境をカスタマイズできます：

```bash
export OTEL_SERVICE_NAME=bedrock-agentcore-agent
export OTEL_DEPLOYMENT_ENVIRONMENT=production
```

### アプリの実行

以下のコマンドでサンプルを開始できます：

```bash
uv run main.py
```

これにより、エージェントの要件を処理するために必要な `/invocations` エンドポイントを実装した、ポート `8080` でリッスンする HTTP サーバーが作成されます。

エージェントはデプロイ準備が整いました。ベストプラクティスは、CI/CD パイプラインと IaC を使用してコードをコンテナとしてパッケージ化し、ECR にプッシュすることです。
完全なステップバイステップチュートリアルについては、[こちら](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/runtime_with_strands_and_bedrock_models.ipynb)のガイドに従ってください。

以下のコマンドでエージェントと対話できます：

```bash
curl -X POST http://127.0.0.1:8080/invocations --data '{"prompt": "What is the weather now?"}'
```

![ダッシュボード](./openlit-dashboard.jpg)

![トレーシング](./openlit-traces.png)
