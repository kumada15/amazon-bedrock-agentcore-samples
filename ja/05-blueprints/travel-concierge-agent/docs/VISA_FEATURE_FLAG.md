# Visa 統合機能フラグ

## 概要

このリポジトリには、**実際の Visa Token Service API** と **モック/フェイク実装** を切り替えるための機能フラグシステムが含まれています。これにより、実際の Visa API 認証情報を必要とせず、実際の API コールを行わずにアプリケーションを開発およびテストできます。

## クイックスタート

### Visa 統合を無効化（モック API を使用 - デフォルト）

デフォルトでは、Visa 統合は **無効** であり、モック/フェイク API を使用します：

```bash
# オプション 1: 環境変数を設定しない（デフォルトで false）

# オプション 2: 明示的に無効化
export VISA_INTEGRATION_ENABLED=false

# オプション 3: 0 を使用して無効化
export VISA_INTEGRATION_ENABLED=0
```

### Visa 統合を有効化（実際の API を使用）

実際の Visa Token Service API を使用するには：

```bash
# オプション 1: true に設定
export VISA_INTEGRATION_ENABLED=true

# オプション 2: 1 に設定
export VISA_INTEGRATION_ENABLED=1
```

## 動作の仕組み

機能フラグは `VISA_INTEGRATION_ENABLED` 環境変数によって制御されます：

- **無効時**（`false`、`0`、または未設定）：
  - すべての Visa API コールがモック/フェイクされる
  - Visa サーバーへの実際の HTTP リクエストは行われない
  - Visa API 認証情報は不要
  - フェイクの登録 ID、トークン ID、カードトークンを返す
  - 開発とテストに最適

- **有効時**（`true` または `1`）：
  - 実際の Visa Token Service API を使用
  - AWS Secrets Manager に有効な Visa API 認証情報が必要
  - Visa サーバーへの実際の HTTPS リクエストを行う
  - 実際の登録データとセキュアトークンを返す
  - 本番環境での使用に必要
