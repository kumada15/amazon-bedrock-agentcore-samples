# Amazon Bedrock Agentcore SDK ツールサンプル

このフォルダには AgentCore SDK ツールの使用方法を示すサンプルが含まれています：

## ブラウザツール

* `browser_viewer.py` - 適切な表示サイズサポートを備えた Amazon Bedrock Agentcore ブラウザライブビューア。
* `run_live_viewer.py` - Bedrock Agentcore ブラウザライブビューアを実行するスタンドアロンスクリプト。

## Code Interpreter ツール

* `dynamic_research_agent_langgraph.py` - 動的コード生成機能を備えた LangGraph 駆動のリサーチエージェント

## 前提条件

### Python 依存関係
```bash
pip install -r requirements.txt
```

必要なパッケージ: fastapi, uvicorn, rich, boto3, bedrock-agentcore

### AWS 認証情報（S3 ストレージ用）
S3 録画ストレージのために AWS 認証情報が設定されていることを確認：
```bash
aws configure
```

## サンプルの実行

### ブラウザライブビューア
`02-Agent-Core-browser-tool` ディレクトリから：
```bash
python -m interactive_tools.run_live_viewer
```

### ダイナミックリサーチエージェント
`02-Agent-Core-browser-tool` ディレクトリから：
```bash
python -m interactive_tools.dynamic_research_agent_langgraph
```

### Bedrock モデルアクセス
ダイナミックリサーチエージェントの例では Amazon Bedrock の Claude モデルを使用します：
- AWS アカウントで Anthropic Claude モデルへのアクセスが必要
- デフォルトモデルは `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- `dynamic_research_agent_langgraph.py` の以下の行を変更することでモデルを変更可能：
  ```python
  # DynamicResearchAgent.__init__() の38行目
  self.llm = ChatBedrockConverse(
      model="global.anthropic.claude-haiku-4-5-20251001-v1:0", # <- 希望のモデルに変更
      region_name=region
  )
  ```
- [Amazon Bedrock コンソール](https://console.aws.amazon.com/bedrock/home#/modelaccess)でモデルアクセスをリクエスト

### セッション再生
`02-Agent-Core-browser-tool/interactive_tools` ディレクトリから：
```bash
python -m live_view_sessionreplay.browser_interactive_session
```

## ブラウザライブビューア

Amazon DCV 技術を使用したリアルタイムブラウザ表示機能。

### 機能

**表示サイズコントロール**
- 1280×720 (HD)
- 1600×900 (HD+) - デフォルト
- 1920×1080 (Full HD)
- 2560×1440 (2K)

**セッションコントロール**
- 制御を取得: 自動化を無効にして手動で操作
- 制御を解放: 自動化に制御を返す

### 設定
- カスタムポート: `BrowserViewerServer(browser_client, port=8080)`

## ブラウザセッション録画と再生

デバッグ、テスト、デモンストレーション目的でブラウザセッションを録画および再生。

### 重要な制限事項
このツールはビデオストリームではなく、rrweb を使用して DOM イベントを録画します：
- 実際のブラウザコンテンツ（DCV キャンバス）は黒いボックスとして表示される場合があります
- ピクセルパーフェクトなビデオ録画には、画面録画ソフトウェアを使用してください

## トラブルシューティング

### DCV SDK が見つからない
DCV SDK ファイルが `interactive_tools/static/dcvjs/` に配置されていることを確認

### ブラウザセッションが表示されない
- ブラウザコンソール（F12）でエラーを確認
- AWS 認証情報に適切な権限があることを確認

### 再生中に録画が見つからない
- 録画が保存されたときに表示された正確なパスを確認
- S3 録画の場合、完全な S3 URL を使用
- `aws s3 ls` または `ls` コマンドを使用してファイルが存在することを確認

### S3 アクセスエラー
- AWS 認証情報が設定されていることを確認
- S3 操作の IAM 権限を確認
- バケット名がグローバルに一意であることを確認

## パフォーマンスの考慮事項
- 録画はブラウザパフォーマンスにオーバーヘッドを追加
- ファイルサイズは通常 1 分あたり 1-10MB
- S3 アップロードは録画停止後に発生
- 再生には最初にファイル全体のダウンロードが必要

## アーキテクチャノート
- ライブビューアは FastAPI を使用して署名付き DCV URL を提供
- 録画は rrweb ライブラリを介して DOM イベントをキャプチャ
- 再生は rrweb-player を使用
- すべてのコンポーネントは同じ BrowserClient インスタンスを共有
- モジュラー設計により各コンポーネントの独立した使用が可能
