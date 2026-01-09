# AgentCore 評価ユーティリティ

CloudWatch トレースデータを抽出し、AgentCore Evaluation DataPlane API を使用してエージェントセッションを評価する Python ユーティリティです。

## インストール

```bash
pip install -r requirements.txt
```

## 設定

CloudWatch Logs と AgentCore Evaluation API へのアクセス権を持つ AWS 認証情報を設定：

```bash
aws configure
```

または環境変数を設定：

```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

## 使用方法

```python
from utils import EvaluationClient

# クライアントを初期化
client = EvaluationClient(region="us-east-1")

# セッションを評価
results = client.evaluate_session(
    session_id="your-session-id",
    evaluator_ids=["Builtin.Helpfulness"],
    agent_id="your-agent-id",
    region="us-east-1"
)

# 結果を出力
for result in results.results:
    print(f"{result.evaluator_name}: {result.value} - {result.label}")
    print(f"説明: {result.explanation}")
```

## マルチ評価者サポート

1回の呼び出しで複数の評価者を使用して評価：

```python
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=["Builtin.Helpfulness", "Builtin.Accuracy", "Builtin.Harmfulness"],
    agent_id="agent-id",
    region="us-east-1"
)
```

## 自動保存とメタデータ

入力/出力ファイルを保存し、実験を追跡：

```python
results = client.evaluate_session(
    session_id="session-id",
    evaluator_ids=["Builtin.Helpfulness"],
    agent_id="agent-id",
    region="us-east-1",
    auto_save_input=True,   # evaluation_input/ に保存
    auto_save_output=True,  # evaluation_output/ に保存
    auto_create_dashboard=True,  # ローカルで利用可能な HTML ダッシュボード用データを生成
    metadata={  # 任意のデータを渡す
        "experiment": "baseline",
        "description": "初回評価実行"
    }
)
```

入力ファイルには、正確な再生のために API に送信されたスパンのみが含まれます。出力ファイルには、メタデータを含む完全な結果が含まれます。

## 実装詳細

このユーティリティは OpenTelemetry スパンとランタイムログのために CloudWatch Logs をクエリし、関連データ（gen_ai 属性と会話ログ）をフィルタリングし、評価 API に送信します。デフォルトのルックバックウィンドウは7日間で、評価ごとに最大1000アイテムです。
