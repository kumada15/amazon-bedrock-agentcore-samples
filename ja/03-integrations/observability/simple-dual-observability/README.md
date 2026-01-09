# シンプルなデュアルプラットフォームオブザーバビリティチュートリアル

## 概要

このチュートリアルでは、Amazon Bedrock AgentCoreエージェント向けの2つのオブザーバビリティアプローチを紹介します：

1. **CloudWatchオブザーバビリティ（デフォルトで常時有効）**: AgentCore Runtimeは設定不要でCloudWatch Logsにベンダートレースを自動的に提供します
2. **Braintrustオブザーバビリティ（オプション）**: エージェントからBraintrustプラットフォームにOpenTelemetryトレースをエクスポートすることで、AI特化のオブザーバビリティを追加します

このチュートリアルでは、AgentCore Runtimeがどのように CloudWatchを通じて自動オブザーバビリティを提供し、オプションでStrandsエージェントからOpenTelemetryトレースをエクスポートすることでBraintrustを通じたAI特化のモニタリングを追加できるかを示します。注：CloudWatchトレースはAgentCore Runtimeインフラストラクチャによって提供され、BraintrustはエージェントコードからOTELトレースを直接受信します。

### ユースケースの詳細
| 項目                | 詳細                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| ユースケースタイプ   | オブザーバビリティ、モニタリング                                                                                                           |
| エージェントタイプ          | ツール付きの単一エージェント                                                                                                             |
| ユースケースコンポーネント | AgentCore Runtime、Strandsエージェント、組み込みツール、デュアルプラットフォームオブザーバビリティ（CloudWatch + Braintrust）                          |
| ユースケースの業種   | DevOps、プラットフォームエンジニアリング、AI運用                                                                                        |
| サンプルの複雑さ  | 中級                                                                                                                        |
| 使用SDK            | Amazon Bedrock AgentCore Runtime、boto3、OpenTelemetry、Strands                                                                   |

## アセット

| アセット | 説明 |
|-------|-------------|
| CloudWatchダッシュボード | エージェントメトリクス、レイテンシー、エラー率を表示する事前設定済みダッシュボード |
| Braintrustプロジェクト | LLMコスト追跡と品質メトリクスを備えたAI特化のオブザーバビリティ |
| サンプルエージェント | ツール実行トレースをデモンストレーションする天気、時刻、電卓ツール |

### ユースケースアーキテクチャ

```
┌─────────────────────────────────────────────────────────────────────┐
│  オブザーバビリティアーキテクチャ                                         │
│                                                                     │
│  ローカルPC                                                        │
│    ↓ (simple_observability.pyまたはtest_agent.shを実行)              │
│  Python CLIスクリプト（boto3クライアント）                                  │
│    ↓ (APIコール: invoke_agent)                                      │
│  AgentCore Runtime（マネージドサービス）                               │
│    ├─ 自動CloudWatchインストルメンテーション（AgentCore管理）    │
│    │  └─ CloudWatch Logsへのベンダートレース                         │
│    ├─ Strandsエージェント（Runtimeにデプロイ）                         │
│    │  ├─ 天気ツール（組み込み）                                  │
│    │  ├─ 時刻ツール（組み込み）                                     │
│    │  └─ 電卓ツール（組み込み）                               │
│    │  └─ OTELエクスポーター（オプション、BRAINTRUST_API_KEY設定時）  │
│    │                                                               │
│  ┌──────────────────────────┬────────────────────────────────────┐
│  │ CloudWatch Logs          │ Braintrust（オプション）              │
│  │ （AgentCore Runtimeから） │ （Strands OTELエクスポートから）         │
│  │ 常時有効           │ BRAINTRUST_API_KEY設定時のみ  │
│  └──────────────────────────┴────────────────────────────────────┘
│                                                                     │
│  凡例: CloudWatch = 自動インフラストラクチャレベルのオブザーバビリティ    │
│       Braintrust = オプションのエージェントレベルOTELエクスポート（有効時）   │
│       異なるトレースソース、補完的なプラットフォーム             │
└─────────────────────────────────────────────────────────────────────┘
```

### ユースケースの主な機能

- **自動CloudWatchオブザーバビリティ**: AgentCore Runtimeはコード変更なしでCloudWatch Logsにベンダートレースを自動的に提供します
- **オプションのBraintrustエクスポート**: StrandsエージェントはオプションでBraintrustプラットフォームに直接OpenTelemetryトレースをエクスポートしてAI特化のモニタリングを行えます
- **デュアルプラットフォーム機能**: 異なるトレースソースを使用して、同じエージェント実行をCloudWatch（AWSネイティブ）とオプションでBraintrust（AI特化）で表示できます
- **フルマネージドRuntime**: AgentCore Runtimeはすべてのインフラストラクチャ管理と自動CloudWatchインストルメンテーションを処理します
- **組み込みツール**: デモンストレーション用の天気、時刻、電卓ツールを備えたStrandsエージェント
- **包括的なトレース**: 両プラットフォームでエージェント呼び出し、モデルコール、ツール選択、実行スパンをキャプチャします
- **プラットフォーム比較**: AWSネイティブとAI特化のオブザーバビリティの長所とトレードオフを示します

## 詳細ドキュメント

このオブザーバビリティチュートリアルの包括的な情報については、以下の詳細ドキュメントを参照してください：

### オブザーバビリティガイド
- **[Observability Options](docs/observability-options.md)** - 3つのデプロイメントアプローチの比較、実際のCloudWatchログ、各プラットフォームがキャプチャするもの
- **[Design & Architecture](docs/design.md)** - システムアーキテクチャ、コンポーネントの相互作用、OTELフロー図

### セットアップと設定
- **[Braintrust Setup](docs/braintrust-setup.md)** - Braintrustアカウントの作成、APIキー管理、ダッシュボード設定

### デモンストレーションと開発
- **[Demo Guide](scenarios/demo-guide.md)** - ステップバイステップのシナリオ、プレゼンテーションのヒント、デモ前チェックリスト
- **[Troubleshooting](docs/troubleshooting.md)** - よくある問題、解決策、デバッグ技術
- **[Development](docs/development.md)** - ローカルテスト、コード構造、新しいツールの追加

## デモ動画

このチュートリアルの実際の動作を見るには、以下の短い動画をご覧ください：

| 説明 | 動画 |
|---|---|
| **CloudWatchメトリクスとセッショントレース**<br>CloudWatchがGenAI Observabilityコンソールでエージェント呼び出し、ツール実行、トレースの詳細をどのように表示するかを確認できます。<br><br><details><summary>表示内容：</summary><ul><li>エージェント実行メトリクス（リクエスト数、レイテンシー、成功率）</li><li>完全な実行タイムラインを持つセッショントレース</li><li>ツールコールとそれぞれのレイテンシー</li><li>エラー処理とリカバリー</li></ul></details> | ▶️ **[動画を見る](https://github.com/user-attachments/assets/63c877e8-9611-4824-9aa4-7d1ae9ed9b1d)** |
| **CloudWatch APM（アプリケーションパフォーマンスモニタリング）**<br>詳細なパフォーマンス分析とスパン可視化のためのAPMコンソールを探索します。<br><br><details><summary>表示内容：</summary><ul><li>エージェントとツールの依存関係を示すサービスマップ</li><li>タイミング内訳を含むスパンウォーターフォール可視化</li><li>パフォーマンスメトリクスとレイテンシーパーセンタイル</li><li>ノードの健全性とエラー追跡</li></ul></details> | ▶️ **[動画を見る](https://github.com/user-attachments/assets/dfad7acc-0523-41b8-b961-f5480fc9e456)** |
| **Braintrustダッシュボード**<br>BraintrustがLLM固有のメトリクスとトレースの詳細をどのようにキャプチャして表示するかを確認します。<br><br><details><summary>表示内容：</summary><ul><li>実行履歴とパフォーマンスを含む実験リスト</li><li>強力なフィルタリングを備えたトレースエクスプローラー</li><li>LLMコスト追跡とトークン使用量の内訳</li><li>スパンタイムライン可視化</li><li>入出力分析と品質メトリクス</li></ul></details> | ▶️ **[動画を見る](https://github.com/user-attachments/assets/d6ec96cb-17a7-41b8-a73d-d52a537842fa)** |

## 前提条件

| 要件 | 説明 |
|-------------|-------------|
| Python 3.11+ | デプロイメントスクリプトとエージェントコード用のPythonランタイム |
| pip | 依存関係用のPythonパッケージインストーラー |
| Docker | エージェントコンテナのビルドに必要。インストール: https://docs.docker.com/get-docker/ |
| AWSアカウント | リージョンでBedrock アクセスが有効なアクティブなAWSアカウント |
| AWS CLI | 認証情報が設定済み。確認: `aws sts get-caller-identity` |
| IAM権限 | AgentCore RuntimeとCloudWatchに必要な権限（以下参照） |
| Braintrustアカウント（オプション） | AI特化のオブザーバビリティ用のオプション無料層アカウント。https://www.braintrust.dev/signup でサインアップ。詳細な設定は[Braintrust Setup](docs/braintrust-setup.md)を参照。 |
| Amazon Bedrockアクセス | リージョンでClaude 3.5 Haikuモデルへのアクセス |

### 必要なIAM権限

デプロイメントプロセスでは、AWS CodeBuildを使用してDockerコンテナをビルドし、AgentCore Runtimeにデプロイします。IAMユーザーまたはロールには包括的な権限が必要です。

#### クイックセットアップ：ポリシーのアタッチ

完全なIAMポリシーが[`docs/iam-policy-deployment.json`](docs/iam-policy-deployment.json)に提供されています。

**ポリシーをアタッチするには：**

```bash
# AWS CLIを使用
aws iam put-user-policy \
  --user-name YOUR_IAM_USER \
  --policy-name BedrockAgentCoreDeployment \
  --policy-document file://docs/iam-policy-deployment.json

# またはIAMロールの場合
aws iam put-role-policy \
  --role-name YOUR_ROLE_NAME \
  --policy-name BedrockAgentCoreDeployment \
  --policy-document file://docs/iam-policy-deployment.json
```

#### 必要な権限カテゴリ

1. **CodeBuild**（Dockerコンテナのビルド用）：
   - `codebuild:CreateProject`、`codebuild:UpdateProject`、`codebuild:StartBuild`
   - `codebuild:BatchGetBuilds`、`codebuild:BatchGetProjects`

2. **ECR**（コンテナイメージの保存用）：
   - `ecr:CreateRepository`、`ecr:GetAuthorizationToken`
   - `ecr:PutImage`、`ecr:BatchCheckLayerAvailability`

3. **S3**（CodeBuildソースストレージ用）：
   - `s3:CreateBucket`、`s3:PutObject`、`s3:GetObject`

4. **IAM**（実行ロールの作成用）：
   - `iam:CreateRole`、`iam:AttachRolePolicy`、`iam:PassRole`

5. **Bedrock AgentCore**（エージェントデプロイメント用）：
   - `bedrock-agentcore:*`

6. **Bedrock**（モデル呼び出し用）：
   - `bedrock:InvokeModel`

7. **CloudWatch**（オブザーバビリティ用）：
   - `cloudwatch:PutMetricData`、`logs:CreateLogGroup`、`logs:CreateLogStream`、`logs:PutLogEvents`

完全なポリシーについては[`docs/iam-policy-deployment.json`](docs/iam-policy-deployment.json)を参照してください。

## 環境設定

このチュートリアルでは、認証情報管理を容易にするための`.env`ファイルによるオプション設定をサポートしています。

### .envファイルのセットアップ

テンプレートが`.env.example`（リポジトリにコミット済み）に提供されています：

```bash
# サンプルテンプレートをコピー
cp .env.example .env

# .envを編集して値を設定（ファイルは.gitignoreにあり、コミットされません）
```

**.envの設定変数：**

| 変数 | 必須 | 目的 |
|----------|----------|---------|
| `AWS_REGION` | いいえ | デプロイメント用のAWSリージョン（デフォルト: `us-east-1`） |
| `AWS_PROFILE` | いいえ | AWS認証情報プロファイル（デフォルト: `default`）。ローカルに複数のプロファイルが設定されている場合に使用 |
| `BRAINTRUST_API_KEY` | 条件付き | デュアルオブザーバビリティ用のBraintrust APIキー（オプション） |
| `BRAINTRUST_PROJECT_ID` | 条件付き | デュアルオブザーバビリティ用のBraintrustプロジェクトID（オプション） |
| `AGENTCORE_AGENT_ID` | いいえ | エージェントID（デプロイメント後に`.deployment_metadata.json`に自動保存） |

**重要な注意事項：**
- `.env`ファイルは`.gitignore`にあり、リポジトリにコミットされることはありません
- `.env.example`は参照用テンプレートとしてコミットされています
- Braintrust認証情報はオプションです - CloudWatchオブザーバビリティのみを使用する場合は省略してください
- セキュリティのため、実際の認証情報をリポジトリにコミットしないでください

### AWS認証情報の設定

ローカルマシンから実行する場合（EC2などのAWSコンピュートインスタンスからではなく）、以下のいずれかの方法でAWS認証情報を設定してください：

**オプション1：AWS CLI設定を使用（推奨）**

名前付きプロファイルを使用してAWS CLIで認証情報を設定：

```bash
# 新しいプロファイルをセットアップ（対話式）
aws configure --profile dev-profile

# 以下の入力を求められます：
# - AWS Access Key ID
# - AWS Secret Access Key
# - デフォルトリージョン
# - デフォルト出力形式

# その後、.envまたはコマンド実行時にプロファイルを指定
export AWS_PROFILE=dev-profile
scripts/deploy_agent.sh
```

**オプション2：環境変数を使用**

認証情報を環境変数として直接設定：

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
scripts/deploy_agent.sh
```

**オプション3：IAMロールを使用（EC2インスタンス用）**

EC2インスタンスまたは他のAWSコンピュートサービスで実行する場合、IAMロールが自動的に利用可能です。手動での認証情報設定は不要です：

```bash
# 認証情報を設定せずに単純に実行
scripts/deploy_agent.sh  # 自動的にIAMロールを使用
```

**オプション4：プロファイル付きの.envファイルを使用**

`.env`にプロファイル設定を保存：

```bash
# .envファイル
AWS_PROFILE=dev-profile
AWS_REGION=us-east-1
```

追加の環境変数なしで実行：

```bash
scripts/deploy_agent.sh  # .envのAWS_PROFILEを使用
```

**認証情報が機能していることを確認：**

```bash
# 設定されているAWSアカウント/ユーザーを確認
aws sts get-caller-identity

# 期待される出力：
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }
```

AWS CLI認証情報設定の詳細については、[AWS CLI Configuration Guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)を参照してください。

### デプロイメントメタデータの自動読み込み

`scripts/deploy_agent.sh`でエージェントをデプロイすると、スクリプトはデプロイメント情報（エージェントIDとARNを含む）を`scripts/`ディレクトリの`.deployment_metadata.json`に自動的に保存します。

**主なメリット**：`AGENTCORE_AGENT_ID`環境変数を手動で設定する必要が常にあるわけではありません。デモまたはテストスクリプトを実行すると、環境変数が設定されていない場合、コードは自動的に`.deployment_metadata.json`からエージェントIDを読み取ります。

**エージェントID解決の優先順位**：
1. コマンドライン引数：`--agent-id <agent-id>`
2. デプロイメントメタデータファイル：`scripts/.deployment_metadata.json`（存在する場合）
3. 環境変数：`AGENTCORE_AGENT_ID`または`AGENTCORE_AGENT_ARN`

つまり、最初のデプロイメント後は、単純に実行できます：
```bash
# これらのコマンドはAGENTCORE_AGENT_IDを設定せずに機能します
# エージェントIDは.deployment_metadata.jsonから自動的に読み込まれるためです
uv run python simple_observability.py --scenario all
scripts/tests/test_agent.sh --test weather
```

メタデータファイルには以下が含まれます：
- `agent_id`：エージェントの一意識別子
- `agent_arn`：エージェントの完全なAmazon Resource Name
- `deployment_timestamp`：エージェントがデプロイされた日時
- その他のデプロイメント設定

**注意**：`scripts/delete_agent.py`を使用してエージェントを削除すると、メタデータファイルもクリーンアップされ、デモスクリプトを再度実行する前に再デプロイが必要になります。

## クイックスタート

3ステップでエージェントを実行：

```bash
# 1. 依存関係をインストール
uv sync

# 2. エージェントをデプロイ（オプションでBraintrustオブザーバビリティ付き）
# オプションA：.envファイルを使用（繰り返しのデプロイメントに推奨）
cp .env.example .env
# .envを編集 - Braintrust認証情報を追加（オプション）：
#   BRAINTRUST_API_KEY=bt-xxxxxxxxxxxxxxxxxxxxx
# CloudWatchトレースは自動。Braintrustはオプション（BRAINTRUST_API_KEY設定時のみ）
scripts/deploy_agent.sh

# オプションB：CloudWatchオブザーバビリティのみ（デフォルト、Braintrustなし）
scripts/deploy_agent.sh --region us-east-1

# オプションC：.envにBraintrust認証情報を追加し、コマンドラインでリージョンを上書き
# まず、.envにBraintrust認証情報を編集してから：
scripts/deploy_agent.sh --region us-west-2  # .envの認証情報を使用

# オプションD：.envとコマンドライン引数の両方を上書き
# まず.envに正確なパラメータ名を追加：
#   BRAINTRUST_API_KEY=bt-xxxxxxxxxxxxxxxxxxxxx
# その後、コマンドライン上書きでデプロイ：
scripts/deploy_agent.sh \
    --region us-east-1 \
    --braintrust-api-key bt-xxxxxxxxxxxxxxxxxxxxx
# エージェントはOTELトレースをBraintrustにエクスポート（CloudWatchは自動）

# オプションE：既存のエージェントを更新（競合時に自動更新）
# 新しいエージェントを作成する代わりに、既にデプロイされたエージェントを更新するにはこのフラグを使用：
scripts/deploy_agent.sh --auto-update-on-conflict
# delete_agent.py実行後の再デプロイメントに便利

# オプションF：deploy_agent.pyを直接呼び出し（上級者向け）
# deploy_agent.shとdeploy_agent.pyは両方とも同じ引数をサポート：
uv run python scripts/deploy_agent.py \
    --region us-east-1 \
    --braintrust-api-key sk-user-xxxxxxxxxxxxxxxxxxxxx \
    --braintrust-project-id proj-xxxxxxxxxxxxxxxxxxxxx \
    --auto-update-on-conflict

# 3. エージェントをテスト
scripts/tests/test_agent.sh --test calculator
scripts/tests/test_agent.sh --test weather
scripts/tests/test_agent.sh --prompt "What time is it in Tokyo?"

# 4. CloudWatchコンソールでトレースを有効化（重要）
# ⚠️ エージェントからトレースを表示するにはトレースを有効にする必要があります
# AWS CloudWatchコンソールに移動：
#   1. Agent Runtimeに移動
#   2. リストからエージェントを選択
#   3. 下にスクロールして「Tracing」セクションまで移動
#   4. 「Edit」をクリック
#   5. 「Enable Tracing」をクリック
#   6. 「Save」ボタンを押す
# このステップをスキップすると、CloudWatchでトレースが表示されません！

# 5. CloudWatchログを確認してトレースを表示
# シェルスクリプトを使用（シンプル）：
# 過去30分間のログを表示
scripts/check_logs.sh --time 30m

# エラーのみ表示
scripts/check_logs.sh --errors

# リアルタイムでログをフォロー（テスト実行中に便利）
scripts/check_logs.sh --follow

# 過去1時間のログを表示
scripts/check_logs.sh --time 1h

# またはPythonスクリプトでより多くのオプションを使用（下記CloudWatch Logsセクション参照）：
uv run python scripts/get_cw_logs.py --follow
```

## デプロイメントシナリオ

### 初回デプロイメント

初回デプロイメントでは、クイックスタートセクションのいずれかのオプションを使用：

```bash
scripts/deploy_agent.sh
```

これにより、一意のエージェントIDを持つ新しいエージェントが作成され、デプロイメントメタデータが`.deployment_metadata.json`に保存されます。

### エージェント削除後の再デプロイメント

`scripts/delete_agent.py`を使用してエージェントを削除し、再デプロイする場合：

```bash
# 実行後：uv run python scripts/delete_agent.py
# これによりエージェントが削除され、メタデータファイルがクリーンアップされます

# 競合時に自動更新でエージェントを再デプロイ：
scripts/deploy_agent.sh --auto-update-on-conflict
```

`--auto-update-on-conflict`フラグはデプロイメントスクリプトに以下を指示します：
- 同じ名前のエージェントが既に存在するか確認
- 存在する場合、失敗する代わりに自動的に更新
- 新しいエージェントIDで`.deployment_metadata.json`を再作成

### 既存エージェントの更新

削除と再デプロイなしでエージェントコードを更新するには：

```bash
# エージェントコードを修正（例：agent/weather_time_agent.py）
# その後、自動更新で再デプロイ：
scripts/deploy_agent.sh --auto-update-on-conflict
```

これは削除して再デプロイするワークフローより高速で、既存のオブザーバビリティデータを保持します。

詳細な設定とセットアップ手順については、以下を参照：
- **[Braintrust Setup](docs/braintrust-setup.md)** - Braintrustアカウントの作成、APIキー管理、ダッシュボードセットアップ
- **[System Design](docs/design.md)** - 完全なアーキテクチャとOTELトレースフローの詳細

## ⚠️ 重要：デプロイメント後にトレースを有効化

**エージェントからトレースを表示するには、CloudWatchコンソールでトレースを有効にする必要があります。**

`scripts/deploy_agent.sh`でエージェントをデプロイした後、以下の手順に従ってください：

1. AWS CloudWatchコンソールを開く：https://console.aws.amazon.com/cloudwatch
2. 左サイドバーで**Agent Runtime**に移動
3. リストから**エージェントを選択**（名前は`weather_time_observability_agent-XXXXX`）
4. **下にスクロール**して**Tracing**セクションまで移動
5. **Edit**ボタンをクリック
6. **Enable Tracing**のチェックボックスをオン
7. **Save**ボタンを押す

**⚠️ このステップをスキップすると、CloudWatchでトレースが表示されません！**

トレースが有効になると、以下が可能になります：
- エージェントのCloudWatch Logsを表示
- すべてのスパン（LLMコール、ツール呼び出し、エージェント推論）を確認
- トレースIDを使用してログとトレースを関連付け

## チュートリアルの実行

デモスクリプトは、さまざまなオブザーバビリティ機能を示す3つのシナリオを提供します。

エージェントIDは`.deployment_metadata.json`から自動的に読み込まれます（上記の[デプロイメントメタデータの自動読み込み](#デプロイメントメタデータの自動読み込み)を参照）。上書きしたい場合を除き、`--agent-id`を指定する必要はありません。

### すべてのシナリオを実行（推奨）

3つのシナリオすべてを順番に実行し、それぞれの間に自動的に遅延を入れます：

```bash
# チュートリアルルートディレクトリから
# エージェントIDは.deployment_metadata.jsonから自動的に読み込まれます
uv run python simple_observability.py --scenario all

# またはエージェントIDを明示的に指定
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all
```

### 個別シナリオの実行

**シナリオ1：成功したマルチツールクエリ**

複数のツールコールを伴う成功したエージェント実行をデモンストレーション：

```bash
# .deployment_metadata.jsonからエージェントIDを自動的に使用
uv run python simple_observability.py --scenario success

# またはエージェントIDを明示的に指定
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

クエリ：「シアトルの天気と現在の時刻は？」

期待される動作：
- エージェントが2つのツール（天気 + 時刻）を選択
- 両方のツールが正常に実行
- エージェントがレスポンスを集約
- 両プラットフォームですべてのスパンが表示されるクリーンなトレース

**シナリオ2：エラー処理**

オブザーバビリティを通じたエラー伝播と処理をデモンストレーション：

```bash
# .deployment_metadata.jsonからエージェントIDを自動的に使用
uv run python simple_observability.py --scenario error

# またはエージェントIDを明示的に指定
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error
```

クエリ：「-5の階乗を計算して」

期待される動作：
- エージェントが電卓ツールを選択
- ツールがエラーを返す（階乗の無効な入力）
- エラーステータスがスパンに記録
- トレースで表示される適切なエラー処理

### 追加オプション

```bash
# 詳細な実行トレースのためにデバッグログを有効化
# （エージェントIDは.deployment_metadata.jsonから自動的に読み込まれます）
uv run python simple_observability.py --scenario all --debug

# 異なるAWSリージョンを指定
uv run python simple_observability.py --region us-west-2 --scenario success

# メタデータを明示的なエージェントIDで上書き
uv run python simple_observability.py --agent-id <your-agent-id> --scenario success

# 環境変数を使用（メタデータファイルが見つからない場合のフォールバック）
export AGENTCORE_AGENT_ID=abc123xyz
uv run python simple_observability.py

# 最小限のコマンド（.deployment_metadata.jsonのデフォルトを使用）
uv run python simple_observability.py
```

## 期待される結果

### CloudWatch Logs

check_logs.shスクリプトとAWSコンソールを使用してCloudWatchログを表示：

**check_logs.shスクリプトを使用（クイックレビューに推奨）：**
```bash
# 過去30分間のエージェント実行ログを表示
scripts/check_logs.sh --time 30m

# テスト実行中にリアルタイムでログをフォロー
scripts/check_logs.sh --follow

# エラーメッセージのみ表示
scripts/check_logs.sh --errors

# 過去1時間のログを表示
scripts/check_logs.sh --time 1h
```

**表示される内容：**
- エージェント実行タイムスタンプ
- ツール呼び出しログ
- モデルコールとレスポンス
- 実行ステータスと完了メッセージ
- エラーメッセージとスタックトレース（シナリオ2）
- パフォーマンスメトリクスとレイテンシー

### Braintrustトレース

AI特化のメトリクスでBraintrustで同じトレースを表示：

1. Braintrustダッシュボードを開く：https://www.braintrust.dev/app
2. プロジェクトに移動：「agentcore-observability-demo」
3. トレースタブを表示
4. スクリプト出力からトレースIDを検索

**表示される内容：**
- LLMコールの詳細（モデル、temperature、max tokens）
- トークン消費量（入力トークン、出力トークン、合計）
- 操作ごとのコスト内訳（モデル価格に基づいて計算）
- インタラクティブな可視化を備えたレイテンシータイムライン
- ツール実行の詳細とパラメータ
- スタックトレース付きのエラーアノテーション（シナリオ2）
- カスタム属性とイベント

### プラットフォーム比較

**CloudWatch（自動、AgentCore Runtimeからのインフラストラクチャレベルトレース）：**
- 他のAWSサービスとのネイティブAWS統合
- 自動アラート用のCloudWatch Alarms
- VPC Flow Logsとの相関
- より長い保持オプション（最大10年）
- AWS Systems ManagerおよびAWS Configとの統合
- AgentCore Runtimeからベンダートレースを受信

**Braintrust（オプション、StrandsエージェントからのエージェントレベルOTELトレース）：**
- AI特化のメトリクス（品質スコア、ハルシネーション検出）
- プロバイダー間のLLMコスト追跡
- プロンプトバージョン比較とA/Bテスト
- 品質保証のための評価フレームワーク
- 専門的なAI/ML可視化と分析
- `BRAINTRUST_API_KEY`環境変数が必要

**両プラットフォームが提供するもの：**
- リアルタイムトレース取り込み
- トレースIDまたはセッションIDによるクエリ
- 属性付きのスパンレベル詳細
- 分散トレースのサポート
- **注意**：異なるトレースソース（ベンダートレース vs OTEL形式）、同一ではない

## クリーンアップ

不要なAWS料金を避けるため、作成したすべてのリソースを削除：

```bash
# クリーンアップスクリプトを実行
scripts/cleanup.sh

# または確認をスキップするためにforceフラグ付きで
scripts/cleanup.sh --force
```

## 追加リソース

### ドキュメント
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [CloudWatch Logs Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
- [Braintrust Documentation](https://www.braintrust.dev/docs)
- [OpenTelemetry Specification](https://opentelemetry.io/docs/)

## 次のステップ

このチュートリアル完了後、以下を検討してください：

1. ユースケースに合わせて組み込みツール（天気、時刻、電卓）をカスタマイズ
2. エラー率モニタリング用のCloudWatch Alarmsを設定
3. エージェント品質モニタリング用のBraintrust評価をセットアップ
4. オブザーバビリティを本番アプリケーションに統合
5. 高度なOTEL機能（カスタムスパン、イベント、メトリクス）を探索
6. 複数のプラットフォーム間でオブザーバビリティデータを比較
7. ユースケースに合わせたカスタムダッシュボードを構築

## 免責事項

このリポジトリで提供されるサンプルは、実験および教育目的のみを対象としています。概念と技術をデモンストレーションしますが、適切なセキュリティ強化とテストなしに本番環境で直接使用することを意図していません。プロンプトインジェクションやその他のセキュリティリスクから保護するために、Amazon Bedrock Guardrailsを導入してください。
