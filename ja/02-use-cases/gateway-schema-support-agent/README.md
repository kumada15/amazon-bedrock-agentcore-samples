# ICARUS: インタラクティブ AgentCore Gateway 設定用スキーマサポートエージェント

![ICARUS Overview](.assets/overview.png)

## 概要

ICARUS は、AgentCore Gateway との互換性のために OpenAPI 仕様を自動的に修正する AI エージェントです。レガシー仕様を OpenAPI 3.0 に変換し、バリデーションエラーを解決し、Gateway 固有の要件が満たされていることを確認することで、統合時間を数日から数時間に短縮します。

エージェントと対話して、大規模な API から焦点を絞ったサブスキーマを作成し（数百のエンドポイントを特定のコンポーネントにフィルタリング）、API の説明を改善して AI エージェントにとってより使いやすくします。

**主な機能：**

- 自動スキーマ変換と修復
- 反復的な修正によるリアルタイムバリデーション
- 専用ツールを備えたインタラクティブなエージェント
- 大規模 API からの焦点を絞ったサブスキーマ抽出
- エージェント最適化のための AI 強化記述子
- 複雑な API 移行のためのワンクリックソリューション

## デモ
![ICARUS Demo](.assets/ICARUS-demo.gif)

## クイックスタート

すべてのデプロイおよび管理コマンドは、簡単なワンクリックデプロイのために [Makefile](Makefile) で `make` ターゲットとして利用できます。

**前提条件：**

- Bedrock アクセスが有効な AWS アカウント
- 有効な認証情報（`AWS_ACCESS_KEY_ID` など）で設定された [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [AWS Systems Manager Session Manager プラグイン](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)

**デプロイ：**

> **重要:** 以下のコマンドを実行する前に、AWS 認証情報が環境に読み込まれていることを確認してください。

```bash
# アプリケーションをデプロイ（Web アプリケーション付き EC2 インスタンスを作成）
make deploy

# デプロイ完了を待機
make wait

# SSH トンネル経由でアプリケーションにアクセス
make session LOCAL_PORT=8080
# その後、ブラウザで http://localhost:<LOCAL_PORT> を開く
```

`deploy` コマンドは CloudFormation 経由で必要なすべての AWS リソースをプロビジョニングします。`make wait` を使用して完了を監視します（デプロイには約5分かかります）。デプロイ後、`make session` を使用して Session Manager プラグイン経由で安全な SSH トンネルを作成し、ローカルでアプリケーションにアクセスします。

**オプション設定：**

```bash
make deploy \
    STACK_NAME=icarus-app \
    REGION=us-west-2 \
    INSTANCE_TYPE=t3.medium
```

**クリーンアップ：**

```bash
# すべてのリソースを削除
make delete
```

## アーキテクチャ

![ICARUS Architecture](.assets/architecture-flow.png)

ICARUS は [Strands Agent SDK](https://github.com/strands-agents/sdk-python) を使用して構築され、AWS インフラストラクチャ上にデプロイされています（[cfn.yaml](cfn.yaml) を参照）：

- **Amazon Bedrock** - 基盤モデルで AI エージェントを駆動
- **Amazon EC2** - Web アプリケーションとエージェントランタイムをホスト
- **AWS Systems Manager** - Session Manager プラグイン経由で安全なアクセスを提供
- **Amazon CloudWatch** - ロギングとモニタリングを提供
- **Amazon S3** - アプリケーションコードとアーティファクトを保存
- **AWS IAM** - 権限とアクセス制御を管理

## API 仕様の例
- [Adobe API Spec](.assets/sample-spec/adobe-io-events.yaml)

