# Claude Agent を使用した Code Interpreter でのコード実行

このプロジェクトでは、[AWS Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/) にデプロイされた [Claude agent](https://docs.claude.com/en/api/agent-sdk/overview) が [Code Interpreter](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html) セッションを作成してコードを安全に実行する方法を示します。

ユーザープロンプトを解釈し、Code Interpreter セッションを作成し、Code Interpreter 環境内で bash およびコード実行操作を呼び出し、レスポンスを返す Claude Agent を構築することでこれを実演します。

![architecture](./images/deploy.png)
![architecture](./images/invoke.png)

## 概要

プロジェクトには以下が含まれます：
- Claude を使用してコード実行をオーケストレーションするエージェント
- Code Interpreter ツールをラップする MCP サーバー
- boto3 SDK を使用して Code Interpreter API を呼び出すクライアント
- AgentCore デプロイ用の Docker コンテナ化

## 前提条件

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Docker（コンテナ化用）
- Bedrock AgentCore 権限を持つ AWS アカウントアクセス
- Amazon Bedrock コンソールから Claude モデルへのアクセスを有効化
- Claude Code CLI は Claude Agent SDK が動作するための依存関係です。Node.js と npm を介してインストールされます。

## セットアップ

### 1. uv のインストール（未インストールの場合）
``` bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# または pip 経由
pip install uv
```

### 2. 仮想環境のセットアップ
```bash
# 仮想環境を作成してアクティベート。pyproject.toml は提供されています。
uv sync
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
```

### 2. AgentCore Starter Toolkit を使用して AgentCore にデプロイ
```bash
# デプロイ用にエージェントを設定
agentcore configure --entrypoint agent.py --name claude_ci_agent --disable-memory
```

設定セットアップ中に、2 - Container デプロイメントタイプを選択

デプロイメントタイプを選択：
  1. Direct Code Deploy（推奨）- Python のみ、Docker 不要
  2. Container - カスタムランタイムまたは複雑な依存関係用


# エージェントをローンチ
```
agentcore launch
```

**注意**: エージェントが正常にローンチされると表示されるエージェント ARN を記録してください。テストに必要です。

**注意**: Claude Agent SDK は `ANTHROPIC_API_KEY` または AWS Bedrock アクセスのいずれかを環境変数として設定する必要があります。このサンプルでは `CLAUDE_CODE_USE_BEDROCK=1` を使用して Bedrock 統合を有効化しています。これらの環境変数は Dockerfile で設定するか、--env オプションでインラインで設定できます。設定オプションの詳細については、[Claude Agent SDK ドキュメント](https://docs.claude.com/en/api/agent-sdk/overview#core-concepts)を参照してください。

**注意**: スターターツールキットは自動的に Dockerfile を作成し、AgentCore Runtime にエージェントをデプロイします。このサンプルでは Claude Code CLI が依存関係として必要なため、npm インストールを追加した独自の Dockerfile でオーバーライドしています。

### 3. エージェントのテスト

ツールキットコマンドを使用してエージェントをテスト。
```bash
agentcore invoke '{"prompt":"Create a sample data set of a retail store orders. Create a simple data analysis on a sample dataset. Save the files."}'
```

上記のプロンプトに対して、エージェントは以下を実行します：
- プロンプトを解釈
- サンプルデータセットを作成する Python コードを記述
- Code Interpreter セッションを開始してコードを実行
- データ分析を実行する Python コードを記述
- Code Interpreter セッションを使用してデータ分析のコードを実行
- Code Interpreter セッションを使用してファイルを保存
- ユーザーにサマリーを送信


**または** test_scripts ディレクトリに提供されているスクリプトを使用できます。いくつかのサンプルプロンプトが含まれています。
```bash
uv run test_scripts/invoke_agent.py
```

**注意**: スクリプトを実行する前に、invoke_agent.py の `agent_arn` 変数をデプロイしたエージェントの ARN に変更してください。 


## 機能

このエージェントを使用して以下のことができます：
- 分離された Code Interpreter セッションを維持
- セッションにファイルを転送
- セッション内で Python コードを実行
- bash コマンドを実行

## プロジェクト構造

```
.
├── code_int_mcp/
│   ├── client.py                # Code Interpreter API を呼び出すクライアント
│   ├── models.py                # Pydantic データモデル
│   ├── server.py                # ツール付き MCP サーバー
│   └── __init__.py
├── test_scripts/
│   ├── invoke_agent.py          # デプロイされたエージェントを呼び出すクライアント
│   └── cleanup.py               # クリーンアップスクリプト
├── agent.py                     # メインエージェント実装
├── Dockerfile                   # コンテナイメージ定義
├── pyproject.toml               # Python パッケージ設定
└── README.md                    # このファイル
```

### エージェントコードの理解
Claude Agent SDK は2種類のインタラクションをサポートしています - query() と ClaudeSDKClient です。簡単な比較は[こちら](https://docs.claude.com/en/api/agent-sdk/python#quick-comparison)で提供されています。このサンプルでは、カスタムツールの使用をサポートする ClaudeSDKClient を特に使用しています。

このサンプルのエージェントのシステムプロンプトは、bash、ファイル読み書き操作、コード実行に Code Interpreter ツールを使用するよう非常に具体的に設定されています。これは、これらの操作に独自のツールを使用する Claude Agent のデフォルト動作をオーバーライドするために行われています。エージェントは完全なエージェントセッション中に Code Interpreter セッション ID を維持します。

Code Interpreter ツールの操作（`code_int_mcp/server.py`）は、Claude Agent が使用するカスタムツールとして作成されています。[カスタムツール](https://docs.claude.com/en/api/agent-sdk/custom-tools)により、インプロセス MCP サーバーを通じて独自のツールを Claude Agent にプラグインできます。`code_int_mcp/client.py` は、サーバーが boto3 SDK を介して Code Interpreter 操作を呼び出すために使用するシンプルなクラスです。ツールは、Claude Agent が使用できるように[特定の命名形式](https://docs.claude.com/en/api/agent-sdk/custom-tools#tool-name-format)を持つ必要があります。

Code Interpreter のセッションは、分離された CPU、メモリ、ファイルシステムリソースを持つ専用の microVM で実行されます。クライアントがユーザーリクエストのためにセッションを再利用することが理想的です。これを念頭に置いて、エージェントは `prompt` と `code_int_session_id` のペイロードを受け取り、そのセッションを再利用します。実際のアプリケーションでは理想的にはセッション ID をヘッダーで渡しますが、セッション機能をデモするためにペイロードの一部として渡しています。

エージェントの動作をデモするために、コード内に広範なログ記録があります。テスト中のみ使用してください。

Claude Code はデフォルトでモデルが設定されていますが、ClaudeAgentOptions の model プロパティを介して変更できます。詳細は[こちら](https://code.claude.com/docs/en/amazon-bedrock)

### テストスクリプトの理解
`test_scripts\invoke_agent.py` は boto3 SDK を使用して AgentCore Runtime にデプロイされたエージェントを呼び出します。エージェントがレスポンスを送信すると、スクリプトはそれをターミナルにストリーミングします。これにはアクション、呼び出されたツール、最終レスポンスが含まれます。

### クリーンアップ

#### 1. エージェントと関連するすべてのリソースを破棄
```bash
agentcore destroy
```

以下のような出力が表示されます：

```bash
⚠️  About to destroy resources for agent 'code-interpreter-with-claude'

Current deployment:
  • Agent ARN: arn:aws:bedrock-agentcore:us-west-2:XXXXXXXXXXXX:runtime/code-interpreter-with-claude-XXXXXXXXXX
  • Agent ID: code-interpreter-with-claude-XXXXXXXXXX
  • ECR Repository: XXXXXXXXXXXX.dkr.ecr.us-west-2.amazonaws.com/bedrock-agentcore-claude_agent_simple
  • Execution Role: arn:aws:iam::XXXXXXXXXXXX:role/AmazonBedrockAgentCoreSDKRuntime-us-west-2-XXXXXXXXXX

This will permanently delete AWS resources and cannot be undone!
エージェント 'code-interpreter-with-claude' とそのすべてのリソースを削除してもよろしいですか？ [y/N]:
```
y と入力して確認すると、ECR リポジトリと実行ロールを含むエージェントとすべての関連リソースが完全に削除されます。

#### 2. セッションの終了
`test_scripts\invoke_agent.py` を使用してエージェントをテストした場合、すべてのプロンプトが処理されると Code Interpreter セッションは終了します。

`agentcore invoke` を使用してエージェントをテストした場合は、`test_scripts/cleanup.py` スクリプトを使用してセッションを終了してください。`code-int-session-id` はレスポンスの一部として返され、テストスクリプト実行時にターミナルに表示されます。これはテスト用であり、実際の本番デプロイメントではセッション ID のログ記録は無効にする必要があります。

```bash
uv run test_scripts/cleanup.py --code_int_session_id="<code-int-session-id>"
```

エージェントがスタックして応答しない場合は、以下を使用してランタイムセッションを停止できます
```bash
uv run test_scripts/cleanup.py --runtime_session_id="<runtime_session_id>"
```
