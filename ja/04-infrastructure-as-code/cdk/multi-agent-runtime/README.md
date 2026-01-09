# マルチエージェント AgentCore ランタイム - CDK

この CDK スタックは、1つのエージェント（オーケストレーター）が別のエージェント（スペシャリスト）を呼び出して複雑なタスクを処理するマルチエージェントアーキテクチャを実演します。このパターンは、専門的な機能を持つ高度な AI システムを構築する際に役立ちます。

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

この CDK スタックは、エージェント間通信を実演する2つのエージェントシステムを作成します：

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

3. **Python 3.10+** と **AWS CDK v2** のインストール
   ```bash
   # CDK のインストール
   npm install -g aws-cdk

   # インストールの確認
   cdk --version
   ```

4. **CDK バージョン 2.220.0 以降**（BedrockAgentCore サポートのため）

5. **Bedrock モデルアクセス**: AWS リージョンで Amazon Bedrock モデルへのアクセスを有効化
   - [Amazon Bedrock コンソール](https://console.aws.amazon.com/bedrock/) に移動
   - 「モデルアクセス」に移動し、以下へのアクセスをリクエスト：
     - Anthropic Claude モデル
   - [Bedrock モデルアクセスガイド](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

6. **必要な権限**: AWS ユーザー/ロールには以下の権限が必要：
   - CloudFormation スタック操作
   - ECR リポジトリ管理
   - IAM ロール作成
   - Lambda 関数作成
   - CodeBuild プロジェクト作成
   - BedrockAgentCore リソース作成

## デプロイ

### CDK と CloudFormation の比較

これはマルチエージェントランタイムの **CDK バージョン** です。CloudFormation を使用する場合は、[CloudFormation バージョン](../../cloudformation/multi-agent-runtime/) を参照してください。

### オプション1: クイックデプロイ（推奨）

```bash
# 依存関係のインストール
pip install -r requirements.txt

# CDK のブートストラップ（初回のみ）
cdk bootstrap

# デプロイ
cdk deploy
```

### オプション2: ステップバイステップ

```bash
# 1. Python 仮想環境を作成してアクティベート
python3 -m venv .venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate

# 2. Python 依存関係のインストール
pip install -r requirements.txt

# 3. アカウント/リージョンで CDK をブートストラップ（初回のみ）
cdk bootstrap

# 4. CloudFormation テンプレートを合成（オプション）
cdk synth

# 5. スタックのデプロイ
cdk deploy --require-approval never

# 6. 出力の取得
cdk list
```

### デプロイ時間

- **想定所要時間**: 15〜20分
- **主なステップ**:
  - スタック作成: 約2分
  - Docker イメージビルド（CodeBuild）: 約10〜12分
  - ランタイムプロビジョニング: 約3〜5分

## テスト

### エージェント1（オーケストレーター）のテスト

エージェント1がメインのエントリーポイントです。単純なクエリを直接処理するか、複雑なタスクの場合はエージェント2に委任します。

#### AWS CLI の使用

```bash
# Agent1 ランタイム ID の取得
AGENT1_ID=$(aws cloudformation describe-stacks \
  --stack-name MultiAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`Agent1RuntimeId`].OutputValue' \
  --output text)

# 単純なクエリでテスト（Agent1 が直接処理）
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $AGENT1_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "Hello, how are you?"}' \
  --region us-east-1 \
  response.json

# 複雑なクエリでテスト（Agent1 が Agent2 に委任）
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $AGENT1_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "Provide a detailed analysis of cloud computing benefits"}' \
  --region us-east-1 \
  response.json

cat response.json
```

### AWS コンソールの使用

1. [Bedrock AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/) に移動
2. 左側のナビゲーションで「Runtimes」に移動
3. Agent1 ランタイムを見つける（名前は `MultiAgentDemo_OrchestratorAgent` で始まる）
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
# Agent2 ランタイム ID の取得
AGENT2_ID=$(aws cloudformation describe-stacks \
  --stack-name MultiAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`Agent2RuntimeId`].OutputValue' \
  --output text)

# Agent2 を直接呼び出し
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $AGENT2_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "Explain quantum computing in detail"}' \
  --region us-east-1 \
  response.json
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

### CDK の使用（推奨）

```bash
cdk destroy
```

### AWS CLI の使用

```bash
aws cloudformation delete-stack \
  --stack-name MultiAgentDemo \
  --region us-east-1

# 削除完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name MultiAgentDemo \
  --region us-east-1
```

### AWS コンソールの使用

1. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
2. `MultiAgentDemo` スタックを選択
3. 「Delete」をクリック
4. 削除を確認

## コスト見積もり

### 月額コスト内訳（us-east-1）

| サービス | 使用量 | 月額コスト |
|---------|-------|--------------|
| **AgentCore ランタイム** | 2ランタイム、最小限の使用 | 約$10〜20 |
| **ECR リポジトリ** | 2リポジトリ、2GB未満のストレージ | 約$0.20 |
| **CodeBuild** | 時々のビルド | 約$2〜4 |
| **Lambda** | カスタムリソースの実行 | 約$0.01 |
| **CloudWatch Logs** | エージェントログ | 約$1.00 |
| **Bedrock モデル使用量** | トークン単位の従量課金 | 変動* |

**推定合計: 約$13〜25/月**（Bedrock モデル使用量を除く）

*Bedrock のコストは使用パターンと選択したモデルによって異なります。詳細は [Bedrock 料金](https://aws.amazon.com/bedrock/pricing/) を参照してください。

### コスト最適化のヒント

- **未使用時は削除**: `cdk destroy` を使用してすべてのリソースを削除
- **使用量の監視**: CloudWatch 請求アラームを設定
- **効率的なモデルの選択**: ユースケースに適した Bedrock モデルを選択

## トラブルシューティング

### CDK ブートストラップが必要

ブートストラップエラーが発生した場合：
```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

### 権限の問題

IAM ユーザー/ロールに以下があることを確認：
- `CDKToolkit` 権限または同等のもの
- スタック内のすべてのリソースを作成する権限
- サービスロール用の `iam:PassRole`

### Python 依存関係

プロジェクトディレクトリで依存関係をインストール：
```bash
pip install -r requirements.txt
```

### ビルドの失敗

AWS コンソールで CodeBuild ログを確認：
1. CodeBuild コンソールに移動
2. ビルドプロジェクトを見つける（名前に「agent1-build」と「agent2-build」が含まれる）
3. ビルド履歴とログを確認

### エージェント通信の問題

エージェント1がエージェント2を呼び出せない場合：
1. `bedrock-agentcore:InvokeAgentRuntime` の IAM 権限を確認
2. エージェント2のランタイムが実行中であることを確認
3. 両エージェントの CloudWatch ログを確認

## コントリビューション

コントリビューションを歓迎します！詳細は [コントリビューションガイド](../../CONTRIBUTING.md) を参照してください。

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は [LICENSE](../../LICENSE) ファイルを参照してください。
