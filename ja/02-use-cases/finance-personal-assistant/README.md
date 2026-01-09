# エージェント戦略を使用して複雑なビジネスタスクを効率化

この[ワークショップ](https://catalog.us-east-1.prod.workshops.aws/workshops/57f577e3-9a24-45e2-9937-e48b2cdf6986/en-US)は、[Amazon Bedrock](https://aws.amazon.com/bedrock)、[Strands Agents](https://strandsagents.com/latest/)、[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) などの最先端テクノロジーを使用して、高度でコンテキスト対応の AI エージェントを構築するための実践的なトレーニングプログラムです。

![architecture](./images/architecture.png)

私たちは、インテリジェントなオーケストレーションを通じて専門分野を組み合わせる**マルチエージェント金融アドバイザリーシステム**を作成しています。このシステムは、専門家がコーディネーターの下で協力して包括的なガイダンスを提供する、プロフェッショナルな金融アドバイザリー会社の運営方法を模倣しています。

私たちのマルチエージェントシステムは3つのコアコンポーネントで構成されています：

1. **Budget Agent（[Lab 1](./lab1-develop_a_personal_budget_assistant_strands_agent.ipynb) より）**

    *個人の予算管理、支出分析、財務規律を専門としています*

    | ツール | 説明 | 使用例 |
    |------|-------------|------------------|
    | **calculate_budget_breakdown** | あらゆる収入レベルに対する 50/30/20 予算計算 | 「月収 $6000 の予算を作成して」 |
    | **analyze_spending_pattern** | 支出パターン分析とパーソナライズされた推奨 | 「収入 $5000 に対して $800 の外食費を分析して」 |
    | **calculator** | 財務計算と数学的操作 | 「予算の 20% 貯蓄目標を計算して」 |

2. **Financial Analysis Agent（[Lab 2](./lab2-build_multi_agent_workflows_with_strands.ipynb) より）**

    *投資リサーチ、ポートフォリオ管理、市場分析に焦点を当てています*

    | ツール | 説明 | 使用例 |
    |------|-------------|------------------|
    | **get_stock_analysis** | リアルタイム株式データと包括的な分析 | 「Apple 株のパフォーマンスと指標を分析して」 |
    | **create_diversified_portfolio** | リスクベースのポートフォリオ推奨と配分 | 「$10,000 で中リスクのポートフォリオを作成して」 |
    | **compare_stock_performance** | 期間にわたる複数株式のパフォーマンス比較 | 「6ヶ月間で Tesla、Apple、Google を比較して」 |

3. **Orchestrator Agent（[Lab 2](./lab2-build_multi_agent_workflows_with_strands.ipynb) より）**

    *専門エージェントを調整し、包括的な回答を合成します*

    | 機能 | 説明 | 使用例 |
    |------------|-------------|------------------|
    | **Agent Routing** | どの専門家に相談するかをインテリジェントに判断 | 予算の質問は Budget Agent に、投資クエリは Financial Agent にルーティング |
    | **Multi-Agent Coordination** | 複雑なクエリに対して複数エージェントからの洞察を組み合わせ | 「予算と投資を手伝って」は両方のエージェントを一緒に使用 |
    | **Response Synthesis** | 複数エージェントの出力から一貫した回答を作成 | 予算分析と投資推奨を組み合わせ |
    | **Context Management** | エージェント間のやり取りで会話の流れを維持 | フォローアップの推奨時に以前のアドバイスを記憶 |

## ワークショップ構成

| Lab | 焦点 | 所要時間 | 学習内容 |
|-----|-------|----------|-------------------|
| 前提条件 | 環境セットアップ | 5 分 | AWS アカウントセットアップ、SageMaker Studio 設定 |
| [Lab 1](./lab1-develop_a_personal_budget_assistant_strands_agent.ipynb) | パーソナルファイナンスアシスタント | 20 分 | 最初の Strands エージェントを構築、コアコンセプトを理解、カスタムツールを作成 |
| [Lab 2](./lab2-build_multi_agent_workflows_with_strands.ipynb)| マルチエージェントワークフロー | 20 分 | マルチエージェントワークフローを実装 |
| [Lab 3](./lab3-deploy_agents_on_amazon_bedrock_agentcore.ipynb) | 本番デプロイ | 15 分 | Amazon Bedrock AgentCore を使用してエージェントをデプロイ、スケーリングとモニタリング |

**合計所要時間:** 1 時間

## 前提条件

参加者は以下を準備してください：

- Amazon Bedrock アクセス用に設定された AWS 認証情報
- 開発マシンに Python 3.8+ がインストール済み
- Amazon Bedrock アクセス権を持つ AWS アカウント。AWS 主催のイベントでは、プロビジョニングされたアカウントが提供されます
- Amazon Bedrock で Anthropic Claude 3.7 Sonnet の[モデルアクセス](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html)を有効化
- Jupyter Notebook または互換性のある IDE

## サンプルクエリ

- 「月収 $6000 で毎月 $500 の投資を始めたいです。予算を作成し、投資ポートフォリオを提案してください。」
- 「外食に使いすぎています（月 $800）。節約分を投資したいです。どうすればいいですか？」
- 「Tesla と Apple 株を比較し、月収 $4000 で $2000 の投資が可能か教えてください。」

## クリーンアップ

各 Lab には Jupyter ノートブックの最後にクリーンアップ手順が含まれています。デフォルトでは、これらのクリーンアップ手順はコメントアウトされています。ワークショップの終了時にリソースをクリーンアップするには、コメントを解除して実行してください。
