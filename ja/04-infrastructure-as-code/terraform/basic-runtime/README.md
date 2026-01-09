# Basic AgentCore Runtime - Terraform

このパターンは、Terraform を使用した AgentCore Runtime の最もシンプルなデプロイを示しています。Memory、Code Interpreter、Browser などの追加ツールなしで基本的なエージェントを作成します。

## 目次

- [概要](#概要)
- [アーキテクチャ](#アーキテクチャ)
- [前提条件](#前提条件)
- [クイックスタート](#クイックスタート)
- [エージェントのテスト](#エージェントのテスト)
- [サンプルクエリ](#サンプルクエリ)
- [カスタマイズ](#カスタマイズ)
- [ファイル構成](#ファイル構成)
- [トラブルシューティング](#トラブルシューティング)
- [クリーンアップ](#クリーンアップ)
- [料金](#料金)
- [次のステップ](#次のステップ)
- [リソース](#リソース)
- [コントリビューション](#コントリビューション)
- [ライセンス](#ライセンス)

## 概要

この Terraform 設定は、以下を含む最小限の AgentCore デプロイを作成します：

- **AgentCore Runtime**: シンプルな Strands エージェントをホスト
- **ECR リポジトリ**: Docker コンテナイメージを保存
- **IAM ロール**: 必要な権限を提供
- **CodeBuild プロジェクト**: ARM64 Docker イメージを自動的にビルド

これにより、以下に最適です：
- Terraform で AgentCore の基本を学ぶ
- 迅速なプロトタイピングと実験
- コアデプロイパターンの理解
- 複雑さを追加する前の基盤構築

## アーキテクチャ

![Architecture Diagram](architecture.png)

## 含まれる内容

この Terraform 設定は以下を作成します：

- **S3 バケット**: バージョン管理されたビルド用のエージェントソースコードを保存
- **ECR リポジトリ**: エージェント Docker イメージ用のコンテナレジストリ
- **CodeBuild プロジェクト**: 自動化された Docker イメージのビルドとプッシュ
- **IAM ロール**: エージェントと CodeBuild 用の実行ロール
- **AgentCore Runtime**: デプロイされたコンテナを使用したサーバーレスエージェントランタイム

### エージェントコード管理

`agent-code/` ディレクトリにはエージェントのソースファイルが含まれています：
- `basic_agent.py` - エージェントの実装
- `Dockerfile` - コンテナ設定
- `requirements.txt` - Python 依存関係

**自動変更検出**:
- Terraform は `agent-code/` ディレクトリをアーカイブ
- MD5 ベースのバージョニングで S3 にアップロード
- CodeBuild が S3 からプルして Docker イメージをビルド
- ファイルへの変更は自動的に再ビルドをトリガー (新規ファイル、変更、削除)

## 前提条件

### 必要なツール

1. **Terraform** (>= 1.6)
   - **推奨**: バージョン管理用の [tfenv](https://github.com/tfutils/tfenv)
   - **または直接ダウンロード**: [terraform.io/downloads](https://www.terraform.io/downloads)

   **注意**: `brew install terraform` は v1.5.7 (非推奨) を提供します。>= 1.6 には tfenv または直接ダウンロードを使用してください。

2. **AWS CLI** (認証情報設定済み)
   ```bash
   aws configure
   ```

3. **Python 3.11+** (テストスクリプト用)
   ```bash
   python --version  # Python 3.11 以降を確認
   pip install boto3
   ```

4. **Docker** (ローカルテスト用、オプション)

### AWS アカウント要件

- 適切な権限を持つ AWS アカウント
- Amazon Bedrock モデルへのアクセス

## クイックスタート

### 1. 変数の設定

サンプル変数ファイルをコピーしてカスタマイズ：

```bash
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を好みの値で編集します。

### 2. Terraform の初期化

ローカルとリモートのステートに関する詳細なガイダンスは、メイン README の [ステート管理オプション](../README.md#state-management-options) を参照してください。

**ローカルステートでのクイックスタート:**
```bash
terraform init
```

**チームコラボレーションにはリモートステートを使用** - セットアップ手順は [メイン README](../README.md#state-management-options) を参照してください。

### 3. プランのレビュー

```bash
terraform plan
```

### 4. デプロイ

**方法 1: デプロイスクリプトを使用 (推奨)**

スクリプトを実行可能にする (初回のみ):
```bash
chmod +x deploy.sh
```

その後デプロイ:
```bash
./deploy.sh
```

デプロイスクリプトは以下を実行:
- Terraform 設定の検証
- デプロイプランの表示
- 確認のプロンプト
- 変更の適用

**方法 2: Terraform コマンドを直接使用**

```bash
terraform apply
```

プロンプトが表示されたら、`yes` と入力してデプロイを確認します。

**注意**: デプロイプロセスには以下が含まれます：
1. ECR リポジトリの作成
2. CodeBuild による Docker イメージのビルド
3. AgentCore Runtime の作成

合計デプロイ時間: **約 3-5 分**

### 5. 出力の取得

デプロイ完了後：

```bash
terraform output
```

出力例：
```
agent_runtime_id = "AGENT1234567890"
agent_runtime_arn = "arn:aws:bedrock-agentcore:<us-west-2>:123456789012:agent-runtime/AGENT1234567890"
ecr_repository_url = "123456789012.dkr.ecr.us-west-2.amazonaws.com/agentcore-basic-basic-agent"
```

## エージェントのテスト

### テストの前提条件

テスト前に、必要なパッケージがインストールされていることを確認：

**オプション A: uv を使用 (推奨)**
```bash
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
uv pip install boto3  # エージェント呼び出しに必要
```

**オプション B: システム全体へのインストール**
```bash
pip install boto3  # エージェント呼び出しに必要
```

**注意**: `boto3` は AWS API 経由でエージェントランタイムを呼び出すテストスクリプトに必要です。

### オプション 1: テストスクリプトを使用 (推奨)

```bash
# テストスイートを実行
python test_basic_agent.py $(terraform output -raw agent_runtime_arn)
```

### オプション 2: AWS CLI を使用

```bash
# 出力からランタイム ARN を取得
RUNTIME_ARN=$(terraform output -raw agent_runtime_arn)

# エージェントを呼び出し
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $RUNTIME_ARN \
  --qualifier DEFAULT \
  --payload $(echo '{"prompt": "Hello, introduce yourself"}' | base64) \
  response.json

# レスポンスを表示
cat response.json | jq -r '.response'
```

### オプション 3: AWS コンソールを使用

1. Amazon Bedrock コンソールに移動
2. AgentCore → Runtimes に移動
3. ランタイムを選択
4. 「Test」機能を使用してクエリを送信

## サンプルクエリ

basic エージェントをテストするために、以下のクエリを試してください：

1. **簡単な計算**:
   ```json
   {"prompt": "What is 2+2?"}
   ```

2. **一般知識**:
   ```json
   {"prompt": "What is the capital of France?"}
   ```

3. **説明のリクエスト**:
   ```json
   {"prompt": "Explain what Amazon Bedrock is in simple terms"}
   ```

4. **クリエイティブタスク**:
   ```json
   {"prompt": "Write a haiku about cloud computing"}
   ```

## カスタマイズ

### エージェントコードの変更

`agent-code/` 内のファイルを編集してデプロイ：
- `basic_agent.py` - エージェントロジックとシステムプロンプト
- `Dockerfile` - コンテナ設定
- `requirements.txt` - Python 依存関係

変更は自動的に検出され、再ビルドがトリガーされます。デプロイするには `terraform apply` を実行します。

### 環境変数

`terraform.tfvars` に追加：
```hcl
environment_variables = {
  LOG_LEVEL = "DEBUG"
}
```

### ネットワークモード

VPC デプロイには `network_mode = "PRIVATE"` を設定 (追加の VPC 設定が必要)。

## ファイル構成

```
basic-runtime/
├── main.tf                      # AgentCore ランタイムリソース
├── variables.tf                 # 入力変数
├── outputs.tf                   # 出力値
├── versions.tf                  # プロバイダー設定
├── iam.tf                       # IAM ロールとポリシー
├── s3.tf                        # ソースコード用 S3 バケット
├── ecr.tf                       # ECR リポジトリ
├── codebuild.tf                 # Docker ビルド自動化
├── buildspec.yml                # CodeBuild ビルド仕様
├── terraform.tfvars.example     # 設定例
├── backend.tf.example           # リモートステート例
├── test_basic_agent.py          # 自動テストスクリプト
├── agent-code/                  # エージェントソースコード
│   ├── basic_agent.py          # エージェントの実装
│   ├── Dockerfile              # コンテナ設定
│   └── requirements.txt        # Python 依存関係
├── scripts/                     # ビルド自動化スクリプト
│   └── build-image.sh          # CodeBuild トリガーと検証
├── deploy.sh                    # デプロイヘルパースクリプト
├── destroy.sh                   # クリーンアップヘルパースクリプト
├── .gitignore                   # Git 無視パターン
└── README.md                    # このファイル
```

## トラブルシューティング

### CodeBuild の失敗

Docker ビルドが失敗した場合：

1. CodeBuild ログを確認：
   ```bash
   aws codebuild batch-get-builds \
     --ids $(terraform output -raw codebuild_project_name) \
     --region us-west-2
   ```

2. よくある問題：
   - ネットワーク接続の問題
   - ECR 認証の問題
   - Python 依存関係の競合

### ランタイム作成の失敗

ランタイム作成が失敗した場合：

1. Docker イメージが存在することを確認：
   ```bash
   aws ecr describe-images \
     --repository-name $(terraform output -raw ecr_repository_url | cut -d'/' -f2) \
     --region us-west-2
   ```

2. IAM ロールの権限を確認
3. Bedrock AgentCore サービスクォータを確認

### エージェント呼び出しの失敗

エージェントの呼び出しが失敗した場合：

1. AWS コンソールでランタイムステータスを確認
2. ランタイムの CloudWatch Logs を確認
3. Bedrock モデルアクセス権限を確認

## クリーンアップ

### すべてのリソースを削除

スクリプトを実行可能にする (初回のみ):
```bash
chmod +x destroy.sh
```

その後クリーンアップ:
```bash
./destroy.sh
```

または Terraform を直接使用：

```bash
terraform destroy
```

### クリーンアップの確認

すべてのリソースが削除されたことを確認：

```bash
# ECR リポジトリを確認
aws ecr describe-repositories --region us-west-2 | grep agentcore-basic

# AgentCore ランタイムを確認
aws bedrock-agentcore list-agent-runtimes --region us-west-2
```

## 料金

最新の料金情報については、以下を参照してください：
- [Amazon Bedrock 料金](https://aws.amazon.com/bedrock/pricing/)
- [Amazon ECR 料金](https://aws.amazon.com/ecr/pricing/)
- [AWS CodeBuild 料金](https://aws.amazon.com/codebuild/pricing/)
- [Amazon S3 料金](https://aws.amazon.com/s3/pricing/)
- [Amazon CloudWatch 料金](https://aws.amazon.com/cloudwatch/pricing/)

**注意**: 実際のコストは、使用パターン、AWS リージョン、および消費した特定のサービスによって異なります。

## 次のステップ

### 他のパターンを探索

- [MCP Server Runtime](../mcp-server-agentcore-runtime/) - MCP プロトコルサポートを追加
- [Multi-Agent Runtime](../multi-agent-runtime/) - 複数の連携するエージェントをデプロイ
- [End-to-End Weather Agent](../end-to-end-weather-agent/) - ツールを備えたフル機能エージェント

## リソース

- [Terraform AWS プロバイダードキュメント](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Strands Agents ドキュメント](https://strands-agents.readthedocs.io/)
- [AgentCore サンプルリポジトリ](https://github.com/aws-samples/amazon-bedrock-agentcore-samples)

## コントリビューション

コントリビューションを歓迎します！詳細は [Contributing Guide](../../../CONTRIBUTING.md) をご覧ください。

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は [LICENSE](../../../LICENSE) ファイルをご覧ください。
