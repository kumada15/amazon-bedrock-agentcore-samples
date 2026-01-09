# ショッピングエージェント概要

AWS Bedrock AgentCore、Amplify、React で構築された、ショッピング支援機能を備えた AI 搭載コンシェルジュエージェントです。

このショッピングアシスタントは、レビュー調査、機能情報、ユーザープロファイルに基づいたパーソナライズされた推奨など、すべてのショッピング関連のクエリに特化しています。商品を比較し、価格を提示し、レビューを表示し、すべての商品がユーザーの好みや制約に沿っていることを確認します。

## ユースケース詳細
| 情報                | 詳細                                                         |
|---------------------|--------------------------------------------------------------|
| ユースケースタイプ   | Agentic Payments                                             |
| エージェントタイプ   | マルチエージェント                                           |
| ユースケースコンポーネント | ツール (MCP ベース)、オブザーバビリティ (ログ、メトリクス) |
| ユースケース業界     | FSI                                                          |
| 例の複雑さ          | 上級                                                         |
| 使用 SDK            | Strands, MCP                                                 |

## 機能

- **ショッピングアシスタント** - 商品検索とレコメンデーション (SERP API 連携が必要)
- **カート & 決済** - Visa トークン化対応のカート管理 (フィーチャーフラグで有効化)
- **会話メモリ** - セッション間で永続化されるチャット履歴
- **リアルタイムストリーミング** - ツール使用状況インジケーター付きのライブエージェントレスポンス
- **セキュア認証** - JWT ベース認証を使用した AWS Cognito

## はじめに

完全なデプロイ手順、前提条件、トラブルシューティング、設定については、**[デプロイガイド](DEPLOYMENT.md)** を参照してください。

### クイックデプロイ
[開発ガイドセクションへ移動](./DEPLOYMENT.md#Quick_Start)

## プロジェクト構成

```
sample-concierge-agent/
├── amplify/                    # AWS Amplify バックエンド (Cognito, DynamoDB, GraphQL)
├── concierge_agent/           # エージェントコードと Docker コンテナ
│   ├── Dockerfile
│   └── code/                  # Python エージェント実装
├── infrastructure/            # エージェントデプロイ用 CDK インフラストラクチャ
├── documents/                 # ナレッジベースドキュメント
├── web-ui/                    # React フロントエンドアプリケーション
└── scripts/                   # デプロイとセットアップスクリプト
```

## ドキュメント

- **[デプロイガイド](DEPLOYMENT.md)** - 完全なデプロイ手順、前提条件、トラブルシューティング
- **[Visa ローカルセットアップ](docs/VISA_LOCAL_SETUP.md)** - 実際の Visa API テスト用セットアップ
- **[インフラストラクチャ README](infrastructure/README.md)** - CDK インフラストラクチャの詳細
- **[フロントエンドモックモード](FRONTEND_MOCK_MODE.md)** - バックエンドなしで UI をテスト
- **[Visa ドキュメント](visa-documentation/README.md)** - Visa API ドキュメント

## データフロー
![shopping data flow](docs/shopping_data_flow.png)

## アーキテクチャ
![shopping arch](docs/Shopping_Agent_VISA.png)

## デモ
![Shopping Agent Demo](docs/demo.gif)

## 設定

詳細な設定については以下を参照してください:
- API キー (SERP API, Visa API)
- Visa 決済連携 (モック vs 実際)
- ローカル開発セットアップ
- 環境変数
- クリーンアップ手順

**[デプロイガイド](DEPLOYMENT.md)** を参照してください。

> [!NOTE]
> このプロジェクトは教育目的のサンプル実装として提供されており、本番環境向けではありません。
> 組織のポリシーと AWS サービス規約への準拠を確認してください。
