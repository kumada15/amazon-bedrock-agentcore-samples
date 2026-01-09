# マーケットインテリジェンスプラットフォーム

Amazon Bedrock AgentCore を活用したエンタープライズグレードの自動 Web インテリジェンス収集システムで、LangGraph と Strands の 2 つの異なるアーキテクチャアプローチを示しています。

## ⚠️ コード構造に関する重要な注意

このリポジトリには、基本的なアーキテクチャの違いによりほとんどのコードを共有できない **2 つの独立した実装** が含まれています：

- **LangGraph** (`/langgraph`) - 明示的な状態管理を備えたグラフベースのワークフロー
- **Strands** (`/strands`) - 組み込み AWS 統合を備えたエージェントベースのツールオーケストレーション

実装間で共有されるのは、設定ファイルとユーティリティのみです。異なる非同期処理、LLM 呼び出しパターン、状態管理アプローチにより、それぞれが独自のバージョンのコアコンポーネントを持っています。

## 🏗️ アーキテクチャ概要

![Market Intelligence Platform Architecture](./images/highlevel_arch.png)

## 🏗️ アーキテクチャの違い

### なぜ別々の実装なのか？

2 つのフレームワークは以下の点で互換性のないアプローチを持っています：

1. **イベントループ管理**
   - LangGraph: 標準的な async/await パターン
   - Strands: nest_asyncio とスレッドセーフラッパーが必要

2. **LLM 呼び出し**
   - LangGraph: langchain メソッド（`await llm.ainvoke()`）を使用
   - Strands: Bedrock への直接 boto3 呼び出し

3. **状態管理**
   - LangGraph: グラフノードを持つカスタム TypedDict 状態
   - Strands: 安全なアクセサを持つ組み込み agent.state

4. **ツール実行**
   - LangGraph: グラフノード内でツールを呼び出し
   - Strands: 特別な処理を持つデコレートされた関数としてのツール

## 📁 プロジェクト構造

```
enterprise-web-intelligence-agent/
├── shared/                     # 最小限の共有コンポーネント
│   ├── config.py              # 設定（共有）
│   ├── cleanup_resources.py   # AWS クリーンアップスクリプト（共有）
│   └── utils/
│       └── s3_datasource.py   # S3 リプレイユーティリティ（共有）
│
├── langgraph/                  # 完全な LangGraph 実装
│   ├── agent.py               # グラフベースのオーケストレーション
│   ├── browser_tools.py      # オリジナルの非同期バージョン
│   ├── analysis_tools.py     # LangChain LLM 呼び出し
│   ├── run_agent.py          # エントリーポイント
│   ├── requirements.txt      # LangGraph 依存関係
│   └── utils/
│       └── imports.py        # LangGraph 用パスセットアップ
│
└── strands/                    # 完全な Strands 実装
    ├── agent.py               # エージェントベースのオーケストレーション
    ├── browser_tools.py      # イベントループ用に修正
    ├── analysis_tools.py     # 直接 boto3 呼び出し
    ├── run_agent.py          # エントリーポイント
    ├── requirements.txt      # Strands 依存関係
    └── utils/
        └── imports.py        # Strands 用パスセットアップ
```

## 🚀 インストール

### 前提条件
- Bedrock アクセスを持つ AWS アカウント
- Bedrock で有効化された Claude 3.7 Sonnet モデルへのアクセス（us-west-2 リージョン）
- 適切な権限を持つ IAM ロール
- 録画用 S3 バケット（オプション - 指定されない場合は自動的に作成）

### 環境セットアップ

```bash
# リポジトリをクローン
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
cd amazon-bedrock-agentcore-samples/02-use-cases/enterprise-web-intelligence-agent
```

### LangGraph バージョン
```bash
cd langgraph
uv pip install -r requirements.txt
```

### Strands バージョン
```bash
cd strands
uv pip install -r requirements.txt
```

## 🔧 設定

両方の実装は同じ設定を共有します。S3 バケットはオプションです - 指定されない場合、エージェントは AWS アカウント ID を使用して自動的に作成します：

```bash
# 必須
export AWS_REGION="us-west-2"
export AWS_ACCOUNT_ID="your-account-id"  # 自動バケット作成に必要

# 必須 - BedrockAgentCore 権限を持つ IAM ロール
export RECORDING_ROLE_ARN="arn:aws:iam::your-account-id:role/BedrockAgentCoreRole"

# オプション - S3 バケット（指定されない場合は bedrock-agentcore-recordings-{account-id} として作成）
export S3_RECORDING_BUCKET="your-recordings-bucket"

# オプション - カスタムポート
export LIVE_VIEW_PORT=8000  # デフォルト: 8000
export REPLAY_VIEWER_PORT=8001  # デフォルト: 8001
```

### IAM ロール要件

IAM ロールには以下の権限が必要です：

- BedrockAgentCore ブラウザ操作（作成、削除、一覧表示）
- 録画バケットへの S3 読み取り/書き込みアクセス
- Bedrock モデル呼び出し権限

## 📊 実装比較

| コンポーネント | LangGraph | Strands |
|-------------|-----------|---------|
| **browser_tools.py** | オリジナルの async/await | nest_asyncio で修正 |
| **analysis_tools.py** | LangChain LLM 呼び出し | 直接 boto3 呼び出し |
| **イベントループ** | 標準 asyncio | スレッドセーフラッパー |
| **LLM 呼び出し** | `await llm.ainvoke()` | `bedrock_client.invoke_model()` |
| **状態アクセス** | 直接辞書アクセス | デフォルト付き安全なゲッター |
| **エラー処理** | グラフノード境界 | ツールレベルの try/catch |
| **セッション永続化** | カスタム実装 | 組み込み S3SessionManager |
| **コード再利用** | 約 20% 共有 | 約 20% 共有 |

## ⚙️ 各実装の実行

### LangGraph
```bash
cd langgraph
python run_agent.py
# 競合他社と分析オプションを選択
```

### Strands
```bash
cd strands
python run_agent.py
# 競合他社と分析オプションを選択
```

## 🔍 コードの主な違い

### 例：LLM 呼び出し

**LangGraph** (`langgraph/browser_tools.py`):
```python
response = await self.llm.ainvoke([HumanMessage(content=prompt)])
```

**Strands** (`strands/browser_tools.py`):
```python
response = bedrock_client.invoke_model(
    modelId=self.config.llm_model_id,
    body=json.dumps(native_request)
)
```

### 例：イベントループ処理

**LangGraph**: 標準 async
```python
async def analyze_competitor(self, state):
    result = await self.browser_tools.navigate_to_url(url)
```

**Strands**: スレッドセーフ実行
```python
future = asyncio.run_coroutine_threadsafe(
    self._analyze_website_async(name, url),
    self.browser_loop
)
return future.result(timeout=120)
```

### 例：状態管理

**LangGraph**: 直接状態辞書
```python
state["competitor_data"][name] = extracted_data
current_index = state["current_competitor_index"]
```

**Strands**: デフォルト付き安全な状態アクセサ
```python
competitor_data = self._safe_state_get("competitor_data", {})
competitor_data[name] = extracted_data
self.agent.state.set("competitor_data", competitor_data)
```

## クリーンアップ

#### 自動クリーンアップ
両方の実装は、プログラム終了時にリソースを自動的にクリーンアップします：

- BedrockAgentCore ブラウザが削除される
- Code Interpreter セッションが終了する
- Playwright 接続が閉じられる

#### 手動クリーンアップ
孤立したリソースや古い録画用：

```bash
# 停止したブラウザをクリーンアップ（$0.10/時間の主なコスト要因）
python shared/cleanup_resources.py

# 古い S3 録画も削除
python shared/cleanup_resources.py --delete-old-recordings

# cron で自動クリーンアップをスケジュール
crontab -e
# 追加: 0 2 * * * cd /path/to/project && python shared/cleanup_resources.py
```

## 🚀 機能

両方の実装は以下を提供します：

- **ライブブラウザ表示:** エージェントのナビゲーションをリアルタイムで監視
- **インタラクティブ制御:** 自動化中に制御を取得/解放
- **セッション録画:** S3 に保存される完全な監査証跡
- **セッションリプレイ:** 過去の分析のタイムトラベルデバッグ
- **ネットワークインターセプト:** 隠れた API エンドポイントを発見
- **LLM 抽出:** Claude 3.7 Sonnet がページコンテキストを理解
- **Code Interpreter:** 分析用の安全な Python サンドボックス
- **並列処理:** 複数の競合他社を同時に分析

## 🤝 コントリビューション

コントリビューション時には、以下に注意してください：
- `browser_tools.py` または `analysis_tools.py` への変更は、各実装に対して個別に行う必要があります
- 両方の実装を独立してテストしてください
- 両方のフレームワークで動作する場合のみ、共有ファイルを更新してください


## 🆘 サポート

- LangGraph の問題: グラフ実行と状態管理を確認
- Strands の問題: イベントループ処理とツール登録を確認
- 両方: AWS 認証情報と Bedrock アクセスを確認

---

**注意**: これは 2 つのアーキテクチャアプローチを示すデモプロジェクトです。ニーズに最も適した実装を選択してください：
- **LangGraph**: 明示的な制御を持つ複雑なワークフローに最適
- **Strands**: AWS 統合を持つ迅速な開発に最適
