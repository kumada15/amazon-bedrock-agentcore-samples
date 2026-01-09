# Microsoft Entra ID と Amazon Bedrock AgentCore の統合

このリポジトリには、様々な認証および認可シナリオにおいて Microsoft Entra ID（旧 Azure Active Directory）を Amazon Bedrock AgentCore と統合する方法を示す 3 つの包括的なノートブックが含まれています。

## Microsoft Entra ID とは？

Microsoft Entra ID は、Microsoft 365、Azure、およびその他の SaaS アプリケーションの中央 ID プロバイダーとして機能する、Microsoft のクラウドベースの ID およびアクセス管理サービスです。

### 主な機能:
- **シングルサインオン (SSO)** - ユーザーは一度認証すると複数のアプリケーションにアクセス可能
- **多要素認証 (MFA)** - 追加の検証方法によるセキュリティ強化
- **条件付きアクセス** - ユーザー、デバイス、場所、リスクに基づくポリシーベースのアクセス制御
- **アプリケーション統合** - OAuth 2.0、OpenID Connect、SAML などの最新認証プロトコルをサポート

### AgentCore との統合


Microsoft Entra ID は、AgentCore Identity と共に ID プロバイダーとして使用でき、以下が可能です：
- エージェントを呼び出す前にユーザーを認証（インバウンド認証）
- ユーザーに代わって保護されたリソースにアクセスするようエージェントを認可（アウトバウンド認証）
- JWT ベースの認可で AgentCore Gateway エンドポイントを保護

## サンプルノートブックの概要

このラーニングパスには、異なる統合パターンを示す 3 つの実践的なノートブックが含まれています：

### 1. Step By Step MS EntraID and 3LO Outbound for Tools.ipynb

**目的**: AgentCore Runtime にデプロイされたエージェントが認証済みユーザーに代わって外部リソース（Microsoft OneNote）にアクセスする **アウトバウンド認証** に Entra ID を使用する方法を示します。

**学習内容**:
- Entra ID テナントとアプリケーション登録のセットアップ
- AgentCore OAuth2 資格情報プロバイダーの作成
- ユーザー委任のための 3-legged OAuth (3LO) フローの実装
- OneNote ノートブックを作成および管理するためのエージェント構築と AgentCore Runtime へのデプロイ

**主要な統合パターン**:
- ユーザーが Entra ID で認証
- AgentCore Runtime が OneNote API にアクセスするための委任された権限を受け取る
- AgentCore Runtime エージェントツールがユーザーに代わってアクションを実行


**作成されるツール**:
- `create_notebook` - 新しい OneNote ノートブックを作成
- `create_notebook_section` - ノートブックにセクションを追加
- `add_content_to_notebook_section` - コンテンツを含むページを作成

### 2. Step by Step Entra ID for Inbound Auth.ipynb

**目的**: AgentCore Runtime エージェントエンドポイントを保護するための **インバウンド認証** に Entra ID を使用し、認証されたユーザーのみがエージェントを呼び出せるようにする方法を示します。

**学習内容**:
- Entra ID によるカスタム JWT 認可の設定
- デバイスコードフローのための MSAL（Microsoft Authentication Library）の使用
- ベアラートークンによる AgentCore Runtime エンドポイントの保護
- 認証されたユーザーとのセッションベースの会話管理

**主要な統合パターン**:
- ユーザーは AgentCore Runtime エージェントエンドポイントにアクセスする前に Entra ID で認証が必要
- ベアラートークンが各リクエストでユーザー ID を検証
- エージェントは認証レイヤーの背後で保護されたまま


### 3. Step by Step Entra ID with AgentCore Gateway.ipynb

**目的**: クライアント資格情報フローを使用したマシン間 (M2M) 認証で **AgentCore Gateway** エンドポイントを保護するために Entra ID を使用する方法を示します。

**学習内容**:
- API 保護のための Entra ID アプリロールのセットアップ
- カスタム JWT 認可による AgentCore Gateway の設定
- MCP（Model Context Protocol）ツールとしての Lambda 関数の作成
- サービス間認証のためのクライアント資格情報フローの使用

**主要な統合パターン**:
- アプリケーションはクライアント資格情報を使用して認証（ユーザーインタラクションなし）
- Gateway が Entra ID に対して JWT トークンを検証
- Lambda 関数が標準化された MCP ツールとして公開



## サポートとドキュメント

- [Microsoft Entra ID ドキュメント](https://learn.microsoft.com/en-us/entra/)
- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)
- [OAuth 2.0 仕様](https://oauth.net/2/)

## 注記

Microsoft Entra ID は AWS サービスではありません。Entra ID の使用に関するコストとライセンスについては、Microsoft Entra ID のドキュメントを参照してください。
