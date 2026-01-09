# AWS re:Invent 2025 AIML301: Bedrock AgentCore でエンドツーエンドの SRE ユースケースを構築

## 概要

このワークショップでは、Site Reliability Engineers (SRE) が Amazon Bedrock AgentCore を活用して、診断から修復、予防までのインシデント対応を自動化する方法を示します。

**ワークショップシナリオ:** AWS 上にデプロイされた CRM アプリケーション（EC2 + NGINX + DynamoDB）で障害が発生します。問題を診断し、承認ワークフローで安全に修復し、リサーチとベストプラクティスを通じて再発を防止するマルチエージェントシステムを構築します。

## 学習目標

このワークショップを完了することで、以下を習得します：

1. **Lab 1** - 前提条件の確認と、障害注入機能を備えた現実的な CRM アプリケーションスタックのセットアップ
2. **Lab 2** - CloudWatch ログとメトリクスを分析する診断エージェントの構築
3. **Lab 3a** - 承認ワークフローと Code Interpreter を備えた修復エージェントの作成
4. **Lab 3b** - カスタム Lambda インターセプターによるきめ細かいアクセス制御の実装
5. **Lab 4** - リサーチ用に AgentCore Browser を使用した予防エージェントの実装
6. **Lab 5** - AgentCore Gateway と対話型 Streamlit UI を使用したスーパーバイザーパターンによるすべてのエージェントのオーケストレーション

## クイックスタート

### 推奨ラボフロー

```
Lab-01 (前提条件とインフラストラクチャ)
   ↓
Lab-02 (診断エージェント)
   ↓
Lab-03a (修復エージェント)
   ↓
Lab-03b (きめ細かいアクセス制御)
   ↓
Lab-04 (予防エージェント)
   ↓
Lab-05 (マルチエージェントオーケストレーション + Streamlit UI)
```

### 始め方

1. **ワークショップをダウンロード**してローカルマシンに保存
2. ワークショップディレクトリで **Jupyter Notebook/Lab を開く**
3. **`Lab-01-prerequisites-infra.ipynb` から開始**し、すべてのセクションを実行
4. Lab-05 まで**ラボを順番に進める**
5. 完了したら Lab-05 のクリーンアップセルを使用して**リソースをクリーンアップ**

**⏱️ 推定時間:**
- 完全なワークショップ（Lab 1-5）: **2時間**

**✨ すべてがノートブック内で完結 - ターミナルコマンドは不要です！**

## 動作原理

### すべてがノートブックで実行

- ノートブックを開き、上から下まで実行
- すべてのセットアップ、設定、プロビジョニングが自動的に行われる
- ターミナルコマンドは不要
- 各ノートブックは自己完結型
- ノートブックは必要に応じてヘルパーとユーティリティをインポート

**ノートブック内で行われることの例：**
1. `pip install` で必要な Python パッケージをインストール
2. AWS 認証情報と環境を設定
3. 前提条件を確認
4. AWS リソース（EC2、DynamoDB、Lambda など）をプロビジョニング
5. エージェントを実装してテスト
6. テスト用に障害を注入
7. 診断、修復、または予防ワークフローを実行
8. CloudWatch で結果を監視
9. 完了したらリソースをクリーンアップ

## アーキテクチャ

ワークショップでは、自動化されたインシデント対応のためのマルチエージェントシステムを実装します：

![アーキテクチャ図](architecture/architecture.png)

**主要コンポーネント：**

1. **CRM アプリケーションスタック**
   - NGINX ウェブサーバーを実行する EC2 インスタンス
   - データ永続化用の DynamoDB
   - ログとメトリクス用の CloudWatch

2. **エージェントシステム**
   - **診断エージェント**: CloudWatch ログとメトリクスを分析して問題を特定
   - **修復エージェント**: 承認ワークフローで Code Interpreter を使用して修正を実行
   - **予防エージェント**: Browser ツールを使用してベストプラクティスをリサーチ
   - **スーパーバイザーエージェント**: すべてのエージェントをオーケストレートしワークフローを管理

3. **AgentCore プラットフォーム**
   - **Runtime**: エージェントのサーバーレスデプロイ
   - **Gateway**: JWT 認証付きツールオーケストレーション用 MCP プロトコル
   - **Code Interpreter**: 修復スクリプトの安全な実行環境
   - **Browser**: 予防のためのウェブリサーチ機能
   - **Memory**: インタラクション間のコンテキスト永続化

4. **セキュリティとアクセス制御**
   - ユーザー認証用 Cognito
   - エージェント間通信用 OAuth2 M2M
   - きめ細かい RBAC 用 Lambda インターセプター
   - JWT ベースの認可

5. **ユーザーインターフェース**
   - 対話型エージェント操作用 Streamlit ウェブアプリ
   - リアルタイムストリーミングレスポンス
   - 承認ワークフロー統合

## デモビデオ

完全なワークショップウォークスルーを視聴：

![ワークショップデモ](demo/aim301-multi-agent-mcp-agentcore-gateway.gif)

デモでは以下を示します：
- CRM アプリケーションインフラストラクチャのセットアップ
- 実際のインシデントをシミュレートする障害の注入
- 問題を特定するための診断の実行
- 承認ワークフローによる修復の実行
- 予防戦略のリサーチ
- Streamlit UI を通じたすべてのエージェントのオーケストレーション

## ワークショップ構造

```
├── Lab-01-prerequisites-infra.ipynb             # Lab 1: 前提条件とインフラストラクチャセットアップ
├── Lab-02-diagnostics-agent.ipynb               # Lab 2: 診断エージェント
├── Lab-03a-remediation-agent.ipynb              # Lab 3a: 修復エージェント + 承認
├── Lab-03b-remediation-agent-fgac.ipynb         # Lab 3b: きめ細かいアクセス制御
├── Lab-04-prevention-agent.ipynb                # Lab 4: 予防エージェント
├── Lab-05-multi-agent-orchestration.ipynb       # Lab 5: マルチエージェントオーケストレーション + Streamlit
│
├── lab_helpers/                        # ノートブックがインポートするヘルパーモジュール
│   ├── lab_01/                        # Lab 1 固有のヘルパー
│   ├── lab_02/                        # Lab 2 固有のヘルパー
│   ├── lab_03/                        # Lab 3 固有のヘルパー
│   ├── lab_04/                        # Lab 4 固有のヘルパー
│   ├── lab_05/                        # Lab 5 固有のヘルパー（streamlit_app.py を含む）
│   ├── constants.py                   # 設定定数
│   ├── parameter_store.py             # AWS Parameter Store ユーティリティ
│   └── ...                            # その他の共有ユーティリティ
├── requirements.txt                    # Python 依存関係
└── README.md                           # このファイル
```

## 前提条件

開始前に以下を確認してください：

- Python 3.10 以上
- Jupyter Notebook または JupyterLab がインストール済み
- EC2、DynamoDB、Lambda、CloudWatch、Bedrock の権限を持つ AWS アカウント
- ローカルに設定された AWS 認証情報（または Lab 1 でセットアップ）

`Lab-01-prerequisites-infra.ipynb` ノートブックがこれらすべてを確認し、不足している依存関係をインストールします。

## ラボ概要

**Lab 1: 前提条件とインフラストラクチャセットアップ**
- Python バージョン、AWS 認証情報、依存関係を確認
- ワークショップ要件をインストールし Bedrock アクセスを確認
- CRM アプリケーション（EC2 + NGINX + DynamoDB）をデプロイ
- 認証用 Cognito をセットアップ
- CloudWatch モニタリングをセットアップ
- 障害注入ユーティリティを作成

**Lab 2: 診断エージェント**
- CloudWatch ログを分析する Strands エージェントを構築
- 診断ツール付き Lambda 関数をデプロイ
- MCP プロトコル付き AgentCore Gateway を作成
- 実際のアプリケーションログに対してエージェントをテスト

**Lab 3a: Code Interpreter 付き修復エージェント**
- AgentCore Runtime にエージェントをデプロイ
- 安全な実行のために AgentCore Code Interpreter を統合
- OAuth2 M2M 認証を実装
- 修復ワークフローをテスト

**Lab 3b: きめ細かいアクセス制御**
- リクエスト認可用 Lambda インターセプターを作成
- ロールベースのアクセス制御（RBAC）を実装
- Cognito グループを設定（承認者 vs SRE）
- 異なるユーザーロールでアクセス制御をテスト

**Lab 4: Browser 付き予防エージェント**
- AgentCore Browser ツール付き Runtime エージェントをデプロイ
- AWS ドキュメントとベストプラクティスをリサーチ
- 予防プレイブックを生成
- OAuth2 M2M 認証

**Lab 5: Streamlit 付きマルチエージェントオーケストレーション**
- 3つのエージェントすべてを調整するスーパーバイザーエージェントを作成
- JWT 認証付き中央 AgentCore Gateway をセットアップ
- RBAC 用に Lab 3b インターセプターを再利用
- マルチエージェントシステムをデプロイ
- リアルタイムストリーミング付き対話型 Streamlit チャットインターフェースを起動
- エンドツーエンドのインシデント対応ワークフローをテスト

## 主要技術

- **Amazon Bedrock** - 基盤モデル（Claude 3.7 Sonnet）
- **AgentCore** - サーバーレスエージェントプラットフォーム
  - Runtime（デプロイ）
  - Memory（コンテキスト永続化）
  - Gateway（JWT 認証付きツールオーケストレーション）
  - Code Interpreter（修復実行）
  - Browser（リサーチとドキュメント）
  - Observability（モニタリングとトレーシング）
- **Strands Framework** - ストリーミングサポート付きツール使用パターンのエージェントフレームワーク
- **Streamlit** - リアルタイムエージェント操作用対話型ウェブ UI
- **AWS サービス** - EC2、DynamoDB、CloudWatch、Lambda、IAM、Cognito、Bedrock
- **Jupyter Notebooks** - 対話型学習環境

## プロジェクトファイル

### ラボヘルパー (`lab_helpers/`)
ノートブックがインポートする Python モジュール（よりクリーンなコード用）：
- `lab_01/` - インフラストラクチャデプロイと障害注入
- `lab_02/` - Lambda デプロイ、MCP クライアント、ゲートウェイセットアップ
- `lab_03/` - Runtime デプロイ、OAuth2 セットアップ、インターセプター
- `lab_04/` - Runtime デプロイ、ゲートウェイセットアップ、ログ
- `lab_05/` - スーパーバイザーエージェントコード、Streamlit アプリ、IAM セットアップ
- `constants.py` - 設定定数とパラメータパス
- `parameter_store.py` - AWS Parameter Store ユーティリティ
- `config.py` - ワークショップ設定
- `cognito_setup.py` - Cognito ユーザープールとクライアントセットアップ
- `short_term_memory.py` - AgentCore Memory 統合

## トラブルシューティング

**問題が発生した場合：**
1. ノートブック出力でエラーメッセージを確認
2. エラー出力で AWS 認証情報を確認
3. 正しい AWS リージョンにいることを確認
4. ノートブックから直接 CloudWatch ログを確認
5. 前提条件の確認を再度実行

**よくある問題：**
- AWS 認証情報がない → `Lab-01-prerequisites-infra.ipynb` を再実行
- Bedrock モデルにアクセスできない → リージョンで Bedrock が有効になっていることを確認
- Lambda タイムアウト → ノートブックで CloudWatch ログを確認
- リソースが既に存在 → クリーンアップノートブックを実行して再試行

## ワークショップ後

学んだことを適用するために：

1. **自分の環境で：**
   - エージェントを自分のモニタリングシステムに適応
   - デプロイパイプラインと統合
   - インシデント管理プラットフォームに接続

2. **本番環境での使用：**
   - AgentCore Runtime にエージェントをデプロイ
   - インシデント履歴用の永続的メモリをセットアップ
   - オブザーバビリティとアラートを有効化
   - チーム承認ワークフローを確立

3. **高度な機能：**
   - マルチチームオーケストレーション
   - クロスアカウントインシデント対応
   - カスタムツール開発
   - サードパーティ統合

## リソース

- [Amazon Bedrock ドキュメント](https://docs.aws.amazon.com/bedrock/)
- [AgentCore ドキュメント](https://docs.aws.amazon.com/agentcore/)
- [Strands Framework GitHub](https://github.com/aws-samples/strands-agents)
- [AWS re:Invent 2025](https://reinvent.awsevents.com/)

## ライセンス

このワークショップは MIT ライセンスの下でそのまま提供されます。
