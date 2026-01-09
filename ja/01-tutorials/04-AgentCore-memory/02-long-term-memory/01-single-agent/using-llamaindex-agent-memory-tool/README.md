# LlamaIndex と AWS Bedrock AgentCore Memory の統合

このプロジェクトでは、永続的なメモリ機能を持つエンタープライズグレードの AI エージェントを紹介します。LlamaIndex の ReAct フレームワークと AWS Bedrock AgentCore Memory がシームレスに統合され、時間とともに学習、適応、進化するインテリジェントなシステムを作成する方法を実演します。従来のステートレスなエージェントとは異なり、これらの実装はセッション間でコンテキストを維持し、高度な縦断的分析、相互参照機能、累積的な知識構築を可能にし、プロフェッショナル環境における AI エージェントの動作方法を変革します。

## 主な機能

- **ネイティブ LlamaIndex 統合**: `agent.run(message, memory=agentcore_memory)` による直接メモリ受け渡し
- **ドメイン固有の例**: 学術研究、法的文書分析、医療知識、投資ポートフォリオ管理
- **包括的なテスト**: 各例に 8-10 の体系的なテストケースと期待値検証
- **短期・長期メモリ**: 両方のメモリタイプを完全にカバー
- **エンタープライズ対応**: 本番環境に適したシンプルで明示的な API

## プロジェクト構造

```
├── 01-short-term-memory/
│   ├── academic-research-assistant-short-term-memory-tutorial.ipynb
│   ├── legal-document-analyzer-short-term-memory-tutorial.ipynb
│   ├── medical-knowledge-assistant-short-term-memory-tutorial.ipynb
│   └── investment-portfolio-advisor-short-term-memory-tutorial.ipynb
├── 02-long-term-memory/
│   ├── academic-research-assistant-long-term-memory-tutorial.ipynb
│   ├── legal-document-analyzer-long-term-memory-tutorial.ipynb
│   ├── medical-knowledge-assistant-long-term-memory-tutorial.ipynb
│   └── investment-portfolio-advisor-long-term-memory-tutorial.ipynb
└── requirements.txt
```

## ユースケース

### 学術研究アシスタント
- **短期メモリ**: 単一セッション内での論文分析、研究統合
- **長期メモリ**: セッション間での研究の進化、数ヶ月にわたる研究助成金提案のサポート
- **メモリインテリジェンス**: 研究テーマ、引用ネットワーク、方法論の進化を追跡
- **テスト**: コンテキスト推論と相互参照検証を含む 8 つの包括的なテスト

### 法的文書分析
- **短期メモリ**: 契約分析、リスク評価、コンプライアンスチェック
- **長期メモリ**: 複数案件の判例追跡、法的知識の蓄積（12ヶ月保持）
- **メモリインテリジェンス**: 判例データベースの構築、規制変更の追跡、クライアント履歴の維持
- **テスト**: 判例適用と規制コンプライアンスを含む 9 つの体系的なテスト

### 医療知識アシスタント
- **短期メモリ**: 患者相談、薬物相互作用、臨床ガイドライン
- **長期メモリ**: 縦断的な患者ケア、治療結果、集団健康傾向
- **メモリインテリジェンス**: 患者履歴の維持、治療効果の追跡、結果からの学習
- **テスト**: 臨床推論と治療計画を含む 10 の包括的なテスト

### 投資ポートフォリオアドバイザー
- **短期メモリ**: クライアントプロファイリング、ポートフォリオ分析、投資推奨
- **長期メモリ**: 四半期ごとのパフォーマンス追跡（Q1→Q2→Q3→Q4）、市場インテリジェンス、資産管理
- **メモリインテリジェンス**: 320万ドル→345万ドルのポートフォリオ進化、マーケットタイミング決定、投資仮説の適応を追跡
- **テスト**: 四半期パフォーマンス帰属分析と複数年投資ジャーニー分析を含む 10 の体系的なテスト

## システムアーキテクチャ

*アーキテクチャ図はここに追加されます*

## 前提条件

- Python 3.10以上
- Bedrock AgentCore Memory 権限を持つ AWS アカウント
- 適切な認証情報で設定された AWS CLI
- Claude 3.7 Sonnet 推論プロファイルへのアクセス（`us.anthropic.claude-3-7-sonnet-20250219-v1:0`）

## インストール

```bash
# Jupyter を含むすべての依存関係をインストール
pip install -r requirements.txt

# 別の方法: Jupyter を個別にインストール
pip install jupyter ipykernel
```

## クイックスタート

1. **AWS 認証情報を設定:**
   ```bash
   aws configure
   ```

2. **チュートリアルを選択してノートブックを開く:**
   ```bash
   jupyter notebook 01-short-term-memory/academic-research-assistant-short-term-memory-tutorial.ipynb
   ```

3. **包括的なテストを含むステップバイステップのチュートリアルに従う**

## 主な利点

- **明示的な制御**: 隠れた自動化ではなく直接メモリパラメータ
- **簡単なデバッグ**: バックグラウンドフックではなく可視化されたメモリ操作
- **シンプルな API**: 複雑なセットアップではなく `agent.run(message, memory=memory)`
- **包括的なテスト**: 期待結果による体系的な検証
- **ドメイン専門知識**: 汎用的な例ではなく専門的なユースケース

## テスト方法論

各ノートブックには明確な検証付きの **8-10 の体系的なテスト** が含まれています：

### テストカテゴリ
- **テスト 1-2: メモリストレージ** - 情報の永続性とツール統合を検証
- **テスト 3-4: コンテキスト想起** - 識別情報、メトリクス、詳細情報の取得を検証
- **テスト 5-6: 推論と統合** - 相互参照機能と知識統合をテスト
- **テスト 7-8: 実用的なアプリケーション** - 実世界シナリオの検証（研究助成金提案、ケース分析）
- **テスト 9-10: セッション境界** - メモリ分離とセッション間動作の検証

### 検証アプローチ
- **期待結果**: 各テストは比較用の期待出力を表示
- **成功基準**: 特定のメトリクスによる明確な合否指標
- **段階的な複雑さ**: テストは基本的な想起から高度な推論へと構築
- **エッジケーステスト**: セッション境界、メモリ制限、エラー処理

### テストパターンの例
```python
# テスト 4: 詳細メトリクスの想起
response = await agent.run("正確な精度パーセンテージは何でしたか？", memory=memory)
print("結果:", response)
print("期待値: Zhang et al - CNNs 95.2%, Johnson et al - BERT 89.1%")
# ユーザーは検証できます: 応答には両方の精度数値が含まれていますか？
```

## 技術概要

**主要な長期メモリコンポーネント:**
1. **セマンティック戦略設定**: 365日保持で自動インサイト抽出のための SemanticStrategy を使用
2. **セッション間の永続性**: 同じ actor_id + memory_id、期間ごとに異なる session_id で知識の継続性を実現
3. **カスタムメモリ検索ツール**: AgentCore のネイティブ search_long_term_memories() を LlamaIndex FunctionTool でラップ
4. **セマンティック処理パイプライン**: 会話イベント → セマンティックメモリ変換のために 90-120 秒待機
5. **動的セッション管理**: 柔軟なセッション処理のために memory.context.session_id を使用

## メモリ設定

### 短期メモリ
```python
context = AgentCoreMemoryContext(
    actor_id="user-id",
    memory_id=memory_id,
    session_id="session-id",
    namespace="/domain-specific"
)
agentcore_memory = AgentCoreMemory(context=context)
```

### 長期メモリ（12ヶ月保持）
```python
# セマンティック戦略によるセッション間の永続性
memory = memory_manager.get_or_create_memory(
    name='DomainSpecificLongTerm',
    strategies=[SemanticStrategy(name="domainLongTermMemory")],
    event_expiry_days=365  # 12ヶ月保持
)

# 永続性のためのセッション間で同じコンテキスト
context = AgentCoreMemoryContext(
    actor_id="advisor-id",      # セッション間で同じアクター
    memory_id=memory_id,        # 同じメモリストア
    session_id="q1-session",    # インタラクションごとに異なる
    namespace="/domain-specific"
)
```

### メモリインテリジェンスの例
- **投資アドバイザー**: 四半期パフォーマンスを追跡（Q1: +8.2% → Q2: -2.1% → Q3: 回復）
- **法的分析**: ケースと規制変更にわたる判例データベースを維持
- **医療アシスタント**: 縦断的な患者ケア記録と治療結果を構築
- **研究アシスタント**: 数ヶ月にわたる研究テーマと方法論のインサイトを進化

## コントリビューション

このプロジェクトは LlamaIndex + AgentCore Memory 統合のベストプラクティスを示しています。以下の貢献を歓迎します：

- 追加のドメイン例
- 強化されたテスト方法論
- パフォーマンス最適化
- ドキュメント改善

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています。

## サポート

以下に関する質問：
- **LlamaIndex 統合**: ドメイン固有のノートブックを参照
- **AgentCore Memory**: AWS Bedrock ドキュメントを確認
- **テストパターン**: 包括的なテスト例をレビュー

