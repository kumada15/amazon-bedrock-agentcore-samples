# デモガイド: オブザーバビリティデモンストレーションの実行

このガイドでは、Amazon Bedrock AgentCore、CloudWatch、および Braintrust を使用したデュアルオブザーバビリティセットアップのデモンストレーションを実行するためのステップバイステップの手順を提供します。システムの動作を紹介し、オブザーバビリティデータの流れを理解するために使用してください。

## 概要

3 つのデモンストレーションシナリオがオブザーバビリティシステムの異なる側面を示します：

- **シナリオ 1**: 複雑な推論を伴う成功したマルチツールクエリ - 正常な動作を示す
- **シナリオ 2**: エラー処理とリカバリ - 両プラットフォームでのエラー可視性を示す
- **シナリオ 3**: ダッシュボードレビュー - CloudWatch と Braintrust ダッシュボードを確認

### クイックスタート - すべてのシナリオを実行

```bash
# 3 つのシナリオを順番に実行（デモに推奨）
uv run python simple_observability.py --scenario all

# 個別のシナリオを実行
uv run python simple_observability.py --scenario success    # シナリオ 1
uv run python simple_observability.py --scenario error      # シナリオ 2
uv run python simple_observability.py --scenario dashboard  # シナリオ 3

# エージェント ID を明示的に指定
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all
```

## シナリオ 1: 成功したマルチツールクエリ

### 目的
複数のツール呼び出しを伴う成功したエージェント実行を示し、CloudWatch（自動）とオプションで Braintrust（設定されている場合）でトレースを紹介します。

### クエリ
```
What's the weather in Seattle and calculate the square root of 144?
```

### 実行方法

```bash
# 成功クエリシナリオを実行
uv run python simple_observability.py --scenario success

# またはエージェント ID を明示的に指定
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

### 期待される動作

#### エージェント実行フロー
1. **入力処理**（0-2 秒）
   - エージェントがユーザークエリを受信
   - Claude との会話を初期化
   - Braintrust が会話全体の親スパンを作成
   - CloudWatch が初期リクエストメトリクスを記録

2. **ツール選択**（2-5 秒）
   - エージェントがクエリを分析し、2 つのタスクを識別
   - 両方のツールを呼び出すことを決定
   - Braintrust で各ツール呼び出しの子スパンを作成
   - CloudWatch がツール使用メトリクスを記録

3. **Weather ツール実行**（5-8 秒）
   - get_weather ツールを location="Seattle" で呼び出し
   - 戻り値: "72 degrees and sunny"
   - Braintrust に記録:
     - ツール名: get_weather
     - 入力: {"location": "Seattle"}
     - 出力: "72 degrees and sunny"
     - 期間: 約 0.5 秒
   - CloudWatch に記録:
     - ToolName ディメンション: get_weather
     - ToolCallDuration メトリクス
     - ToolCallSuccess メトリクス

4. **Calculator ツール実行**（8-11 秒）
   - calculate ツールを operation="sqrt", x=144 で呼び出し
   - 戻り値: 12.0
   - Braintrust に記録:
     - ツール名: calculate
     - 入力: {"operation": "sqrt", "x": 144}
     - 出力: 12.0
     - 期間: 約 0.5 秒
   - CloudWatch も同様のメトリクスを記録

5. **レスポンス生成**（11-15 秒）
   - エージェントが最終レスポンスを合成
   - 両方のツール結果を組み合わせ
   - 自然言語の回答を返す
   - 両システムが完了を記録

#### 期待されるコンソール出力
```
2025-10-25 12:00:00,p12345,{simple_observability.py:150},INFO,Starting dual observability demo...
2025-10-25 12:00:00,p12345,{simple_observability.py:155},INFO,Braintrust experiment initialized: dual-observability-demo
2025-10-25 12:00:00,p12345,{simple_observability.py:160},INFO,CloudWatch namespace: AgentCore/Observability
2025-10-25 12:00:01,p12345,{simple_observability.py:200},INFO,
Query: What's the weather in Seattle and calculate the square root of 144?
2025-10-25 12:00:01,p12345,{simple_observability.py:210},INFO,Processing query with agent...
2025-10-25 12:00:05,p12345,{simple_observability.py:250},INFO,Tool call: get_weather
2025-10-25 12:00:05,p12345,{simple_observability.py:255},INFO,Tool input: {"location": "Seattle"}
2025-10-25 12:00:06,p12345,{simple_observability.py:260},INFO,Tool output: 72 degrees and sunny
2025-10-25 12:00:08,p12345,{simple_observability.py:250},INFO,Tool call: calculate
2025-10-25 12:00:08,p12345,{simple_observability.py:255},INFO,Tool input: {"operation": "sqrt", "x": 144}
2025-10-25 12:00:09,p12345,{simple_observability.py:260},INFO,Tool output: 12.0
2025-10-25 12:00:12,p12345,{simple_observability.py:300},INFO,
Response: The weather in Seattle is currently 72 degrees and sunny. The square root of 144 is 12.
2025-10-25 12:00:12,p12345,{simple_observability.py:305},INFO,Query completed in 11.2 seconds
2025-10-25 12:00:12,p12345,{simple_observability.py:310},INFO,Metrics sent to CloudWatch
2025-10-25 12:00:12,p12345,{simple_observability.py:315},INFO,Trace logged to Braintrust
```

#### 期待される CloudWatch メトリクス

CloudWatch は OpenTelemetry 経由で AgentCore Runtime からトレースとメトリクスを自動的に受信します。主な観察ポイント：

**CloudWatch GenAI Observability/APM コンソールで：**
- エージェント呼び出し数がインクリメント
- 記録されるレイテンシ: 約 11-15 秒（すべてのツール呼び出しと LLM 処理を含む）
- 表示されるツール実行時間: weather ツール 約 500ms、calculator ツール 約 500ms
- 両方のツールの成功した実行を示すスパン詳細
- エラーの記録なし

**メトリクスに関する注意：**
名前空間は `AWS/Bedrock-AgentCore` です（OTEL 設定で構成）。AgentCore Runtime は自動的に以下を出力します：
- 呼び出し回数
- レイテンシ測定
- 成功/エラーステータス
- ツール実行詳細
- スパン階層と関係

これらのメトリクスはカスタムメトリクス名前空間ではなく、CloudWatch GenAI Observability ダッシュボードまたは APM コンソールに表示されます。

#### 期待される Braintrust トレース
```
スパン階層:
└─ conversation_12345 [15.2s]
   ├─ model_call_1 [3.5s]
   │  └─ 入力: "What's the weather in Seattle and calculate the square root of 144?"
   │  └─ 出力: [get_weather と calculate の tool_use ブロック]
   ├─ tool_get_weather [0.5s]
   │  └─ 入力: {"location": "Seattle"}
   │  └─ 出力: "72 degrees and sunny"
   ├─ tool_calculate [0.5s]
   │  └─ 入力: {"operation": "sqrt", "x": 144}
   │  └─ 出力: 12.0
   └─ model_call_2 [2.1s]
      └─ 入力: [ツール結果]
      └─ 出力: "The weather in Seattle is currently 72 degrees and sunny..."

メタデータ:
  - 総期間: 15.2s
  - ツール呼び出し: 2
  - モデル: claude-3-5-sonnet-20241022
  - 成功: true
```

### CloudWatch Logs の表示

`check_logs.sh` スクリプトを使用してエージェント実行ログを表示：

```bash
# 過去 30 分間のログを表示
scripts/check_logs.sh --time 30m

# デモ実行中にリアルタイムでログを追跡
scripts/check_logs.sh --follow

# 過去 1 時間のログを表示
scripts/check_logs.sh --time 1h
```

**ログで表示される内容：**
- エージェントの初期化と起動メッセージ
- 入力パラメータ付きのツール呼び出し
- ツール実行結果と出力
- 各操作のタイミング情報
- CloudWatch と Braintrust への OTEL トレースエクスポート確認
- ログレベル（INFO、DEBUG など）付きの構造化ログ

### ハイライトするポイント
- ✓ 両方のツールが正常に実行
- ✓ トレースが完全な実行フローを表示
- ✓ CloudWatch メトリクスが Braintrust スパンと一致
- ✓ トークン使用量が正確に追跡
- ✓ レイテンシがコンポーネント別に分類
- ✓ check_logs.sh 経由でデバッグ用の詳細ログが利用可能

### 時間見積もり
総デモンストレーション時間: 3-5 分
- 実行: 約 15 秒
- CloudWatch ダッシュボードレビュー: 1-2 分
- Braintrust トレースレビュー: 2-3 分

## シナリオ 2: エラー処理

### 目的
オブザーバビリティシステムがエラーをキャプチャして追跡する方法を示し、部分的な失敗とリカバリを含めます。

### クエリ
```
Calculate the factorial of -5
```

### 実行方法

```bash
# エラー処理シナリオを実行
uv run python simple_observability.py --scenario error

# またはエージェント ID を明示的に指定
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error
```

### 期待される動作

#### エージェント実行フロー
1. **入力処理**（0-2 秒）
   - エージェントがクエリを受信
   - calculator ツールが必要と識別
   - Braintrust で親スパンを作成

2. **ツール呼び出し試行**（2-5 秒）
   - calculate ツールを operation="factorial", x=-5 で呼び出し
   - ツール検証が無効な入力（負の数）を検出
   - ValueError を発生
   - 両システムでエラーをキャプチャ

3. **エラー記録**（5-6 秒）
   - Braintrust に記録:
     - スパンがエラーとしてマーク
     - エラータイプ: ValueError
     - エラーメッセージ: "Factorial is not defined for negative numbers"
     - スタックトレースをキャプチャ
   - CloudWatch に記録:
     - ErrorCount: 1
     - ErrorType ディメンション: ValueError
     - ToolCallFailure: 1

4. **エージェントリカバリ**（6-10 秒）
   - エージェントが操作が失敗した理由を説明しようと試みる可能性
   - ユーザーフレンドリーなエラーメッセージを返す
   - 分析用に合計トレースがログに記録

#### 期待されるコンソール出力
```
2025-10-25 12:05:00,p12345,{simple_observability.py:200},INFO,
Query: Calculate the factorial of -5
2025-10-25 12:05:00,p12345,{simple_observability.py:210},INFO,Processing query with agent...
2025-10-25 12:05:03,p12345,{simple_observability.py:250},INFO,Tool call: calculate
2025-10-25 12:05:03,p12345,{simple_observability.py:255},INFO,Tool input: {"operation": "factorial", "x": -5}
2025-10-25 12:05:03,p12345,{simple_observability.py:270},ERROR,Tool execution failed: Factorial is not defined for negative numbers
2025-10-25 12:05:05,p12345,{simple_observability.py:300},INFO,
Response: I apologize, but I cannot calculate the factorial of -5. The factorial function is only defined for non-negative integers.
2025-10-25 12:05:05,p12345,{simple_observability.py:305},INFO,Query completed in 5.3 seconds
2025-10-25 12:05:05,p12345,{simple_observability.py:320},INFO,Error metrics sent to CloudWatch
2025-10-25 12:05:05,p12345,{simple_observability.py:325},INFO,Error trace logged to Braintrust
```

#### 期待される CloudWatch メトリクス

CloudWatch はエラーシナリオを示すトレースを受信します：

**CloudWatch GenAI Observability/APM コンソールで：**
- エージェント呼び出し数がインクリメント
- 記録されるレイテンシ: 約 5-8 秒（エラーにより短い）
- 試行されたツール実行: calculator ツール
- トレースにエラーステータスが表示
- ツールが検証エラーで失敗

**エラー追跡：**
名前空間は `AWS/Bedrock-AgentCore` です。AgentCore Runtime は以下を記録します：
- エラーとなったリクエスト
- 失敗したリクエストのレイテンシ
- 失敗したツールとエラー詳細
- 失敗/エラーとしてマークされたステータス
- トレース属性に保存されたエラー詳細

エラー詳細はデバッグ用にトレーススパン属性にキャプチャされます。

#### 期待される Braintrust トレース
```
スパン階層:
└─ conversation_12346 [5.3s] [ERROR]
   ├─ model_call_1 [2.5s]
   │  └─ 入力: "Calculate the factorial of -5"
   │  └─ 出力: [calculate の tool_use ブロック]
   ├─ tool_calculate [0.2s] [ERROR]
   │  └─ 入力: {"operation": "factorial", "x": -5}
   │  └─ エラー: ValueError - Factorial is not defined for negative numbers
   │  └─ スタックトレース: [完全なトレース]
   └─ model_call_2 [1.5s]
      └─ 入力: [エラー結果]
      └─ 出力: "I apologize, but I cannot calculate the factorial of -5..."

メタデータ:
  - 総期間: 5.3s
  - ツール呼び出し: 1
  - ツール失敗: 1
  - エラータイプ: ValueError
  - 成功: false
```

### エラーログの表示

`check_logs.sh` スクリプトを使用してエラーメッセージを表示：

```bash
# 過去 15 分間の ERROR メッセージのみを表示
scripts/check_logs.sh --errors

# 過去 1 時間の ERROR メッセージのみを表示
scripts/check_logs.sh --time 1h --errors

# 過去 30 分間のすべてのログを表示（コンテキスト付きエラーを含む）
scripts/check_logs.sh --time 30m
```

**エラーログで表示される内容：**
- ログ出力の ERROR 重大度レベル
- ツールからの正確なエラーメッセージ
- エラータイプ（ValueError など）
- ファイルと行番号情報を含むスタックトレース
- 失敗のコンテキスト（試行された内容）
- エージェントがリカバリしてユーザーに応答した方法

### ハイライトするポイント
- ✓ 両システムでエラーをキャプチャ
- ✓ エラー詳細が保持（タイプ、メッセージ、スタックトレース）
- ✓ メトリクスが成功と失敗を区別
- ✓ エージェントがエラーを適切に処理
- ✓ check_logs.sh 経由でデバッグ用の完全なコンテキストが利用可能
- ✓ トラブルシューティング時にエラーのみを簡単にフィルタリング

### 時間見積もり
総デモンストレーション時間: 3-4 分
- 実行: 約 6 秒
- エラーメトリクスレビュー: 1-2 分
- トレース分析: 2 分

## シナリオ 3: ダッシュボードレビュー

### 目的
CloudWatch と Braintrust ダッシュボードを確認し、オブザーバビリティカバレッジを示します。CloudWatch は自動的なインフラストラクチャレベルのトレースを表示し、Braintrust はエージェントレベルの OTEL トレースを表示します（設定されている場合）。

### 実行方法

シナリオ 3 では、クエリを実行しません - ダッシュボードをナビゲートしてレビューします。ただし、データを生成するためにシナリオ 1 と 2 を先に実行しておく必要があります：

```bash
# まず、シナリオ 1 を実行して成功クエリトレースを生成
uv run python simple_observability.py --scenario success

# 次に、シナリオ 2 を実行してエラートレースを生成
uv run python simple_observability.py --scenario error

# シナリオ 3 は上記の実行からのデータを使用
uv run python simple_observability.py --scenario dashboard

# または 3 つのシナリオを順番に実行
uv run python simple_observability.py --scenario all
```

**クエリを実行した後**、以下に説明するようにダッシュボードをレビューする準備が整います。

### CloudWatch ダッシュボードレビュー

#### リクエストメトリクスウィジェット
**表示する内容：**
- 期間中の総リクエスト数
- 1 分あたりのリクエストレート
- 前期間との比較

**ポイント：**
- 「これはリクエストボリュームを示しています - キャパシティプランニングに有用です」
- 「リクエストスパイクとレイテンシの相関に注目してください」

#### レイテンシ分布ウィジェット
**表示する内容：**
- P50、P90、P99 レイテンシ
- 成功リクエストと失敗リクエストの比較
- ツール別レイテンシの内訳

**ポイント：**
- 「P99 レイテンシはユーザー体験にとって重要です」
- 「ツール呼び出しは測定可能なレイテンシを追加します - 内訳を参照」
- 「失敗したリクエストは通常より速く完了します（フェイルファストパターン）」

#### エラー率ウィジェット
**表示する内容：**
- 経時的なエラー率
- タイプ別エラー内訳
- 特定のツール呼び出しとの相関

**ポイント：**
- 「エラースパイクを素早く特定できます」
- 「エラータイプが根本原因の診断に役立ちます」
- 「5% しきい値でアラートシステムがトリガーされます」

#### トークン使用量ウィジェット
**表示する内容：**
- 入力トークン vs 出力トークン
- トークン消費レート
- コストへの影響

**ポイント：**
- 「API コストを直接確認できます」
- 「入力トークンには会話履歴が含まれます」
- 「プロンプトエンジニアリングの最適化に役立ちます」

#### 成功率ウィジェット
**表示する内容：**
- 全体的な成功率
- ツール別成功率
- 経時的なトレンド

**ポイント：**
- 「目標: 95% 以上の成功率」
- 「低下はシステムまたは統合の問題を示します」
- 「ツール別成功率が問題のある統合を特定するのに役立ちます」

#### 最近のトレースウィジェット
**表示する内容：**
- 最新のリクエストトレース
- 失敗リクエストへのクイックアクセス
- 詳細ログへのリンク

**ポイント：**
- 「最近のアクティビティへのクイックアクセス」
- 「失敗リクエストが即座に注目のためにハイライトされます」
- 「クリックして完全な CloudWatch Logs Insights に移動」

### Braintrust ダッシュボードレビュー

#### 実験概要
**表示する内容：**
- 実験リスト
- 実行履歴
- パフォーマンストレンド

**ポイント：**
- 「各実行が完全なコンテキストでキャプチャされます」
- 「コード変更間でパフォーマンスを比較」
- 「経時的な改善を追跡」

#### トレースエクスプローラー
**表示する内容：**
- 成功/失敗でフィルター
- 入力/出力コンテンツで検索
- 期間またはトークン数でソート

**ポイント：**
- 「デバッグ用の強力なフィルタリング」
- 「実際の会話コンテンツを検索」
- 「遅いまたは高コストのクエリを見つける」

#### スパンタイムラインビュー
**表示する内容：**
- 実行のウォーターフォールビュー
- 並列 vs 順次操作
- ボトルネックの特定

**ポイント：**
- 「実行フローの視覚的表現」
- 「最適化の機会を特定」
- 「各コンポーネントの正確なタイミングを確認」

#### コスト分析
**表示する内容：**
- リクエストごとのトークン使用量
- 会話ごとのコスト
- トレンド分析

**ポイント：**
- 「直接的なコスト可視性」
- 「高コストのクエリパターンを特定」
- 「コスト効率の最適化」

### 比較: CloudWatch vs Braintrust

#### CloudWatch の強み
- ✓ リアルタイムメトリクスとアラート
- ✓ AWS ネイティブ統合
- ✓ 集約された統計
- ✓ 運用ダッシュボード
- ✓ ログ相関

#### Braintrust の強み
- ✓ 詳細なトレース可視化
- ✓ 会話レベルの分析
- ✓ 開発ワークフロー統合
- ✓ A/B テストサポート
- ✓ リッチなフィルタリングと検索

#### 組み合わせて使用すると
- ✓ 完全なオブザーバビリティカバレッジ
- ✓ 運用（CloudWatch）+ 開発（Braintrust）
- ✓ メトリクス（CloudWatch）+ トレース（Braintrust）
- ✓ アラート（CloudWatch）+ デバッグ（Braintrust）

### 時間見積もり
総デモンストレーション時間: 8-12 分
- CloudWatch ダッシュボード: 4-6 分
- Braintrust ダッシュボード: 4-6 分
- 比較ディスカッション: 2-3 分

## 追加シナリオ（オプション）

### シナリオ 4: パフォーマンス最適化
**クエリ:** "What's the weather in Tokyo, London, Paris, and New York?"
**目的:** 複数のツール呼び出しと最適化の機会を示す

### シナリオ 5: 複雑な推論チェーン
**クエリ:** "Calculate 15 factorial, then find the square root of the result"
**目的:** 依存するツール呼び出しを伴う複数ステップの推論を示す

### シナリオ 6: レート制限
**クエリ:** 100 クエリを高速に実行
**目的:** スロットリングメトリクスとキュー動作を示す

## 一般的なデモ問題のトラブルシューティング

### 問題: CloudWatch にメトリクスが表示されない
**原因:** メトリクスバッファがフラッシュされていないか IAM 権限
**解決策:**
1. IAM ロールに `cloudwatch:PutMetricData` 権限があることを確認
2. 名前空間のスペルが正確に一致することを確認
3. メトリクスの伝播に 1-2 分待つ
4. CloudWatch Logs でエラーメッセージを確認

### 問題: Braintrust トレースが欠落
**原因:** API キーが設定されていないかネットワーク問題
**解決策:**
1. `BRAINTRUST_API_KEY` 環境変数を確認
2. インターネット接続を確認
3. コンソール出力でエラーメッセージを探す
4. Braintrust にプロジェクト名が存在することを確認

### 問題: ツール呼び出しが失敗
**原因:** ツール実装のバグまたは入力検証
**解決策:**
1. ツール入力形式がスキーマに一致することを確認
2. ログでエラーメッセージを確認
3. エージェントにツールが登録されていることを確認
4. ツールを独立してテスト

### 問題: レスポンス時間が遅い
**原因:** ネットワークレイテンシまたはモデル選択
**解決策:**
1. AWS リージョンが Amazon Bedrock モデルの可用性と一致することを確認
2. Amazon Bedrock へのネットワーク接続を確認
3. より高速なモデルバリアントの使用を検討
4. CloudWatch レイテンシの内訳を確認

## デモのベストプラクティス

### 準備
1. プレゼンテーション前にデモスクリプトを一度実行してウォームアップ
2. CloudWatch ダッシュボードを事前に作成
3. Braintrust 実験をクリアするか新規作成
4. AWS コンソールと Braintrust を別々のタブで開く
5. 問題発生時のバックアップクエリを準備

### デモ中
1. 各クエリを実行する前に何をするか説明
2. 出力が表示されたらキーポイントをハイライト
3. 両方のダッシュボードを使用して完全なストーリーを伝える
4. 特定のメトリクスとそのビジネス価値を指摘
5. シナリオ間で質問の時間を確保

### デモ後
1. ダッシュボードへのリンクを共有
2. 参加者が試せるサンプルクエリを提供
3. セットアップ用のドキュメントを参照
4. オブザーバビリティニーズに関するフィードバックを収集

## 期待されるメトリクスまとめ

### 成功クエリあたり
- リクエストレイテンシ: 10-20 秒
- ツール呼び出し: 1-3
- 入力トークン: 100-300
- 出力トークン: 50-150
- 成功率: 100%

### 失敗クエリあたり
- リクエストレイテンシ: 3-8 秒
- ツール呼び出し: 1-2
- エラー数: 1
- 成功率: 0%

### ダッシュボード更新頻度
- CloudWatch: 1 分間隔
- Braintrust: リアルタイム（非同期アップロード）
- ログエントリ: 即時

## プレゼンテーション準備

### デモ前チェックリスト

#### 環境セットアップ（デモの 30 分前）

- [ ] AWS 認証情報が設定されていることを確認
  ```bash
  aws sts get-caller-identity
  ```

- [ ] Amazon Bedrock モデルアクセスを確認
  ```bash
  aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?modelId==`us.anthropic.claude-haiku-4-5-20251001-v1:0`]'
  ```

- [ ] 環境変数を確認
  ```bash
  cat .env
  # 確認: AWS_REGION, BRAINTRUST_API_KEY, BRAINTRUST_PROJECT_ID
  ```

- [ ] スクリプト実行をテスト
  ```bash
  uv run python simple_observability.py --scenario success
  # ウォームアップのためにテストクエリを一度実行
  ```

- [ ] CloudWatch コンソールを開く
  - CloudWatch > GenAI Observability > Bedrock AgentCore に移動
  - "Agents" でメトリクスを表示
  - "Sessions" から "Traces" でトレースを表示

- [ ] Braintrust コンソールを開く
  - https://www.braintrust.dev/app に移動
  - "agentcore-observability-demo" プロジェクトを開く
  - トレースが表示されることを確認

- [ ] ブラウザタブを準備
  - タブ 1: デモディレクトリでターミナル
  - タブ 2: CloudWatch ダッシュボード
  - タブ 3: Braintrust プロジェクトビュー
  - タブ 4: このデモガイド（参照用）

#### コンテンツ準備

- [ ] このガイドの 3 つのシナリオすべてを確認
- [ ] バックアップクエリを準備（以下参照）
- [ ] すべてのサービスへのネットワーク接続をテスト
- [ ] 必要に応じて以前のデモデータをクリア（オプション）

### バックアップクエリ

プライマリデモクエリが失敗した場合、これらの代替を使用：

#### 成功クエリのバックアップ
1. "What's the weather in Tokyo?"
2. "Calculate 12 squared"
3. "What's 25 plus 17?"

#### エラークエリのバックアップ
1. "Calculate the square root of -1"
2. "What's the weather in zzz123?"（無効な場所）
3. "Calculate 10 divided by 0"

#### マルチツールのバックアップ
1. "What's the weather in London and calculate 144 divided by 12"
2. "Calculate the square root of 256 and tell me the weather in Paris"

### プレゼンテーションのヒント

#### ペース配分
- システムが応答する時間を確保（クエリあたり 10-15 秒）
- ダッシュボード説明を急がない
- シナリオ間で質問の時間を確保
- 総デモ時間を 45 分以内に収める

#### ナレーション
1. 各クエリを実行する前に何をするか説明
2. 出力が表示されたらキーポイントをハイライト
3. 両方のダッシュボードを使用して完全なストーリーを伝える
4. 特定のメトリクスとそのビジネス価値を指摘
5. シナリオ間で質問の時間を確保

#### ビジュアルフォーカス
- 大人数向けプレゼンテーションの場合はブラウザをズーム
- ブラウザズームを使用: Cmd/Ctrl + "+"
- カーソルで重要なセクションをハイライト
- 長いリストを表示する際はゆっくりスクロール

#### エンゲージメント
- 修辞的な質問をする: 「なぜ P99 レイテンシを気にするのでしょうか？」
- 聴衆のペインポイントに関連付ける
- 全体を通して質問を促す
- 機能をユースケースに結び付ける

#### リカバリ
- 何かが失敗しても落ち着いてバックアップクエリを使用
- 失敗を教育の機会に変える
- エラー処理機能を参照
- 問題が続く場合は次のシナリオに移動

### デモ成功チェックリスト

- [ ] マルチツールクエリを正常に実行
- [ ] CloudWatch トレース（自動）と Braintrust トレース（設定されている場合）を表示
- [ ] エラー処理をデモンストレーション
- [ ] 主要メトリクスとそのビジネス価値を説明
- [ ] 運用ワークフローと開発ワークフローを接続
- [ ] 聴衆の質問に回答
- [ ] 次のステップとリソースを提供
- [ ] フィードバックを収集

### デモ後
1. ダッシュボードへのリンクを共有
2. 参加者が試せるサンプルクエリを提供
3. セットアップ用のドキュメントを参照
4. オブザーバビリティニーズに関するフィードバックを収集
