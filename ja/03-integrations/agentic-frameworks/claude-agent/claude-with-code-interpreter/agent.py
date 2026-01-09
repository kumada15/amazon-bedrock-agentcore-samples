from code_int_mcp.server import code_int_mcp_server
from claude_agent_sdk import (
    AssistantMessage,
    UserMessage,
    ResultMessage,
    ClaudeAgentOptions,
    TextBlock,
    ToolUseBlock,
    ClaudeSDKClient,
    ToolResultBlock,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging
import json

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
async def main(payload):
    """
    エージェントのエントリーポイント。ユーザープロンプトを受け取り、コードインタープリターツールを使用してプロンプトを実行します。
    ストリーミング用の中間レスポンスを生成します。
    """
    prompt = payload["prompt"]
    session_id = payload.get("session_id", "")
    agent_responses = []
    code_int_session_id = session_id

    options = ClaudeAgentOptions(
        mcp_servers={"codeint": code_int_mcp_server},
        model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        allowed_tools=[
            "mcp__codeint__execute_code",
            "mcp__codeint__execute_command",
            "mcp__codeint__write_files",
            "mcp__codeint__read_files",
        ],
        system_prompt=f"""あなたはコード生成と実行に関連するタスクでユーザーを支援する AI アシスタントです。

  重要なルール：
  1. すべての Python コード実行タスクに mcp__codeint__execute_code を必ず使用してください。ライブラリが見つからない場合は、代替ライブラリを使用するようにコードを書き直してください。不足しているライブラリのインストールは試みないでください。
  2. コードインタープリターセッション内で bash コマンドを実行するには mcp__codeint__execute_command を使用できます。
  3. コードインタープリターセッション内でファイルの書き込み/保存を行うには mcp__codeint_write_files を使用できます。
  4. 許可を求めずにツールを使用してください。
  5. セッションを継続するためにコードインタープリターツールを呼び出す際は {code_int_session_id} を使用してください。'default' にしないでください。空の場合でも渡してください。

  コードインタープリターセッションと対話するための利用可能なツール：
  - mcp__codeint__execute_code: Python/コードスニペットを実行します。
  - mcp__codeint__execute_command: bash/shell コマンドを実行します。
  - mcp__codeint_write_files コマンド: ファイルの書き込み/保存操作を実行します。すべてのファイルについて path（ファイル名）と text（ファイルの内容）のリストを作成してツールに渡してください。
  - mcp__codeint_read_files コマンド: ファイルの読み取り操作を実行します。path（ファイル名）のリストを作成してください。

  あなたのレスポンスは：
  1. 結果を表示する
  2. 簡潔な説明を提供する
  """,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_messages():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        logger.info("*" * 80 + "\n")
                        logger.info("ツール使用: %s", block.name)
                        logger.info(
                            "入力パラメータ:\n%s", json.dumps(block.input, indent=2)
                        )
                        logger.info("*" * 80 + "\n")
                        # Yield tool use as a streaming chunk
                        yield {
                            "type": "tool_use",
                            "tool_name": block.name,
                            "tool_input": block.input,
                            "session_id": code_int_session_id,
                        }
                    elif isinstance(block, TextBlock):
                        logger.info("*" * 80 + "\n")
                        logger.info("エージェントの応答: %s", block.text)
                        logger.info("*" * 80 + "\n")
                        agent_responses.append(block.text)
                        # Yield text response as a streaming chunk
                        yield {
                            "type": "text",
                            "text": block.text,
                            "session_id": code_int_session_id,
                        }
            elif isinstance(msg, UserMessage):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        if block.content and len(block.content) > 0:
                            if isinstance(block.content[0], dict):
                                text_content = block.content[0].get("text", "")
                                logger.info("*" * 80 + "\n")
                                logger.info("ツール結果: %s", text_content)
                                logger.info("*" * 80 + "\n")
                                result_data = json.loads(text_content)
                                extracted_session_id = result_data.get(
                                    "code_int_session_id", ""
                                )
                                if extracted_session_id:
                                    code_int_session_id = extracted_session_id
                        logger.info("*" * 80 + "\n")
            elif isinstance(msg, ResultMessage):
                logger.info("*" * 80 + "\n")
                logger.info("ResultMessage を受信 - 会話が完了 %s", msg)
                break  # Exit loop when final result is received

    # Yield final response with complete data
    yield {
        "type": "final",
        "response": "\n".join(agent_responses)
        if agent_responses
        else "No response from agent",
        "session_id": code_int_session_id,
    }


if __name__ == "__main__":
    app.run()
