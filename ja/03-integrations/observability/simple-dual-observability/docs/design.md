# システム設計とアーキテクチャ

## 概要

このドキュメントでは、Simple Dual Observability チュートリアルのアーキテクチャ、コンポーネントの相互作用、および OpenTelemetry トレースフローについて包括的に説明します。

## アーキテクチャ概要

チュートリアルでは、同じエージェントに対して 2 つのデプロイモードを示します：

### モード 1: ローカルテスト（開発用）

本番環境へのデプロイ前の開発とデバッグに使用します。

```
開発者マシン
    |
    v
agent/weather_time_agent.py（ローカルで実行）
    |
    v（Bedrock Converse API を呼び出し）
Amazon Bedrock（Claude 3.5 Haiku）
    |
    v（ツール呼び出し）
tools/*.py（ローカルで実行）
    |
    v
ターミナルにレスポンスを返す

オブザーバビリティ: なし（ローカルテストのみ）
目的: デプロイ前にエージェントロジックをテスト
```

### モード 2: AgentCore Runtime デプロイ（本番/デモ）

メインのチュートリアルフロー - 本番環境での自動オブザーバビリティを示します。

```
開発者のラップトップ
    |
    v（simple_observability.py を実行）
Python CLI スクリプト（boto3 クライアント）
    |
    v（API 呼び出し: invoke_agent）
Amazon Bedrock AgentCore Runtime（マネージドサービス）
    |
    v（あなたのエージェントはここで自動 OTEL 付きで実行）
agent/weather_time_agent.py（デプロイされてホスト）
    |
    v（MCP 経由のツール呼び出し）
MCP ツール（weather、time、calculator）
    |
    v（トレースは自動的にエクスポート）
    |
    +------------------+------------------+
    |                  |
    v                  v
CloudWatch Logs    Braintrust
（AWS ネイティブ）  （AI プラットフォーム）

オブザーバビリティ: フル - 自動 OTEL トレース
目的: ゼロコードオブザーバビリティを備えた本番デプロイ
```

## コンポーネントの相互作用

### 1. クライアントスクリプト（simple_observability.py）

**目的**: デプロイ済みエージェントを呼び出し、デモシナリオを管理

**責任**:
- AgentCore Runtime 用の boto3 クライアントを作成
- トレース相関のための一意のセッション ID を生成
- `invoke_agent` API 経由でエージェントを呼び出し
- オブザーバビリティリンクとガイダンスを出力
- シナリオ実行を管理（success、error、dashboard）

**主要な操作**:
```python
# クライアントを作成
client = boto3.client("bedrock-agentcore-runtime", region_name=region)

# エージェントを呼び出し
response = client.invoke_agent(
    agentId=agent_id,
    sessionId=session_id,
    inputText=query,
    enableTrace=True  # 詳細なトレースを有効化
)
```

### 2. AgentCore Runtime（マネージドサービス）

**目的**: 自動計装でエージェントコードをホストして実行

**責任**:
- デプロイされたエージェントコードを読み込み
- 自動 OTEL 計装を注入
- エージェントのライフサイクルを管理
- MCP ツールへのツール呼び出しをルーティング
- 設定されたプラットフォームにトレースをエクスポート

**自動計装**:
- エージェントコードを OTEL スパンでラップ
- タイミング、パラメータ、結果をキャプチャ
- エラーと例外を記録
- 分散トレースを相関
- 複数のバックエンドに同時にエクスポート

**コード変更不要** - 計装は自動です。

### 3. Weather/Time エージェント（agent/weather_time_agent.py）

**目的**: Bedrock Converse API を使用したコアエージェントロジック

**責任**:
- ユーザークエリを受信
- ツール付きで Bedrock Converse API を呼び出し
- エージェンティックループ（ツール呼び出し）を実装
- ツールを実行してレスポンスを集約
- ユーザーに最終回答を返す

**主な機能**:
- Amazon Bedrock Converse API を使用
- Claude 経由のツール呼び出しをサポート
- 標準的なエージェンティックループパターンを実装
- 適切なエラー処理

**エージェンティックループ**:
```
1. ユーザークエリ -> ツール付きで Claude に送信
2. Claude がツール使用を決定 -> ツールを実行
3. ツール結果 -> Claude に送り返す
4. Claude が最終回答を提供 -> ユーザーに返す
```

### 4. MCP ツール（tools/*.py）

**目的**: エージェントが実行するツールの実装

**利用可能なツール**:

**Weather ツール**（`tools/weather_tool.py`）:
```python
def get_weather(city: str) -> Dict[str, Any]:
    """デモ目的のシミュレートされた天気データを返します。"""
    return {
        "city": city,
        "temperature": "72F",
        "condition": "Partly cloudy",
        "humidity": "65%"
    }
```

**Time ツール**（`tools/time_tool.py`）:
```python
def get_time(timezone: str) -> Dict[str, Any]:
    """タイムゾーンの現在時刻を返します。"""
    return {
        "timezone": timezone,
        "current_time": datetime.now(pytz.timezone(tz)).isoformat(),
        "utc_offset": "+/-X hours"
    }
```

**Calculator ツール**（`tools/calculator_tool.py`）:
```python
def calculator(
    operation: str,
    a: float,
    b: Optional[float] = None
) -> Dict[str, Any]:
    """数学計算を実行します。"""
    # サポート: add、subtract、multiply、divide、factorial
    # エラー処理のデモ（負の数の階乗）
```

### 5. テレメトリ計装（Strands ライブラリ）

**目的**: エージェントコードを自動的に計装し、複数のプラットフォームにトレースをエクスポート

**設定**:

Strands テレメトリライブラリは以下を自動的に設定します：

**プロセッサ**:
- バッチプロセッサ（効率のためにスパンをグループ化）
- リソースプロセッサ（サービスメタデータを追加）
- メモリリミッター（OOM を防止）

**エクスポーター**:
1. **OTLP/Braintrust**: Braintrust プラットフォームにエクスポート（BRAINTRUST_API_KEY が設定されている場合）
2. **CloudWatch Logs**: AgentCore Runtime によって自動的にキャプチャ
3. **Logging**: stdout へのデバッグ出力（オプション）

**設定**:
すべての設定は環境変数経由で処理されます：
- `BRAINTRUST_API_KEY`: Braintrust プラットフォームの API キー
- `OTEL_*`: 標準の OpenTelemetry 環境変数
- `BEDROCK_*`: Bedrock 固有の設定

エージェントはこれらの環境変数に基づいて OTLP エクスポーターを自動的に設定する Strands テレメトリライブラリを使用します。静的な YAML 設定ファイルは不要です。

### 6. CloudWatch Logs

**目的**: AWS ネイティブのアプリケーションログとオブザーバビリティ

**機能**:
- リアルタイムログストリーム表示
- タイムスタンプ付き構造化ログ
- ツール実行追跡
- エラーと例外のログ
- CloudWatch アラームとの統合

**キャプチャされるデータ**:
- トレース ID とスパン ID
- サービス名と操作
- タイミング情報（開始、期間）
- HTTP ステータスコード
- エラーメッセージとスタックトレース
- カスタム属性（モデル、トークンなど）

### 7. Braintrust

**目的**: AI に特化したオブザーバビリティと品質監視

**機能**:
- LLM 固有のメトリクス
- トークンとコスト追跡
- プロンプトバージョン比較
- 品質評価
- ハルシネーション検出

**キャプチャされるデータ**:
- すべての OTEL トレースデータ
- トークン数（入力、出力、合計）
- モデルパラメータ（temperature、max tokens）
- コスト計算
- カスタム AI メトリクス

## OTEL フローダイアグラム

### トレース作成フロー

```
エージェント呼び出し
    |
    v
AgentCore Runtime が ROOT SPAN を作成
    |
    +-- Span: agent.invocation
        |  属性: agent_id、session_id、query
        |  開始時間: T0
        |
        +-- Span: llm.call（Bedrock Converse）
        |   |  属性: model_id、temperature、max_tokens
        |   |  開始時間: T0 + 50ms
        |   |  期間: 800ms
        |   |  イベント: token_usage（input: 120、output: 45）
        |
        +-- Span: tool.selection
        |   |  属性: tools_available、tools_selected
        |   |  開始時間: T0 + 900ms
        |   |  期間: 50ms
        |
        +-- Span: gateway.execution（weather ツール）
        |   |  属性: tool_name、tool_input
        |   |  開始時間: T0 + 1000ms
        |   |  期間: 200ms
        |   |  イベント: tool_result
        |
        +-- Span: gateway.execution（time ツール）
        |   |  属性: tool_name、tool_input
        |   |  開始時間: T0 + 1250ms
        |   |  期間: 150ms
        |
        +-- Span: llm.call（最終回答）
        |   |  属性: model_id
        |   |  開始時間: T0 + 1450ms
        |   |  期間: 600ms
        |
        +-- Span: response.formatting
            |  開始時間: T0 + 2100ms
            |  期間: 50ms
            |  終了時間: T0 + 2150ms

総期間: 2150ms
ステータス: OK
```

### エラーフロー（シナリオ 2）

```
エージェント呼び出し: "Calculate factorial of -5"
    |
    v
AgentCore Runtime が ROOT SPAN を作成
    |
    +-- Span: agent.invocation
        |
        +-- Span: llm.call
        |   |  Claude が calculator ツールを使用することを決定
        |
        +-- Span: tool.selection
        |   |  選択: calculator
        |
        +-- Span: gateway.execution（calculator）
        |   |  属性: operation=factorial、a=-5
        |   |  ステータス: ERROR
        |   |  エラー: "Cannot calculate factorial of negative number"
        |   |  例外: ValueError
        |
        +-- Span: llm.call（エラー処理）
        |   |  Claude がエラーメッセージを受信
        |   |  有用なレスポンスを生成
        |
        +-- Span: response.formatting
            |  最終レスポンスでエラーを説明

総期間: 1800ms
ステータス: OK（エラーを適切に処理）
ルートスパンステータス: OK
子スパンステータス: ERROR（calculator スパン）
```

## デュアルプラットフォームオブザーバビリティ戦略

### なぜデュアルプラットフォームオブザーバビリティなのか？

このチュートリアルでは、連携して動作する 2 つの異なるオブザーバビリティメカニズムを示します：

**CloudWatch オブザーバビリティ（自動、AgentCore Runtime から）**:
- 設定なしで常に有効
- AgentCore Runtime インフラストラクチャからベンダードトレースを受信
- CloudWatch Logs とのネイティブ AWS 統合
- アラート用の CloudWatch アラーム
- 長期保持ポリシー
- VPC 統合

**Braintrust オブザーバビリティ（オプション、Strands Agent から）**:
- `BRAINTRUST_API_KEY` 環境変数でオプトイン
- Strands エージェントから OpenTelemetry トレースを直接受信
- AI 固有のメトリクス（LLM トークン、コスト、品質）
- より良い LLM フォーカスの可視化
- 評価とプロンプト管理
- AWS インフラストラクチャから独立

**主な違い**: CloudWatch トレースは AgentCore Runtime インフラストラクチャ（ベンダード形式）から来ますが、Braintrust トレースは Strands エージェントコード（OTEL 形式）から来ます。これらは重複ではなく、補完的です。

### エクスポートアーキテクチャ

```
AgentCore Runtime（Strands テレメトリ付き）
    |
    v
OTLP エクスポーター（環境変数で設定）
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
CloudWatch Logs   OTLP/Braintrust    Logging
（AgentCore）       エクスポーター     エクスポーター
    |                  |                  |
    v                  v                  v
CloudWatch Logs   Braintrust API     stdout
（OTEL トレース）   プラットフォーム   （デバッグ）
```

**注意**: 設定は Strands テレメトリライブラリを使用した純粋な環境変数ベースです。外部の OTEL Collector や静的な YAML 設定は必要ありません。

### トレース相関

すべてのトレースは相関のために共通の識別子を共有します：

**トレース ID**: リクエスト全体の一意の識別子
**スパン ID**: 各操作の一意の識別子
**親スパン ID**: スパンを階層的にリンク
**セッション ID**: 複数の呼び出しをグループ化
**カスタム属性**: 追加の相関データ

**例**:
```
トレース ID: 1-67891011-abcdef1234567890
セッション ID: demo_session_a1b2c3d4
エージェント ID: agent-xyz123

CloudWatch クエリ:
トレース ID またはセッション ID でトレースをフィルター

Braintrust クエリ:
同じトレース ID またはセッション ID でトレースをフィルター

結果: 両方のプラットフォームで同一のスパンが表示
```

## データフローまとめ

1. **ユーザーがスクリプトを実行**: `simple_observability.py --scenario success`
2. **スクリプトがエージェントを呼び出し**: boto3 が AgentCore Runtime を呼び出し
3. **Runtime がトレースを開始**: トレース ID でルートスパンを作成
4. **エージェントコードが実行**: Bedrock Converse API を呼び出し
5. **Claude がツールを選択**: 子スパンとして計装
6. **ツールが MCP 経由で実行**: 各ツール呼び出しはスパン
7. **エージェントが結果を集約**: 最終レスポンススパン
8. **CloudWatch ログ**: AgentCore Runtime がアプリケーションログを CloudWatch Logs に自動エクスポート
9. **Braintrust エクスポート**（オプション）: BRAINTRUST_API_KEY が設定されている場合、Strands エージェントが OTEL トレースを Braintrust にエクスポート
10. **ユーザーがトレースを表示**: CloudWatch（常に利用可能）とオプションで Braintrust（設定されている場合）

## パフォーマンス特性

### レイテンシ内訳

典型的な成功リクエスト（2 ツール）:
- エージェント呼び出しオーバーヘッド: 50ms
- LLM 呼び出し（ツール選択）: 800ms
- ツール実行（2 ツール）: 350ms
- LLM 呼び出し（最終回答）: 600ms
- レスポンスフォーマット: 50ms
- **合計**: 約 1850ms

### トレースエクスポートオーバーヘッド

- トレース生成: <5ms（自動）
- OTEL 収集: <10ms（バッチ処理）
- CloudWatch へのエクスポート: <50ms（非同期）
- Braintrust へのエクスポート: <50ms（非同期）
- **ユーザーへの影響**: <5ms（エクスポートは非同期）

### スケールに関する考慮事項

このチュートリアルは学習とデモンストレーション用に設計されています：
- **リクエストレート**: 1 分あたり 1-10 リクエスト
- **トレースボリューム**: デモ実行あたり 3-30 トレース
- **データ保持**: 7 日間（Braintrust 無料プラン）

本番スケールについては、本番デプロイガイドを参照してください。

## セキュリティに関する考慮事項

### 認証

**AgentCore Runtime**: IAM 権限を使用
**MCP ツール**: エージェント権限で実行
**Braintrust**: OTEL 設定内の API キー
**CloudWatch**: IAM ロール権限

### データプライバシー

**トレースデータに含まれる内容**:
- ユーザークエリ（潜在的に機密）
- ツールの入力と出力
- モデルのレスポンス

**推奨事項**:
- PII フィルタリングに Amazon Bedrock Guardrails を使用
- Braintrust データ保持ポリシーを確認
- CloudWatch ログ保持を設定
- 本番環境でトレースサンプリングを実装

### ネットワークセキュリティ

**AgentCore Runtime**: プライベート AWS ネットワーク
**MCP ツール**: ランタイム内でローカル実行
**OTEL エクスポート**: CloudWatch と Braintrust への HTTPS
デフォルトでは**パブリックエンドポイントは公開されない**

## モニタリングのモニタリング

### OTEL Collector の健全性

OTEL Collector は健全性エンドポイントを公開します：

```bash
# ヘルスチェック
curl http://localhost:13133

# メトリクスエンドポイント
curl http://localhost:8888/metrics

# デバッグエンドポイント（zpages）
curl http://localhost:55679/debug/tracez
```

### トレースエクスポートの検証

トレースが両方のプラットフォームに到達していることを確認：

```bash
# CloudWatch Logs でエクスポートを確認
aws logs tail /aws/agentcore/traces --follow

# OTEL Collector ログを確認
docker logs otel-collector --follow

# Braintrust UI で確認
# プロジェクトに移動してトレース数を確認
```

## よくある問題のトラブルシューティング

### トレースが表示されない

**症状**: CloudWatch または Braintrust にトレースがない

**原因**:
1. OTEL Collector が実行されていない
2. 無効な API キー
3. サンプリングレートが 0 に設定
4. ネットワーク接続の問題

**解決策**: [docs/troubleshooting.md](troubleshooting.md) を参照

### 不完全なトレース

**症状**: スパンが欠けているか、トレースが部分的

**原因**:
1. エージェントタイムアウト
2. ツール実行の失敗
3. OTEL Collector バッファオーバーフロー

**解決策**: エージェントログを確認し、タイムアウトを増加

### トレース相関の問題

**症状**: 関連するスパンが見つからない

**原因**:
1. セッション ID が伝播されていない
2. 異なるトレース ID が使用されている
3. サービス間のクロックスキュー

**解決策**: API 呼び出しでセッション ID を確認

## 次のステップ

アーキテクチャを理解した後：

1. Braintrust プラットフォーム設定について [Braintrust セットアップ](braintrust-setup.md) を確認
2. エージェントのカスタマイズについて [開発ガイド](development.md) を確認
3. CloudWatch と一般的な問題について [トラブルシューティング](troubleshooting.md) を確認
