# Strands 保険エージェント

ローカル MCP サーバーに接続して保険情報と見積もりを提供する Strands で構築されたインタラクティブエージェントです。

![Strands 保険エージェントデモ](images/strands_local_agent_conversation.gif)

## 概要

このプロジェクトは、MCP（Model Context Protocol）サーバーと Strands Agents を使用してインタラクティブな保険アシスタントを作成する方法を示します。エージェントは AWS Bedrock を通じて Claude 3.7 Sonnet を活用し、MCP サーバーを通じて公開されたローカル保険 API ツールに接続します。

## 前提条件

- Python 3.10 以上
- Claude 3.7 Sonnet への Bedrock アクセスがある AWS アカウント
- http://localhost:8000/mcp で実行中のローカル MCP サーバー
- http://localhost:8001 で実行中の保険 API

## プロジェクト構造

```
strands-insurance-agent/
├── interactive_insurance_agent.py  # メインのインタラクティブエージェント
├── strands_insurance_agent.py      # 非インタラクティブエージェント
├── requirements.txt                # プロジェクト依存関係
├── strands_local_agent.png         # エージェント動作のスクリーンショット
└── README.md                       # このファイル
```

## セットアップ手順

### 1. リポジトリのクローン（まだの場合）

```bash
git clone <repository-url>
cd local_prototype/strands-insurance-agent
```

### 2. 仮想環境のセットアップ

```bash
python -m venv venv
source venv/bin/activate  # Windows の場合: venv\Scripts\activate
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. AWS 認証情報のセットアップ

このエージェントは AWS Bedrock を使用して Claude 3.7 Sonnet にアクセスします。AWS 認証情報が正しく設定されていることを確認してください：

1. AWS CLI をインストール（まだの場合）：
   ```bash
   pip install awscli
   ```

2. [リンク](https://strandsagents.com/latest/documentation/docs/user-guide/quickstart/#configuring-credentials)を参照して認証情報を設定


### 5. 必要なサービスの起動

エージェントを実行する前に、これらのサービスが実行されていることを確認してください：

1. **保険 API**：
   ```bash
   cd ../insurance_api
   python -m uvicorn server:app --port 8001
   ```

2. **MCP サーバー**：
   ```bash
   cd ../native_mcp_server
   python server.py
   ```

## インタラクティブエージェントの実行

すべての設定が完了したら、インタラクティブエージェントを実行：

```bash
python interactive_insurance_agent.py
```

これにより、保険商品について質問したりパーソナライズされた見積もりを取得できるインタラクティブなチャットセッションが開始されます。エージェントはセッション中ローカルチャット履歴を維持し、自然な会話の流れとフォローアップの質問を可能にします。

### チャット履歴

ローカルチャット履歴機能：
- セッション中のすべての会話ターンをメモリに保存
- 以前のインタラクションに関するコンテキストをモデルに提供
- エージェントがより関連性の高いパーソナライズされた応答を提供可能
- 特定の顧客や車両について話し合う際の連続性を維持
- プログラム終了時にクリア（セッション間の永続的なストレージなし）

## 機能

インタラクティブ保険エージェントには以下の機能があります：

1. **インタラクティブチャットインターフェース**：
   - 絵文字で強化されたコンソールインターフェース
   - 自然な会話の流れ
   - コンテキスト保持付きのコマンド履歴

2. **保険 API 統合**：
   - 顧客情報の検索
   - 車両情報の取得
   - 保険見積もりの生成
   - 車両安全評価

3. **高度な機能**：
   - 包括的なログ（コンソールとファイルベース）
   - エラーハンドリングとリカバリー
   - 読みやすさのためのレスポンスフォーマット
   - ツール使用状況の追跡

4. **ローカルチャット履歴と会話コンテキスト**：
   - すべての会話ターンのメモリ内履歴を維持
   - シームレスなフォローアップのためにセッション全体で持続
   - エージェントが以前の質問と回答を参照可能
   - クエリ間で顧客と車両の詳細を記憶
   - 会話の流れに基づいたコンテキスト応答を提供

## クエリ例

以下のようなクエリを試すことができます：

- "顧客 cust-001 についてどんな情報がありますか？"
- "2020 年の Toyota Camry について教えてください"
- "顧客 ID cust-001 の 2020 年 Toyota Camry にはどんな保険オプションがありますか？"
- "Honda Civic の安全評価は？"
- "顧客 cust-002 の 2022 年 Ford F-150 の見積もりをください"

### チャット履歴を使用した会話例

エージェントは以前のコンテキストを記憶しているので、以下のような自然な会話ができます：

```
あなた: 顧客 cust-001 についてどんな情報がありますか？
エージェント: [John Smith に関する情報を返す]

あなた: 彼はどんな車を持っていますか？
エージェント: [前のコンテキストを使用して John Smith について質問していることを理解]

あなた: 彼に 2023 年の Toyota RAV4 の見積もりをもらえますか？
エージェント: [顧客情報と新しい車両リクエストを組み合わせる]
```

このコンテキスト認識により、インタラクションがより自然で効率的になります。

## アーキテクチャ

Strands 保険エージェントは以下の間の橋渡しをします：

1. **ユーザー**（コンソールインターフェース経由）
2. **Strands Agent**（Claude 3.7 Sonnet を使用）
3. **MCP サーバー**（保険ツールを提供）
4. **保険 API**（実際のデータを提供）

質問をすると：
1. エージェントがそれをフォーマットして Strands 経由で Claude 3.7 に送信
2. Claude が質問に基づいて使用するツールを決定
3. エージェントが MCP サーバーを通じて必要な API 呼び出しを実行
4. 結果が収集、フォーマットされてユーザーに提示

## ログ

エージェントはすべてのインタラクションを以下に記録：
- コンソール（デフォルトで DEBUG レベル）
- ファイル（`insurance_agent.log` - ファイルログが有効な場合）

ログには以下が含まれます：
- ユーザー入力とエージェント応答
- ツール呼び出しとその引数
- レスポンス処理の詳細
- エラー情報

## トラブルシューティング

### よくある問題

1. **AWS 認証情報が見つからないか無効**
   - エラー: "Could not connect to the endpoint URL"
   - 解決策: AWS 認証情報とリージョンを確認

2. **MCP サーバーが実行されていない**
   - エラー: "Connection refused" when connecting to the MCP server
   - 解決策: http://localhost:8000/mcp で MCP サーバーを起動

3. **保険 API が実行されていない**
   - エラー: "Error connecting to auto insurance API"
   - 解決策: http://localhost:8001 で保険 API が実行されていることを確認

4. **レスポンス形式の問題**
   - エラー: エージェントがクリーンなテキストではなく生の JSON やリスト形式を表示
   - 解決策: 新しい Strands バージョンに合わせてレスポンスパーサーの更新が必要かもしれません

## ライセンス

このプロジェクトは Apache License 2.0 の下でライセンスされています - 詳細は [LICENSE](../../../../LICENSE) ファイルを参照してください。


## 注意

- MCP サーバー: LocalMCP FastMCP サーバーに基づく
- 保険 API: FastAPI で構築
- エージェントフレームワーク: Anthropic の Strands Agents
- LLM: AWS Bedrock 経由の Claude 3.7 Sonnet
