## AgentCore Runtime での A2A 入門

### 概要

Amazon Bedrock AgentCore Runtime は、AI エージェントとツールをデプロイおよびスケーリングするために設計された、安全でサーバーレスのランタイムです。
任意のフレームワーク、モデル、プロトコルをサポートし、開発者がローカルプロトタイプを最小限のコード変更で本番対応ソリューションに変換できるようにします。

[Strands Agents](https://strandsagents.com/latest/) は、エージェントを構築するためのシンプルで使いやすいコードファーストのフレームワークです。

最近、AWS は AgentCore Runtime の [A2A サポート](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html) を発表しました。

この例では、Amazon Bedrock AgentCore と Strands Agents を使用してマルチエージェントシステムを構築します。

このチュートリアルでは、3つのエージェントの作成を案内します。1つ目は MCP を使用して AWS Docs を利用する AWS ドキュメントエキスパート、2つ目は最新のブログや AWS ニュースをウェブで検索するエージェント、3つ目は MCP を使用して前の2つを呼び出すオーケストレーターです。

<img src="images/architecture.png" style="width: 80%;">

### チュートリアル概要

これらのチュートリアルでは、以下の機能をカバーします：

- [1 - Strands と Bedrock AgentCore での A2A 入門](01-a2a-getting-started-agentcore-strands.ipynb)
- [2 - A2A を使用してサブエージェントを呼び出すオーケストレーターの作成](02-a2a-deploy-orchestrator.ipynb)
- [3 - クリーンアップ](03-a2a-cleanup.ipynb)
