# Braintrust セットアップガイド

## 概要

このガイドでは、Simple Dual Observability チュートリアル用の Braintrust 統合を設定する手順を提供します。Braintrust は OpenTelemetry トレースをネイティブに受信し、エージェント実行データを探索するためのダッシュボードを提供します。

Braintrust の機能に関する包括的な情報については、[Braintrust ドキュメント](https://docs.braintrust.dev) を参照してください。

## 前提条件

Braintrust をセットアップする前に：

1. アカウント作成用のメールアドレス
2. Braintrust Web UI へのブラウザアクセス
3. OTEL コレクター設定（チュートリアルに含まれています）

## アカウント作成

### ステップ 1: 無料アカウントにサインアップ

1. https://www.braintrust.dev/signup に移動
2. 以下を使用してサインアップ：
   - メールアドレスとパスワード
   - Google アカウント（SSO）
   - GitHub アカウント（SSO）
3. メールアドレスを確認（メールサインアップを使用した場合）

### ステップ 2: ダッシュボードにアクセス

サインアップ後：

1. https://www.braintrust.dev/app にログイン
2. メインダッシュボードが表示されます
3. 「Create Project」をクリックして開始

## API キー管理

### API キーの生成

1. Settings に移動: https://www.braintrust.dev/app/settings/api
2. 「Create API Key」をクリック
3. 名前を入力: 「AgentCore-Observability-Demo」
4. 権限を選択：
   - トレースへの読み取り/書き込みアクセス
   - プロジェクトへの読み取りアクセス
5. 「Generate」をクリック
6. **API キーをすぐにコピーして保存**（一度だけ表示されます）

**API キーの形式**: `bt-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### API キーを安全に保存

**オプション 1: 環境変数**

```bash
# .env ファイルに追加
echo "BRAINTRUST_API_KEY=bt-xxxxx" >> .env

# または直接エクスポート
export BRAINTRUST_API_KEY=bt-xxxxx
```

**オプション 2: 自動設定**

`BRAINTRUST_API_KEY` を設定してエージェントをデプロイすると、Strands テレメトリライブラリは環境変数から API キーを使用して、Braintrust のエンドポイント（https://api.braintrust.dev/otel）への OTLP エクスポートを自動的に設定します。

**セキュリティのベストプラクティス**：
- API キーを git にコミットしない
- 環境変数またはシークレット管理を使用
- キーを定期的にローテーション
- 開発/本番用に別のキーを使用

### API キーの取り消し

キーが侵害された場合：

1. Settings > API Keys に移動
2. 名前または部分的な値でキーを見つける
3. 「Revoke」をクリック
4. 新しいキーを生成して設定を更新

## プロジェクトセットアップ

### プロジェクトの作成

1. ダッシュボードから「Create Project」をクリック
2. プロジェクト名: `agentcore-observability-demo`
3. 説明: 「Amazon Bedrock AgentCore 用のシンプルなデュアルオブザーバビリティチュートリアル」
4. 「Create」をクリック

### プロジェクト設定の構成

1. プロジェクト設定（歯車アイコン）に移動
2. 保持期間を設定：
   - 無料プラン: 7 日間（デフォルト）
   - 有料プラン: 30 日以上（オプションでアップグレード）
3. プロジェクトメタデータを設定：
   - Environment: development
   - Owner: あなたのメールアドレス
   - Tags: agentcore, tutorial, observability

### 機能の有効化

強化されたオブザーバビリティのためにオプション機能を有効化：

1. **Evaluations**: 自動品質チェック
2. **Datasets**: 比較用のテストデータを保存
3. **Experiments**: プロンプトの A/B テスト
4. **Monitoring**: リアルタイムアラート（有料機能）

## テレメトリ設定

### 自動 OTEL エクスポート

エージェントは OTLP エクスポート設定を自動的に構成する Strands テレメトリライブラリを使用します：

```python
# weather_time_agent.py 内
strands_telemetry = StrandsTelemetry()
strands_telemetry.setup_otlp_exporter()
```

OTLP エクスポーターは以下で自動的に設定されます：
- **エンドポイント**: `https://api.braintrust.dev/otel`（BRAINTRUST_API_KEY が設定されている場合）
- **認証**: 環境から BRAINTRUST_API_KEY を使用
- **リトライ**: 指数バックオフによる自動リトライ
- **圧縮**: 効率のための gzip 圧縮
- **バッチ処理**: パフォーマンス向上のための自動スパンバッチ処理

静的な YAML 設定ファイルは不要です。すべての設定は環境変数で駆動されます。

### 設定の確認

エージェントを実行してダッシュボードを確認し、Braintrust への OTEL エクスポートをテスト：

```bash
# API キーを設定（形式: bt-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx）
export BRAINTRUST_API_KEY=bt-xxxxx

# エージェントテストを実行してトレースを生成
# BRAINTRUST_API_KEY が設定されている場合、エージェントは自動的に Braintrust への OTLP エクスポートを設定
uv run python scripts/tests/test_agent.py --test weather

# トレースが Braintrust ダッシュボードに表示されることを確認
# https://www.braintrust.dev/app に移動
# トレースは 1〜2 分以内に表示されます
```

接続の確認に関する詳細については、[Braintrust API ドキュメント](https://docs.braintrust.dev/reference/api) を参照してください。

## ダッシュボード設定

### プロジェクトダッシュボードにアクセス

1. https://www.braintrust.dev/app に移動
2. プロジェクトを選択: `agentcore-observability-demo`
3. 複数のタブとビューが表示されます：
   - **Logs**: コストと期間を含むすべての呼び出しを表示
   - **Traces**: スパン階層とタイミングを含む詳細なトレースツリービュー

### ダッシュボードの理解

**Traces タブ**:
- 受信したすべてのトレースを一覧表示
- トレース ID、セッション ID、または属性で検索
- 時間範囲、ステータス、またはカスタムフィールドでフィルタリング
- レイテンシ、コスト、またはタイムスタンプでソート

**表示される主要メトリクス**:
- 受信した総トレース数
- 平均レイテンシ
- トークン使用量（入力/出力）
- 推定コスト
- エラー率

### トレースの表示

デモ実行後、トレースは自動的に表示されます：

1. Traces タブに移動
2. ID でトレースを検索（デモスクリプトで出力）
3. トレースをクリックして詳細ビューを開く

**トレース詳細ビューに表示される内容**:
- タイムライン可視化
- スパン階層
- スパンごとのトークン消費
- コスト内訳
- カスタム属性
- エラー詳細（ある場合）

### 検索とフィルター

**トレース ID で検索**:
```
trace_id = "1-67891011-abcdef1234567890"
```

**セッションで検索**:
```
session_id = "demo_session_abc123"
```

**モデルで検索**:
```
model_id CONTAINS "haiku"
```

**時間範囲でフィルター**:
- 過去 5 分
- 過去 1 時間
- 過去 24 時間
- カスタム範囲

**ステータスでフィルター**:
- 成功のみ
- エラーのみ
- すべてのステータス

### カスタムビュー

特定のユースケース用にカスタムビューを作成：

1. 「Create View」をクリック
2. 名前: 「High Latency Traces」
3. フィルター: `latency_ms > 2000`
4. ビューを保存
5. チームと共有（オプション）

## トレース可視化

### タイムラインビュー

タイムラインに表示される内容：
- 相対的なタイミングを示すスパン期間の水平バー
- 親子関係を示すスパン階層：
  - ルートスパン: `invoke_agent`（Strands Agents）
  - 子スパン: `execute_event_loop_cycle`、ツール実行など
  - リーフスパン: 個別の操作（例: `calculator`、`get_weather`）
- スパンタイプを示す色分けとアイコン
- 開始時間と期間を示すタイミング情報
- 任意のスパンをクリックして詳細な属性とタイミングを表示

**ダッシュボードの例**:

![エージェントトレース付き Braintrust ダッシュボード](img/bt.png)

スクリーンショットに表示される内容：
- 左パネル: メトリクス（コスト、期間、トークン）を含む呼び出しログ一覧
- 中央: トレース検索とフィルタリングインターフェース
- 右: スパン階層と実行タイムラインを示すトレースツリービュー
- メトリクスパネル: トークン数、コスト見積もり、パフォーマンスメトリクス

### トークン使用量ビュー

トークン消費を表示：
- スパンごとの入力トークン
- スパンごとの出力トークン
- トレースの総トークン
- 経時的なトークン使用量（ダッシュボード）

コスト分析およびその他の Braintrust 機能については、[Braintrust ドキュメント](https://docs.braintrust.dev) を参照してください。

## チュートリアルとの統合

### 自動セットアップ

チュートリアルは自動化された Braintrust セットアップを提供します：

```bash
cd scripts
./setup_braintrust.sh --api-key bt-xxxxx
```

このスクリプトは以下を実行します：
1. API キーを確認
2. プロジェクトが存在しない場合は作成
3. OTEL コレクターを設定
4. トレースエクスポートをテスト
5. 使用ガイドを生成

### 手動統合

手動でセットアップする場合：

```bash
# 1. API キーを設定
export BRAINTRUST_API_KEY=bt-xxxxx

# 2. API キーでエージェントをデプロイ
# エージェントは環境から BRAINTRUST_API_KEY を自動的に使用
scripts/deploy_agent.sh

# 3. デモを実行
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all

# 4. Braintrust ダッシュボードでトレースを表示
# https://www.braintrust.dev/app/projects/agentcore-observability-demo/traces
```

## トラブルシューティング

### API キーの問題

**問題**: 401 Unauthorized エラー

**解決策**:
1. API キーが正しいことを確認
2. キーが取り消されていないことを確認
3. キーに適切な権限があることを確認
4. 必要に応じてキーを再生成

### トレースが表示されない

**問題**: Braintrust ダッシュボードにトレースがない

**解決策**:
1. API キーが設定され、正しい形式であることを確認: `echo $BRAINTRUST_API_KEY`（`bt-` で始まる必要があります）
2. Braintrust のプロジェクト名が一致することを確認: `agentcore-observability-demo`
3. braintrust.dev へのネットワーク接続を確認: `curl -I https://api.braintrust.dev/otel`
4. テレメトリの初期化についてエージェントログを確認: `uv run python -m weather_time_agent 2>&1 | grep -i telemetry`
5. トレースが表示されるまで 1〜2 分待つ（バッチ処理）

### 不完全なトレースデータ

**問題**: トレースにスパンや属性が欠けている

**解決策**:
1. エージェントコードがすべての操作を計装していることを確認
2. 属性サイズ制限を確認（それぞれ最大 1000 文字）
3. ログにスパンコンテキストが含まれていることを確認
4. テレメトリエラーについてエージェントログを確認: `grep -i "telemetry\|span" agent.log`

### 高レイテンシ

**問題**: Braintrust へのトレースエクスポートが遅いか、エージェント実行時間が長い

**解決策**:
1. Braintrust API へのネットワークレイテンシを確認: `curl -w "@curl-format.txt" https://api.braintrust.dev/otel`
2. エージェントコードにブロッキング操作がないことを確認
3. 長時間実行されるスパンについてエージェントログを確認
4. ボリュームが高い場合はアプリケーションレベルでサンプリングまたはバッチ処理を検討

## 確認

セットアップ後、Braintrust 統合を確認：

```bash
# 1. エージェントテストを実行してトレースを生成
uv run python scripts/tests/test_agent.py --test weather

# 期待: エージェントがエラーなしで正常に実行
```

その後、Braintrust ダッシュボードで確認：

1. https://www.braintrust.dev/app に移動
2. プロジェクトを選択: `agentcore-observability-demo`
3. Traces タブに移動
4. 最近のトレースを探す（1〜2 分以内に表示されます）
5. トレースをクリックして表示：
   - スパンのタイムライン可視化
   - 各スパンの入力/出力トークン
   - エージェント実行フロー

トレースが表示されない場合：
- `BRAINTRUST_API_KEY` が正しく設定されていることを確認（形式: `bt-xxxxxxx...`）
- エージェントが API キー環境変数でデプロイされたことを確認
- テレメトリ初期化メッセージについてエージェントログを確認
- 詳細なデバッグ手順については [トラブルシューティングガイド](troubleshooting.md) を参照

## 次のステップ

Braintrust セットアップ後：

1. デモシナリオを実行してトレースを探索
2. 一般的な問題については [トラブルシューティングガイド](troubleshooting.md) を確認
3. 高度な機能とベストプラクティスについては [Braintrust ドキュメント](https://docs.braintrust.dev) を参照
