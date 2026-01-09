# セットアップガイド

## 前提条件

AgentCore コードインタープリターをセットアップする前に、以下を確認してください:

- **Python 3.8+**（pip 付き）
- **Node.js 16+**（npm 付き）
- **AWS アカウント**（Bedrock アクセス付き）
- **AWS CLI**（設定済みまたは認証情報が利用可能）

## クイックセットアップ

### 1. 初期セットアップ

```bash
# プロジェクトディレクトリに移動
cd /path/to/strands-agents/agent-core/code-interpreter

# 自動セットアップスクリプトを実行
./setup.sh
```

セットアップスクリプトは以下を行います:
- Python 仮想環境を作成
- バックエンド依存関係をインストール
- フロントエンド依存関係をインストール
- 設定ファイルを作成

### 2. AWS 設定

以下のいずれかの方法を選択:

#### オプション A: AWS プロファイル（推奨）
```bash
# プロファイルで AWS CLI を設定
aws configure --profile your_profile_name

# .env ファイルを更新
echo "AWS_PROFILE=your_profile_name" >> .env
echo "AWS_REGION=us-east-1" >> .env
```

#### オプション B: アクセスキー
```bash
# 認証情報で .env ファイルを更新
echo "AWS_ACCESS_KEY_ID=your_access_key" >> .env
echo "AWS_SECRET_ACCESS_KEY=your_secret_key" >> .env
echo "AWS_REGION=us-east-1" >> .env
```

### 3. AWS 権限

AWS ユーザー/ロールに以下のポリシーをアタッチ:

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

または、マネージドポリシー `BedrockAgentCoreFullAccess` を使用

### 4. 検証

```bash
# セットアップを検証
python tests/verify_setup.py

# 包括的テストを実行
python tests/run_all_tests.py
```

### 5. アプリケーション起動

```bash
# バックエンドとフロントエンドを起動
./start.sh

# アプリケーションにアクセス
# フロントエンド: http://localhost:3000
# バックエンド API: http://localhost:8000
```

## 手動セットアップ

自動セットアップが失敗した場合、以下の手動手順に従ってください:

### バックエンドセットアップ

```bash
# 仮想環境を作成
python -m venv venv

# 仮想環境を有効化
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate     # Windows

# 依存関係をインストール
pip install -r backend/requirements.txt
```

### フロントエンドセットアップ

```bash
# フロントエンドディレクトリに移動
cd frontend

# 依存関係をインストール
npm install

# プロジェクトルートに戻る
cd ..
```

### 設定

```bash
# テンプレートから .env ファイルを作成
cp .env.example .env

# 設定で .env ファイルを編集
nano .env
```

## 環境変数

| 変数 | 説明 | 必須 | デフォルト |
|----------|-------------|----------|---------|
| `AWS_PROFILE` | AWS プロファイル名 | はい* | - |
| `AWS_ACCESS_KEY_ID` | AWS アクセスキー | はい* | - |
| `AWS_SECRET_ACCESS_KEY` | AWS シークレットキー | はい* | - |
| `AWS_REGION` | AWS リージョン | いいえ | `us-east-1` |
| `BACKEND_HOST` | バックエンドホスト | いいえ | `0.0.0.0` |
| `BACKEND_PORT` | バックエンドポート | いいえ | `8000` |
| `REACT_APP_API_URL` | フロントエンド API URL | いいえ | `http://localhost:8000` |

*AWS_PROFILE または AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY のいずれかが必要

## トラブルシューティング

### よくある問題

#### 仮想環境の問題
```bash
# venv 作成が失敗した場合
python3 -m venv venv

# Mac/Linux でアクティベーションが失敗した場合
chmod +x venv/bin/activate
source venv/bin/activate
```

#### 依存関係インストールの問題
```bash
# まず pip を更新
pip install --upgrade pip

# 詳細出力でインストール
pip install -r backend/requirements.txt -v

# フロントエンドの問題の場合
cd frontend
npm cache clean --force
npm install
```

#### AWS 設定の問題
```bash
# AWS 認証情報をテスト
aws sts get-caller-identity

# Bedrock アクセスをテスト
aws bedrock list-foundation-models --region us-east-1

# AgentCore アクセスをテスト（BedrockAgentCoreFullAccess が必要）
python -c "from bedrock_agentcore.tools.code_interpreter_client import code_session; print('AgentCore accessible')"
```

#### ポートの競合
```bash
# ポート 3000 と 8000 のプロセスを終了
lsof -ti:3000 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

### ヘルプの取得

1. **ログを確認**: `backend.log` と `frontend.log` を確認
2. **診断を実行**: `python tests/verify_setup.py`
3. **コンポーネントをテスト**: `python tests/run_all_tests.py`
4. **AWS を検証**: `aws bedrock list-foundation-models`

## 開発セットアップ

開発作業用:

### バックエンド開発
```bash
# 仮想環境を有効化
source venv/bin/activate

# 自動リロードでバックエンドを起動
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### フロントエンド開発
```bash
# ホットリロードでフロントエンドを起動
cd frontend
npm start
```

### テスト
```bash
# すべてのテストを実行
python tests/run_all_tests.py

# 特定のテストを実行
python -c "from tests.run_all_tests import TestRunner; runner = TestRunner(); runner.test_code_generation_api()"
```

## 次のステップ

セットアップ成功後:

1. **アプリケーションを起動**: `./start.sh`
2. **ブラウザを開く**: `http://localhost:3000` に移動
3. **コードを生成**: 「フィボナッチ数を計算する関数を作成」を試す
4. **コードを実行**: 「コードを実行」をクリックして AgentCore サンドボックスで実行
5. **機能を探索**: ファイルアップロード、インタラクティブコード、セッション履歴を試す

アプリケーションが使用できる状態になりました！ 🚀
