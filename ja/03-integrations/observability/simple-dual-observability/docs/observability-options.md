# オブザーバビリティオプションガイド

このガイドでは、AgentCore エージェントをデプロイする際に使用できる 3 つのオブザーバビリティアプローチを比較します：

1. **CloudWatch のみ** - エージェント内部への完全な可視性、外部依存関係なし
2. **Braintrust + CloudWatch** - LLM 固有の洞察とコスト追跡を備えた外部オブザーバビリティプラットフォーム
3. **CloudWatch APM** - 組み込みのエージェントダッシュボードとパフォーマンス監視

各オプションは異なる機能を提供します。このガイドでは、ニーズに合った適切なオプションを選択するために、各アプローチで何が表示でき、何ができるかを説明します。

## オプション 1: CloudWatch のみ（Braintrust なし）

Braintrust 認証情報**なしで**エージェントをデプロイすると、CloudWatch で完全なオブザーバビリティが得られます。

### デプロイ方法

```bash
# Braintrust 認証情報が .env でコメントアウトまたは空であることを確認
# (.env.example の 13-14 行目)
# BRAINTRUST_API_KEY=your-api-key-here
# BRAINTRUST_PROJECT_ID=your-project-id-here

# CloudWatch オブザーバビリティでデプロイ
./scripts/deploy_agent.sh
```

### 表示される内容

#### エージェントレベルのメトリクス

CloudWatch はエージェント呼び出しメトリクスを表示します：

- **呼び出し回数**: エージェントが呼び出された総回数
- **成功率**: 成功した呼び出しの割合
- **平均時間**: 各呼び出しにかかった時間
- **エラー率**: 失敗した呼び出しの割合

![CloudWatch エージェントメトリクス](./img/demo1-cw-1.gif)

#### エージェントセッション

会話履歴とセッションコンテキストを表示：

- **セッション ID**: 各会話の一意の識別子
- **メッセージ**: 完全な会話履歴
- **メモリ**: エージェントの短期記憶の状態
- **コンテキスト**: エージェントがアクセスできる情報



#### すべての詳細を含む完全なトレース

呼び出し内で発生するすべての完全なトレースを確認：

- **LLM 呼び出し**: 言語モデルへの各呼び出し
  - 送信されたプロンプト
  - 受信したレスポンス
  - トークン数
  - レイテンシ

- **ツール呼び出し**: エージェントが呼び出す各ツール
  - ツール名とパラメータ
  - ツール出力
  - 実行時間

- **エージェント決定ポイント**: エージェントが次に何をするか決定する場所
  - 推論
  - 選択された次のアクション

- **スパンタイミング**: 各操作の正確なタイミング



#### 詳細なトラジェクトリビュー

エージェントの思考過程をステップバイステップで確認：

- ステップ 1: エージェントがクエリを受信
- ステップ 2: エージェントがアクションを決定するために LLM を呼び出し
- ステップ 3: エージェントがツールを呼び出し
- ステップ 4: エージェントがツール結果を処理
- ステップ 5: エージェントが再度 LLM を呼び出し
- ステップ 6: エージェントが最終レスポンスを提供

各ステップには以下が表示されます：
- 操作タイプ（LLM 呼び出し、ツール呼び出しなど）
- 入力と出力
- タイミング情報
- エラー詳細（ある場合）

![CloudWatch セッション](./img/demo1-cw-2.gif)

#### ライブログの例

CloudWatch のみのデプロイで CloudWatch ログを表示すると、ランタイムと OTEL の両方のログが表示されます：

**ランタイムログ**（人間が読みやすい形式）：
```
2025-11-02T20:02:42.861000+00:00 2025/11/02/[runtime-logs]3f6d959d-9b0a-4f1b-8894-ad142233fc6e 2025-11-02 20:02:42,861,p1,{weather_time_agent.py:105},INFO,Initializing Strands agent with model: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

**OTEL ログ**（構造化 JSON）：
```json
{
  "resource": {
    "attributes": {
      "service.name": "weather_time_observability_agent.DEFAULT",
      "cloud.region": "us-east-1",
      "cloud.platform": "aws_bedrock_agentcore",
      "cloud.resource_id": "arn:aws:bedrock-agentcore:us-east-1:015469603702:runtime/weather_time_observability_agent-dWTPGP46D4/..."
    }
  },
  "scope": {"name": "__main__"},
  "timeUnixNano": 1762113762861725952,
  "severityText": "INFO",
  "body": "Initializing Strands agent with model: us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "attributes": {
    "code.file.path": "/app/agent/weather_time_agent.py",
    "code.function.name": "<module>",
    "code.line.number": 105,
    "otelTraceID": "68fe3f82667cdc015abcd1d779d96d56",
    "otelSpanID": "49dbfa0650a0f03d"
  }
}
```

**同じログメッセージが両方の形式で表示されます**：
- ランタイムログは読みやすい
- OTEL ログは相関と自動分析のための構造化メタデータを持つ
- 両方ともログとトレースを関連付けるためのトレース ID を含む

### 利点

✅ エージェント内部で発生するすべてを確認
✅ 外部依存関係や API キーが不要
✅ 無料（CloudWatch のコストは最小限）
✅ AWS ネイティブ統合
✅ エージェント内部の簡単なデバッグ

### 最適な用途

- 開発とデバッグ
- エージェントの動作の理解
- エージェントの問題のトラブルシューティング
- エージェントの動作方法の学習

---

## オプション 2: Braintrust + CloudWatch（デュアルオブザーバビリティ）

Braintrust 認証情報**付きで**エージェントをデプロイすると、外部オブザーバビリティプラットフォームの洞察が得られます。

### デプロイ方法

```bash
# Braintrust 認証情報を .env に追加（13-14 行目）
BRAINTRUST_API_KEY=sk-your-actual-api-key
BRAINTRUST_PROJECT_ID=your-actual-project-id

# デュアルオブザーバビリティでデプロイ
./scripts/deploy_agent.sh
```

### 表示される内容

#### CloudWatch エージェントレベルメトリクス（引き続き利用可能）

CloudWatch のみと同じ：

- **呼び出し回数**: 総呼び出し数
- **成功率**: 成功率
- **平均時間**: 呼び出しタイミング
- **エラー率**: 失敗率

*注意: Braintrust が有効な場合、CloudWatch では詳細なトレースは利用できません。*

#### CloudWatch セッション情報（引き続き利用可能）

- セッション ID と会話履歴
- エージェントメモリの状態
- エージェントが利用可能なコンテキスト

#### Braintrust: 低レベルの運用詳細

Braintrust は、CloudWatch に表示されない詳細な OTEL スパンとトレースをすべて受信します：

- **LLM 呼び出し**: 言語モデルへのすべての呼び出し
  - 正確なプロンプトと完了
  - トークン使用量とコスト
  - 各呼び出しのレイテンシ
  - モデル選択とパラメータ

- **ツール呼び出し**: エージェントが呼び出すすべてのツール
  - ツール実行タイミング
  - 入力パラメータ
  - 出力結果
  - 実行中のエラー



- **完全なリクエストトレース**: 呼び出しの完全なトレース
  - 開始から終了までのスパンツリー
  - すべてのネストされた操作
  - 各スパンのタイミング
  - ログとの相関

![Braintrust 完全トレース](./img/demo1-bt-1.gif)

#### Braintrust ログエントリの例

エージェント呼び出しの実際の Braintrust ログエントリはこのようになります：

```json
{
  "__bt_assignments": null,
  "created": "2025-11-14T21:29:10.633Z",
  "expected": null,
  "input": [
    {
      "content": "What's the weather in Paris and what time is it there?",
      "role": "user"
    }
  ],
  "metadata": {
    "gen_ai.agent.name": "Strands Agents",
    "gen_ai.agent.tools": "[\"get_weather\", \"get_time\", \"calculator\"]",
    "gen_ai.event.end_time": "2025-11-14T21:29:14.299184Z",
    "gen_ai.event.start_time": "2025-11-14T21:29:10.633887Z",
    "gen_ai.operation.name": "invoke_agent",
    "gen_ai.request.model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "gen_ai.system": "strands-agents",
    "gen_ai.usage.completion_tokens": 187,
    "gen_ai.usage.input_tokens": 2200,
    "gen_ai.usage.output_tokens": 187,
    "gen_ai.usage.total_tokens": 2387,
    "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "system_prompt": "You are a helpful assistant with access to weather, time, and calculator tools..."
  },
  "metrics": {
    "completion_tokens": 374,
    "duration": 3.6653401851654053,
    "errors": 0,
    "estimated_cost": 0.005016,
    "llm_calls": 2,
    "llm_duration": 2.1108832359313965,
    "llm_errors": 0,
    "prompt_tokens": 4400,
    "time_to_first_token": null,
    "tool_calls": 2,
    "tool_errors": 0,
    "total_tokens": 4774
  },
  "output": [
    {
      "content": "Here's the current information for Paris:\n\n**Weather:**\n- Temperature: 64°F\n- Conditions: Cloudy\n- Humidity: 70%\n\n**Time:**\n- Current time: 10:29 PM\n- Date: Friday, November 14, 2025\n- Timezone: Europe/Paris (UTC+1)\n\nIt's a cloudy evening in Paris with moderate temperatures and humidity.",
      "role": "assistant"
    }
  ],
  "root_span_id": "240393a48004d6196b59d381bc12dc10",
  "name": "invoke_agent Strands Agents",
  "tags": null
}
```

**これで分かること**：
- **入力**: ユーザーのクエリ（「What's the weather in Paris...」）
- **メタデータ**: エージェント名、利用可能なツール、使用されたモデル、トークン使用量の詳細
- **メトリクス**: 期間（3.67 秒）、推定コスト（$0.005016）、LLM 呼び出し（2）、ツール呼び出し（2）
- **出力**: 天気と時間情報を含むエージェントの完全なレスポンス
- **ルートスパン ID**: 詳細なスパントレースとの相関用

#### Braintrust: LLM 固有の洞察

AI/LLM ワークロード向けの Braintrust 固有の機能：

- **コスト追跡**: 異なるモデルと呼び出しにわたる API コストを追跡
- **品質スコア**: モデル改善のために呼び出し品質を評価
- **カスタムメトリクス**: カスタムオブザーバビリティメトリクスを定義して追跡
- **モデルパフォーマンス**: 異なるモデル間でパフォーマンスを比較
- **フィードバック統合**: ユーザーフィードバックとグラウンドトゥルースを記録


### 主なトレードオフ

**CloudWatch に表示されるもの**: ❌ トレースなし（トレースは Braintrust のみ）、メトリクスのみ

**Braintrust に表示されるもの**: ✅ すべての低レベル運用詳細

**結果**: 詳細なトレースデバッグが必要な場合、Braintrust を確認する必要があります（CloudWatch では利用不可）

### 利点

✅ 外部オブザーバビリティプラットフォームのバックアップ
✅ LLM 固有のメトリクスとコスト追跡
✅ モデル改善のための品質スコアリング
✅ カスタムメトリクスのサポート
✅ クロスプラットフォームの一貫性（OTEL 標準）

### 最適な用途

- 本番環境のデプロイ
- コスト追跡と最適化
- モデルパフォーマンス監視
- 外部監査証跡
- マルチプラットフォームオブザーバビリティ

### このセットアップを使用するタイミング

以下の場合に Braintrust オブザーバビリティを使用：

1. 外部オブザーバビリティが必要
2. LLM API コストを詳細に追跡したい
3. モデル品質を評価している
4. ベンダー非依存のオブザーバビリティが必要
5. 外部バックアップを必要とする SLA がある

---

## オプション 3: CloudWatch APM（エージェントサービス）

CloudWatch は、迅速な運用監視のための組み込みサービスレベルダッシュボードを提供します。

### 表示される内容

#### 組み込みエージェントダッシュボード

CloudWatch はエージェント用のダッシュボードを自動的に作成します：

- **エージェント名**: エージェントの識別子
- **ステータス**: 実行中、停止、またはエラー状態
- **パフォーマンスメトリクス**: レスポンス時間とスループット
- **エラー追跡**: エラー率とタイプ
- **リソース使用量**: CPU とメモリ使用率

![CloudWatch エージェントサービスダッシュボード](./img/demo1-cw-3.gif)

#### 経時的なエージェントパフォーマンス

トレンドを監視：

- **呼び出しトレンド**: エージェントが呼び出された回数（時間別、日別）
- **レイテンシトレンド**: レスポンス時間の変化
- **エラートレンド**: エラー率の変化
- **成功率トレンド**: 経時的な成功率



#### エラー分析

組み込みのエラーダッシュボードに表示される内容：

- **エラータイプ**: 発生したエラーの種類
- **エラー頻度**: 各エラーの発生頻度
- **エラータイムライン**: エラーが発生した時期
- **影響を受けた呼び出し**: 影響を受けた呼び出しの数



### 利点

✅ 組み込み、セットアップ不要
✅ クイック運用概要
✅ 自動ダッシュボード
✅ リアルタイム監視
✅ CloudWatch との統合

### 最適な用途

- 運用監視
- クイックヘルスチェック
- トレンド分析
- エグゼクティブダッシュボード
- アラートと通知

### APM ダッシュボードへのアクセス

```bash
# AWS コンソールを開く
# 移動: CloudWatch → APM → Services → Agents
# エージェントを選択してダッシュボードを表示
```

---

## 比較まとめ

| 機能 | CloudWatch のみ | Braintrust | CloudWatch APM |
|---------|-----------------|-----------|----------------|
| **エージェントメトリクス** | ✅ 完全な詳細 | ✅ 呼び出しレベル | ✅ 集約済み |
| **トレース詳細** | ✅ すべての操作 | ✅ Braintrust のみ | ❌ トレースなし |
| **セッション/メモリ** | ✅ 完全な履歴 | ✅ 利用可能 | ❌ なし |
| **LLM コスト追跡** | ❌ なし | ✅ あり | ❌ なし |
| **トラブルシューティング** | ✅ 最適 | ⚠️ CW では制限あり | ❌ 制限あり |
| **運用監視** | ✅ 良好 | ✅ 良好 | ✅ 最適 |
| **セットアップの複雑さ** | ✅ シンプル | ⚠️ 中程度 | ✅ 自動 |
| **外部バックアップ** | ❌ AWS のみ | ✅ あり | ❌ AWS のみ |

---

## CloudWatch ログ: 実際に記録される内容

CloudWatch ログに表示される内容を理解することが、オブザーバビリティアプローチを選択する鍵です。

### オプション 1: CloudWatch のみ - ランタイムと OTEL 両方のログ

Braintrust が**設定されていない**場合、CloudWatch は**両方のタイプのログ**をキャプチャします：

#### ランタイムログ（人間が読みやすい形式）
エージェントコードからのプレーンテキストアプリケーションログ：

```
2025-11-14T21:14:27.242000+00:00 2025/11/14/[runtime-logs]ff54a177-6721-40a0-abf6-5c47e2a265c5 2025-11-14 21:14:27,242,p1,{weather_time_agent.py:172},INFO,Agent invoked with prompt: What's the weather in Paris and what time is it there?
2025-11-14T21:14:27.243000+00:00 2025/11/14/[runtime-logs]ff54a177-6721-40a0-abf6-5c47e2a265c5 2025-11-14 21:14:27,243,p1,{weather_time_agent.py:128},INFO,Braintrust observability not configured (CloudWatch only)
2025-11-14T21:14:27.244000+00:00 2025/11/14/[runtime-logs]ff54a177-6721-40a0-abf6-5c47e2a265c5 2025-11-14 21:14:27,244,p1,{weather_time_agent.py:145},INFO,Agent initialized with tools: get_weather, get_time, calculator
2025-11-14T21:14:28.303000+00:00 2025/11/14/[runtime-logs]ff54a177-6721-40a0-abf6-5c47e2a265c5 2025-11-14 21:14:28,303,p1,{weather_tool.py:91},INFO,Weather for Paris: 64°F, Cloudy
```

**ランタイムログに表示される内容**：
- エージェントの初期化と設定
- ツール実行の開始/完了
- ビジネスロジック出力
- コードからのエラーと警告
- 読みやすく理解しやすい

#### OTEL ログ（構造化 JSON）- 追加のインフラストラクチャテレメトリ

**ランタイムログに加えて**、CloudWatch は豊富なメタデータを含む構造化 OTEL JSON ログを受信します：

```json
{
  "resource": {
    "attributes": {
      "deployment.environment.name": "bedrock-agentcore:default",
      "aws.local.service": "weather_time_observability_agent.DEFAULT",
      "service.name": "weather_time_observability_agent.DEFAULT",
      "cloud.region": "us-east-1",
      "aws.log.stream.names": "otel-rt-logs",
      "telemetry.sdk.name": "opentelemetry",
      "aws.service.type": "gen_ai_agent",
      "telemetry.sdk.language": "python",
      "cloud.provider": "aws",
      "cloud.resource_id": "arn:aws:bedrock-agentcore:us-east-1:015469603702:runtime/weather_time_observability_agent-wFRAfL58PN/runtime-endpoint/DEFAULT:DEFAULT",
      "aws.log.group.names": "/aws/bedrock-agentcore/runtimes/weather_time_observability_agent-wFRAfL58PN-DEFAULT",
      "telemetry.sdk.version": "1.33.1",
      "cloud.platform": "aws_bedrock_agentcore",
      "telemetry.auto.version": "0.12.2-aws"
    }
  },
  "scope": {
    "name": "__main__"
  },
  "timeUnixNano": 1763506342567173120,
  "observedTimeUnixNano": 1763506342567458901,
  "severityNumber": 9,
  "severityText": "INFO",
  "body": "Agent invoked with prompt: What's the weather in Seattle and what time is it there?",
  "attributes": {
    "otelTraceSampled": true,
    "code.file.path": "/app/agent/weather_time_agent.py",
    "code.function.name": "strands_agent_bedrock",
    "otelTraceID": "691cf8a657baf2b2608cb3c275537ebf",
    "otelSpanID": "f0db04745985210a",
    "code.line.number": 172,
    "otelServiceName": "weather_time_observability_agent.DEFAULT"
  },
  "flags": 1,
  "traceId": "691cf8a657baf2b2608cb3c275537ebf",
  "spanId": "f0db04745985210a"
}
```

**OTEL ログが提供する内容**（Braintrust が無効な場合のみ利用可能）：
- **リソースコンテキスト**: AWS サービス詳細、リージョン、環境（bedrock-agentcore、サービス名、クラウドリージョンなど）
- **スコープ情報**: ログの発生元（`__main__` などの計装スコープ）
- **コードの場所**: 正確なソースの場所のためのファイルパス、関数名、行番号
- **トレース相関**: エージェント実行内のすべての操作をリンクする `traceId` と `spanId`
- **メッセージ本文**: 構造化されたログメッセージ内容
- **タイミング**: 正確なタイミング分析のための Unix ナノ秒タイムスタンプ
- **テレメトリメタデータ**: SDK バージョンと自動計装の詳細

**重要なポイント**: 各 OTEL ログエントリには、そのエージェント実行内の他のすべての操作と相関するトレースコンテキスト（`traceId`、`spanId`）が含まれます。runtime-logs と otel-rt-logs の両方のストリームがある場合、デバッグと監視のための完全なオブザーバビリティが得られます：人間が読みやすいログと構造化されたトレースデータ。

---

### オプション 2: Braintrust + CloudWatch - ランタイムログのみ

Braintrust が**設定されている**場合（BRAINTRUST_API_KEY が設定済み）、CloudWatch の動作が変わります：

#### ランタイムログのみ（OTEL ログなし）

```
2025-11-14T21:27:47.557000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:47,557,p1,{weather_time_agent.py:172},INFO,Agent invoked with prompt: What's the weather in Paris and what time is it there?
2025-11-14T21:27:47.559000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:47,557,p1,{weather_time_agent.py:117},INFO,Braintrust observability enabled - initializing telemetry
2025-11-14T21:27:47.598000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:47,598,p1,{config.py:164},INFO,OTLP exporter configured
2025-11-14T21:27:47.598000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:47,598,p1,{weather_time_agent.py:123},INFO,Strands telemetry initialized successfully
2025-11-14T21:27:47.599000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:47,599,p1,{weather_time_agent.py:145},INFO,Agent initialized with tools: get_weather, get_time, calculator
2025-11-14T21:27:49.437000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:49,437,p1,{weather_time_agent.py:47},INFO,Getting weather for city: Paris
2025-11-14T21:27:49.437000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:49,437,p1,{weather_tool.py:91},INFO,Weather for Paris: 64°F, Cloudy
2025-11-14T21:27:52.634000+00:00 2025/11/14/[runtime-logs]44ed2d92-3d5e-42fa-ab34-30050e2c046c 2025-11-14 21:27:52,634,p1,{weather_time_agent.py:183},INFO,Agent invocation completed successfully
```

**Braintrust が有効な場合の変更点**：
- ✅ ランタイムログは引き続き表示される（アプリケーション出力）
- ❌ **OTEL ログは CloudWatch に送信されない**（代わりに Braintrust に送信）
- ✅ 完全な OTEL トレースデータは代わりに Braintrust に送信

**理由は？** Braintrust がメインのオブザーバビリティプラットフォームの場合、重複したトレースストレージを避け、CloudWatch のコストを削減するため。

---

## まとめ: 各オプションがキャプチャする内容

| データタイプ | CloudWatch のみ | Braintrust 有効 |
|-----------|-----------------|-------------------|
| **ランタイムログ** | ✅ はい | ✅ はい |
| **OTEL ログ（JSON）** | ✅ はい | ❌ なし（Braintrust に送信） |
| **構造化トレースデータ** | ✅ CloudWatch Logs 内 | ✅ Braintrust 内 |
| **完全なトレース詳細** | ✅ 利用可能 | ✅ 利用可能 |

---

## 次のステップ

1. **まず CloudWatch のみを試す** - Braintrust 認証情報なしでデプロイして、ランタイム + OTEL ログを確認
2. **メトリクスとトレースを探索** - `scripts/check_*.sh` のスクリプトを使用して両方のログタイプを表示
3. **ログを比較** - runtime-logs と otel-rt-logs ストリームの違いに注目
4. **必要に応じて Braintrust を追加** - Braintrust 認証情報で `.env` を編集し、再デプロイして Braintrust でトレースを確認
