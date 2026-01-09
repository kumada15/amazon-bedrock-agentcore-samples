# Amazon Bedrock AgentCore Runtime での Strands Agents と Amazon Bedrock モデルによるストリーミングレスポンス

## 概要

このチュートリアルでは、Amazon Bedrock AgentCore Runtime を使用して既存のエージェントでストリーミングレスポンスを実装する方法を学びます。

リアルタイムストリーミング機能を示す Strands Agents と Amazon Bedrock モデルの例に焦点を当てます。

### チュートリアル詳細

| 情報                | 詳細                                                                                 |
|:--------------------|:------------------------------------------------------------------------------------|
| チュートリアルタイプ | ストリーミング付き会話型                                                             |
| エージェントタイプ   | シングル                                                                             |
| エージェントフレームワーク | Strands Agents                                                                  |
| LLM モデル          | Anthropic Claude Haiku 4.5                                                          |
| チュートリアル構成   | AgentCore Runtime でのストリーミングレスポンス。Strands Agent と Amazon Bedrock Model を使用 |
| チュートリアル分野   | クロスバーティカル                                                                   |
| 例の複雑さ          | 簡単                                                                                 |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK および boto3                                      |

### チュートリアルアーキテクチャ

このチュートリアルでは、ストリーミングエージェントを AgentCore Runtime にデプロイする方法を説明します。

デモンストレーション目的で、ストリーミング機能を備えた Amazon Bedrock モデルを使用する Strands Agent を使用します。

この例では、`get_weather`、`get_time`、`calculator` の3つのツールを持つシンプルなエージェントを使用しますが、リアルタイムストリーミングレスポンス機能で強化されています。

<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="100%"/>
</div>

### チュートリアルの主な機能

* Amazon Bedrock AgentCore Runtime でのストリーミングレスポンスの実装
* Server-Sent Events（SSE）を使用したリアルタイム部分結果配信
* ストリーミング機能を備えた Amazon Bedrock モデルの使用
* 非同期ストリーミングサポート付き Strands Agents の使用
* プログレッシブレスポンス表示による強化されたユーザーエクスペリエンス
