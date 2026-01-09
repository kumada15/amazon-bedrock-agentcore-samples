# Gateway コンポーネント

このディレクトリには、SRE Agent 用の MCP（Model Context Protocol）ゲートウェイ管理ツールが含まれています。

## 📁 ファイル

- `main.py` - AWS AgentCore Gateway の作成と管理のための AgentCore Gateway 管理ツール
- `mcp_cmds.sh` - MCP ゲートウェイ操作とセットアップ用のシェルスクリプト
- `generate_token.py` - ゲートウェイ認証用の JWT トークン生成
- `openapi_s3_target_cognito.sh` - S3 と Cognito 統合で OpenAPI ターゲットを追加するスクリプト
- `config.yaml` - ゲートウェイ設定ファイル
- `config.yaml.example` - 設定テンプレートの例
- `.env` - ゲートウェイセットアップ用の環境変数
- `.env.example` - 環境変数テンプレートの例

## 🚀 Gateway セットアップ

### ステップバイステップセットアップ

1. **ゲートウェイを設定**（設定をコピーして編集）：
   ```bash
   cd gateway
   cp config.yaml.example config.yaml
   cp .env.example .env
   # config.yaml と .env を特定の設定で編集
   ```

2. **ゲートウェイを作成**：
   ```bash
   ./create_gateway.sh
   ```

3. **ゲートウェイをテスト**：
   ```bash
   ./mcp_cmds.sh

   # デバッグ用にログファイルに出力をキャプチャ：
   ./mcp_cmds.sh 2>&1 | tee mcp_cmds.log
   ```

このセットアッププロセスは以下を行います：
- MCP ゲートウェイインフラストラクチャを設定
- 適切な認証とトークン管理でゲートウェイを作成
- ゲートウェイ機能をテストしセットアップを検証

## 🔧 コンポーネント

### Gateway 管理 (`main.py`)
メインのゲートウェイ管理ツールは以下の機能を提供：
- AWS AgentCore Gateway の作成と管理
- MCP プロトコル統合のサポート
- JWT 認可の処理
- S3 またはインラインスキーマから OpenAPI ターゲットを追加

### MCP コマンド (`mcp_cmds.sh`)
以下を含むゲートウェイセットアッププロセスをオーケストレーションするシェルスクリプト：
- ゲートウェイ作成
- 設定検証
- サービス登録
- ヘルスチェック

### トークン生成 (`generate_token.py`)
ゲートウェイ認証用の JWT トークンを生成するユーティリティ：
```bash
python generate_token.py --config config.yaml
```

### OpenAPI 統合 (`openapi_s3_target_cognito.sh`)
OpenAPI 仕様を S3 ストレージと Cognito 認証と統合するスクリプト。

## 🔍 使用方法

### クイックリファレンス
1. `config.yaml` で設定を構成
2. ゲートウェイを作成：`./create_gateway.sh`
3. ゲートウェイをテスト：`./mcp_cmds.sh`
4. デバッグ用に出力をキャプチャ：`./mcp_cmds.sh 2>&1 | tee mcp_cmds.log`
5. ゲートウェイが実行中でアクセス可能か確認
6. クライアント認証用に必要に応じてトークンを生成

### 開発モード
開発とテストでは、コンポーネントを個別に実行することも可能：

```bash
# トークンを生成
python generate_token.py

# 特定の設定でゲートウェイを作成
python main.py --config config.yaml

# OpenAPI ターゲットを追加
./openapi_s3_target_cognito.sh
```

## ⚠️ 重要な注意事項

- 常に gateway ディレクトリから `mcp_cmds.sh` を実行
- セットアップ前に `config.yaml` が適切に設定されていることを確認
- SRE Agent の調査を開始する前にゲートウェイが実行されている必要あり
- 認証トークンは安全に保管し定期的にローテーション
- ログファイル（*.log）は git で自動的に無視 - デバッグ用に作成しても安全

## 🔗 統合

ゲートウェイがセットアップされ実行されると、SRE Agent コアシステムがインフラストラクチャ API とツールにアクセスするために接続する MCP エンドポイントを提供します。