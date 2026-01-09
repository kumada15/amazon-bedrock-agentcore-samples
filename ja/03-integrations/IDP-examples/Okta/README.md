# Okta と Amazon Bedrock AgentCore の統合

このリポジトリには、様々な認証および認可シナリオにおいて Okta を Amazon Bedrock AgentCore と統合する方法を示す包括的なノートブックが含まれています。

## Okta とは？

Okta は、企業向けに安全な ID ソリューションを提供するクラウドベースの ID およびアクセス管理サービスで、アプリケーションやサービス間でのシームレスな認証と認可を可能にします。

### 主な機能:
- **シングルサインオン (SSO)** - ユーザーは一度認証すると複数のアプリケーションにアクセス可能
- **多要素認証 (MFA)** - 追加の検証方法によるセキュリティ強化
- **アダプティブ認証** - ユーザーの行動とコンテキストに基づくリスクベースの認証ポリシー
- **ユニバーサルディレクトリ** - 一元化されたユーザー管理とプロファイル同期
- **API アクセス管理** - API セキュリティのための OAuth 2.0 と OpenID Connect のサポート

### AgentCore との統合

Okta は、AgentCore Identity と共に ID プロバイダーとして使用でき、以下が可能です：
- エージェントを呼び出す前にユーザーを認証（インバウンド認証）
- ユーザーに代わって保護されたリソースにアクセスするようエージェントを認可（アウトバウンド認証）
- JWT ベースの認可で AgentCore Gateway エンドポイントを保護

## サンプルノートブックの概要

このラーニングパスには、異なる統合パターンを示す実践的なノートブックが含まれています：

### 1. Step by Step Okta for Inbound Auth.ipynb

**目的**: AgentCore Runtime エージェントエンドポイントを保護するための **インバウンド認証** に Okta を使用し、認証されたユーザーのみがエージェントを呼び出せるようにする方法を示します。

**学習内容**:
- Okta テナントとアプリケーション設定のセットアップ
- AgentCore OAuth2 資格情報プロバイダーの作成
- ユーザー認証と委任のための OAuth 2.0 フローの実装
- Okta 統合による AgentCore Runtime へのエージェント構築とデプロイ
- ユーザーセッションの管理

**主要な統合パターン**:
- ユーザーは AgentCore Runtime エージェントエンドポイントにアクセスする前に Okta で認証が必要
- ベアラートークンが各リクエストでユーザー ID を検証
- エージェントは認証レイヤーの背後で保護されたまま

## サポートとドキュメント

- [Okta 開発者ドキュメント](https://developer.okta.com/)
- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)
- [OAuth 2.0 と OpenID Connect](https://developer.okta.com/docs/concepts/oauth-openid/)

## 注記

Okta は AWS サービスではありません。Okta の使用に関するコストとライセンスについては、Okta のドキュメントを参照してください。
