# トラブルシューティングガイド

## 概要

このガイドでは、Simple Dual Observability チュートリアルの実行時に発生する一般的な問題の解決方法を提供します。

## よくある誤解

### エージェントコードをローカルで実行できない

**問題**:
```
ModuleNotFoundError: No module named 'strands'
```

エージェントコードを直接実行しようとした場合：
```bash
python agent/weather_time_agent.py --help  # これは動作しません
uv run python agent/weather_time_agent.py  # これも動作しません
```

**説明**:
`agent/weather_time_agent.py` ファイルは**ローカルで実行することを想定していません**。これはコンテナ化されて Amazon Bedrock AgentCore Runtime にデプロイされ、以下が適用されます：
- すべての依存関係（`strands-agents` を含む）が Docker イメージにプリインストール済み
- ランタイムによる自動 OpenTelemetry 計装が適用
- エージェントは完全な計装とツールアクセスで実行

**エージェントの正しい使用方法**:

**オプション 1: デプロイ済みエージェントをテスト**（推奨）
```bash
# 事前定義されたテストを実行
scripts/tests/test_agent.sh --test weather
scripts/tests/test_agent.sh --test calculator
scripts/tests/test_agent.sh --test combined

# カスタムプロンプトでテスト
scripts/tests/test_agent.sh --prompt "Calculate the factorial of -5"

# インタラクティブモード
scripts/tests/test_agent.sh --interactive
```

**オプション 2: オブザーバビリティデモを実行**
```bash
# すべてのオブザーバビリティシナリオを実行
python simple_observability.py --scenario all

# または特定のシナリオ
python simple_observability.py --scenario success
python simple_observability.py --scenario error
```

**動作の仕組み**:
1. `scripts/deploy_agent.sh` を使用してエージェントをデプロイ
2. テストスクリプトが AgentCore Runtime 上のデプロイ済みエージェントを呼び出し（API 経由）
3. ランタイムが自動的に OpenTelemetry で計装
4. 結果が CloudWatch および/または Braintrust で収集される

エージェントコードはローカルで実行されません - テストスクリプトとデプロイツールのみがラップトップで実行されます。

## エージェント呼び出しエラー

### エージェントが見つからないエラー

**エラーメッセージ**:
```
ClientError: An error occurred (ResourceNotFoundException) when calling the InvokeAgent operation:
Agent with ID 'abc123xyz' not found
```

**原因**:
1. エージェント ID が正しくない
2. エージェントが AgentCore Runtime にデプロイされていない
3. 指定した AWS リージョンが間違っている
4. エージェントが削除された

**解決策**:

```bash
# 1. リージョン内のすべてのエージェントを一覧表示
aws bedrock-agentcore list-agents --region us-east-1

# 2. エージェントの存在を確認
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 3. リージョンの一致を確認
echo $AWS_REGION  # エージェントのデプロイリージョンと一致する必要があります

# 4. 必要に応じてエージェントを再デプロイ
cd scripts
./deploy_agent.sh --region us-east-1
```

### アクセス拒否エラー

**エラーメッセージ**:
```
ClientError: An error occurred (AccessDeniedException) when calling the InvokeAgent operation:
User is not authorized to perform: bedrock-agentcore-runtime:InvokeAgent
```

**原因**:
1. IAM 権限が不足している
2. 間違った IAM ロールを使用している
3. AWS 認証情報が設定されていない

**解決策**:

```bash
# 1. AWS 認証情報を確認
aws sts get-caller-identity

# 2. IAM 権限を確認
aws iam get-user-policy \
  --user-name your-username \
  --policy-name your-policy

# 3. 必要な権限を追加
# 以下の権限を持つポリシーをアタッチ：
# - bedrock-agentcore-runtime:InvokeAgent
# - bedrock-agentcore:DescribeAgent
# - bedrock:InvokeModel

# 4. Bedrock へのアクセスを確認
aws bedrock list-foundation-models --region $AWS_REGION
```

### エージェントタイムアウトエラー

**エラーメッセージ**:
```
ClientError: An error occurred (TimeoutException) when calling the InvokeAgent operation:
Agent invocation timed out
```

**原因**:
1. エージェントの処理に時間がかかりすぎている
2. ツール実行のタイムアウト
3. ネットワーク遅延の問題
4. モデルのスロットリング

**解決策**:

```bash
# 1. クライアントコードでタイムアウトを増加
# simple_observability.py を編集：
client._client_config.read_timeout = 300  # 5 分

# 2. ログでツール実行時間を確認
aws logs tail /aws/agentcore/observability --follow

# 3. モデルのクォータを確認
aws bedrock get-model-invocation-metrics \
  --model-id us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --region $AWS_REGION

# 4. 必要に応じてクォータ増加をリクエスト
# Service Quotas コンソールに移動
```

## ツール実行の失敗

### ツールが利用できないエラー

**エラーメッセージ**:
```
ToolExecutionError: Tool 'get_weather' not found in gateway
```

**原因**:
1. エージェントに MCP ツールが設定されていない
2. ツールサーバーにアクセスできない
3. ツール名の不一致
4. ツール認証の失敗

**解決策**:

```bash
# 1. エージェント設定を確認
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 2. ツールの実装を確認
ls -la tools/*.py

# 3. 正しいツール設定でエージェントを再デプロイ
cd scripts
./deploy_agent.sh

# 4. ツール実行を直接テスト
python -c "from tools import get_weather; print(get_weather('Paris'))"
```

### ツールがエラーを返す

**エラーメッセージ**:
```
ToolExecutionError: Calculator tool failed: Cannot calculate factorial of negative number
```

**原因**:
1. 無効なツール入力
2. ツールのロジックエラー
3. ツールの依存関係の失敗

**期待される動作**:
- これはシナリオ 2（エラー処理デモ）では正常です
- エージェントはエラーを適切に処理する必要があります
- エラーは適切なステータスでトレースに表示されます

**解決策**:

```bash
# 1. これがシナリオ 2（期待されるエラー）であることを確認
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error

# 2. ツールの実装を確認
cat tools/calculator_tool.py

# 3. ログでエラーを表示
# CloudWatch Logs: エラーメッセージは runtime-logs に含まれます
# Braintrust: エラーアノテーションが表示されます

# 4. ツールを直接テスト
python -c "from tools import calculator; print(calculator('factorial', -5, None))"
```

## ログとメトリクスの問題

### CloudWatch にログが表示されない

**問題**: エージェント実行後も CloudWatch Logs にエントリが表示されない

**原因**:
1. エージェントがデプロイされていない
2. ロググループが存在しない
3. IAM 権限が不足している
4. エージェントの実行が失敗した

**解決策**:

```bash
# 1. エージェントが存在しデプロイされていることを確認
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 2. ロググループが存在することを確認
aws logs describe-log-groups --region $AWS_REGION | grep bedrock-agentcore

# 3. 最近のログストリームを表示
aws logs describe-log-streams \
  --log-group-name /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT \
  --region $AWS_REGION

# 4. リアルタイムでログを追跡
aws logs tail /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT --follow --region $AWS_REGION

# 5. テストを実行してログを生成
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

### オブザーバビリティ設定

**CloudWatch ログストリームの理解**:

Braintrust が**設定されていない**場合：
- CloudWatch は runtime-logs と構造化 OTEL データの両方を受信
- 完全な運用可視性がログで利用可能
- デバッグと開発に最適

Braintrust が**設定されている**場合（BRAINTRUST_API_KEY が設定済み）：
- CloudWatch はアプリケーションログ（runtime-logs ストリーム）を受信
- 詳細な OTEL データは代わりに Braintrust に送信
- CloudWatch Logs にはまだエージェントのアクティビティとステータスが表示
- これは重複したログストレージを避けるための期待される動作

**確認**:

```bash
# 1. CloudWatch Logs が書き込まれていることを確認
aws logs tail /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT --since 5m

# 期待される出力：
# [runtime-logs] Agent invoked with prompt: ...
# [runtime-logs] Agent initialized with tools: ...
# [runtime-logs] Agent invocation completed successfully

# 2. エージェント実行が完了したことを確認
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT \
  --filter-pattern "completed" \
  --region $AWS_REGION

# 3. Braintrust を使用している場合、Braintrust ダッシュボードでトレースを確認
# https://www.braintrust.dev/app に移動してプロジェクトを確認
# トレースはエージェント実行後 1〜2 分以内に表示されます
```

### Braintrust にトレースが表示されない

**問題**: Braintrust ダッシュボードにトレースがない

**原因**:
1. 無効な Braintrust API キー
2. BRAINTRUST_API_KEY 環境変数が設定されていない
3. ネットワーク接続の問題
4. プロジェクト名の不一致

**解決策**:

```bash
# 1. API キーが設定されていることを確認
echo "BRAINTRUST_API_KEY: $BRAINTRUST_API_KEY"

# 2. API キーが有効であることを確認
curl -H "Authorization: Bearer $BRAINTRUST_API_KEY" \
  https://api.braintrust.dev/v1/auth/verify

# 3. Braintrust OTEL エンドポイントへの接続をテスト
curl -I https://api.braintrust.dev/otel/v1/traces

# 4. プロジェクトの存在を確認
# https://www.braintrust.dev/app に移動
# プロジェクト agentcore-observability-demo が存在することを確認

# 5. エージェントログでテレメトリの初期化を確認
uv run python -m weather_time_agent 2>&1 | grep -i "telemetry\|braintrust\|initialized"

# 6. デプロイ済みエージェントの場合、BRAINTRUST_API_KEY が環境変数にあることを確認
aws bedrock-agentcore get-agent --agent-id $AGENT_ID --region $AWS_REGION | jq '.agent.envVars'
```

### 不完全なトレース

**問題**: トレースにスパンが欠けているか、部分的なデータが表示される

**原因**:
1. 実行中のエージェントタイムアウト
2. バッチプロセッサがスパンをフラッシュしていない
3. スパン属性のサイズ制限を超過
4. エクスポート中のネットワーク中断

**解決策**:

```bash
# 1. エージェント実行が完了したことを確認
aws logs filter-log-events \
  --log-group-name /aws/agentcore/observability \
  --filter-pattern '"COMPLETED"' \
  --region $AWS_REGION

# 2. ログを確認してスパンのフラッシュを強制
# エージェントは完了時に自動的にスパンをフラッシュします
# ログで "Strands telemetry initialized successfully" を確認

# 3. CloudWatch でドロップされたスパンを確認
aws logs filter-log-events \
  --log-group-name /aws/agentcore/observability \
  --filter-pattern '"dropped_spans"' \
  --region $AWS_REGION

# 4. スパン属性のサイズを削減
# 属性は 1000 文字未満にする必要があります
# logger ステートメントで大きな属性がないかエージェントコードを確認
# logging.basicConfig を使用してメッセージサイズを制限

# 5. スパンが早期終了により欠落している場合、エージェントタイムアウトを増加
# AgentCore コンソールでエージェント設定を更新
```

## パフォーマンスの問題

### 高レイテンシ

**問題**: エージェントの応答が予想より遅い

**原因**:
1. モデルの選択（大きなモデルは遅い）
2. 複雑なツール実行
3. ネットワーク遅延
4. コールドスタートの遅延

**解決策**:

```bash
# 1. ログを確認してボトルネックを特定
# CloudWatch Logs でタイミングメッセージを確認
# 最も時間がかかっている操作を探す

# 2. より高速なモデルを使用
# agent/weather_time_agent.py を編集：
# model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"  # 推奨

# 3. ツール実行を最適化
# tools/*.py で遅い操作を確認

# 4. キャッシュを有効化
# 繰り返しの呼び出しを減らすためにレスポンスキャッシュを追加

# 5. 経時的なレイテンシを監視
aws cloudwatch get-metric-statistics \
  --namespace AgentCore/Observability \
  --metric-name Latency \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,p99 \
  --region $AWS_REGION
```

### トークン使用量が多い

**問題**: トークン消費が予想より多い

**原因**:
1. 冗長なシステムプロンプト
2. 大きなツール説明
3. 長い会話履歴
4. 非効率なツール呼び出し

**解決策**:

```bash
# 1. Braintrust でトークン使用量を確認
# Dashboard > Traces > トレースを選択 > トークンの内訳を表示

# 2. システムプロンプトを最適化
# agent/weather_time_agent.py を編集：
# system_prompt を簡潔に保つ

# 3. ツールスキーマの冗長性を削減
# TOOL_SCHEMAS のツール説明を簡素化

# 4. トークンのトレンドを監視
# Braintrust Dashboard > Metrics > Token Usage Over Time

# 5. トークン制限を設定
# エージェント呼び出しを編集：
# inferenceConfig:
#   maxTokens: 1024  # 適切であれば 2048 から削減
```

### コストが高い

**問題**: AWS/LLM のコストが予想より高い

**原因**:
1. 高い呼び出し率
2. 高価なモデルを選択
3. 大きなトークン消費
4. 長い CloudWatch 保持期間

**解決策**:

```bash
# 1. Braintrust でコストの内訳を確認
# Dashboard > Costs > モデル/操作別に表示

# 2. より安価なモデルを使用
# Haiku は Sonnet の 10 分の 1 のコスト

# 3. CloudWatch の保持期間を短縮
aws logs put-retention-policy \
  --log-group-name /aws/agentcore/observability \
  --retention-in-days 1 \
  --region $AWS_REGION

# 4. CloudWatch ログの保持期間を調整
aws logs put-retention-policy \
  --log-group-name /aws/agentcore/observability \
  --retention-in-days 7 \
  --region $AWS_REGION

# 5. AWS Cost Explorer を有効化
# Bedrock と CloudWatch の日次支出を監視
```

## 環境の問題

### Python 依存関係

**問題**: インポートエラーまたはモジュールの欠落

**原因**:
1. 依存関係がインストールされていない
2. Python のバージョンが間違っている
3. 仮想環境がアクティブ化されていない

**解決策**:

```bash
# 1. Python のバージョンを確認
python --version  # 3.11 以上である必要があります

# 2. 仮想環境をアクティブ化
source .venv/bin/activate

# 3. 依存関係をインストール/再インストール
uv pip install boto3 botocore

# 4. インポートが機能することを確認
python -c "import boto3; print(boto3.__version__)"

# 5. 必要に応じてクリーンアップして再インストール
rm -rf .venv
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 環境変数が設定されていない

**問題**: 環境変数の欠落エラーでスクリプトが失敗する

**原因**:
1. .env ファイルが読み込まれていない
2. 変数がエクスポートされていない
3. 変数名が間違っている

**解決策**:

```bash
# 1. 変数が設定されているか確認
echo $AGENTCORE_AGENT_ID
echo $AWS_REGION
echo $BRAINTRUST_API_KEY

# 2. .env ファイルを読み込む
source .env  # または
source scripts/.env

# 3. 必要に応じて手動でエクスポート
export AGENTCORE_AGENT_ID=abc123xyz
export AWS_REGION=us-east-1
export BRAINTRUST_API_KEY=bt-xxxxx

# 4. 確認
env | grep AGENTCORE
```

### AWS リージョンの不一致

**問題**: 正しい ID にもかかわらずリソースが見つからない

**原因**:
1. エージェントが別のリージョンにデプロイされている
2. AWS_REGION が正しく設定されていない
3. 複数のリージョンが設定されている

**解決策**:

```bash
# 1. 現在のリージョンを確認
echo $AWS_REGION
aws configure get region

# 2. エージェントのリージョンを確認
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region us-east-1

# 3. 一貫性を確保
export AWS_REGION=us-east-1  # エージェントのデプロイリージョンと一致させる

# 4. すべてのスクリプトを同じリージョンを使用するように更新
```

## スクリプトの失敗

### セットアップスクリプトの失敗

**問題**: `./setup_all.sh` がエラーで終了する

**原因**:
1. 前提条件が不足している
2. 無効な AWS 認証情報
3. 権限が不十分
4. ネットワークの問題

**解決策**:

```bash
# 1. 前提条件チェックを実行
cd scripts
./check_prerequisites.sh

# 2. セットアップステップを個別に実行
./deploy_agent.sh
./setup_cloudwatch.sh
./setup_braintrust.sh

# 3. 特定のエラーのログを確認
# スクリプト出力でエラーメッセージを確認

# 4. デバッグモードを有効化
bash -x ./setup_all.sh
```

### デモスクリプトの失敗

**問題**: `simple_observability.py` がエラーで終了する

**原因**:
1. エージェント ID が設定されていない
2. エージェントがデプロイされていない
3. ネットワークの問題
4. 無効な引数

**解決策**:

```bash
# 1. デバッグログ付きで実行
python simple_observability.py \
  --agent-id $AGENTCORE_AGENT_ID \
  --scenario success \
  --debug

# 2. エージェント ID を確認
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 3. シンプルなクエリでテスト
python simple_observability.py \
  --agent-id $AGENTCORE_AGENT_ID \
  --scenario dashboard

# 4. Python パスを確認
which python
python --version
```

## データの問題

### ダッシュボードにメトリクスがない

**問題**: CloudWatch ダッシュボードにデータが表示されない

**原因**:
1. エージェント呼び出しがまだない
2. メトリクスフィルターが作成されていない
3. 間違った時間範囲が選択されている
4. ダッシュボードのリージョンが不一致

**解決策**:

```bash
# 1. デモを実行してデータを生成
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all

# 2. メトリクスの存在を確認
aws cloudwatch list-metrics \
  --namespace AgentCore/Observability \
  --region $AWS_REGION

# 3. メトリクスフィルターを確認
aws logs describe-metric-filters \
  --log-group-name /aws/agentcore/observability \
  --region $AWS_REGION

# 4. ダッシュボードを再作成
cd scripts
./setup_cloudwatch.sh --region $AWS_REGION

# 5. ダッシュボードの時間範囲を確認
# 「過去 5 分」または「過去 1 時間」に設定
```

### ログが空または欠落

**問題**: CloudWatch Logs にエントリが表示されない

**原因**:
1. エージェントが呼び出されていない
2. ロググループが存在しない
3. IAM 権限が不足している
4. ログが無効化されている

**解決策**:

```bash
# 1. ロググループの存在を確認
aws logs describe-log-groups \
  --log-group-name-prefix /aws/agentcore \
  --region $AWS_REGION

# 2. 最近のログストリームを確認
aws logs describe-log-streams \
  --log-group-name /aws/agentcore/observability \
  --order-by LastEventTime \
  --descending \
  --max-items 5 \
  --region $AWS_REGION

# 3. リアルタイムでログを追跡
aws logs tail /aws/agentcore/observability --follow --region $AWS_REGION

# 4. デモを実行してログを確認
# ターミナル 1:
aws logs tail /aws/agentcore/observability --follow --region $AWS_REGION

# ターミナル 2:
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

## ヘルプを求める

### 診断情報の収集

ヘルプをリクエストする際は、以下を提供してください：

```bash
# 1. エージェント情報
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION > agent-info.json

# 2. 最近のログ
aws logs filter-log-events \
  --log-group-name /aws/agentcore/observability \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --region $AWS_REGION > recent-logs.json

# 3. 環境情報
echo "Python: $(python --version)" > environment.txt
echo "AWS CLI: $(aws --version)" >> environment.txt
echo "Region: $AWS_REGION" >> environment.txt
echo "Agent ID: $AGENTCORE_AGENT_ID" >> environment.txt

# 4. エラーメッセージ
# ターミナルからの完全なエラー出力をコピー
```

### サポートチャネル

- **AWS サポート**: https://console.aws.amazon.com/support
- **AWS re:Post**: https://repost.aws/tags/TA4IvCeWI1TE-69RURudUzbw/amazon-bedrock
- **GitHub Issues**: https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues
- **Braintrust Discord**: https://discord.gg/braintrust（Braintrust 固有の問題）

## 一般的なエラーメッセージリファレンス

### エラー: "Rate limit exceeded"

**原因**: Bedrock への API 呼び出しが多すぎる
**解決策**: 1 分待って再試行するか、クォータ増加をリクエスト

### エラー: "Model not found"

**原因**: モデル ID が正しくないか、リージョンで利用できない
**解決策**: モデル ID とリージョンのサポートを確認

### エラー: "Validation error"

**原因**: API 呼び出しのパラメータが無効
**解決策**: パラメータ形式について API ドキュメントを確認

### エラー: "Connection timeout"

**原因**: ネットワーク接続の問題
**解決策**: インターネット接続と AWS サービスの健全性を確認

### エラー: "Access denied to S3"

**原因**: S3 権限が不足している（アーティファクトに S3 を使用している場合）
**解決策**: IAM ロールに S3 読み取り/書き込み権限を追加

## 予防措置

### チュートリアル実行前

1. すべての前提条件を確認
2. AWS サービス健全性ダッシュボードを確認
3. 十分な AWS クォータを確保
4. AWS 認証情報をテスト
5. IAM 権限を確認

### チュートリアル実行中

1. CloudWatch Logs をリアルタイムで監視
2. ダッシュボードにデータが表示されているか確認
3. 次に進む前に各ステップを確認
4. 後で参照するためにトレース ID を保存

### チュートリアル実行後

1. 両方のプラットフォームですべてのトレースを確認
2. エラーや警告がないか確認
3. クリーンアップが正常に完了したことを確認
4. 発生した問題を文書化

## Braintrust オブザーバビリティの問題

### OTEL トレースが Braintrust に表示されない

**ログのエラーメッセージ**:
```
ERROR,Failed to export metrics to api.braintrust.dev, error code: StatusCode.PERMISSION_DENIED
```

**注意**: このエラーメッセージには「metrics」と書かれていますが、実際には OTEL トレース/スパンのエクスポートに関するものです。

**原因**:
1. 無効または期限切れの Braintrust API キー
2. 間違った Braintrust プロジェクト ID
3. API キーとプロジェクト ID が同じ Braintrust アカウントに属していない
4. Braintrust API エンドポイントが変更されたか到達不能

**解決策**:

**ステップ 1: Braintrust 認証情報を確認**
```bash
# 1. Braintrust にログイン: https://www.braintrust.dev/app
# 2. Settings → API Keys に移動
# 3. アクティブな API キーをコピー（'sk-' で始まる）
# 4. プロジェクト URL からプロジェクト ID を取得:
#    https://www.braintrust.dev/app/ORG/p/PROJECT_ID

# 正しい認証情報で .env を更新
BRAINTRUST_API_KEY=sk-your-real-api-key
BRAINTRUST_PROJECT_ID=your-real-project-id
```

**ステップ 2: Braintrust 接続をテスト**
```bash
# curl を使用して直接 OTEL 接続をテスト
curl -X POST https://api.braintrust.dev/otel \
  -H "Authorization: Bearer sk-your-real-api-key" \
  -H "x-bt-parent: project_id:your-real-project-id" \
  -H "Content-Type: application/x-protobuf" \
  -d "" -v
```

**ステップ 3: 更新された認証情報でエージェントを再デプロイ**
```bash
# 正しい Braintrust 認証情報で .env を編集
# その後再デプロイ
./scripts/deploy_agent.sh

# テストを実行してオブザーバビリティデータを生成
./scripts/tests/test_agent.sh --test weather

# エクスポートエラーのログを確認
./scripts/check_logs.sh --time 5m | grep -i "export\|permission"
```

**ステップ 4: Braintrust で確認**
```bash
# 1. https://www.braintrust.dev/app に移動
# 2. プロジェクトを選択
# 3. 過去数分間のトレースを探す
# 4. トレースがまだ表示されない場合、認証情報が無効
```

**エラーが続く場合**:
- API キーが期限切れでないことを確認（必要に応じて Settings で再生成）
- プロジェクトがまだ存在することを確認（削除されている可能性）
- 新しい API キーとプロジェクトの作成を試す
- サービスの問題について Braintrust ステータスページを確認

### CloudWatch トレースは表示されるが Braintrust トレースは表示されない

**シナリオ**: CloudWatch ログは表示されるが Braintrust には何もない

**原因**: Braintrust 認証情報が無効またはエンドポイントに到達できない

**解決策**: 上記の「OTEL トレースが Braintrust に表示されない」セクションに従って、認証情報を確認およびテスト

**注意**: Braintrust が誤設定されている場合：
- CloudWatch ログは引き続き表示される（これは常に機能する）
- Braintrust はトレースを受信しない（認証情報/ネットワークの問題）
- エージェントは正常に機能し続ける

## 次のステップ

トラブルシューティング後も問題が続く場合：

1. アーキテクチャの理解のために [システム設計](design.md) を確認
2. プラットフォーム設定について [Braintrust セットアップ](braintrust-setup.md) を確認
3. コードのカスタマイズについて [開発ガイド](development.md) を確認
4. 代替アプローチについて [オブザーバビリティオプション](observability-options.md) を確認
5. 診断情報を添えて AWS サポートに連絡するか GitHub issue を作成
