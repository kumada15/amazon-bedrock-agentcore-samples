# Strands Agent と Bedrock AgentCore の統合

| 項目         | 詳細                                                                      |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ          | 同期型                                                                 |
| エージェントフレームワーク   | Strands                                                                    |
| LLM モデル           | Anthropic Claude 3 Haiku                                                     |
| コンポーネント          | AgentCore Runtime                                |
| サンプルの複雑さ  | 簡単                                                                 |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK                                           |

これらの例では、Strands エージェントを AWS Bedrock AgentCore と統合し、エージェントをマネージドサービスとしてデプロイする方法を示しています。`agentcore` CLI を使用してこれらのエージェントを設定および起動できます。

## 前提条件

- Python 3.10 以上
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Bedrock AgentCore へのアクセス権を持つ AWS アカウント

## セットアップ手順

### 1. uv で Python 環境を作成する

```bash
# まだインストールしていない場合は uv をインストール

# 仮想環境を作成してアクティベート
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
```

### 2. 必要なパッケージをインストール

```bash
uv pip install -r requirements.txt
```

### 3. API キープロバイダーの設定（OpenAI + strands の例の場合）

Strands エージェントで OpenAI モデルを使用する場合は、API キープロバイダーを設定する必要があります：

```python
from bedrock_agentcore.services.identity import IdentityClient
from boto3.session import Session
import boto3

boto_session = Session()
region = boto_session.region_name

# API キープロバイダーを設定
identity_client = IdentityClient(region=region)
api_key_provider = identity_client.create_api_key_credential_provider({
    "name": "openai-apikey-provider",
    "apiKey": "sk-..." # OpenAI から取得した API キーに置き換えてください
})
print(api_key_provider)
```

### 4. エージェントコードの理解

`strands_agent_file_system.py` ファイルには、ファイルシステム機能を備えたシンプルな Strands エージェントが含まれており、Bedrock AgentCore と統合されています：

```python
import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from strands import Agent
from strands_tools import file_read, file_write, editor

# ファイルシステムツールを持つ Strands エージェントを初期化
agent = Agent(tools=[file_read, file_write, editor])

# Bedrock AgentCore と統合
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    """エージェント呼び出しのハンドラー"""
    user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    result = agent(user_message)
    return {"result": result.message}

app.run()
```

### 5. Bedrock AgentCore Toolkit での設定と起動

```bash
# デプロイ用にエージェントを設定
agentcore configure -e strands_agent_file_system.py

# エージェントを起動
agentcore launch
```

### 6. エージェントのテスト

デプロイ後、以下を使用してエージェントをテストできます：

```bash
agentcore invoke '{"prompt":"hello"}'
```
