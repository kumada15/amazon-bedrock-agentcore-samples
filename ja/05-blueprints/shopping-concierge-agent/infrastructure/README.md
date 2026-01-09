# エージェントインフラストラクチャ

AWS Bedrock AgentCore を使用したコンシェルジュエージェントシステムをデプロイするための CDK インフラストラクチャです。

このディレクトリには、エージェントインフラストラクチャをデプロイする 3 つの個別の CDK アプリケーションが含まれています:

## インフラストラクチャコンポーネント

### 1. MCP サーバー (`mcp-servers/`)

複数の MCP ランタイムスタック、それぞれに以下が含まれます:
- **AgentCore Runtime** - OAuth 認証を備えたコンテナ化された MCP サーバー
- **IAM ロール** - Bedrock モデル、CloudWatch、SSM パラメータ、DynamoDB の権限

**デプロイされるスタック**:
- **CartStack** - ショッピングカート管理と Visa 決済連携
- **ShoppingStack** - 商品検索ツール (SerpAPI 連携)

### 2. エージェントスタック (`agent-stack/`)

メインスーパーバイザーエージェントのインフラストラクチャ:
- **AgentCore Runtime** - JWT 認証を備えたスーパーバイザーエージェント
- **Memory Resource** - 会話の永続化 (短期メモリ)
- **AgentCore Gateway** - すべての MCP サーバーに接続する MCP プロトコルゲートウェイ
- **OAuth2 Credential Provider** - ゲートウェイ用のマシン間認証
- **IAM ロール** - DynamoDB、Bedrock、Memory、Gateway 呼び出しの権限
- **SSM パラメータ** - Gateway URL 設定

### 3. フロントエンドスタック (`frontend-stack/`)

Web UI ホスティングインフラストラクチャ:
- **Amplify Hosting App** - React Web UI デプロイメント
- **GitHub 連携** - リポジトリからの自動ビルド
- **環境変数** - エージェント接続用のランタイム設定

**注記**: これらのスタックは、プロジェクトルートから `npm run deploy:amplify` でデプロイされる Amplify バックエンド (Cognito, DynamoDB) に依存しています。

## アーキテクチャ
![shopping arch](../docs/Shopping_Agent_VISA.jpg)


## 前提条件

1. **AWS CLI 設定済み**
   ```bash
   aws configure
   ```

2. **Amplify バックエンドのデプロイ** - プロジェクトルートから最初にデプロイする必要があります:
   ```bash
   npm run deploy:amplify
   ```
   これにより、これらのスタックに必要な Cognito、DynamoDB、CloudFormation エクスポートが作成されます。

3. **Node.js 18+** と npm がインストールされていること

4. **Docker** がインストールされ、実行中であること

5. **API キー設定** (オプションですが推奨)
   ```bash
   cd ..
   ./scripts/set-api-keys.sh
   ```

## デプロイ

npm スクリプトを使用してプロジェクトルートからデプロイします:

```bash
# すべてのインフラストラクチャスタックをデプロイ
cd ..
npm run deploy:mcp       # MCP サーバーをデプロイ (~60 秒)
npm run deploy:agent     # メインエージェントをデプロイ (~4 分)
npm run deploy:frontend  # Web UI をデプロイ (オプション、~3 分)
```

## プロジェクト構成

```
infrastructure/
├── agent-stack/              # メインスーパーバイザーエージェント
│   ├── lib/
│   │   ├── agent-stack.ts    # メインスタック定義
│   │   └── constructs/
│   │       └── gateway-construct.ts  # MCP ターゲット付きゲートウェイ
│   ├── lambdas/
│   │   └── oauth-provider/   # OAuth セットアップ用カスタムリソース
│   ├── cdk.json
│   └── package.json
│
├── mcp-servers/              # MCP ランタイムスタック
│   ├── lib/
│   │   ├── app.ts            # CDK アプリエントリーポイント
│   │   ├── base-mcp-stack.ts # MCP スタックの基底クラス
│   │   ├── cart-stack.ts     # カート & 決済
│   │   └── shopping-stack.ts # 商品検索
│   ├── cdk.json
│   └── package.json
│
├── frontend-stack/           # Amplify Hosting
│   ├── lib/
│   │   └── frontend-stack.ts
│   ├── cdk.json
│   └── package.json
│
├── certs/                    # Visa API 証明書 (オプション)
│   ├── server_mle_cert.pem
│   └── mle_private_cert.pem
│
└── README.md                 # このファイル
```

## スタック出力

### MCP スタック

各 MCP スタックは以下をエクスポートします:
- `{StackName}-RuntimeArn` - MCP ランタイム ARN
- `{StackName}-RuntimeId` - MCP ランタイム ID

例: `CartStack-shopping-RuntimeArn`

### エージェントスタック

- `MainRuntimeArn` - メインエージェントランタイム ARN
- `MainRuntimeId` - メインエージェントランタイム ID
- `MemoryId` - メモリリソース ID
- `GatewayUrl` - MCP 接続用ゲートウェイ URL
- `GatewayId` - ゲートウェイ ID
- `GatewayArn` - ゲートウェイ ARN
- `OAuthProviderArn` - OAuth プロバイダー ARN

### フロントエンドスタック

- `AmplifyAppId` - Amplify アプリ ID
- `AmplifyAppUrl` - ライブアプリケーション URL

## 動作の仕組み

### クロススタック統合

これらのスタックは CloudFormation エクスポートを介して Amplify バックエンドからリソースをインポートします:

```typescript
// Amplify スタックからインポート
const userPoolId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-UserPoolId`);
const machineClientId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-MachineClientId`);
const userProfileTable = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-UserProfileTableName`);
```

**デプロイ順序**:
1. Amplify バックエンド (プロジェクトルートから)
2. MCP サーバー (Cognito 設定をインポート)
3. エージェントスタック (Cognito、DynamoDB、MCP ランタイム ARN をインポート)
4. フロントエンドスタック (オプション)

### 認証フロー

**ユーザー → エージェント**:
- フロントエンドが Cognito Web クライアントで認証
- JWT トークンでエージェントランタイムを呼び出し
- エージェントが Cognito に対して JWT を検証

**エージェント → ゲートウェイ → MCP サーバー**:
- エージェントが Cognito に M2M トークンをリクエスト
- エージェントが M2M JWT でゲートウェイを呼び出し
- ゲートウェイが JWT を検証し OAuth トークンを取得
- ゲートウェイが OAuth トークンで MCP サーバーを呼び出し
- MCP サーバーが OAuth トークンを検証

## 設定

### デプロイメント ID

すべてのスタックは `../deployment-config.json` からデプロイメント ID を読み取ります:

```json
{
  "deploymentId": "shopping",
  "description": "Unique identifier for this deployment"
}
```

これにより、同じ AWS アカウント内で複数のデプロイが可能になります。

### 環境変数

**MCP サーバー** は以下を自動的に受け取ります:
- `AWS_REGION` - 現在の AWS リージョン
- `USER_PROFILE_TABLE_NAME` - DynamoDB テーブル (CartStack のみ)
- `WISHLIST_TABLE_NAME` - DynamoDB テーブル (CartStack のみ)

**エージェントスタック** は以下を自動的に受け取ります:
- `MEMORY_ID` - メモリリソース ID
- `USER_PROFILE_TABLE_NAME` - DynamoDB テーブル名
- `WISHLIST_TABLE_NAME` - DynamoDB テーブル名
- `FEEDBACK_TABLE_NAME` - DynamoDB テーブル名
- `DEPLOYMENT_ID` - デプロイメント識別子
- `GATEWAY_CLIENT_ID` - Cognito マシンクライアント ID
- `GATEWAY_USER_POOL_ID` - Cognito ユーザープール ID
- `GATEWAY_SCOPE` - OAuth スコープ

ゲートウェイ URL は `/concierge-agent/{DEPLOYMENT_ID}/gateway-url` の SSM Parameter Store に保存されます。

## インフラストラクチャの更新

### エージェントコードの更新

```bash
npm run deploy:agent
```

スーパーバイザーエージェントコンテナを再ビルドしてデプロイします。

### MCP サーバーコードの更新

```bash
npm run deploy:mcp
```

すべての MCP サーバーコンテナを再ビルドしてデプロイします。

### フロントエンドの更新

```bash
npm run deploy:frontend
```

最新の Web UI コードを Amplify Hosting にデプロイします。

## トラブルシューティング

### CloudFormation エクスポートが見つからない

**エラー**: `Export ConciergeAgent-shopping-Auth-UserPoolId not found`

**解決策**: プロジェクトルートから Amplify バックエンドを最初にデプロイしてください:

```bash
cd .. && npm run deploy:amplify
```

エクスポートを確認:

```bash
aws cloudformation list-exports --query "Exports[?contains(Name, 'ConciergeAgent')]"
```

### Docker ビルドの失敗

**解決策**:
- Docker が実行中であることを確認: `docker ps`
- `../concierge_agent/*/` の Dockerfile を確認
- `requirements.txt` の依存関係を確認
- ECR 権限を確認

### ゲートウェイ接続エラー

**解決策**:

1. SSM でゲートウェイ URL を確認:
   ```bash
   aws ssm get-parameter --name /concierge-agent/shopping/gateway-url
   ```

2. ゲートウェイデバッグログを有効化:
   ```bash
   aws bedrock-agentcore-control update-gateway \
     --gateway-identifier <GATEWAY_ID> \
     --exception-level DEBUG
   ```

### MCP 認証の失敗

**解決策**:
- OAuth プロバイダーが存在することを確認
- Cognito の M2M クライアントスコープを確認
- MCP サーバーが正しいクライアント ID を使用していることを確認

### エージェントスタックのデプロイ失敗

**エラー**: `Cannot import MCP runtime ARN`

**解決策**: MCP スタックが最初にデプロイされていることを確認:

```bash
npm run deploy:mcp
```

MCP エクスポートを確認:

```bash
aws cloudformation list-exports --query "Exports[?contains(Name, 'RuntimeArn')]"
```

## クリーンアップ

プロジェクトルートからインフラストラクチャを削除:

```bash
cd ..
npm run clean:frontend  # Amplify Hosting を削除
npm run clean:agent     # エージェントスタックを削除
npm run clean:mcp       # MCP スタックを削除
```

**注記**: 一部のリソースは手動削除が必要な場合があります:
- CloudWatch ロググループ
- SSM パラメータ
- Secrets Manager シークレット (Visa 認証情報)

## 追加リソース

- [AWS CDK ドキュメント](https://docs.aws.amazon.com/cdk/)
- [Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)
- [メインプロジェクト README](../README.md)
- [デプロイガイド](../DEPLOYMENT.md)
