# Visa Lambda スタック

Visa Payment API 統合用の AWS Lambda プロキシ。

## 概要

このスタックは、フロントエンドからのすべての Visa Payment API 呼び出しをプロキシする Lambda 関数をデプロイします。開発および本番環境でローカル Flask サーバー（`local-visa-server`）を実行する必要がなくなります。

## アーキテクチャ

```
フロントエンド → API Gateway → Lambda → Visa API
                          ↓
                    Secrets Manager (Visa 認証情報)
```

## クイックスタート

### デプロイ

プロジェクトルートから：

```bash
npm run deploy:visa-lambda
```

### フロントエンドの更新

デプロイ後、出力から API Gateway URL をコピーし、`web-ui/.env.local` を更新します：

```bash
VITE_VISA_PROXY_URL=https://YOUR_API_GATEWAY_URL/
VITE_VISA_MOCK_MODE=false
```

### テスト

```bash
npm run dev
```

## スタックリソース

- **Lambda 関数**: Flask + Mangum を備えた Python 3.11 コンテナ
- **API Gateway**: `/api/visa/*` プロキシルート付き REST API
- **IAM ロール**: Visa 認証情報用の Secrets Manager アクセス
- **CloudWatch Logs**: 自動ログ記録

## モニタリング

```bash
# Lambda ログを表示
aws logs tail /aws/lambda/VisaProxyLambda --follow
```

## コスト

- 開発環境: 約 $4/月
- 本番環境: 約 $37/月

## クリーンアップ

```bash
npm run clean:visa-lambda
```

## ドキュメント

完全なデプロイガイドはこの README と `../../docs/VISA_LOCAL_SETUP.md` を参照してください
