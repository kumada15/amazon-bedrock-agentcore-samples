# Market Trends Agent

## 概要

このユースケースは、Amazon Bedrock AgentCore を使用して、リアルタイムの市場インテリジェンス、株式分析、パーソナライズされた投資推奨を提供するインテリジェントな金融分析エージェントを実装しています。このエージェントは、LLM を活用した分析とライブ市場データを組み合わせ、セッション間でブローカーの好みを永続的なメモリとして保持します。

## ユースケースアーキテクチャ

![Market Trends Agent Architecture](images/market-trends-agent-architecture.png)

| 情報 | 詳細 |
|-------------|---------|
| ユースケースタイプ | 対話型 |
| エージェントタイプ | Graph |
| ユースケースコンポーネント | Memory、Tools、Browser Automation |
| ユースケース業界 | 金融サービス |
| 複雑度 | 上級 |
| 使用 SDK | Amazon Bedrock AgentCore SDK、LangGraph、Playwright |

## 機能

### 高度なメモリ管理
- **マルチ戦略メモリ**: USER_PREFERENCE と SEMANTIC の両方のメモリ戦略を使用
- **ブローカープロファイル**: 各ブローカー/クライアントの永続的な金融プロファイルを維持
- **LLM ベースのアイデンティティ**: セッション間でブローカーのアイデンティティをインテリジェントに抽出・照合
- **投資プリファレンス**: リスク許容度、投資スタイル、セクター嗜好を保存

### リアルタイム市場インテリジェンス
- **対話型ブローカープロファイル**: ユーザーがチャットを通じて構造化されたブローカー情報を提供 - **テスト済み・準備完了**
- **自動プロファイル解析**: 構造化入力からブローカーの嗜好をインテリジェントに抽出・保存
- **パーソナライズされたマーケットブリーフィング**: 保存されたブローカープロファイルに基づいた分析
- **マルチソースニュース**: Bloomberg、Reuters、WSJ、Financial Times、CNBC をサポート
- **ライブ株式データ**: 現在の価格、変動、市場パフォーマンス指標
- **プロフェッショナル基準**: ブローカーのリスク許容度と投資スタイルに沿った機関投資家レベルの分析を提供

### ブラウザ自動化
- **Web スクレイピング**: 金融ウェブサイトからの自動データ収集
- **動的コンテンツ**: JavaScript でレンダリングされたページやインタラクティブ要素を処理
- **レート制限**: 信頼性の高いデータ収集のための組み込み遅延とリトライロジック



Market Trends Agent は、Amazon Bedrock AgentCore の包括的な機能を活用してパーソナライズされた金融インテリジェンスを提供します：

- **AgentCore Runtime**: LangGraph ベースのエージェント用サーバーレス実行環境
- **AgentCore Memory**: ブローカーの嗜好と金融インサイトを保存するマルチ戦略メモリシステム
- **AgentCore Browser Tool**: 金融ウェブサイトからリアルタイム市場データを取得するためのセキュアな Web スクレイピング
- **Claude Sonnet 4**: 金融分析とブローカー対話のための高度な LLM
- **マルチソース統合**: Bloomberg、Reuters、WSJ などからのリアルタイムデータ

## クイックスタート

### 前提条件
- Python 3.10+
- 適切な認証情報で設定された AWS CLI
- Docker または Podman がインストールされ実行中
- Amazon Bedrock AgentCore へのアクセス

### インストールとデプロイ

1. **uv のインストール**（未インストールの場合）
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# または pip 経由
pip install uv
```

2. **依存関係のインストール**
```bash
uv sync
```

3. **エージェントのデプロイ**（ワンコマンド！）
```bash
# シンプルなデプロイ
uv run python deploy.py

# カスタム設定（オプション）
uv run python deploy.py \
  --agent-name "my-market-agent" \
  --region "us-west-2" \
  --role-name "MyCustomRole"
```

**利用可能なオプション：**
- `--agent-name`: エージェント名（デフォルト: market_trends_agent）
- `--role-name`: IAM ロール名（デフォルト: MarketTrendsAgentRole）
- `--region`: AWS リージョン（デフォルト: us-east-1）
- `--skip-checks`: 前提条件の検証をスキップ

4. **エージェントのテスト**
```bash
uv run python test_agent.py
```

## 使用例

### ブローカープロファイル設定（初回対話）
以下の構造化フォーマットでブローカー情報を送信します：

```
Name: Yuval Bing
Company: HSBC
Role: Investment Advisor
Preferred News Feed: BBC
Industry Interests: oil, emerging markets
Investment Strategy: dividend
Risk Tolerance: low
Client Demographics: younger professionals, tech workers
Geographic Focus: North America, Asia-Pacific
Recent Interests: middle east geopolitics
```

エージェントは自動的に以下を行います：
- プロファイルを解析してメモリに保存
- パーソナライズされた確認を提供
- 今後のすべての応答を特定の嗜好に合わせて調整

### パーソナライズされた市場分析
プロファイル設定後、市場インサイトを要求します：

```
"今日のバイオテック株はどうなっていますか？"
"テック志向のクライアント向けに AI セクターの分析をお願いします"
"ヨーロッパの最新の ESG 投資トレンドは何ですか？"
```

エージェントは以下に特化した分析を提供します：
- あなたの業界関心事項
- あなたのリスク許容度
- あなたのクライアント属性
- あなたの好みのニュースソース

### ブローカーカード機能のテスト
```bash
uv run python test_broker_card.py
```

これは完全なワークフローを示します：
1. 構造化ブローカープロファイルの送信
2. エージェントによる嗜好の解析と保存
3. パーソナライズされた市場分析の受信

### インタラクティブな会話の継続
テスト後、エージェントとのチャットを継続できます：

**即時チャット用のワンライナー：**
```bash
uv run python -c "
import boto3, json
client = boto3.client('bedrock-agentcore', region_name='us-east-1')
with open('.agent_arn', 'r') as f: arn = f.read().strip()
print('💬 Market Trends Agent Chat (type \"quit\" to exit)')
while True:
    try:
        msg = input('\n🤖 You: ')
        if msg.lower() in ['quit', 'exit']: break
        resp = client.invoke_agent_runtime(agentRuntimeArn=arn, payload=json.dumps({'prompt': msg}))
        print('📈 Agent:', resp['response'].read().decode('utf-8'))
    except KeyboardInterrupt: break
"
```

## アーキテクチャ

### ユースケースアーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                    Market Trends Agent                          │
├─────────────────────────────────────────────────────────────────┤
│  LangGraph Agent Framework                                      │
│  ├── Claude Sonnet 4 (LLM)                                     │
│  ├── Browser Automation Tools                                   │
│  └── Memory Management Tools                                    │
├─────────────────────────────────────────────────────────────────┤
│  AgentCore Multi-Strategy Memory                                │
│  ├── USER_PREFERENCE: Broker profiles & preferences            │
│  └── SEMANTIC: Financial facts & market insights               │
├─────────────────────────────────────────────────────────────────┤
│  External Data Sources                                          │
│  ├── Real-time Stock Data (Google Finance, Yahoo Finance)      │
│  ├── Financial News (Bloomberg)                                 │
│  └── Market Analysis APIs                                       │
└─────────────────────────────────────────────────────────────────┘
```

### メモリ戦略
- **USER_PREFERENCE**: ブローカーの嗜好、リスク許容度、投資スタイルをキャプチャ
- **SEMANTIC**: 金融ファクト、市場分析、投資インサイトを保存

### 利用可能なツール

**市場データとニュース** (`tools/browser_tool.py`):
- `get_stock_data(symbol)`: リアルタイムの株価と市場データ
- `search_news(query, news_source)`: マルチソースニュース検索（Bloomberg、Reuters、CNBC、WSJ、Financial Times、Dow Jones）

**ブローカープロファイル管理** (`tools/broker_card_tools.py`):
- `parse_broker_profile_from_message()`: 構造化ブローカーカードの解析
- `generate_market_summary_for_broker()`: カスタマイズされた市場分析
- `get_broker_card_template()`: ブローカーカードフォーマットテンプレートの提供
- `collect_broker_preferences_interactively()`: 嗜好収集のガイド

**メモリとアイデンティティ管理** (`tools/memory_tools.py`):
- `identify_broker(message)`: LLM ベースのブローカーアイデンティティ抽出
- `get_broker_financial_profile()`: 保存された金融プロファイルの取得
- `update_broker_financial_interests()`: 新しい嗜好と関心事項の保存
- `list_conversation_history()`: 最近の会話履歴の取得

## モニタリング

### CloudWatch Logs
デプロイ後、エージェントを監視できます：
```bash
# ログの表示（エージェント ID を置き換えてください）
aws logs tail /aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT --follow
```

### ヘルスチェック
- 組み込みのヘルスチェックエンドポイント
- エージェントの可用性と応答時間を監視

## クリーンアップ

### 完全なリソースクリーンアップ
エージェントの使用が完了したら、クリーンアップスクリプトを使用してすべての AWS リソースを削除します：

```bash
# 完全なクリーンアップ（すべてを削除）
uv run python cleanup.py

# 削除される内容のプレビュー（ドライラン）
uv run python cleanup.py --dry-run

# IAM ロールを保持（他のプロジェクトと共有している場合に便利）
uv run python cleanup.py --skip-iam

# 別のリージョンでのクリーンアップ
uv run python cleanup.py --region us-west-2
```

**クリーンアップされる内容：**
- AgentCore Runtime インスタンス
- AgentCore Memory インスタンス
- ECR リポジトリとコンテナイメージ
- CodeBuild プロジェクト
- S3 ビルドアーティファクト
- SSM パラメータ
- IAM ロールとポリシー（`--skip-iam` を指定しない限り）
- ローカルデプロイファイル

### 手動クリーンアップ（必要な場合）
自動クリーンアップが失敗した場合は、手動でリソースを削除できます：

1. **AgentCore Runtime**: AWS コンソール → Bedrock → AgentCore → Runtimes
2. **AgentCore Memory**: AWS コンソール → Bedrock → AgentCore → Memory
3. **ECR Repository**: AWS コンソール → ECR → Repositories
4. **IAM Roles**: AWS コンソール → IAM → Roles（"MarketTrendsAgent" で検索）
5. **CodeBuild**: AWS コンソール → CodeBuild → Build projects

## トラブルシューティング

### よくある問題

1. **スロットリングエラー**
   - リクエスト間に数分待機してください
   - アカウントのレート制限が低い可能性があります
   - 詳細は CloudWatch ログを確認してください

2. **コンテナビルドの失敗**
   - Docker/Podman が実行中であることを確認してください
   - ネットワーク接続を確認してください
   - 必要なファイルがすべて存在することを確認してください

3. **権限エラー**
   - デプロイスクリプトは必要なすべての IAM 権限を作成します
   - AWS 認証情報が正しく設定されていることを確認してください

4. **メモリインスタンスの重複**
   - エージェントは競合状態を防ぐために SSM Parameter Store を使用します
   - 複数のメモリインスタンスが表示される場合は、次を実行してください: `uv run python cleanup.py`
   - その後、再デプロイしてください: `uv run python deploy.py`

### デバッグ情報
デプロイスクリプトには包括的なエラーレポートが含まれており、問題が発生した場合にガイダンスを提供します。

## セキュリティ

### IAM 権限
デプロイスクリプトは以下の権限を持つロールを自動的に作成します：
- `bedrock:InvokeModel`（Claude Sonnet 用）
- `bedrock-agentcore:*`（メモリおよびランタイム操作用）
- `ecr:*`（コンテナレジストリアクセス用）
- `xray:*`（トレーシング用）
- `logs:*`（CloudWatch ロギング用）

### データプライバシー
- 金融プロファイルは Bedrock AgentCore Memory に安全に保存されます
- 機密データはログに記録されたり公開されたりしません
- すべての通信は転送中に暗号化されます

## コントリビューション

1. リポジトリをフォーク
2. フィーチャーブランチを作成
3. 変更を加える
4. 新機能のテストを追加
5. プルリクエストを提出

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は LICENSE ファイルを参照してください。
