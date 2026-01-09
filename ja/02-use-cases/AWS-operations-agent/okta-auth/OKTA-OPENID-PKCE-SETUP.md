# Okta OpenID Connect PKCE セットアップガイド

AWS Support Agent AgentCore システム用の Okta OAuth2 認証セットアップの完全ガイド。

## 概要

このガイドでは、AgentCore システム用の Okta OAuth2 認証を設定します。ユーザー認証（PKCE フロー）とマシン間認証（クライアント認証情報フロー）の両方をサポートしています。

## 前提条件

- **Okta 開発者アカウント**（[developer.okta.com](https://developer.okta.com) で無料取得可能）
- **AWS アカウント**（Bedrock AgentCore へのアクセス権付き）
- **nginx**（ローカルテスト用にインストール済み）
- **Python 3.11+**（システム実行用）

## Okta アプリケーションセットアップ

#### PKCE APP セットアップの OKTA ドキュメント:

https://developer.okta.com/blog/2019/08/22/okta-authjs-pkce

https://developer.okta.com/docs/guides/implement-grant-type/authcodepkce/main/

#### `"Access the Okta Integrator Free Plan" で Okta 開発者アカウントを作成 https://developer.okta.com/signup/`

### 1. OIDC アプリケーションの作成

1. **Okta 開発者コンソールにログイン**
2. **移動先**: Applications → Applications → Create App Integration
3. **選択**: OIDC - OpenID Connect → Single-Page Application (SPA)
4. **アプリケーションの設定**: アプリケーションを編集し、以下の値を入力
   ```
   App name: aws-support-agent-client
   Grant types: ✅ Authorization Code, ✅ Refresh Token
   Sign-in redirect URIs:
     - http://localhost:8080/callback
     - http://localhost:8080/okta-auth/
     - http://localhost:8080/okta-auth/iframe-oauth-flow.html
   Sign-out redirect URIs: http://localhost:8080/
   Controlled access: Allow everyone in your organization to access
   uncheck "Immediate app access with Federation Broker Mode"
   ```
5. アプリケーションを**保存**し、**Client ID** をメモ
```
aws-support-agent-client アプリケーションの Assignments に自分が追加されていることを確認
```

### 2a. API スコープとポリシーの設定

1. **移動先**: Security → API → Authorization Servers → default
2. **スコープが存在することを確認**:
   - `openid` - OpenID Connect に必要
   - `profile` - ユーザープロファイル情報
   - `email` - ユーザーメールアドレス
3. **カスタムスコープを追加**:
   - **Name**: `api`
   - **Description**: API access for AgentCore
   - **Include in public metadata**: ✅
   - **Set as a default scope**: ✅
4. **アクセスポリシーを追加**:
    - デフォルト認可サーバーで 'Access Policies' タブをクリック
    - Add Policy をクリック
    - **Name**: `All`
    - **Description**: Access to all
    - Create Policy をクリック
    - Add Rule をクリック
    - **Rule Name**: 'All'
    - Create Rule をクリック

### 2b. CORS の設定
```
Security → API → Trusted Origins で、http://localhost:8080 の CORS を有効化
Origin: http://localhost:8080
 ✅ Cross-Origin Resource Sharing (CORS)
 ✅ Redirect
 ✅ iFrame embed
 ✅ Allows iFrame embedding of Okta End User Dashboard
```

### 3. マシン間アプリケーションの作成

AgentCore ワークロード認証用:

1. **新しいアプリインテグレーションを作成**:
```
   移動先: Applications → Applications → Create App Integration

   App Type: API Services
```
2. **設定**: アプリケーションを編集し、以下の値を入力
   ```
   App name: aws-support-agent-m2m
   Client authentication: ✅ Client secret
   Grant types: ✅ Client Credentials
   General Settings の右にある edit をクリックし、Grant types の下で Advanced をクリック
      Enable : Token Exchange
      Disable : Require Demonstrating Proof of Possession (DPoP)
      Save をクリック
   ```
3. **保存**し、**Client ID** と **Client Secret** をメモ

### 4. 認可サーバーのオーディエンスを変更

1. **移動先**: Security → API → Authorization Servers
2. デフォルトの認可サーバーを編集（ヒント - 右側の鉛筆マークをクリック）
3. 設定の下で edit をクリック
4. **Audience**: api://default から 'myagentcoreaud' またはその他の名前に変更
5. Save をクリック

### 注意:
```
a) Directory > People からユーザーを追加できます
    - そうでない場合、Admin ユーザーでログインすると、http://localhost:8080/okta-auth/iframe-oauth-flow.html での PKCE ログイン時に Okta verify アプリからの OTP 入力を求められます
b) このユーザーが 'aws-support-agent-client' アプリに割り当てられていることを確認
c) 'aws-support-agent-client' と 'aws-support-agent-m2m' の両方のアプリ間で共通の認可サーバーを使用しています。本番環境では、分離とセキュリティニーズのために各アプリに異なる認可サーバーがあります。また、M2M フローで AgentCore Identity によって生成されたトークンをデコードできないため、共通の認可サーバーを維持することで、HTML ページ（http://localhost:8080/okta-auth/iframe-oauth-flow.html）経由で PKCE フローからトークンをデコードできます。トークンをデコードすることで、スコープとオーディエンスがアクセストークンに正しく追加されていることを検証できます。
```

# Nginx のローカルインストール

### Nginx インストールドキュメント: https://docs.nginx.com/nginx/admin-guide/installing-nginx/installing-nginx-open-source/

## macOS インストール

### Homebrew を使用（推奨）

1. Homebrew のインストール（まだインストールされていない場合）:
  bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"


2. Nginx のインストール:
  bash
   brew install nginx


3. Nginx の起動:
  bash
   brew services start nginx


4. インストールの確認:
  ブラウザで http://localhost:8080 にアクセス。Nginx のウェルカムページが表示されるはずです。

デフォルト設定場所: /opt/homebrew/etc/nginx/nginx.conf

## Windows インストール

### 直接ダウンロード

1. Nginx のダウンロード:
   • [nginx.org/en/download.html](http://nginx.org/en/download.html) にアクセス
   • Windows バージョン（安定版リリース）をダウンロード

2. ファイルの展開:
   • ダウンロードした zip ファイルを C:\nginx に展開

3. Nginx の起動:
   • コマンドプロンプトを管理者として開く
   • nginx ディレクトリに移動:
    cmd
     cd C:\nginx

   • nginx を起動:
    cmd
     nginx.exe


4. インストールの確認:
  ブラウザで http://localhost にアクセス。Nginx のウェルカムページが表示されるはずです。


### 設定ファイル（Windows）
• **メイン設定**: C:\nginx\conf\nginx.conf
• **ドキュメントルート**: C:\nginx\html

## Linux インストール

必要に応じて sudo を使用。

1. apt update -y
2. apt upgrade -y
3. apt install nginx

デフォルト nginx の場所: /etc/nginx
デフォルト nginx 設定: /etc/nginx/nginx.conf

デフォルトサーバーブロックの場所: etc/nginx/sites-enabled/default

サーバーがポート 80 で動作している場合、8080 に変更。ファイルを保存して終了。
```
server {
	listen 8080 default_server;
	listen [::]:8080 default_server;
```
nginx を再起動

```
Bash > nginx -s reload

# このドキュメントの以下の手順に従って、このファイルのサーバーブロックを置き換えてください。
```
## 共通コマンド

### Nginx の起動と停止

### macOS（Homebrew）:
bash
#### 起動
brew services start nginx

#### 停止
brew services stop nginx

#### 再起動
brew services restart nginx


### Windows:
cmd
#### 起動
nginx.exe

#### 停止
nginx.exe -s stop

#### 設定のリロード
nginx.exe -s reload


### 設定のテスト
bash
# 設定ファイルのテスト
nginx -t


## デフォルトポート
• **macOS**: ポート 8080（Homebrew デフォルト）
• **Windows**: ポート 80（ポートを 8080 に変更するか、すべての Okta とローカル設定から 8080 を削除する必要があります）

必要に応じて nginx 設定ファイルでポートを変更できます。

## Nginx インストールの確認

```
curl http://localhost:8080

# 期待される出力: Welcome to nginx!
```

## Nginx セットアップの設定

ローカル PKCE テストのために、nginx 設定にサーバーブロックを追加する必要があります:

```bash
ステップ 1: nginx サーバーブロックの設定
# プロジェクトディレクトリに移動
cd /path/to/your/AWS-operations-agent/project

ステップ 1: /path/to/your/AWS-operations-agent/okta-auth/nginx/ にある nginx 設定ファイル 'okta-local.conf' のパスを更新
# プレースホルダーパスを実際のプロジェクトパスに置き換え
# 'okta-local.conf' のサーバーブロックで更新するパスは 2 つ。プロジェクトからの絶対パスを使用。
# 1. root /path/to/your/AWS-operations-agent/okta-auth;
# 2. location
#/okta-auth {
#        このパスを更新: 実際のプロジェクトパス + /okta-auth に置き換え
#        alias /path/to/your/AWS-operations-agent/okta-auth;

# パスが正しく更新されたことを確認
cat okta-auth/nginx/okta-local.conf | grep "root\|alias"

ステップ 2: 重要 - okta-local.conf にはサーバーブロックのみが含まれ、完全な nginx.conf ではありません
# このサーバーブロックを既存の nginx 設定のサーバーブロックと置き換える必要があります。

# 手動統合手順:
1. nginx.conf の場所を見つける:
#    - macOS（Homebrew）: /usr/local/etc/nginx/nginx.conf または /opt/homebrew/etc/nginx/nginx.conf
#    - Linux: /etc/nginx/nginx.conf
#    - Docker: /etc/nginx/nginx.conf

2. 現在の nginx.conf のバックアップを作成
sudo cp /opt/homebrew/etc/nginx/nginx.conf /opt/homebrew/etc/nginx/nginx.conf.backup  # macOS
# sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup                    # Linux

3. メインの nginx.conf ファイルを編集用に開く:
sudo vi /opt/homebrew/etc/nginx/nginx.conf  # macOS
# sudo nano /etc/nginx/nginx.conf          # Linux

4. nginx.conf 内の http {} ブロックを見つける
5. 既存のサーバーブロックをコメントアウト/削除
6. okta-auth/nginx/okta-local.conf からサーバーブロック全体をコピー
7. 既存の http {} ブロック内（閉じ括弧 } の前）に貼り付け
8. ファイルを保存して閉じる

# 注意: setup-local-nginx.sh スクリプトは MAC と Windows のセットアップでは動作しません。
# okta-local.conf を完全な nginx 設定として使用しようとするため、失敗します。Linux セットアップではサーバーブロックが別ファイルなので動作します。

ステップ 3: nginx のテストとリロード
# 構文エラーがないか nginx 設定をテスト
sudo nginx -t

# テストが通った場合、nginx 設定をリロード
sudo nginx -s reload

curl http://localhost:8080/okta-auth/iframe-oauth-flow.html
# 期待される出力: PKCE OpenID Flow HTML ページ
```

### 2. OAuth フローのテスト

提供された HTML テストページを使用:

1. `okta-auth/iframe-oauth-flow.html` の**設定を更新**:
   ```javascript
   const config = {
     clientId: 'YOUR_SPA_CLIENT_ID',
     redirectUri: 'http://localhost:8080/okta-auth/',
     authorizationEndpoint: 'https://your-domain.okta.com/oauth2/default/v1/authorize',
     tokenEndpoint: 'https://your-domain.okta.com/oauth2/default/v1/token',
     scope: 'openid profile email',
   };
   ```
または HTML ページで値を入力できます。

2. a) **ブラウザを開く**: http://localhost:8080/okta-auth/iframe-oauth-flow.html
2. b) HTML ページで以下の値を入力/更新:
      - Okta Domain: **Okta コンソールページの右上の名前をクリック** - integrator-xxxx.okta.com のような形式
      - Client ID: **'aws-support-agent-client' アプリの Client ID**
      - Redirect URI: http://localhost:8080/okta-auth/iframe-oauth-flow.html
      - Authorization Server ID: default
          **新しい認可サーバーを作成した場合を除く** - default の使用を推奨
2. c) 'Validate and Save configuration' をクリック
3. **"Login with Okta" をクリック**: 認証情報を入力してログイン
4. **セッショントークン取得**: セッショントークンが正常に取得された場合、'Continue with iframe PKCE Flow' をクリック
5. **iframe PKCE**: Okta でユーザーに付与した権限によっては、okta verify からのコード入力が必要な場合があります。通常、管理者権限はこの追加検証をトリガーします。
6. **アクセストークンのデコード**: decode access token をクリックし、下にスクロールしてトークン内の audience と scope（api）を検証。
7. テスト用に**アクセストークンをコピー**

## プロジェクト設定

### 1. 静的設定の更新

`config/static-config.yaml` を編集: すべての Okta 固有の設定値を更新。

```yaml
# Okta OAuth2 設定（デプロイメントスクリプトとゲートウェイ作成で使用）
okta:
  domain: "<YOUR_OKTA_DOMAIN>"

  # OAuth2 認可サーバー設定（デフォルト認可サーバーを維持することを推奨。そうでない場合は設定 URL を変更）
  authorization_server: "default"

  # ユーザー認証用クライアント設定（PKCE フロー）
  user_auth:
    client_id: "<YOUR_OKTA_CLIENT_ID>"
    audience: "<YOUR_OKTA_AUTHORIZATION_SERVER_AUDIENCE>"
    redirect_uri: "http://localhost:8080/callback"
    scope: "openid profile email"

  # M2M フロー用 JWT トークン設定
  jwt:
    audience: "<YOUR_OKTA_AUTHORIZATION_SERVER_AUDIENCE>"
    issuer: "https://<YOUR_OKTA_DOMAIN>/oauth2/default"
    discovery_url: "https://<YOUR_OKTA_DOMAIN>/oauth2/default/.well-known/openid-configuration"
    cache_duration: 300
    refresh_threshold: 60

# Runtime 用 AgentCore JWT オーソライザー設定
agentcore:
  jwt_authorizer:
    discovery_url: "https://<YOUR_OKTA_DOMAIN>/oauth2/default/.well-known/openid-configuration"
    allowed_audience:
      - "<YOUR_OKTA_AUTHORIZATION_SERVER_AUDIENCE>"
```

### 2. 環境変数の設定

```bash
# オプション: デフォルトと異なる場合は AWS プロファイルを設定してエクスポート - default の使用を推奨
export AWS_PROFILE="your-aws-profile"
```


## システムのデプロイとテスト

### 1. インフラストラクチャのデプロイ - README.md に戻って手順を確認

```bash
# AgentCore システムをデプロイ
cd agentcore-runtime/deployment
./01-prerequisites.sh
./02-create-memory.sh
./03-setup-oauth-provider.sh  # Okta 設定を使用
./04-deploy-mcp-tool-lambda.sh
./05-create-gateway-targets.sh
./06-deploy-diy.sh
./07-deploy-sdk.sh
```

## 認証フロー

### ユーザー認証（PKCE）
1. **ユーザー** → Okta ログイン → JWT トークン
2. **チャットクライアント** → AgentCore Runtime（JWT 付き）
3. **Runtime が検証** Okta ディスカバリーエンドポイントに対して JWT を検証
4. **Runtime が処理** ユーザーリクエスト

### マシン間（M2M）
1. **Runtime** → AgentCore Identity → ワークロードトークン
2. **ワークロードトークン** → OAuth プロバイダー → M2M トークン
3. **M2M トークン** → AgentCore Gateway → ツールアクセス
4. **ツール** → AWS サービス → 結果

## トラブルシューティング

### よくある問題

**1. Invalid Client エラー**
```bash
# static-config.yaml のクライアント ID を確認
grep -A 10 "client details:" config/static-config.yaml
grep -A 10 "user_auth:" config/static-config.yaml
```

**2. トークン検証の失敗**
```bash
# Okta ディスカバリーエンドポイントを検証
curl https://your-domain.okta.com/oauth2/default/.well-known/openid-configuration

```

### ログ分析

**AgentCore Runtime ログ**（確認項目）:
- `✅ OAuth initialized with provider`
- `✅ M2M token obtained successfully`
- `✅ MCP client ready`

**よくあるエラーパターン**:
- `❌ OAuth provider not found` → デプロイメントステップ 03 を確認
- `❌ Invalid client credentials` → クライアントシークレット環境変数を確認
- `❌ Token validation failed` → static-config.yaml の JWT 設定を確認

## セキュリティベストプラクティス

1. **シークレットをコミットしない** - クライアントシークレットには常に環境変数を使用
2. **本番環境では HTTPS を使用** - 本番デプロイメント用にリダイレクト URI を更新
3. **トークンを定期的にローテーション** - Okta で適切なトークン有効期間を設定
4. **トークンオーディエンスを検証** - JWT オーディエンス検証が厳格であることを確認
5. **認証を監視** - Okta システムログを定期的にレビュー

## 本番デプロイメント

本番環境では以下を更新:

1. **リダイレクト URI** を本番ドメインに
2. **環境変数** をデプロイメントパイプラインに
3. **ネットワークセキュリティ** で適切にアクセスを制限
4. **トークン有効期間** をセキュリティ要件に基づいて設定

---

追加のヘルプについては以下を参照:
- [Okta 開発者ドキュメント](https://developer.okta.com/docs/)
- [AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [プロジェクト README](../README.md) で完全なシステムセットアップを確認
