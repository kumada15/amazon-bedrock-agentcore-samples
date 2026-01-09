# Terraform サンプル

Terraform を使用して Amazon Bedrock AgentCore リソースをデプロイします。

## 前提条件

- **Terraform >= 1.6**
  - **推奨**: バージョン管理用の [tfenv](https://github.com/tfutils/tfenv)
  - **または直接ダウンロード**: [terraform.io/downloads](https://www.terraform.io/downloads)
  - **注意**: `brew install terraform` は v1.5.7 (非推奨) を提供します。>= 1.6 には tfenv または直接ダウンロードを使用してください
- 認証情報が設定された **AWS CLI**
- **Python 3.11+** (テストスクリプト用)
- **Docker** (オプション、ローカルテスト用)
- Amazon Bedrock AgentCore へのアクセス (プレビュー)

## ステート管理オプション

Terraform はデプロイされたリソースをステートファイルで追跡します。ニーズに合ったアプローチを選択してください：

### オプション A: ローカルステート (クイックスタート)

テスト、学習、個人開発に最適：

```bash
cd <sample-directory>
terraform init
```

**特徴:**
- ステートはローカルの `terraform.tfstate` ファイルに保存
- シンプルなセットアップ、追加設定不要
- 個人的な実験に最適
- チームコラボレーションには不向き

### オプション B: リモートステート (チーム/本番環境)

チームコラボレーションと本番環境に推奨：

```bash
cd <sample-directory>

# 1. セットアップ (パターンごとに1回)
cp backend.tf.example backend.tf
# S3 バケットと DynamoDB テーブルで backend.tf を編集

# 2. バックエンドで初期化
terraform init
```

**特徴:**
- DynamoDB ロック付きで S3 にステートを保存
- チームコラボレーションを実現
- ステートのバージョン管理とバックアップを提供
- 同時変更を防止

**セットアップ要件:**
- ステート保存用の S3 バケット
- ステートロック用の DynamoDB テーブル
- 詳細は各パターンの `backend.tf.example` を参照

**注意**: リモートステートで `terraform init` を実行する前に、S3 バケットと DynamoDB テーブルを作成する必要があります。セットアップ手順は各パターンディレクトリの `backend.tf.example` を参照してください。

## 一般的なデプロイパターン

### オプション 1: 自動化スクリプトの使用 (推奨)

```bash
cd <sample-directory>
chmod +x deploy.sh
./deploy.sh
```

デプロイスクリプトは以下を実行します:
- 環境の検証
- Terraform の初期化
- プランの作成とレビュー
- すべてのリソースのデプロイ
- 出力と次のステップの表示

### オプション 2: 手動の Terraform コマンド

```bash
cd <sample-directory>

# 1. 変数の設定
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars を編集して値を設定

# 2. ステート管理を選択 (上記のステート管理オプションを参照)
terraform init

# 3. プランのレビュー
terraform plan

# 4. デプロイ
terraform apply

# 5. 出力の確認
terraform output
```

## テスト

すべてのパターンにはデプロイを検証する Python テストスクリプトが含まれています。

### テスト環境のセットアップ

**オプション 1: uv の使用 (推奨)**

```bash
# uv がインストールされていない場合はインストール
curl -LsSf https://astral.sh/uv/install.sh | sh

# 仮想環境の作成
uv venv

# 仮想環境の有効化
source .venv/bin/activate  # macOS/Linux の場合
# .venv\Scripts\activate   # Windows の場合

# boto3 のインストール
uv pip install boto3
```

**オプション 2: pip の使用**

```bash
# 仮想環境の作成
python3 -m venv .venv

# 仮想環境の有効化
source .venv/bin/activate  # macOS/Linux の場合
# .venv\Scripts\activate   # Windows の場合

# boto3 のインストール
pip install boto3
```

### テストの実行

```bash
# Terraform 出力からエージェント ARN を取得
AGENT_ARN=$(terraform output -raw agent_runtime_arn)

# テストスクリプトを実行
python test_*.py $AGENT_ARN
```

### クリーンアップ

```bash
# 自動化スクリプトを使用
./destroy.sh

# または Terraform を直接使用
terraform destroy
```

## サンプル

- **[basic-runtime/](./basic-runtime/)** - コンテナランタイムを使用したシンプルなエージェントのデプロイ
- **[mcp-server-agentcore-runtime/](./mcp-server-agentcore-runtime/)** - JWT 認証と API Gateway 付き MCP Server
- **[multi-agent-runtime/](./multi-agent-runtime/)** - Agent-to-Agent (A2A) 通信を使用したマルチエージェントシステム
- **[end-to-end-weather-agent/](./end-to-end-weather-agent/)** - Browser、Code Interpreter、Memory ツールを備えた天気エージェント

## Terraform の利点

- **Infrastructure as Code**: HCL でリソースを宣言的に定義
- **ステート管理**: インフラストラクチャのステートを追跡・管理
- **モジュールの再利用性**: 再利用可能なインフラストラクチャコンポーネントを作成
- **適用前のプラン**: デプロイ前に変更をプレビュー
- **自動イメージビルド**: Docker イメージ作成に CodeBuild を使用
- **プロバイダーエコシステム**: 数千のプロバイダーとリソースにアクセス
- **自動化スクリプト**: 簡単なデプロイのための deploy.sh と destroy.sh を含む

## パターン比較

| パターン | Agent Runtime | ツール | A2A | MCP Server | ユースケース |
|---------|---------------|--------|-----|------------|--------------|
| basic-runtime | 1 | - | No | No | シンプルなエージェントのデプロイ |
| mcp-server | 1 | - | No | Yes | JWT 認証付き API 統合 |
| multi-agent | 2 | - | Yes | No | オーケストレーター + スペシャリストパターン |
| weather-agent | 1 | Browser, Code Interpreter, Memory | No | No | ツールを備えたフル機能エージェント |

## トラブルシューティング

### Terraform バージョンの問題

プロバイダー互換性の問題が発生した場合:

```bash
# tfenv で特定の Terraform バージョンをインストール
tfenv install 1.6.0
tfenv use 1.6.0
```

### ステート管理

```bash
# 現在のステートを表示
terraform show

# ステート内のすべてのリソースを一覧表示
terraform state list

# 必要に応じてステートからリソースを削除
terraform state rm <resource_address>
```

### プロバイダーエラー

プロバイダーバージョンの競合が表示された場合:

```bash
# プロバイダーを最新の互換バージョンにアップグレード
terraform init -upgrade

# プロバイダーバージョンをロック
terraform providers lock
```

### CodeBuild の失敗

ビルドログを確認:

```bash
# 出力からプロジェクト名を取得
PROJECT_NAME=$(terraform output -raw codebuild_project_name)

# 最近のビルドログを表示
aws codebuild list-builds-for-project \
  --project-name $PROJECT_NAME \
  --region <region>

# 特定のビルドの詳細を取得
aws codebuild batch-get-builds \
  --ids <build-id> \
  --region <region>
```

### デプロイがスタックした場合

デプロイがスタックしているように見える場合:

```bash
# エージェントランタイムの CloudWatch Logs を確認
aws logs tail /aws/bedrock-agentcore/<runtime-name> --follow

# CodeBuild の進行状況を確認
aws codebuild list-builds-for-project \
  --project-name <project-name> \
  --max-items 5
```

### リソースが既に存在する

「resource already exists」エラーが発生した場合:

```bash
# 既存のリソースをステートにインポート
terraform import <resource_type>.<resource_name> <resource_id>

# S3 バケットの例
terraform import aws_s3_bucket.example my-bucket-name
```

### クリーンアップの問題

`terraform destroy` が失敗した場合:

```bash
# まず S3 バケットを手動で空にする
aws s3 rm s3://<bucket-name> --recursive

# 強制削除 (注意して使用)
terraform destroy -auto-approve

# 残っているリソースを確認
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=ManagedBy,Values=Terraform
```

## 主な機能

### ステート管理

Terraform はすべてのデプロイされたリソースをステートファイルで追跡します。チームコラボレーションの場合:

```bash
# リモートステートのセットアップ (S3 の例)
cp backend.tf.example backend.tf
# S3 バケットの詳細で backend.tf を編集
terraform init -migrate-state
```

### 自動 Docker ビルド

各パターンは AWS CodeBuild を使用して ARM64 Docker イメージを自動的にビルドします:
- ソースコードの変更でトリガー (MD5 ハッシュ検出)
- ローカル Docker デーモン不要
- AWS Graviton プロセッサ向けに最適化

### テストスクリプト

すべてのパターンにインフラストラクチャに依存しない Python テストスクリプトが含まれています:

```bash
# Terraform 出力からエージェント ARN を取得
AGENT_ARN=$(terraform output -raw agent_runtime_arn)

# テストを実行
python test_*.py $AGENT_ARN
```

## 追加リソース

- [Terraform ドキュメント](https://www.terraform.io/docs)
- [AWS プロバイダードキュメント](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Terraform ベストプラクティス](https://www.terraform.io/docs/cloud/guides/recommended-practices/index.html)

## コントリビューション

コントリビューションを歓迎します！詳細は [Contributing Guide](../../CONTRIBUTING.md) をご覧ください。

## ライセンス

このプロジェクトは MIT-0 ライセンスの下でライセンスされています。詳細は [LICENSE](../../LICENSE) ファイルをご覧ください。
