# Amazon Bedrock AgentCore での TypeScript MCP サーバー

## 概要

このチュートリアルでは、Amazon Bedrock AgentCore ランタイム環境を使用して TypeScript ベースの MCP（Model Context Protocol）サーバーをホストする方法を示します。


### チュートリアル詳細

| 情報                | 詳細                                                      |
|:--------------------|:----------------------------------------------------------|
| チュートリアルタイプ | TypeScript MCP サーバーのホスティング                      |
| ツールタイプ        | MCP サーバー                                               |
| チュートリアル構成   | AgentCore Runtime での TypeScript MCP サーバーのホスティング |
| チュートリアル分野   | クロスバーティカル                                         |
| 例の複雑さ          | 簡単                                                       |
| 使用 SDK            | Anthropic の MCP 用 TypeScript SDK                         |

## 前提条件

- Node.js v22 以降
- Docker（コンテナ化用）
- Amazon ECR（Docker イメージの保存用 Elastic Container Registry）
- Bedrock AgentCore へのアクセスを持つ AWS アカウント

---

## AgentCore Runtime サービスコントラクト

[公式サービスコントラクトドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html)を参照してください。

**ランタイム設定：**
- **ホスト：** `0.0.0.0`
- **ポート：** `8000`
- **トランスポート：** ステートレス `streamable-http`
- **エンドポイントパス：** `POST /mcp`

## ローカル開発

1. 依存関係をインストール

```
npm install
```

2. AWS 認証情報を設定
```
aws configure
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
```

3. サーバーを起動
```
npm run start
```

4. [MCP inspector](https://github.com/modelcontextprotocol/inspector) を使用してローカルでテスト

```
npx @modelcontextprotocol/inspector
```

## Docker デプロイメント

1. ECR リポジトリを作成
```
aws ecr create-repository --repository-name mcp-server --region us-east-1
```
2. イメージをビルドして ECR にプッシュ
```
# ログイントークンを取得
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin [account-id].dkr.ecr.us-east-1.amazonaws.com

docker buildx --platform linux/arm64 \
  -t [account-id].dkr.ecr.us-east-1.amazonaws.com/mcp-server:latest --push .
```

3. Bedrock AgentCore にデプロイ

    - AWS コンソール → Bedrock → AgentCore → エージェント作成に移動
    - プロトコルとして MCP を選択
    - エージェントランタイムを設定：
        - イメージ URI：[account-id].dkr.ecr.us-east-1.amazonaws.com/mcp-server:latest
        - Bedrock モデルアクセス用の IAM 権限を設定
        - エージェントサンドボックスでデプロイしてテスト


4. エンコードされた ARN MCP URL を構築

```
echo "agent_arn" | sed 's/:/%3A/g; s/\//%2F/g'
```

```
https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT
```

5. [MCP inspector](https://github.com/modelcontextprotocol/inspector) で MCP URL を使用

## 参考資料
- https://aws.amazon.com/bedrock/agentcore/
- https://github.com/modelcontextprotocol/typescript-sdk
- https://github.com/modelcontextprotocol/inspector


