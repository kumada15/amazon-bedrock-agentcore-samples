# Amazon Bedrock AgentCore Runtime 用 Java Google ADK Agent サンプル

このプロジェクトは [Java Spring Boot](https://spring.io/projects/spring-boot) を使用して Amazon Bedrock AgentCore Runtime の HTTP プロトコルコントラクトを実装しています。[Java Google の Agent Development Kit (ADK)](https://github.com/google/adk-java) を Amazon Bedrock AgentCore Runtime と統合するための基盤を提供します。

| 情報                | 詳細                                                                         |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ  | 同期                                                                         |
| エージェントフレームワーク | Java Google ADK                                                         |
| LLM モデル          | Gemini 2.0 Flash                                                             |
| コンポーネント      | AgentCore Runtime                                                            |
| サンプルの複雑さ    | 簡単                                                                         |

## 概要

Amazon Bedrock AgentCore Runtime は、AI エージェントをデプロイするための安全でサーバーレスなホスティング環境を提供します。この実装は AgentCore HTTP プロトコルコントラクトに準拠した REST API エンドポイントを作成します。

## 前提条件

- **Java 17** 以上、[ダウンロード](https://www.oracle.com/java/technologies/downloads/)
- **Maven 3.6+**、[ダウンロード](https://maven.apache.org/download.cgi)
- **AWS アカウント**: 適切な権限を持つアクティブな AWS アカウントが必要
  - [AWS アカウントを作成](https://aws.amazon.com/account/)
  - [AWS マネジメントコンソールアクセス](https://aws.amazon.com/console/)
- **AWS CLI**: AWS CLI をインストールし、認証情報を設定
  - [AWS CLI をインストール](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  - [AWS CLI を設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
- Google AI API キー（Gemini モデル用）、[ドキュメント](https://ai.google.dev/gemini-api/docs/api-key)

## プロジェクト構造

```bash
java_adk/
├── src/
│   ├── main/
│   │   ├── java/com/agentswithek/GoogleADKAgentCore/
│   │   │   ├── controllers/
│   │   │   │   └── AgentCoreRuntimeController.java    # REST エンドポイント
│   │   │   ├── entities/
│   │   │   │   ├── InvocationRequest.java             # リクエスト DTO
│   │   │   │   ├── InvocationResponse.java            # レスポンス DTO
│   │   │   │   └── PingResponse.java                  # ヘルスチェック DTO
│   │   │   └── GoogleAdkAgentCoreApplication.java     # メインアプリケーション
│   │   └── resources/
│   │       └── application.properties                  # 設定
│   └── test/
├── Dockerfile                                          # ARM64 Docker ビルド
├── pom.xml                                             # Maven 依存関係
└── README.md                                           # このファイル
```

## ローカル開発とテスト

```bash
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
cd 03-integrations/agentic-frameworks/java_adk
```

### Google API キー

> [!IMPORTANT]
> `<ValidAPIKey>` を [Google](https://ai.google.dev/gemini-api/docs/api-key) から取得した有効な API キーに置き換えてください。

```bash
export GOOGLE_API_KEY="<ValidAPIKey>"
```

### ビルドと実行

```bash
# Maven で実行
mvn spring-boot:run
```

アプリケーションは `http://localhost:8080` で起動します

### エンドポイントのテスト

**/invocations のテスト:**

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "Hello, how are you?"}'
```

**/ping のテスト:**

```bash
curl http://localhost:8080/ping
```

## AWS CloudFormation を使用した AgentCore Runtime へのデプロイ

### ステップ 1: CloudFormation スタックのデプロイ

> [!IMPORTANT]
> `<ValidAPIKey>` を [Google](https://ai.google.dev/gemini-api/docs/api-key) から取得した有効な API キーに置き換えてください。

```bash
# CloudFormation スタックをデプロイ
aws cloudformation create-stack \
  --stack-name java-adk-agent \
  --template-body file://cloudformation/github-source.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=AgentName,ParameterValue=adkjavaagent \
    ParameterKey=GoogleApiKey,ParameterValue=<ValidAPIKey>

# スタック作成の完了を待機
aws cloudformation wait stack-create-complete \
  --stack-name java-adk-agent

# スタック出力を取得
aws cloudformation describe-stacks \
  --stack-name java-adk-agent \
  --query "Stacks[0].Outputs" \
  --output table
```

### ステップ 2: テスト

エージェントがデプロイされたら、統合テストを使用してテストできます。

### ステップ 1: SSM Parameter Store から Agent Runtime ARN を取得

```bash
# ARN を直接エクスポート（'adkjavaagent' をエージェント名に置き換え）
export AGENT_RUNTIME_ARN=$(aws ssm get-parameter \
  --name "/hostagent/agentcore/adkjavaagent/runtime-arn" \
  --query "Parameter.Value" \
  --output text )

# 設定されていることを確認
echo $AGENT_RUNTIME_ARN

export AWS_REGION="us-west-2"
```

### ステップ 2: 統合テストを実行

```bash
# すべてのテストを実行
mvn test -Dtest=AgentRuntimeInvokerTest
```

## クリーンアップ

CloudFormation スタックで作成されたすべてのリソースを削除するには：

```bash
# CloudFormation スタックを削除
aws cloudformation delete-stack \
  --stack-name java-adk-agent

# スタック削除の完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name java-adk-agent

# 削除を確認
aws cloudformation describe-stacks \
  --stack-name java-adk-agent | grep -q "does not exist" && echo "Stack successfully deleted"
```
