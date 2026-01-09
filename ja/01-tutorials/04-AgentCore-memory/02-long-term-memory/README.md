# AgentCore Memory: 長期メモリ戦略

## 概要

Amazon Bedrock AgentCore の長期メモリは、AI エージェントが複数の会話やセッションにわたって永続的な情報を維持できるようにします。即時のコンテキストに焦点を当てる短期メモリとは異なり、長期メモリは意味のある情報を抽出、処理、保存し、将来のインタラクションで取得して適用できるため、真にパーソナライズされたインテリジェントなエージェント体験を作成します。

## 長期メモリとは？

長期メモリは以下を提供します：

- **セッション間の永続性**: 個々の会話を超えて存続する情報
- **インテリジェントな抽出**: 重要な事実、好み、パターンの自動識別と保存
- **セマンティック理解**: 自然言語検索を可能にするベクトルベースのストレージ
- **パーソナライゼーション**: カスタマイズされた体験を可能にするユーザー固有の情報
- **知識の蓄積**: 時間の経過とともに継続的な学習と情報構築

## 長期メモリ戦略の仕組み

長期メモリは、どの情報を抽出し、どのように処理するかを定義する**メモリ戦略**を通じて動作します。システムはバックグラウンドで自動的に動作します：

### 処理パイプライン

1. **会話分析**: 保存された会話が設定された戦略に基づいて分析されます
2. **情報抽出**: AI モデルを使用して重要なデータ（事実、好み、要約）が抽出されます
3. **構造化ストレージ**: 抽出された情報は効率的な取得のために名前空間で整理されます
4. **セマンティックインデキシング**: 自然言語検索機能のために情報がベクトル化されます
5. **統合**: 類似の情報が時間の経過とともにマージされ、洗練されます

**処理時間**: 通常、会話が保存されてから約1分かかり、追加のコードは不要です。

### 舞台裏

- **AI による抽出**: 基盤モデルを使用して関連情報を理解し抽出
- **ベクトル埋め込み**: 類似性ベースの検索のためのセマンティック表現を作成
- **名前空間構成**: 設定可能なパスのような階層を使用して情報を構造化
- **自動統合**: 類似の情報をマージして洗練し、重複を防止
- **増分学習**: 会話パターンに基づいて抽出品質を継続的に改善

## 長期メモリ戦略タイプ

AgentCore Memory は、長期情報ストレージのために4つの異なる戦略タイプをサポートしています：

### 1. セマンティックメモリ戦略

類似性検索のためのベクトル埋め込みを使用して、会話から抽出された事実情報を保存します。

```python
{
    "semanticMemoryStrategy": {
        "name": "FactExtractor",
        "description": "Extracts and stores factual information",
        "namespaces": ["support/user/{actorId}/facts"]
    }
}
```

**最適な用途**: 製品情報、技術的な詳細、または自然言語クエリを通じて取得する必要がある事実データの保存。

### 2. 要約メモリ戦略

長いインタラクションのコンテキストを保持するために、会話の要約を作成して維持します。

```python
{
    "summaryMemoryStrategy": {
        "name": "ConversationSummary",
        "description": "Maintains conversation summaries",
        "namespaces": ["support/summaries/{sessionId}"]
    }
}
```

**最適な用途**: フォローアップ会話でのコンテキスト提供と、長いインタラクションにわたる継続性の維持。

### 3. ユーザー設定メモリ戦略

インタラクションをパーソナライズするために、ユーザー固有の好みと設定を追跡します。

```python
{
    "userPreferenceMemoryStrategy": {
        "name": "UserPreferences",
        "description": "Captures user preferences and settings",
        "namespaces": ["support/user/{actorId}/preferences"]
    }
}
```

**最適な用途**: コミュニケーションの好み、製品の好み、またはユーザー固有の設定の保存。

### 4. カスタムメモリ戦略

抽出と統合のためのプロンプトをカスタマイズでき、特殊なユースケースに柔軟性を提供します。

```python
{
    "customMemoryStrategy": {
        "name": "CustomExtractor",
        "description": "Custom memory extraction logic",
        "namespaces": ["user/custom/{actorId}"],
        "configuration": {
            "semanticOverride": { # 要約やユーザー設定もオーバーライドできます。
                "extraction": {
                    "appendToPrompt": "Extract specific information based on custom criteria",
                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                },
                "consolidation": {
                    "appendToPrompt": "Consolidate extracted information in a specific format",
                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                }
            }
        }
    }
}
```

**最適な用途**: 標準戦略に適合しない特殊な抽出ニーズ。

## 名前空間の理解

名前空間は、パスのような構造を使用して戦略内のメモリレコードを整理します。動的に置き換えられる変数を含めることができます：

- `support/facts/{sessionId}`: セッションごとに事実を整理
- `user/{actorId}/preferences`: アクター ID ごとにユーザー設定を保存
- `meetings/{memoryId}/summaries/{sessionId}`: メモリごとに要約をグループ化

`{actorId}`、`{sessionId}`、`{memoryId}` 変数は、メモリの保存と取得時に実際の値に自動的に置き換えられます。

## 例: 実際の動作

ユーザーがカスタマーサポートエージェントに次のように伝えたとします：_「私はベジタリアンで、イタリア料理が本当に好きです。午後6時以降には電話しないでください。」_

この会話を保存すると、設定された戦略が自動的に：

**セマンティック戦略** が抽出：

- 「ユーザーはベジタリアン」
- 「ユーザーはイタリア料理が好き」

**ユーザー設定戦略** がキャプチャ：

- 「食事の好み: ベジタリアン」
- 「料理の好み: イタリアン」
- 「連絡の好み: 午後6時以降は電話なし」

**要約戦略** が作成：

- 「ユーザーは食事制限と連絡先の好みについて話し合った」

これらはすべてバックグラウンドで自動的に行われます - 会話を保存するだけで、戦略が残りを処理します。

## 利用可能なサンプルノートブック

これらのハンズオン例を探索して、長期メモリ戦略の実装を学びましょう：

| 統合方法                  | ユースケース        | 説明                                                                            | ノートブック                                                                                                   | アーキテクチャ                                                                             |
| ------------------------- | ------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Strands Agent フック      | カスタマーサポート  | セマンティックと設定メモリ戦略を備えた完全なサポートシステム                    | [customer-support.ipynb](./01-single-agent/using-strands-agent-hooks/customer-support/customer-support.ipynb)  | [表示](./01-single-agent/using-strands-agent-hooks/customer-support/architecture.png)      |
| Strands Agent フック      | 数学アシスタント    | ユーザーの学習好みと進捗を記憶する数学家庭教師アシスタント                      | [math-assistant.ipynb](./01-single-agent/using-strands-agent-hooks/simple-math-assistant/math-assistant.ipynb) | [表示](./01-single-agent/using-strands-agent-hooks/simple-math-assistant/architecture.png) |
| LangGraph Agent フック    | 栄養アシスタント    | パーソナライズされた推奨のためにユーザーの食事好みと健康目標を保存する栄養アドバイザー | [nutrition-assistant-with-user-preference-saving.ipynb](./01-single-agent/using-langgraph-agent-hooks/nutrition-assistant-with-user-preference-saving.ipynb) | [表示](./01-single-agent/using-langgraph-agent-hooks/architecture.png) |
| Strands Agent メモリツール | 料理アシスタント    | 食事の好みと料理スタイルを学習する食品推奨エージェント                          | [culinary-assistant.ipynb](./01-single-agent/using-strands-agent-memory-tool/culinary-assistant.ipynb)         | [表示](./01-single-agent/using-strands-agent-memory-tool/architecture.png)                 |
| マルチエージェント        | エージェント連携    | 長期メモリ戦略を共有・活用する複数のエージェントを持つ旅行アシスタント          | [travel-booking-assistant.ipynb](./02-multi-agent/with-strands-agent/travel-booking-assistant.ipynb)           | [表示](./02-multi-agent/with-strands-agent/architecture.png)                               |

## 始め方

1. ユースケースに合ったサンプルを選択
2. サンプルフォルダに移動
3. 要件をインストール: `pip install -r requirements.txt`
4. Jupyter ノートブックを開き、ステップバイステップの実装に従う

## ベストプラクティス

1. **戦略の選択**: ユースケース要件に基づいて適切な戦略を選択
2. **名前空間設計**: 効率的な情報整理のために名前空間階層を計画
3. **抽出チューニング**: ドメイン固有の情報のために抽出プロンプトをカスタマイズ
4. **パフォーマンス監視**: メモリ抽出品質と取得パフォーマンスを追跡
5. **プライバシー考慮**: 適切なデータ保持とプライバシーポリシーを実装

## 次のステップ

長期メモリ戦略をマスターしたら、以下を探索してください：

- 包括的なエージェント体験のための短期メモリと長期メモリの組み合わせ
- 高度なカスタム戦略設定
- マルチエージェントメモリ共有パターン
- 本番デプロイメントの考慮事項
