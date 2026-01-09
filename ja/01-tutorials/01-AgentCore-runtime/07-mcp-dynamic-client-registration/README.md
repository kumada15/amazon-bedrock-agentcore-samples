# AgentCore Runtime と Auth0 による動的クライアント登録

## 概要

このセッションでは、Amazon Bedrock AgentCore Runtime で MCP ツールをホストする方法を説明します。この MCP は Auth0 の動的クライアント登録機能と統合されます。

Amazon Bedrock AgentCore Python SDK を使用して、エージェントの関数を Amazon Bedrock AgentCore 互換の MCP サーバーとしてラップします。MCP サーバーの詳細を処理するため、エージェントのコア機能に集中できます。

Amazon Bedrock AgentCore Python SDK は、エージェントまたはツールコードを AgentCore Runtime で実行するために準備します。

## はじめに

このチュートリアルを始めるには、Jupyter ノートブックを開き、ステップバイステップガイドに従ってください：

**[📓 deploy_dcr_mcp_agentcore.ipynb](deploy_dcr_mcp_agentcore.ipynb)**

ノートブックには、このチュートリアルを完了するために必要なすべてのコード例、設定、詳細な手順が含まれています。

## 学ぶこと

このチュートリアルでは、以下を学びます：

* ツールを持つ MCP サーバーの作成方法
* サーバーをローカルでテストする方法
* DCR をサポートし、API とアプリを追加するように Auth0 テナントを設定する方法
* Auth0 上の DCR と統合したサーバーを AWS にデプロイする方法
* デプロイしたサーバーを呼び出す方法

### チュートリアル詳細

| 情報                | 詳細                                                      |
|:--------------------|:----------------------------------------------------------|
| チュートリアルタイプ | ツールのホスティング + Auth0 での DCR                     |
| ツールタイプ        | MCP サーバー                                               |
| チュートリアル構成   | AgentCore Runtime でのツールホスティング、MCP サーバーの作成 |
| チュートリアル分野   | クロスバーティカル                                         |
| 例の複雑さ          | 中級                                                       |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK および MCP Client       |

### チュートリアルアーキテクチャ

このチュートリアルでは、この例を AgentCore Runtime にデプロイする方法を説明します。

デモンストレーション目的で、`add_numbers`、`multiply_numbers`、`greet_users` の3つのツールを持つ非常にシンプルな MCP サーバーを使用します。

<img src="images/architecture.png" width="80%">

### チュートリアルの主な機能

* MCP サーバーのホスティング
* 動的クライアント登録（DCR）
* Auth0
