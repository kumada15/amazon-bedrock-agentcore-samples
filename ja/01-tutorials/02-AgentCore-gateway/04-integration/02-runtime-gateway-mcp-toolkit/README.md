# AgentCore Runtime と Gateway MCP サーバーツールキット

AgentCore ランタイムとゲートウェイインフラストラクチャでカスタム MCP サーバーを素早くセットアップするための設定可能なツールキット。

MCP サーバーのデプロイを合理化された体験を提供するために [bedrock-agentcore-starter-toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit/) の上に構築されています。

## 概要

- コードを書かずにカスタム MCP サーバーを AgentCore にすばやくデプロイしたいですか？
- 複数のカスタム MCP サーバー/ツールを、さまざまな MCP サーバーからすべてのツールを公開する 1 つの URL に統合したいですか？
- MCP サーバーへの安全なアクセスが必要ですか？

このツールキットは、シンプルなコマンドライン引数でこれらすべてを実現するのに役立ちます。以下の作成を自動化します：

- 認証用の Cognito ユーザープール
- 各 MCP サーバー用の AgentCore Runtime 環境
- MCP プロトコルサポート付き AgentCore Gateway
- OAuth2 認証付き Gateway MCP サーバーターゲット

ツールキットは完全な MCP ゲートウェイを作成し、複数の MCP サーバー（例：calculator と helloworld）が適切な認証とルーティングで単一のゲートウェイエンドポイントを通じてアクセスできるようにします。

## 前提条件

1. AWS 認証情報が設定済み
2. Python 3.8 以上がインストール済み
3. （オプション）Cognito ユーザー設定用の `.env` ファイル

## インストール

### PyPI から（公開時）
```bash
pip install agentcore-runtime-gw-mcp-toolkit
```

### ソースから
```bash
git clone <repository-url>
cd agentcore-runtime-gw-mcp-tool-kit
pip install -e .
```

## 設定

### 環境変数（オプション）

プロジェクトディレクトリに `.env` ファイルを作成することで、Cognito ユーザー認証情報をカスタマイズできます：

```bash
# .env ファイル
COGNITO_USERNAME=your_username
COGNITO_TEMP_PASSWORD=your_temp_password
COGNITO_PASSWORD=your_permanent_password
```

**デフォルト値**（`.env` ファイルが提供されない場合に使用）：
- `COGNITO_USERNAME`: `testuser`
- `COGNITO_TEMP_PASSWORD`: `Temp123!`
- `COGNITO_PASSWORD`: `MyPassword123!`

**注意**: ツールキットはテスト目的でこれらの認証情報を使用して Cognito ユーザーを自動的に作成します。

## 使用方法

### 始め方

1. **リポジトリをクローン**
   ```bash
   git clone <repository-url>
   cd agentcore-runtime-gw-mcp-tool-kit
   ```

2. **パッケージをインストール**
   ```bash
   pip install -e .
   ```

3. **MCP サーバーコードを準備**
   - MCP サーバーファイルはシステム上のどこにでも配置可能
   - 各サーバーに `server.py` と `requirements.txt` があることを確認
   - ランタイム設定用にこれらのファイルのフルパスをメモ


   **サンプル構造（どこにでも配置可能）:**
   ```
   /path/to/my-servers/
   ├── calculator/
   │   ├── server.py
   │   └── requirements.txt
   ├── helloworld/
   │   ├── server.py
   │   └── requirements.txt
   └── my-custom-server/
       ├── server.py
       └── requirements.txt
   ```

4. **コマンドライン引数でデプロイ**
   ```bash
   agentcore-mcp-toolkit \
     --gateway-name "my-gateway" \
     --runtime-configs '[
       {
         "name": "my-custom-runtime",
         "description": "My Custom MCP Server",
         "entrypoint": "/path/to/my-servers/my-custom-server/server.py",
         "requirements_file": "/path/to/my-servers/my-custom-server/requirements.txt"
       }
     ]'
   ```
   **注意:** agentcore-mcp-toolkit は MCP サーバープロジェクトのルートから呼び出す必要があります。例：上記の例では /path/to からユーティリティを呼び出す必要があります。

### 基本的な使用方法

```bash
# 最小限の引数でデプロイ
agentcore-mcp-toolkit \
  --gateway-name "my-gateway" \
  --runtime-configs '[{"name":"runtime1","description":"My Runtime","entrypoint":"/path/to/myserver/server.py","requirements_file":"/path/to/myserver/requirements.txt"}]'

# すべてのオプションでデプロイ
agentcore-mcp-toolkit \
  --region us-east-1 \
  --gateway-name "my-gateway-mcp-server" \
  --gateway-description "My AgentCore Gateway" \
  --runtime-configs '[
    {
      "name": "my-calculator-runtime",
      "description": "Calculator MCP Server",
      "entrypoint": "/path/to/calculator/server.py",
      "requirements_file": "/path/to/calculator/requirements.txt"
    }
  ]'
```

### コマンドラインオプション

- `--region`: AWS リージョン（デフォルト: us-east-1）
- `--gateway-name`: ゲートウェイ名（必須）
- `--gateway-description`: ゲートウェイの説明（オプション）
- `--runtime-configs`: ランタイム設定の JSON 配列（必須）

### ランタイム設定形式

`--runtime-configs` JSON 配列の各ランタイム設定には以下を含める必要があります：

```json
{
  "name": "runtime-name",
  "description": "Runtime description",
  "entrypoint": "path/to/server.py",
  "requirements_file": "path/to/requirements.txt",
  "auto_create_execution_role": true,
  "auto_create_ecr": true
}
```

**必須フィールド:**
- `name`: 一意のランタイム名
- `entrypoint`: MCP サーバー Python ファイルのフルパス
- `requirements_file`: requirements.txt ファイルのフルパス

**オプションフィールド:**
- `description`: ランタイムの説明
- `auto_create_execution_role`: IAM ロールを自動作成（デフォルト: true）
- `auto_create_ecr`: ECR リポジトリを自動作成（デフォルト: true）

### 自動導出される名前

ツールキットは `gateway-name` とランタイムの `name` フィールドからリソース名を自動的に導出します：

**Gateway リソース**（`--gateway-name` から）：
- IAM ロール: `{gateway-name}-role`
- ユーザープール: `{gateway-name}-pool`
- リソースサーバー ID: `{gateway-name}-id`
- リソースサーバー名: `{gateway-name}-name`
- クライアント名: `{gateway-name}-client`

**Runtime リソース**（ランタイム `name` から）：
- ユーザープール: `{runtime-name}-pool`
- リソースサーバー ID: `{runtime-name}-id`
- リソースサーバー名: `{runtime-name}-name`
- クライアント名: `{runtime-name}-client`
- エージェント名: `{runtime-name}`（ダッシュはアンダースコアに変換）

**Target リソース**（自動生成）：
- ターゲット名: `{runtime-name}-target`
- ID プロバイダー: `{runtime-name}-identity`

## ゲートウェイのテスト

デプロイ後、ツールキットは MCP ゲートウェイをテストして使用するために必要なすべての接続情報を自動的に提供します。

### Gateway 接続情報

ツールキットは接続詳細を自動的に表示し、デプロイ成功後に**認証情報を安全にファイルに保存**します：

#### **安全な認証情報ストレージ**

セキュリティのため、機密性の高い認証情報はコンソールログに表示される代わりに安全なファイルに保存されます：

- **ファイルの場所**: `.agentcore-credentials-{gateway-name}.json`
- **ファイル権限**: 所有者のみアクセス可能（600）
- **コンソール出力**: 機密値には `<redacted>` と表示
- **アクセス方法**: `cat .agentcore-credentials-{gateway-name}.json` を使用

**出力例:**
```
============================================================
GATEWAY CONNECTION INFORMATION
============================================================
Gateway URL: https://my-gateway-mcp-server-123456789.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
User Pool ID: us-east-1_bt4yEZFOx
Client ID: <redacted>
Client Secret: <redacted>
Access Token: <redacted>
Credentials saved to: .agentcore-credentials-my-gateway.json
ファイル権限は所有者のみのアクセス（600）に設定されます
Use: cat .agentcore-credentials-my-gateway.json
============================================================

✅ Setup completed successfully!
Gateway ID: my-gateway-mcp-server-123456789
Runtime 1 Agent ARN: arn:aws:bedrock-agentcore:us-east-1:123456789:runtime/my_calculator_runtime-123456789
```

### アクセストークンで QDev プラグインを設定

QDev プラグインで MCP ゲートウェイを使用するには、以下のように設定します：

![QDev MCP 設定](images/qdev_mcp_config.png)

**QDev を設定する手順：**
1. 安全なファイルから**認証情報を取得**：
   ```bash
   cat .agentcore-credentials-{gateway-name}.json
   ```
2. JSON ファイルから **access_token** の値をコピー
3. QDev プラグイン設定で、新しい MCP サーバーを追加：
   - **サーバー URL**: 認証情報ファイルの `gateway_url` を使用
   - **認証**: Bearer Token
   - **トークン**: ステップ 2 のアクセストークンを貼り付け
4. 設定を保存して接続をテスト

**セキュリティに関する注意**: 認証情報ファイルを共有したりバージョン管理にコミットしたりしないでください。

### ライブデモ例

設定後、QDev で MCP ツールを直接使用できます：

**Calculator MCP サーバーデモ:**
![Calculator Add デモ](images/calculator_add_demo.png)

**Hello World MCP サーバーデモ:**
![Greet Hello World デモ](images/greet_hello_world.png)

## アーキテクチャ

![アーキテクチャ](images/architecture.png)

### アーキテクチャコンポーネント

ツールキットが作成するもの：
1. **単一ゲートウェイ**: リクエストをルーティングする複数の MCP サーバーターゲットを持つ 1 つの AgentCore Gateway
2. **複数ランタイム**: 各 MCP サーバーは独自の AgentCore Runtime で実行
3. **認証**: ゲートウェイと各ランタイム用の個別の Cognito リソース
4. **ターゲット**: ゲートウェイを各ランタイムに接続する Gateway MCP サーバーターゲット

### 認証フロー

**インバウンド認可（クライアント → ゲートウェイ）：**
- MCP クライアント（QDev）が Bearer トークン付きでリクエストを送信
- Gateway JWT Authorizer が Gateway Cognito ユーザープールに対してトークンを検証
- 認可されたリクエストは適切なターゲットにルーティング

**アウトバウンド認可（ゲートウェイ → ランタイム）：**
- 各ターゲットは独自の OAuth2 認証情報プロバイダーを持つ
- ゲートウェイはそれぞれの Runtime Cognito ユーザープールから OAuth トークンを取得
- 認証されたリクエストが個々の MCP サーバーランタイムに送信

## 認可サポート

### 現在の実装
このツールキットは現在、インバウンドとアウトバウンドの両方の認可で **Amazon Cognito OAuth2** をサポートしています：
- **インバウンド認可**: ゲートウェイはクライアント認証に Cognito JWT トークンを使用
- **アウトバウンド認可**: ゲートウェイは Cognito OAuth2 認証情報を使用してランタイムに認証

### ロードマップ
- **IAM ロールベース認可**: インバウンドとアウトバウンドの両方の認証に対する IAM ロールとポリシーのサポート（TODO - 次回リリースで予定）

## セキュリティ機能

### **安全な認証情報管理**
- **ファイルベースストレージ**: 認証情報は制限された権限を持つ安全なファイルに保存
- **コンソールマスキング**: 機密値はログで `<redacted>` として表示
- **ファイル権限**: 所有者のみアクセス可能（600）を自動設定
- **フォールバック保護**: ファイル操作が失敗した場合の優雅な処理

### **入力検証**
- **パストラバーサル保護**: ファイルパスでの `..` を防止
- **ファイル拡張子検証**: `.py` と `.txt` 拡張子を確認
- **JSON 構造検証**: ランタイム設定形式を検証
- **必須フィールドチェック**: すべての必須フィールドの存在を確認

### **エラー処理**
- **特定の例外処理**: 適切な例外タイプを使用
- **サニタイズされたエラーメッセージ**: 情報漏洩を防止
- **優雅な劣化**: 可能な場合は操作を継続
- **適切な終了コード**: 自動化のための適切なステータスを返す

## クリーンアップ

### リソースの削除

ツールキットで作成されたすべてのリソースをクリーンアップするには、クリーンアップスクリプトを使用します：

```bash
# 特定のゲートウェイとランタイムをクリーンアップ
python -m cleanup \
  --gateway-name "my-gateway" \
  --runtime-names '["runtime1", "runtime2"]' \
  --region us-east-1

# 確認プロンプトをスキップ
python -m cleanup \
  --gateway-name "my-gateway" \
  --runtime-names '["runtime1", "runtime2"]' \
  --confirm
```

### クリーンアップオプション

- `--gateway-name`: クリーンアップするゲートウェイ名（必須）
- `--runtime-names`: クリーンアップするランタイム名の JSON 配列（必須）
- `--region`: AWS リージョン（デフォルト: us-east-1）
- `--confirm`: 確認プロンプトをスキップ

### クリーンアップされるリソース

クリーンアップスクリプトは以下を削除します：
- AgentCore Gateway とすべてのターゲット
- AgentCore Runtime インスタンス
- Cognito ユーザープールとドメイン
- IAM ロールとポリシー
- OAuth2 認証情報プロバイダー

**注意**: クリーンアップスクリプトはローカルの認証情報ファイルを削除しません。削除するには：
```bash
# 認証情報ファイルを手動で削除
rm .agentcore-credentials-*.json
```

**警告**: このアクションは元に戻せません。続行する前に必ずリソースを確認してください。

## トラブルシューティング

1. AWS 認証情報が正しく設定されていることを確認
2. 必要な MCP サーバーファイルがそれぞれのディレクトリに存在することを確認
3. AWS リージョンの権限を確認
4. 詳細なエラー情報については CloudWatch ログを確認
5. テスト時にゲートウェイ URL が正しくフォーマットされていることを確認
6. Cognito ユーザープールとクライアントが正常に作成されていることを確認
7. **アクセストークンの問題**: アクセストークンが期限切れの場合、ツールキットを再実行して新しいトークンを取得
8. **QDev 接続の問題**: ゲートウェイ URL が `/mcp` で終わり、Bearer トークンが正しくコピーされていることを確認
9. **ツール検出**: ツールが見つからない場合は、異なるクエリ用語を試す（「calculator」、「greet」、「tools」など）
10. **認可の問題**: 現在 Cognito OAuth2 のみがサポートされています - すべての認証で Cognito トークンを使用していることを確認
11. **Cognito ユーザーの問題**: ユーザー作成エラーが発生した場合、`.env` ファイルの設定を確認するか、デフォルトの認証情報を使用
12. **クリーンアップの問題**: クリーンアップが失敗した場合、AWS コンソールでリソースを手動で確認し、特定のリソース名で再試行
13. **認証情報ファイルの問題**: 認証情報ファイルを作成できない場合、ディレクトリ権限とディスク容量を確認
14. **ファイル権限の問題**: Windows では、ファイル権限が正しく設定されない場合があります - 認証情報ファイルを手動で保護
15. **パス検証エラー**: ファイルパスに `..` が含まれず、正しい拡張子（`.py`、`.txt`）を持っていることを確認
16. **JSON 検証エラー**: runtime-configs が必須フィールドを持つ有効な JSON 配列であることを確認

## サンプル MCP サーバー

ツールキットにはサンプル MCP サーバーが含まれています：
- **Calculator**: 加算と乗算の機能を提供
- **HelloWorld**: 挨拶機能を提供

両方のサーバーは MCP プロトコルの実装を示しており、カスタム MCP サーバーを作成するためのテンプレートとして使用できます。
