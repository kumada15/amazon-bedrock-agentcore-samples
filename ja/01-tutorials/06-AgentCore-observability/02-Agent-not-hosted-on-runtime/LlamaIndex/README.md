# LlamaIndex Function Agent と AWS Bedrock および OpenTelemetry

このプロジェクトでは、AWS Bedrock でホストされ、AgentCore オブザーバビリティトレーシング用の OpenTelemetry インストルメンテーションを備えた LlamaIndex を使用してシンプルな算術エージェントを作成する方法を示します。

## プロジェクト概要

このプロジェクトは以下を実装しています：
- LlamaIndex.core の FunctionAgent を使用した Function エージェントパターン
- LLM バックエンド用の AWS Bedrock Claude モデルとの統合
- AWS CloudWatch によるオブザーバビリティのための OpenTelemetry インストルメンテーション
- シンプルな算術ツール（加算と乗算）
- 複数のエージェント実行間でトレースを相関させるためのセッショントラッキング機能

## アーキテクチャ図

以下の図は、AWS Bedrock と OpenTelemetry を使用したこの LlamaIndex エージェント実装のアーキテクチャを示しています：

![LlamaIndex AgentCore アーキテクチャ図](images/llamaindex_agentcore_arch_diagram.png)

## 前提条件

- Python 3.9 以上
- Bedrock サービス（特に Claude モデル）へのアクセスがある AWS アカウント
- ローカルで設定された AWS 認証情報
- AWS Bedrock と CloudWatch の適切な IAM 権限
- CloudWatch Transaction Search が有効化済み（トレース表示用）

## インストール

1. Amazon Bedrock AgentCore Samples リポジトリ全体をクローンした場合：
```bash
git clone https://github.com/aws-samples/amazon-bedrock-agentcore-samples.git
cd amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/02-Agent-not-hosted-on-runtime/LlamaIndex
```

2. 仮想環境を作成して有効化：
```bash
# 仮想環境を作成
python -m venv venv

# 仮想環境を有効化
# Windows の場合
venv\Scripts\activate
# macOS/Linux の場合
source venv/bin/activate
```

3. 依存関係をインストール：
```bash
pip install -r requirements.txt
```

4. Jupyter または VS Code でノートブックを開く場合：
   - カーネルセレクタから「venv」カーネルを選択
   - カーネルがリストに表示されない場合は、Jupyter または VS Code を再起動

## 設定

### AWS 認証情報

AWS Bedrock と CloudWatch へのアクセスで AWS 認証情報が適切に設定されていることを確認してください：

CLI で `aws configure` を実行して Amazon 認証情報を正しく設定してください。.env ファイルに保存する必要はありません。

### OpenTelemetry 設定

プロジェクトは以下の OpenTelemetry 環境変数を使用します。`.env` ファイルで設定してください（`.env.example` をテンプレートとして使用）：

```bash
# エージェント設定
AGENT_ID=llama-index-function-agent
SERVICE_NAME=llama-index-bedrock-agent
BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0

# OpenTelemetry 設定
AGENT_OBSERVABILITY_ENABLED=true
OTEL_PYTHON_DISTRO=aws_distro
OTEL_PYTHON_CONFIGURATOR=aws_configurator
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_EXPORTER=otlp
```

### CloudWatch ロググループのセットアップ

エージェントを実行する前に、CloudWatch でロググループとログストリームを作成する必要があります：

```python
import boto3

cloudwatch_client = boto3.client("logs")
cloudwatch_client.create_log_group(logGroupName='agents/llama-index-agent-logs')
cloudwatch_client.create_log_stream(logGroupName='agents/llama-index-agent-logs', logStreamName='default')
```

次に `.env` ファイルを更新して以下を含めます：

```bash
OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=agents/llama-index-agent-logs,x-aws-log-stream=default,x-aws-metric-namespace=bedrock-agentcore
OTEL_RESOURCE_ATTRIBUTES=service.name=agentic-llamaindex-agentcore
```

## 使用方法

### 基本エージェント

OpenTelemetry インストルメンテーションを備えた基本算術エージェントを実行するには：

```bash
opentelemetry-instrument python llama_index_agent.py
```

これにより、シンプルな算術タスクが実行されます：`What is (121 + 2) * 5?`

### セッショントラッキング付きエージェント

トレース相関のためのセッショントラッキングを備えたエージェントを実行するには：

```bash
opentelemetry-instrument python llama_index_agent_with_session.py --session-id "your-session-id"
```

このバージョンでは、一貫したセッション ID を使用して複数のエージェント実行間でトレースを相関させることができます。

## Jupyter ノートブックチュートリアル

リポジトリには、以下を示す Jupyter ノートブック（`LlamaIndex_Observability.ipynb`）が含まれています：

1. 環境と前提条件のセットアップ
2. 必要な CloudWatch ロググループの作成
3. 環境変数の設定
4. セッショントラッキングありなしでのエージェント実行
5. AWS CloudWatch ダッシュボードでのトレースの理解

ノートブックは、適切なオブザーバビリティでエージェントをセットアップして実行するためのインタラクティブなチュートリアルとして機能します。

## OpenTelemetry インストルメンテーションの詳細

このプロジェクトは、AWS Distro for OpenTelemetry (ADOT) を使用してテレメトリデータを AWS CloudWatch に送信します。インストルメンテーションは `llama_index.observability.otel` の `LlamaIndexOpenTelemetry` クラスを使用してセットアップされます。

主なインストルメンテーションポイント：
- エージェントの初期化
- AWS Bedrock への LLM 呼び出し
- ツール実行（各ツールには独自のスパンがあります）
- エージェントクエリ処理

### トレースの表示

トレースを表示するには：
1. CloudWatch Transaction Search が有効になっていることを確認
2. CloudWatch コンソールに移動
3. GenAI Observability に移動
4. エージェントのサービス名（デフォルト：`agentic-llamaindex-agentcore`）でトレースを探す

## トラブルシューティング

### よくある問題

1. **AWS 認証情報が見つからない**
   - AWS 認証情報が環境で正しく設定されていることを確認
   - IAM ユーザーが Bedrock と CloudWatch の適切な権限を持っていることを確認

2. **OpenTelemetry トレースが表示されない**
   - CloudWatch Transaction Search が有効になっていることを確認
   - `OTEL_EXPORTER_OTLP_LOGS_HEADERS` で指定されたロググループが存在することを確認
   - AWS リージョンが正しく設定されていることを確認

3. **Bedrock モデルアクセス**
   - `BEDROCK_MODEL_ID` で指定された Bedrock モデルへのアクセスがあることを確認
   - アカウントの Bedrock モデルスループットクォータを確認

4. **Jupyter ノートブックでの OpenTelemetry 警告**
   - Jupyter ノートブックセルで `opentelemetry-instrument` を実行すると、以下のような警告が表示される場合があります：
     ```
     WARNING:opentelemetry.trace:Overriding of current TracerProvider is not allowed
     ```
     または `SpanDropEvent` やスパンがエラーで終了したメッセージ。
   - これらの警告はノートブック環境では予期されるものであり、エージェントの機能やオブザーバビリティデータ収集には影響しません
   - Jupyter には独自のインストルメンテーションコンテキストがあり、セルを複数回実行すると OpenTelemetry が再登録を試みるために発生します
   - エージェントが正しく実行され、トレースが CloudWatch に表示される限り、これらの警告は無視しても安全です

### CloudWatch ロググループ

OpenTelemetry トレースは、環境変数で指定された CloudWatch ロググループに送信されます：
```
agents/llama-index-agent-logs
```

トレースが表示されない場合は、このロググループが存在し、`.env` ファイルで適切に設定されていることを確認してください。


## 追加リソース

- [LlamaIndex ドキュメント](https://docs.llamaindex.ai/)
- [AWS Bedrock ドキュメント](https://docs.aws.amazon.com/bedrock)
- [OpenTelemetry ドキュメント](https://opentelemetry.io/docs/)
- [AWS Distro for OpenTelemetry (ADOT)](https://aws.amazon.com/otel/)
- [CloudWatch Transaction Search ドキュメント](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Enable-TransactionSearch.html)
