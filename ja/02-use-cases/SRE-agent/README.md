# SRE Agent - マルチエージェント Site Reliability Engineering アシスタント

## 概要

SRE Agent は、インフラストラクチャの問題を調査するサイト信頼性エンジニア向けのマルチエージェントシステムです。Model Context Protocol（MCP）上に構築され、Amazon Nova および Anthropic Claude モデル（Claude は Amazon Bedrock または Anthropic から直接アクセス可能）を活用するこのシステムは、問題を調査し、ログを分析し、パフォーマンスメトリクスを監視し、運用手順を実行するために協力する専門の AI エージェントを使用します。AgentCore Gateway は、MCP ツールとして利用可能なデータソースとシステムへのアクセスを提供します。この例では、本番環境向けに Amazon Bedrock AgentCore Runtime を使用してエージェントをデプロイする方法も示しています。

### ユースケースの詳細
| 情報         | 詳細                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| ユースケースタイプ       | 対話型                                                                                                                      |
| エージェントタイプ          | マルチエージェント                                                                                                                         |
| ユースケースコンポーネント | Tools（MCP ベース）、オブザーバビリティ（ログ、メトリクス）、運用 Runbook                                                             |
| ユースケース業界   | DevOps/SRE                                                                                                                          |
| 複雑度  | 上級                                                                                                                            |
| 使用 SDK            | Amazon Bedrock AgentCore SDK、LangGraph、MCP                                                                                       |

## アセット

| アセット | 説明 |
|-------|-------------|
| [デモビデオ 1（SRE-Agent CLI、VSCode 統合）](https://github.com/user-attachments/assets/c28087a6-7a97-43f0-933d-28e3f6e2eeeb) | CLI と VSCode を使用した SRE Agent によるインフラストラクチャ問題の調査と解決のウォークスルー |
| [デモビデオ 2（Cursor 統合）](https://github.com/user-attachments/assets/c1a3c26b-e982-4842-bed0-8e668d79269e) | Cursor IDE との AgentCore Gateway と SRE ツール統合のデモンストレーション |
| [AI 生成ポッドキャスト](https://github.com/user-attachments/assets/feedb9d2-064c-4c5e-a306-94941065cf82) | SRE Agent の機能とアーキテクチャを説明するオーディオディスカッション |

### ユースケースアーキテクチャ

![SRE support agent with Amazon Bedrock AgentCore](docs/images/sre-agent-architecture.png)

### ユースケースの主な機能

- **マルチエージェントオーケストレーション**: 専門エージェントがリアルタイムストリーミングでインフラストラクチャ調査に協力
- **対話型インターフェース**: 単一クエリ調査とコンテキスト保持付きインタラクティブなマルチターン会話
- **長期メモリ統合**: Amazon Bedrock Agent Memory がセッション間で永続的なユーザー好みとインフラストラクチャ知識を提供
- **ユーザーパーソナライズ**: 個々のユーザーの好みとロールに基づいたカスタマイズされたレポートとエスカレーション手順
- **MCP ベースの統合**: AgentCore Gateway が認証とヘルスモニタリング付きのセキュアな API アクセスを提供
- **専門エージェント**: Kubernetes、ログ、メトリクス、運用手順用の4つのドメイン固有エージェント
- **ドキュメントとレポート**: 各調査の監査証跡付き Markdown レポートを生成

## 詳細ドキュメント

SRE Agent システムの包括的な情報については、以下の詳細ドキュメントを参照してください：

- **[システムコンポーネント](docs/system-components.md)** - 詳細なアーキテクチャとコンポーネントの説明
- **[メモリシステム](docs/memory-system.md)** - 長期メモリ統合、ユーザーパーソナライズ、クロスセッション学習
- **[設定](docs/configuration.md)** - 環境変数、エージェント、ゲートウェイの完全な設定ガイド
- **[デプロイメントガイド](docs/deployment-guide.md)** - Amazon Bedrock AgentCore Runtime の完全なデプロイメントガイド
- **[セキュリティ](docs/security.md)** - 本番デプロイメントのセキュリティベストプラクティスと考慮事項
- **[デモ環境](docs/demo-environment.md)** - デモシナリオ、データカスタマイズ、テストセットアップ
- **[ユースケース例](docs/example-use-cases.md)** - 詳細なウォークスルーとインタラクティブなトラブルシューティング例
- **[検証](docs/verification.md)** - グラウンドトゥルース検証とレポート検証
- **[開発](docs/development.md)** - テスト、コード品質、コントリビューションガイドライン


## 前提条件

| 要件 | 説明 |
|-------------|-------------|
| Python 3.12+ と `uv` | Python ランタイムとパッケージマネージャー。[ユースケースセットアップ](#ユースケースセットアップ)を参照 |
| Amazon EC2 インスタンス | 推奨: `t3.xlarge` 以上 |
| 有効な SSL 証明書 | **重要:** Amazon Bedrock AgentCore Gateway は **HTTPS エンドポイントのみで動作します**。例えば、Amazon EC2 を [no-ip.com](https://www.noip.com/) に登録し、[letsencrypt.org](https://letsencrypt.org/) から証明書を取得するか、他のドメイン登録および SSL 証明書プロバイダーを使用できます。ドメイン名は `BACKEND_DOMAIN` として、証明書パスは[ユースケースセットアップ](#ユースケースセットアップ)セクションで必要です |
| EC2 インスタンスポート設定 | 必要なインバウンドポート（443、8011-8014）。[EC2 インスタンスポート設定](docs/ec2-port-configuration.md)を参照 |
| BedrockAgentCoreFullAccess ポリシー付き IAM ロール | 必要な権限と AgentCore サービス用のトラストポリシー。[BedrockAgentCoreFullAccess ポリシー付き IAM ロール](docs/auth.md)を参照 |
| アイデンティティプロバイダー（IDP） | JWT 認証用の Amazon Cognito、Auth0、または Okta。自動 Cognito セットアップには `deployment/setup_cognito.sh` を使用。[認証セットアップ](docs/auth.md#identity-provider-configuration)を参照 |

> **注意:** ユースケースセットアップに進む前にすべての前提条件を完了する必要があります。適切な SSL 証明書、IAM 権限、アイデンティティプロバイダー設定がないとセットアップは失敗します。

## ユースケースセットアップ

> **設定ガイド**: このプロジェクトで使用されるすべての設定ファイルの詳細については、[設定ドキュメント](docs/configuration.md)を参照してください。

```bash
# リポジトリをクローン
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples
cd amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent

# 仮想環境を作成してアクティベート
uv venv --python 3.12
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate

# SRE Agent と依存関係をインストール
uv pip install -e .

# 環境変数を設定
cp sre_agent/.env.example sre_agent/.env
# sre_agent/.env を編集し、Anthropic を直接使用する場合は Anthropic API キーを追加:
# ANTHROPIC_API_KEY=sk-ant-your-key-here
#
# 注意: 推論に Amazon Bedrock モデルを使用している場合は、
# .env ファイルに変更を加える必要はありません - デフォルトで開始できます

# OpenAPI テンプレートがバックエンドドメインで置換され .yaml として保存されます
BACKEND_DOMAIN=api.mycompany.com ./backend/openapi_specs/generate_specs.sh

# バックエンド起動制御変数を設定（バックエンド起動をスキップするには 0、false、または no に設定）
# これはバックエンド API サーバーが別の場所で既に実行されている場合に便利です
# 例えば、Workshop Studio アカウントや共有環境など
START_API_BACKEND=${START_API_BACKEND:-1}

if [[ "$START_API_BACKEND" =~ ^(1|true|yes)$ ]]; then
  echo "Starting backend API servers..."

  # サーバーバインディング用の EC2 インスタンスプライベート IP を取得
  TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s)
  PRIVATE_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    -s http://169.254.169.254/latest/meta-data/local-ipv4)

  # SSL 付きでデモバックエンドサーバーを起動
  cd backend
  ./scripts/start_demo_backend.sh \
    --host $PRIVATE_IP  \
    --ssl-keyfile /opt/ssl/privkey.pem \
    --ssl-certfile /opt/ssl/fullchain.pem
  cd ..
else
  echo "Skipping backend API server startup (START_API_BACKEND is set to $START_API_BACKEND)"
fi

# AgentCore Gateway を設定
cd gateway
cp config.yaml.example config.yaml
# config.yaml を編集してパラメータ値を更新
# ファイルには各パラメータの説明コメントが含まれています
# 更新すべき主なパラメータ:
#   - account_id: AWS アカウント ID
#   - region: AWS リージョン
#   - role_name: BedrockAgentCoreFullAccess 付き IAM ロール
#     テスト用: 現在の EC2/ノートブックロールを使用可能（実行: aws sts get-caller-identity）
#     本番用: 専用のゲートウェイロールを使用（推奨）
#   - user_pool_id と client_id: Cognito セットアップから
#   - s3_bucket: OpenAPI スキーマ用の S3 バケット
# 詳細なパラメータ説明は gateway/config.yaml を参照

# AgentCore Gateway を作成して設定
./create_gateway.sh
./mcp_cmds.sh
cd ..

# エージェント設定でゲートウェイ URI を更新
GATEWAY_URI=$(cat gateway/.gateway_uri)
sed -i "s|uri: \".*\"|uri: \"$GATEWAY_URI\"|" sre_agent/config/agent_config.yaml

# ゲートウェイアクセストークンを .env ファイルにコピー
sed -i '/^GATEWAY_ACCESS_TOKEN=/d' sre_agent/.env
echo "GATEWAY_ACCESS_TOKEN=$(cat gateway/.access_token)" >> sre_agent/.env

# メモリシステムを初期化しユーザー好みを追加
uv run python scripts/manage_memories.py update

# 注意: メモリシステムが準備完了になるまで 10-12 分かかります
# 10 分後にメモリステータスを確認:
uv run python scripts/manage_memories.py list

# メモリが準備完了と表示されたら、好みがロードされていることを確認するために再度 update を実行:
uv run python scripts/manage_memories.py update
```

> **ローカルセットアップ完了**: SRE Agent は EC2 インスタンスでローカルに実行され、AgentCore Gateway と Memory サービスを使用しています。このエージェントを AgentCore Runtime にデプロイしてアプリケーション（チャットボット、Slack ボットなど）に統合したい場合は、以下の[開発から本番デプロイメントフロー](#開発から本番デプロイメントフロー)セクションの手順に従ってください。

## 実行手順

### メモリ強化パーソナライズ調査

SRE Agent には、ユーザーの好みに基づいて調査をパーソナライズする高度なメモリシステムが含まれています。システムには [`scripts/user_config.yaml`](scripts/user_config.yaml) に2つのユーザーペルソナが事前設定されています：

- **Alice**: 包括的な分析とチームアラート付きの技術的な詳細調査
- **Carol**: ビジネスインパクト分析と戦略的アラート付きのエグゼクティブ向け調査

異なるユーザー ID で調査を実行すると、エージェントは同様の技術的発見を生成しますが、各ユーザーの好みに応じて提示します：

```bash
# Alice の詳細な技術調査
USER_ID=Alice sre-agent --prompt "API response times have degraded 3x in the last hour" --provider bedrock

# Carol のエグゼクティブ向け調査
USER_ID=Carol sre-agent --prompt "API response times have degraded 3x in the last hour" --provider bedrock
```

両方のコマンドは同じ技術的問題を特定しますが、異なる方法で提示します：
- **Alice** はステップバイステップのトラブルシューティングとチーム通知付きの詳細な技術分析を受け取ります
- **Carol** は迅速なエスカレーションタイムライン付きのビジネスインパクトに焦点を当てたエグゼクティブサマリーを受け取ります

メモリシステムが同一のインシデントをどのようにパーソナライズするかの詳細な比較については、以下を参照してください: [**メモリシステムレポート比較**](docs/examples/Memory_System_Analysis_User_Personalization_20250802_162648.md)

### 単一クエリモード
```bash
# 特定の Pod の問題を調査
sre-agent --prompt "Why are the payment-service pods crash looping?"

# パフォーマンス低下を分析
sre-agent --prompt "Investigate high latency in the API gateway over the last hour"

# エラーパターンを検索
sre-agent --prompt "Find all database connection errors in the last 24 hours"
```

### インタラクティブモード
```bash
# インタラクティブな会話を開始
sre-agent --interactive

# インタラクティブモードで利用可能なコマンド:
# /help     - 利用可能なコマンドを表示
# /agents   - 利用可能な専門エージェントをリスト
# /history  - 会話履歴を表示
# /save     - 現在の会話を保存
# /clear    - 会話履歴をクリア
# /exit     - インタラクティブセッションを終了
```

#### 高度なオプション
```bash
# Amazon Bedrock を使用
sre-agent --provider bedrock --query "Check cluster health"

# 調査レポートをカスタムディレクトリに保存
sre-agent --output-dir ./investigations --query "Analyze memory usage trends"

# 特定のプロファイルで Amazon Bedrock を使用
AWS_PROFILE=production sre-agent --provider bedrock --interactive
```

## 開発から本番デプロイメントフロー

SRE Agent は、ローカル開発から Amazon Bedrock AgentCore Runtime への本番までの構造化されたデプロイメントプロセスに従います。詳細な手順については、**[デプロイメントガイド](docs/deployment-guide.md)**を参照してください。

```
STEP 1: ローカル開発
┌─────────────────────────────────────────────────────────────────────┐
│  Python パッケージ (sre_agent/) を開発                                │
│  └─> CLI でローカルテスト: uv run sre-agent --prompt "..."         │
│      └─> エージェントが MCP プロトコル経由で AgentCore Gateway に接続       │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
STEP 2: コンテナ化
┌─────────────────────────────────────────────────────────────────────┐
│  agent_runtime.py（FastAPI サーバーラッパー）を追加                      │
│  └─> Dockerfile を作成（AgentCore 用 ARM64）                        │
│      └─> deployment/build_and_deploy.sh スクリプトを使用                 │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
STEP 3: ローカルコンテナテスト
┌─────────────────────────────────────────────────────────────────────┐
│  ビルド: LOCAL_BUILD=true ./deployment/build_and_deploy.sh           │
│  └─> 実行: docker run -p 8080:8080 sre_agent:latest                  │
│      └─> テスト: curl -X POST http://localhost:8080/invocations       │
│          └─> コンテナは同じ AgentCore Gateway に接続           │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
STEP 4: 本番デプロイメント
┌─────────────────────────────────────────────────────────────────────┐
│  ビルド＆プッシュ: ./deployment/build_and_deploy.sh                     │
│  └─> Amazon ECR にコンテナをプッシュ                                 │
│      └─> deployment/deploy_agent_runtime.py が AgentCore にデプロイ    │
│          └─> テスト: uv run python deployment/invoke_agent_runtime.py │
│              └─> 本番エージェントは本番 Gateway を使用           │
└─────────────────────────────────────────────────────────────────────┘

ポイント:
• コアエージェントコード (sre_agent/) は変更なし
• deployment/ フォルダにすべてのデプロイメント固有ユーティリティを格納
• 環境設定により同じエージェントがローカルと本番で動作
• AgentCore Gateway がすべての段階で MCP ツールアクセスを提供
```

## Amazon Bedrock AgentCore Runtime へのエージェントのデプロイ

本番デプロイメントでは、SRE Agent を Amazon Bedrock AgentCore Runtime に直接デプロイできます。これにより、エンタープライズグレードのセキュリティとモニタリングを備えたスケーラブルなマネージド環境でエージェントを実行できます。

AgentCore Runtime デプロイメントは以下をサポートします：
- 自動スケーリング付き**コンテナベースのデプロイメント**
- **複数の LLM プロバイダー**（Amazon Bedrock または Anthropic Claude）
- トラブルシューティングと開発用の**デバッグモード**
- 異なるデプロイメントステージ用の**環境ベースの設定**
- AWS IAM と環境変数による**セキュアな認証情報管理**

ローカルテスト、コンテナビルド、本番デプロイメントを含む完全なステップバイステップの手順については、**[デプロイメントガイド](docs/deployment-guide.md)**を参照してください。

## AgentCore オブザーバビリティ

AgentCore Runtime にデプロイされたエージェントにオブザーバビリティを追加するのは、オブザーバビリティプリミティブを使用して簡単です。これにより、Amazon CloudWatch を通じてメトリクス、トレース、ログによる包括的なモニタリングが可能になります。

### オブザーバビリティのセットアップ

#### 1. OpenTelemetry パッケージの追加

必要な OpenTelemetry パッケージは既に `pyproject.toml` に含まれています：

```toml
dependencies = [
    # ... other dependencies ...
    "opentelemetry-instrumentation-langchain",
    "aws-opentelemetry-distro~=0.10.1",
]
```

#### 2. エージェントのオブザーバビリティ設定

[Amazon Bedrock AgentCore オブザーバビリティ設定ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html#observability-configure-builtin)に従って、Amazon CloudWatch でメトリクスを有効にします。

#### 3. OpenTelemetry インストゥルメンテーションの有効化

コンテナを起動するときは、`opentelemetry-instrument` ユーティリティを使用してアプリケーションを自動的にインストゥルメントします。これは Dockerfile で設定されています：

```dockerfile
# OpenTelemetry インストゥルメンテーションでアプリケーションを実行
CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "sre_agent.agent_runtime:app", "--host", "0.0.0.0", "--port", "8080"]
```

### メトリクスとトレースの表示

オブザーバビリティを有効にしてデプロイすると、以下を通じてエージェントのパフォーマンスを監視できます：

- **Amazon CloudWatch Metrics**: リクエストレート、レイテンシ、エラーレートを表示
- **AWS X-Ray Traces**: 分散トレースを分析してリクエストフローを理解
- **CloudWatch Logs**: デバッグと分析のための構造化ログにアクセス

![Agent Metrics Dashboard](docs/images/agent-metrics.gif)

オブザーバビリティプリミティブは以下を自動的にキャプチャします：
- LLM 呼び出しメトリクス（トークン、レイテンシ、モデル使用状況）
- ツール実行トレース（期間、成功/失敗）
- メモリ操作（取得、保存）
- すべてのエージェントコンポーネントにわたるエンドツーエンドのリクエストトレーシング

## メンテナンスと運用

### バックエンドサーバーの再起動とアクセストークンの更新

Amazon Bedrock AgentCore Gateway との接続を維持するために、定期的にバックエンドサーバーを再起動してアクセストークンを更新する必要があります。ゲートウェイ設定スクリプトを実行します：

```bash
# 重要: 仮想環境内から実行してください
source .venv/bin/activate  # まだアクティベートしていない場合
./scripts/configure_gateway.sh
```

**このスクリプトが行うこと：**
- クリーンな再起動のために**実行中のバックエンドサーバーを停止**
- AgentCore Gateway 認証用の**新しいアクセストークンを生成**
- 適切な SSL バインディングのために **EC2 インスタンスのプライベート IP を取得**
- SSL 証明書（HTTPS）または HTTP フォールバック付きで**バックエンドサーバーを起動**
- `gateway/.gateway_uri` からエージェント設定の**ゲートウェイ URI を更新**
- エージェント認証のために `.env` ファイルの**アクセストークンを更新**

**重要:** アクセストークンは 24 時間後に期限切れになるため、このスクリプトを **24 時間ごとに**実行する必要があります。トークンを更新しない場合：
- SRE エージェントは AgentCore ゲートウェイへの接続を失います
- MCP ツールは利用できなくなります（Kubernetes、ログ、メトリクス、Runbook API）
- エージェントがバックエンドサービスにアクセスできないため、調査が失敗します

詳細については、[configure_gateway.sh](scripts/configure_gateway.sh) スクリプトを参照してください。

### ゲートウェイ接続問題のトラブルシューティング

「gateway connection failed」または「MCP tools unavailable」エラーが発生した場合：
1. アクセストークンが期限切れかどうかを確認（24 時間制限）
2. 認証を更新するために `./scripts/configure_gateway.sh` を実行（仮想環境内から）
3. `ps aux | grep python` でバックエンドサーバーが実行中か確認
4. HTTPS を使用している場合は SSL 証明書の有効性を確認

## クリーンアップ手順

### 完全な AWS リソースクリーンアップ

すべての AWS リソース（Gateway、Runtime、ローカルファイル）の完全なクリーンアップ：

```bash
# 完全なクリーンアップ - AWS リソースとローカルファイルを削除
./scripts/cleanup.sh

# またはカスタム名で
./scripts/cleanup.sh --gateway-name my-gateway --runtime-name my-runtime

# 確認プロンプトなしで強制クリーンアップ
./scripts/cleanup.sh --force
```

このスクリプトは以下を行います：
- バックエンドサーバーを停止
- AgentCore Gateway とそのすべてのターゲットを削除
- メモリリソースを削除
- AgentCore Runtime を削除
- 生成されたファイル（ゲートウェイ URI、トークン、エージェント ARN、メモリ ID）を削除

### 手動ローカルクリーンアップのみ

AWS リソースに触れずにローカルファイルのみをクリーンアップしたい場合：

```bash
# すべてのデモサーバーを停止
cd backend
./scripts/stop_demo_backend.sh
cd ..

# 生成されたファイルのみをクリーンアップ
rm -rf gateway/.gateway_uri gateway/.access_token
rm -rf deployment/.agent_arn .memory_id

# 注意: .env、.venv、reports/ は開発の継続性のために保持されます
```

## 免責事項
このリポジトリで提供される例は、実験的および教育目的のみを意図しています。概念と技術を示していますが、本番環境での直接使用を意図していません。[プロンプトインジェクション](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html)から保護するために Amazon Bedrock Guardrails を設置してください。

**重要な注意**: [`backend/data`](backend/data) 内のデータは合成的に生成されており、backend ディレクトリには実際の SRE エージェントバックエンドがどのように機能するかを示すスタブサーバーが含まれています。本番環境では、これらの実装を実際のシステムに接続し、ベクトルデータベースを使用し、他のデータソースと統合する実際の実装に置き換える必要があります。
