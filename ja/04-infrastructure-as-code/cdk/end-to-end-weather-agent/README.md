# ツールとメモリを備えたエンドツーエンド天気エージェント - CDK

この CDK スタックは、高度な天気ベースのアクティビティ計画エージェントを備えた完全な Amazon Bedrock AgentCore ランタイムをデプロイします。Browser ツール、Code Interpreter、Memory、および S3 ストレージを単一のデプロイに統合することで、AgentCore の全機能を実演します。

## 目次

- [概要](#概要)
- [アーキテクチャ](#アーキテクチャ)
- [前提条件](#前提条件)
- [デプロイ](#デプロイ)
- [テスト](#テスト)
- [サンプルクエリ](#サンプルクエリ)
- [動作の仕組み](#動作の仕組み)
- [クリーンアップ](#クリーンアップ)
- [トラブルシューティング](#トラブルシューティング)

## 概要

この CDK スタックは、以下を紹介する包括的な AgentCore デプロイを作成します：

### コアコンポーネント

- **AgentCore ランタイム**: 複数のツールを持つ Strands エージェントをホスト
- **Browser ツール**: weather.gov から天気データをスクレイピングするための Web オートメーション
- **Code Interpreter**: 天気分析のための Python コード実行
- **Memory**: ユーザーのアクティビティ設定を保存
- **S3 バケット**: 生成されたアクティビティ推奨を保存
- **ECR リポジトリ**: コンテナイメージストレージ
- **IAM ロール**: すべてのコンポーネントのための包括的な権限

### エージェントの機能

天気アクティビティプランナーエージェントは以下を実行できます：

1. **天気データのスクレイピング**: ブラウザオートメーションを使用して weather.gov から8日間の予報を取得
2. **天気の分析**: Python コードを生成・実行して日を GOOD/OK/POOR に分類
3. **設定の取得**: メモリからユーザーのアクティビティ設定にアクセス
4. **推奨の生成**: 天気と設定に基づいてパーソナライズされたアクティビティ提案を作成
5. **結果の保存**: S3 に推奨を Markdown ファイルとして保存

### ユースケース

- 天気ベースのアクティビティ計画
- 自動化された Web スクレイピングとデータ分析
- マルチツールエージェントオーケストレーション
- メモリ駆動のパーソナライゼーション
- 非同期タスク処理

## アーキテクチャ

このアーキテクチャは、複数の統合ツールを備えた完全な AgentCore デプロイを実演します：

**コアコンポーネント:**
- **ユーザー**: 天気ベースのアクティビティ計画クエリを送信
- **AWS CodeBuild**: エージェントコードを含む ARM64 Docker コンテナイメージをビルド
- **Amazon ECR リポジトリ**: コンテナイメージを保存
- **AgentCore ランタイム**: 天気アクティビティプランナーエージェントをホスト
  - **天気エージェント**: 複数のツールをオーケストレーションする Strands エージェント
  - 推論とコード生成のために Amazon Bedrock LLM を呼び出し
- **Browser ツール**: weather.gov から天気データをスクレイピングするための Web オートメーション
- **Code Interpreter ツール**: 天気分析のための Python コードを実行
- **Memory**: ユーザーのアクティビティ設定を保存（30日間保持）
- **S3 バケット**: 生成されたアクティビティ推奨を保存
- **IAM ロール**: すべてのコンポーネントのための包括的な権限

**ワークフロー:**
1. ユーザーがクエリを送信: "What should I do this weekend in Richmond VA?"
2. エージェントが都市を抽出し、Browser ツールを使用して8日間の予報をスクレイピング
3. エージェントが Python コードを生成し、Code Interpreter を使用して天気を分類
4. エージェントが Memory からユーザー設定を取得
5. エージェントがパーソナライズされた推奨を生成
6. エージェントが use_aws ツールを使用して結果を S3 バケットに保存

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

4. **CDK バージョン 2.218.0 以降**（BedrockAgentCore サポートのため）

5. **Bedrock モデルアクセス**: AWS リージョンで Amazon Bedrock モデルへのアクセスを有効化
   - [Bedrock モデルアクセスガイド](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

6. **必要な権限**: AWS ユーザー/ロールには以下の権限が必要：
   - CloudFormation スタック操作
   - ECR リポジトリ管理
   - IAM ロール作成
   - Lambda 関数作成
   - CodeBuild プロジェクト作成
   - BedrockAgentCore リソース作成（Runtime、Browser、CodeInterpreter、Memory）
   - S3 バケット操作（CDK アセットと結果保存用）

## デプロイ

### CDK と CloudFormation の比較

これはエンドツーエンド天気エージェントの **CDK バージョン** です。CloudFormation を使用する場合は、[CloudFormation バージョン](../../cloudformation/end-to-end-weather-agent/) を参照してください。

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
  - ランタイムとツールのプロビジョニング: 約3〜5分
  - メモリの初期化: 約1分

## テスト

### AWS CLI の使用

```bash
# CDK 出力からランタイム ARN を取得
RUNTIME_ARN=$(aws cloudformation describe-stacks \
  --stack-name WeatherAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeArn`].OutputValue' \
  --output text)

# S3 バケット名を取得
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name WeatherAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucketName`].OutputValue' \
  --output text)

# エージェントを呼び出し
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $RUNTIME_ARN \
  --qualifier DEFAULT \
  --payload $(echo '{"prompt": "What should I do this weekend in Richmond VA?"}' | base64) \
  response.json

# 即時レスポンスを表示
cat response.json

# 処理のために数分待ってから、S3 で結果を確認
aws s3 ls s3://$BUCKET_NAME/

# 結果をダウンロード
aws s3 cp s3://$BUCKET_NAME/results.md ./results.md
cat results.md
```

### AWS コンソールの使用

1. [Bedrock AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/) に移動
2. 左側のナビゲーションで「Runtimes」に移動
3. ランタイムを見つける（名前は `WeatherAgentDemo_` で始まる）
4. ランタイム名をクリック
5. 「Test」ボタンをクリック
6. テストペイロードを入力：
   ```json
   {
     "prompt": "What should I do this weekend in Richmond VA?"
   }
   ```
7. 「Invoke」をクリック
8. 即時レスポンスを表示
9. バックグラウンド処理のために2〜3分待つ
10. [S3 コンソール](https://console.aws.amazon.com/s3/) に移動して結果バケットから results.md をダウンロード

## サンプルクエリ

天気エージェントをテストするためにこれらのクエリを試してください：

1. **週末の計画**:
   ```json
   {"prompt": "What should I do this weekend in Richmond VA?"}
   ```

2. **特定の都市**:
   ```json
   {"prompt": "Plan activities for next week in San Francisco"}
   ```

3. **別の場所**:
   ```json
   {"prompt": "What outdoor activities can I do in Seattle this week?"}
   ```

4. **旅行の計画**:
   ```json
   {"prompt": "I'm visiting Austin next week. What should I plan based on the weather?"}
   ```

## 動作の仕組み

### ステップバイステップのワークフロー

1. **ユーザークエリ**: "What should I do this weekend in Richmond VA?"

2. **都市の抽出**: エージェントがクエリから "Richmond VA" を抽出

3. **天気のスクレイピング**（Browser ツール）:
   - weather.gov に移動
   - Richmond VA を検索
   - 「Printable Forecast」をクリック
   - 8日間の予報データを抽出（日付、最高気温、最低気温、天候、風、降水確率）
   - 天気データの JSON 配列を返す

4. **コード生成**（LLM）:
   - エージェントが天気の日を分類する Python コードを生成
   - 分類ルール：
     - GOOD: 65〜80°F、晴れ、雨なし
     - OK: 55〜85°F、曇り時々晴れ、小雨
     - POOR: 55°F 未満または 85°F 超、曇り/雨

5. **コード実行**（Code Interpreter）:
   - 生成された Python コードを実行
   - タプルのリストを返す: `[('2025-09-16', 'GOOD'), ('2025-09-17', 'OK'), ...]`

6. **設定の取得**（Memory）:
   - メモリからユーザーのアクティビティ設定を取得
   - 天気タイプ別に保存された設定：
     ```json
     {
       "good_weather": ["hiking", "beach volleyball", "outdoor picnic"],
       "ok_weather": ["walking tours", "outdoor dining", "park visits"],
       "poor_weather": ["indoor museums", "shopping", "restaurants"]
     }
     ```

7. **推奨の生成**（LLM）:
   - 天気分析とユーザー設定を組み合わせる
   - 日ごとのアクティビティ推奨を作成
   - Markdown ドキュメントとしてフォーマット

8. **保存**（use_aws ツールを介した S3）:
   - S3 バケットに推奨を `results.md` として保存
   - ユーザーは推奨をダウンロードして確認可能

### 非同期処理

エージェントは長時間実行タスクを処理するために非同期で実行されます：
- 即時レスポンス: "Processing started..."
- バックグラウンド処理: すべてのステップを完了
- 約2〜3分後に S3 で結果が利用可能

## クリーンアップ

### CDK の使用（推奨）

```bash
cdk destroy
```

### AWS CLI の使用

```bash
# ステップ1: S3 バケットを空にする（削除前に必要）
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name WeatherAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucketName`].OutputValue' \
  --output text)

aws s3 rm s3://$BUCKET_NAME --recursive

# ステップ2: アクティブなブラウザセッションを終了
# Browser ID を取得
BROWSER_ID=$(aws cloudformation describe-stacks \
  --stack-name WeatherAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`BrowserId`].OutputValue' \
  --output text)

# アクティブなセッションをリスト
aws bedrock-agentcore list-browser-sessions \
  --browser-id $BROWSER_ID \
  --region us-east-1

# 各アクティブセッションを終了（SESSION_ID を list コマンドの実際のセッション ID に置き換え）
# 各アクティブセッションに対してこのコマンドを繰り返す
aws bedrock-agentcore terminate-browser-session \
  --browser-id $BROWSER_ID \
  --session-id SESSION_ID \
  --region us-east-1

# ステップ3: スタックを削除
aws cloudformation delete-stack \
  --stack-name WeatherAgentDemo \
  --region us-east-1

# 削除完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name WeatherAgentDemo \
  --region us-east-1
```

**重要**: ブラウザセッションはエージェントがブラウザツールを使用すると自動的に作成されます。削除失敗を避けるため、スタック削除前に必ずアクティブセッションを終了してください。

### AWS コンソールの使用

1. [S3 コンソール](https://console.aws.amazon.com/s3/) に移動
2. バケットを見つける（名前形式: `<stack-name>-results-<account-id>`）
3. バケットを空にする
4. [Bedrock AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/) に移動
5. 左側のナビゲーションで「Browsers」に移動
6. ブラウザを見つける（名前は `WeatherAgentDemo_browser` で始まる）
7. ブラウザ名をクリック
8. 「Sessions」タブでアクティブなセッションを終了
9. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
10. `WeatherAgentDemo` スタックを選択
11. 「Delete」をクリック
12. 削除を確認

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
2. ビルドプロジェクトを見つける（名前に「weather-agent-build」が含まれる）
3. ビルド履歴とログを確認

### ブラウザセッションの問題

ブラウザセッションが原因でデプロイが失敗した場合：
1. AWS CLI を使用してアクティブセッションをリスト
2. すべてのアクティブセッションを終了
3. デプロイまたはクリーンアップを再試行

### メモリ初期化の問題

メモリ初期化が失敗した場合：
1. CloudWatch で Lambda 関数ログを確認
2. メモリアクセスの IAM 権限を確認
3. デプロイを再試行
