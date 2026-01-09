# 開発ガイド

## 概要

このガイドでは、Simple Dual Observability チュートリアルのコードをカスタマイズ、拡張、または学習したい開発者向けの詳細情報を提供します。

## コード構造

### プロジェクト構成

```
simple-dual-observability/
│
├── agent/
│   ├── weather_time_agent.py          # コアエージェント実装
│   ├── strands_agent_config.json      # エージェントデプロイ設定
│   └── __init__.py
│
├── tools/
│   ├── weather_tool.py                # Weather ツール実装
│   ├── time_tool.py                   # Time ツール実装
│   ├── calculator_tool.py             # Calculator ツール実装
│   └── __init__.py
│
├── simple_observability.py            # メインデモスクリプト
│
├── scripts/
│   ├── deploy_agent.sh                # Runtime にエージェントをデプロイ
│   ├── setup_cloudwatch.sh            # CloudWatch を設定
│   ├── setup_braintrust.sh            # Braintrust を設定
│   ├── setup_all.sh                   # 完全セットアップ
│   └── cleanup.sh                     # リソースクリーンアップ
│
├── dashboards/
│   ├── cloudwatch-dashboard.json      # CloudWatch ダッシュボード設定
│   └── braintrust-dashboard-export.json
│
└── docs/
    ├── design.md                      # アーキテクチャドキュメント
    ├── braintrust-setup.md            # Braintrust ガイド
    ├── development.md                 # このファイル
    ├── troubleshooting.md             # トラブルシューティングガイド
    ├── observability-options.md       # オブザーバビリティアプローチと CloudWatch ログ
    └── generated-files.md             # 生成ファイルガイド
```

## ローカルテスト

### エージェントをローカルでテスト

AgentCore Runtime にデプロイする前に、エージェントをローカルでテスト：

```bash
# 仮想環境をアクティブ化
source .venv/bin/activate

# 単一のクエリでテスト
python -m agent.weather_time_agent "What's the weather in Seattle?"

# 異なるシナリオをテスト
python -m agent.weather_time_agent "What time is it in Tokyo?"
python -m agent.weather_time_agent "Calculate 25 + 17"
python -m agent.weather_time_agent "Calculate factorial of 5"
```

**注意**: ローカルテストでは OTEL トレースは生成されません。トレースは AgentCore Runtime で実行した場合のみ生成されます。

### 個別のツールをテスト

ツールを分離してテスト：

```python
# Python REPL またはスクリプト内で
from tools import get_weather, get_time, calculator

# Weather ツールをテスト
result = get_weather(city="Seattle")
print(result)

# Time ツールをテスト
result = get_time(timezone="America/Los_Angeles")
print(result)

# Calculator をテスト
result = calculator(operation="add", a=10, b=5)
print(result)

# エラー処理をテスト
result = calculator(operation="factorial", a=-5)
print(result)  # エラーを返すはず
```

### モック Bedrock でテスト

Bedrock API 呼び出しなしでテストする場合：

```python
from unittest.mock import Mock, patch
from agent.weather_time_agent import WeatherTimeAgent

# Bedrock クライアントをモック
with patch('boto3.client') as mock_client:
    mock_bedrock = Mock()
    mock_client.return_value = mock_bedrock

    # モックレスポンスを設定
    mock_bedrock.converse.return_value = {
        'output': {
            'message': {
                'content': [{'text': 'The weather in Seattle is sunny.'}]
            }
        },
        'stopReason': 'end_turn'
    }

    # エージェントをテスト
    agent = WeatherTimeAgent()
    response = agent.run("What's the weather in Seattle?")
    print(response)
```

## 新しいツールの追加

### ステップ 1: ツール実装を作成

`tools/` ディレクトリに新しいファイルを作成：

```python
# tools/stock_price_tool.py

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    指定されたシンボルの現在の株価を取得します。

    Args:
        symbol: 株式ティッカーシンボル（例: 'AAPL'、'GOOGL'）

    Returns:
        株価データを含む辞書

    Example:
        >>> result = get_stock_price('AAPL')
        >>> print(result['price'])
        150.25
    """
    logger.info(f"Getting stock price for: {symbol}")

    # デモ用: シミュレートデータを返す
    # 本番環境: 実際の株価 API を呼び出し
    result = {
        "symbol": symbol.upper(),
        "price": 150.25,
        "currency": "USD",
        "timestamp": "2024-01-15T10:30:00Z",
        "change_percent": "+2.5%"
    }

    logger.info(f"Stock price result: {result}")
    return result
```

### ステップ 2: エージェントにツールを登録

`agent/weather_time_agent.py` を更新：

```python
# TOOL_SCHEMAS に追加
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    # ... 既存のツール ...
    {
        "name": "get_stock_price",
        "description": "Get current stock price for a given ticker symbol",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AAPL', 'GOOGL')"
                }
            },
            "required": ["symbol"]
        }
    }
]

# _execute_tool メソッドに追加
def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    # 新しいツールをインポート
    from tools import get_weather, get_time, calculator, get_stock_price

    # ... 既存のツール処理 ...

    elif tool_name == "get_stock_price":
        result = get_stock_price(symbol=tool_input["symbol"])

    else:
        raise ValueError(f"Unknown tool: {tool_name}")

    return result
```

### ステップ 3: 新しいツールをテスト

```bash
# ローカルでテスト
python -m agent.weather_time_agent "What's the stock price of AAPL?"

# デプロイ後にテスト
python simple_observability.py \
  --agent-id $AGENTCORE_AGENT_ID \
  --scenario success
```

### ステップ 4: ツールエクスポートを更新

`tools/__init__.py` を更新：

```python
from .weather_tool import get_weather
from .time_tool import get_time
from .calculator_tool import calculator
from .stock_price_tool import get_stock_price

__all__ = [
    'get_weather',
    'get_time',
    'calculator',
    'get_stock_price'
]
```

## デモスクリプトのカスタマイズ

### カスタムシナリオの追加

`simple_observability.py` に新しいシナリオを追加：

```python
def scenario_parallel_tools(
    client: boto3.client,
    agent_id: str,
    region: str
) -> None:
    """
    シナリオ 4: 並列ツール実行。

    エージェントが複数のツールを同時に使用することを示します。
    トレースに並列スパンが表示されることが期待されます。
    """
    logger.info("Starting Scenario 4: Parallel Tool Execution")

    session_id = _generate_session_id()
    query = "Get the weather and time for New York, London, and Tokyo"

    result = _invoke_agent(
        client=client,
        agent_id=agent_id,
        query=query,
        session_id=session_id
    )

    _print_result(result, "Scenario 4: Parallel Tool Execution")
    _print_observability_links(region, result["trace_id"])

    print("✓ Expected in traces:")
    print("   - Multiple tool executions")
    print("   - Some tools may execute in parallel")
    print("   - Trace shows concurrent spans")

# main() 関数に追加
if args.scenario in ["parallel", "all"]:
    scenario_parallel_tools(client, args.agent_id, args.region)
```

### 出力フォーマットのカスタマイズ

異なる出力用に `_print_result()` を変更：

```python
def _print_result_json(
    result: Dict[str, Any],
    scenario_name: str
) -> None:
    """プログラム的使用のために結果を JSON として出力します。"""
    import json

    output = {
        "scenario": scenario_name,
        "output": result["output"],
        "trace_id": result["trace_id"],
        "session_id": result["session_id"],
        "elapsed_time": result["elapsed_time"]
    }

    print(json.dumps(output, indent=2))
```

### メトリクス収集の追加

実行中にカスタムメトリクスを追跡：

```python
import time
from collections import defaultdict

class MetricsCollector:
    """デモ実行メトリクスを収集します。"""

    def __init__(self):
        self.metrics = defaultdict(list)

    def record_latency(self, scenario: str, latency: float):
        self.metrics[f"{scenario}_latency"].append(latency)

    def record_tokens(self, scenario: str, tokens: int):
        self.metrics[f"{scenario}_tokens"].append(tokens)

    def print_summary(self):
        print("\n" + "=" * 80)
        print("METRICS SUMMARY")
        print("=" * 80)

        for metric_name, values in self.metrics.items():
            avg = sum(values) / len(values)
            print(f"{metric_name}: avg={avg:.2f}, count={len(values)}")

        print("=" * 80)

# main() で使用
metrics = MetricsCollector()

for scenario in scenarios:
    start = time.time()
    run_scenario(scenario)
    latency = time.time() - start
    metrics.record_latency(scenario, latency)

metrics.print_summary()
```

## エージェント動作の変更

### モデルパラメータの調整

`agent/weather_time_agent.py` でモデル動作を変更：

```python
# run() メソッドで inferenceConfig を変更：
response = self.bedrock.converse(
    modelId=self.model_id,
    messages=messages,
    system=self.system_prompt,
    toolConfig={"tools": [{"toolSpec": tool_spec} for tool_spec in TOOL_SCHEMAS]},
    inferenceConfig={
        "maxTokens": 1024,        # 短いレスポンス用に削減
        "temperature": 0.5,        # より決定論的に低く
        "topP": 0.9,              # Nucleus サンプリング
        "stopSequences": ["\n\n"]  # カスタム停止シーケンス
    }
)
```

### システムプロンプトのカスタマイズ

エージェントのパーソナリティと動作を変更：

```python
# __init__ メソッド内：
self.system_prompt = [
    {
        "text": (
            "You are an expert assistant specializing in real-time data. "
            "Use available tools to provide accurate, up-to-date information. "
            "Always cite which tool you used for each piece of information. "
            "Be concise but thorough. "
            "If a tool returns an error, explain it clearly to the user."
        )
    }
]
```

### 会話メモリの追加

メモリ付きのマルチターン会話を実装：

```python
class WeatherTimeAgent:
    def __init__(self, ...):
        self.conversation_history = []  # 会話履歴を追加

    def run(self, query: str, session_id: Optional[str] = None):
        # 履歴からメッセージを初期化
        messages = self.conversation_history.copy()

        # 新しいユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": [{"text": query}]
        })

        # ... エージェンティックループを実行 ...

        # 履歴に保存
        self.conversation_history = messages

        return final_text

    def clear_history(self):
        """会話履歴をクリアします。"""
        self.conversation_history = []
```

## OTEL 設定の拡張

### カスタムスパンの追加

特定の操作にカスタム計装を追加：

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]):
    # カスタムスパンを作成
    with tracer.start_as_current_span(
        f"custom.tool.{tool_name}",
        attributes={
            "tool.name": tool_name,
            "tool.input": str(tool_input),
            "custom.attribute": "value"
        }
    ) as span:
        # ツールを実行
        result = self._execute_tool_impl(tool_name, tool_input)

        # 結果をスパンに追加
        span.set_attribute("tool.result_size", len(str(result)))

        return result
```

### カスタムメトリクスの追加

OTEL 経由でカスタムメトリクスをエクスポート：

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)

# カウンターを作成
tool_calls_counter = meter.create_counter(
    "agent.tool_calls",
    description="Number of tool calls",
    unit="1"
)

# コード内でインクリメント
def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]):
    tool_calls_counter.add(1, {"tool.name": tool_name})
    # ... ツールを実行 ...
```

### 追加エクスポーターの設定

Strands テレメトリライブラリは環境変数経由で追加エクスポーターの設定をサポートします。エクスポート先を追加するには、適切な OTEL 環境変数を設定します：

```bash
# 複数の OTLP エクスポーターを使用するように OTEL を設定
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Braintrust（BRAINTRUST_API_KEY が設定されている場合、デフォルトで設定済み）
export BRAINTRUST_API_KEY=sk-xxxxx

# Datadog エクスポーターを追加
export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.datadoghq.com/v1/traces
export DD_API_KEY=${DATADOG_API_KEY}

# Honeycomb エクスポーターを追加
export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
export HONEYCOMB_API_KEY=${HONEYCOMB_API_KEY}
```

高度な設定については、[OpenTelemetry 環境変数仕様](https://opentelemetry.io/docs/specs/otel/protocol/exporter/) を参照してください。

## テスト戦略

### ユニットテスト

ツール用のユニットテストを作成：

```python
# tests/test_tools.py

import pytest
from tools import get_weather, get_time, calculator


class TestWeatherTool:
    def test_get_weather_returns_data(self):
        result = get_weather("Seattle")
        assert "city" in result
        assert result["city"] == "Seattle"
        assert "temperature" in result

    def test_get_weather_handles_empty_city(self):
        result = get_weather("")
        assert "error" in result


class TestCalculatorTool:
    def test_add_operation(self):
        result = calculator("add", 10, 5)
        assert result["result"] == 15

    def test_factorial_negative_number(self):
        result = calculator("factorial", -5)
        assert "error" in result

    @pytest.mark.parametrize("a,b,expected", [
        (10, 5, 15),
        (0, 0, 0),
        (-5, 5, 0),
    ])
    def test_add_various_inputs(self, a, b, expected):
        result = calculator("add", a, b)
        assert result["result"] == expected
```

### 統合テスト

エージェントをエンドツーエンドでテスト：

```python
# tests/test_agent.py

import pytest
from unittest.mock import Mock, patch
from agent.weather_time_agent import WeatherTimeAgent


class TestWeatherTimeAgent:
    @patch('boto3.client')
    def test_agent_handles_weather_query(self, mock_client):
        # モックをセットアップ
        mock_bedrock = Mock()
        mock_client.return_value = mock_bedrock

        mock_bedrock.converse.return_value = {
            'output': {'message': {'content': [{'text': 'Sunny, 72F'}]}},
            'stopReason': 'end_turn'
        }

        # テスト
        agent = WeatherTimeAgent()
        response = agent.run("What's the weather?")

        # 検証
        assert "Sunny" in response
        mock_bedrock.converse.assert_called_once()

    @patch('boto3.client')
    def test_agent_handles_tool_calling(self, mock_client):
        # ツール呼び出しでモックをセットアップ
        mock_bedrock = Mock()
        mock_client.return_value = mock_bedrock

        # 最初のレスポンス: ツール使用
        # 2 番目のレスポンス: 最終回答
        mock_bedrock.converse.side_effect = [
            {
                'output': {
                    'message': {
                        'content': [{
                            'toolUse': {
                                'toolUseId': 'tool-1',
                                'name': 'get_weather',
                                'input': {'city': 'Seattle'}
                            }
                        }]
                    }
                },
                'stopReason': 'tool_use'
            },
            {
                'output': {'message': {'content': [{'text': 'Weather is sunny'}]}},
                'stopReason': 'end_turn'
            }
        ]

        # テスト
        agent = WeatherTimeAgent()
        response = agent.run("What's the weather in Seattle?")

        # 検証
        assert response is not None
        assert mock_bedrock.converse.call_count == 2
```

### 負荷テスト

負荷下でのパフォーマンスをテスト：

```python
# tests/load_test.py

import time
import concurrent.futures
from simple_observability import _invoke_agent, _create_bedrock_client


def invoke_agent_once(agent_id, region, query_num):
    """単一のエージェント呼び出し。"""
    client = _create_bedrock_client(region)
    session_id = f"load_test_{query_num}"

    start = time.time()
    result = _invoke_agent(
        client=client,
        agent_id=agent_id,
        query="What's the weather in Seattle?",
        session_id=session_id
    )
    latency = time.time() - start

    return {
        "query_num": query_num,
        "latency": latency,
        "trace_id": result["trace_id"]
    }


def run_load_test(agent_id, region, num_requests=10, concurrency=3):
    """同時リクエストで負荷テストを実行。"""
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(invoke_agent_once, agent_id, region, i)
            for i in range(num_requests)
        ]

        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # 統計を計算
    latencies = [r["latency"] for r in results]
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    print(f"Load Test Results:")
    print(f"  Total requests: {num_requests}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Average latency: {avg_latency:.2f}s")
    print(f"  P95 latency: {p95_latency:.2f}s")

    return results


if __name__ == "__main__":
    import sys
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "abc123"
    run_load_test(agent_id, "us-east-1", num_requests=20, concurrency=5)
```

## コード品質

### リンティングとフォーマット

ruff を使用したリンティングとフォーマット：

```bash
# ruff をインストール
uv add --dev ruff

# リンティングを実行
uv run ruff check .

# 問題を自動修正
uv run ruff check --fix .

# コードをフォーマット
uv run ruff format .
```

### 型チェック

mypy を使用した型チェック：

```bash
# mypy をインストール
uv add --dev mypy

# 型チェックを実行
uv run mypy agent/ tools/ simple_observability.py
```

### セキュリティスキャン

bandit を使用したセキュリティチェック：

```bash
# bandit をインストール
uv add --dev bandit

# セキュリティスキャンを実行
uv run bandit -r agent/ tools/ simple_observability.py
```

## デバッグ

### デバッグログを有効化

```bash
# simple_observability.py 内
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all --debug

# または環境変数を設定
export LOGLEVEL=DEBUG
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all
```

### Python デバッガーを使用

```python
# コード内にブレークポイントを追加
import pdb; pdb.set_trace()

# またはリモートデバッグ用に debugpy を使用
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

### OTEL データの検査

```bash
# OTEL Collector のデバッグ出力を表示
docker logs otel-collector --follow

# OTEL Collector メトリクスを確認
curl http://localhost:8888/metrics

# トレース詳細を表示
curl http://localhost:55679/debug/tracez
```

## コントリビューション

改善をコントリビュートする際は：

1. 既存のコード構造と命名規則に従う
2. 新機能にテストを追加
3. ドキュメントを更新
4. リンティングと型チェックを実行
5. 提出前にローカルでテスト
6. CLAUDE.md のコーディング標準に従う

## 次のステップ

開発を理解した後：

1. アーキテクチャについて [システム設計](design.md) を確認
2. デバッグについて [トラブルシューティング](troubleshooting.md) を確認
3. カスタムツールとシナリオを実験
4. 改善をリポジトリにコントリビュート
