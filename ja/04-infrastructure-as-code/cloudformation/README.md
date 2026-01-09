# CloudFormation サンプル

CloudFormation テンプレートを使用して Amazon Bedrock AgentCore リソースをデプロイします。

## 前提条件

- AWS CLI のインストールと設定済み
- スタックとリソースを作成するための CloudFormation 権限
- Amazon Bedrock AgentCore へのアクセス (プレビュー)

## 一般的なデプロイパターン

```bash
# デプロイ
aws cloudformation create-stack \
  --stack-name <stack-name> \
  --template-body file://<template-file> \
  --capabilities CAPABILITY_IAM \
  --region <region>

# 監視
aws cloudformation describe-stacks \
  --stack-name <stack-name> \
  --region <region>

# クリーンアップ
aws cloudformation delete-stack \
  --stack-name <stack-name> \
  --region <region>
```

## サンプル

- **[mcp-server-agentcore-runtime/](./mcp-server-agentcore-runtime/)** - JWT 認証付き MCP Server
- **[basic-runtime/](./basic-runtime/)** - シンプルなエージェントのデプロイ
- **[multi-agent-runtime/](./multi-agent-runtime/)** - マルチエージェントシステム
- **[end-to-end-weather-agent/](./end-to-end-weather-agent/)** - ツールとメモリを備えた天気エージェント

## トラブルシューティング

### スタック作成の失敗
```bash
aws cloudformation describe-stack-events \
  --stack-name <stack-name> \
  --region <region>
```

### CodeBuild の失敗
```bash
aws codebuild batch-get-builds \
  --ids <build-id> \
  --region <region>
```
