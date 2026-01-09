# ADK エージェントと Bedrock AgentCore の統合

| 情報                | 詳細                                                                         |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ  | 同期                                                                         |
| エージェントフレームワーク | Google ADK                                                              |
| LLM モデル          | Gemini 2.0 Flash                                                             |
| コンポーネント      | AgentCore Runtime                                                            |
| サンプルの複雑さ    | 簡単                                                                         |
| 使用 SDK            | Amazon Bedrock AgentCore Python SDK                                          |

このサンプルでは、Google ADK エージェントを Amazon Bedrock AgentCore と統合し、検索機能を持つエージェントをマネージドサービスとしてデプロイする方法を示します。

## 前提条件

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Bedrock へのアクセス権を持つ AWS アカウント
- Google AI API キー（Gemini モデル用）

## セットアップ手順

### 1. uv で Python 環境を作成

```bash
# uv がまだインストールされていない場合はインストール
pip install uv

# 仮想環境を作成してアクティベート
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
```

### 2. 依存関係のインストール

```bash
uv pip install -r requirements.txt
```

### 3. エージェントコードの理解

`adk_agent_google_search.py` ファイルには、Google 検索機能を持つ Google ADK エージェントが含まれており、Bedrock AgentCore と統合されています：


```python
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types
import asyncio

# エージェント定義
root_agent = Agent(
    model="gemini-2.0-flash",
    name="openai_agent",
    description="Agent to answer questions using Google Search.",
    instruction="I can answer your questions by searching the internet. Just ask me anything!",
    # google_search はエージェントが Google 検索を実行できる組み込みツールです。
    tools=[google_search]
)

# セッションとランナー
async def setup_session_and_runner(user_id, session_id):
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    return session, runner

# エージェントとのインタラクション
async def call_agent_async(query, user_id, session_id):
    content = types.Content(role='user', parts=[types.Part(text=query)])
    session, runner = await setup_session_and_runner(user_id, session_id)
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=content)

    async for event in events:
        if event.is_final_response():
            final_response = event.content.parts[0].text
            print("Agent Response: ", final_response)

    return final_response

# Bedrock AgentCore との統合
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    return asyncio.run(call_agent_async(
        payload.get("prompt", "what is Bedrock Agentcore Runtime?"),
        payload.get("user_id", "user1234"),
        context.session_id
    ))

app.run()
```

### 4. Bedrock AgentCore Toolkit での設定とローンチ

```bash
# デプロイ用にエージェントを設定
agentcore configure -e adk_agent_google_search.py


# Gemini API キーを使用してエージェントをデプロイ
agentcore launch --env GEMINI_API_KEY=your_api_key_here
```

### 5. エージェントのローカルテスト

ローカルでテストするためにローンチ：
```bash
agentcore launch -l --env GEMINI_API_KEY=your_api_key_here
```

次にエージェントを呼び出し：
```bash
agentcore invoke -l '{"prompt": "What is Amazon Bedrock Agentcore Runtime?"}'
```

エージェントは以下を実行します：
1. クエリを処理
2. Google 検索を使用して関連情報を検索
3. 検索結果に基づいた包括的な回答を提供

> 注意：クラウドでローンチおよび呼び出しを行うには `-l` フラグを削除してください

## 動作の仕組み

このエージェントは Google の ADK（Agent Development Kit）フレームワークを使用して、以下が可能なアシスタントを作成します：

1. 自然言語クエリの処理
2. 関連情報を見つけるための Google 検索の実行
3. 検索結果を一貫した回答に統合
4. インタラクション間のセッション状態の維持

エージェントは Bedrock AgentCore フレームワークでラップされており、以下を処理します：
- AWS へのデプロイ
- スケーリングと管理
- リクエスト/レスポンスの処理
- 環境変数の管理

## その他のリソース

- [Google ADK ドキュメント]([https://github.com/google/adk](https://google.github.io/adk-docs/))
- [Gemini API ドキュメント](https://ai.google.dev/docs)
- [Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)
