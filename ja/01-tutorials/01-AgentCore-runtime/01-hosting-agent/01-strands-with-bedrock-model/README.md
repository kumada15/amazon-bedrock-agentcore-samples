# Amazon Bedrock AgentCore Runtime での Strands Agents と Amazon Bedrock モデルのホスティング

## 概要

このチュートリアルでは、Amazon Bedrock AgentCore Runtime を使用して既存のエージェントをホストする方法を学びます。

ここでは Strands Agents と Amazon Bedrock モデルの例に焦点を当てます。LangGraph と Amazon Bedrock モデルについては[こちら](../02-langgraph-with-bedrock-model)を、
Strands Agents と OpenAI モデルについては[こちら](../03-strands-with-openai-model)をご確認ください。


### チュートリアル詳細

| 情報                | 詳細                                                                             |
|:--------------------|:---------------------------------------------------------------------------------|
| チュートリアルタイプ | 会話型                                                                           |
| エージェントタイプ   | シングル                                                                         |
| エージェントフレームワーク | Strands Agents                                                              |
| LLM モデル          | Anthropic Claude Haiku 4.5                                                       |
| チュートリアル構成   | AgentCore Runtime でのエージェントホスティング。Strands Agent と Amazon Bedrock Model を使用 |
| チュートリアル分野   | クロスバーティカル                                                               |
| 例の複雑さ          | 簡単                                                                             |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK および boto3                                  |

### チュートリアルアーキテクチャ

このチュートリアルでは、既存のエージェントを AgentCore Runtime にデプロイする方法を説明します。

デモンストレーション目的で、Amazon Bedrock モデルを使用する Strands Agent を使用します。

この例では、`get_weather` と `get_time` の2つのツールを持つ非常にシンプルなエージェントを使用します。

<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="100%"/>
</div>

### チュートリアルの主な機能

* Amazon Bedrock AgentCore Runtime でのエージェントホスティング
* Amazon Bedrock モデルの使用
* Strands Agents の使用
