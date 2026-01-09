# プロジェクト構造

## 📁 整理されたファイル構造

```
strands-agents/agent-core/code-interpreter/
├── 📂 backend/                    # FastAPI バックエンド
│   ├── main.py                   # メインアプリケーションサーバー
│   └── requirements.txt          # Python 依存関係
│
├── 📂 frontend/                   # React フロントエンド
│   ├── 📂 src/
│   │   ├── App.js               # メイン React アプリケーション
│   │   └── 📂 components/       # React コンポーネント
│   │       ├── CodeEditor.js    # Monaco コードエディター
│   │       ├── CodeDisplay.js   # コード出力表示
│   │       ├── ExecutionResults.js # 実行結果
│   │       └── SessionHistory.js   # セッション管理
│   ├── 📂 public/               # 静的アセット
│   ├── package.json             # Node.js 依存関係
│   └── package-lock.json        # 依存関係ロックファイル
│
├── 📂 tests/                      # テストスイート
│   ├── run_all_tests.py         # 包括的テストランナー
│   ├── verify_setup.py          # セットアップ検証
│   ├── test_model_fallback.py   # モデルフォールバックテスト
│   ├── test_execution_fix.py    # 実行結果テスト
│   └── debug_code_generation.py # コード生成デバッグ
│
├── 📂 docs/                       # ドキュメント
│   ├── ARCHITECTURE.md          # システムアーキテクチャ
│   ├── SETUP.md                 # セットアップ手順
│   ├── OVERVIEW.md              # プロジェクト概要
│   └── [historical docs]        # 過去のイテレーションドキュメント
│
├── 📂 venv/                       # Python 仮想環境
│   ├── bin/                     # 実行ファイル
│   ├── lib/                     # Python パッケージ
│   └── ...
│
├── 🔧 設定ファイル
│   ├── .env                     # 環境変数
│   ├── .env.example             # 環境テンプレート
│   └── .gitignore               # Git 除外ルール
│
├── 🚀 スクリプト
│   ├── setup.sh                 # 自動セットアップ
│   ├── start.sh                 # アプリケーション起動
│   └── cleanup.sh               # クリーンアップスクリプト
│
├── 📋 ドキュメント
│   ├── README.md                # メインドキュメント
│   └── PROJECT_STRUCTURE.md     # このファイル
│
└── 📊 ログ（生成）
    ├── backend.log              # バックエンドログ
    ├── frontend.log             # フロントエンドログ
    └── *.pid                    # プロセス ID ファイル
```

## 🎯 主要ディレクトリ

### `/backend/`
**目的**: Strands-Agents 統合を持つ FastAPI サーバー
- **main.py**: REST API と WebSocket ハンドラーを持つコアアプリケーション
- **requirements.txt**: strands-agents と bedrock-agentcore を含む Python 依存関係

### `/frontend/`
**目的**: AWS Cloudscape UI を持つ React アプリケーション
- **src/App.js**: タブ付きインターフェースを持つメインアプリケーション
- **src/components/**: 再利用可能な React コンポーネント
- **package.json**: Node.js 依存関係とスクリプト

### `/tests/`
**目的**: 包括的なテストと検証
- **run_all_tests.py**: すべてのコンポーネント用の完全なテストスイート
- **verify_setup.py**: クイックセットアップ検証
- **test_*.py**: 特定のコンポーネントテスト
- **debug_*.py**: デバッグユーティリティ

### `/docs/`
**目的**: プロジェクトドキュメント
- **ARCHITECTURE.md**: システム設計とコンポーネントの詳細
- **SETUP.md**: 詳細なセットアップ手順
- **OVERVIEW.md**: プロジェクト概要とユースケース

## 🔧 設定

### 環境変数 (`.env`)
```bash
# AWS 設定
AWS_PROFILE=default
AWS_REGION=us-east-1

# アプリケーション設定
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
REACT_APP_API_URL=http://localhost:8000
```

### スクリプト
- **setup.sh**: 自動環境セットアップ
- **start.sh**: バックエンドとフロントエンドの起動
- **cleanup.sh**: プロセスと一時ファイルのクリーンアップ

## 🧪 テスト構造

### テストカテゴリ
1. **環境テスト**: 依存関係、AWS 設定、ファイル構造
2. **モデルテスト**: AI モデルの初期化とフォールバック
3. **エージェントテスト**: Strands-Agents 統合
4. **API テスト**: REST エンドポイントと WebSocket ハンドラー
5. **統合テスト**: エンドツーエンド機能

### テストの実行
```bash
# クイック検証
python tests/verify_setup.py

# 包括的テスト
python tests/run_all_tests.py

# 特定のコンポーネントテスト
python tests/test_model_fallback.py
```

## 📊 ログと監視

### ログファイル
- **backend.log**: FastAPI サーバーログ、エージェント応答、エラー
- **frontend.log**: React 開発サーバーログ
- ***.pid**: クリーンアップ用のプロセス ID ファイル

### ヘルス監視
- **ヘルスエンドポイント**: `GET /health` - システムステータス
- **エージェントステータス**: `GET /api/agents/status` - エージェント情報
- **モデル情報**: 現在のモデルとフォールバックステータス

## 🚀 クイックコマンド

### セットアップと起動
```bash
./setup.sh          # 初期セットアップ
./start.sh           # アプリケーション起動
./cleanup.sh         # クリーンアップとリセット
```

### テスト
```bash
python tests/verify_setup.py      # セットアップ検証
python tests/run_all_tests.py     # すべてのテスト実行
```

### 開発
```bash
# バックエンドのみ
source venv/bin/activate
python backend/main.py

# フロントエンドのみ
cd frontend && npm start
```

## 📋 ファイル構成の利点

### ✅ **保守性の向上**
- 関心事の明確な分離
- 関連ファイルの論理的なグループ化
- 簡単なナビゲーションと発見

### ✅ **より良いテスト**
- 集中化されたテストスイート
- 包括的なカバレッジ
- 簡単なテスト実行

### ✅ **強化されたドキュメント**
- 整理されたドキュメント構造
- 明確なセットアップ手順
- アーキテクチャ概要

### ✅ **効率化された開発**
- 自動化されたセットアップとクリーンアップ
- 一貫したプロジェクト構造
- 新しい開発者の簡単なオンボーディング

この整理された構造は、AgentCore コードインタープリターの開発、テスト、デプロイメントのための堅固な基盤を提供します。
