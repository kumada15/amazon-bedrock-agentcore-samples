# Amazon Bedrock AgentCore Runtime

## 概要
Amazon Bedrock AgentCore Runtime は、AIエージェントとツールをデプロイしてスケールするために設計された、安全でサーバーレスなランタイムです。
あらゆるフレームワーク、モデル、プロトコルをサポートし、開発者がローカルのプロトタイプを最小限のコード変更で本番環境対応のソリューションに変換できるようにします。

Amazon BedrockAgentCore Python SDK は、エージェント関数を Amazon Bedrock と互換性のあるHTTPサービスとしてデプロイするのを支援する軽量ラッパーを提供します。HTTPサーバーの詳細をすべて処理するため、エージェントのコア機能に集中できます。

必要なのは、関数を `@app.entrypoint` デコレーターで装飾し、SDKの `configure` と `launch` 機能を使用してエージェントを AgentCore Runtime にデプロイするだけです。その後、アプリケーションは SDK または boto3、AWS SDK for JavaScript、AWS SDK for Java などのAWS開発者ツールを使用してこのエージェントを呼び出すことができます。

![Runtime 概要](images/runtime_overview.png)

## 主な機能

### フレームワークとモデルの柔軟性

- あらゆるフレームワーク（Strands Agents、LangChain、LangGraph、CrewAI など）からエージェントとツールをデプロイ
- あらゆるモデル（Amazon Bedrock 内外問わず）を使用

### 統合

Amazon Bedrock AgentCore Runtime は、統合SDKを通じて他の Amazon Bedrock AgentCore 機能と統合されます：

- Amazon Bedrock AgentCore Memory
- Amazon Bedrock AgentCore Gateway
- Amazon Bedrock AgentCore Observability
- Amazon Bedrock AgentCore Tools

この統合は、開発プロセスを簡素化し、AIエージェントの構築、デプロイ、管理のための包括的なプラットフォームを提供することを目的としています。

### ユースケース

このランタイムは、以下を含む幅広いアプリケーションに適しています：

- リアルタイムでインタラクティブなAIエージェント
- 長時間実行される複雑なAIワークフロー
- マルチモーダルAI処理（テキスト、画像、音声、動画）

## チュートリアル概要

これらのチュートリアルでは、以下の機能をカバーします：

- [エージェントのホスティング](01-hosting-agent)
- [MCPサーバーのホスティング](02-hosting-MCP-server)
- [高度な概念](03-advanced-concepts)
