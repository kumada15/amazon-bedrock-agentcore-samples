# バックエンドデモインフラストラクチャ

このディレクトリには、SRE Agent のテストと開発のための完全なデモバックエンドインフラストラクチャが含まれています。

## 📁 構造

```
backend/
├── config_utils.py               # 設定ユーティリティ
├── data/                         # 整理されたフェイクデータ
│   ├── k8s_data/                # Kubernetes モックデータ
│   ├── logs_data/               # アプリケーションログ
│   ├── metrics_data/            # パフォーマンスメトリクス
│   └── runbooks_data/           # 運用手順
├── openapi_specs/               # API 仕様
│   ├── k8s_api.yaml            # Kubernetes API 仕様
│   ├── logs_api.yaml           # Logs API 仕様
│   ├── metrics_api.yaml        # Metrics API 仕様
│   └── runbooks_api.yaml       # Runbooks API 仕様
├── servers/                     # モック API 実装
│   ├── k8s_server.py           # Kubernetes API サーバー
│   ├── logs_server.py          # Logs API サーバー
│   ├── metrics_server.py       # Metrics API サーバー
│   ├── runbooks_server.py      # Runbooks API サーバー
│   ├── run_all_servers.py      # 全サーバーを起動
│   └── stop_servers.py         # 全サーバーを停止
└── scripts/                    # 運用スクリプト
    ├── start_demo_backend.sh   # 簡易起動
    └── stop_demo_backend.sh    # 簡易停止
```

## 🚀 クイックスタート

### 簡易起動（推奨）
```bash
# シンプルな Python HTTP サーバーで全デモサーバーを起動
./scripts/start_demo_backend.sh
```

### 高度な起動（完全な FastAPI サーバー）
```bash
# FastAPI で完全機能サーバーを起動
cd servers
python run_all_servers.py
```

## 🌐 API エンドポイント

実行時、デモバックエンドは以下のエンドポイントを提供：

- **Kubernetes API**: http://localhost:8001
- **Logs API**: http://localhost:8002
- **Metrics API**: http://localhost:8003
- **Runbooks API**: http://localhost:8004

## 📊 データ構成

### K8s データ (`data/k8s_data/`)
- `deployments.json` - デプロイメントステータスと設定
- `pods.json` - Pod 状態とリソース使用量
- `events.json` - クラスターイベントと警告

### Logs データ (`data/logs_data/`)
- `application_logs.json` - アプリケーションログエントリ
- `error_logs.json` - エラー固有のログエントリ

### Metrics データ (`data/metrics_data/`)
- `performance_metrics.json` - レスポンスタイム、スループット
- `resource_metrics.json` - CPU、メモリ、ディスク使用量

### Runbooks データ (`data/runbooks_data/`)
- `incident_playbooks.json` - インシデント対応手順
- `troubleshooting_guides.json` - ステップバイステップガイド

## 🔧 サーバー実装

### シンプル HTTP サーバー（デフォルト）
ファイルから JSON データを直接提供する基本的な Python `http.server` 実装。

### FastAPI サーバー（高度）
以下を含む完全機能 FastAPI サーバー：
- OpenAPI ドキュメント
- リクエストバリデーション
- レスポンススキーマ
- ヘルスエンドポイント

## 📋 OpenAPI 仕様

すべての API の完全な OpenAPI 3.0 仕様：
- エンドポイント定義
- リクエスト/レスポンススキーマ
- 認証要件
- サンプルデータ

## 🛑 サービス停止

```bash
# シンプルな方法
./scripts/stop_demo_backend.sh

# 高度な方法
cd servers
python stop_servers.py
```

## 🧪 テスト

個別の API をテスト：
```bash
# K8s API をテスト
curl http://localhost:8001/health

# 特定のエンドポイントでテスト
curl http://localhost:8001/api/v1/namespaces/production/pods
curl http://localhost:8002/api/v1/logs/search?query=error
```

## ⚙️ 設定

バックエンドは以下を含むリアルなデータシナリオを使用：
- 失敗したデータベース Pod
- メモリプレッシャー警告
- パフォーマンス低下パターン
- 一般的なトラブルシューティング手順

これにより、SRE Agent システムの包括的なテスト環境が提供されます。