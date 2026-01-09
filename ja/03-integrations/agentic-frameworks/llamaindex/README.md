# LlamaIndex エージェントと Bedrock AgentCore の統合

| 情報                | 詳細                                                                         |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ  | 同期                                                                         |
| エージェントフレームワーク | LlamaIndex                                                              |
| LLM モデル          | OpenAI GPT-4o-mini                                                           |
| コンポーネント      | AgentCore Runtime、Yahoo Finance Tools                                       |
| サンプルの複雑さ    | 簡単                                                                         |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK                                           |

このサンプルでは、LlamaIndex エージェントを AWS Bedrock AgentCore と統合し、ツール使用機能を持つ金融アシスタントをマネージドサービスとしてデプロイする方法を示します。

## 前提条件

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Bedrock へのアクセス権を持つ AWS アカウント
- OpenAI API キー（モデルクライアント用）

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

`llama_agent_hello_world.py` ファイルには、金融ツールと基本的な計算機能を持つ LlamaIndex エージェントが含まれており、Bedrock AgentCore と統合されています：

```python
import asyncio
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.yahoo_finance import YahooFinanceToolSpec

# カスタム関数ツールを定義
def multiply(a: float, b: float) -> float:
    """2つの数値を掛け算して積を返します"""
    return a * b

def add(a: float, b: float) -> float:
    """2つの数値を足し算して和を返します"""
    return a + b

# 他の定義済みツールを追加
finance_tools = YahooFinanceToolSpec().to_tool_list()
finance_tools.extend([multiply, add])

# ツールを持つエージェントワークフローを作成
agent = FunctionAgent(
    tools=finance_tools,
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="You are a helpful assistant.",
)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def main(payload):
    # エージェントを実行
    response = await agent.run(payload.get("prompt","What is the current stock price of AMZN?"))
    print(response)
    return response.response.content

# エージェントを実行
if __name__ == "__main__":
    app.run()
```

### 4. Bedrock AgentCore Toolkit での設定とローンチ

```bash
# デプロイ用にエージェントを設定
agentcore configure -e llama_agent_hello_world.py

# OpenAI API キーを使用してエージェントをデプロイ
agentcore launch --env OPENAI_API_KEY=sk-...
```

### 5. エージェントのテスト

クラウドにデプロイする前にローカルでエージェントをテストできます：

```bash
# OpenAI API キーを使用してローカルでローンチ
agentcore launch -l --env OPENAI_API_KEY=sk-...

# クエリでエージェントを呼び出し
agentcore invoke -l '{"prompt":"Price of AMZN stock today"}'
```

クラウドデプロイの場合は `-l` フラグを削除します：

```bash
# クラウドにデプロイ
agentcore launch --env OPENAI_API_KEY=sk-...

# デプロイされたエージェントを呼び出し
agentcore invoke '{"prompt":"Price of AMZN stock today"}'
```

エージェントは以下を実行します：
1. 金融クエリを処理
2. Yahoo Finance ツールを使用してリアルタイムの株式データを取得
3. 要求された金融情報を含むレスポンスを提供
4. 必要に応じて計算ツールを使用して計算を実行

## 動作の仕組み

このエージェントは LlamaIndex のエージェントフレームワークを使用して、以下が可能な金融アシスタントを作成します：

1. 株式や金融データに関する自然言語クエリの処理
2. Yahoo Finance ツールを通じたリアルタイム株式情報へのアクセス
3. 必要に応じて基本的な数学演算の実行
4. データに基づいた包括的なレスポンスの提供

エージェントは Bedrock AgentCore フレームワークでラップされており、以下を処理します：
- AWS へのデプロイ
- スケーリングと管理
- リクエスト/レスポンスの処理
- 環境変数の管理

## その他のリソース

- [LlamaIndex ドキュメント](https://docs.llamaindex.ai/en/stable/use_cases/agents/)
- [Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)
- [OpenAI API ドキュメント](https://platform.openai.com/docs/api-reference)
- [Yahoo Finance API ドキュメント](https://pypi.org/project/yfinance/)
