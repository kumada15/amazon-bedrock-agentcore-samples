# AI を活用した DB パフォーマンスアナライザー

このプロジェクトは、Amazon Bedrock AgentCore を使用して AI を活用したデータベースパフォーマンスアナライザーを構築する方法を示しています。データベースのパフォーマンスを分析し、クエリを説明し、推奨事項を提供し、自然言語での会話を通じてデータベース操作の最適化を支援するインテリジェントエージェントを作成します。

## 概要

DB パフォーマンスアナライザーは、データベース管理者と開発者が PostgreSQL データベースのパフォーマンス問題を特定し解決するのを支援する AI を活用したアシスタントです。Amazon Bedrock AgentCore と大規模言語モデルを活用することで、データベースのメトリクスと統計に基づいた人間のような分析と推奨事項を提供します。

## ユースケース

- **パフォーマンスのトラブルシューティング**: 遅いクエリ、接続の問題、その他のパフォーマンスボトルネックを迅速に特定し診断
- **インデックスの最適化**: インデックスの使用状況を分析し、インデックスの作成、変更、削除に関する推奨事項を取得
- **リソース使用率**: CPU、メモリ、I/O 使用量を監視および最適化
- **メンテナンス計画**: 自動バキュームのパフォーマンスに関するインサイトとメンテナンスタスクの推奨事項を取得
- **レプリケーション監視**: レプリケーション遅延を追跡し、高可用性を確保
- **クエリの最適化**: 複雑なクエリの説明と改善提案を取得

## アーキテクチャ

![DB performance analyzer architecture](./images/db-analyzer-architecture.png)

### VPC 接続

Lambda 関数はデータベースと同じ VPC にデプロイされ、安全な通信を可能にします：

1. **自動 VPC 検出**: セットアップスクリプトがデータベースクラスターの VPC、サブネット、セキュリティグループを自動的に検出
2. **セキュリティグループの設定**: Lambda 関数用の専用セキュリティグループを作成し、データベースセキュリティグループにアクセスを許可するよう設定
3. **プライベートネットワーク通信**: すべてのデータベーストラフィックは VPC 内に留まり、パブリックインターネットを経由しない
4. **安全な認証情報管理**: データベース認証情報は AWS Secrets Manager に保存され、Lambda 関数から安全にアクセス
5. **VPC エンドポイント**: 正しい DNS 設定を持つ Secrets Manager や SSM などの AWS サービス用に適切に設定された VPC エンドポイント

## プロセスフロー

1. **ユーザークエリ**: ユーザーが Amazon Q を通じてデータベースパフォーマンスについて自然言語で質問
2. **クエリ処理**: Amazon Q がクエリを処理し、適切な AgentCore Gateway にルーティング
3. **ツール選択**: AgentCore Gateway がクエリに基づいて適切なツールを選択
4. **データ収集**: Lambda 関数がデータベースに接続し、関連するメトリクスと統計を収集
5. **分析**: Lambda 関数が収集したデータを分析し、インサイトを生成
6. **レスポンス生成**: 結果がフォーマットされ、自然言語の説明と推奨事項としてユーザーに返される

## プロジェクト構造

```
.
├── README.md               # このファイル
├── setup.sh                # メインセットアップスクリプト
├── setup_database.sh       # データベース設定スクリプト
├── cleanup.sh              # クリーンアップスクリプト
├── setup_observability.sh  # ゲートウェイとターゲットのオブザーバビリティをセットアップ
├── cleanup_observability.sh # オブザーバビリティリソースをクリーンアップ
├── config/                 # 設定ファイル（セットアップ中に生成）
│   └── *.env               # 環境固有の設定ファイル（Git にはコミットされない）
└── scripts/                # サポートスクリプト
    ├── create_gateway.py   # AgentCore Gateway を作成
    ├── create_iam_roles.sh # 必要な IAM ロールを作成
    ├── create_lambda.sh    # Lambda 関数を作成
    ├── create_target.py    # Gateway ターゲットを作成
    ├── lambda-target-analyze-db-performance.py # パフォーマンス分析ツール
    ├── lambda-target-analyze-db-slow-query.py  # スロークエリ分析ツール
    ├── get_token.py        # 認証トークンを取得/更新
    └── test_vpc_connectivity.py # AWS サービスへの接続をテスト
```

### 設定ファイル

セットアッププロセスは `config/` ディレクトリにいくつかの設定ファイルを自動生成します：

- **cognito_config.env**: Cognito ユーザープール、クライアント、トークン情報を含む
- **gateway_config.env**: Gateway ID、ARN、リージョンを含む
- **iam_config.env**: IAM ロール ARN とアカウント情報を含む
- **db_dev_config.env/db_prod_config.env**: データベース接続情報を含む（認証情報は AWS Secrets Manager に安全に保存）
- **vpc_config.env**: VPC、サブネット、セキュリティグループ ID を含む
- **target_config.env**: Gateway ターゲット設定を含む
- **pgstat_target_config.env**: pg_stat_statements ターゲットの設定を含む

これらのファイルには設定情報が含まれ、`.gitignore` で Git から除外されています。機密性の高い認証情報は AWS Secrets Manager と SSM Parameter Store に安全に保存され、これらの設定ファイルには含まれません。

## 前提条件

- 適切な権限で設定された AWS CLI
- Python 3.9 以上
- Boto3 ライブラリがインストールされていること
- jq コマンドラインツールがインストールされていること
- Amazon Aurora PostgreSQL または RDS PostgreSQL データベースへのアクセス
- AWS Secrets Manager でシークレットを作成する権限
- AWS Systems Manager Parameter Store でパラメータを作成する権限
- VPC セキュリティグループを作成および変更する権限
- VPC 設定を持つ Lambda 関数を作成する権限
- VPC エンドポイントを作成する権限（Lambda 関数が AWS サービスにアクセスする必要がある場合）

## セットアップ手順

1. リポジトリをクローン：
   ```bash
   git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
   cd amazon-bedrock-agentcore-samples/02-use-cases/02-DB-performance-analyzer
   ```

2. Python 仮想環境を作成：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. データベースアクセスをセットアップ：
   ```bash
   ./setup_database.sh --cluster-name your-aurora-cluster --environment prod
   ```

   このスクリプトは以下を実行します：
   - クラスターの既存のシークレットを検索
   - 見つかった場合、使用するシークレットを選択可能
   - 見つからない場合、ユーザー名とパスワードを入力するよう促す
   - RDS からクラスターエンドポイントとポートを取得
   - 必要な形式で AWS Secrets Manager にシークレットを作成
   - SSM Parameter Store にシークレット名を保存
   - 非機密性の設定をファイルに保存（認証情報は AWS サービスに安全に保管）

   既存のシークレットを直接指定することもできます：
   ```bash
   ./setup_database.sh --cluster-name your-aurora-cluster --environment prod --existing-secret your-secret-name
   ```

4. メインセットアップスクリプトを実行：
   ```bash
   ./setup.sh
   ```

   このスクリプトは以下を実行します：
   - 認証用の Amazon Cognito リソースをセットアップ
   - 必要な IAM ロールを作成
   - DB パフォーマンス分析用の Lambda 関数を作成
   - 必要に応じて AWS サービス用の VPC エンドポイントを設定
   - Amazon Bedrock AgentCore Gateway を作成
   - Lambda 関数用の Gateway ターゲットを作成
   - すべてが連携して動作するよう設定

5. ゲートウェイを使用するように Amazon Q を設定：
   ```bash
   source venv/bin/activate
   python3 scripts/get_token.py
   deactivate
   ```

   これにより、ゲートウェイ設定で `~/.aws/amazonq/mcp.json` ファイルが更新されます。

## DB パフォーマンスアナライザーの使用

セットアップが完了したら、Amazon Q を通じて DB パフォーマンスアナライザーを使用できます：

1. コマンドプロンプトで Amazon Q CLI を開く `q chat`
2. 「db-performance-analyzer」エージェントが読み込まれます
3. データベースパフォーマンスについて質問します。例：
   - "本番データベースのスロークエリを分析して"
   - "開発環境の接続管理の問題をチェックして"
   - "データベースのインデックス使用状況を分析して"
   - "本番環境の自動バキュームの問題をチェックして"

## 利用可能な分析ツール

DB パフォーマンスアナライザーはいくつかのツールを提供します：

- **スロークエリ分析**: 遅いクエリを特定して説明し、最適化のための推奨事項を提供
- **接続管理**: 接続の問題、アイドル接続、接続パターンを分析してリソース使用率を改善
- **インデックス分析**: インデックスの使用状況を評価し、不足または未使用のインデックスを特定し、改善を提案
- **自動バキューム分析**: 自動バキュームの設定を確認し、デッドタプルを監視し、設定変更を推奨
- **I/O 分析**: I/O パターン、バッファ使用量、チェックポイント活動を分析してボトルネックを特定
- **レプリケーション分析**: レプリケーションのステータス、遅延、健全性を監視して高可用性を確保
- **システムヘルス**: キャッシュヒット率、デッドロック、長時間実行トランザクションなど、全体的なシステムヘルスメトリクスを提供
- **クエリ説明**: クエリ実行プランを説明し、最適化の提案を提供
- **DDL 抽出**: データベースオブジェクトの Data Definition Language (DDL) ステートメントを抽出
- **クエリ実行**: クエリを安全に実行し、結果を返す

## 主なメリット

- **自然言語インターフェース**: 平易な日本語/英語の質問でデータベースと対話
- **プロアクティブな推奨事項**: パフォーマンス改善のための実用的な提案を取得
- **時間の節約**: 手動で診断するのに数時間かかる問題を迅速に特定
- **教育的**: AI の説明を通じてデータベースの内部構造とベストプラクティスを学習
- **アクセシブル**: 複雑な SQL クエリや監視コマンドを覚える必要がない
- **包括的**: 1 つのツールでデータベースパフォーマンスの複数の側面をカバー

## オブザーバビリティ

DB パフォーマンスアナライザーには、AgentCore Gateway と Lambda ターゲットの監視とトラブルシューティングに役立つオブザーバビリティ機能が含まれています。

### クイックセットアップ

1. オブザーバビリティセットアップスクリプトを実行：
   ```bash
   ./setup_observability.sh
   ```

2. CloudWatch コンソールで CloudWatch Transaction Search を有効化。

3. CloudWatch Logs、X-Ray Traces、Transaction Search でデータを表示。

### クリーンアップ

```bash
./cleanup_observability.sh
```

詳細なセットアップ手順、ランタイム外のエージェントの設定オプション、カスタムヘッダー、ベストプラクティスを含む AgentCore オブザーバビリティ機能の包括的なドキュメントについては、[AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) を参照してください。

## トラブルシューティング

### VPC 接続の問題

Lambda 関数が AWS サービスへの接続に問題がある場合：

1. **DNS 設定を確認**：
   - VPC で DNS 解決と DNS ホスト名が有効になっていることを確認
   - VPC エンドポイントでプライベート DNS が有効になっていることを確認

2. **環境変数を確認**：
   - Lambda 関数に `AWS_REGION` 環境変数が正しく設定されている必要がある
   - Secrets Manager などのサービスでは、コードでリージョンが指定されていることを確認

3. **接続をテスト**：
   ```bash
   python3 scripts/test_vpc_connectivity.py
   ```

4. **セキュリティグループを確認**：
   - Lambda セキュリティグループが VPC エンドポイントセキュリティグループへのアウトバウンドトラフィックを許可していることを確認
   - VPC エンドポイントセキュリティグループが Lambda セキュリティグループからのインバウンドトラフィックを許可していることを確認

5. **ルートテーブルを確認**：
   - Lambda 関数が実行されるサブネットに適切なルートを持つルートテーブルがあることを確認

6. **手動確認コマンド**：
   ```bash
   # DNS 設定を確認
   aws ec2 describe-vpc-attribute --vpc-id YOUR_VPC_ID --attribute enableDnsSupport
   aws ec2 describe-vpc-attribute --vpc-id YOUR_VPC_ID --attribute enableDnsHostnames

   # VPC エンドポイントを一覧表示
   aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=YOUR_VPC_ID"

   # サブネットのルートテーブルを確認
   aws ec2 describe-route-tables --filters "Name=association.subnet-id,Values=YOUR_SUBNET_ID"
   ```

### Lambda 関数の問題

Lambda 関数が環境変数の欠落に関連するエラーで失敗する場合：

1. **必要な環境変数を確認**：
   - Lambda 設定ですべての必要な環境変数が設定されていることを確認
   - `REGION` 環境変数は AWS サービスアクセスにとって特に重要

2. **Lambda 設定を更新**：
   ```bash
   aws lambda update-function-configuration \
     --function-name DBPerformanceAnalyzer \
     --environment "Variables={REGION=us-west-2}" \
     --region us-west-2
   ```

3. **エラーの説明**：
   `Error: Failed to extract database object DDL: 'REGION'` や `cannot access local variable 'conn'` などのエラーが表示される場合は、環境変数の欠落が原因である可能性があります。

4. **代替ソリューション**：
   Lambda 関数コードを更新して、環境変数の欠落を適切なデフォルトで処理することもできます：
   ```python
   region = os.getenv('REGION', os.getenv('AWS_REGION', 'us-west-2'))
   ```

### シークレット管理の問題

データベースシークレットに問題がある場合：

1. **シークレットの形式を確認**：
   - シークレットには `username`、`password`、`host`、`port`、`dbname` フィールドが含まれている必要がある
   - setup_database.sh スクリプトはシークレット名の特殊文字を処理するようになった

2. **シークレットアクセスを確認**：
   - Lambda 実行ロールにシークレットへのアクセス権限があることを確認
   - シークレットが Lambda 関数と同じリージョンにあることを確認

3. **シークレットアクセスをテスト**：
   ```bash
   ./scripts/list_secrets.sh --filter your-cluster-name
   ```

### オブザーバビリティのトラブルシューティング

オブザーバビリティデータが表示されない場合：

1. **CloudWatch Transaction Search を確認**: CloudWatch コンソールで有効になっていることを確認
2. **ロググループを確認**: ゲートウェイとターゲットのロググループが存在することを確認
3. **トラフィックを生成**: ゲートウェイにいくつかのリクエストを送信してトレースとログを生成

## クリーンアップ

このプロジェクトで作成されたすべてのリソースを削除するには：

```bash
./cleanup.sh
```

これにより以下が削除されます：
- Lambda 関数
- Gateway ターゲット
- Gateway
- Cognito リソース
- IAM ロール
- VPC エンドポイント（作成された場合）
- 設定ファイル

注意：スクリプトはデフォルトでは AWS Secrets Manager のシークレットや SSM Parameter Store のパラメータを削除しません。これらのリソースも削除するには、以下を使用します：

```bash
./cleanup.sh --delete-secrets
```

## 認証の更新

認証トークンが期限切れになった場合は、以下を実行：

```bash
source venv/bin/activate
python3 scripts/get_token.py
deactivate
```

## クエリ例

以下は、DB パフォーマンスアナライザーに対して行える質問の例です：

- "本番データベースで最も遅い上位 5 つのクエリは何ですか？"
- "開発環境に接続管理の問題はありますか？"
- "データベースのインデックス使用状況を分析して改善点を提案してください"
- "本番データベースで自動バキュームは効果的に動作していますか？"
- "今データベースで I/O が高い原因は何ですか？"
- "データベースにレプリケーション遅延がないか確認してください"
- "本番データベースの全体的なヘルスチェックを実行してください"
- "このクエリの実行プランを説明してください: SELECT * FROM users WHERE email LIKE '%example.com'"
- "データベースの users テーブルの DDL を抽出してください"


## コントリビューション

コントリビューションを歓迎します！お気軽にプルリクエストを送信してください。
