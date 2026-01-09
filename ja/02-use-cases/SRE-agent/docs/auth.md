# 認証と認可のセットアップ

このドキュメントでは、AgentCore Gateway に必要な IAM 権限と ID プロバイダー（IDP）設定のセットアップ要件について説明します。

## IAM 権限のセットアップ

### AWS マネージドポリシー

簡素化されたセットアップのために、AWS は Bedrock AgentCore 操作に必要なすべての権限を含むマネージドポリシーを提供しています：

**ポリシー名**: `BedrockAgentCoreFullAccess`

このマネージドポリシーは、AgentCore ランタイムで使用される IAM ロールにアタッチする必要があります。以下が含まれます：
- すべての bedrock-agentcore 権限
- 必要な IAM:PassRole 権限
- スキーマストレージ用の S3 アクセス
- その他必要なサービス権限

### 信頼ポリシー要件

IAM ロールには、Bedrock AgentCore サービスがロールを引き受けることを許可する信頼ポリシーを含める必要があります：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock-agentcore.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

### コアゲートウェイ権限（代替）

マネージドポリシーではなく詳細な権限を使用したい場合は、Gateway Target または Gateway での CRUDL 操作の呼び出し、InvokeTool API、ListTool に対してこのポリシーを使用します：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:*",
                "iam:PassRole"
            ],
            "Resource": "*"
        }
    ]
}
```

### S3 スキーマアクセス

S3 内の API スキーマでターゲットを作成するために必要なポリシー（上記のポリシーと同じ呼び出し元 ID にアタッチ）：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "*"
        }
    ]
}
```

### Lambda ターゲット権限

Lambda が Gateway ターゲットタイプの場合、実行ロールには Lambda を呼び出す権限が必要です：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "lambda:InvokeFunction",
            "Resource": "arn:aws:lambda:us-west-2:<account-with-lambda>:function:TestLambda"
        }
    ]
}
```

### Smithy ターゲット権限

Gateway Target が Smithy Target タイプの場合：
- 実行ロールには、呼び出したいツール/API の AWS 権限を含める必要があります
- 例：S3 用のゲートウェイターゲットを追加 → ロールに関連する S3 権限を追加

ロールを引き受けるために AgentCore サービスのベータアカウントを信頼する必要があります：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock-agentcore.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        },
    ]
}
```

### クロスアカウント Lambda アクセス

Lambda が別のアカウントにある場合、Lambda 関数にリソースベースポリシー（RBP）を設定します：

```json
{
    "Version": "2012-10-17",
    "Id": "default",
    "Statement": [
        {
            "Sid": "cross-account-access",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<gateway-account>:role/AgentCoreBetaLambdaExecuteRole"
            },
            "Action": "lambda:InvokeFunction",
            "Resource": "arn:aws:lambda:us-west-2:<account-with-lambda>:function:TestLambda"
        }
    ]
}
```

## ID プロバイダー設定

### 重要：Cognito vs Auth0/Okta 認証の違い

**AgentCore Gateway 設定の重要な区別：**

| プロバイダー | 使用する JWT クレーム | Gateway 設定 | トークンに含まれる |
|----------|---------------|---------------------|----------------|
| **Amazon Cognito** | `client_id` | `allowedClients: ["client-id"]` | ❌ `aud` クレームなし |
| **Auth0** | `aud` | `allowedAudience: ["audience"]` | ✅ `aud` クレームあり |
| **Okta** | `aud` | `allowedAudience: ["audience"]` | ✅ `aud` クレームあり |

**これが重要な理由：**
- Cognito クライアント認証情報トークンには `aud`（オーディエンス）クレームが含まれない
- `allowedAudience` を持つ AgentCore Gateway は Cognito トークンを拒否する（401 エラー）
- Cognito の場合、アプリクライアント ID で `allowedClients` を使用する必要がある
- Auth0/Okta の場合、API 識別子で `allowedAudience` を使用する必要がある

### 1. Amazon Cognito セットアップ

#### オプション A：自動セットアップ（推奨）

完全なエンドツーエンドの Cognito セットアップには、自動化スクリプトを使用します：

```bash
cd deployment
./setup_cognito.sh
```

このスクリプトは以下を行います：
- ユーザープールとドメインを作成
- スコープ付きのリソースサーバーを作成
- 認証情報付きのアプリクライアントを作成
- 必要なすべての変数を含む `.env` ファイルを生成
- すべての Cognito 設定を `deployment/.cognito_config` ファイルに保存
- ゲートウェイセットアップ用の設定詳細を提供

**作成される重要なファイル：**
- `deployment/.cognito_config` - USER_POOL_ID、CLIENT_ID、CLIENT_SECRET、その他の Cognito 設定を含む
- `gateway/.env` - 認証用の環境変数

`gateway/config.yaml` を設定する際に `.cognito_config` の値を参照できます

#### オプション B：手動セットアップ

手動で Cognito をセットアップしたい場合は、以下の手順に従ってください：

#### ユーザープールの作成

マシン間通信用のユーザープールを作成：

```bash
# ユーザープールを作成
aws cognito-idp create-user-pool \
    --region us-west-2 \
    --pool-name "test-agentcore-user-pool"

# プール ID を取得するためにユーザープールをリスト
aws cognito-idp list-user-pools \
    --region us-west-2 \
    --max-results 60
```

#### ディスカバリー URL 形式

```
https://cognito-idp.us-west-2.amazonaws.com/<UserPoolId>/.well-known/openid-configuration
```

#### リソースサーバーの作成

```bash
aws cognito-idp create-resource-server \
    --region us-west-2 \
    --user-pool-id <UserPoolId> \
    --identifier "test-agentcore-server" \
    --name "TestAgentCoreServer" \
    --scopes '[{"ScopeName":"read","ScopeDescription":"Read access"}, {"ScopeName":"write","ScopeDescription":"Write access"}]'
```

#### ユーザープールドメインの作成

**重要**：アクセストークンを取得する前にドメインを作成する必要があります。

```bash
# ユーザープールドメインを作成（トークンエンドポイントに必要）
aws cognito-idp create-user-pool-domain \
    --region us-west-2 \
    --user-pool-id <UserPoolId> \
    --domain "your-unique-domain-name"

# 注意：ドメイン名はすべての AWS アカウント間でグローバルに一意である必要があります
# 例："sre-agent-demo-12345" または "mycompany-sre-agent"
```

#### クライアントの作成

```bash
aws cognito-idp create-user-pool-client \
    --region us-west-2 \
    --user-pool-id <UserPoolId> \
    --client-name "test-agentcore-client" \
    --generate-secret \
    --allowed-o-auth-flows client_credentials \
    --allowed-o-auth-scopes "test-agentcore-server/read" "test-agentcore-server/write" \
    --allowed-o-auth-flows-user-pool-client \
    --supported-identity-providers "COGNITO"
```

#### アクセストークンの取得

```bash
# URL にはドメイン名（UserPoolId ではなく）を使用
curl --http1.1 -X POST https://<your-domain-name>.auth.us-west-2.amazoncognito.com/oauth2/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials&client_id=<ClientId>&client_secret=<ClientSecret>"
```

**注意**：前のステップで作成したドメイン名を使用します。UserPoolId ではありません。URL 形式は次のとおりです：
`https://<domain-name>.auth.<region>.amazoncognito.com/oauth2/token`

#### Cognito トークンクレームの例

```json
{
    "sub": "<>",
    "token_use": "access",
    "scope": "default-m2m-resource-server-<>/read",
    "auth_time": 1749679004,
    "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-<>",
    "exp": 1749682604,
    "iat": 1749679004,
    "version": 2,
    "jti": "<>",
    "client_id": "<>"
}
```

#### Cognito オーソライザー設定

```json
{
    "authorizerConfiguration": {
        "customJWTAuthorizer": {
            "allowedClients": ["<ClientId>"],
            "discoveryUrl": "https://cognito-idp.us-west-2.amazonaws.com/<UserPoolId>/.well-known/openid-configuration"
        }
    }
}
```

### 2. Auth0 セットアップ

#### セットアップ手順

1. **API を作成**（リソースサーバーへの 1:1 マッピング）
2. **アプリケーションを作成**（リソースサーバーへのクライアントとして機能）
3. **API > Settings で API Identifier を設定**（オーディエンスクレームに追加）
4. **API > Scopes セクションでスコープを設定**

#### ディスカバリー URL 形式

```
https://<your-domain>/.well-known/openid-configuration
```

#### アクセストークンの取得

```bash
curl --request POST \
    --url https://dev-<your-domain>.us.auth0.com/oauth/token \
    --header 'content-type: application/json' \
    --data '{
        "client_id":"YOUR_CLIENT_ID",
        "client_secret":"YOUR_CLIENT_SECRET",
        "audience":"gateway123",
        "grant_type":"client_credentials",
        "scope": "invoke:gateway"
    }'
```

#### Auth0 トークンクレームの例

```json
{
    "iss": "https://dev-<>.us.auth0.com/",
    "sub": "<>",
    "aud": "gateway123",
    "iat": 1749741913,
    "exp": 1749828313,
    "scope": "invoke:gateway read:gateway",
    "jti": "<>",
    "client_id": "<>",
    "permissions": [
        "invoke:gateway",
        "read:gateway"
    ]
}
```

#### Auth0 オーソライザー設定

```json
{
    "authorizerConfiguration": {
        "customJWTAuthorizer": {
            "allowedAudience": ["gateway123"],
            "discoveryUrl": "https://dev-<your-domain>.us.auth0.com/.well-known/openid-configuration"
        }
    }
}
```

### 3. Okta セットアップ

#### セットアップ手順

1. **クライアント認証情報グラントタイプでアプリケーションを作成**
   - [Okta ドキュメント](https://developer.okta.com/docs/guides/implement-grant-type/clientcreds/main/)に従う
   - 必要に応じて無料トライアルにサインアップ

2. **アプリケーションを設定**
   - Admin → Applications → シークレット付きのクライアントを作成
   - "Require Demonstrating Proof of Possession (DPoP) header in token requests" を無効化

3. **認可サーバーを設定**
   - Admin → Security → API
   - デフォルトの認可サーバーを使用
   - 追加のスコープを追加（例："InvokeGateway"）
   - オプションでアクセスポリシーとクレームを追加

4. **設定を取得**
   - デフォルトの認可サーバーのメタデータ URI（ディスカバリー URI）を取得
   - JWT オーソライザー設定用の ClientID/Secret を取得

## トークン検証

デバッグ中にベアラートークンをデコードおよび検証するには [jwt.io](https://jwt.io/) を使用します。

## 環境変数

ID プロバイダーをセットアップした後、`.env` ファイルでこれらの環境変数を設定します：

```bash
# Cognito の場合
COGNITO_DOMAIN=https://your-domain-name.auth.us-west-2.amazoncognito.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret

# 'your-domain-name' は以下で作成したドメイン：
# aws cognito-idp create-user-pool-domain --domain "your-domain-name"

# Auth0 の場合
COGNITO_DOMAIN=https://dev-yourdomain.us.auth0.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret
```

## トラブルシューティング

### よくある 401 "Invalid Bearer token" エラー

**問題：** Gateway が HTTP 401 と `"Invalid Bearer token"` メッセージを返す。

**根本原因：** トークンクレームとゲートウェイ設定の不一致。

**解決手順：**

1. **JWT トークンをデコード** [jwt.io](https://jwt.io/) を使用してクレームを検査
2. **トークンクレームを確認：**
   - Cognito トークン：`client_id` クレームを探す（`aud` クレームなし）
   - Auth0/Okta トークン：`aud` クレームを探す
3. **ゲートウェイ設定がトークンと一致することを確認：**
   ```bash
   # トークンに client_id があり aud クレームがない場合（Cognito）
   python main.py "Gateway" --allowed-clients "your-client-id" ...

   # トークンに aud クレームがある場合（Auth0/Okta）
   python main.py "Gateway" --allowed-audience "your-audience" ...
   ```
4. **一般的な修正：**
   - **Cognito ユーザー：** `--allowed-audience` ではなく `--allowed-clients` を使用
   - **Auth0 ユーザー：** `--allowed-clients` ではなく `--allowed-audience` を使用
   - **クライアント ID を確認：** 完全に一致する必要がある（大文字小文字を区別）
   - **オーディエンスを確認：** API 識別子と完全に一致する必要がある

### その他の一般的な問題

- トークンエンドポイントが機能しない場合、ブラウザでディスカバリー URL を確認して正しい `token_endpoint` を見つける
- トークンリクエストとゲートウェイ設定間でオーディエンス値が一致することを確認
- IDP でスコープが適切に設定されていることを確認
- ディスカバリー URL がアクセス可能で有効な OpenID 設定を返すことを確認
- Cognito の場合：アプリクライアントで `client_credentials` グラントタイプが有効になっていることを確認
