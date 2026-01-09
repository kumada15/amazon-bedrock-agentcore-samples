import json
from pathlib import Path

from strands import Agent
from strands.experimental.hooks import BeforeToolInvocationEvent
from strands.hooks import HookProvider
from strands.hooks import HookRegistry
from strands.hooks.events import MessageAddedEvent
from strands.models.litellm import LiteLLMModel
from strands.types.content import Messages

from icarus.tools.convert_openapi_schema_version import ConvertSchemaVersionTool
from icarus.tools.python_interpreter import PythonInterpreterTool
from icarus.tools.schema_editor import SchemaEditorTool
from icarus.tools.schema_graph import SchemaGraphActions
from icarus.tools.validate_openapi_schema import ValidateSchemaTool
from icarus.utils.time_machine import TimeMachine

DEFAULT_MODEL_ID = "bedrock/converse/us.anthropic.claude-3-7-sonnet-20250219-v1:0"

SYSTEM_PROMPT = """\
あなたは OpenAPI スキーマ検証のエキスパートです。あなたのミッションは、提供された OpenAPI スキーマファイル内のすべての検証エラーを体系的に特定し修正することです。

**ワークフロー:**
1. まず、validate_openapi_schema ツールを実行して現在のすべてのエラーを特定
2. 各エラーについて、schema_editor preview コマンドを使用して問題のあるセクションを確認（ファイル全体ではなく小さなチャンクを読み取る）
3. または、schema_editor search コマンドを使用して特定のパターンや関連する問題を検索
4. 適切な方法でエラーを修正:
   - 単純な修正には直接ファイル編集
   - パターンベースの一括変更には run_python_script ツール経由で Python スクリプト
5. 各修正または修正バッチの後に再検証
6. validate_openapi_schema がエラーを返さなくなるまで続行

**重要な制約:**
- OpenAPI バージョンが正しくない場合は、まず convert_openapi_schema_version ツールを使用してスキーマを変換し、再度検証
- スキーマファイルは非常に大きい可能性があります - 常に小さなセクションのみを読み取る
- 検証警告は無視し、検証エラーの修正のみに集中
- すべての検証エラーが解決されるまで停止しない
- 各修正が新しいエラーを導入しないことを確認

**スキーマファイルの場所（run_python_script ツール用）:**
/ctx/schema.yaml"""

DEFAULT_USER_MESSAGE = "Validate my OpenAPI schema and repair it if needed."


class TimeMachineCommitHook(HookProvider):
    def __init__(self, tm: TimeMachine):
        self.tm = tm

    def register_hooks(self, registry: HookRegistry, **kwargs):
        registry.add_callback(BeforeToolInvocationEvent, self.before_tool_invocation)

    def before_tool_invocation(
        self, event: BeforeToolInvocationEvent  # pylint:disable=unused-argument
    ):
        self.tm.commit()


class SaveMessagesHook(HookProvider):
    MESSAGES_FILE = "messages.json"

    def __init__(self, session_dir: Path):
        self.messages_path = session_dir / self.MESSAGES_FILE

    def register_hooks(self, registry: HookRegistry, **kwargs):
        registry.add_callback(MessageAddedEvent, self.save_messages)

    def save_messages(self, event: MessageAddedEvent):
        messages = event.agent.messages
        if len(messages):
            self.messages_path.write_text(json.dumps(messages, indent=2))


def init_agent(session_dir: Path, model_id: str = DEFAULT_MODEL_ID) -> Agent:
    session_dir = session_dir.resolve()
    schema_path = session_dir / "schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(schema_path)

    messages: Messages | None = None
    messages_path = session_dir / SaveMessagesHook.MESSAGES_FILE
    if messages_path.exists():
        messages = json.loads(messages_path.read_text())

    schema_graph_actions = SchemaGraphActions(context_dir=session_dir)

    model = LiteLLMModel(model_id=model_id)
    agent = Agent(
        model=model,
        messages=messages,
        system_prompt=SYSTEM_PROMPT,
        hooks=[TimeMachineCommitHook(tm=TimeMachine(schema_path)), SaveMessagesHook(session_dir)],
        state=dict(session_dir=str(session_dir)),
        tools=[
            ValidateSchemaTool(mount_dir=session_dir).validate_openapi_schema,
            ConvertSchemaVersionTool(workdir=session_dir).convert_openapi_schema_version,
            SchemaEditorTool(context_dir=session_dir).schema_editor,
            PythonInterpreterTool(context_dir=session_dir).make_tool(),
            schema_graph_actions.list_paths_related_to_component,
            schema_graph_actions.update_schema_extract_paths,
        ],
    )
    return agent
