# 設定

このドキュメントでは、SRE エージェントシステムで使用されるすべての設定ファイルの包括的な概要を提供します。設定ファイルは、目的とスコープに基づいて異なるディレクトリに整理されています。

## 設定ファイルの概要

| ファイルパス | タイプ | 目的 | 手動編集が必要？ | 自動生成？ |
|-----------|------|---------|----------------------|-----------------|
| `sre_agent/.env` | ENV | SRE エージェント固有の設定 | はい | はい（GATEWAY_ACCESS_TOKEN は[セットアップ](../README.md#use-case-setup)により） |
| `gateway/.env` | ENV | ゲートウェイ認証設定 | はい | いいえ |
| `gateway/config.yaml` | YAML | AgentCore Gateway の設定 | はい | 部分的（provider_arn は[セットアップ](../README.md#use-case-setup)により） |
| `deployment/.env` | ENV | `sre_agent/.env` へのソフトリンク | いいえ（sre_agent/.env を使用） | N/A（シンボリックリンク） |
| `deployment/.cognito_config` | ENV | Cognito 設定の詳細 | いいえ | はい（[setup_cognito.sh](../deployment/setup_cognito.sh) により） |
| `sre_agent/config/agent_config.yaml` | YAML | エージェントからツールへのマッピング設定 | いいえ | はい（gateway URI は[セットアップ](../README.md#use-case-setup)により） |
| `scripts/user_config.yaml` | YAML | スクリプト固有のユーザー設定 | いいえ | いいえ |
| `backend/openapi_specs/*.yaml` | YAML | ツール用の OpenAPI 仕様 | いいえ | はい（テンプレートから[セットアップ](../README.md#use-case-setup)により） |

### セットアップ手順

`.example` バージョンがあるファイルについて：
1. `.example` ファイルをコピーして実際の設定ファイルを作成
2. コピーしたファイルを環境固有の値で編集
3. 実際の設定ファイルは決してバージョン管理にコミットしない

```bash
# セットアップコマンドの例
cp sre_agent/.env.example sre_agent/.env
cp gateway/.env.example gateway/.env
cp gateway/config.yaml.example gateway/config.yaml
```

### セットアップ中に自動更新されるファイル

以下のファイルはセットアップスクリプトによって自動的に変更されます：

1. **`sre_agent/.env`** - `GATEWAY_ACCESS_TOKEN` が自動的に追加される
2. **`sre_agent/config/agent_config.yaml`** - `gateway.uri` フィールドが作成されたゲートウェイ URI で更新される
3. **`gateway/config.yaml`** - クレデンシャルプロバイダー作成時に `provider_arn` フィールドが更新される
4. **`backend/openapi_specs/*.yaml`** - テンプレートからバックエンドドメインを使用して生成される
5. **`deployment/.cognito_config`** - `setup_cognito.sh` により USER_POOL_ID、CLIENT_ID、CLIENT_SECRET、その他の Cognito 設定で作成される

## 環境変数

SRE エージェントは機密設定値に環境変数を使用します。`sre_agent/` ディレクトリに以下の必須変数を含む `.env` ファイルを作成します：

```bash
# 必須: Claude モデルアクセス用の API キー
# Anthropic 直接アクセスの場合:
ANTHROPIC_API_KEY=sk-ant-api-key-here

# Amazon Bedrock アクセスの場合:
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=your-profile-name  # または AWS_ACCESS_KEY_ID と AWS_SECRET_ACCESS_KEY を使用

# 必須: AgentCore Gateway 認証
GATEWAY_ACCESS_TOKEN=your-gateway-token-here  # ゲートウェイセットアップで生成

# オプション: デバッグとロギング
LOG_LEVEL=INFO  # オプション: DEBUG, INFO, WARNING, ERROR
DEBUG=false     # 詳細出力のためのデバッグモードを有効化
```

**注意**: SRE エージェントはプロジェクトルートではなく、`sre_agent/` ディレクトリ内の `.env` ファイルを探します。これにより、モジュラーな設定管理が可能になります。

## エージェント設定

エージェントの動作は `sre_agent/config/agent_config.yaml` を通じて設定されます。このファイルは、エージェントと利用可能なツールのマッピング、および LLM パラメータを定義します：

```yaml
# エージェントからツールへのマッピング
agents:
  kubernetes_agent:
    name: "Kubernetes Infrastructure Agent"
    description: "Specializes in Kubernetes operations and troubleshooting"
    tools:
      - get_pod_status
      - get_deployment_status
      - get_cluster_events
      - get_resource_usage
      - get_node_status

  logs_agent:
    name: "Application Logs Agent"
    description: "Expert in log analysis and pattern detection"
    tools:
      - search_logs
      - get_error_logs
      - analyze_log_patterns
      - get_recent_logs
      - count_log_events

  metrics_agent:
    name: "Performance Metrics Agent"
    description: "Analyzes performance metrics and trends"
    tools:
      - get_performance_metrics
      - get_error_rates
      - get_resource_metrics
      - get_availability_metrics
      - analyze_trends

  runbooks_agent:
    name: "Operational Runbooks Agent"
    description: "Provides operational procedures and guides"
    tools:
      - search_runbooks
      - get_incident_playbook
      - get_troubleshooting_guide
      - get_escalation_procedures
      - get_common_resolutions

# すべてのエージェントで利用可能なグローバルツール
global_tools:
  - x-amz-bedrock-agentcore-search  # AgentCore 検索ツール

# ゲートウェイ設定
gateway:
  uri: "https://your-gateway-url.com"  # セットアップ中に更新
```

## ゲートウェイ環境変数

AgentCore Gateway には認証用の追加の環境変数が必要です。`gateway/` ディレクトリに以下を含む `.env` ファイルを作成します：

```bash
# 必須: クレデンシャルプロバイダー認証用のバックエンド API キー
BACKEND_API_KEY=your-backend-api-key-here

# オプション: 環境変数で config.yaml の値を上書き
# ACCOUNT_ID=123456789012
# REGION=us-east-1
# ROLE_NAME=your-role-name
# GATEWAY_NAME=MyAgentCoreGateway
# CREDENTIAL_PROVIDER_NAME=sre-agent-api-key-credential-provider
```

**注意**: `BACKEND_API_KEY` は `create_gateway.sh` スクリプトがクレデンシャルプロバイダーサービスと認証するために使用されます。

## ゲートウェイ設定

AgentCore Gateway は `gateway/config.yaml` を通じて設定されます。この設定はセットアップスクリプトによって管理されますが、カスタマイズ可能です：

```yaml
# AgentCore Gateway 設定テンプレート
# このファイルを config.yaml にコピーし、環境固有の設定で更新

# AWS 設定
account_id: "YOUR_ACCOUNT_ID"
region: "us-east-1"
role_name: "YOUR_ROLE_NAME"
endpoint_url: "https://bedrock-agentcore-control.us-east-1.amazonaws.com"
credential_provider_endpoint_url: "https://bedrock-agentcore-control.us-east-1.amazonaws.com"

# Cognito 設定
user_pool_id: "YOUR_USER_POOL_ID"
client_id: "YOUR_CLIENT_ID"

# S3 設定
# オプション 1: 自動作成（推奨）
# s3_bucket を空または未指定のままにすると、create_gateway.sh が自動的に
# sreagent-{uuid} の形式でバケットを作成します
s3_bucket: ""  # 自動作成の場合は空のまま

# オプション 2: 手動バケット
# 自分でバケットを管理したい場合は、以下のコメントを解除して独自のバケット名を指定
# s3_bucket: "your-custom-bucket-name"

s3_path_prefix: "devops-multiagent-demo"  # OpenAPI スキーマファイルのパスプレフィックス

# プロバイダー設定
# この ARN は create_gateway.sh が create_credentials_provider.py を実行する際に自動的に生成
provider_arn: "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:token-vault/default/apikeycredentialprovider/YOUR_PROVIDER_NAME"

# ゲートウェイ設定
gateway_name: "MyAgentCoreGateway"
gateway_description: "AgentCore Gateway for API Integration"

# ターゲット設定
target_description: "S3 target for OpenAPI schema"
```

## 設定ファイルの詳細

### SRE エージェント `.env` ファイル
- **場所**: `sre_agent/.env`
- **目的**: デプロイメント設定とは別のエージェント固有の設定
- **セットアップ**: `sre_agent/.env.example` からコピーしてカスタマイズ
- **自動更新**: セットアップスクリプトが自動的に `GATEWAY_ACCESS_TOKEN` をこのファイルに追加
- **注意**: エージェントは特に `sre_agent/` ディレクトリ内のこのファイルを探す

### ゲートウェイ `.env` ファイル
- **場所**: `gateway/.env`
- **目的**: ゲートウェイ認証とバックエンド API 設定
- **セットアップ**: `gateway/.env.example` からコピーしてカスタマイズ
- **主要変数**: クレデンシャルプロバイダー認証用のバックエンド API キー

### デプロイメント `.env` ファイル
- **場所**: `deployment/.env`
- **目的**: `sre_agent/.env` へのシンボリックリンク
- **セットアップ**: 手動セットアップ不要 - これはソフトリンク
- **注意**: このシンボリックリンクにより、デプロイメントスクリプトがエージェントと同じ環境変数を使用することを保証

### ゲートウェイ設定 (`config.yaml`)
- **場所**: `gateway/config.yaml`
- **目的**: AWS、Cognito、S3 設定を含む AgentCore Gateway の設定
- **セットアップ**: `config.yaml.example` からコピーしてカスタマイズ
- **自動更新**: `create_gateway.sh` スクリプトが `provider_arn` などの特定のフィールドを自動的に更新

### エージェント設定 (`agent_config.yaml`)
- **場所**: `sre_agent/config/agent_config.yaml`
- **目的**: エージェントからツールへのマッピングとエージェント機能を定義
- **セットアップ**: 直接編集（サンプルファイルなし）
- **自動更新**: セットアップスクリプトが作成されたゲートウェイ URI で `gateway.uri` フィールドを自動的に更新
- **内容**: エージェント定義、ツール割り当て、グローバルツール設定

### ユーザー設定ファイル
- **場所**: `scripts/user_config.yaml`
- **目的**: メモリ強化パーソナライズのためのユーザーペルソナと好み
- **セットアップ**: 直接編集してユーザーペルソナを追加または変更
- **内容**: 事前定義されたユーザー好み（Alice: 技術者、Carol: エグゼクティブ）

### S3 バケット設定
- **場所**: `gateway/config.yaml` の `s3_bucket` パラメータで指定
- **目的**: ゲートウェイで使用される OpenAPI 仕様ファイルのストレージ
- **自動作成**:
  - config で `s3_bucket` が空または未指定の場合、`create_gateway.sh` スクリプトが自動的にバケットを作成
  - 自動作成されるバケットの命名形式: `sreagent-{uuid}`（例: `sreagent-550e8400-e29b-41d4-a716-446655440000`）
  - この形式は AWS S3 バケット命名制限に準拠
- **手動バケット**: 自分でバケットを作成および管理したい場合は、`gateway/config.yaml` に独自のバケット名を指定することも可能
- **注意**: S3 バケット作成権限（`s3:CreateBucket`、`s3:PutObject`）を持つ AWS 認証情報が必要

### OpenAPI 仕様
- **場所**: `backend/openapi_specs/*.yaml`
- **目的**: 各種バックエンドサービスの API コントラクトを定義
- **ファイル**:
  - `k8s_api.yaml` - Kubernetes 操作 API
  - `logs_api.yaml` - ログ分析 API
  - `metrics_api.yaml` - メトリクス収集 API
  - `runbooks_api.yaml` - ランブック管理 API
- **自動生成**: これらのファイルは `generate_specs.sh` 実行時にセットアップ中にテンプレートから生成
- **注意**: これらを直接編集しないでください - 代わりにテンプレートを変更
