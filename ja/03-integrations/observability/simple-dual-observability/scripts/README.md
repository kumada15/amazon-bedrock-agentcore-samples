# AgentCore オブザーバビリティスクリプト

Simple Dual Observability チュートリアル用のデプロイおよびセットアップスクリプト。

## 概要

これらのスクリプトは、Braintrust サポート付きの Amazon Bedrock AgentCore オブザーバビリティの完全なセットアップを自動化します。

**注意:** このドキュメントのすべてのコマンドは、`scripts/` フォルダー内からではなく、チュートリアルのルートディレクトリ（`simple-dual-observability`）から実行することを前提としています。スクリプトを呼び出すには `scripts/<script-name>.sh` を使用してください。

## スクリプト

### check_prerequisites.sh

セットアップを実行する前にすべての前提条件が満たされていることを確認します。

```bash
# 前提条件チェックを実行
scripts/check_prerequisites.sh

# 詳細出力で実行
scripts/check_prerequisites.sh --verbose
```

**実行内容:**
1. AWS CLI のインストールと設定を確認
2. Python 3.11 以上がインストールされていることを確認
3. 必要な Python パッケージ（boto3）を確認
4. AWS 認証情報と権限を検証
5. サービスの可用性をテスト（AgentCore、CloudWatch、X-Ray）
6. 問題に対する実行可能な修正を提供

他のスクリプトを実行する前に、まずこれを実行してください。

### setup_all.sh

完全なエンドツーエンドのセットアップオーケストレーション。

```bash
# デフォルト設定でセットアップ
scripts/setup_all.sh

# Braintrust 統合付きでセットアップ
scripts/setup_all.sh --api-key bt-xxxxx --project-id your-project-id

# 特定のリージョンでセットアップ
scripts/setup_all.sh --region us-west-2
```

**実行内容:**
1. AgentCore Runtime にエージェントをデプロイ
2. オプションで Braintrust 統合を設定

### deploy_agent.sh

Strands エージェントを AgentCore Runtime にデプロイします。

```bash
# デフォルトでデプロイ
scripts/deploy_agent.sh

# カスタムリージョンとモデルでデプロイ
scripts/deploy_agent.sh --region us-west-2 --model global.anthropic.claude-haiku-4-5-20251001-v1:0

# Braintrust 統合付きでデプロイ
export BRAINTRUST_API_KEY=your_api_key_here
scripts/deploy_agent.sh
```

**実行内容:**
1. ツール（天気、時間、計算機）付きのエージェント設定を作成
2. AgentCore Runtime にエージェントをデプロイ
3. OTEL 環境変数を設定
4. デモで使用するためにエージェント ID を保存

**環境変数:**
- `AWS_REGION` - デプロイ用の AWS リージョン
- `AGENT_NAME` - エージェントの名前
- `MODEL_ID` - Bedrock モデル識別子
- `BRAINTRUST_API_KEY` - Braintrust API キー（オプション）
- `SERVICE_NAME` - OTEL トレース用のサービス名

### cleanup.sh

チュートリアルで作成されたすべてのリソースを削除します。

```bash
# 対話式クリーンアップ
scripts/cleanup.sh

# プロンプトなしで強制クリーンアップ
scripts/cleanup.sh --force

# ログを保持してクリーンアップ
scripts/cleanup.sh --keep-logs
```

**実行内容:**
1. AgentCore Runtime からデプロイされたエージェントを削除
2. ローカル設定ファイルをクリーンアップ

**環境変数:**
- `AWS_REGION` - リソース用の AWS リージョン

## クイックスタート

### ステップ 0: 前提条件の確認

```bash
scripts/check_prerequisites.sh
```

続行する前に報告された問題を修正してください。

### 基本セットアップ

```bash
scripts/setup_all.sh

# オブザーバビリティデモを実行（メタデータからエージェント ID を自動的に読み取り）
python simple_observability.py --scenario all
```

### Braintrust 付きセットアップ

```bash
# 環境から Braintrust API キーを使用
export BRAINTRUST_API_KEY=your_api_key_here
export BRAINTRUST_PROJECT_ID=your_project_id
scripts/setup_all.sh

# または引数として渡す
scripts/setup_all.sh --api-key your_api_key_here --project-id your_project_id

# オブザーバビリティデモを実行
python simple_observability.py --scenario all
```

### 手動ステップバイステップ

```bash
# 1. エージェントをデプロイ
scripts/deploy_agent.sh

# 2. デモを実行（.deployment_metadata.json からエージェント ID を自動的に読み取り）
python simple_observability.py --scenario all
```

## 生成されるファイル

スクリプトを実行後、以下のファイルが作成されます：

- `.agent_id` - デプロイされたエージェント ID
- `.env` - API キーとリージョンを含む環境設定
- `braintrust-usage.md` - Braintrust 使用ガイド（設定された場合）
- `.env.backup` - .env のバックアップ（クリーンアップ時に作成）

## 前提条件

### 必須

- 認証情報が設定された AWS CLI
- Python 3.11 以上
- boto3 がインストール済み
- ご利用のリージョンで Amazon Bedrock AgentCore にアクセス可能

### Braintrust 統合用

- Braintrust アカウント（https://www.braintrust.dev で無料サインアップ）
- Braintrust API キー

## 一般的な操作

### エージェント設定の表示

```bash
# エージェント ID を取得
AGENT_ID=$(cat .agent_id)

# エージェントを説明
aws bedrock-agentcore-runtime describe-agent \
    --agent-id $AGENT_ID \
    --region us-east-1
```

### トレースの表示

```bash
# Braintrust（設定されている場合）
echo "https://www.braintrust.dev/app"
```

### エージェント設定の更新

```bash
# 古いエージェントをクリーンアップ
scripts/cleanup.sh

# 新しい設定でデプロイ
scripts/deploy_agent.sh --model global.anthropic.claude-haiku-4-5-20251001-v1:0
```

## トラブルシューティング

### エージェントのデプロイが失敗する

確認事項：
1. AWS 認証情報が設定されている：`aws sts get-caller-identity`
2. リージョンが AgentCore Runtime をサポートしている：`aws bedrock-agentcore-runtime help`
3. 必要な IAM 権限がある

### Braintrust にトレースが表示されない

確認事項：
1. API キーが正しく設定されている
2. プロジェクト ID が有効
3. エージェントが少なくとも一度呼び出されている
4. 数秒後に Braintrust ダッシュボードを確認

## サポート

特定の問題については：
- AgentCore：AWS サポートまたは Bedrock ドキュメント
- Braintrust：support@braintrust.dev

## 追加リソース

- AgentCore ドキュメント：[Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/)
- Braintrust：[Braintrust ドキュメント](https://www.braintrust.dev/docs)
- OpenTelemetry：[OTEL ドキュメント](https://opentelemetry.io/docs/)
