

# Amazon Bedrock AgentCore上のStrandsエージェント向けSageMaker Managed MLflowオブザーバビリティ
このサンプルでは、Amazon SageMaker Managed MLflowをオブザーバビリティに使用して、Amazon BedrockのAgentCore RuntimeでStrandsエージェントを運用するためのステップバイステップの手順、サンプルコード、デプロイメントJupyter Notebookを提供します。これにより、Amazon Bedrock AgentCore Runtimeにデプロイされたエージェントアプリケーションの監査と分析のために、リアルタイムのエージェントインタラクションとツール呼び出しがMLflowに記録されるのを観察できます。

![image](./images/sagemaker-mlflow-agentCore.png)

## 機能
- Amazon Bedrock AgentCore Runtimeを介したツール拡張金融分析エージェントのデプロイメント
- AgentCore RuntimeとSageMaker Managed MLflowの統合
- SageMaker Managed MLflowを使用した自動トレースと実験追跡（MLflow 3.4.0以上が必要）。サンプル出力を以下に示します。
- 例：投資アドバイス用のリアルタイム金融エージェントレスポンスのストリーミング

![image](./images/sagemaker-mlflow-output.png)

## サンプルコードリポジトリ [sample-aiops-on-amazon-sagemakerai](https://github.com/aws-samples/sample-aiops-on-amazon-sagemakerai/tree/main/examples/sagemaker-mlflow-agentcore-runtime)
コードサンプルと付属のJupyter Notebookは、リポジトリで確認できます：[sample-aiops-on-amazon-sagemakerai](https://github.com/aws-samples/sample-aiops-on-amazon-sagemakerai/tree/main/examples/sagemaker-mlflow-agentcore-runtime)

# ライセンス
このライブラリはMIT-0ライセンスの下でライセンスされています。LICENSEファイルを参照してください。
---

*このソリューションは、AWS上のAI/MLワークロード向けの最新の自動化アーキテクチャパターンを示し、スケーラブルなエージェントワークロードを構築する方法を紹介しています。*
