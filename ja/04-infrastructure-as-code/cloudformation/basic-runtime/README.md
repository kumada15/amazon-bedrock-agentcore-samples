# Basic AgentCore Runtime

この CloudFormation テンプレートは、シンプルな Strands エージェントを使用した基本的な Amazon Bedrock AgentCore Runtime をデプロイします。これは最もシンプルな AgentCore デプロイであり、追加の複雑さなしにコアコンセプトを理解し始めるのに最適です。

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

このテンプレートは、以下を含む最小限の AgentCore デプロイを作成します：

- **AgentCore Runtime**: シンプルな Strands エージェントをホスト
- **ECR リポジトリ**: Docker コンテナイメージを保存
- **IAM ロール**: 必要な権限を提供
- **CodeBuild プロジェクト**: ARM64 Docker イメージを自動的にビルド
- **Lambda 関数**: 自動化用のカスタムリソース


これにより、以下に最適です：
- AgentCore の基本を学ぶ
- 迅速なプロトタイピング
- コアデプロイパターンの理解
- 複雑さを追加する前の基盤構築

## アーキテクチャ

![Basic AgentCore Runtime Architecture](architecture.png)

アーキテクチャは以下で構成されます：

- **ユーザー**: エージェントに質問を送信し、レスポンスを受信
- **AWS CodeBuild**: エージェントコードを含む ARM64 Docker コンテナイメージをビルド
- **Amazon ECR リポジトリ**: コンテナイメージを保存
- **AgentCore Runtime**: Basic Agent コンテナをホスト
  - **Basic Agent**: ユーザークエリを処理するシンプルな Strands エージェント
  - レスポンスを生成するために Amazon Bedrock LLM を呼び出し
- **IAM ロール**:
  - CodeBuild 用 IAM ロール (イメージのビルドとプッシュ)
  - Agent Execution 用 IAM ロール (ランタイム権限)
- **Amazon Bedrock LLM**: エージェントに AI モデル機能を提供

## 前提条件

### AWS アカウントのセットアップ

1. **AWS アカウント**: 適切な権限を持つアクティブな AWS アカウントが必要
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
   - 「Model access」に移動し、以下へのアクセスをリクエスト：
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

### オプション 1: デプロイスクリプトを使用 (推奨)

```bash
# スクリプトを実行可能にする
chmod +x deploy.sh

# スタックをデプロイ
./deploy.sh
```

スクリプトは以下を実行します：
1. CloudFormation スタックをデプロイ
2. スタック作成の完了を待機
3. AgentCore Runtime ID を表示

### オプション 2: AWS CLI を使用

```bash
# スタックをデプロイ
aws cloudformation create-stack \
  --stack-name basic-agent-demo \
  --template-body file://template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2

# スタック作成を待機
aws cloudformation wait stack-create-complete \
  --stack-name basic-agent-demo \
  --region us-west-2

# Runtime ID を取得
aws cloudformation describe-stacks \
  --stack-name basic-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeId`].OutputValue' \
  --output text
```

### オプション 3: AWS コンソールを使用

1. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
2. 「Create stack」→「With new resources」をクリック
3. `template.yaml` ファイルをアップロード
4. スタック名を入力: `basic-agent-demo`
5. パラメータを確認 (またはデフォルトを使用)
6. 「I acknowledge that AWS CloudFormation might create IAM resources」をチェック
7. 「Create stack」をクリック

### デプロイ時間

- **予想所要時間**: 10-15 分
- **主なステップ**:
  - スタック作成: 約 2 分
  - Docker イメージビルド (CodeBuild): 約 8-10 分
  - ランタイムプロビジョニング: 約 2-3 分

## テスト

### AWS CLI を使用

```bash
# スタック出力から Runtime ID を取得
RUNTIME_ID=$(aws cloudformation describe-stacks \
  --stack-name basic-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeId`].OutputValue' \
  --output text)

# アカウント ID を取得して ARN を構築
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
RUNTIME_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:runtime/${RUNTIME_ID}"

# ペイロードを準備 (base64 エンコード、改行を避けるために -n フラグを使用)
PAYLOAD=$(echo -n '{"prompt": "What is 2+2?"}' | base64)

# エージェントを呼び出し
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $RUNTIME_ARN \
  --qualifier DEFAULT \
  --payload $PAYLOAD \
  --region us-west-2 \
  response.json

# レスポンスを表示
cat response.json
```

### AWS コンソールを使用

1. [Bedrock AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/) に移動
2. 左側のナビゲーションで「Runtimes」に移動
3. ランタイムを見つける (名前が `basic_agent_demo_` で始まる)
4. ランタイム名をクリック
5. 「Test」ボタンをクリック
6. テストペイロードを入力:
   ```json
   {
     "prompt": "What is 2+2?"
   }
   ```
7. 「Invoke」をクリック



## サンプルクエリ

basic エージェントをテストするために、以下のクエリを試してください：

1. **簡単な計算**:
   ```json
   {"prompt": "What is 2+2?"}
   ```

2. **一般知識**:
   ```json
   {"prompt": "What is the capital of France?"}
   ```

3. **説明のリクエスト**:
   ```json
   {"prompt": "Explain what Amazon Bedrock is in simple terms"}
   ```

4. **クリエイティブタスク**:
   ```json
   {"prompt": "Write a haiku about cloud computing"}
   ```

5. **推論**:
   ```json
   {"prompt": "If I have 5 apples and give away 2, how many do I have left?"}
   ```

## クリーンアップ

### クリーンアップスクリプトを使用 (推奨)

```bash
# スクリプトを実行可能にする
chmod +x cleanup.sh

# スタックを削除
./cleanup.sh
```

### AWS CLI を使用

```bash
aws cloudformation delete-stack \
  --stack-name basic-agent-demo \
  --region us-west-2

# 削除完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name basic-agent-demo \
  --region us-west-2
```

### AWS コンソールを使用

1. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
2. `basic-agent-demo` スタックを選択
3. 「Delete」をクリック
4. 削除を確認
