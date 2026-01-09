# AgentCore Policy - はじめにデモ

Amazon Bedrock AgentCore Policy を使用した AI エージェントのポリシーベース制御を実装する完全なハンズオンデモです。

## 🚀 クイックスタート

1. **依存関係のインストール**: `pip install -r requirements.txt`
2. **ノートブックを開く**: `jupyter notebook AgentCore-Policy-Demo.ipynb`
3. **ノートブックの手順に従う**

> **注意**: ネイティブ policy-registry API サポートには boto3 バージョン 1.42.0 以上が必要です。

## 概要

このデモでは、AgentCore Gateway を通じた AI エージェントとツールの対話に対するポリシーベース制御の実装を完全にウォークスルーします。

## 学習内容

- ✅ Lambda 関数をエージェントツールとしてデプロイ
- ✅ 複数の Lambda ターゲットを持つ AgentCore Gateway のセットアップ
- ✅ Policy Engine の作成と設定
- ✅ きめ細かなアクセス制御のための Cedar ポリシーの作成
- ✅ 実際の AI エージェントリクエストでポリシー適用をテスト
- ✅ ALLOW と DENY シナリオの理解

## デモシナリオ

ポリシー制御を備えた**保険引受処理システム**を構築します：

- **ツール**:
  - **ApplicationTool** - 地理的および適格性検証を備えた保険申請を作成
    - パラメータ: `applicant_region`（文字列）、`coverage_amount`（整数）
  - **RiskModelTool** - ガバナンス制御を備えた外部リスクスコアリングモデルを呼び出し
    - パラメータ: `API_classification`（文字列）、`data_governance_approval`（ブール値）
  - **ApprovalTool** - 高額または高リスクの引受決定を承認
    - パラメータ: `claim_amount`（整数）、`risk_level`（文字列）

- **ポリシールール**: 100万ドル未満の補償額の保険申請のみを許可
- **テストケース**:
  - ✅ 75万ドルの申請（許可）
  - ❌ 150万ドルの申請（拒否）

> **重要**: ポリシーは Gateway ターゲットスキーマで定義されたパラメータのみを参照できます。各ツールには、ポリシー条件で使用できる特定のパラメータを持つ独自のスキーマがあります。

## 前提条件

開始前に、以下を確認してください：

- 適切な認証情報で設定された AWS CLI
- boto3 1.42.0+ がインストールされた Python 3.10+
- `bedrock_agentcore_starter_toolkit` パッケージがインストール済み
- `strands` パッケージがインストール済み（AI エージェント機能用）
- AWS Lambda へのアクセス（ターゲット関数の作成用）
- Amazon Bedrock へのアクセス（AI エージェントモデル用）
- **us-east-1（バージニア北部）**リージョンで作業

> **注意**: Gateway セットアップスクリプトは、AgentCore サービス用の適切な信頼ポリシーを持つ必要な IAM ロールを自動的に作成します。

## セットアップ手順

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

**重要**: boto3 バージョン 1.42.0 以上がインストールされていることを確認：

```bash
pip install --upgrade boto3
```

### 2. デモノートブックを開く

```bash
jupyter notebook AgentCore-Policy-Demo.ipynb
```

### 3. ノートブックに従う

ノートブックは以下をガイドします：

1. **環境セットアップ** - 認証情報と依存関係の確認
2. **Lambda デプロイ** - 3つの Lambda 関数をデプロイ（ApplicationTool、RiskModelTool、ApprovalTool）
3. **Gateway セットアップ** - OAuth で AgentCore Gateway を設定し、Lambda ターゲットをアタッチ
4. **エージェントテスト** - すべてのツールにアクセスできる AI エージェントをテスト（ポリシーなし）
5. **Policy Engine** - Policy Engine を作成し Gateway にアタッチ
6. **Cedar ポリシー** - アクセス制御用の Cedar ポリシーを作成してデプロイ
7. **ポリシーテスト** - 実際の AI エージェントリクエストで ALLOW と DENY シナリオをテスト
8. **クリーンアップ** - 作成されたすべてのリソースを削除

> **注意**: このデモでは boto3 のネイティブ policy-registry クライアント（boto3 1.42.0+ で利用可能）と AI エージェント機能用の Strands フレームワークを使用します。

## プロジェクト構造

```
Getting-Started/
├── AgentCore-Policy-Demo.ipynb    # メインデモノートブック
├── README.md                       # このファイル
├── requirements.txt                # Python 依存関係
├── config.json                     # 生成された設定ファイル
└── scripts/                        # サポートスクリプト
    ├── setup_gateway.py            # 自動 IAM ロール作成を備えた Gateway セットアップ
    ├── agent_with_tools.py         # AI エージェントセッションマネージャー
    ├── get_client_secret.py        # Cognito クライアントシークレットの取得
    ├── policy_generator.py         # 自然言語から Cedar への生成
    └── lambda-target-setup/        # Lambda デプロイスクリプト
        ├── deploy_lambdas.py       # 3つの Lambda 関数すべてをデプロイ
        ├── application_tool.js     # ApplicationTool Lambda コード
        ├── risk_model_tool.js      # RiskModelTool Lambda コード
        └── approval_tool.js        # ApprovalTool Lambda コード
```

## 主要概念

### AgentCore Gateway

エージェントがツールにアクセスできるようにする MCP のようなクライアント。

### Policy Engine

定義されたルールに対してリクエストをリアルタイムで評価する Cedar ポリシーのコレクション。

### Cedar ポリシー言語

以下の構造を持つ宣言的ポリシー言語：

```cedar
permit(
  principal,              // 誰がアクセスできるか
  action,                 // どのアクションを実行できるか
  resource                // どのリソースにアクセスできるか
) when {
  conditions              // どの条件下で
};
```

### ポリシーモード

- **LOG_ONLY**: ポリシーを評価するがリクエストをブロックしない（テスト用）
- **ENFORCE**: ポリシーに違反するリクエストを積極的にブロック（本番用）

## ポリシー例

```cedar
permit(
  principal,
  action == AgentCore::Action::"ApplicationToolTarget___create_application",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  context.input.coverage_amount <= 1000000
};
```

このポリシーは：
- 100万ドル未満の補償額での保険申請作成を許可
- 100万ドル以上の補償額の申請を拒否
- ApplicationTool ターゲットに適用
- `coverage_amount` パラメータをリアルタイムで評価

> **重要な洞察**: Policy Engine が ENFORCE モードで Gateway にアタッチされると、デフォルトのアクションは DENY です。アクセスを許可したい各ツールに対して明示的に permit ポリシーを作成する必要があります。

## アーキテクチャ

```
┌─────────────┐
│   AI Agent  │
└──────┬──────┘
       │ ツール呼び出しリクエスト
       ▼
┌─────────────────────┐
│  AgentCore Gateway  │
│  + OAuth 認証       │
└──────┬──────────────┘
       │ ポリシーチェック
       ▼
┌─────────────────────┐
│   Policy Engine     │
│   (Cedar ポリシー)  │
└──────┬──────────────┘
       │ ALLOW / DENY
       ▼
┌─────────────────────┐
│   Lambda ターゲット │
│   (RefundTool)      │
└─────────────────────┘
```

## テスト

デモには実際の AI エージェントによる包括的なテストが含まれています：

### Policy Engine アタッチ前
- エージェントは3つすべてのツールをリストできる
- エージェントは制限なしですべてのツールを呼び出せる
- ポリシー適用なし

### Policy Engine アタッチ後（空）
- エージェントはツールをリストできない（デフォルト DENY）
- エージェントはツールを呼び出せない
- すべてのリクエストがブロック

### Application ポリシー追加後
- エージェントは ApplicationTool のみをリストできる
- エージェントは100万ドル未満の申請を作成できる ✅
- エージェントは100万ドル超の申請を作成できない ❌
- 他のツールはブロックされたまま

### テスト 1: ALLOW シナリオ ✅
- リクエスト: 75万ドルの補償額で申請を作成
- 期待結果: 許可
- 理由: 75万ドル <= 100万ドル
- 結果: Lambda が実行され、申請が作成される

### テスト 2: DENY シナリオ ❌
- リクエスト: 150万ドルの補償額で申請を作成
- 期待結果: 拒否
- 理由: 150万ドル > 100万ドル
- 結果: ポリシーがリクエストをブロック、Lambda は実行されない

## 高度な機能

### 複数条件

```cedar
permit(...) when {
  context.input.coverage_amount <= 1000000 &&
  has(context.input.applicant_region) &&
  context.input.applicant_region == "US"
};
```

### リージョンベースの条件

```cedar
permit(...) when {
  context.input.applicant_region in ["US", "CA", "UK"]
};
```

### リスクモデルガバナンス

```cedar
permit(
  principal,
  action == AgentCore::Action::"RiskModelToolTarget___invoke_risk_model",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  context.input.API_classification == "public" &&
  context.input.data_governance_approval == true
};
```

### 承認しきい値

```cedar
permit(
  principal,
  action == AgentCore::Action::"ApprovalToolTarget___approve_underwriting",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  context.input.claim_amount <= 100000 &&
  context.input.risk_level in ["low", "medium"]
};
```

### Deny ポリシー

```cedar
forbid(...) when {
  context.input.coverage_amount > 10000000
};
```

## モニタリングとデバッグ

### CloudWatch ログ

ポリシー判定は CloudWatch にログ記録されます：

- **Gateway ログ**: リクエスト/レスポンスの詳細
- **Policy Engine ログ**: ポリシー評価結果
- **Lambda ログ**: ツール実行の詳細

### よくある問題

1. **ポリシーが適用されない**
   - ENFORCE モード（LOG_ONLY ではない）を確認
   - ポリシーステータスが ACTIVE であることを確認
   - Gateway アタッチメントを確認

2. **すべてのリクエストが拒否される**
   - ポリシー条件を確認
   - アクション名がターゲットと一致することを確認
   - リソース ARN が Gateway と一致することを確認

3. **認証エラー**
   - OAuth 認証情報を確認
   - トークンエンドポイントへのアクセスを確認
   - client_id と client_secret が正しいことを確認

4. **モジュールインポートエラー**
   - boto3 1.42.0+ がインストールされていることを確認: `pip install --upgrade boto3`
   - strands がインストールされていることを確認: `pip install strands`
   - 依存関係更新後に Jupyter カーネルを再起動
   - Python キャッシュをクリア: `rm -rf scripts/__pycache__`

5. **エージェントセッションエラー**
   - `MCPClientInitializationError` が表示される場合、ノートブックカーネルを再起動
   - config.json に client_secret フィールドが入力されていることを確認
   - シークレットがない場合は `scripts/get_client_secret.py` を実行して取得

6. **AWS トークン期限切れ**
   - AWS 認証情報を更新: `aws sso login` または `aws configure`
   - ノートブックカーネルを再起動して新しい認証情報を取得
   - 最初からセルを再実行

## その他のリソース

- **Cedar ポリシー言語**: [Cedar ドキュメント](https://docs.cedarpolicy.com/)
- **Amazon Bedrock AgentCore Policy**: [AWS AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)

---

**ハッピービルディング！** 🚀
