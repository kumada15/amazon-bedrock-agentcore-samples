# マルチエージェント AgentCore ランタイム

この CloudFormation テンプレートは、1つのエージェント（オーケストレーター）が別のエージェント（スペシャリスト）を呼び出して複雑なタスクを処理するマルチエージェントアーキテクチャを実演します。このパターンは、専門的な機能を持つ高度な AI システムを構築する際に役立ちます。

## 目次

- [概要](#概要)
- [アーキテクチャ](#アーキテクチャ)
- [前提条件](#前提条件)
- [デプロイ](#デプロイ)
- [テスト](#テスト)
- [サンプルクエリ](#サンプルクエリ)
- [クリーンアップ](#クリーンアップ)
- [コスト見積もり](#コスト見積もり)
- [トラブルシューティング](#トラブルシューティング)
- [コントリビューション](#コントリビューション)
- [ライセンス](#ライセンス)

## 概要

このテンプレートは、エージェント間通信を実演する2つのエージェントシステムを作成します：

### エージェント1: オーケストレーターエージェント
- **役割**: ユーザークエリのメインエントリーポイント
- **機能**:
  - 単純なクエリを直接処理
  - 複雑なタスクをエージェント2に委任
  - エージェント2のランタイムを呼び出すツールを保持
- **ユースケース**: ルーティング、タスク委任、シンプルな Q&A

### エージェント2: スペシャリストエージェント
- **役割**: 詳細な分析のためのエキスパートエージェント
- **機能**:
  - 詳細な分析レスポンスを提供
  - 複雑な推論タスクを処理
  - 正確性と完全性に焦点を当てる
- **ユースケース**: データ分析、専門知識、詳細な説明

### 主な機能

- **マルチエージェント通信**: エージェント1は `bedrock-agentcore:InvokeAgentRuntime` を使用してエージェント2を呼び出し可能
- **自動オーケストレーション**: エージェント1がクエリの複雑さに基づいて委任を判断
- **独立したデプロイ**: 各エージェントは独自の ECR リポジトリとランタイムを保持
- **モジュラーアーキテクチャ**: 追加の専門エージェントを容易に拡張可能

## アーキテクチャ

![マルチエージェント AgentCore ランタイムアーキテクチャ](architecture.png)

アーキテクチャは以下で構成されます：

- **ユーザー**: エージェント1（オーケストレーター）に質問を送信し、レスポンスを受信
- **エージェント1 - オーケストレーターエージェント**:
  - **AWS CodeBuild**: エージェント1の ARM64 Docker コンテナイメージをビルド
  - **Amazon ECR リポジトリ**: エージェント1のコンテナイメージを保存
  - **AgentCore ランタイム**: オーケストレーターエージェントをホスト
    - 単純なクエリを直接ルーティング
    - `call_specialist_agent` ツールを使用して複雑なクエリをエージェント2に委任
    - 推論のために Amazon Bedrock LLM を呼び出し
  - **IAM ロール**: エージェント2のランタイム呼び出しと Bedrock アクセスの権限
- **エージェント2 - スペシャリストエージェント**:
  - **AWS CodeBuild**: エージェント2の ARM64 Docker コンテナイメージをビルド
  - **Amazon ECR リポジトリ**: エージェント2のコンテナイメージを保存
  - **AgentCore ランタイム**: スペシャリストエージェントをホスト
    - 詳細な分析とエキスパートレスポンスを提供
    - 詳細な推論のために Amazon Bedrock LLM を呼び出し
  - **IAM ロール**: 標準のランタイム権限と Bedrock アクセス
- **Amazon Bedrock LLM**: 両エージェントに AI モデル機能を提供
- **エージェント間通信**: エージェント1は `bedrock-agentcore:InvokeAgentRuntime` API を介してエージェント2のランタイムを呼び出し可能

## 前提条件

### AWS アカウントのセットアップ

1. **AWS アカウント**: 適切な権限を持つアクティブな AWS アカウントが必要です
   - [AWS アカウントの作成](https://aws.amazon.com/account/)
   - [AWS コンソールアクセス](https://aws.amazon.com/console/)

2. **AWS CLI**: AWS CLI をインストールし、認証情報を設定
   - [AWS CLI のインストール](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [AWS CLI の設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

   ```bash
   aws configure
   ```

3. **Bedrock モデルアクセス**: AWS リージョンで Amazon Bedrock モデルへのアクセスを有効化
   - [Amazon Bedrock コンソール](https://console.aws.amazon.com/bedrock/) に移動
   - 「モデルアクセス」に移動し、以下へのアクセスをリクエスト：
     - Anthropic Claude モデル
   - [Bedrock モデルアクセスガイド](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. **必要な権限**: AWS ユーザー/ロールには以下の権限が必要：
   - CloudFormation スタック操作
   - ECR リポジトリ管理
   - IAM ロール作成
   - Lambda 関数作成
   - CodeBuild プロジェクト作成
   - BedrockAgentCore リソース作成

## デプロイ

### オプション1: デプロイスクリプトの使用（推奨）

```bash
# スクリプトを実行可能にする
chmod +x deploy.sh

# スタックのデプロイ
./deploy.sh
```

スクリプトは以下を実行します：
1. CloudFormation スタックのデプロイ
2. スタック作成完了を待機
3. 両エージェントのランタイム ID を表示

### オプション2: AWS CLI の使用

```bash
# スタックのデプロイ
aws cloudformation create-stack \
  --stack-name multi-agent-demo \
  --template-body file://template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2

# スタック作成を待機
aws cloudformation wait stack-create-complete \
  --stack-name multi-agent-demo \
  --region us-west-2

# ランタイム ID の取得
aws cloudformation describe-stacks \
  --stack-name multi-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs'
```

### オプション3: AWS コンソールの使用

1. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
2. 「スタックの作成」→「新しいリソースを使用」をクリック
3. `template.yaml` ファイルをアップロード
4. スタック名を入力: `multi-agent-demo`
5. パラメータを確認（またはデフォルトを使用）
6. 「AWS CloudFormation によって IAM リソースが作成される場合があることを承認します」にチェック
7. 「スタックの作成」をクリック




## テスト

### エージェント1（オーケストレーター）のテスト

エージェント1がメインのエントリーポイントです。単純なクエリを直接処理するか、複雑なタスクの場合はエージェント2に委任します。

#### AWS CLI の使用

```bash
# Agent1 ランタイム ID を取得して ARN を構築
AGENT1_ID=$(aws cloudformation describe-stacks \
  --stack-name multi-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`Agent1RuntimeId`].OutputValue' \
  --output text)

# アカウント ID を取得して ARN を構築
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
AGENT1_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:runtime/${AGENT1_ID}"

# 単純なクエリでテスト（Agent1 が直接処理）
PAYLOAD1=$(echo -n '{"prompt": "Hello, how are you?"}' | base64)
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $AGENT1_ARN \
  --qualifier DEFAULT \
  --payload $PAYLOAD1 \
  --region us-west-2 \
  response1.json

# 複雑なクエリでテスト（Agent1 が Agent2 に委任）
PAYLOAD2=$(echo -n '{"prompt": "Provide a detailed analysis of cloud computing benefits"}' | base64)
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $AGENT1_ARN \
  --qualifier DEFAULT \
  --payload $PAYLOAD2 \
  --region us-west-2 \
  response2.json

cat response1.json
cat response2.json
```

### AWS コンソールの使用

1. [Bedrock AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/) に移動
2. 左側のナビゲーションで「Runtimes」に移動
3. Agent1 ランタイムを見つける（名前は `multi_agent_demo_OrchestratorAgent` で始まる）
4. ランタイム名をクリック
5. 「Test」ボタンをクリック
6. テストペイロードを入力：
   ```json
   {
     "prompt": "Hello, how are you?"
   }
   ```
7. 「Invoke」をクリック

### エージェント2（スペシャリスト）の直接テスト

エージェント2の専門機能を直接テストすることもできます。

```bash
# Agent2 ランタイム ID を取得して ARN を構築
AGENT2_ID=$(aws cloudformation describe-stacks \
  --stack-name multi-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`Agent2RuntimeId`].OutputValue' \
  --output text)

# アカウント ID を取得して ARN を構築
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
AGENT2_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:runtime/${AGENT2_ID}"

# ペイロードを準備（base64 エンコード、-n フラグに注意）
PAYLOAD3=$(echo -n '{"prompt": "Explain quantum computing in detail"}' | base64)

# Agent2 を直接呼び出し
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $AGENT2_ARN \
  --qualifier DEFAULT \
  --payload $PAYLOAD3 \
  --region us-west-2 \
  response3.json

cat response3.json
```

## サンプルクエリ

### エージェント1が直接処理するクエリ

これらの単純なクエリは専門知識を必要としません：

1. **挨拶**:
   ```json
   {"prompt": "Hello, how are you?"}
   ```

2. **簡単な計算**:
   ```json
   {"prompt": "What is 5 + 3?"}
   ```


### エージェント2への委任をトリガーするクエリ

これらの複雑なクエリはエキスパート分析を必要とします：

1. **詳細分析**:
   ```json
   {"prompt": "Provide a detailed analysis of the benefits and drawbacks of serverless architecture"}
   ```

2. **専門知識**:
   ```json
   {"prompt": "Explain the CAP theorem and its implications for distributed systems"}
   ```

3. **複雑な推論**:
   ```json
   {"prompt": "Compare and contrast different machine learning algorithms for time series forecasting"}
   ```

4. **詳細な説明**:
   ```json
   {"prompt": "Provide expert analysis on best practices for securing cloud infrastructure"}
   ```

## クリーンアップ

### クリーンアップスクリプトの使用（推奨）

```bash
# スクリプトを実行可能にする
chmod +x cleanup.sh

# スタックの削除
./cleanup.sh
```

### AWS CLI の使用

```bash
aws cloudformation delete-stack \
  --stack-name multi-agent-demo \
  --region us-west-2

# 削除完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name multi-agent-demo \
  --region us-west-2
```

### AWS コンソールの使用

1. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
2. `multi-agent-demo` スタックを選択
3. 「Delete」をクリック
4. 削除を確認
