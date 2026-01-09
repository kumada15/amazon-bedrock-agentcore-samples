# AgentCore Observability

このリポジトリでは、Amazon CloudWatch および他のプロバイダーを使用してエージェントの AgentCore 可観測性を実装する方法を示します。Amazon Bedrock AgentCore Runtime でホストされたエージェントと、人気のあるオープンソースエージェントフレームワークを使用したランタイム外でホストされたエージェントの両方のサンプルを提供します。

AgentCore Observability の詳細については、[こちら](https://aws.amazon.com/blogs/machine-learning/build-trustworthy-ai-agents-with-amazon-bedrock-agentcore-observability/)のブログ投稿を参照してください。

## プロジェクト構成

```
06-AgentCore-observability/
├── 01-Agentcore-runtime-hosted/
│   ├── CrewAI/
│   │   ├── images/
│   │   ├── requirements.txt
│   │   └── runtime-with-crewai-and-bedrock-models.ipynb
│   ├── Strands Agents/
│   │   ├── images/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_bedrock_models.ipynb
│   └── README.md
├── 02-Agent-not-hosted-on-runtime/
│   ├── CrewAI/
│   │   ├── .env.example
│   │   ├── CrewAI_Observability.ipynb
│   │   └── requirements.txt
│   ├── Langgraph/
│   │   ├── .env.example
│   │   ├── Langgraph_Observability.ipynb
│   │   └── requirements.txt
│   ├── LlamaIndex/
│   │   ├── images/
│   │   ├── .env.example
│   │   ├── LlamaIndex_Observability.ipynb
│   │   ├── README.md
│   │   └── requirements.txt
│   ├── Strands/
│   │   ├── images/
│   │   ├── .env.example
│   │   ├── requirements.txt
│   │   └── Strands_Observability.ipynb
│   └── README.md
├── 03-advanced-concepts/
│   ├── 01-custom-span-creation/
│   │   ├── .env.example
│   │   ├── Custom_Span_Creation.ipynb
│   │   └── requirements.txt
│   └── README.md
├── 04-Agentcore-runtime-partner-observability/
│   ├── Arize/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_arize.ipynb
│   ├── Braintrust/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_braintrust.ipynb
│   ├── Instana/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_instana.ipynb
│   ├── Langfuse/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_langfuse.ipynb
│   ├── images/
│   └── README.md
├── 05-Lambda-AgentCore-invocation/
│   ├── .gitignore
│   ├── agentcore_observability_lambda.ipynb
│   ├── lambda_agentcore_invoker.py
│   ├── mcp_agent_multi_server.py
│   ├── README.md
│   └── requirements.txt
└── README.md
```

## 概要

このリポジトリは、GenAIアプリケーションの可観測性を実装するためのサンプルとツールを提供します。AgentCore Observability は、統合された運用ダッシュボードを通じて、開発者が本番環境でエージェントのパフォーマンスをトレース、デバッグ、モニタリングするのを支援します。OpenTelemetry 互換のテレメトリとエージェントワークフローの各ステップの詳細な可視化をサポートし、Amazon CloudWatch GenAI Observability により、開発者がエージェントの動作を容易に把握し、大規模に標準を維持できるようにします。

## 内容

人気のあるエージェント開発フレームワークを使用したサンプルを示します：

- **Strands Agents**：モデル駆動のエージェント開発を使用して複雑なワークフローでLLMアプリケーションを構築
- **CrewAI**：タスクを達成するために役割で協力する自律型AIエージェントを作成
- **LangGraph**：複雑な推論システム用のステートフルなマルチアクターアプリケーションでLangChainを拡張
- **LlamaIndex**：ワークフローを備えたデータ上のLLM駆動エージェント


### 1. Bedrock AgentCore Runtime ホスト（01-Agentcore-runtime-hosted）

Amazon OpenTelemetry Python Instrumentation と Amazon CloudWatch を使用した、Amazon Bedrock AgentCore Runtime でホストされたエージェントの可観測性を示すサンプル。

### 2. ランタイム外でホストされたエージェント（02-Agent-not-hosted-on-runtime）

Amazon Bedrock AgentCore Runtime でホストされていない人気のあるオープンソースエージェントフレームワークの可観測性を示すサンプル：

### 3. 高度な概念（03-advanced-concepts）

高度な可観測性パターンと技術：

- **カスタムスパン作成**：エージェントワークフロー内の特定の操作の詳細なトレースとモニタリングのためのカスタムスパンを作成する方法を学ぶ

### 4. パートナー可観測性（04-Agentcore-runtime-partner-observability）

サードパーティの可観測性ツールを使用した Amazon Bedrock AgentCore Runtime でホストされたエージェントの使用例：

- **Arize**：AIおよびエージェントエンジニアリングプラットフォーム
- **Braintrust**：AI評価およびモニタリングプラットフォーム
- **Instana**：リアルタイムAPMおよび可観測性プラットフォーム
- **Langfuse**：LLM可観測性および分析

### 5. Lambda AgentCore 呼び出し（05-Lambda-AgentCore-invocation）

完全な CloudWatch 可観測性を備えた AWS Lambda 関数から AgentCore Runtime エージェントを呼び出す方法を学ぶ：

- **Lambda統合**：ホストされたエージェントを呼び出すサーバーレス関数をデプロイ
- **MCPマルチサーバー**：単一のエージェントで複数のMCPサーバー（AWS Docs + CDK）を使用
- **CloudWatch GenAI Observability**：本番環境でエージェントの動作とパフォーマンスをモニタリング

## はじめに

1. 探索したいフレームワークのディレクトリに移動
2. 要件をインストール
3. AWS認証情報を設定
4. `.env.example` ファイルを `.env` にコピーして変数を更新
5. Jupyter ノートブックを開いて実行

## 前提条件

- 適切な権限を持つAWSアカウント
- Python 3.10以上
- Jupyter ノートブック環境
- 認証情報で設定された AWS CLI
- Transaction Search を有効化

## クリーンアップ

サンプル完了後、不要な料金を避けるため、Amazon CloudWatch で作成されたロググループと関連リソースを削除してください。

## ライセンス

このプロジェクトはリポジトリで指定された条件の下でライセンスされています。
