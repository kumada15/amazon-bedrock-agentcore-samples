# Amazon Bedrock Agent と Bedrock AgentCore Gateway の統合

## 概要

このユースケースでは、**Amazon Bedrock Agents** と **Amazon Bedrock AgentCore Gateway** 間の完全なエンドツーエンド統合を、AWS Lambda と DynamoDB 上に構築された実用的なフルーツスタンドバックエンド API に接続するための **Model Context Protocol (MCP)** を使用して示します。このショーケースは、MCP が AI エージェントと既存のバックエンドシステム間のシームレスな通信を可能にし、複雑な統合作業なしにエージェントが実世界のツールとデータにアクセスできるようにする方法を説明しています。

**主要な統合フォーカス: Model Context Protocol (MCP)**
MCP は、AI エージェントが外部データソースやツールに安全に接続できるようにするオープンスタンダードです。このユースケースでは：
- **Bedrock Agent** は標準的なアクショングループ呼び出しを使用して Gateway と通信
- **AgentCore Gateway** はこれらの呼び出しを MCP 互換フォーマットに変換
- **バックエンド Lambda 関数** は自動的に MCP ツールとして公開
- **リアルタイムデータアクセス** は MCP の標準化されたプロトコルを通じて実現

### ユースケースの詳細
| 項目         | 詳細                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| ユースケースタイプ       | 会話型                                                                                                                      |
| エージェントタイプ          | 単一エージェント                                                                                                                        |
| ユースケースコンポーネント | ツール統合、MCP プロトコル、認証、リアルタイムデータアクセス、自然言語処理                                |
| ユースケース業種   | E コマース / リテール                                                                                                                 |
| サンプルの複雑さ  | 中級                                                                                                                        |
| 使用 SDK            | Amazon Bedrock AgentCore SDK、boto3                                                                                                |

### ユースケースアーキテクチャ

![Architecture Diagram](architecture.png)

```
User Query → Bedrock Agent → Bridge Lambda → AgentCore Gateway → Backend Lambda → DynamoDB
```

### ユースケースの主な機能

- **バックエンド変更ゼロ**: 既存の Lambda 関数は Gateway 統合でそのまま動作
- **自動ツール検出**: Gateway は Lambda 関数をエージェントツールとして自動的に公開
- **MCP プロトコル処理**: Gateway は Model Context Protocol 通信を透過的に管理
- **自然言語処理**: Bedrock Agent はユーザーリクエストを解釈し、適切なツールを選択
- **リアルタイムデータ統合**: エージェントの応答は DynamoDB からのライブデータを反映
- **シームレスな認証**: すべてのコンポーネント間の安全な通信

#### 主要コンポーネント:

1. **Amazon Bedrock Agent**: 基盤モデルの推論を使用してユーザーリクエストを理解し、ツール使用をオーケストレート
2. **Bridge Lambda**: Bedrock Agent アクショングループ呼び出しを MCP フォーマットに変換
3. **Amazon Bedrock AgentCore Gateway**: バックエンド API を MCP 互換ツールに自動変換
4. **Backend Lambda (Fruit Stand API)**: 在庫および注文管理のための既存ビジネスロジック
5. **DynamoDB テーブル**: フルーツスタンドビジネスのデータ永続化レイヤー
6. **Amazon Cognito**: 安全な Gateway アクセスのための OAuth2 認証を提供

#### Amazon Cognito による認証

**Cognito が必要な理由:**
Bedrock AgentCore Gateway は、バックエンド API を保護するために安全な認証を必要とします。Amazon Cognito は以下を提供します：

- **OAuth2 Client Credentials フロー**: 安全なマシン間認証
- **JWT トークン管理**: 自動トークン生成と検証
- **アクセス制御**: 認可されたエージェントのみがツールにアクセスできることを保証
- **スケーラブルな ID 管理**: カスタムコードなしで認証を処理

**動作の仕組み:**
1. Cognito User Pool が ID プロバイダーとして機能
2. クライアント認証情報（ID/シークレット）が Gateway 用に設定
3. Bridge Lambda が Cognito を使用して自動的に JWT トークンを生成
4. Gateway はツールアクセスを許可する前にトークンを検証
5. バックエンド API は認証された Gateway の背後で安全に保護

#### このデモが示すこと

**Amazon Bedrock Agents** は、基盤モデル（FM）、API、データの推論機能を使用して、ユーザーリクエストを分解し、関連情報を収集し、タスクを効率的に完了します。これにより、チームは高付加価値の作業に集中できます。

**Amazon Bedrock AgentCore Gateway** は、API、Lambda 関数、既存のサービスを MCP 互換ツールに自動変換するため、開発者は複雑な統合を管理することなく、これらの重要な機能をエージェントに迅速に利用可能にできます。

#### 解決される統合の課題

従来、AI エージェントを既存のバックエンドシステムに接続するには、複雑な API 統合、プロトコル変換、ツール管理、認証処理が必要でした。このユースケースは、Gateway がこれらの課題を以下のように解消する方法を示しています：

- **「利用可能なフルーツは何ですか？」** → エージェントが Gateway 経由で在庫ツールを呼び出し
- **「ボブの注文としてリンゴ 2 個を作成してください」** → エージェントが注文作成ツールを呼び出し
- **「注文 ABC123 の詳細を取得してください」** → エージェントが注文情報を取得

## 前提条件

* Python 3.9 以上
* 適切な権限を持つ AWS アカウント
* 認証情報で設定された AWS CLI 2.x
* Jupyter Notebook または JupyterLab
* AWS API 呼び出し用のインターネット接続
* 以下の AWS サービスへのアクセス:
  * Amazon Bedrock
  * AWS Lambda
  * Amazon DynamoDB
  * Amazon Cognito（Gateway 認証用）
  * AWS IAM
* 必要な AWS 権限: 管理者ロールからこのサンプルを実行する場合は無視してください
  * `bedrock:*` - Bedrock Agent 操作用
  * `lambda:*` - Lambda 関数管理用
  * `dynamodb:*` - DynamoDB テーブル操作用
  * `iam:*` - ロールとポリシー管理用
  * `cognito-idp:*` - OAuth2 認証セットアップ用

## ユースケースのセットアップ

必要なパッケージをインストールし、環境を設定します：

```bash
# プロジェクトディレクトリに移動
cd 06-BedrockAgent-Integration

# 仮想環境を作成
python -m venv .venv
.venv/bin/activate

# Bedrock AgentCore Gateway に必要なパッケージをインストール
pip install -r requirements.txt

# 残りのパッケージをインストール
pip install jupyter notebook requests urllib3

# AWS 認証情報を設定
aws configure
```

## 実行手順

Jupyter ノートブックを実行してユースケースを実行します：

```bash
# Jupyter Notebook を起動
jupyter notebook

# ノートブックファイルを開く
# Bedrock_Agent_Integration_with_Bedrock_AgentCore_Gateway.ipynb
```

ノートブックのセルを順番に実行します：

1. **ステップ 1-2**: 依存関係をインストールし、IAM ロールを作成
2. **ステップ 3**: 注文と在庫用の DynamoDB テーブルを作成
3. **ステップ 4**: Cognito 認証をセットアップ
4. **ステップ 5**: ターゲット Lambda 関数をデプロイ
5. **ステップ 6-7**: Bedrock AgentCore Gateway を作成および設定
6. **ステップ 8**: Gateway 統合をテスト
7. **ステップ 9-12**: Bedrock Agent を作成および設定
8. **ステップ 13**: エンドツーエンドテスト

デプロイ後、自然言語クエリを使用してインテリジェントエージェントと対話できます：

## 対話例

### クエリ 1: 利用可能な在庫を確認
**ユーザー入力:**
```
🤔 User: What fruits are available?
```

**エージェント応答:**
```
🤖 Enhanced Agent: Here are the available fruits and their current prices and stock levels:

- Strawberries: $3.99 per pound, 25 pounds in stock
- Oranges: $0.75 each, 80 in stock
- Bananas: $0.50 each, 148 in stock
- Apples: $1.20 each, 97 in stock
- Blueberries: $4.50 per pint, 30 pints in stock
```

### クエリ 2: 注文を作成
**ユーザー入力:**
```
🤔 User: Create an order for Bob with 2 apples
```

**エージェント応答:**
```
🤖 Enhanced Agent: The order for Bob with 2 apples has been successfully created. The order details are:

Order ID: e2c57daf
Customer Name: Bob
Items:
- 2 apples at $1.2 each, total $2.4
Total Cost: $2.4
Status: Pending
Created At: 2025-07-14T01:39:58.042975
```

### クエリ 3: 複数アイテムの複雑な注文
**ユーザー入力:**
```
🤔 User: I'd like to place an order for Alice with 3 apples and 2 bananas
```

**エージェント応答:**
```
🤖 Enhanced Agent: Perfect! I've created an order for Alice. Here are the details:

Order ID: f8a9b2c1
Customer Name: Alice
Items:
- 3 apples at $1.20 each, total $3.60
- 2 bananas at $0.50 each, total $1.00
Total Cost: $4.60
Status: Pending
Created At: 2025-07-14T02:15:33.891234

The inventory has been automatically updated to reflect the new stock levels.
```

### クエリ 4: 注文状況を確認
**ユーザー入力:**
```
🤔 User: Can you get the details for order e2c57daf?
```

**エージェント応答:**
```
🤖 Enhanced Agent: Here are the details for order e2c57daf:

Order ID: e2c57daf
Customer Name: Bob
Items:
- 2 apples at $1.20 each, total $2.40
Total Cost: $2.40
Status: Pending
Created At: 2025-07-14T01:39:58.042975
```

### これらの例が示すこと

1. **自然言語理解**: エージェントは同じ情報を求める様々な方法を解釈
2. **自動ツール選択**: エージェントは適切なバックエンド関数を選択（在庫一覧、注文作成、注文取得）
3. **リアルタイムデータ**: すべての応答は現在のデータベース状態を反映
4. **ビジネスロジック統合**: 注文時に在庫が自動的に更新
5. **構造化された応答**: エージェントはデータをユーザーフレンドリーな形式でフォーマット
6. **エラーハンドリング**: システムは無効なリクエストや在庫不足を適切に処理

## クリーンアップ手順

作成されたすべてのインフラストラクチャを削除し、継続的な課金を回避するには、ノートブックの最後にあるクリーンアップセクションを実行します：

```bash
# ノートブックのクリーンアップセルを実行して以下を削除:
# - Bedrock Agent とアクショングループ
# - Lambda 関数（Bridge と Target）
# - Gateway と Gateway ターゲット
# - DynamoDB テーブル
# - Cognito リソース
# - IAM ロールとポリシー
```

## トラブルシューティング

**よくある問題:**

1. **IAM 権限エラー**: AWS 認証情報に十分な権限があることを確認
2. **DynamoDB Decimal エラー**: ノートブックは Decimal 型変換を自動的に処理
3. **Gateway タイムアウト**: 操作に時間がかかる場合は Lambda タイムアウト設定を増加
4. **認証失敗**: Cognito 設定と認証情報を確認

## データベーススキーマリファレンス

**FruitInventory テーブル:**
- `fruit_name` (String, プライマリキー): フルーツの名前
- `price` (Number): 単位あたりの価格
- `unit` (String): 計量単位（each、pound、pint）
- `stock` (Number): 利用可能な数量

**FruitOrders テーブル:**
- `order_id` (String, プライマリキー): 一意の注文識別子
- `customer_name` (String): 顧客名
- `items` (List): 数量と価格を含む注文アイテム
- `total_cost` (Number): 注文合計金額
- `status` (String): 注文ステータス（pending、completed など）
- `created_at` (String): 注文作成の ISO タイムスタンプ

## 免責事項
このリポジトリで提供される例は、実験および教育目的のみです。コンセプトと技術を示していますが、本番環境での直接使用を目的としていません。[プロンプトインジェクション](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html)から保護するために、Amazon Bedrock Guardrails を導入してください。
