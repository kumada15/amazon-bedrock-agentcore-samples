# Amazon Bedrock AgentCore Memory

## 概要

メモリはインテリジェンスの重要なコンポーネントです。大規模言語モデル（LLM）は印象的な能力を持っていますが、会話間で持続的なメモリがありません。Amazon Bedrock AgentCore Memory は、AIエージェントが時間をかけてコンテキストを維持し、重要な事実を記憶し、一貫したパーソナライズされた体験を提供できるマネージドサービスを提供することで、この制限に対処します。

## 主な機能

AgentCore Memory は以下を提供します：

- **コアインフラストラクチャ**：組み込みの暗号化と可観測性を備えたサーバーレスセットアップ
- **イベントストレージ**：ブランチングをサポートする生イベントストレージ（会話履歴/チェックポイント）
- **ストラテジー管理**：設定可能な抽出ストラテジー（SEMANTIC、SUMMARY、USER_PREFERENCES、CUSTOM）
- **メモリレコード抽出**：設定されたストラテジーに基づく事実、好み、サマリーの自動抽出
- **セマンティック検索**：自然言語クエリを使用した関連メモリのベクターベース検索

## AgentCore Memory の仕組み

![高レベルワークフロー](./images/high_level_memory.png)

AgentCore Memory は2つのレベルで動作します：

### 短期メモリ

単一のインタラクションまたは密接に関連するセッション内で継続性を提供する、即時の会話コンテキストとセッションベースの情報。

### 長期メモリ

時間をかけてパーソナライズされた体験を可能にする、事実、好み、サマリーを含む、複数の会話にまたがって抽出・保存される永続的な情報。

## メモリアーキテクチャ

1. **会話ストレージ**：完全な会話が即時アクセス用に生の形式で保存される
2. **ストラテジー処理**：設定されたストラテジーがバックグラウンドで会話を自動的に分析
3. **情報抽出**：ストラテジータイプに基づいて重要なデータが抽出される（通常約1分かかる）
4. **整理されたストレージ**：抽出された情報が効率的な検索のために構造化されたネームスペースに保存される
5. **セマンティック検索**：自然言語クエリがベクトル類似性を使用して関連メモリを検索できる

## メモリストラテジータイプ

AgentCore Memory は4つのストラテジータイプをサポートします：

- **セマンティックメモリ**：類似性検索用のベクトル埋め込みを使用して事実情報を保存
- **サマリーメモリ**：コンテキスト保持のための会話サマリーを作成・維持
- **ユーザー好みメモリ**：ユーザー固有の好みと設定を追跡
- **カスタムメモリ**：抽出と統合ロジックのカスタマイズが可能

## はじめに

整理されたチュートリアルを通じてメモリ機能を探索してください：

- **[短期メモリ](./01-short-term-memory/)**：セッションベースのメモリと即時コンテキスト管理について学ぶ
- **[長期メモリ](./02-long-term-memory/)**：永続メモリストラテジーと会話間の継続性を理解する

## サンプルノートブック概要

| メモリタイプ | フレームワーク | ユースケース | ノートブック |
| ----------- | ------------------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| 短期 | Strands Agent | パーソナルエージェント | [personal-agent.ipynb](./01-short-term-memory/01-single-agent/with-strands-agent/personal-agent.ipynb) |
| 短期 | LangGraph | フィットネスコーチ | [personal-fitness-coach.ipynb](./01-short-term-memory/01-single-agent/with-langgraph-agent/personal-fitness-coach.ipynb) |
| 短期 | Strands Agent | 旅行計画 | [travel-planning-agent.ipynb](./01-short-term-memory/02-multi-agent/with-strands-agent/travel-planning-agent.ipynb) |
| 長期 | Strands Hooks | カスタマーサポート | [customer-support.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/customer-support/customer-support.ipynb) |
| 長期 | Strands Hooks | 数学アシスタント | [math-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-hooks/simple-math-assistant/math-assistant.ipynb) |
| 長期 | Strands Tool | 料理アシスタント | [culinary-assistant.ipynb](./02-long-term-memory/01-single-agent/using-strands-agent-memory-tool/culinary-assistant.ipynb) |
| 長期 | Strands Multi-Agent | 旅行予約 | [travel-booking-assistant.ipynb](./02-long-term-memory/02-multi-agent/with-strands-agent/travel-booking-assistant.ipynb) |

## 前提条件

- Python 3.10 以上
- Amazon Bedrock アクセスのある AWS アカウント
- Jupyter Notebook 環境
- 必要な Python パッケージ（個別サンプルの requirements.txt ファイルを参照）
