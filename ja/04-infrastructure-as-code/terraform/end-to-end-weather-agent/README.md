# Amazon Bedrock AgentCore でのエンドツーエンド天気エージェント（Terraform）

この Terraform モジュールは、統合された AgentCore ツール（Browser、Code Interpreter、Memory）を備えた Amazon Bedrock AgentCore ランタイムを使用して包括的な天気エージェントをデプロイします。

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
- [トラブルシューティング](#トラブルシューティング)
- [クリーンアップ](#クリーンアップ)
- [高度なトピック](#高度なトピック)
- [次のステップ](#次のステップ)
- [リソース](#リソース)
- [コントリビューション](#コントリビューション)
- [ライセンス](#ライセンス)

## 概要

このパターンは、Amazon Bedrock AgentCore ツールを備えたフル機能の天気エージェントのデプロイを実演し、Web ブラウジング、コード実行、および永続メモリを通じて高度な天気インテリジェンス機能を実現します。

**主な機能:**
- 統合された AgentCore ツール（Browser、Code Interpreter、Memory）
- CodeBuild を介した自動 Docker イメージビルド
- 分析結果用の S3 ベースのアーティファクトストレージ
- ツール固有の権限を持つ IAM ベースのセキュリティ
- 天気データの可視化と分析機能

以下に最適です：
- インテリジェントな天気情報システムの構築
- コード実行を含むデータ分析パイプラインの作成
- リアルタイム天気データの Web スクレイピング実装
- AgentCore ツール統合パターンの学習

## アーキテクチャ

![天気エージェントアーキテクチャ](architecture.png)

### システムコンポーネント

**天気エージェントランタイム**
- 自然言語による天気クエリを処理
- 包括的なレスポンスのために複数のツールを調整
- 可視化と詳細な分析を生成
- セッション間で会話コンテキストを維持

**AgentCore ツール**

1. **Browser ツール**
   - 天気 Web サイトと注意報にアクセス
   - リアルタイムの天気データをスクレイピング
   - アラートと警報を取得
   - 天気関連のニュースをチェック

2. **Code Interpreter ツール**
   - データ分析のために Python を実行
   - 天気の可視化を作成（チャート、グラフ）
   - 統計計算を実行
   - 天気データを処理・変換

3. **Memory**
   - 会話履歴を保存
   - ユーザー設定を記憶
   - セッション間でコンテキストを維持
   - イベント有効期限: 30日

### ツール統合

エージェントはすべてのツールをシームレスに調整します：
- **クエリ処理**: 天気関連のリクエストを理解
- **ツール選択**: 適切なツールを自動的に選択
- **データ分析**: 複雑な計算に Code Interpreter を使用
- **Web アクセス**: リアルタイム情報に Browser を使用
- **コンテキスト保持**: パーソナライズされたレスポンスに Memory を活用

## 含まれる内容

この Terraform 設定は以下を作成します：

- **2つの S3 バケット**:
  - バージョニング付きソースコードストレージ
  - 分析アーティファクト用の結果バケット
- **1つの ECR リポジトリ**: ARM64 Docker イメージ用のコンテナレジストリ
- **1つの CodeBuild プロジェクト**: 自動イメージビルドとプッシュ
- **2つの IAM ロール**:
  - エージェント実行ロール（ツール権限付き）
  - CodeBuild サービスロール
- **1つのエージェントランタイム**: ツール統合を備えた天気エージェント
- **3つの AgentCore ツール**:
  - Web アクセス用の Browser
  - 分析用の Code Interpreter
  - コンテキスト保持用の Memory
- **ビルド自動化**: コード変更時の自動再ビルド（MD5 ベースの検出）
- **サポートリソース**: S3 ライフサイクルポリシー、ECR ライフサイクルポリシー、IAM ポリシー

**合計:** Terraform で管理される約20の AWS リソースがデプロイ

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

3. **Python 3.11+**（テストスクリプトとメモリ初期化用）
   ```bash
   python --version  # Python 3.11 以降を確認
   pip install boto3
   ```

   **注意**: `boto3` は以下に必要です：
   - テストスクリプトの実行（`test_weather_agent.py`）
   - デプロイ中の自動メモリ初期化

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
- `agent_name`: 天気エージェントの名前（デフォルト: "WeatherAgent"）
- `memory_name`: メモリリソースの名前（デフォルト: "WeatherAgentMemory"）
- `stack_name`: スタック識別子（デフォルト: "agentcore-weather"）
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

**注意**: デプロイには、インフラストラクチャの作成、Docker イメージのビルド、およびすべての AgentCore ツールのプロビジョニングが含まれます。合計デプロイ時間: **約8〜12分**

### 4. デプロイの確認

```bash
# すべての出力を表示
terraform output

# エージェントとツール ID の取得
terraform output agent_runtime_arn
terraform output browser_id
terraform output code_interpreter_id
terraform output memory_id
```

## デプロイプロセス

### ビルドとデプロイのシーケンス

デプロイは以下のシーケンスに従います：

```
1. S3 バケット作成（ソース & 結果）
2. ECR リポジトリ作成
3. IAM ロール作成（ツール権限付き）
4. AgentCore ツール作成（Browser、Code Interpreter、Memory）
5. CodeBuild プロジェクト作成
6. Docker イメージビルド
7. 天気エージェントランタイム作成（環境変数としてツール ID を持つ）
```

**ツール統合:**
- エージェントは環境変数としてツール ID を受け取る
- IAM ロールがツール操作の権限を付与
- ツールはエージェントランタイムの前に作成
- Code Interpreter 出力用の結果バケット

### ビルドトリガー

インフラストラクチャは Docker イメージビルドを自動的にトリガーします：
- ソースコード変更時（MD5 ハッシュ検出）
- インフラストラクチャ変更で再ビルドが必要な時
- ビルドは通常5〜8分かかる

### メモリ初期化

デプロイ中に `scripts/init-memory.py` を介してアクティビティ設定（良い/普通/悪い天気のアクティビティ）でメモリが自動的に初期化されます。エージェントは天気ベースのアクティビティ推奨にこれらの設定を使用します。

### オブザーバビリティ

CloudWatch Logs（14日間保持）と X-Ray トレースで完全なオブザーバビリティが自動的に設定されます。ログは `/aws/vendedlogs/bedrock-agentcore/${runtime_id}` への vended logs 配信経由で配信されます。CloudWatch コンソールまたは `aws logs tail` コマンドでアクセスできます。

## 認証モデル

このパターンは **ワークロードアイデンティティトークンを使用した IAM ベースの認証** を使用します：

- **サービスプリンシパル**: エージェントは `bedrock-agentcore.amazonaws.com` を介して IAM ロールを引き受け
- **ワークロードアイデンティティ**: エージェントは安全な操作のためにアクセストークンを取得
- **ツールアクセス**: Browser、Code Interpreter、Memory の IAM 権限
- **S3 アクセス**: エージェントは S3 バケットに分析結果を書き込み可能

**注意**: これはユーザー認証レイヤーのないバックエンドインフラストラクチャパターンです。ユーザー向けアプリケーションの場合は、Cognito または API Gateway オーソライザーを別途追加します。

## テスト

含まれている `test_weather_agent.py` スクリプトは **インフラストラクチャに依存しない** もので、任意のデプロイ方法（Terraform、CDK、CloudFormation、または手動）で動作します。

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

**注意**: テストスクリプトが AWS API を介してエージェントランタイムを呼び出すには `boto3` が必要です。

### 基本テスト

```bash
# Terraform から ARN を取得
AGENT_ARN=$(terraform output -raw agent_runtime_arn)

# エージェントをテスト
python test_weather_agent.py $AGENT_ARN
```

### テストシナリオ

スクリプトは2つの包括的なテストを実行します：
1. **シンプルな天気クエリ**: 基本的な天気情報リクエスト
2. **ツールを使用した複雑なクエリ**: Browser、Code Interpreter、Memory の併用を実演

### 期待される出力

```
TEST 1: Simple Weather Query ✅
TEST 2: Complex Query with Tools ✅

✅ ALL TESTS PASSED
```

## エージェントの機能

### 天気エージェント

**コア機能:**
- 自然言語による天気クエリ
- リアルタイム天気データアクセス
- 過去の天気分析
- 天気予報インサイト
- 複数地点の比較
- 旅行天気計画

**統合ツール:**

1. **Browser ツール**
   - weather.gov、weather.com、およびその他の天気サイトにアクセス
   - 現在の状況と予報を取得
   - 天気警報と注意報を確認
   - レーダーと衛星画像のリンクを収集

2. **Code Interpreter ツール**
   - 気温傾向を分析
   - 天気の可視化を作成（折れ線グラフ、棒グラフ）
   - 統計を計算（平均、極値）
   - 過去の天気データを処理
   - カスタム天気レポートを生成

3. **Memory**
   - ユーザーの場所設定を記憶
   - よく要求される場所を追跡
   - 会話コンテキストを維持
   - 単位（F/C）のユーザー設定を保存
   - 天気ベースの推奨用にアクティビティ設定を事前初期化

### インタラクション例

**シンプルクエリ:**
```
ユーザー: "What's the weather like in Seattle?"
エージェント: [Browser を使用] 現在の状況、予報、気温を提供
```

**分析クエリ:**
```
ユーザー: "Compare temperatures between New York and Miami over the past week"
エージェント: [Browser + Code Interpreter を使用] データを取得し、比較チャートを作成
```

**計画クエリ:**
```
ユーザー: "I'm planning a road trip from Boston to Miami next week. What should I expect?"
エージェント: [Browser + Memory を使用] ルートベースの天気予報を提供し、旅行詳細を記憶
```

## カスタマイズ

### エージェントコードの修正

1. **エージェントファイルの編集**
   ```bash
   vim agent-code/weather_agent.py
   vim agent-code/requirements.txt
   vim agent-code/Dockerfile
   ```

2. **再デプロイ**
   ```bash
   terraform apply  # 変更を自動検出して再ビルド
   ```

### 追加の AgentCore ツールの追加

より多くのツールを追加するには：
1. 新しいツールリソースファイルを作成（例: `gateway.tf`）
2. `main.tf` でエージェント環境変数にツール ID を追加
3. 必要に応じて `iam.tf` で IAM 権限を更新
4. 新しいツール出力で `outputs.tf` を更新

### ネットワーク設定の変更

PUBLIC から PRIVATE ネットワーキングに変更：

```hcl
# terraform.tfvars
network_mode = "PRIVATE"
```

VPC 設定が必要です（このモジュールには含まれていません）。

### メモリ設定のカスタマイズ

メモリ保持期間を調整：

```hcl
# memory.tf
event_expiry_duration = 60  # 30日から60日に変更
```

## ファイル構成

```
end-to-end-weather-agent/
├── agent-code/               # 天気エージェントのソースコード
│   ├── weather_agent.py      # エージェント実装
│   ├── requirements.txt      # Python 依存関係
│   └── Dockerfile            # コンテナ定義
├── scripts/                  # ビルド自動化と初期化
│   ├── build-image.sh        # Docker ビルドスクリプト
│   └── init-memory.py        # メモリ初期化スクリプト
├── main.tf                   # エージェントランタイム設定
├── browser.tf                # Browser ツール
├── code_interpreter.tf       # Code Interpreter ツール
├── memory.tf                 # Memory リソース
├── memory-init.tf            # メモリ初期化自動化
├── observability.tf          # CloudWatch Logs と X-Ray トレース
├── iam.tf                    # IAM ロールとポリシー
├── s3.tf                     # S3 バケット
├── ecr.tf                    # ECR リポジトリ
├── codebuild.tf              # CodeBuild プロジェクト
├── outputs.tf                # 出力値
├── variables.tf              # 入力変数
├── versions.tf               # プロバイダーバージョン
├── buildspec.yml             # CodeBuild 仕様
├── test_weather_agent.py     # インフラストラクチャに依存しないテストスクリプト
├── deploy.sh                 # デプロイ自動化
├── destroy.sh                # クリーンアップ自動化
├── terraform.tfvars.example  # 設定例
├── backend.tf.example        # リモート状態の例
├── .gitignore                # Git 除外設定
├── architecture.png          # アーキテクチャ図
└── README.md                 # このファイル
```

## モニタリングとオブザーバビリティ

### CloudWatch Logs（自動）

Terraform は vended logs 配信で CloudWatch Log Group を自動的に作成します：

```bash
# ロググループ名を取得
LOG_GROUP=$(terraform output -raw log_group_name)

# エージェントログを tail
aws logs tail $LOG_GROUP --follow

# CodeBuild ログ
aws logs tail /aws/codebuild/agentcore-weather-agent-build --follow
```

### X-Ray トレース（自動）

分散トレーシングは X-Ray に自動的に配信されます。[X-Ray コンソール](https://console.aws.amazon.com/xray/home) でトレースを表示できます。

### メトリクス

CloudWatch でメトリクスにアクセス：
- エージェント呼び出し回数
- ツール使用頻度（Browser、Code Interpreter、Memory）
- エージェント実行時間
- エラー率
- Code Interpreter 実行時間

### AWS コンソール

AWS コンソールでモニタリング：
- **CloudWatch Logs**: `/aws/vendedlogs/bedrock-agentcore/${runtime_id}` の Vended logs
- **X-Ray**: 分散リクエストトレース
- **Bedrock AgentCore**: [コンソールリンク](https://console.aws.amazon.com/bedrock/home#/agentcore)
- **ECR リポジトリ**: Docker イメージ
- **CodeBuild**: ビルドステータス
- **S3 結果バケット**: 生成されたアーティファクト

## セキュリティ

### IAM 権限

**エージェント実行ロール:**
- 標準 AgentCore 権限
- ECR イメージプルアクセス
- 結果バケットへの S3 読み取り/書き込み
- CloudWatch Logs 書き込みアクセス
- ツール固有の権限（Browser、Code Interpreter、Memory アクセス）

**CodeBuild ロール:**
- ソースバケットへの S3 アクセス
- ECR プッシュアクセス
- CloudWatch Logs 書き込みアクセス

### ネットワークセキュリティ

- エージェントは指定されたネットワークモード（PUBLIC/PRIVATE）で実行
- ECR リポジトリにはアカウントレベルのアクセス制御あり
- S3 バケットはパブリックアクセスをブロック
- IAM ポリシーは最小権限の原則に従う
- ツールリソースはネットワーク分離を使用

### シークレット管理

機密データの場合：
- AWS Secrets Manager を使用
- シークレット ARN を環境変数として渡す
- エージェントコードで実行時にシークレットを取得

## トラブルシューティング

### よくある問題

**問題**: エージェントがツールにアクセスできない
- **解決策**: ツール ID が環境変数として設定されているか確認
- **確認**: IAM 権限にツールアクセスが含まれているか

**問題**: Code Interpreter が失敗
- **解決策**: CloudWatch ログで Python エラーを確認
- **確認**: 結果バケットの権限を確認

**問題**: Browser ツールがタイムアウト
- **解決策**: ネットワーク接続を確認
- **確認**: ターゲット Web サイトにアクセス可能か確認

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
terraform state show aws_bedrockagentcore_agent_runtime.agent

# ツール ID を取得
terraform output browser_id
terraform output code_interpreter_id
terraform output memory_id

# 結果バケットを確認
aws s3 ls s3://$(terraform output -raw results_bucket_name)/

# 詳細なビルドログを取得
PROJECT_NAME=$(terraform output -raw agent_codebuild_project_name)
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
   python test_weather_agent.py $(terraform output -raw agent_runtime_arn)
   ```

2. 特定のユースケースに合わせて **エージェントをカスタマイズ**
   - 天気データソースを修正
   - カスタム天気分析ロジックを追加
   - 追加の外部 API を統合
   - 可視化機能を強化

3. **関連パターンを探索**
   - [マルチエージェントランタイム](../multi-agent-runtime/) - エージェント間通信
   - [MCP サーバーパターン](../mcp-server-agentcore-runtime/) - JWT 認証付き MCP プロトコル
   - [AgentCore サンプル](https://github.com/aws-samples/amazon-bedrock-agentcore-samples) - その他の例

4. **本番機能を追加**
   - モニタリングとアラート
   - カスタム認証レイヤー
   - プライベートネットワーキング用の VPC デプロイ
   - CI/CD パイプライン統合
   - レート制限とスロットリング

## リソース

- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Terraform AWS プロバイダー](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [エージェント間通信](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-a2a.html)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## コントリビューション

コントリビューションを歓迎します！詳細は [コントリビューションガイド](../../../CONTRIBUTING.md) を参照してください。

## ライセンス

このプロジェクトは MIT-0 ライセンスの下でライセンスされています。詳細は [LICENSE](../../../LICENSE) ファイルを参照してください。
