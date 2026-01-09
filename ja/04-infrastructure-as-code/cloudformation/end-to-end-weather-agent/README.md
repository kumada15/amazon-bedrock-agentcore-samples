# ツールとメモリを備えたエンドツーエンド天気エージェント

この CloudFormation テンプレートは、高度な天気ベースのアクティビティ計画エージェントを備えた完全な Amazon Bedrock AgentCore ランタイムをデプロイします。Browser ツール、Code Interpreter、Memory、および S3 ストレージを単一のデプロイに統合することで、AgentCore の全機能を実演します。

## 目次

- [概要](#概要)
- [アーキテクチャ](#アーキテクチャ)
- [前提条件](#前提条件)
- [デプロイ](#デプロイ)
- [テスト](#テスト)
- [サンプルクエリ](#サンプルクエリ)
- [動作の仕組み](#動作の仕組み)
- [クリーンアップ](#クリーンアップ)
- [コスト見積もり](#コスト見積もり)
- [トラブルシューティング](#トラブルシューティング)
- [コントリビューション](#コントリビューション)
- [ライセンス](#ライセンス)

## 概要

このテンプレートは、以下を紹介する包括的な AgentCore デプロイを作成します：

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

![エンドツーエンド天気エージェントアーキテクチャ](architecture.png)

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

3. **Bedrock モデルアクセス**: AWS リージョンで Amazon Bedrock モデルへのアクセスを有効化
   - [Amazon Bedrock コンソール](https://console.aws.amazon.com/bedrock/) に移動
   - [Bedrock モデルアクセスガイド](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. **必要な権限**: AWS ユーザー/ロールには以下の権限が必要：
   - CloudFormation スタック操作
   - ECR リポジトリ管理
   - IAM ロール作成
   - Lambda 関数作成
   - CodeBuild プロジェクト作成
   - BedrockAgentCore リソース作成（Runtime、Browser、CodeInterpreter、Memory）
   - S3 バケット作成

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
3. すべてのリソース ID を表示（Runtime、Browser、CodeInterpreter、Memory、S3 バケット）

### オプション2: AWS CLI の使用

```bash
# スタックのデプロイ
aws cloudformation create-stack \
  --stack-name weather-agent-demo \
  --template-body file://end-to-end-weather-agent.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2

# スタック作成を待機
aws cloudformation wait stack-create-complete \
  --stack-name weather-agent-demo \
  --region us-west-2

# すべての出力を取得
aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs'
```

### オプション3: AWS コンソールの使用

1. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
2. 「スタックの作成」→「新しいリソースを使用」をクリック
3. `end-to-end-weather-agent.yaml` ファイルをアップロード
4. スタック名を入力: `weather-agent-demo`
5. パラメータを確認（またはデフォルトを使用）
6. 「AWS CloudFormation によって IAM リソースが作成される場合があることを承認します」にチェック
7. 「スタックの作成」をクリック

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
# スタック出力からランタイム ID を取得して ARN を構築
RUNTIME_ID=$(aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeId`].OutputValue' \
  --output text)

# アカウント ID を取得して ARN を構築
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
RUNTIME_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:runtime/${RUNTIME_ID}"

# S3 バケット名を取得
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucket`].OutputValue' \
  --output text)

# ペイロードを準備（base64 エンコード、-n フラグに注意）
PAYLOAD=$(echo -n '{"prompt": "What should I do this weekend in Richmond VA?"}' | base64)

# エージェントを呼び出し
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $RUNTIME_ARN \
  --qualifier DEFAULT \
  --payload $PAYLOAD \
  --region us-west-2 \
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
3. ランタイムを見つける（名前は `weather_agent_demo_` で始まる）
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

### クリーンアップスクリプトの使用（推奨）

```bash
# スクリプトを実行可能にする
chmod +x cleanup.sh

# スタックの削除
./cleanup.sh
```

**注意**: アクティブなブラウザセッションが原因でクリーンアップに失敗した場合は、以下の AWS CLI クリーンアップ方法で手動でセッションを終了してください。

### AWS CLI の使用

```bash
# ステップ1: S3 バケットを空にする（削除前に必要）
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucket`].OutputValue' \
  --output text)

aws s3 rm s3://$BUCKET_NAME --recursive

# ステップ2: アクティブなブラウザセッションを終了
# Browser ID を取得
BROWSER_ID=$(aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`BrowserId`].OutputValue' \
  --output text)

# アクティブなセッションをリスト
aws bedrock-agentcore list-browser-sessions \
  --browser-id $BROWSER_ID \
  --region us-west-2

# 各アクティブセッションを終了（SESSION_ID を list コマンドの実際のセッション ID に置き換え）
# 各アクティブセッションに対してこのコマンドを繰り返す
aws bedrock-agentcore terminate-browser-session \
  --browser-id $BROWSER_ID \
  --session-id SESSION_ID \
  --region us-west-2

# ステップ3: スタックを削除
aws cloudformation delete-stack \
  --stack-name weather-agent-demo \
  --region us-west-2

# 削除完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name weather-agent-demo \
  --region us-west-2
```

**重要**: ブラウザセッションはエージェントがブラウザツールを使用すると自動的に作成されます。削除失敗を避けるため、スタック削除前に必ずアクティブセッションを終了してください。

### AWS コンソールの使用

1. [S3 コンソール](https://console.aws.amazon.com/s3/) に移動
2. バケットを見つける（名前形式: `<stack-name>-results-<account-id>`、例: `weather-agent-demo-results-123456789012`）
3. バケットを空にする
4. [Bedrock AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/) に移動
5. 左側のナビゲーションで「Browsers」に移動
6. ブラウザを見つける（名前は `weather_agent_demo_browser` で始まる）
7. ブラウザ名をクリック
8. 「Sessions」タブでアクティブなセッションを終了
9. [CloudFormation コンソール](https://console.aws.amazon.com/cloudformation/) に移動
10. `weather-agent-demo` スタックを選択
11. 「Delete」をクリック
12. 削除を確認
