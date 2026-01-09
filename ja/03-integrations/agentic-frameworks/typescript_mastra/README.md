# Amazon Bedrock AgentCore Runtime 用 Typescript Mastra AI サンプル

このプロジェクトは [Express.js](https://expressjs.com/) を使用して Amazon Bedrock AgentCore Runtime の HTTP プロトコルコントラクトを実装しています。[Typescript Mastra AI](https://mastra.ai/) を Amazon Bedrock AgentCore Runtime と統合するための基盤を提供します。

| 情報                | 詳細                                                                         |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ  | ストリーミング                                                               |
| エージェントフレームワーク | Mastra AI (TypeScript)                                                  |
| LLM モデル          | OpenAI GPT-4o-mini                                                           |
| コンポーネント      | AgentCore Runtime、Express.js、ツール付き Mastra Agents                      |
| サンプルの複雑さ    | 簡単                                                                         |

## 概要

Amazon Bedrock AgentCore Runtime は、AI エージェントをデプロイするための安全でサーバーレスなホスティング環境を提供します。この実装は AgentCore HTTP プロトコルコントラクトに準拠した REST API エンドポイントを作成します。

### 機能

- **ストリーミングレスポンス**: エージェントレスポンスのリアルタイムトークンごとのストリーミング
- **ツール付き Mastra Agent**: 3 つの専用ツールを備えたユーティリティエージェント：
  - `getCurrentTimeTool`: 任意のタイムゾーンの現在時刻を取得
  - `calculateTool`: 算術演算を実行（加算、減算、乗算、除算）
  - `generateRandomNumberTool`: 指定された範囲内で乱数を生成
- **Express.js サーバー**: AgentCore プロトコルを実装した HTTP サーバー
- **CloudFormation デプロイ**: Docker コンテナ化による AWS への自動デプロイ
- **SSM 統合**: Parameter Store に保存されるエージェントランタイム設定

## 前提条件

- **Node.js 20 または 21**: Mastra フレームワークに必要
  - [Node.js をダウンロード](https://nodejs.org/en/download/)
  - インストールの確認: `node --version`
- **npm**: パッケージマネージャー（Node.js に付属）
  - インストールの確認: `npm --version`
- **TypeScript**: TypeScript コンパイラー（開発依存関係としてインストール）
- **AWS アカウント**: 適切な権限を持つアクティブな AWS アカウントが必要
  - [AWS アカウントを作成](https://aws.amazon.com/account/)
  - [AWS マネジメントコンソールアクセス](https://aws.amazon.com/console/)
- **AWS CLI**: AWS CLI をインストールし、認証情報を設定
  - [AWS CLI をインストール](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  - [AWS CLI を設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
- **OpenAI API キー**（GPT-4o-mini モデル用）、[ドキュメント](https://openai.com/index/openai-api/)

## ローカル開発とテスト

```bash
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
cd 03-integrations/agentic-frameworks/typescript_mastra
```

### OpenAI API キー

> [!IMPORTANT]
> `<ValidAPIKey>` を [OpenAI](https://openai.com/index/openai-api/) から取得した有効な API キーに置き換えてください。

```bash
export OPENAI_API_KEY="<ValidAPIKey>"
```

### ビルドと実行

```bash
# 依存関係をインストール
npm install

# TypeScript プロジェクトをビルド
npm run build

# サーバーを起動
npm start

# または自動リロード付き開発モードで実行
npm run dev
```

アプリケーションは `http://localhost:8080` で起動します

### エンドポイントのテスト

**/invocations のテスト（ストリーミングレスポンス）:**

```bash
# シンプルな挨拶
curl --no-buffer -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "Hello, how are you?"}'

# 計算ツールでテスト
curl --no-buffer -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "What is 12345 multiplied by 6789?"}'

# 時間ツールでテスト
curl --no-buffer -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "What is the current time in Tokyo?"}'
```

> **注意**: `--no-buffer` フラグはストリーミングレスポンスをリアルタイムで確認できるようにします。

**/ping のテスト:**

```bash
curl http://localhost:8080/ping
```

## AWS CloudFormation を使用した AgentCore Runtime へのデプロイ

### ステップ 1: CloudFormation スタックのデプロイ

> [!IMPORTANT]
> `<ValidAPIKey>` を [OpenAI](https://openai.com/index/openai-api/) から取得した有効な API キーに置き換えてください。

```bash
# CloudFormation スタックをデプロイ
aws cloudformation create-stack \
  --stack-name ts-mastra-agent \
  --template-body file://cloudformation/github-source.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=AgentName,ParameterValue=tsmastraagent \
    ParameterKey=OpenAIApiKey,ParameterValue=<ValidAPIKey>

# スタック作成の完了を待機
aws cloudformation wait stack-create-complete \
  --stack-name ts-mastra-agent

# スタック出力を取得
aws cloudformation describe-stacks \
  --stack-name ts-mastra-agent \
  --query "Stacks[0].Outputs" \
  --output table
```

### ステップ 2: テスト

エージェントがデプロイされたら、[invoke スクリプト](./scripts/invoke-agent.ts)を使用してテストできます。

このスクリプトは SSM Parameter Store から Agent Runtime ARN を取得し、ストリーミングサポート付きでデプロイされたエージェントを呼び出します。

```bash
# AWS リージョンを設定（デフォルトと異なる場合）
export AWS_REGION=us-east-1

# デフォルトプロンプトでエージェントを呼び出し
AGENT_NAME=tsmastraagent npm run invoke-agent

# カスタムプロンプトで呼び出し
AGENT_NAME=tsmastraagent PROMPT="What is 123 times 456?" npm run invoke-agent

# タイムゾーンツールでテスト
AGENT_NAME=tsmastraagent PROMPT="What time is it in Paris?" npm run invoke-agent

# 乱数生成でテスト
AGENT_NAME=tsmastraagent PROMPT="Generate a random number between 1 and 100" npm run invoke-agent
```

スクリプトは以下を行います：
1. `/hostagent/agentcore/tsmastraagent/runtime-arn` の SSM Parameter Store から Agent Runtime ARN を取得
2. プロンプトでエージェントランタイムを呼び出し
3. ターミナルにリアルタイムでレスポンスをストリーミング

## クリーンアップ

CloudFormation スタックで作成されたすべてのリソースを削除するには：

```bash
# CloudFormation スタックを削除
aws cloudformation delete-stack \
  --stack-name ts-mastra-agent

# スタック削除の完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name ts-mastra-agent

# 削除を確認
aws cloudformation describe-stacks \
  --stack-name ts-mastra-agent | grep -q "does not exist" && echo "Stack successfully deleted"
```
