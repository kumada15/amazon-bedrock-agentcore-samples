# Claude Agent SDK と Bedrock AgentCore の統合

| 情報                | 詳細                                                                         |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ  | ストリーミング付き非同期                                                     |
| エージェントフレームワーク | Claude Agent SDK                                                        |
| LLM モデル          | Anthropic Claude（Bedrock 経由）                                             |
| コンポーネント      | AgentCore Runtime                                                            |
| サンプルの複雑さ    | 簡単                                                                         |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK、Claude Agent SDK                         |

このサンプルでは、Claude Agent SDK を AWS Bedrock AgentCore と統合し、ストリーミングサポート付きの Claude 搭載エージェントをマネージドサービスとしてデプロイする方法を示します。`agentcore` CLI を使用してこのエージェントを設定およびローンチできます。

## 前提条件

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Bedrock AgentCore へのアクセス権を持つ AWS アカウント
- Node.js と npm（Claude Code CLI 用）

## セットアップ手順

### 1. uv で Python 環境を作成

```bash
# uv がまだインストールされていない場合はインストール

# 仮想環境を作成してアクティベート
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
```

### 2. 依存関係のインストール

```bash
uv pip install -r requirements.txt
```

### 3. エージェントコードの理解

`agent.py` ファイルには、Bedrock AgentCore と統合されたストリーミングサポート付きの Claude Agent SDK 実装が含まれています：

```python
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

async def basic_example(prompt):
    """ストリーミング付きの基本的なサンプル。"""
    async for message in query(prompt=prompt):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        yield message

@app.entrypoint
async def run_main(payload):
    """ストリーミングサポート付きのエージェント呼び出しハンドラー"""
    async for message in basic_example(payload["prompt"]):
        yield message

app.run()
```

エージェントは3つのモードをサポートしています：
- **モード 1**: 基本的なサンプル - シンプルな質問応答
- **モード 2**: カスタムオプション付き - カスタマイズされたシステムプロンプトと最大ターン数
- **モード 3**: ツール付き - ファイルの読み書き機能

### 4. Bedrock AgentCore Toolkit での設定とローンチ

```bash
# デプロイ用にエージェントを設定（メモリなし）
agentcore configure -e agent.py --disable-memory

# 環境変数付きでエージェントをデプロイ
agentcore launch --env CLAUDE_CODE_USE_BEDROCK=1 --env AWS_BEARER_TOKEN_BEDROCK=<your-token>
```

**注意**: Claude Agent SDK は `ANTHROPIC_API_KEY` または AWS Bedrock アクセスのいずれかを環境変数として設定する必要があります。このサンプルでは以下を使用します：
- `CLAUDE_CODE_USE_BEDROCK=1` で Bedrock 統合を有効化
- `AWS_BEARER_TOKEN_BEDROCK` で Bedrock との認証

これらの環境変数は Dockerfile で提供するか、上記のように `--env` オプションでインラインで提供できます。設定オプションの詳細については、[Claude Agent SDK ドキュメント](https://docs.claude.com/en/api/agent-sdk/overview#core-concepts)を参照してください。

### 5. エージェントのテスト

デプロイ後、以下を使用してエージェントをテストできます：

```bash
# 基本的なクエリ（モード 1）
agentcore invoke '{"prompt":"What is the capital of France?", "mode":1}'

# カスタムオプション付き（モード 2）
agentcore invoke '{"prompt":"Explain quantum computing", "mode":2}'

# ツール付き（モード 3）
agentcore invoke '{"prompt":"Read the contents of test.txt", "mode":3}'
```

## 主な機能

- **ストリーミングサポート**: より良いユーザー体験のためのリアルタイムレスポンスストリーミング
- **複数モード**: 異なるユースケース向けの3つの動作モード
- **ツール統合**: Read と Write ツールの組み込みサポート
- **Async/Await**: 最適なパフォーマンスのための完全な非同期処理
- **BedrockAgentCore 統合**: マネージド AWS サービスとしてのシームレスなデプロイ

## アーキテクチャ

エージェントはレイヤードアーキテクチャを使用します：
1. **Claude Agent SDK**: `query()` 関数を介して LLM インタラクションを処理
2. **サンプル関数**: メッセージを処理しストリーミング用に yield
3. **メイン関数**: モードパラメータに基づいてリクエストをルーティング
4. **BedrockAgentCoreApp**: ランタイム環境を提供しデプロイを処理

## カスタマイズ

以下の方法でエージェントをカスタマイズできます：
- `allowed_tools` リストにツールを追加
- `ClaudeAgentOptions` の `system_prompt` を変更
- 会話の長さのために `max_turns` を調整
- 追加のユースケース用に新しいサンプル関数を作成

## クリーンアップ

エージェントの使用が終わったら、デプロイされたリソースをクリーンアップできます。

### メモリ
このサンプルは `--disable-memory` で設定されているため、メモリリソースは作成されていません。メモリに関して削除するものはありません。

### エージェントランタイム
エージェントと関連するすべての AWS リソースを破棄するには、`agentcore destroy` コマンドを使用します：

```bash
agentcore destroy
```

以下のような出力が表示されます：

```
⚠️  About to destroy resources for agent 'claudesdkagent'

Current deployment:
  • Agent ARN: arn:aws:bedrock-agentcore:us-east-1:XXXXXXXXXXXX:runtime/claudesdkagent-XXXXXXXXXX
  • Agent ID: claudesdkagent-XXXXXXXXXX
  • ECR Repository: XXXXXXXXXXXX.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-claudesdkagent
  • Execution Role: arn:aws:iam::XXXXXXXXXXXX:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-XXXXXXXXXX

This will permanently delete AWS resources and cannot be undone!
エージェント 'claudesdkagent' とそのすべてのリソースを削除してもよろしいですか？ [y/N]:
```

`y` と入力して確認すると、ECR リポジトリと実行ロールを含むエージェントとすべての関連リソースが完全に削除されます。
