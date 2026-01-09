# デモ環境

SRE エージェントには、インフラストラクチャ操作をシミュレートするデモ環境が含まれています。これにより、本番システムに接続せずにシステムの機能を探索できます。

**重要な注意**: [`backend/data`](../backend/data) 内のデータは合成的に生成されたものであり、backend ディレクトリには実際の SRE エージェントバックエンドがどのように動作するかを示すスタブサーバーが含まれています。本番環境では、これらの実装を実際のシステムに接続し、ベクトルデータベースを使用し、他のデータソースと統合する実際の実装に置き換える必要があります。このデモはアーキテクチャの例示として機能し、バックエンドコンポーネントはプラグアンドプレイで置き換え可能なように設計されています。

## デモバックエンドの起動

> **🔒 SSL 要件:** AgentCore Gateway を使用する場合、バックエンドサーバーは HTTPS で実行する必要があります。クイックスタートセクションの SSL コマンドを使用してください。

デモバックエンドは、異なるインフラストラクチャドメインに対して現実的なレスポンスを提供する 4 つの専門 API サーバーで構成されています：

```bash
# SSL 付きですべてのデモサーバーを起動（推奨）
cd backend

# サーバーバインディング用のプライベート IP を取得
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s)
PRIVATE_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
  -s http://169.254.169.254/latest/meta-data/local-ipv4)

# SSL 証明書付きで起動
./scripts/start_demo_backend.sh \
  --host $PRIVATE_IP \
  --ssl-keyfile /opt/ssl/privkey.pem \
  --ssl-certfile /opt/ssl/fullchain.pem

# 代替: SSL なしで起動（テスト専用 - AgentCore Gateway と互換性なし）
# ./scripts/start_demo_backend.sh --host 0.0.0.0

# スクリプトは 4 つの API サーバーを起動：
# - Kubernetes API（ポート 8011）: 複数の namespace を持つ K8s クラスターをシミュレート
# - Logs API（ポート 8012）: エラーインジェクション付きの検索可能なアプリケーションログを提供
# - Metrics API（ポート 8013）: 異常を含む現実的なパフォーマンスメトリクスを生成
# - Runbooks API（ポート 8014）: 運用手順とトラブルシューティングガイドを提供
```

## デモシナリオ

デモ環境には、SRE エージェントの機能を示す事前設定されたシナリオがいくつか含まれています：

**データベース Pod 障害シナリオ**: デモには、本番 namespace で障害が発生しているデータベース Pod が含まれており、関連するエラーログとリソース枯渇メトリクスが付随しています。このシナリオは、エージェントがメモリリークを根本原因として特定するためにどのように協力するかを示しています。

**API ゲートウェイレイテンシシナリオ**: API ゲートウェイの高レイテンシをシミュレートし、対応する遅いクエリログと CPU スパイクを伴います。これは、異なるデータソース間で問題を相関させるシステムの能力を示しています。

**カスケード障害シナリオ**: 認証サービスの障害が複数のサービスにカスケード障害を引き起こす複雑なシナリオです。これは、分散システム全体で問題をトレースするエージェントの能力を示しています。

## デモデータのカスタマイズ

デモデータは `backend/data/` 下の JSON ファイルに保存されており、特定のユースケースに合わせてカスタマイズできます：

```bash
backend/data/
├── k8s_data/
│   ├── pods.json         # Pod の定義とステータス
│   ├── deployments.json  # デプロイメント設定
│   └── events.json       # クラスターイベント
├── logs_data/
│   └── application_logs.json  # 様々な重大度レベルのログエントリ
├── metrics_data/
│   └── performance_metrics.json  # 時系列メトリクスデータ
└── runbooks_data/
    └── runbooks.json     # 運用手順
```

## デモの停止

```bash
# すべてのデモサーバーを停止
cd backend
./scripts/stop_demo_backend.sh
```
