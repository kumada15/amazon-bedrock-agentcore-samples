# 生成ファイルと設定ファイル

このドキュメントでは、チュートリアルで使用されるすべての生成ファイル、設定ファイル、および隠しファイルについて説明します。これらのファイルはセットアップ、デプロイ、または実行時に作成され、通常はバージョン管理にコミットすべきではありません。

## ファイル概要

**注意:** 以下にリストされているすべてのファイルは `.gitignore` にあり、バージョン管理にコミットしてはいけません。

| ファイル | 場所 | 目的 | 生成元 |
|------|----------|---------|--------------|
| `.env` | チュートリアルルート | ローカル開発用の環境変数 | 手動/ユーザー |
| `.bedrock_agentcore.yaml` | チュートリアルルート | AgentCore Runtime 設定キャッシュ | bedrock-agentcore-starter-toolkit |
| `.deployment_metadata.json` | `scripts/` | デプロイ情報（エージェント ID、ARN など） | `deploy_agent.py` |
| `.env.backup` | `scripts/` | 前の .env ファイルのバックアップ | `setup_braintrust.sh` |
| `Dockerfile` | チュートリアルルート | Docker コンテナ定義 | bedrock-agentcore-starter-toolkit |
| `.dockerignore` | チュートリアルルート | Docker ビルド除外設定 | bedrock-agentcore-starter-toolkit |

## 詳細なファイル説明

---

### `.env`
**場所:** チュートリアルルート（`simple-dual-observability/.env`）

**目的:** AWS リージョンとオプションの Braintrust 認証情報を含む、ローカル開発およびデプロイ用の環境変数を保存します。

**生成元:** ユーザーによる手動作成またはサンプルテンプレートからコピー

**典型的な内容:**
```bash
# AWS 設定
AWS_REGION=us-east-1

# Braintrust 設定（オプション）
BRAINTRUST_API_KEY=bt-xxxxxxxxxxxxxxxxxxxxxxxx
BRAINTRUST_PROJECT_ID=your-project-id
```

**使用方法:**
- `setup_all.sh` スクリプトによって自動的に読み込まれる
- デプロイスクリプトがエージェントを設定するために使用
- コマンドライン引数で提供されない場合、このファイルから認証情報が読み取られる

**重要な注意事項:**
- **このファイルは絶対にコミットしない** - 機密性の高い API キーを含む
- 誤ったコミットを防ぐために `.gitignore` にリスト済み
- 存在する場合は `.env.example` テンプレートから作成
- API キーを安全に保管し、定期的にローテーション

---

### `.bedrock_agentcore.yaml`
**場所:** チュートリアルルート（`simple-dual-observability/.bedrock_agentcore.yaml`）

**目的:** AgentCore Runtime の設定と状態をキャッシュして、後続のデプロイを高速化し、不要なリソースの再作成を回避します。

**生成元:** 最初の `Runtime.configure()` 呼び出し時に `bedrock-agentcore-starter-toolkit` が生成

**典型的な内容:**
```yaml
agent_name: weather_time_observability_agent
region: us-east-1
entrypoint: agent/weather_time_agent.py
requirements_file: requirements.txt
auto_create_execution_role: true
auto_create_ecr: true
disable_otel: false  # Braintrust が有効な場合は true
# ... その他の設定オプション
```

**使用方法:**
- ツールキットが後続のデプロイ実行時に読み取る
- ツールキットが以前の設定を記憶できるようにする
- 既存のリソースを再利用してデプロイを高速化

**重要な注意事項:**
- 最初のデプロイ時に自動生成
- 削除しても安全 - 次のデプロイ時に再生成される
- `.gitignore` にリスト済み
- シークレットではなく、デプロイ状態を含む

---

### `.deployment_metadata.json`
**場所:** `scripts/.deployment_metadata.json`

**目的:** デプロイ情報の単一の信頼できるソース。エージェント ID、ARN、ECR URI、リージョン、および設定フラグを含みます。デプロイされたエージェントを識別して操作するためにすべてのスクリプトで使用されます。

**生成元:** デプロイ成功後に `scripts/deploy_agent.py` が生成

**典型的な内容:**
```json
{
  "agent_id": "weather_time_observability_agent-dWTPGP46D4",
  "agent_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/weather_time_observability_agent-dWTPGP46D4",
  "ecr_uri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/weather_time_observability_agent",
  "region": "us-east-1",
  "agent_name": "weather_time_observability_agent",
  "braintrust_enabled": true
}
```

**使用方法:**
- `test_agent.py`、`test_agent.sh` がエージェントを呼び出すために読み取る
- `cleanup.sh` がリソースを削除するために読み取る
- `simple_observability.py` が Braintrust 設定を検出するために読み取る
- `setup_all.sh` がデプロイ情報を表示するために読み取る

**重要な注意事項:**
- デプロイ中に作成
- クリーンアップ中に削除
- `.gitignore` にリスト済み
- これが必要な**唯一**のメタデータファイル（レガシーの `.agent_id` と `.env` ファイルを置き換え）
- スクリプトが動作するために存在する必要がある - 欠落している場合はエージェントを再デプロイ

**生成プロセス:**
```python
# deploy_agent.py 内
deployment_info = {
    "agent_id": launch_result.agent_id,
    "agent_arn": launch_result.agent_arn,
    "ecr_uri": launch_result.ecr_uri,
    "region": region,
    "agent_name": agent_name,
    "braintrust_enabled": enable_braintrust
}
metadata_file.write_text(json.dumps(deployment_info, indent=2))
```

---

### `.env.backup`
**場所:** `scripts/.env.backup`

**目的:** `setup_braintrust.sh` が環境変数を更新する際に作成される前の `.env` ファイルのバックアップ。

**生成元:** Braintrust 認証情報を追加する際に `scripts/setup_braintrust.sh` が生成

**典型的な内容:**
`.env` ファイルと同じ形式（以前のバージョン）

**使用方法:**
- 必要に応じて以前の設定を復元可能
- セットアップ実行時に `.env` が既に存在する場合のみ作成

**重要な注意事項:**
- `.gitignore` にリスト済み
- 機密情報を含む - コミットしない
- 新しい設定が動作することを確認した後、安全に削除可能

**生成プロセス:**
```bash
# setup_braintrust.sh 内
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$SCRIPT_DIR/.env.backup"
fi
```

---

### `Dockerfile`
**場所:** チュートリアルルート（`simple-dual-observability/Dockerfile`）

**目的:** Python 環境、依存関係、および起動コマンドを含むエージェント用の Docker コンテナイメージを定義します。

**生成元:** `Runtime.configure()` 呼び出し時に `bedrock-agentcore-starter-toolkit` が生成

**典型的な内容:**
```dockerfile
FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# より高速なパッケージ管理のために uv をインストール
RUN pip install uv

# requirements をコピーしてインストール
COPY requirements.txt .
RUN uv pip install -r requirements.txt

# 環境変数を設定
ENV DOCKER_CONTAINER=1

# アプリケーションコードをコピー
COPY . .

# エージェントを実行
CMD ["python", "-m", "agent.weather_time_agent"]
```

**使用方法:**
- コンテナビルドプロセス中に Docker が使用
- `requirements.txt` とエージェント設定に基づいて自動生成
- Braintrust オブザーバビリティが有効かどうかに基づいて変更

**重要な注意事項:**
- **自動生成 - バージョン管理にコミットしない**
- デプロイごとに再生成
- `tobedeleted/` フォルダに保存
- ツールキットは設定に基づいて異なる Dockerfile を生成：
  - CloudWatch のみ: 標準ランタイム
  - Braintrust 有効: 個別の OTEL 計装ラッパーなし

**生成プロセス:**
スターターツールキットがこのファイルを `Runtime.configure()` で生成：
```python
agentcore_runtime.configure(
    entrypoint="agent/weather_time_agent.py",
    requirements_file="requirements.txt",
    disable_otel=True  # Braintrust が有効な場合
)
# Dockerfile は設定に基づいて自動生成
```

---

### `.dockerignore`
**場所:** チュートリアルルート（`simple-dual-observability/.dockerignore`）

**目的:** Docker ビルドコンテキストから除外するファイルとディレクトリを指定し、イメージサイズとビルド時間を削減します。

**生成元:** `Runtime.configure()` 呼び出し時に `bedrock-agentcore-starter-toolkit` が生成

**典型的な内容:**
```
.git
.gitignore
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.mypy_cache
.ruff_cache
docs/
tests/
scripts/
.env
.env.*
*.md
```

**使用方法:**
- ファイルを除外するために `docker build` 中に Docker が読み取る
- 機密ファイルや不要なコンテンツがコンテナにコピーされるのを防ぐ
- Docker イメージサイズを削減

**重要な注意事項:**
- **自動生成 - コミットしない**
- デプロイごとに再生成
- `tobedeleted/` フォルダに保存
- Python プロジェクトの標準的な除外設定

**生成プロセス:**
`Runtime.configure()` 中に Dockerfile と一緒にスターターツールキットが自動生成

---

## ファイルライフサイクル

### デプロイ中（`scripts/deploy_agent.sh`）
1. `.bedrock_agentcore.yaml` - ツールキットが作成/更新
2. `Dockerfile` - ツールキットが生成
3. `.dockerignore` - ツールキットが生成
4. `.deployment_metadata.json` - デプロイ成功後に作成

### Braintrust セットアップ中（`scripts/setup_braintrust.sh`）
1. `.env.backup` - `.env` が存在する場合に作成
2. `.env` - Braintrust 認証情報で更新（CLI 引数を使用しない場合）

### クリーンアップ中（`scripts/cleanup.sh`）
1. `.deployment_metadata.json` - 削除
2. `.bedrock_agentcore.yaml` - オプションで削除

---

## ベストプラクティス

### バージョン管理
- `.env` ファイルは**絶対にコミットしない**（シークレットを含む）
- `.deployment_metadata.json` は**絶対にコミットしない**（デプロイ固有）
- 自動生成ファイル（`Dockerfile`、`.dockerignore`）は**絶対にコミットしない**
- 誤ったコミットを防ぐために `.gitignore` を**コミットする**

### セキュリティ
- `.env` ファイルはバージョン管理外に保存
- 本番環境では AWS Secrets Manager または Parameter Store を使用
- API キーを定期的にローテーション
- `.env` ファイルを公開チャネルで共有しない

### クリーンアップ
- 環境を切り替える際に生成ファイルを削除
- `scripts/cleanup.sh` を使用してデプロイアーティファクトを削除
- `tobedeleted/` フォルダは参照用に保持するがコミットしない

### リカバリ
- `.env` ファイルのバックアップを安全な場所に保管
- Braintrust プロジェクト ID を外部に文書化
- `.deployment_metadata.json` は再デプロイで再生成可能

---

## トラブルシューティング

### .deployment_metadata.json が見つからない
**症状:** スクリプトが「No deployment metadata found」で失敗

**解決策:** エージェントを再デプロイ：
```bash
scripts/deploy_agent.sh
```

### .env ファイルを紛失
**症状:** Braintrust 認証情報が見つからない

**解決策:**
1. `scripts/` で `.env.backup` を確認
2. Braintrust ダッシュボードから API キーを取得
3. `.env` ファイルを再作成

### .bedrock_agentcore.yaml が古い
**症状:** デプロイが古い設定を使用

**解決策:** ファイルを削除して再デプロイ：
```bash
rm .bedrock_agentcore.yaml
scripts/deploy_agent.sh
```

### Docker ビルドが失敗
**症状:** ビルド中に「No such file or directory」

**解決策:** Dockerfile を再生成：
```bash
# 古いファイルを削除
rm Dockerfile .dockerignore

# 再デプロイ（ファイルを再生成）
scripts/deploy_agent.sh
```

---

## 関連ドキュメント

- [メイン README](../README.md) - チュートリアル概要とセットアップ
- [トラブルシューティングガイド](troubleshooting.md) - 一般的な問題と解決策
- [開発ガイド](development.md) - ローカルテストと開発
