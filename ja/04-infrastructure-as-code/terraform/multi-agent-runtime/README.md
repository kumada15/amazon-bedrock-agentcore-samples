# Amazon Bedrock AgentCore でのマルチエージェントランタイム（Terraform）

この Terraform モジュールは、エージェント間（A2A）通信機能を備えた Amazon Bedrock AgentCore ランタイムを使用してマルチエージェントシステムをデプロイします。

## 目次

- [概要](#概要)
- [アーキテクチャ](#アーキテクチャ)
- [含まれる内容](#含まれる内容)
- [前提条件](#前提条件)
- [クイックスタート](#クイックスタート)
- [デプロイプロセス](#デプロイプロセス)
- [認証モデル](#認証モデル)
- [テスト](#テスト)
- [エージェントの機能](#エージェントの機能)
- [カスタマイズ](#カスタマイズ)
- [ファイル構成](#ファイル構成)
- [モニタリングとオブザーバビリティ](#モニタリングとオブザーバビリティ)
- [セキュリティ](#セキュリティ)
- [料金](#料金)
- [トラブルシューティング](#トラブルシューティング)
- [クリーンアップ](#クリーンアップ)
- [高度なトピック](#高度なトピック)
- [次のステップ](#次のステップ)
- [リソース](#リソース)
- [コントリビューション](#コントリビューション)
- [ライセンス](#ライセンス)

## 概要

このパターンは、エージェント間（A2A）プロトコルを介して通信する2つの協調エージェントによるマルチエージェントシステムのデプロイを実演します。Agent1（オーケストレーター）は専門的なタスクを Agent2（スペシャリスト）に委任でき、モジュラーでスケーラブルなエージェントアーキテクチャを実現します。

**主な機能:**
- A2A 通信を備えた2エージェントアーキテクチャ
- CodeBuild を介した自動 Docker イメージビルド
- 変更検出を備えた S3 ベースのソースコード管理
- 最小権限アクセスによる IAM ベースのセキュリティ
- 適切な依存関係を確保する順次デプロイ

以下に最適です：
- 複雑なマルチエージェントワークフローの構築
- エージェント特化パターンの実装
- スケーラブルなエージェントオーケストレーションシステムの作成
- A2A 通信プロトコルの学習

## アーキテクチャ

![マルチエージェントアーキテクチャ](architecture.png)

### システムコンポーネント

**Agent1（オーケストレーターエージェント）**
- 最初のユーザーリクエストを受信
- 複数のエージェント間でワークフローをオーケストレーション
- Agent2 を呼び出すための特殊なツール（`call_specialist_agent`）を含む
- Agent2 のランタイムを呼び出すための IAM 権限を保持
- 環境変数 `AGENT2_ARN` で A2A 通信を有効化

**Agent2（スペシャリストエージェント）**
- ドメイン固有の機能を持つ独立したスペシャリストエージェント
- データ分析と処理機能を提供
- A2A プロトコルを介して Agent1 から呼び出し可能
- 他のエージェントへの依存なし

### エージェント間（A2A）通信

A2A 通信パターンは以下を可能にします：
- **オーケストレーション**: Agent1 が複雑なワークフローを調整
- **特化**: Agent2 が特定の機能に集中
- **スケーラビリティ**: より多くの専門エージェントを容易に追加
- **セキュリティ**: エージェント間の IAM ベースの認可

## 含まれる内容

この Terraform 設定は以下を作成します：

- **2つの S3 バケット**: 両エージェント用のバージョニング付きソースコードストレージ
- **2つの ECR リポジトリ**: ARM64 Docker イメージ用のコンテナレジストリ
- **2つの CodeBuild プロジェクト**: 自動イメージビルドとプッシュ
- **3つの IAM ロール**:
  - Agent1 実行ロール（A2A 権限付き）
  - Agent2 実行ロール（標準権限）
  - CodeBuild サービスロール
- **2つのエージェントランタイム**:
  - AGENT2_ARN 環境変数を持つ Agent1（オーケストレーター）
  - 独立したランタイムの Agent2（スペシャリスト）
- **ビルド自動化**: コード変更時の自動再ビルド（MD5 ベースの検出）
- **サポートリソース**: S3 ライフサイクルポリシー、ECR ライフサイクルポリシー、IAM ポリシー

**合計:** Terraform で管理される約30の AWS リソースがデプロイ

## 前提条件

### 必要なツール

1. **Terraform**（>= 1.6）
   - **推奨**: バージョン管理用の [tfenv](https://github.com/tfutils/tfenv)
   - **または直接ダウンロード**: [terraform.io/downloads](https://www.terraform.io/downloads)

   **注意**: `brew install terraform` は v1.5.7（非推奨）を提供します。>= 1.6 には tfenv または直接ダウンロードを使用してください。

2. **AWS CLI**（認証情報設定済み）
   ```bash
   aws configure
   ```

3. **Python 3.11+**（テストスクリプト用）
   ```bash
   python --version  # Python 3.11 以降を確認
   pip install boto3
   ```

4. **Docker**（ローカルテスト用、オプション）

### AWS アカウント要件

- 適切な権限を持つ AWS アカウント
- Amazon Bedrock AgentCore サービスへのアクセス
- 以下を作成する権限：
  - S3 バケット
  - ECR リポジトリ
  - CodeBuild プロジェクト
  - IAM ロールとポリシー
  - AgentCore ランタイムリソース

## クイックスタート

### 1. 変数の設定

変数ファイルの例をコピーしてカスタマイズ：

```bash
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を好みの値で編集：
- `orchestrator_name`: オーケストレーターエージェントの名前（デフォルト: "OrchestratorAgent"）
- `specialist_name`: スペシャリストエージェントの名前（デフォルト: "SpecialistAgent"）
- `stack_name`: スタック識別子（デフォルト: "agentcore-multi-agent"）
- `aws_region`: デプロイ用の AWS リージョン（デフォルト: "us-west-2"）
- `network_mode`: PUBLIC または PRIVATE ネットワーキング

### 2. Terraform の初期化

ローカル状態とリモート状態の詳細なガイダンスについては、メイン README の [状態管理オプション](../README.md#state-management-options) を参照してください。

**ローカル状態でのクイックスタート:**
```bash
terraform init
```

**チーム協業にはリモート状態を使用** - セットアップ手順については [メイン README](../README.md#state-management-options) を参照してください。

### 3. デプロイ

**方法1: デプロイスクリプトの使用（推奨）**

```bash
chmod +x deploy.sh
./deploy.sh
```

スクリプトは設定を検証し、プランを表示し、すべてのリソースをデプロイします。

**方法2: 直接 Terraform コマンド**

```bash
terraform plan
terraform apply
```

**注意**: デプロイには、インフラストラクチャの作成、Docker イメージの順次ビルド（最初に Agent2、次に Agent1）、および A2A 通信の確立が含まれます。合計デプロイ時間: **約5〜10分**

### 4. デプロイの確認

```bash
# すべての出力を表示
terraform output

# エージェント ARN の取得
terraform output orchestrator_runtime_arn
terraform output specialist_runtime_arn
```

## デプロイプロセス

### 順次ビルドプロセス

デプロイは適切な依存関係を確保するために厳密な順序に従います：

```
1. S3 バケット作成（オーケストレーター & スペシャリスト）
2. ECR リポジトリ作成（オーケストレーター & スペシャリスト）
3. IAM ロール作成（A2A 権限付き）
4. CodeBuild プロジェクト作成（オーケストレーター & スペシャリスト）
5. Agent2 Docker ビルド → Agent2 ランタイム作成
6. Agent1 Docker ビルド → Agent1 ランタイム作成（Agent2 に依存）
```

**重要な依存関係:**
- Agent1 ランタイムは Agent2 ランタイムが先に作成されることに依存
- Agent1 ビルドは Agent2 ビルドの正常完了に依存
- Agent1 は `AGENT2_ARN` を環境変数として受け取る

### ビルドトリガー

インフラストラクチャは Docker イメージビルドを自動的にトリガーします：
- ソースコード変更時（MD5 ハッシュ検出）
- インフラストラクチャ変更で再ビルドが必要な時
- 順次: 最初に Agent2 ビルド、次に Agent1

## 認証モデル

このパターンは **ワークロードアイデンティティトークンを使用した IAM ベースの認証** を使用します：

- **サービスプリンシパル**: エージェントは `bedrock-agentcore.amazonaws.com` を介して IAM ロールを引き受け
- **ワークロードアイデンティティ**: エージェントは安全な操作のためにアクセストークンを取得
- **A2A 認可**: Agent1 は Agent2 に対する `InvokeAgentRuntime` 権限を持つ
- **API アクセス**: IAM 認証情報を使用した直接 AWS API 呼び出し

**注意**: これはユーザー認証レイヤーのないバックエンドインフラストラクチャパターンです。ユーザー向けアプリケーションの場合は、Cognito または API Gateway オーソライザーを別途追加します。

## テスト

含まれている `test_multi_agent.py` スクリプトは **インフラストラクチャに依存しない** もので、任意のデプロイ方法（Terraform、CDK、CloudFormation、または手動）で動作します。

### テストの前提条件

テスト前に、必要なパッケージがインストールされていることを確認：

**オプション A: uv の使用（推奨）**
```bash
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
uv pip install boto3  # エージェント呼び出しに必要
```

**オプション B: システム全体へのインストール**
```bash
pip install boto3  # エージェント呼び出しに必要
```

**注意**: テストスクリプトが AWS API を介して両方のエージェントランタイムを呼び出すには `boto3` が必要です。

### 基本テスト

```bash
# Terraform から ARN を取得
ORCHESTRATOR_ARN=$(terraform output -raw orchestrator_runtime_arn)
SPECIALIST_ARN=$(terraform output -raw specialist_runtime_arn)

# 両エージェントをテスト
python test_multi_agent.py $ORCHESTRATOR_ARN $SPECIALIST_ARN
```

### テストシナリオ

スクリプトは2つのテストを実行します：
1. **シンプルクエリ**: 基本的なオーケストレーター呼び出し
2. **A2A 通信**: オーケストレーターが A2A プロトコルを介してスペシャリストに委任

### 期待される出力

```
TEST 1: Simple Query (Orchestrator) ✅
TEST 2: Complex Query with A2A Communication ✅

✅ ALL TESTS PASSED
```

## エージェントの機能

### Agent1（オーケストレーター）

**ツール:**
- `call_specialist_agent`: 特殊な処理のために Agent2 を呼び出し
  - パラメータ: `query`（文字列）
  - 戻り値: Agent2 からの処理結果

**ユースケース:**
- 複雑なワークフローオーケストレーション
- 複数ステップのデータ処理
- 専門エージェントへの委任

### Agent2（スペシャリスト）

**機能:**
- ドメイン固有のデータ分析
- 詳細な情報処理
- エキスパートレベルのレスポンス

**ユースケース:**
- データ分析と変換
- ドメイン固有の処理
- 特殊な計算

## カスタマイズ

### エージェントコードの修正

1. **エージェントファイルの編集**
   ```bash
   # オーケストレーターエージェント
   vim agent-orchestrator-code/agent.py
   vim agent-orchestrator-code/requirements.txt

   # スペシャリストエージェント
   vim agent-specialist-code/agent.py
   vim agent-specialist-code/requirements.txt
   ```

2. **再デプロイ**
   ```bash
   terraform apply  # 変更を自動検出して再ビルド
   ```

### エージェントの追加

新しいエージェント（例: Coordinator）を追加するには：
1. 実装を含む `coordinator-code/` ディレクトリを作成
2. ランタイムリソース用の `coordinator.tf` を追加
3. `s3.tf`、`ecr.tf`、`iam.tf`、`codebuild.tf` を更新
4. `buildspec-coordinator.yml` を作成
5. ビルド順序のために `main.tf` を更新
6. `outputs.tf` と `variables.tf` を更新

### ネットワーク設定の変更

PUBLIC から PRIVATE ネットワーキングに変更：

```hcl
# terraform.tfvars
network_mode = "PRIVATE"
```

VPC 設定が必要です（このモジュールには含まれていません）。

## ファイル構成

```
multi-agent-runtime/
├── agent-orchestrator-code/           # オーケストレーターエージェントのソースコード
│   ├── agent.py                 # メインエージェント実装
│   ├── Dockerfile               # コンテナ定義
│   └── requirements.txt         # Python 依存関係
├── agent-specialist-code/             # スペシャリストエージェントのソースコード
│   ├── agent.py                 # メインエージェント実装
│   ├── Dockerfile               # コンテナ定義
│   └── requirements.txt         # Python 依存関係
├── orchestrator.tf              # オーケストレーターランタイム設定
├── specialist.tf                # スペシャリストランタイム設定
├── main.tf                      # メイン Terraform 設定
├── variables.tf                 # 入力変数
├── outputs.tf                   # 出力定義
├── iam.tf                       # IAM ロールとポリシー
├── s3.tf                        # ソースコード用 S3 バケット
├── ecr.tf                       # ECR リポジトリ
├── codebuild.tf                 # CodeBuild プロジェクト
├── versions.tf                  # Terraform とプロバイダーのバージョン
├── buildspec-orchestrator.yml   # オーケストレービルド仕様
├── buildspec-specialist.yml     # スペシャリストビルド仕様
├── terraform.tfvars.example     # 変数値の例
├── backend.tf.example           # バックエンド設定の例
├── deploy.sh                    # デプロイ自動化スクリプト
├── destroy.sh                   # クリーンアップ自動化スクリプト
├── test_multi_agent.py          # インフラストラクチャに依存しないテストスクリプト
└── README.md                    # このファイル
```

## モニタリングとオブザーバビリティ

### CloudWatch Logs

```bash
# オーケストレーターログ
aws logs tail /aws/bedrock-agentcore/agentcore-multi-agent-orchestrator-runtime --follow

# スペシャリストログ
aws logs tail /aws/bedrock-agentcore/agentcore-multi-agent-specialist-runtime --follow
```

### メトリクス

CloudWatch でメトリクスにアクセス：
- エージェント呼び出し回数
- エージェント実行時間
- エラー率
- A2A 呼び出しメトリクス

### AWS コンソール

AWS コンソールでモニタリング：
- **Bedrock AgentCore**: [コンソールリンク](https://console.aws.amazon.com/bedrock/home#/agentcore)
- **ECR リポジトリ**: Docker イメージの表示
- **CodeBuild**: ビルドステータスのモニタリング
- **CloudWatch**: ログとメトリクスの表示

## セキュリティ

### IAM 権限

**Agent1 実行ロール:**
- 標準 AgentCore 権限
- **重要**: Agent2 用の `bedrock-agentcore:InvokeAgentRuntime`

**Agent2 実行ロール:**
- 標準 AgentCore 権限のみ
- クロスエージェント呼び出し権限は不要

**CodeBuild ロール:**
- 両エージェントソースバケットへの S3 アクセス
- 両リポジトリへの ECR プッシュアクセス
- CloudWatch Logs 書き込みアクセス

### ネットワークセキュリティ

- エージェントは指定されたネットワークモード（PUBLIC/PRIVATE）で実行
- ECR リポジトリにはアカウントレベルのアクセス制御あり
- S3 バケットはパブリックアクセスをブロック
- IAM ポリシーは最小権限の原則に従う

### シークレット管理

機密データの場合：
- AWS Secrets Manager を使用
- シークレット ARN を環境変数として渡す
- エージェントコードで実行時にシークレットを取得

## 料金

最新の料金情報については、以下を参照してください：
- [Amazon Bedrock 料金](https://aws.amazon.com/bedrock/pricing/)
- [Amazon ECR 料金](https://aws.amazon.com/ecr/pricing/)
- [AWS CodeBuild 料金](https://aws.amazon.com/codebuild/pricing/)
- [Amazon S3 料金](https://aws.amazon.com/s3/pricing/)
- [Amazon CloudWatch 料金](https://aws.amazon.com/cloudwatch/pricing/)

**注意**: 実際のコストは使用パターン、AWS リージョン、および消費する特定のサービスによって異なります。

## トラブルシューティング

### よくある問題

**問題**: Agent1 が Agent2 を呼び出せない
- **解決策**: AGENT2_ARN 環境変数が設定されていることを確認
- **確認**: IAM 権限に InvokeAgentRuntime が含まれているか

**問題**: ビルドが失敗
- **解決策**: CloudWatch で CodeBuild ログを確認
- **確認**: ソースコードが正しいディレクトリにあるか

**問題**: ランタイムが作成されない
- **解決策**: ECR イメージが存在し、正しくタグ付けされているか確認
- **確認**: Terraform 状態でエラーを確認

### デバッグコマンド

```bash
# Terraform 状態を確認
terraform show

# 設定を検証
terraform validate

# 特定のリソースを表示
terraform state show aws_bedrockagentcore_agent_runtime.orchestrator

# 詳細なビルドログを取得
PROJECT_NAME=$(terraform output -raw orchestrator_codebuild_project)
aws codebuild batch-get-builds --ids $(aws codebuild list-builds-for-project --project-name $PROJECT_NAME --query 'ids[0]' --output text)
```

## クリーンアップ

### 自動クリーンアップ

```bash
chmod +x destroy.sh
./destroy.sh
```

スクリプトは破棄プランを表示し、確認を要求し、すべてのリソースを破棄します。

### 手動クリーンアップ

```bash
terraform destroy
```

**重要**: AWS コンソールですべてのリソースが削除されたことを確認：
- Bedrock AgentCore ランタイム
- ECR リポジトリ
- S3 バケット
- CodeBuild プロジェクト
- IAM ロール

## 高度なトピック

### カスタムツールの追加

1. エージェントコードでツールスキーマを定義
2. ツールハンドラー関数を実装
3. エージェントにツールを登録
4. 再ビルドしてデプロイ

### メモリの実装

エージェントコードにセッション管理を追加：
```python
session_data = {}

def handle_request(input_text, session_id):
    if session_id not in session_data:
        session_data[session_id] = {}
    # コンテキストに session_data を使用
```

### マルチリージョンデプロイ

マルチリージョンの場合：
1. 状態ロック用にバックエンドを設定
2. 各リージョンに個別にデプロイ
3. フェイルオーバーに Route53 を使用
4. S3/ECR のクロスリージョンレプリケーションを検討

## 次のステップ

1. **デプロイのテスト**
   ```bash
   python test_multi_agent.py $(terraform output -raw orchestrator_runtime_arn) $(terraform output -raw specialist_runtime_arn)
   ```

2. 特定のユースケースに合わせて **エージェントをカスタマイズ**
   - エージェントにドメイン固有のツールを追加
   - カスタムビジネスロジックを実装
   - 外部 API と統合

3. **関連パターンを探索**
   - [MCP サーバーパターン](../mcp-server-agentcore-runtime/) - JWT 認証付き MCP プロトコル
   - [AgentCore サンプル](https://github.com/aws-samples/amazon-bedrock-agentcore-samples) - その他の例

4. **本番機能を追加**
   - モニタリングとアラート
   - カスタム認証レイヤー（必要に応じて）
   - プライベートネットワーキング用の VPC デプロイ
   - CI/CD パイプライン統合

## リソース

- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Terraform AWS プロバイダー](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [エージェント間通信](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-a2a.html)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## コントリビューション

コントリビューションを歓迎します！詳細は [コントリビューションガイド](../../../CONTRIBUTING.md) を参照してください。

## ライセンス

このプロジェクトは MIT-0 ライセンスの下でライセンスされています。詳細は [LICENSE](../../../LICENSE) ファイルを参照してください。
