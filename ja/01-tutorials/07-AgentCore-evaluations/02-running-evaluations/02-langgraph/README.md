# LangGraph での評価の実行

## 概要

このチュートリアルでは、[LangGraph](https://www.langchain.com/langgraph) を使用して構築されたエージェントで AgentCore Evaluations を使用する方法を示します。組み込みおよびカスタム評価者を使用して LangGraph エージェントのパフォーマンスを評価・監視するために、オンデマンドとオンライン評価の両方を実行する方法を学びます。

## 学習内容

- 特定の LangGraph エージェントトレースに対するオンデマンド評価の実行
- LangGraph エージェントの継続的な監視のためのオンライン評価のセットアップ
- AgentCore Starter Toolkit を使用した評価の管理
- エージェント品質を向上させるための評価結果の分析

## 前提条件

これらのチュートリアルを開始する前に、以下を確認してください：

- [チュートリアル 00: 前提条件](../../00-prereqs) を完了し、LangGraph エージェント（`eval_agent_langgraph.py`）を作成済み
- [チュートリアル 01: カスタム評価者の作成](../../01-creating-custom-evaluators) を完了し、カスタム評価者を作成済み
- LangGraph エージェントが AgentCore Runtime にデプロイ済み
- エージェントを呼び出してトレースを含む少なくとも1つのセッションを生成済み
- Python 3.10 以上がインストール済み
- 適切な権限で AWS 認証情報が設定済み

## チュートリアル構成

### [01-on-demand-eval.ipynb](01-on-demand-eval.ipynb)

**チュートリアルタイプ:** オンデマンド評価者（組み込みおよびカスタム）を使用した LangGraph エージェントの評価

**学習内容：**

- デプロイされた LangGraph エージェントからセッションとトレース情報を取得する方法
- Starter Toolkit を使用した AgentCore Evaluations クライアントの初期化
- 特定のトレースまたはセッションに対するオンデマンド評価の実行
- 組み込み評価者（例：`Builtin.Correctness`、`Builtin.Helpfulness`）とカスタム評価者の両方の使用
- スコア、説明、トークン使用量を含む評価結果の解釈

**主要概念：**

- **ターゲット評価**: セッションまたはトレース ID を提供して特定のインタラクションを評価
- **同期実行**: 評価リクエストに対して即座に結果を取得
- **柔軟な評価者選択**: 同じトレースに複数の評価者を適用
- **調査ツール**: 特定のインタラクションの分析や修正の検証に最適

### [02-online-eval.ipynb](02-online-eval.ipynb)

**チュートリアルタイプ:** オンライン評価者（組み込みおよびカスタム）を使用した LangGraph エージェントの評価

**学習内容：**

- LangGraph エージェント用のオンライン評価設定の作成
- サンプリングレートとフィルタリングルールの設定
- 組み込みおよびカスタム評価者を使用した継続的な評価のセットアップ
- CloudWatch ダッシュボードでの評価結果の監視
- オンライン評価設定の管理（有効化、無効化、更新、削除）

**主要概念：**

- **継続的な監視**: インタラクションが発生するたびにエージェントのパフォーマンスを自動評価
- **サンプリングベース**: パーセンテージベースのサンプリングを設定（例：セッションの10%を評価）
- **リアルタイムインサイト**: 品質トレンドを追跡し、リグレッションを早期に検出
- **本番対応**: 最小限のパフォーマンス影響でスケールに対応

## LangGraph エージェントアーキテクチャ

これらのチュートリアルで使用される LangGraph エージェントには以下が含まれます：

**ツール:**

- 基本的な計算用の Math ツール
- 天気情報用の Weather ツール

**モデル:**

- Amazon Bedrock の Anthropic Claude Haiku 4.5

**オブザーバビリティ:**

- AgentCore Runtime による自動 OTEL 計装
- CloudWatch GenAI Observability Dashboard でトレースが利用可能

## LangGraph エージェントでの評価の仕組み

1. **エージェント呼び出し**: LangGraph エージェントがユーザーリクエストを処理
2. **トレース生成**: AgentCore Observability が OTEL トレースを自動キャプチャ
3. **トレース保存**: トレースが CloudWatch Log グループに保存
4. **評価**:
   - **オンデマンド**: 評価する特定のセッション/トレースを選択
   - **オンライン**: 設定に基づいて AgentCore が自動的にサンプリングして評価
5. **結果分析**: CloudWatch でスコア、説明、トレンドを表示

## AgentCore Starter Toolkit の使用

両方のノートブックは、評価ワークフローを簡素化するために **AgentCore Starter Toolkit** を使用しています：

```python
from bedrock_agentcore_starter_toolkit import Evaluations

# 評価クライアントを初期化
evaluations = Evaluations()

# オンデマンド評価
result = evaluations.evaluate_session(
    session_id="your-session-id",
    evaluator_ids=["Builtin.Correctness", "your-custom-evaluator-id"]
)

# オンライン評価
config = evaluations.create_online_evaluation(
    config_name="your-config-name",
    sampling_percentage=100,
    evaluator_ids=["Builtin.Helpfulness", "your-custom-evaluator-id"]
)
```

## 期待される成果

これらのチュートリアルを完了すると、以下ができるようになります：

- オンデマンド評価を使用して特定の LangGraph エージェントインタラクションを評価
- 本番 LangGraph エージェントの継続的な品質監視をセットアップ
- 改善領域を特定するための評価結果の分析
- 組み込みおよびカスタム評価者を効果的に使用
- 時間の経過に伴うエージェント品質トレンドの監視

## 次のステップ

これらの LangGraph 固有のチュートリアルを完了した後：

- [Strands の例](../01-strands/) を探索して、異なるフレームワークでの評価の動作を確認
- [チュートリアル 03: 高度](../../03-advanced) に進んで高度な評価テクニックを学習
- CloudWatch GenAI Observability Dashboard で評価結果を確認
