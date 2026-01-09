# Amazon Bedrock AgentCore SDK ツールサンプル

このフォルダには、Amazon Bedrock AgentCore SDK ツールの使用方法を示すサンプルが含まれています：

## ブラウザツール

* `browser_viewer_replay.py` - 適切な表示サイズサポートを備えた Amazon Bedrock AgentCore ブラウザライブビューア。
* `browser_interactive_session.py` - ライブ表示、録画、再生機能を備えた完全なエンドツーエンドブラウザ体験。
* `session_replay_viewer.py` - 録画されたブラウザセッションを再生するためのビューア。
* `view_recordings.py` - S3 から録画されたセッションを表示するスタンドアロンスクリプト。

## 前提条件

### Python 依存関係
```bash
pip install -r requirements.txt
```

必要なパッケージ: fastapi, uvicorn, rich, boto3, bedrock-agentcore

### AWS 認証情報
AWS 認証情報が設定されていることを確認：
```bash
aws configure
```

## サンプルの実行

### 録画と再生を備えた完全なブラウザ体験
`02-Agent-Core-browser-tool/interactive_tools` ディレクトリから：
```bash
python -m live_view_sessionreplay.browser_interactive_session
```

### 録画の表示
`02-Agent-Core-browser-tool/interactive_tools` ディレクトリから：
```bash
python -m live_view_sessionreplay.view_recordings --bucket YOUR_BUCKET --prefix YOUR_PREFIX
```

## 録画と再生を備えた完全なブラウザ体験

ライブブラウザ表示、S3 への自動録画、統合セッション再生を含む完全なエンドツーエンドワークフローを実行します。

### 機能
- S3 への自動録画付きブラウザセッションの作成
- インタラクティブ制御（取得/解放）付きライブ表示
- 表示解像度のオンザフライ調整
- S3 への自動セッション録画
- 録画を視聴するための統合セッション再生ビューア

### 動作原理
1. スクリプトが録画を有効にしたブラウザを作成
2. ブラウザセッションが開始され、ローカルブラウザに表示
3. ブラウザの手動制御を取得するか、自動化を実行
4. すべてのアクションが自動的に S3 に録画
5. セッションを終了（Ctrl+C）すると、録画を表示する再生ビューアが開く

### 環境変数
- `AWS_REGION` - AWS リージョン（デフォルト: us-west-2）
- `AGENTCORE_ROLE_ARN` - ブラウザ実行用の IAM ロール ARN（デフォルト: アカウント ID から自動生成）
- `RECORDING_BUCKET` - 録画用 S3 バケット（デフォルト: session-record-test-{ACCOUNT_ID}）
- `RECORDING_PREFIX` - 録画用 S3 プレフィックス（デフォルト: replay-data）

### 必要な IAM 権限
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::session-record-test-*",
                "arn:aws:s3:::session-record-test-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "bedrock:*",
            "Resource": "*"
        }
    ]
}
```

## スタンドアロンセッション再生ビューア

新しいブラウザを作成せずに S3 から直接録画されたブラウザセッションを表示するための個別ツール。

### 機能
- S3 に直接接続して録画を表示
- セッション ID を指定して過去の任意の録画を表示
- セッション ID が指定されていない場合は最新の録画を自動的に検索

### 使用方法

```bash
# バケット内の最新の録画を表示
python -m live_view_sessionreplay.view_recordings --bucket session-record-test-123456789012 --prefix replay-data

# 特定の録画を表示
python -m live_view_sessionreplay.view_recordings --bucket session-record-test-123456789012 --prefix replay-data --session 01JZVDG02M8MXZY2N7P3PKDQ74

# 特定の AWS プロファイルを使用
python -m live_view_sessionreplay.view_recordings --bucket session-record-test-123456789012 --prefix replay-data --profile my-profile
```

### 録画の検索

S3 録画の一覧表示：
```bash
aws s3 ls s3://session-record-test-123456789012/replay-data/ --recursive
```

## トラブルシューティング

### DCV SDK が見つからない
DCV SDK ファイルが `interactive_tools/static/dcvjs/` に配置されていることを確認

### ブラウザセッションが表示されない
- DCV SDK が正しくインストールされていることを確認
- ブラウザコンソール（F12）でエラーを確認
- AWS 認証情報に適切な権限があることを確認

### 録画が機能しない
- S3 バケットが存在しアクセス可能であることを確認
- S3 操作の IAM 権限を確認
- 実行ロールに適切な権限があることを確認

### セッション再生の問題
- S3 に録画が存在することを確認（AWS CLI またはコンソールを使用）
- コンソールログでエラーを確認
- S3 バケットポリシーがオブジェクトの読み取りを許可していることを確認

### S3 アクセスエラー
- AWS 認証情報が設定されていることを確認
- S3 操作の IAM 権限を確認
- バケット名がグローバルに一意であることを確認

## アーキテクチャノート
- ライブビューアは FastAPI を使用して署名付き DCV URL を提供
- 録画はデータプレーンのブラウザサービスによって直接処理
- 再生は録画されたイベントの再生に rrweb-player を使用
- すべてのコンポーネントは一緒にまたは独立して動作可能
