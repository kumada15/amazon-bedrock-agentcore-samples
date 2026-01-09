# AgentCore コードインタープリター

コード生成に **strands-agents** を、コード実行に **Amazon Bedrock AgentCore** を使用した **ハイブリッドアーキテクチャ** で構築された Python コード実行環境です。AWS Cloudscape デザインシステムを使用した React フロントエンドを備えています。

## アーキテクチャ

このアプリケーションは、**正しい AgentCore 統合** を備えた **ハイブリッドマルチエージェントアーキテクチャ** を使用します：

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────────┐
│   React UI      │    │   FastAPI        │    │   Hybrid Agent System   │
│   (Cloudscape)  │◄──►│   Backend        │◄──►│                         │
│                 │    │                  │    │  ┌─────────────────┐    │
└─────────────────┘    └──────────────────┘    │  │ Strands Agent   │    │
                                                │  │ Code Generator  │    │
                                                │  │ Claude 3.7      │    │
                                                │  └─────────────────┘    │
                                                │           │             │
                                                │           ▼             │
                                                │  ┌─────────────────┐    │
                                                │  │ Strands Agent   │    │
                                                │  │ + AgentCore     │    │
                                                │  │ CodeInterpreter │    │
                                                │  │ Tool            │    │
                                                │  └─────────────────┘    │
                                                └─────────────────────────┘
```

## モデル階層

アプリケーションは **推論プロファイル** を使用したインテリジェントなモデルフォールバックシステムを使用します：

1. **プライマリ**: Claude Haiku 4.5 (`global.anthropic.claude-haiku-4-5-20251001-v1:0`)
2. **フォールバック**: Nova Premier (`us.amazon.nova-premier-v1:0`)
3. **最終手段**: Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`)

システムはモデルの利用可能性を自動的に検出し、最適なオプションを選択します。

1. **コードジェネレーターエージェント**（Strands-Agents フレームワーク）：
   - strands-agents 経由で **Claude Haiku 4.5**（プライマリ）または **Nova Premier**（フォールバック）を使用
   - 自然言語からクリーンで実行可能な Python コードを生成
   - コード生成タスクに最適化
   - 説明なしの純粋な Python コードを返す

2. **コードエグゼキューターエージェント**（ハイブリッド Strands-Agents + AgentCore）：
   - **プライマリモード**: AgentCore CodeInterpreter ツールを備えた Strands-Agents エージェント
   - **モデル**: コードジェネレーターと同じ（Claude Haiku 4.5 → Nova Premier → Claude 3.5 Sonnet）
   - 実際のコード実行に AgentCore の `code_session` を使用
   - AWS 管理のサンドボックス環境で Python コードを実行

### AgentCore 統合パターン

アプリケーションは **公式 AgentCore サンプルパターン** に従います：

```python
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands import Agent, tool  # strands-agents パッケージ
import json

@tool
def execute_python(code: str, description: str = "") -> str:
    """公式サンプルに従って AgentCore を使用して Python コードを実行"""
    if description:
        code = f"# {description}\n{code}"

    with code_session(aws_region) as code_client:
        response = code_client.invoke("executeCode", {
            "code": code,
            "language": "python",
            "clearContext": False
        })

    for event in response["stream"]:
        return json.dumps(event["result"])

# AgentCore ツールを備えた Strands-Agents エージェント
agent = Agent(
    model=bedrock_model,
    tools=[execute_python],
    system_prompt="ツールを使用してコードを実行"
)
```

## 前提条件

- Python 3.8 以上
- Node.js 16 以上
- Bedrock アクセスのある AWS アカウント
- 設定済みの AWS CLI または AWS 認証情報

## インストール

1. **プロジェクトディレクトリにクローンして移動**：
   ```bash
   cd /Users/nmurich/strands-agents/agent-core/code-interpreter
   ```

2. **セットアップスクリプトを実行**：
   ```bash
   ./setup.sh
   ```

3. **AWS 認証情報を設定**：
   `.env` ファイルに AWS 認証情報を編集：
   ```bash
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_access_key_here
   AWS_SECRET_ACCESS_KEY=your_secret_key_here
   ```

## 使用方法

### クイックスタート

単一のコマンドでバックエンドとフロントエンドを実行：
```bash
./start.sh
```

以下が起動されます：
- バックエンド API サーバー（`http://localhost:8000`）
- React フロントエンド（`http://localhost:3000`）

### 手動起動

**バックエンド**：
```bash
source venv/bin/activate
cd backend
python main.py
```

**フロントエンド**：
```bash
cd frontend
npm start
```

## アプリケーション機能

### 1. コード生成
- コードで何を行いたいかを説明する自然言語プロンプトを入力
- 「Generate Code」をクリックして Strands Agent 経由で Claude Haiku 4.5 を使用して Python コードを作成
- **生成されたコードは自動的にコードエディターにロード**
- 実行または編集前に生成されたコードをプレビュー
- すぐに実行するか、実行前に編集するかを選択

### 2. コードエディター
- Python シンタックスハイライト付き Monaco エディター
- **生成されたコードで自動的にポピュレート**
- 既存の Python ファイルをアップロード
- 生成またはアップロードされたコードを編集
- コードが生成されたときの視覚的インジケーター
- **入力処理付きのインタラクティブ実行サポート**
- ワンクリックでコードを実行

### 3. インタラクティブコード実行
- インタラクティブコード（input() 呼び出し）の**自動検出**
- 必要な入力を識別し値を提案する**コード分析**
- 実行前に入力を提供する**インタラクティブ実行モーダル**
- インタラクティブコードのテスト用の**事前提供入力シミュレーション**
- 複雑なインタラクティブシナリオ（ループ、条件分岐）のサポート
- インタラクティブ実行の詳細を示す**視覚的インジケーター**

### 4. 実行結果
- シンタックスハイライト付きのフォーマットされた表示で実行出力を表示
- 詳細なエラーメッセージと適切なスタイリングによるエラーハンドリング
- 組み込みのコピー機能でクリップボードに出力をコピー
- 提供された入力を示す**インタラクティブ実行の詳細**
- コードを簡単に再実行
- 成功した実行とエラーの明確な区別

### 5. セッション履歴
- エージェント帰属付きですべての生成コードとプロンプトを追跡
- タイムスタンプ付きで実行履歴を表示
- 入力詳細付きの**インタラクティブ実行追跡**
- 以前のコードスニペットを再実行
- アプリケーション使用中のセッション永続化
- どのエージェント（Strands vs AgentCore）が各操作を処理したか確認

## API エンドポイント

### コード生成
```http
POST /api/generate-code
Content-Type: application/json

{
  "prompt": "フィボナッチ数を計算する関数を作成",
  "session_id": "optional-session-id"
}
```

### コード実行
```http
POST /api/execute-code
Content-Type: application/json

{
  "code": "print('Hello, World!')",
  "session_id": "optional-session-id",
  "interactive": false,
  "inputs": ["input1", "input2"]
}
```

### インタラクティブコード分析
```http
POST /api/analyze-code
Content-Type: application/json

{
  "code": "name = input('Your name: ')",
  "session_id": "optional-session-id"
}
```

### ファイルアップロード
```http
POST /api/upload-file
Content-Type: application/json

{
  "filename": "script.py",
  "content": "# Python code content",
  "session_id": "optional-session-id"
}
```

### セッション履歴
```http
GET /api/session/{session_id}/history
```

## 設定

### 環境変数

| 変数 | 説明 | デフォルト |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS CLI プロファイル名（推奨） | `default` |
| `AWS_REGION` | Bedrock 用 AWS リージョン | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | AWS アクセスキー（フォールバック） | プロファイルがない場合は必須 |
| `AWS_SECRET_ACCESS_KEY` | AWS シークレットキー（フォールバック） | プロファイルがない場合は必須 |
| `BACKEND_HOST` | バックエンドサーバーホスト | `0.0.0.0` |
| `BACKEND_PORT` | バックエンドサーバーポート | `8000` |
| `REACT_APP_API_URL` | フロントエンド API URL | `http://localhost:8000` |

### AWS 認証優先順位

アプリケーションは以下の認証優先順位を使用：

1. **AWS プロファイル**（推奨）：`.env` ファイルの `AWS_PROFILE` を使用
2. **アクセスキー**（フォールバック）：`AWS_ACCESS_KEY_ID` と `AWS_SECRET_ACCESS_KEY` を使用

**.env 設定例：**
```bash
# オプション 1: AWS プロファイルを使用（推奨）
AWS_PROFILE=default
AWS_REGION=us-east-1

# オプション 2: アクセスキーを使用（プロファイルがない場合のみ）
# AWS_ACCESS_KEY_ID=your_access_key_here
# AWS_SECRET_ACCESS_KEY=your_secret_key_here
```

### AgentCore 設定

アプリケーションは2つの実行モードをサポート：

- **AgentCore モード**: Amazon Bedrock AgentCore での完全なコード実行
- **Strands シミュレーション**: AgentCore が利用できない場合のコード分析とシミュレーション

AgentCore には追加の権限（`bedrock-agentcore:*`）が必要です。利用できない場合、アプリケーションは自動的に Strands シミュレーションにフォールバックします。

## セキュリティ考慮事項

- コード実行は AgentCore のサンドボックス環境で行われる
- セッションデータはメモリに保存（再起動間で永続化されない）
- AWS 認証情報は適切にセキュリティ保護する必要がある
- 本番使用には認証の実装を検討

## トラブルシューティング

### よくある問題

1. **「No response from server」エラー**：
   ```bash
   # バックエンドが実行中か確認
   curl http://localhost:8000/health

   # 診断を実行
   python diagnose_backend.py

   # デバッグ用にバックエンドを手動で起動
   ./start_manual.sh
   ```

2. **バックエンドが起動しない**：
   - `.env` ファイルの AWS 認証情報を確認
   - AWS アカウントで Bedrock アクセスが有効か確認
   - Python 依存関係がインストールされているか確認
   - 実行：`python test_strands.py` で strands-agents フレームワークを確認

3. **Strands-Agents フレームワークが見つからない**：
   ```bash
   # strands-agents が利用可能か確認
   python test_strands.py

   # インストールされていない場合、インストール
   pip install strands-agents

   # またはローカルに存在するか確認
   ls -la ../strands*
   ```

4. **フロントエンドがバックエンドに接続できない**：
   - バックエンドがポート 8000 で実行中か確認
   - CORS 設定を確認
   - フロントエンド設定の API URL を確認

5. **コード実行が失敗する**：
   - AgentCore 初期化を確認
   - Bedrock モデルアクセスを確認
   - 特定のエラーについて実行ログを確認

### 診断ツール

1. **完全な診断**：
   ```bash
   python diagnose_backend.py
   ```

2. **AWS 認証テスト**：
   ```bash
   python test_aws_auth.py
   ```

3. **Strands-Agents フレームワークテスト**：
   ```bash
   python test_strands.py
   ```

4. **AgentCore 統合テスト**：
   ```bash
   python test_agentcore_integration.py
   ```

5. **フロントエンドコンポーネントテスト**：
   ```bash
   node test_frontend.js
   ```

6. **インタラクティブ実行テスト**：
   ```bash
   python test_interactive.py
   ```

### 手動起動

自動起動スクリプトが失敗した場合は、手動起動を使用：

1. **バックエンドのみ**：
   ```bash
   ./start_manual.sh
   ```

2. **フロントエンドのみ**（別のターミナルで）：
   ```bash
   cd frontend
   npm start
   ```

### ログ

バックエンドログはコンソールに出力されます。デバッグ用：
```bash
# 詳細ログ付きでバックエンドを実行
cd backend
python main.py --log-level debug

# または改良版 start.sh 使用時のログファイルを確認
tail -f backend.log
tail -f frontend.log
```

## 開発

### プロジェクト構成
```
├── backend/
│   └── main.py              # FastAPI バックエンドサーバー
├── frontend/
│   ├── src/
│   │   ├── components/      # React コンポーネント
│   │   ├── services/        # API サービス
│   │   └── App.js          # メイン React アプリ
│   └── package.json
├── requirements.txt         # Python 依存関係
├── setup.sh                # セットアップスクリプト
├── start.sh                # 起動スクリプト
└── README.md
```

### 新機能の追加

1. **バックエンド**: `backend/main.py` に新しいエンドポイントを追加
2. **フロントエンド**: `frontend/src/components/` に新しいコンポーネントを追加
3. **API**: 新しいエンドポイント用に `frontend/src/services/api.js` を更新

## コントリビューション

1. リポジトリをフォーク
2. フィーチャーブランチを作成
3. 変更を加える
4. 徹底的にテスト
5. プルリクエストを提出

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています。

## サポート

問題や質問がある場合：
1. トラブルシューティングセクションを確認
2. AWS Bedrock AgentCore ドキュメントを確認
3. リポジトリで Issue をオープン
