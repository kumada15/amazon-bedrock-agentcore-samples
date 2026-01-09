# Text to Python IDE

**Strands-Agents** フレームワークと **AWS Bedrock AgentCore** を組み合わせて、インテリジェントな Python コード開発を実現する、強力な AI 駆動コード生成および実行プラットフォームです。

## 概要

Text to Python IDE は、ユーザーが以下を行えるフルスタックアプリケーションです：

- 高度な AI モデルを使用して自然言語の説明から **Python コードを生成**
- AWS マネージドのサンドボックス環境で**コードを安全に実行**
- 生成されたコードでデータ分析と処理のために **CSV ファイルをアップロード**
- モダンな Web インターフェースを通じて**結果と対話**
- 永続的な会話履歴で**セッションを管理**

### 主な機能

- Claude Haiku 4.5 と Nova Premier を使用した **AI 駆動コード生成**
- AWS Bedrock AgentCore 経由の**リアルタイムコード実行**
- データ分析ワークフロー用の **CSV ファイルアップロードと統合**
- 長時間実行操作の視覚的フィードバック付き**実行タイマー**
- 最大限の信頼性のための**インテリジェントモデルフォールバック**
- React と AWS Cloudscape で構築された**モダン Web インターフェース**
- 実行履歴付き**セッション管理**
- 分離された AWS 環境での**セキュアな実行**
- 既存の Python ファイルと CSV データ用の**ファイルアップロードサポート**
- キャッシングとコネクションプーリングによる**パフォーマンス最適化**
- 自動エンドツーエンド検証による**包括的なテスト**
- matplotlib/seaborn を使用したデータ可視化用の**チャートレンダリング**

## アーキテクチャ

![Architecture Diagram](./img/agentcore_aws_architecture_simple.png)

### コンポーネントの詳細

#### **フロントエンド（React + AWS Cloudscape）**
- **Code Generator タブ**: 自然言語から Python コードへの変換
- **Code Editor タブ**: シンタックスハイライト付き Monaco ベースエディター
- **Execution Results タブ**: エラー処理付きフォーマットされた出力表示
- **Session History タブ**: 実行と会話の履歴を表示

#### **バックエンド（FastAPI + Strands-Agents）**
- **Code Generator Agent**: インテリジェントなコード生成に Claude Haiku 4.5 を使用
- **Code Executor Agent**: 安全なコード実行のために AgentCore と統合
- **Session Management**: RESTful API と WebSocket サポート
- **Model Fallback**: AI モデル間の自動フェイルオーバー

#### **AI モデル（AWS Bedrock）**
- **プライマリ**: Claude Haiku 4.5（Inference Profile）- `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- **フォールバック**: Nova Premier（Inference Profile）- `us.amazon.nova-premier-v1:0`
- **セーフティネット**: Claude 3.5 Sonnet - `anthropic.claude-3-5-sonnet-20241022-v2:0`

#### **実行環境（AgentCore）**
- **サンドボックス Python 環境**: AWS での分離された実行
- **リアルタイム結果**: ストリーミング出力とエラー処理
- **セッション永続化**: 実行間で状態を維持

## クイックスタート

### 前提条件

- pip 付き **Python 3.8+**
- npm 付き **Node.js 16+**
- Bedrock アクセス付き **AWS アカウント**
- **AWS CLI** 設定済みまたは認証情報が利用可能

### 1. セットアップと起動

アプリケーションには自動セットアップが含まれています - 起動スクリプトを実行するだけです：

```bash
# アプリケーションを起動（自動セットアップを含む）
./start.sh

# スクリプトは自動的に以下を行います：
# - 必要に応じて Python 仮想環境を作成
# - すべての依存関係をインストール
# - .env 設定ファイルを作成
# - バックエンドとフロントエンドの両サーバーを起動
```

### 2. 環境の設定（オプション）

AWS 認証情報をカスタマイズする必要がある場合は、`.env` ファイルを編集します：

```bash
# AWS 設定（いずれかの方法を選択）
AWS_PROFILE=your_profile_name          # 推奨

# アプリケーション設定
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
REACT_APP_API_URL=http://localhost:8000
```

### 3. アプリケーションへのアクセス

`./start.sh` 実行後、以下にアクセス：
- **フロントエンド**: http://localhost:3000
- **バックエンド API**: http://localhost:8000

### 4. セットアップの確認（オプション）

```bash
# セットアップを確認（オプション - start.sh が自動的に行います）
python tests/verify_setup.py

# 包括的なテストを実行
python tests/run_all_tests.py
```

## 使用方法

### コード生成
1. **Code Generator** タブに移動
2. **オプション**: データ分析タスク用に「Upload CSV File」ボタンで CSV ファイルをアップロード
3. 自然言語の説明を入力（例：「フィボナッチ数を計算する関数を作成」や「アップロードされた CSV データを分析して可視化を作成」）
4. **Generate Code** をクリック
5. **Code Editor** タブで生成されたコードを確認

### CSV ファイル統合
1. **Code Generator** タブで **Upload CSV File** をクリック
2. CSV ファイルを選択（.csv 拡張子が必要）
3. ファイルはコード生成で使用可能になります
4. プロンプトでデータ分析、ファイル、CSV について言及すると、AI は自動的にアップロードされたデータを組み込みます
5. プロンプトでファイルに言及したが CSV をアップロードしていない場合、アップロードを促されます

### コード実行
1. **Code Editor** タブでコードを確認または修正
2. 即時実行には **Execute Code** をクリック
3. ユーザー入力が必要なコードには **Interactive Execute** をクリック
4. **Execution Results** タブで結果を表示

### ファイルアップロード
1. **Code Editor** タブでファイルアップロードコンポーネントを使用
2. `.py` または `.txt` ファイルを選択
3. ファイル内容がエディターにロードされます
4. 必要に応じて実行または修正

## 開発

### プロジェクト構成

```
├── backend/                 # FastAPI バックエンド
│   ├── main.py             # メインアプリケーション
│   └── requirements.txt    # Python 依存関係
├── frontend/               # React フロントエンド
│   ├── src/
│   │   ├── App.js         # メインアプリケーション
│   │   └── components/    # React コンポーネント
│   └── package.json       # Node 依存関係
├── tests/                  # テストスクリプト
│   ├── run_all_tests.py   # 包括的なテストスイート
│   └── verify_setup.py    # セットアップ確認
├── docs/                   # ドキュメント
├── .env                    # 環境設定
├── setup.sh               # セットアップスクリプト
└── start.sh               # 起動スクリプト
```

### テストの実行

```bash
# セットアップを確認
python tests/verify_setup.py

# 包括的なテストを実行
python tests/run_all_tests.py

# 自動エンドツーエンドテストを実行（ユーザー入力不要）
python tests/automated_e2e_test.py

# 特定のコンポーネントをテスト
python -c "from tests.run_all_tests import TestRunner; runner = TestRunner(); runner.test_code_generation_api()"
```

### 開発モード

```bash
# バックエンドのみ
source venv/bin/activate
python backend/main.py

# フロントエンドのみ
cd frontend
npm start

# 自動リロード付きウォッチモード
# バックエンド: uvicorn --reload を使用
# フロントエンド: npm start（ホットリロード含む）
```

## 設定

### 必要な AWS 権限

AWS ユーザー/ロールには以下の権限が必要です：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:StartCodeInterpreterSession",
                "bedrock-agentcore:StopCodeInterpreterSession",
                "bedrock-agentcore:InvokeCodeInterpreter"
            ],
            "Resource": "*"
        }
    ]
}
```

またはマネージドポリシーを使用: `BedrockAgentCoreFullAccess`

### モデル設定

アプリケーションは利用可能な最適なモデルを自動的に選択します：

1. **Claude Haiku 4.5**（Inference Profile）- 第一選択
2. **Nova Premier**（Inference Profile）- 自動フォールバック
3. **Claude 3.5 Sonnet** - セーフティフォールバック

### 環境変数

| 変数 | 説明 | デフォルト |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS プロファイル名 | - |
| `AWS_REGION` | AWS リージョン | `us-east-1` |
| `BACKEND_HOST` | バックエンドホスト | `0.0.0.0` |
| `BACKEND_PORT` | バックエンドポート | `8000` |
| `REACT_APP_API_URL` | フロントエンド API URL | `http://localhost:8000` |

#### タイムアウト設定

| 変数 | 説明 | デフォルト | 推奨最大値 |
|----------|-------------|---------|-----------------|
| `AWS_READ_TIMEOUT` | AWS Bedrock 読み取りタイムアウト（秒） | `600` | `600` |
| `AWS_CONNECT_TIMEOUT` | AWS 接続タイムアウト（秒） | `120` | `300` |
| `AWS_MAX_RETRIES` | 最大リトライ回数 | `5` | `10` |
| `AGENTCORE_SESSION_TIMEOUT` | AgentCore セッションタイムアウト（秒） | `1800` | `1800` |
| `REACT_APP_EXECUTION_TIMEOUT_WARNING` | UI 警告しきい値（秒） | `300` | - |
| `REACT_APP_MAX_EXECUTION_TIME` | UI 最大時間表示（秒） | `600` | - |

**注意**: これらのタイムアウト値は、データ分析、機械学習、可視化タスクを含む複雑なコード実行に最適化されています。

## クリーンアップ

```bash
# アプリケーションを停止
# start.sh を実行しているターミナルで Ctrl+C を押す

# またはプロセスを手動で停止
lsof -ti:8000 | xargs kill -9  # バックエンド
lsof -ti:3000 | xargs kill -9  # フロントエンド

# 一時ファイルをクリーンアップ
rm -f backend.log frontend.log *.pid
```

## トラブルシューティング

### よくある問題

**バックエンドが起動しない:**
- AWS 認証情報を確認: `aws sts get-caller-identity`
- 依存関係を確認: `python tests/verify_setup.py`
- ログを確認: `tail -f backend.log`

**フロントエンドが起動しない:**
- 依存関係をインストール: `cd frontend && npm install`
- Node バージョンを確認: `node --version`（16+ が必要）
- キャッシュをクリア: `npm start -- --reset-cache`

**コード生成が失敗する:**
- Bedrock アクセスを確認: AWS 権限を確認
- モデルの利用可能性をテスト: `python tests/run_all_tests.py`
- リージョンを確認: モデルがリージョンで利用可能か確認

**コード実行が失敗する:**
- AgentCore 権限を確認: `BedrockAgentCoreFullAccess`
- AgentCore を直接テスト: `tests/` 内のテストスクリプトを参照
- セッション制限を確認: AgentCore には同時セッション制限があります

### ヘルプを得る

1. **診断を実行**: `python tests/verify_setup.py`
2. **ログを確認**: `backend.log` と `frontend.log`
3. **コンポーネントをテスト**: `python tests/run_all_tests.py`
4. **AWS セットアップを確認**: `aws bedrock list-foundation-models`

## ライセンス

このプロジェクトは Strands-Agents エコシステムの一部です。メインプロジェクトのライセンスを参照してください。

---

**AI でコーディングを始める準備はできましたか？ `./start.sh` を実行して http://localhost:3000 にアクセスしてください**
