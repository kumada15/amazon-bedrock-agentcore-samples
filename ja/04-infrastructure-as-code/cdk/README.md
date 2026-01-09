# CDK サンプル

AWS CDK (Python) を使用して Amazon Bedrock AgentCore リソースをデプロイします。

## 前提条件

- Python 3.8+
- AWS CDK v2.218.0 以降 (BedrockAgentCore サポート用)
- AWS CLI の設定済み
- Amazon Bedrock AgentCore へのアクセス (プレビュー)

```bash
npm install -g aws-cdk
```

## 一般的なデプロイパターン

```bash
cd <sample-directory>
pip install -r requirements.txt
cdk deploy
```

## サンプル

- **[basic-runtime/](./basic-runtime/)** - シンプルなエージェントのデプロイ
- **[multi-agent-runtime/](./multi-agent-runtime/)** - マルチエージェントシステム
- **[mcp-server-agentcore-runtime/](./mcp-server-agentcore-runtime/)** - JWT 認証付き MCP Server
- **[end-to-end-weather-agent/](./end-to-end-weather-agent/)** - ツールとメモリを備えた天気エージェント

## CDK の利点

- コンテナビルドに `DockerImageAsset` を使用 (CodeBuild 不要)
- よりクリーンなコンストラクト分離と再利用性
- 型安全性と IDE サポート
- より高速なデプロイ時間
