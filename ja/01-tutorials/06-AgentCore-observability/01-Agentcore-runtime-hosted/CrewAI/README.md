# Amazon Bedrock AgentCore Runtime とオブザーバビリティを備えた CrewAI エージェント

このチュートリアルでは、Amazon CloudWatch によるオブザーバビリティを備えた [CrewAI](https://www.crewai.com/) 旅行エージェントを Amazon Bedrock AgentCore Runtime にデプロイする方法を示します。

## 概要

AWS OpenTelemetry インストゥルメンテーションと Amazon CloudWatch モニタリングによる包括的なオブザーバビリティを備えた、Amazon Bedrock モデルを使用した CrewAI エージェントのホスティング方法を学びます。

## 前提条件

* Python 3.10 以上
* 適切な権限で設定された AWS 認証情報
* Amazon Bedrock AgentCore SDK
* CrewAI フレームワーク
* Amazon CloudWatch アクセス
* Amazon CloudWatch で[トランザクション検索](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Enable-TransactionSearch.html)を有効化

## 始め方

1. 依存関係をインストール：
   ```bash
   pip install -r requirements.txt
   ```

2. Jupyter ノートブックを開く: `runtime-with-crewai-and-bedrock-models.ipynb`

3. チュートリアルに従って：
   - CrewAI エージェントをローカルで作成してテスト
   - AgentCore Runtime にエージェントをデプロイ
   - OpenTelemetry でオブザーバビリティを有効化
   - CloudWatch でパフォーマンスを監視

## 主な機能

* ウェブ検索機能を備えた CrewAI 旅行エージェント
* Amazon Bedrock モデル（Anthropic Claude Haiku 4.5）
* AgentCore Runtime ホスティング
* CloudWatch オブザーバビリティとトレーシング

## クリーンアップ

チュートリアル完了後：
1. AgentCore Runtime デプロイメントを削除
2. ECR リポジトリをクリーンアップ
