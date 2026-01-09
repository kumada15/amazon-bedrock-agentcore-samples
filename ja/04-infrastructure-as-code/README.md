# Amazon Bedrock AgentCore 用 Infrastructure as Code サンプル

CloudFormation テンプレート、AWS CDK、または Terraform を使用して Amazon Bedrock AgentCore リソースをデプロイします。

## 概要

これらの Infrastructure as Code サンプルを使用すると、以下のことが可能になります：
- 環境間で一貫して AgentCore リソースをデプロイ
- Infrastructure as Code でインフラストラクチャのプロビジョニングを自動化
- インフラストラクチャのバージョン管理を維持
- セキュリティとモニタリングに関する AWS のベストプラクティスを実装

お好みのアプローチを選択してください：
- **[CloudFormation](./cloudformation/)** - 宣言的インフラストラクチャ用の YAML/JSON テンプレート
- **[CDK](./cdk/)** - プログラマティックなインフラストラクチャ用の Python コード
- **[Terraform](./terraform/)** - 状態管理を備えた宣言的インフラストラクチャ用の HCL コード

## サンプル

### 1. 基本的なエージェントランタイム
追加のツールやメモリなしで、シンプルな Strands エージェントを含む AgentCore Runtime をデプロイします。

**デプロイされるもの：**
- シンプルなエージェントを含む AgentCore Runtime
- ECR リポジトリと自動化された Docker ビルド
- 最小権限ポリシーを持つ IAM ロール

**ユースケース：** 複雑さなしに AgentCore の基礎を学ぶ
**デプロイ時間：** 約5-15分
**推定コスト：** 約$50-100/月

**実装：** [CloudFormation](./cloudformation/basic-runtime/) | [CDK](./cdk/basic-runtime/) | [Terraform](./terraform/basic-runtime/)

### 2. AgentCore Runtime 上の MCP サーバー
自動化された Docker ビルドと JWT 認証を備えた完全な MCP（Model Context Protocol）サーバーをデプロイします。

**デプロイされるもの：**
- MCP サーバーをホストする AgentCore Runtime
- JWT 認証用の Amazon Cognito
- 自動化された ARM64 Docker ビルド

**サンプル MCP ツール：** `add_numbers`、`multiply_numbers`、`greet_user`
**デプロイ時間：** 約10-15分
**推定コスト：** 約$50-100/月

**実装：** [CloudFormation](./cloudformation/mcp-server-agentcore-runtime/) | [CDK](./cdk/mcp-server-agentcore-runtime/) | [Terraform](./terraform/mcp-server-agentcore-runtime/)

### 3. マルチエージェントランタイム
Agent1（オーケストレーター）が複雑なタスクのために Agent2（スペシャリスト）を呼び出すことができるマルチエージェントシステムをデプロイします。

**デプロイされるもの：**
- エージェント間通信を備えた2つの AgentCore Runtime
- エージェント間呼び出し権限を持つ IAM ロール
- 各エージェント用の個別 ECR リポジトリ

**アーキテクチャ：** Agent1 がリクエストをルーティングし、詳細な分析のために Agent2 に委任
**デプロイ時間：** 約15-20分
**推定コスト：** 約$100-200/月

**実装：** [CloudFormation](./cloudformation/multi-agent-runtime/) | [CDK](./cdk/multi-agent-runtime/) | [Terraform](./terraform/multi-agent-runtime/)

### 4. ツールとメモリを備えたエンドツーエンド天気エージェント
ブラウザ自動化、コードインタープリター、メモリを備えた完全な天気ベースのアクティビティ計画エージェントをデプロイします。

**デプロイされるもの：**
- Strands エージェントを含む AgentCore Runtime
- 天気データの Web スクレイピング用ブラウザツール
- 天気分析用コードインタープリターツール
- ユーザー設定を保存するメモリ
- 結果保存用 S3 バケット

**機能：** weather.gov をスクレイプし、状況を分析し、設定を保存し、推奨を生成
**デプロイ時間：** 約15-20分
**推定コスト：** 約$100-150/月

**実装：** [CloudFormation](./cloudformation/end-to-end-weather-agent/) | [CDK](./cdk/end-to-end-weather-agent/) | [Terraform](./terraform/end-to-end-weather-agent/)

## 前提条件

サンプルをデプロイする前に、以下を確認してください：

1. 適切な権限を持つ **AWS アカウント**
2. **AWS CLI** がインストールされ設定済み
3. **Amazon Bedrock AgentCore** へのアクセス（プレビュー）
4. 以下を作成するための **IAM 権限**：
   - CloudFormation スタック（CloudFormation サンプル用）
   - IAM ロールとポリシー
   - ECR リポジトリ
   - Lambda 関数
   - AgentCore リソース
   - S3 バケット（天気エージェント用）

CDK サンプルの場合は、以下もインストールしてください：
- Python 3.8+
- AWS CDK v2.218.0 以降

Terraform サンプルの場合は、以下もインストールしてください：
- Terraform >= 1.6（バージョン管理には [tfenv](https://github.com/tfutils/tfenv) を推奨）
- 注意：`brew install terraform` は非推奨の v1.5.7 を提供します

## リポジトリ構造

```
04-infrastructure-as-code/
├── README.md                          # このファイル
├── cloudformation/                    # CloudFormation サンプル
│   ├── README.md                      # CloudFormation 固有のガイド
│   ├── basic-runtime/
│   ├── mcp-server-agentcore-runtime/
│   ├── multi-agent-runtime/
│   └── end-to-end-weather-agent/
├── cdk/                              # CDK サンプル
│   ├── README.md                     # CDK 固有のガイド
│   ├── basic-runtime/
│   ├── mcp-server-agentcore-runtime/
│   ├── multi-agent-runtime/
│   └── end-to-end-weather-agent/
└── terraform/                        # Terraform サンプル
    ├── README.md                     # Terraform 固有のガイド
    ├── basic-runtime/
    ├── mcp-server-agentcore-runtime/
    ├── multi-agent-runtime/
    └── end-to-end-weather-agent/
```

## 追加リソース

- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [AWS CloudFormation ドキュメント](https://docs.aws.amazon.com/cloudformation/)
- [AWS CDK ドキュメント](https://docs.aws.amazon.com/cdk/)
- [Terraform ドキュメント](https://www.terraform.io/docs)
- [オリジナルチュートリアル](../01-tutorials/)
