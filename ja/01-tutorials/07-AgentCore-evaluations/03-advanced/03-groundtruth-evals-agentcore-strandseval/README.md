# オフラインマルチセッション評価

AgentCore Observability からの履歴トレースを使用して、デプロイされた AI エージェントセッションを評価します。このツールは、エージェントのオブザーバビリティログからトレースを取得し、Strands Evals 形式に変換し、評価を実行し、ダッシュボード相関のために元のトレース ID と共に結果を AgentCore Observability にログバックします。

## ユースケース

AgentCore Observability 計装でデプロイされた AI エージェントがある場合、このツールでは以下が可能です：

- 過去のエージェントインタラクションに対するオフライン評価の実行
- 更新されたルブリックで低スコアのセッションを再評価
- 既存のトレースに対して新しい評価者設定をテスト
- エージェントの出力を正解（SME からの期待される応答）と比較
- エージェントの変更が既知の良好な動作を壊さないことを確認するリグレッションテスト
- AgentCore Observability ダッシュボードで元のトレースと評価結果を相関

## 仕組み

1. **セッション発見**: 時間範囲または既存の評価スコアによって AgentCore Observability をクエリしてエージェントセッションを検索
2. **トレース取得**: CloudWatch Logs Insights を使用して各セッションのスパンを取得
3. **フォーマット変換**: AgentCore Observability スパンを Strands Evals Session 形式にマッピング（ツール呼び出し、エージェント応答、トラジェクトリ）
4. **評価**: 2つのアプローチのいずれかを使用して評価者を実行：
   - **ルブリックベース**: 定義した基準に対してスコアリング（柔軟、定性的）
   - **正解データ**: 期待される出力と比較（参照ベース、リグレッションテスト）
5. **結果ログ**: ダッシュボード相関のために元のトレース ID と共に EMF 形式で評価結果を送信

## ノートブックワークフロー

![ノートブックワークフロー](images/notebook_workflow.svg)

## エージェント評価の理解

エージェント評価は従来のソフトウェアテストを超えています。単体テストは決定論的な出力を検証しますが、エージェントは定性的な評価を必要とする可変的な応答を生成します。体系的な評価は、失敗パターンを特定し、時間の経過とともに改善を測定し、プロンプトやツールを反復する際に一貫した品質を確保するのに役立ちます。

### 2つの補完的なアプローチ

**AgentCore Evaluations** と **Strands Evals** は連携して、包括的なエージェント品質管理を提供します：

| | AgentCore Evaluations | Strands Evals |
|---|---|---|
| **目的** | 継続的なリアルタイム品質監視 | オフラインバッチ評価と実験 |
| **ユースケース** | 本番監視、品質低下時のアラート | テスト、リグレッション分析、ルブリック開発 |
| **実行** | フルマネージド、ライブインタラクションをサンプリング | オンデマンド、履歴トレースで実行 |
| **組み込み評価者** | 正確性、有用性、ツール選択精度、安全性、目標成功率、コンテキスト関連性 | 出力、トラジェクトリ、有用性、忠実性、目標成功率、ツール精度 |
| **カスタム評価者** | カスタムプロンプトによるモデルベースのスコアリング | 任意のコードベースまたは LLM ベースの評価者 |

**AgentCore Evaluations** は、実世界の動作に基づいてエージェントのパフォーマンスを継続的に監視するフルマネージドサービスです。ライブインタラクションをサンプリングし、組み込みまたはカスタム評価者に対してスコアリングし、オブザーバビリティインサイトと共に CloudWatch で結果を可視化します。満足度の低下や礼儀正しさのスコア低下など、品質メトリクスがしきい値を下回った場合にアラートを設定し、問題をより早く検出して対処します。

**Strands Evals** は、複数の評価タイプ、マルチターン会話用の動的シミュレータ、OpenTelemetry によるトレースベース評価、自動実験生成、および任意のライブラリからのカスタム評価者をサポートする拡張可能なアーキテクチャを提供する包括的な評価フレームワークです。完全な機能については [Strands Evals ドキュメント](https://strandsagents.com/latest/documentation/docs/user-guide/evals-sdk/quickstart/) を参照してください。

### このプロジェクト

このプロジェクトは、**AgentCore Observability** によって収集されたトレースの **Strands Evals によるオフライン評価** を使用し、2つの一般的なパターンを示しています：

- **出力品質**: エージェントの応答はユーザーのリクエストに正しく完全に対応していますか？どのように生成されたかに関係なく、最終的な回答を評価します。

- **トラジェクトリ品質**: エージェントはツールを効果的に使用しましたか？エージェントが適切なツールを選択し、効率的に使用し、論理的なシーケンスに従ったかを評価します。

結果は元のトレース ID と共に AgentCore Observability にログバックされ、AgentCore Evaluations の結果と共にダッシュボードで相関が可能になります。

## Strands Evals の概念

このツールは、AI エージェント用の汎用評価フレームワークである [Strands Evals](https://github.com/strands-agents/strands-evals) を使用しています。Strands Evals は、人間が定義した基準に対してエージェントの動作をスコアリングするために LLM をジャッジとして使用します。フレームワークは、エージェント応答の固有の変動性を、説明付きの 0.0 から 1.0 のスケールで品質を定量化することで処理します。

**主要なインサイト**: エージェントは「正しい」または「間違った」回答を生成するのではなく、より良いまたはより悪い応答を生成します。Strands Evals は主観的な品質評価を測定可能で一貫したメトリクスに変換します。

コア概念を理解することで、評価を効果的にカスタマイズできます。

**Session**: 潜在的に複数の往復のやり取りを含む完全なユーザー会話を表します。AgentCore Observability では、セッションは `session.id` によって関連するインタラクションをグループ化します。

**Trace**: 単一のユーザーリクエストとエージェントの完全な応答（そのリクエストを満たすために行われたすべてのツール呼び出しを含む）。各トレースには AgentCore Observability と相関する一意の `trace_id` があります。

**Case**: 入力（ユーザープロンプト）、実際の出力（エージェント応答）、およびメタデータ（trace_id、ツールトラジェクトリ）を含む評価用のテストケース。ケースは評価者がスコアリングするものです。

**Experiment**: 1つ以上の評価者とペアになったケースのコレクション。実験を実行すると、各ケースのスコアと説明が生成されます。

## 評価アプローチ

Strands Evals は、複数の評価アプローチをサポートする拡張可能な LLM ベースの評価フレームワークです。正確な文字列マッチングではなく、LLM をジャッジとして使用してエージェントの出力をスコアリングします。フレームワークは柔軟性を重視して設計されており、事実上あらゆる評価タイプを実装できます。

**2つの基本的な評価アプローチ：**

| アプローチ | 説明 | 使用タイミング |
|----------|-------------|----------|
| **ルブリックベース** | 定義した基準に対して LLM がジャッジ | 柔軟な定性評価が必要な場合 |
| **正解データ** | 既知の正しい回答と比較 | 測定対象となる期待される出力がある場合 |

このプロジェクトでは、両方のアプローチを別々のノートブックで示しています。

### ルブリックベース評価（ノートブック 02）

ルブリックで評価基準を定義し、LLM が各応答を基準に対してジャッジします。このアプローチは、応答が異なっても「良い」場合に最適です。

**OutputEvaluator**: エージェントの応答の品質を評価します。良い応答とは何か（関連性、正確性、完全性）を説明するルブリックを提供し、評価者は LLM を使用して 0.0 から 1.0 の出力をスコアリングし、説明を付けます。

**TrajectoryEvaluator**: エージェントがツールをどのように使用したかを評価します。良いツール使用パターン（適切な選択、効率性、論理的なシーケンス）を説明するルブリックを提供し、評価者はツールトラジェクトリを 0.0 から 1.0 でスコアリングします。

### 正解データ評価（ノートブック 03）

実際のエージェント出力を事前定義された期待される応答と比較します。このアプローチは、リグレッションテスト、ベンチマーキング、および既知の正しい回答がある場合に最適です。

評価者は実際と期待を比較し、エージェントの出力が Subject Matter Expert（SME）が正しい応答として定義したものとどれだけ一致するかをスコアリングします。詳細は [正解データ評価](#正解データ評価) セクションを参照してください。

### 拡張性

Strands Evals フレームワークは、このプロジェクトで示されている以上のカスタム評価者をサポートしています。スコアリング基準として表現できる任意の評価（事実の正確性、安全性、ドメイン固有の品質チェック、コンプライアンス要件）は、LLM-as-judge アプローチを使用して実装できます。

**ルブリックの仕組み**: ルブリックはエージェントの出力と共に LLM に送信されます。LLM はジャッジとして機能し、基準を適用してスコアと説明を生成します。明確なスコアリングガイダンスを持つ適切に書かれたルブリックは、より一貫した評価を生成します。

## 正解データ評価

正解データ評価は、エージェントの出力を事前定義された期待される応答と比較します。これは、特定のクエリに対して既知の正しい回答があり、エージェントがそれらにどれだけ近いかを測定したい場合に便利です。

![正解データフロー](images/ground_truth_flow.svg)

**主要概念：**
- **session_id**: 単一のユーザーセッションからのすべてのトレースをグループ化
- **trace_id**: セッション内の各個別のインタラクション（ユーザープロンプト + エージェント応答）を識別

**2ファイルアプローチ**: 正解データノートブックは同じ `session_id` を共有する2つのファイルを使用します：

1. **トレースファイル**（`demo_traces.json`）: CloudWatch からの実際のエージェント出力を含む
   ```json
   {
     "session_id": "5B467129-E54A-4F70-908D-CB31818004B5",
     "traces": [
       {
         "trace_id": "693cb6c4e931",
         "user_prompt": "What is the best route for a NZ road trip?",
         "actual_output": "Based on the search results...",
         "actual_trajectory": ["web_search"]
       },
       {
         "trace_id": "693cb6fa87aa",
         "user_prompt": "Should I visit North or South Island?",
         "actual_output": "Here's how the islands compare...",
         "actual_trajectory": ["web_search"]
       }
     ]
   }
   ```

2. **正解データファイル**（`demo_ground_truth.json`）: SME が作成した期待される出力
   ```json
   {
     "session_id": "5B467129-E54A-4F70-908D-CB31818004B5",
     "ground_truth": [
       {
         "trace_id": "693cb6c4e931",
         "expected_output": "Response should mention Milford Road, Southern Scenic Route...",
         "expected_trajectory": ["web_search"]
       },
       {
         "trace_id": "693cb6fa87aa",
         "expected_output": "Response should compare both islands...",
         "expected_trajectory": ["web_search"]
       }
     ]
   }
   ```

**仕組み：**
1. ノートブックが CloudWatch からトレースを取得（またはデモファイルをロード）
2. SME が各 `trace_id` の期待される出力を含む正解データファイルを作成
3. ノートブックが `trace_id` でマージし、実際と期待をペアリング
4. 評価者が各ペアをスコアリング

**デモモード**: 独自の CloudWatch データに接続する前に、提供されたサンプルファイルを使用してテストするには `USE_DEMO_MODE = True` で実行します。

## データフロー

評価パイプラインは AgentCore Observability トレースをスコアリングされた結果に変換します：

![評価パイプライン](images/evaluation_pipeline.svg)

## プロジェクト構造

```
01_session_discovery.ipynb        - ノートブック 1: セッション発見
02_multi_session_analysis.ipynb   - ノートブック 2: カスタムルブリックで評価
03_ground_truth_evaluation.ipynb  - ノートブック 3: 正解データに対して評価
demo_traces.json                  - サンプルトレースデータ（デモモード用）
demo_ground_truth.json            - サンプル正解データ期待値（デモモード用）
config.py                         - 集中設定
requirements.txt                  - Python 依存関係
utils/
  __init__.py                     - モジュールエクスポート
  cloudwatch_client.py            - CloudWatch Logs Insights クエリクライアント
  constants.py                    - 定数と評価者設定
  evaluation_cloudwatch_logger.py - 元のトレース ID を保持する EMF ロガー
  models.py                       - データモデル（Span、TraceData、SessionInfo）
  session_mapper.py               - AgentCore Observability スパンから Strands Evals Session へのマッパー
```

## クイックスタート

### 1. 設定

`config.py` を AWS 設定で編集：

```python
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "123456789012"
SOURCE_LOG_GROUP = "your-agent-log-group"
EVAL_RESULTS_LOG_GROUP = "your-eval-log-group"
EVALUATION_CONFIG_ID = "your-evaluation-config-id"
SERVICE_NAME = "your-service-name"
```

### 2. セッション発見

`01_session_discovery.ipynb` を実行：
- 時間ベースの発見（時間ウィンドウ内のすべてのセッション）またはスコアベースの発見（評価スコアによるセッション）を選択
- 発見されたセッションをプレビュー
- 評価ノートブック用に JSON に保存

### 3. セッション評価（1つのパスを選択）

**オプション A: カスタムルブリック** - `02_multi_session_analysis.ipynb` を実行：
- 発見されたセッションをロード（またはカスタムセッション ID を提供）
- ユースケースに合わせて評価者ルブリックをカスタマイズ
- 評価を実行して結果を表示
- 結果は元のトレース ID と共に AgentCore Observability にログ

**オプション B: 正解データ** - `03_ground_truth_evaluation.ipynb` を実行：
- エージェント出力を事前定義された期待される応答と比較
- 評価対象となる既知の正しい回答がある場合に便利
- サンプルファイル（`demo_traces.json`、`demo_ground_truth.json`）を使用したデモモードをサポート
- `trace_id` でトレースを正解データとマージ

## 設定リファレンス

すべての設定は `config.py` にあります。値を直接編集してください。

| 変数 | 説明 |
|----------|-------------|
| `AWS_REGION` | AWS リージョン（例：us-east-1） |
| `AWS_ACCOUNT_ID` | AWS アカウント ID |
| `SOURCE_LOG_GROUP` | AgentCore Observability ロググループ名 |
| `EVAL_RESULTS_LOG_GROUP` | 評価結果ロググループ名 |
| `EVALUATION_CONFIG_ID` | AgentCore Observability 評価設定 ID |
| `SERVICE_NAME` | CloudWatch ログ用のサービス名 |
| `EVALUATOR_NAME` | スコアベース発見用の評価者名 |
| `LOOKBACK_HOURS` | セッションを検索する時間数（デフォルト：72） |
| `MAX_SESSIONS` | 発見する最大セッション数（デフォルト：100） |
| `MIN_SCORE` / `MAX_SCORE` | スコアベース発見用のスコアフィルター |
| `MAX_CASES_PER_SESSION` | セッションごとに評価する最大トレース数（デフォルト：10） |

## カスタマイズ

### 評価者ルブリック

分析ノートブックで、評価基準に合わせてルブリックをカスタマイズ：

```python
output_rubric = """
以下に基づいてエージェントの応答を評価：
1. 関連性: ユーザーの質問に対応していますか？
2. 正確性: 情報は正しいですか？
...
"""
```

### 評価者名

CloudWatch メトリクス用のカスタム評価者名を設定：

```python
OUTPUT_EVALUATOR_NAME = "Custom.YourOutputEvaluator"
TRAJECTORY_EVALUATOR_NAME = "Custom.YourTrajectoryEvaluator"
```

### 評価設定 ID

`config.py` で AgentCore Observability 評価設定に一致する評価設定 ID を設定：

```python
EVALUATION_CONFIG_ID = "your-evaluation-config-id"
```

## 要件

- Python 3.9 以上
- CloudWatch Logs アクセス権を持つ AWS 認証情報
- `strands-evals` パッケージ
- `boto3`
