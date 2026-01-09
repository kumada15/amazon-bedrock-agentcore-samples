# AgentCore を使用したセルフホストエージェントのオブザーバビリティ

このセクションでは、Amazon Bedrock AgentCore Runtime で**ホストされていない**人気のあるオープンソースエージェントフレームワークの AgentCore オブザーバビリティを示します。OpenTelemetry と Amazon CloudWatch を使用して、既存のエージェントに包括的なオブザーバビリティを追加する方法を学びます。

## 利用可能なフレームワーク

### CrewAI
- **ノートブック**: `CrewAI_Observability.ipynb`
- **説明**: チームで協力する自律型 AI エージェント
- **機能**: カスタムインストルメンテーションによるマルチエージェントコラボレーション

### LangGraph
- **ノートブック**: `Langgraph_Observability.ipynb`
- **説明**: ステートフルなマルチアクター LLM アプリケーション
- **機能**: トレース可視化を備えた複雑な推論システム

### LlamaIndex
- **ノートブック**: `LlamaIndex_Observability.ipynb`
- **説明**: データ上の LLM 駆動エージェント
- **機能**: セッショントラッキングを備えた関数エージェント
- **追加情報**: アーキテクチャ図を含む詳細な README

### Strands Agents
- **ノートブック**: `Strands_Observability.ipynb`
- **説明**: モデル駆動のエージェント開発
- **機能**: カスタムスパンを備えた複雑なワークフローエージェント

## はじめに

1. フレームワークディレクトリを選択
2. 要件をインストール: `pip install -r requirements.txt`
3. AWS 認証情報を設定
4. `.env.example` を `.env` にコピーして変数を更新
5. CloudWatch Transaction Search を有効化
6. Jupyter ノートブックを実行


## 前提条件

- 適切な権限を持つ Bedrock と CloudWatch へのアクセスがある AWS アカウント
- Python 3.10 以上
- AWS CloudWatch Transaction Search が有効化済み
- フレームワーク固有の依存関係

## クリーンアップ

サンプル完了後：
1. CloudWatch ロググループを削除
2. 作成された AWS リソースを削除
3. ローカル環境ファイルをクリーンアップ
