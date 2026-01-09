# Amazon Bedrock AgentCore オブザーバビリティ用 Transaction Search の有効化

このチュートリアルでは、AgentCore オブザーバビリティ用の Amazon CloudWatch Transaction Search を有効化する方法を示します。Transaction Search は、分散システム全体のアプリケーショントランザクションスパンとトレースを完全に可視化するインタラクティブな分析体験を提供します。

## はじめに

プロジェクトフォルダには以下が含まれています：

- CloudFormation を使用して Transaction Search を有効化する方法を示す Jupyter ノートブック
- 自動デプロイ用の CloudFormation テンプレート（transaction_search.yml）
- Transaction Search 有効化前後を示すサンプル画像

## クリーンアップ

チュートリアル完了後：

1. CloudFormation スタックを削除：`transaction-search`
2. これによりリソースポリシーが削除され、Transaction Search が無効化されます
3. 既存のトレースとログは保持ポリシーに従って保持されます
