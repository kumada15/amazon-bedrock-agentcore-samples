# Amazon Bedrock AgentCore Runtime 用 SRE エージェントデプロイメントガイド

このガイドでは、ローカルテストから Amazon Bedrock AgentCore Runtime への本番デプロイメントまで、SRE エージェントの完全なデプロイメントプロセスについて説明します。

## 前提条件

- 適切な権限で設定された AWS CLI
- Docker がインストールされ実行中
- UV パッケージマネージャーがインストール済み
- Python 3.12 以上
- Amazon Bedrock AgentCore Runtime へのアクセス
- `BedrockAgentCoreFullAccess` ポリシーと適切な信頼ポリシーを持つ IAM ロール（[認証セットアップ](auth.md)を参照）

## 環境設定

SRE エージェントは設定に環境変数を使用します。これらは適切なディレクトリの `.env` ファイルから読み込まれます：

- **CLI テスト**: 環境変数は `sre_agent/.env` から読み込まれる
- **コンテナビルド**: 環境変数は `deployment/.env` から読み込まれる
- **Docker プラットフォーム**: ローカルビルドは `Dockerfile.x86_64`（linux/amd64）を使用、AgentCore デプロイメントは `Dockerfile`（linux/arm64）を使用

### 必須環境変数

これらの変数を含む適切な `.env` ファイルを作成してください：

**sre_agent/.env 用（CLI テストとローカルコンテナ実行）:**
```bash
GATEWAY_ACCESS_TOKEN=your_gateway_access_token
LLM_PROVIDER=bedrock
DEBUG=false
# Anthropic プロバイダーを使用する場合は、以下も追加：
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**deployment/.env 用（コンテナビルドとデプロイメント）:**
```bash
GATEWAY_ACCESS_TOKEN=your_gateway_access_token
ANTHROPIC_API_KEY=sk-ant-your-key-here
# これらはビルド/デプロイ時に環境変数で上書き可能
```

**注意**: `--env-file` を使用する場合、すべての必須変数は .env ファイルに含める必要があります。`-e` は .env ファイルの特定の変数を上書きする場合のみ使用してください。

## デプロイメント順序

### フェーズ 1：CLI でのローカルテスト

まず、CLI を使用して SRE エージェントをローカルでテストし、正しく動作することを確認します。

#### 1.1 環境セットアップ

環境ファイルを作成して設定します：
```bash
# CLI 環境ファイルをセットアップ
cp sre_agent/.env.example sre_agent/.env
# sre_agent/.env を編集して設定を行う
```

**注意**: 環境変数は実行時に上書きできますが、.env ファイルがあることで一貫した設定が保証されます。

#### 1.2 Bedrock（デフォルト）で CLI をテスト

```bash
# デフォルトの Bedrock プロバイダーでテスト
uv run sre-agent --prompt "list the pods in my infrastructure"

# デバッグ出力を有効にしてテスト
uv run sre-agent --prompt "list the pods in my infrastructure" --debug

# 特定のプロバイダーでテスト
uv run sre-agent --prompt "list the pods in my infrastructure" --provider bedrock --debug
```

#### 1.3 Anthropic プロバイダーで CLI をテスト

```bash
# .env ファイルに ANTHROPIC_API_KEY が設定されていることを確認してから：
uv run sre-agent --prompt "list the pods in my infrastructure" --provider anthropic --debug
```

**期待される出力**: エージェントがリクエストを処理し、適切な専門エージェントにルーティングし、インフラストラクチャ情報を返すのが確認できるはずです。

### フェーズ 2：ローカルコンテナテスト

CLI テストが成功したら、エージェントをコンテナとしてビルドしてローカルでテストします。

#### 2.1 ローカルコンテナをビルド

ビルドスクリプトはオプションの ECR リポジトリ名を受け付け、ターゲットプラットフォームに基づいて異なる Dockerfile を使用します：

- **ローカルビルド**（LOCAL_BUILD=true）: linux/amd64 プラットフォーム用の `Dockerfile.x86_64` を使用
- **AgentCore ビルド**（デフォルト）: linux/arm64 プラットフォーム用の `Dockerfile` を使用（AgentCore で必要）

```bash
# カスタム名でローカルテスト用コンテナをビルド
LOCAL_BUILD=true ./deployment/build_and_deploy.sh my_custom_sre_agent

# すべてのオプションのヘルプを表示
./deployment/build_and_deploy.sh --help
```

#### 2.2 Bedrock でローカルコンテナをテスト

デフォルトの Bedrock プロバイダーでコンテナをローカル実行：
```bash
# sre_agent ディレクトリの .env ファイルを使用（推奨）
# sre_agent/.env に LLM_PROVIDER=bedrock が設定されていることを確認
docker run -p 8080:8080 --env-file sre_agent/.env my_custom_sre_agent:latest

# 代替：明示的な環境変数で（.env ファイルを使用しない場合）
docker run -p 8080:8080 \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_PROFILE=default \
  -e GATEWAY_ACCESS_TOKEN=your_token \
  -e LLM_PROVIDER=bedrock \
  my_custom_sre_agent:latest

# デバッグを有効化（.env ファイルの DEBUG 設定を上書き）
docker run -p 8080:8080 --env-file sre_agent/.env -e DEBUG=true my_custom_sre_agent:latest
```

**注意**: コンテナ名はビルド時に指定した ECR リポジトリ名と一致します。

#### 2.3 Anthropic でローカルコンテナをテスト

```bash
# .env ファイルを使用（sre_agent/.env に LLM_PROVIDER=anthropic が設定されていることを確認）
docker run -p 8080:8080 --env-file sre_agent/.env my_custom_sre_agent:latest

# デバッグを有効化（.env ファイルの DEBUG 設定を上書き）
docker run -p 8080:8080 \
  --env-file sre_agent/.env \
  -e DEBUG=true \
  my_custom_sre_agent:latest
```

**注意**: anthropic プロバイダーを使用する場合、`sre_agent/.env` ファイルに `LLM_PROVIDER=anthropic` と `ANTHROPIC_API_KEY` の両方が設定されていることを確認してください。

#### 2.4 curl でコンテナをテスト

実行中のコンテナをテスト：
```bash
# 基本テスト
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "prompt": "list the pods in my infrastructure"
    }
  }'

# ヘルスチェック
curl http://localhost:8080/ping
```

**期待される出力**: コンテナはエージェントのレスポンスを含む JSON で応答するはずです。

### フェーズ 3：Amazon Bedrock AgentCore Runtime へのデプロイメント

ローカルコンテナテストが成功したら、AgentCore にデプロイします。

#### 3.1 Bedrock で AgentCore にデプロイ

```bash
# カスタムリポジトリ名とデフォルト設定でデプロイ（deployment/.env から読み込み）
./deployment/build_and_deploy.sh my_custom_sre_agent

# デバッグを有効にしてデプロイ（環境変数で上書き）
DEBUG=true ./deployment/build_and_deploy.sh my_custom_sre_agent

# 特定のプロバイダーでデプロイ
LLM_PROVIDER=bedrock DEBUG=true ./deployment/build_and_deploy.sh my_custom_sre_agent
```

#### 3.2 Anthropic で AgentCore にデプロイ

```bash
# Anthropic プロバイダーでデプロイ（deployment/.env に ANTHROPIC_API_KEY があることを確認）
LLM_PROVIDER=anthropic ./deployment/build_and_deploy.sh my_custom_sre_agent

# Anthropic とデバッグを有効にしてデプロイ
DEBUG=true LLM_PROVIDER=anthropic ./deployment/build_and_deploy.sh my_custom_sre_agent

# 環境変数で API キーを上書き
LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-your-key ./deployment/build_and_deploy.sh my_custom_sre_agent
```

**ビルドスクリプトの使用方法:**
```bash
# すべての利用可能なオプションを表示
./deployment/build_and_deploy.sh --help

# スクリプトは 1 つのオプション引数を受け付け：ECR リポジトリ名
# デフォルトのリポジトリ名は 'sre_agent'
# 注意：リポジトリ名にはハイフン（-）ではなくアンダースコア（_）を使用
```

**期待される出力**: スクリプトはビルド、ECR へのプッシュ、AgentCore Runtime へのデプロイを行います。

#### 3.3 AgentCore デプロイメントをテスト

invoke スクリプトを使用してデプロイされたエージェントをテスト：
```bash
# デプロイされたエージェントをテスト
uv run python deployment/invoke_agent_runtime.py \
  --prompt "list the pods in my infrastructure"

# カスタムランタイム ARN でテスト
uv run python deployment/invoke_agent_runtime.py \
  --prompt "list the pods in my infrastructure" \
  --runtime-arn "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/your-runtime-id"
```

## 環境変数リファレンス

### コア設定

| 変数 | 説明 | デフォルト | 必須 |
|----------|-------------|---------|----------|
| `GATEWAY_ACCESS_TOKEN` | ゲートウェイ認証トークン | - | はい |
| `BACKEND_API_KEY` | クレデンシャルプロバイダー用のバックエンド API キー | - | はい（ゲートウェイセットアップ） |
| `LLM_PROVIDER` | 言語モデルプロバイダー | `bedrock` | いいえ |
| `ANTHROPIC_API_KEY` | Anthropic API キー | - | anthropic プロバイダーのみ |
| `DEBUG` | デバッグログとトレースを有効化 | `false` | いいえ |

### AWS 設定

| 変数 | 説明 | デフォルト | 必須 |
|----------|-------------|---------|----------|
| `AWS_REGION` | デプロイメント用の AWS リージョン | `us-east-1` | いいえ |
| `AWS_PROFILE` | 使用する AWS プロファイル | - | いいえ |
| `RUNTIME_NAME` | AgentCore ランタイム名 | ECR リポジトリ名 | いいえ |

### ビルドスクリプト設定

| 変数 | 説明 | デフォルト | 備考 |
|----------|-------------|---------|-------|
| `LOCAL_BUILD` | ローカルテスト専用でビルド | `false` | true の場合 Dockerfile.x86_64 を使用 |
| `PLATFORM` | ターゲットプラットフォーム | `arm64` | AgentCore は arm64 が必要、ローカルでは x86_64 を使用 |
| `ECR_REPO_NAME` | ECR リポジトリ名 | `sre_agent` | コマンドライン引数として渡すことも可能 |

## デバッグモードの使用

### CLI デバッグモード
```bash
# --debug フラグでデバッグを有効化
uv run sre-agent --prompt "your query" --debug

# または環境変数で
DEBUG=true uv run sre-agent --prompt "your query"
```

### コンテナデバッグモード
```bash
# デバッグ付きローカルコンテナ（.env ファイルの DEBUG 設定を上書き）
docker run -p 8080:8080 --env-file sre_agent/.env -e DEBUG=true my_custom_sre_agent:latest

# デバッグ付き AgentCore デプロイメント
DEBUG=true ./deployment/build_and_deploy.sh my_custom_sre_agent
```

### デバッグ出力の例

**デバッグモードなし:**
```
🤖 Multi-Agent System: Processing...
🧭 Supervisor: Routing to kubernetes_agent
🔧 Kubernetes Agent:
   💡 Full Response: Here are the pods in your infrastructure...
💬 Final Response: I found 5 pods running in your infrastructure...
```

**デバッグモードあり:**
```
🤖 Multi-Agent System: Processing...

MCP tools loaded: 12
  - kubernetes-list-pods: List all pods in the cluster...
  - kubernetes-get-pod: Get details of a specific pod...

🧭 Supervisor: Routing to kubernetes_agent
🔧 Kubernetes Agent:
   🔍 DEBUG: agent_messages = 3
   📋 Found 3 trace messages:
      1. AIMessage: I'll help you list the pods...
   📞 Calling tools:
      kubernetes-list-pods(
        namespace=None
      ) [id: call_123]
   🛠️  kubernetes-list-pods [id: call_123]:
      {"pods": [...]}
   💡 Full Response: Here are the pods in your infrastructure...
💬 Final Response: I found 5 pods running in your infrastructure...
```

## プロバイダー設定

### Amazon Bedrock の使用（デフォルト）
```bash
# CLI（sre_agent/.env から読み込み）
uv run sre-agent --provider bedrock --prompt "your query"

# コンテナ（sre_agent/.env から LLM_PROVIDER=bedrock を読み込み）
docker run -p 8080:8080 --env-file sre_agent/.env my_custom_sre_agent:latest

# デプロイメント（deployment/.env から読み込み、環境変数で上書き可能）
LLM_PROVIDER=bedrock ./deployment/build_and_deploy.sh my_custom_sre_agent
```

### Anthropic Claude の使用
```bash
# CLI（sre_agent/.env から LLM_PROVIDER と ANTHROPIC_API_KEY を読み込み）
uv run sre-agent --provider anthropic --prompt "your query"

# コンテナ（sre_agent/.env から LLM_PROVIDER=anthropic と ANTHROPIC_API_KEY を読み込み）
docker run -p 8080:8080 --env-file sre_agent/.env my_custom_sre_agent:latest

# デプロイメント（deployment/.env から読み込み、環境変数で上書き可能）
LLM_PROVIDER=anthropic ./deployment/build_and_deploy.sh my_custom_sre_agent

# 環境変数で API キーを上書き（deployment/.env にない場合）
LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-xxx ./deployment/build_and_deploy.sh my_custom_sre_agent
```

## トラブルシューティング

### よくある問題

1. **ゲートウェイトークンの問題**
   ```bash
   # トークンが設定されていることを確認
   echo $GATEWAY_ACCESS_TOKEN
   # または .env ファイルを確認
   cat sre_agent/.env
   ```

2. **プロバイダー設定**
   ```bash
   # Anthropic の場合、API キーが有効であることを確認
   echo $ANTHROPIC_API_KEY
   # シンプルな呼び出しで API キーをテスト
   ```

3. **デバッグ情報**
   ```bash
   # デバッグモードを有効にして詳細ログを確認
   DEBUG=true uv run sre-agent --prompt "test"
   ```

4. **コンテナの問題**
   ```bash
   # コンテナログを確認
   docker logs <container_id>
   # デバッグで実行
   docker run -e DEBUG=true ... my_custom_sre_agent:latest
   ```

### 検証手順

1. **CLI 動作確認**: エージェントがローカルでクエリに応答
2. **コンテナ動作確認**: コンテナが curl リクエストに応答
3. **AgentCore 動作確認**: デプロイされたエージェントが invoke スクリプト経由で応答

## クイックスタート：コマンドシーケンスをコピー&ペースト

`my_custom_sre_agent` を使用した完全なデプロイメントのために、これらのコマンドを順番にコピー&ペーストしてください：

### 1. ローカルコンテナをビルド
```bash
LOCAL_BUILD=true ./deployment/build_and_deploy.sh my_custom_sre_agent
```

### 2. ローカルコンテナをテスト（Bedrock）
```bash
docker run -p 8080:8080 --env-file sre_agent/.env my_custom_sre_agent:latest
```

### 3. curl でテスト
```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "prompt": "list the pods in my infrastructure"
    }
  }'
```

### 4. AgentCore にデプロイ
```bash
./deployment/build_and_deploy.sh my_custom_sre_agent
```

### 5. AgentCore デプロイメントをテスト
```bash
uv run python deployment/invoke_agent_runtime.py \
  --prompt "list the pods in my infrastructure"
```

## ベストプラクティス

1. **開発**: 常にまずローカルでテスト
2. **環境ファイル**: 一貫した設定のために `.env` ファイルを使用
3. **デバッグモード**: トラブルシューティング時にデバッグモードを有効化
4. **プロバイダーテスト**: 両方を使用する場合は Bedrock と Anthropic の両プロバイダーをテスト
5. **段階的デプロイメント**: 本番環境の前にステージング環境にデプロイ
