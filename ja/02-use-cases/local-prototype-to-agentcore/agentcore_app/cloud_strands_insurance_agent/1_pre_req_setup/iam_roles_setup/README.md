# Bedrock AgentCore 用 IAM ロールセットアップ

このディレクトリには、AWS Bedrock AgentCore アプリケーションに必要な IAM ロールを正しい権限でセットアップするためのスクリプトが含まれています。

## クイックセットアップ

簡単にセットアップするには、シェルスクリプトを使用してください：

```bash
./setup_role.sh
```

このスクリプトは以下を行います：
1. AWS 認証情報を確認
2. 適切なデフォルト値で必要な情報を入力
3. 必要なすべての権限を持つ IAM ロールを作成
4. 設定で使用するロール ARN を表示

## 手動セットアップ

よりカスタマイズされたセットアップを行いたい場合は、Python モジュールを使用できます：

1. `iam_config.ini` を作成/編集して設定を構成：
   ```bash
   python3 config.py
   ```

2. 対話形式でセットアップを実行：
   ```bash
   python3 -c "from collect_info import run_interactive_setup; run_interactive_setup()"
   ```

## 必要な権限

IAM ロールには以下の権限が含まれます：
- ECR（コンテナレジストリアクセス）
- CloudWatch Logs
- X-Ray トレース
- CloudWatch メトリクス
- Bedrock AgentCore アクセストークン
- Bedrock モデル呼び出し

これらの権限は、最小権限の原則に従った AWS ベストプラクティスに準拠しています。

## 前提条件

- 適切な権限で設定された AWS CLI
- IAM ロールとポリシーを作成する権限を持つ AWS アカウント

## ファイル

- `setup_role.sh` - クイックセットアップシェルスクリプト
- `config.py` - 設定管理
- `policy_templates.py` - IAM ポリシーテンプレート
- `collect_info.py` - 対話形式の設定収集
- `trust-policy.json` - 信頼関係ポリシーテンプレート

## トラブルシューティング

問題が発生した場合は、以下を確認してください：

- AWS 認証情報が正しく設定されている（`aws configure`）
- IAM ロールを作成するための十分な権限がある
- AWS CLI がインストールされ、PATH に含まれている

## セキュリティに関する注意

作成される IAM ロールはセキュリティのベストプラクティスに従っています：
- 条件付きの厳格な信頼ポリシー
- 権限の最小権限の原則
- 可能な限りリソースベースの制限
