# フロントエンド実装 - すぐに使えるデータアナリストアシスタントアプリケーションとの AgentCore 統合

このチュートリアルでは、**[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)** デプロイメントと統合する React Web アプリケーションのセットアップを案内し、ビデオゲーム売上データアナリストアシスタントを作成します。

> [!NOTE]
> **作業ディレクトリ**: このチュートリアルを開始する前に、`amplify-video-games-sales-assistant-agentcore-strands/` フォルダにいることを確認してください。このガイドのすべてのコマンドはこのディレクトリから実行する必要があります。

## 概要

このチュートリアルを完了すると、Amazon Bedrock AgentCore を搭載したデータアナリストアシスタントインターフェースとユーザーが対話できる、完全に機能する生成 AI Web アプリケーションが完成します。

アプリケーションは2つの主要コンポーネントで構成されます：

- **React Web アプリケーション**: ユーザーインターフェースを提供し、ユーザーインタラクションを処理
- **Amazon Bedrock AgentCore 統合**：
    - データ分析と自然言語処理に AgentCore デプロイメントを使用
    - アプリケーションはアシスタントとの対話のために Amazon Bedrock AgentCore を呼び出し
    - チャート生成と可視化のために Claude 3.7 Sonnet モデルを直接呼び出し

> [!IMPORTANT]
> このサンプルアプリケーションはデモ目的のみであり、本番環境には対応していません。組織のセキュリティベストプラクティスでコードを検証してください。

## 前提条件

開始前に、以下を確認してください：

- [Node.js バージョン 18 以上](https://nodejs.org/en/download/package-manager)

## フロントエンドアプリケーションのセットアップ

### 依存関係のインストール

React アプリケーションフォルダ（amplify-video-games-sales-assistant-agentcore-strands/）に移動し、依存関係をインストール：

``` bash
npm install
```

### Amplify CLI のインストール

Amplify CLI をグローバルにインストール：

``` bash
npm install -g @aws-amplify/cli
```

### Amplify プロジェクトの初期化

Amplify プロジェクトを初期化：

``` bash
amplify init
```

- Do you want to continue with Amplify Gen 1? **`yes`**
- Why would you like to use Amplify Gen 1? **`Prefer not to answer`**

以下の設定を使用：

- ? Enter a name for the project: **`daabedrockagentcore`**

以下のデフォルト設定を使用：
- Name: **daabedrockagentcore**
- Environment: dev
- Default editor: Visual Studio Code
- App type: javascript
- Javascript framework: react
- Source Directory Path: src
- Distribution Directory Path: build
- Build Command: npm run-script build
- Start Command: npm run-script start

- ? Initialize the project with the above configuration? **`Yes`**
- ? Select the authentication method you want to use: **`AWS profile`**

### 認証の追加

ユーザーサインインを有効にするために Amazon Cognito 認証を追加：

``` bash
amplify add auth
```

以下の設定を使用：

- Do you want to use the default authentication and security configuration?: **`Default configuration`**
- How do you want users to be able to sign in?: **`Email`**
- Do you want to configure advanced settings?: **`No, I am done`**

### バックエンドリソースのデプロイ

認証リソースを AWS にデプロイ：

``` bash
amplify push
```

- ? Are you sure you want to continue? **`Yes`**

> [!NOTE]
> これにより、ユーザー認証用の Cognito ユーザープールとアイデンティティプールが AWS アカウントに作成されます。フロントエンドアプリケーションの AWS 認証情報は Cognito を通じて自動的に管理されます。

## AuthRole 権限の設定

認証のデプロイ後、認証されたユーザーに AWS サービスへのアクセス権限を付与する必要があります。

1. **AuthRole を見つける**: AWS コンソール → IAM → ロール → amplify-daabedrockagentcore-dev-*-authRole を検索

2. **DynamoDB テーブル ARN を取得**: CDK プロジェクト出力から `QuestionAnswersTableName` の値を取得：

``` bash
# スタック名の環境変数を設定
export STACK_NAME=CdkAgentcoreStrandsDataAnalystAssistantStack

# DynamoDB テーブル名を取得し ARN を構築
export QUESTION_ANSWERS_TABLE_NAME=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='QuestionAnswersTableName'].OutputValue" --output text)
export QUESTION_ANSWERS_TABLE_ARN="arn:aws:dynamodb:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):table/$QUESTION_ANSWERS_TABLE_NAME"
echo "Table ARN: $QUESTION_ANSWERS_TABLE_ARN"
```

3. **このポリシーを追加**（`<account_id>` を AWS アカウント ID に、`<question_answers_table_arn>` をステップ 2 の ARN に、`<agent_arn>` を AgentCore ランタイム ARN に置き換え）：

> [!NOTE]
> AgentCore ランタイム ARN は現在のデプロイメントに基づいて事前に設定されています。別の AgentCore ランタイムを使用している場合は、BedrockAgentCorePermissions セクションの ARN を適宜更新してください。

``` json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "InvokeBedrockModel",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": [
                "arn:aws:bedrock:*:<account_id>:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0",
                "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
                "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
                "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0"
            ]
        },
        {
            "Sid": "DynamoDB",
            "Effect": "Allow",
            "Action": [
                "dynamodb:Query"
            ],
            "Resource": "<question_answers_table_arn>"
        },
        {
            "Sid": "BedrockAgentCorePermissions",
            "Effect": "Allow",
            "Action": "bedrock-agentcore:InvokeAgentRuntime",
            "Resource": [
                "<agent_arn>",
                "<agent_arn>/runtime-endpoint/*"
            ]
        }
    ]
}
```

## 環境変数の設定

ファイル **src/sample.env.js** を **src/env.js** にリネーム：

``` bash
mv src/sample.env.js src/env.js
```

### CDK 出力値の取得

まず、CDK プロジェクト出力から必要な値を取得：

``` bash
# スタック名の環境変数を設定
export STACK_NAME=CdkAgentcoreStrandsDataAnalystAssistantStack

# CDK 出力から DynamoDB テーブル名と AgentCore ロール ARN を取得
export QUESTION_ANSWERS_TABLE_NAME=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='QuestionAnswersTableName'].OutputValue" --output text)
echo "Table Name: $QUESTION_ANSWERS_TABLE_NAME"
```

### 環境変数の更新

**src/env.js** で以下の環境変数を更新：

- **QUESTION_ANSWERS_TABLE_NAME**: 上記コマンドの値を使用
- **AGENT_RUNTIME_ARN**: AgentCore ランタイム ARN（形式: "arn:aws:bedrock-agentcore:region:account:runtime/runtime-name"）
- **AGENT_ENDPOINT_NAME**: 通常、デフォルトエンドポイントの場合は "DEFAULT"
- **LAST_K_TURNS**: コンテキストメモリのために最後の K 会話ターンを取得する AgentCore Memory の値（デフォルト: 10）

また、一般的なアプリケーション説明も更新可能：
- **APP_NAME**: "Data Analyst Assistant"
- **APP_SUBJECT**: "Video Games Sales"
- **WELCOME_MESSAGE**: カスタムウェルカムメッセージ


## データアナリストアシスタントのテスト

アプリケーションをローカルで起動：

``` bash
npm start
```

アプリケーションが http://localhost:3000 でブラウザに開きます。

初回アクセス：
1. **アカウント作成**: 「Create Account」をクリックし、メールアドレスを使用
2. **メール確認**: 確認コードのメールを確認
3. **サインイン**: メールとパスワードでサインイン

アシスタントをテストするためのサンプル質問：

```
こんにちは！
```

```
何を手伝ってもらえますか？
```

```
データの構造はどうなっていますか？
```

```
どの開発者が最も良いレビューを得る傾向がありますか？
```

```
2000年から2010年の間の各地域の総売上はどうでしたか？パーセンテージでデータを教えてください。
```

```
過去10年間で最も売れたゲームは何ですか？
```

```
最も売れているビデオゲームのジャンルは何ですか？
```

```
トップ3のゲームパブリッシャーを教えてください。
```

```
最も良いレビューと最も良い売上を持つトップ3のビデオゲームを教えてください。
```

```
最も多くのゲームがリリースされた年はいつですか？
```

```
最も人気のあるコンソールはどれで、なぜですか？
```

```
会話の短い要約と結論を教えてください。
```

## Amplify Hosting でアプリケーションをデプロイ

アプリケーションをデプロイするには AWS Amplify Hosting を使用できます：

### ホスティングの追加

Amplify プロジェクトにホスティングを追加：

``` bash
amplify add hosting
```

以下の設定を使用：
- Select the plugin module: `Hosting with Amplify Console`
- Type: `Manual deployment`

### アプリケーションの公開

アプリケーションをビルドしてデプロイ：

``` bash
amplify publish
```

これにより React アプリケーションがビルドされ、AWS Amplify Hosting にデプロイされます。アプリケーションにアクセスできる URL を受け取ります。

## アプリケーション機能

おめでとうございます！データアナリストアシスタントは以下の会話型エクスペリエンスを提供できます：

![Video Games Sales Assistant](../images/preview.png)

- **ユーザーの質問に応答するエージェントとの対話型インターフェース**

![Video Games Sales Assistant](../images/preview1.png)

- **表形式で表示される生のクエリ結果**

![Video Games Sales Assistant](../images/preview2.png)

- **エージェントの回答とデータクエリ結果から生成されたチャート可視化（[Apexcharts](https://apexcharts.com/) を使用して作成）**

![Video Games Sales Assistant](../images/preview3.png)

- **データ分析会話から導出されたサマリーと結論**

![Video Games Sales Assistant](../images/preview4.png)

## ありがとうございます

## ライセンス

このプロジェクトは Apache-2.0 ライセンスの下でライセンスされています。