# 評価アナライザー

**AI エージェント評価分析を数日/数週間から数分にスケールします。**

<p align="center">
  <img src="assets/improvement_loop.svg" alt="AI エージェントの継続的改善ループ" width="700">
</p>

## 問題

AI エージェントを大規模に評価すると、数百の LLM-as-a-Judge 説明が得られます。各説明には、スコアが付けられた理由についての詳細な推論が含まれています。人間がそれらすべてを読んでパターンを見つけることはできません。

## 機能

1. **ロード**: 評価 JSON ファイルをロード
2. **フィルター**: 低スコアの評価をフィルタリング（しきい値は設定可能）
3. **分析**: AI を使用して失敗パターンを分析
4. **生成**: 具体的なシステムプロンプト修正を生成

## 得られるもの

- LLM ジャッジからの証拠引用を含む **上位3つの問題**
- 正確なプロンプト変更を示す **前後比較テーブル**
- コピー＆ペースト可能な **完全な更新済みシステムプロンプト**

サンプルレポートは [`example_agent_output.md`](example_agent_output.md) を参照してください。

## クイックスタート

```bash
# 1. 依存関係をインストール
pip install -r requirements.txt

# 2. データを追加
#    - 評価 JSON を eval_data/ に配置
#    - system_prompt.txt をエージェントのプロンプトで編集

# 3. ノートブックを実行
jupyter notebook evaluation_analyzer.ipynb
```

## 要件

- Python 3.9 以上
- Amazon Bedrock 用に設定された AWS 認証情報
- [Strands Evals](https://github.com/strands-agents/strands-evals) または [AWS AgentCore](https://docs.aws.amazon.com/agentcore/) からの評価データ

---

**完全なウォークスルーとドキュメントについては [ノートブックを開く](evaluation_analyzer.ipynb)。**
