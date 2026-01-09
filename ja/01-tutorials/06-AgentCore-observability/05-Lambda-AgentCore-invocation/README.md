# CloudWatch オブザーバビリティを備えた Lambda AgentCore 呼び出し

このチュートリアルでは、完全な CloudWatch Gen AI Observability を有効にした状態で、AWS Lambda 関数から Amazon Bedrock AgentCore Runtime でホストされた Strands エージェントを呼び出す方法を示します。

## 概要

Lambda 関数が AgentCore Runtime で実行される MCP 対応エージェントを呼び出すサーバーレスアーキテクチャの構築方法を学びます。CloudWatch を通じて Lambda 実行とエージェント動作の両方を完全に可視化できます。

## プロジェクト構成
```
05-Lambda-AgentCore-invocation/
├── agentcore_observability_lambda.ipynb  # メインチュートリアルノートブック
├── lambda_agentcore_invoker.py           # Lambda 関数コード
├── mcp_agent_multi_server.py             # 複数の MCP サーバーを持つエージェント
├── requirements.txt                      # Python 依存関係
├── .gitignore                            # Git 無視パターン
└── README.md                             # このファイル

注：Dockerfile はノートブック内で動的に生成され、git では追跡されません。
```

## チュートリアル詳細

| 情報              | 詳細                                                                              |
|:-----------------|:----------------------------------------------------------------------------------|
| チュートリアルタイプ | 会話型                                                                            |
| エージェントタイプ   | シングル                                                                          |
| エージェントフレームワーク | Strands Agents                                                              |
| LLM モデル         | Anthropic Claude Haiku 4.5                                                       |
| チュートリアルコンポーネント | Lambda 呼び出し、AgentCore Runtime、MCP サーバー、CloudWatch Observability |
| サンプル複雑度      | 上級                                                                              |
| 使用 SDK          | Amazon BedrockAgentCore Python SDK、boto3、AWS Lambda                            |

## アーキテクチャ
```
┌─────────┐      ┌────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   API   │─────>│  AWS Lambda    │─────>│  AgentCore       │─────>│  Strands Agent  │
│  /User  │      │  (Invoker)     │      │  Runtime         │      │  + MCP Servers  │
└─────────┘      └────────────────┘      └──────────────────┘      └─────────────────┘
                        │                         │                          │
                        ▼                         ▼                          ▼
                 ┌─────────────────────────────────────────────────────────────┐
                 │            CloudWatch Observability                         │
                 │       • Gen AI Traces     • Metrics     • Logs              │
                 └─────────────────────────────────────────────────────────────┘
```

## 主な機能

* Strands Agents との複数の MCP サーバー（AWS Documentation + AWS CDK）の統合
* Amazon Bedrock AgentCore Runtime でのエージェントホスティング
* AWS Lambda 関数からのホステッドエージェント呼び出し
* 包括的なエージェントモニタリングのための CloudWatch Gen AI Observability の設定
* CloudWatch コンソールでのトレース、スパン、メトリクスの表示

## 学習内容

1. MCP 対応エージェントを AgentCore Runtime にデプロイする方法
2. Runtime エージェントを呼び出す Lambda 関数を作成する方法
3. エージェントの CloudWatch Gen AI Observability を有効化する方法
4. エージェント実行フローを示すトレースを表示・分析する方法

## 前提条件

* Python 3.10 以上
* 適切な権限で設定された AWS 認証情報
* Amazon Bedrock AgentCore SDK
* Lambda 関数と IAM ロールを作成する権限
* CloudWatch Transaction Search が有効化済み（セットアップ手順はチュートリアルを参照）

## はじめに

1. 必要なパッケージをインストール：
```bash
   pip install -r requirements.txt
```

2. CloudWatch Transaction Search を有効化（AWS アカウントごとにコンソールで一度だけ設定）

3. Jupyter ノートブックを開いて実行：
```bash
   jupyter notebook agentcore_observability_lambda.ipynb
```

4. ノートブックのステップバイステップの手順に従って：
   - MCP エージェントを作成してデプロイ
   - Lambda 関数をビルドしてデプロイ
   - 統合をテスト
   - CloudWatch でトレースを表示

## コンポーネント

### Lambda 関数（`lambda_agentcore_invoker.py`）
ユーザープロンプトを受け取り、AgentCore Runtime エージェントを呼び出すサーバーレス関数。エラーハンドリングと包括的なロギングを含みます。

### MCP エージェント（`mcp_agent_multi_server.py`）
複数の MCP サーバー（AWS Documentation と AWS CDK）と、オブザーバビリティ用の OpenTelemetry インストルメンテーションで設定された Strands エージェント。

## 使用方法

Lambda 関数は以下のイベント形式を期待します：
```json
{
  "prompt": "ここに質問を入力",
  "sessionId": "オプションのセッション ID"
}
```

レスポンス形式：
```json
{
  "statusCode": 200,
  "body": {
    "response": "エージェントのレスポンス",
    "sessionId": "セッション ID"
  }
}
```

## オブザーバビリティ機能

* **Gen AI Traces**: スパンタイムラインで完全なエージェントワークフローを可視化
* **CloudWatch Logs**: Lambda とエージェント実行の詳細なロギング
* **パフォーマンスメトリクス**: トークン使用量、所要時間、エラー率を追跡
* **Transaction Search**: アプリケーション全体のトレースをクエリして分析

## クリーンアップ

チュートリアル完了後、不要な料金を避けるため以下のリソースを削除してください：

1. Lambda 関数と関連する IAM ロール
2. AgentCore Runtime エージェントとエンドポイント
3. CloudWatch ロググループ
4. ECR のコンテナイメージ（該当する場合）

## 追加リソース

- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [CloudWatch Gen AI Observability ガイド](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/GenAI-observability.html)

## ライセンス

このプロジェクトはリポジトリで指定された条件の下でライセンスされています。
