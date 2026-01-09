# Basic AgentCore Runtime - CDK

この CDK スタックは、シンプルな Strands エージェントを使用した基本的な Amazon Bedrock AgentCore Runtime をデプロイします。これは最もシンプルな AgentCore デプロイであり、追加の複雑さなしにコアコンセプトを理解し始めるのに最適です。

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

この CDK スタックは、以下を含む最小限の AgentCore デプロイを作成します：

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

3. **Python 3.10+** と **AWS CDK v2** のインストール
   ```bash
   # CDK のインストール
   npm install -g aws-cdk

   # インストールの確認
   cdk --version
   ```

4. **CDK バージョン 2.220.0 以降** (BedrockAgentCore サポート用)

5. **Bedrock モデルアクセス**: AWS リージョンで Amazon Bedrock モデルへのアクセスを有効化
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

これは basic AgentCore runtime の **CDK バージョン** です。CloudFormation を好む場合は、[CloudFormation バージョン](../../cloudformation/basic-runtime/) をご覧ください。

### オプション 1: クイックデプロイ (推奨)

```bash
# 依存関係のインストール
pip install -r requirements.txt

# CDK のブートストラップ (初回のみ)
cdk bootstrap

# デプロイ
cdk deploy
```

### オプション 2: ステップバイステップ

```bash
# 1. Python 仮想環境を作成して有効化
python3 -m venv .venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate

# 2. Python 依存関係のインストール
pip install -r requirements.txt

# 3. アカウント/リージョンで CDK をブートストラップ (初回のみ)
cdk bootstrap

# 4. CloudFormation テンプレートを合成 (オプション)
cdk synth

# 5. スタックをデプロイ
cdk deploy --require-approval never

# 6. 出力を取得
cdk list
```

### デプロイ時間

- **予想所要時間**: 8-12 分
- **主なステップ**:
  - スタック作成: 約 2 分
  - Docker イメージビルド (CodeBuild): 約 5-8 分
  - ランタイムプロビジョニング: 約 1-2 分

## テスト

### AWS CLI を使用

```bash
# CDK 出力から Runtime ARN を取得
RUNTIME_ARN=$(aws cloudformation describe-stacks \
  --stack-name BasicAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeArn`].OutputValue' \
  --output text)

# エージェントを呼び出し
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $RUNTIME_ARN \
  --qualifier DEFAULT \
  --payload $(echo '{"prompt": "Hello, how are you?"}' | base64) \
  response.json

# レスポンスを表示
cat response.json
```

### AWS コンソールを使用

1. [Bedrock AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/) に移動
2. 左側のナビゲーションで「Runtimes」に移動
3. ランタイムを見つける (名前が `BasicAgentDemo_` で始まる)
4. ランタイム名をクリック
5. 「Test」ボタンをクリック
6. テストペイロードを入力:
   ```json
   {
     "prompt": "Hello, how are you?"
   }
   ```
7. 「Invoke」をクリック

## サンプルクエリ

basic エージェントをテストするために、以下のクエリを試してください：

1. **シンプルな挨拶**:
   ```json
   {"prompt": "Hello, how are you?"}
   ```

2. **質問応答**:
   ```json
   {"prompt": "What is the capital of France?"}
   ```

3. **クリエイティブライティング**:
   ```json
   {"prompt": "Write a short poem about clouds"}
   ```

4. **問題解決**:
   ```json
   {"prompt": "How do I bake a chocolate cake?"}
   ```

## クリーンアップ

### CDK を使用 (推奨)

```bash
cdk destroy
```

### AWS CLI を使用

```bash
aws cloudformation delete-stack \
  --stack-name BasicAgentDemo \
  --region us-east-1

# 削除完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name BasicAgentDemo \
  --region us-east-1
```

### AWS コンソールを使用

1. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
2. `BasicAgentDemo` スタックを選択
3. 「Delete」をクリック
4. 削除を確認

## コスト見積もり

### 月額コスト内訳 (us-east-1)

| サービス | 使用量 | 月額コスト |
|---------|--------|-----------|
| **AgentCore Runtime** | 1 ランタイム、最小使用量 | 約 $5-10 |
| **ECR リポジトリ** | 1 リポジトリ、<1GB ストレージ | 約 $0.10 |
| **CodeBuild** | 時折のビルド | 約 $1-2 |
| **Lambda** | カスタムリソースの実行 | 約 $0.01 |
| **CloudWatch Logs** | エージェントログ | 約 $0.50 |
| **Bedrock モデル使用量** | トークンごとの課金 | 変動* |

**推定合計: 約 $7-13/月** (Bedrock モデル使用量を除く)

*Bedrock のコストは使用パターンと選択したモデルによって異なります。詳細は [Bedrock 料金](https://aws.amazon.com/bedrock/pricing/) をご覧ください。

### コスト最適化のヒント

- **使用しないときは削除**: `cdk destroy` を使用してすべてのリソースを削除
- **使用量を監視**: CloudWatch 請求アラームを設定
- **効率的なモデルを選択**: ユースケースに適した Bedrock モデルを選択

## トラブルシューティング

### CDK ブートストラップが必要

ブートストラップエラーが表示された場合:
```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

### 権限の問題

IAM ユーザー/ロールに以下があることを確認:
- `CDKToolkit` 権限または同等のもの
- スタック内のすべてのリソースを作成する権限
- サービスロール用の `iam:PassRole`

### Python 依存関係

プロジェクトディレクトリで依存関係をインストール:
```bash
pip install -r requirements.txt
```

### ビルドの失敗

AWS コンソールで CodeBuild ログを確認:
1. CodeBuild コンソールに移動
2. ビルドプロジェクトを見つける (名前に "basic-agent-build" を含む)
3. ビルド履歴とログを確認

### ランタイムの問題

ランタイムが起動しない場合:
1. ランタイムの CloudWatch ログを確認
2. Docker イメージが正常にビルドされたことを確認
3. IAM 権限が正しいことを確認

## コントリビューション

コントリビューションを歓迎します！詳細は [Contributing Guide](../../CONTRIBUTING.md) をご覧ください。

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は [LICENSE](../../LICENSE) ファイルをご覧ください。
