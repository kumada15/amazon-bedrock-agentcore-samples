# Concierge Shopping Agent - デプロイガイド

Amplify バックエンド、CDK インフラストラクチャ、Web UI を備えた Concierge Agent システムの完全なデプロイガイドです。

## 前提条件

### 必要なツール
- **Node.js**: v18+（v20 推奨）
- **npm**: v9+
- **AWS CLI**: v2+ 認証情報設定済み
- **Docker**: エージェントコンテナイメージのビルド用
- **jq**: JSON パース用 - `brew install jq`（macOS）または `apt-get install jq`（Linux）

### AWS アカウント要件
- 適切な権限を持つ AWS アカウント

### 必要な AWS 権限
- Amplify デプロイ権限
- CDK デプロイ権限（CloudFormation、IAM など）
- Bedrock 権限（AgentCore）
- S3、DynamoDB、Cognito、ECR

### API キー（オプション）

API キーにより追加機能が有効になりますが、基本機能には必須ではありません。

**注意:** API キーがない場合、ショッピング機能は無効になりますが、エージェント自体は動作します。

#### SERP API（商品検索）

ショッピングアシスタントは商品検索機能に SERP API を必要とします。

1. **サインアップ**: https://serpapi.com/users/sign_up  # pragma: allowlist secret
2. **設定** セットアップスクリプトを使用:
   ```bash
   ./scripts/set-api-keys.sh
   ```
   API キーの入力を求められ、AWS Systems Manager Parameter Store に `/concierge-agent/shopping/serp-api-key` として保存されます

## クイックスタート

npm スクリプトですべてのコンポーネントをデプロイ:

```bash
# 依存関係のインストール
npm install
cd amplify
npm install
cd ..

# 1. バックエンドのデプロイ（Cognito、DynamoDB、AppSync）
npm run deploy:amplify

# 2. MCP サーバーのデプロイ（Cart + Shopping）
npm run deploy:mcp

# 3. メインエージェントのデプロイ（Runtime + Gateway + Memory）
npm run deploy:agent
```

### 決済連携

決済連携には3つのオプションがあります:

#### オプション 1: モックモード（Visa 認証情報不要）

モック Visa API でデプロイ - 実際の決済処理なし:

```bash
npm run deploy:frontend --mock
```

追加のセットアップは不要です。アプリケーションはすべての決済関連機能にモックデータを使用します。


#### オプション 2: Visa 決済連携

**重要:** Visa 認証情報は Visa から直接取得する必要があります。オンボーディングについては [Visa ドキュメント](visa-documentation/visa-payment-integration-guide.md#onboarding-process) の手順に従ってください。

##### オプション 2.1: プロキシ経由の Visa 連携

Visa API 認証情報があり、本番環境にデプロイする場合:

1. **Visa シークレットを AWS Secrets Manager にエクスポート**:
   ```bash
   ./scripts/export-visa-secrets.sh
   ```
   認証情報の入力を求められ、安全に保存されます。

2. **Visa Lambda プロキシをデプロイ**:
   ```bash
   npm run deploy:visa-lambda
   ```

3. **フロントエンドをデプロイ**:
   ```bash
   npm run deploy:frontend
   ```

##### オプション 2.2: ローカルバックエンドサーバー経由の Visa 連携

Visa API 認証情報があり、ローカルで開発する場合:

1. **Visa シークレットを AWS Secrets Manager にエクスポート**:
   ```bash
   ./scripts/export-visa-secrets.sh
   ```

2. **ローカルバックエンドサーバーのセットアップに従う**:
   完全な手順については [Visa ローカルサーバー README](concierge_agent/local-visa-server/README.md) を参照してください。

   概要:
   - AWS にサインインした2つのターミナルが必要
   - ターミナル 1: `npm run dev` を実行し、`https://vcas.local.com:9000` を開く
   - ターミナル 2: ローカル Visa バックエンドサーバーを実行し、`http://localhost:5001` を開く


## デプロイ詳細

### ステップ 1: Amplify バックエンド（約4分）

Cognito、DynamoDB テーブル、AppSync API をデプロイします。

```bash
npm run deploy:amplify
```

**デプロイされるもの:**
- Web クライアントと M2M クライアントを持つ Cognito User Pool
- AppSync GraphQL API
- DynamoDB テーブル（UserProfile、Wishlist、Feedback）
- クロススタック参照用の CloudFormation エクスポート

**期待される出力:**
- `amplify_outputs.json` ファイルの作成
- CloudFormation エクスポート:
  - `ConciergeAgent-{deploymentId}-Auth-UserPoolId`
  - `ConciergeAgent-{deploymentId}-Auth-ClientId`
  - `ConciergeAgent-{deploymentId}-Auth-MachineClientId`
  - `ConciergeAgent-{deploymentId}-Data-UserProfileTableName`
  - `ConciergeAgent-{deploymentId}-Data-WishlistTableName`
  - `ConciergeAgent-{deploymentId}-Data-FeedbackTableName`

**確認:**
```bash
# amplify_outputs.json が存在するか確認
ls amplify_outputs.json

# CloudFormation エクスポートを表示
aws cloudformation list-exports --query "Exports[?contains(Name, 'ConciergeAgent')]"
```

### ステップ 2: MCP サーバー（約60秒）

Cart と Shopping MCP ランタイムを別々のスタックとしてデプロイします。

**デプロイ前に**、オプションで API キーを設定:

```bash
chmod +x scripts/set-api-keys.sh
./scripts/set-api-keys.sh
chmod +x scripts/export-visa-secrets.sh
./scripts/export-visa-secrets.sh
```

すべての MCP サーバーをデプロイ:

```bash
npm run deploy:mcp
```

**デプロイされるもの:**
- **CartStack** - DynamoDB と Visa Secrets Manager アクセスを持つショッピングカート管理
- **ShoppingStack** - SerpAPI 連携を持つ商品検索ツール
- 両方とも OAuth 認証を使用し、Cognito と連携

**期待される出力:**
- `CartStack-{deploymentId}-RuntimeArn`
- `ShoppingStack-{deploymentId}-RuntimeArn`
- 各スタックのランタイム ID

**確認:**
```bash
# MCP ランタイムエクスポートを確認
aws cloudformation list-exports --query "Exports[?contains(Name, 'RuntimeArn')]"
```

### ステップ 3: Agent スタック（約4分）

メモリとゲートウェイを持つメインスーパーバイザーエージェントをデプロイします。

```bash
npm run deploy:agent
```

**デプロイされるもの:**
- JWT 認証を持つ Agent Runtime
- 会話永続化用の Memory リソース
- MCP サーバーに接続する AgentCore Gateway
- M2M 認証用の OAuth2 Credential Provider
- DynamoDB、Bedrock、Memory、Gateway への権限を持つ IAM ロール
- ゲートウェイ URL を保存する SSM パラメータ

**期待される出力:**
- `MainRuntimeArn` - メインエージェントランタイム ARN
- `MemoryId` - 会話メモリ ID
- `GatewayUrl` - ゲートウェイエンドポイント URL
- `GatewayId` - ゲートウェイ ID
- `OAuthProviderArn` - OAuth プロバイダー ARN

**デプロイ後:**
`sync-gateway.sh` スクリプトが自動的に実行され、ランタイムをゲートウェイ URL で更新します。

**確認:**
```bash
# エージェントスタックの出力を確認
aws cloudformation describe-stacks \
  --stack-name AgentStack-shopping \
  --query 'Stacks[0].Outputs'

# SSM でゲートウェイ URL を確認
aws ssm get-parameter --name /concierge-agent/shopping/gateway-url
```

### ステップ 4: Visa Lambda プロキシ（約2分）- オプション

本番環境での Visa API 連携用に Lambda プロキシをデプロイします。

**注意:** Visa API 認証情報があり、実際の決済処理を使用する場合のみデプロイしてください。モックモードを使用する場合はこのステップをスキップしてください。

**デプロイ前に**、Visa シークレットをエクスポートしていることを確認:
```bash
./scripts/export-visa-secrets.sh
```

Visa Lambda プロキシをデプロイ:
```bash
npm run deploy:visa-lambda
```

**デプロイされるもの:**
- Visa API 連携を持つ Lambda 関数
- Visa 操作用の API Gateway エンドポイント
- Secrets Manager アクセスを持つ IAM ロール
- フロントエンドアクセス用の CORS 設定

**期待される出力:**
- `VisaLambdaStack-{deploymentId}-ApiUrl` - API Gateway エンドポイント URL
- Lambda 関数 ARN

**確認:**
```bash
# Visa Lambda スタックの出力を確認
aws cloudformation describe-stacks \
  --stack-name VisaLambdaStack-shopping \
  --query 'Stacks[0].Outputs'

# API エンドポイントをテスト
curl https://<api-url>/health
```

### ステップ 5: フロントエンド（約3分）- オプション

CI/CD を備えた Amplify Hosting に Web UI をデプロイします。

**デプロイオプション:**

**オプション A: モック Visa API でデプロイ（Visa 認証情報不要）**
```bash
npm run deploy:frontend --mock
```

**オプション B: 実際の Visa 連携でデプロイ（ステップ 4 が必要）**
```bash
npm run deploy:frontend
```

**デプロイされるもの:**
- Amplify Hosting アプリ
- CloudFront ディストリビューション
- 自動ビルド用の GitHub 連携
- エージェント接続用の環境変数
- Visa API 設定（デプロイオプションに基づきモックまたは実際）

**期待される出力:**
- ライブアプリ URL（CloudFront ディストリビューション）
- Amplify アプリ ID

**確認:**
```bash
# フロントエンドスタックの出力を確認
aws cloudformation describe-stacks \
  --stack-name FrontendStack \
  --query 'Stacks[0].Outputs'

# デプロイされた URL にアクセス
```

**注意:** ローカル Visa サーバーはローカル開発（`npm run dev`）でのみ動作します。CloudFront にデプロイする場合は、以下のいずれかが必要:
- モックモードを使用（`--mock` フラグ）、または
- 実際の決済処理用に Visa Lambda プロキシをデプロイ（ステップ 4）


## 設定

### デプロイ ID

プロジェクトルートの `deployment-config.json` で設定:

```json
{
  "deploymentId": "shopping",
  "description": "Unique identifier for this deployment"
}
```

同じ AWS アカウントに複数の独立したインスタンスをデプロイするには `deploymentId` を変更します。

### 環境変数

**Agent コンテナ**（自動設定）:
```bash
MEMORY_ID=<memory-id>
USER_PROFILE_TABLE_NAME=<table-name>
WISHLIST_TABLE_NAME=<table-name>
FEEDBACK_TABLE_NAME=<table-name>
DEPLOYMENT_ID=<deployment-id>
GATEWAY_CLIENT_ID=<cognito-client-id>
GATEWAY_USER_POOL_ID=<user-pool-id>
GATEWAY_SCOPE=concierge-gateway/invoke
```

**Web UI**（`web-ui/.env.local` に自動生成）:
```env
VITE_AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
VITE_AGENT_ENDPOINT_NAME=DEFAULT
VITE_AWS_REGION=us-east-1
```

## デプロイスクリプトリファレンス

| スクリプト | 説明 | 時間 |
|--------|-------------|------|
| `npm run deploy` | Amplify + MCP + Agent + Visa Lambda をデプロイ | 約10分 |
| `npm run deploy:amplify` | Amplify バックエンドのみデプロイ | 約4分 |
| `npm run deploy:mcp` | MCP サーバーのみデプロイ | 約60秒 |
| `npm run deploy:agent` | Agent スタックのみデプロイ | 約4分 |
| `npm run deploy:visa-lambda` | Visa Lambda プロキシをデプロイ | 約2分 |
| `npm run deploy:frontend` | Amplify Hosting に Web UI をデプロイ | 約3分 |
| `npm run dev` | ローカル開発サーバーを起動 | - |
| `npm run build` | 本番用に Web UI をビルド | - |
| `npm run clean` | すべてのリソースを削除（frontend、agent、MCP、Visa Lambda、Amplify） | 約6分 |
| `npm run clean:frontend` | フロントエンドのみ削除 | 約1分 |
| `npm run clean:agent` | Agent スタックのみ削除 | 約2分 |
| `npm run clean:mcp` | MCP サーバーのみ削除 | 約1分 |
| `npm run clean:visa-lambda` | Visa Lambda プロキシのみ削除 | 約1分 |
| `npm run clean:amplify` | Amplify バックエンドのみ削除 | 約2分 |

## トラブルシューティング

### Amplify デプロイの問題

**問題:** `amplify_outputs.json` が作成されない
```bash
# 解決策: デプロイが正常に完了したことを確認
npm run deploy:amplify

# CloudFormation スタックのステータスを確認
aws cloudformation describe-stacks --stack-name amplify-*
```

**問題:** Cognito エクスポートが見つからない
```bash
# 解決策: エクスポートが存在することを確認
aws cloudformation list-exports --query "Exports[?contains(Name, 'ConciergeAgent')]"
```

### MCP デプロイの問題

**問題:** MCP スタックのデプロイが失敗
```bash
# 解決策: 先に Amplify がデプロイされていることを確認
npm run deploy:amplify

# Docker が実行中であることを確認
docker ps

# エージェントコードパスが存在することを確認
ls -la concierge_agent/mcp_cart_tools/
ls -la concierge_agent/mcp_shopping_tools/
```

### Agent スタックデプロイの問題

**問題:** MCP ランタイム ARN をインポートできない
```bash
# 解決策: 先に MCP スタックがデプロイされていることを確認
npm run deploy:mcp

# MCP エクスポートを確認
aws cloudformation list-exports --query "Exports[?contains(Name, 'RuntimeArn')]"
```

**問題:** Docker ビルドが失敗
```bash
# 解決策: Docker が実行中であることを確認
docker ps

# ローカルでビルドをテスト
cd concierge_agent/supervisor_agent
docker build -t test-build .
```

**問題:** OAuth プロバイダーの作成が失敗
```bash
# 解決策: Lambda ログを確認
aws logs tail /aws/lambda/AgentStack-*-OAuthProviderLambda* --follow

# Lambda の IAM 権限を確認
```

### Gateway の問題

**問題:** Gateway が "An internal error occurred" を返す

**解決策:** デバッグモードを有効にして詳細なエラーを確認:

```bash
# スタック出力からゲートウェイ ID を取得
GATEWAY_ID=$(aws cloudformation describe-stacks \
  --stack-name AgentStack-shopping \
  --query 'Stacks[0].Outputs[?OutputKey==`GatewayId`].OutputValue' \
  --output text)

# デバッグを有効化
aws bedrock-agentcore-control update-gateway \
  --gateway-identifier $GATEWAY_ID \
  --exception-level DEBUG
```

または CDK のゲートウェイコンストラクトを更新して `exceptionLevel: 'DEBUG'` を含めます。

### Web UI の問題

**問題:** `.env.local` が作成されない
```bash
# 解決策: Agent スタックがデプロイされていることを確認
npm run deploy:agent

# 手動で設定
./scripts/setup-web-ui-env.sh
```

**問題:** 認証が失敗
```bash
# Cognito 設定を確認
cat web-ui/.env.local

# ユーザーが存在することを確認
aws cognito-idp list-users --user-pool-id <pool-id>
```

**問題:** エージェントが応答しない
```bash
# Agent Runtime ARN が正しいことを確認
cat web-ui/.env.local

# ランタイムがアクティブであることを確認
aws bedrock-agentcore list-runtimes
```

### よくある問題
**AWS CLI**: AWS CLI が認証情報で設定され、最新バージョンが実行されていることを確認

**API Gateway ロギング**: CloudWatch で API Gateway ログが有効になっていることを確認

**エラー: CloudWatch Logs role ARN must be set in account settings to enable logging (Service: ApiGateway, Status Code: 400**

1. API Gateway が CloudWatch にログをプッシュするための IAM ロールを作成:

   ```aws iam create-role --role-name APIGatewayCloudWatchLogsRole --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"apigateway.amazonaws.com"},"Action":"sts:AssumeRole"}]}'```

2. ログのプッシュを許可するマネージドポリシーをアタッチ:

   ```aws iam attach-role-policy --role-name APIGatewayCloudWatchLogsRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs```

3. このロールを使用するように API Gateway アカウント設定を設定:

   ```aws apigateway update-account --patch-operations op=replace,path=/cloudwatchRoleArn,value=arn:aws:iam::<account_id>:role/APIGatewayCloudWatchLogsRole```

**AgentCore オブザーバビリティ**: デバッグ用に CloudWatch Transaction Search とログ配信を有効化


CloudWatch Transaction Search の1回限りのアカウントセットアップ（トレース/スパンを有効化）
1. CloudWatch コンソールを開く
2. Application Signals (APM) → Transaction search に移動
3. "Enable Transaction Search" をクリック
4. "Ingest spans as structured logs" をチェック
5. Save をクリック

リソースごとのログ配信（AgentCore コンソールで設定）
1. AgentCore コンソール → Runtime/Memory/Gateway を選択
2. "Log delivery" セクションまでスクロール → "Add" をクリック
3. CloudWatch Logs を選択、APPLICATION_LOGS タイプを選択
4. 保存

Runtime トレーシングを有効化（ランタイムごと）
1. AgentCore コンソール → Runtime agents → ランタイムを選択
2. "Tracing" セクションまでスクロール → 有効化


**Docker ビルドが失敗**: Docker が実行中であることを確認

**権限エラー**: IAM ロールに Bedrock と DynamoDB の権限があることを確認

**フロントエンドビルドが失敗**: `web-ui/src` の TypeScript エラーを確認

**ランタイム接続が失敗**: `.env.local` のランタイム ARN を確認

**CloudFormation エクスポートが見つからない**: デプロイ順序を確認（Amplify → MCP → Agent）

## システムの更新

### Agent コードの更新
```bash
# concierge_agent/supervisor_agent/ に変更を加える
npm run deploy:agent
```

### MCP サーバーコードの更新
```bash
# concierge_agent/mcp_cart_tools/ または mcp_shopping_tools/ に変更を加える
# 再ビルドを強制するために Dockerfile をタッチ
find concierge_agent/mcp_* -name Dockerfile -exec touch {} \;
npm run deploy:mcp
```

### Amplify バックエンドの更新
```bash
# amplify/ に変更を加える
npm run deploy:amplify
```

### Web UI の更新
```bash
# web-ui/src/ に変更を加える
# ローカル開発用
npm run dev

# デプロイ済みフロントエンド用
npm run deploy:frontend
```

## クリーンアップ

### すべてのリソースを削除
```bash
npm run clean
```

これにより以下が順番に削除されます:
1. フロントエンド（Amplify Hosting）
2. Agent スタック（Runtime、Memory、Gateway、OAuth Provider）
3. MCP サーバー（Cart と Shopping）
4. Amplify バックエンド（Cognito、AppSync、DynamoDB）

### 部分的なクリーンアップ
```bash
# フロントエンドのみ削除
npm run clean:frontend

# Agent スタックのみ削除
npm run clean:agent

# MCP サーバーのみ削除
npm run clean:mcp

# Amplify バックエンドのみ削除
npm run clean:amplify
```

**注意:** 一部のリソースは手動で削除が必要な場合があります:
- CloudWatch ロググループ
- SSM パラメータ
- Secrets Manager シークレット（Visa 認証情報）

## コストに関する考慮事項

### Amplify スタック
- Cognito: 無料利用枠あり
- AppSync: リクエストごとの課金
- DynamoDB: オンデマンド価格
- Lambda: 無料利用枠あり

### インフラストラクチャスタック
- **Bedrock AgentCore**: 呼び出しごとの課金
- **Memory**: 操作ごとの課金
- **ECR**: 最小限のストレージコスト
- **MCP Runtimes**: 呼び出しごとの課金
- **Gateway**: リクエストごとの課金

### 最適化のヒント
- 使用しないときはサンドボックス環境を削除
- DynamoDB にはオンデマンド価格を使用
- Bedrock の使用量を監視
- 請求アラートを設定

## 推奨事項

1. **サンドボックスの代わりに Amplify Pipelines を使用**:
```bash
npx ampx pipeline-deploy --branch main
```

2. **インフラストラクチャスタックに CDK Pipelines を使用**

3. **モニタリングを有効化**:
   - CloudWatch ダッシュボード
   - X-Ray トレーシング
   - Bedrock 使用量メトリクス

4. **セキュリティ強化**:
   - Cognito で MFA を有効化
   - IAM 権限を制限
   - CloudTrail ロギングを有効化
   - API キーを AWS Secrets Manager に保存

5. **バックアップ戦略**:
   - DynamoDB ポイントインタイムリカバリ
   - 定期的な設定バックアップ

### 次のステップ

デプロイ成功後:
1. Cognito ユーザーを作成（管理者のみ）
2. サンプルクエリでエージェントをテスト
3. エージェントのパフォーマンスを監視
4. 必要に応じてエージェントプロンプトをカスタマイズ
5. 本番環境を設定
6. モニタリングとアラートを設定

## 追加リソース

- [インフラストラクチャ README](infrastructure/README.md)
- [メイン README](README.md)
- [AWS CDK ドキュメント](https://docs.aws.amazon.com/cdk/)
- [Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Amplify ドキュメント](https://docs.amplify.aws/)
