import json
import re
import time
import uuid
from typing import Dict, Iterator, List

import boto3
import streamlit as st
from streamlit.logger import get_logger

logger = get_logger(__name__)
logger.setLevel("INFO")

# ページ設定
st.set_page_config(
    page_title="Bedrock AgentCore Chat",
    page_icon="static/gen-ai-dark.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit デプロイメントコンポーネントを非表示
st.markdown(
    """
      <style>
        .stAppDeployButton {display:none;}
        #MainMenu {visibility: hidden;}
      </style>
    """,
    unsafe_allow_html=True,
)

HUMAN_AVATAR = "static/user-profile.svg"
AI_AVATAR = "static/gen-ai-dark.svg"


def fetch_agent_runtimes(region: str = "us-east-1") -> List[Dict]:
    """bedrock-agentcore-controlから利用可能なエージェントランタイムを取得します"""
    try:
        client = boto3.client("bedrock-agentcore-control", region_name=region)
        response = client.list_agent_runtimes(maxResults=100)

        # READY 状態のエージェントのみフィルタリングして名前でソート
        ready_agents = [
            agent
            for agent in response.get("agentRuntimes", [])
            if agent.get("status") == "READY"
        ]

        # 最新の更新時刻でソート（新しい順）
        ready_agents.sort(key=lambda x: x.get("lastUpdatedAt", ""), reverse=True)

        return ready_agents
    except Exception as e:
        st.error(f"Error fetching agent runtimes: {e}")
        return []


def fetch_agent_runtime_versions(
    agent_runtime_id: str, region: str = "us-east-1"
) -> List[Dict]:
    """特定のエージェントランタイムのバージョンを取得します"""
    try:
        client = boto3.client("bedrock-agentcore-control", region_name=region)
        response = client.list_agent_runtime_versions(agentRuntimeId=agent_runtime_id)

        # READY 状態のバージョンのみフィルタリング
        ready_versions = [
            version
            for version in response.get("agentRuntimes", [])
            if version.get("status") == "READY"
        ]

        # 最新の更新時刻でソート（新しい順）
        ready_versions.sort(key=lambda x: x.get("lastUpdatedAt", ""), reverse=True)

        return ready_versions
    except Exception as e:
        st.error(f"Error fetching agent runtime versions: {e}")
        return []


def clean_response_text(text: str, show_thinking: bool = True) -> str:
    """より良い表示のためにレスポンステキストをクリーンアップしてフォーマットします"""
    if not text:
        return text

    # 連続するクォートされたチャンクパターンを処理
    # パターン: "word1" "word2" "word3" -> word1 word2 word3
    text = re.sub(r'"\s*"', "", text)
    text = re.sub(r'^"', "", text)
    text = re.sub(r'"$', "", text)

    # リテラル \n を実際の改行に置換
    text = text.replace("\\n", "\n")

    # リテラル \t を実際のタブに置換
    text = text.replace("\\t", "\t")

    # 複数のスペースをクリーンアップ
    text = re.sub(r" {3,}", " ", text)

    # スペースに変換された改行を修正
    text = text.replace(" \n ", "\n")
    text = text.replace("\n ", "\n")
    text = text.replace(" \n", "\n")

    # 番号付きリストを処理
    text = re.sub(r"\n(\d+)\.\s+", r"\n\1. ", text)
    text = re.sub(r"^(\d+)\.\s+", r"\1. ", text)

    # 箇条書きを処理
    text = re.sub(r"\n-\s+", r"\n- ", text)
    text = re.sub(r"^-\s+", r"- ", text)

    # セクションヘッダーを処理
    text = re.sub(r"\n([A-Za-z][A-Za-z\s]{2,30}):\s*\n", r"\n**\1:**\n\n", text)

    # 複数の改行をクリーンアップ
    text = re.sub(r"\n{3,}", "\n\n", text)

    # thinking タグをクリーンアップ

    if not show_thinking:
        text = re.sub(r"<thinking>.*?</thinking>", "", text)

    return text.strip()


def extract_text_from_response(data) -> str:
    """様々な形式のレスポンスデータからテキストコンテンツを抽出します"""
    if isinstance(data, dict):
        # フォーマット処理: {'role': 'assistant', 'content': [{'text': 'Hello!'}]}
        if "role" in data and "content" in data:
            content = data["content"]
            if isinstance(content, list) and len(content) > 0:
                if isinstance(content[0], dict) and "text" in content[0]:
                    return str(content[0]["text"])
                else:
                    return str(content[0])
            elif isinstance(content, str):
                return content
            else:
                return str(content)

        # その他の一般的なフォーマットを処理
        if "text" in data:
            return str(data["text"])
        elif "content" in data:
            content = data["content"]
            if isinstance(content, str):
                return content
            else:
                return str(content)
        elif "message" in data:
            return str(data["message"])
        elif "response" in data:
            return str(data["response"])
        elif "result" in data:
            return str(data["result"])

    return str(data)


def parse_streaming_chunk(chunk: str) -> str:
    """個々のストリーミングチャンクをパースして意味のあるコンテンツを抽出します"""
    logger.debug(f"parse_streaming_chunk: チャンクを受信: {chunk}")
    logger.debug(f"parse_streaming_chunk: チャンクの型: {type(chunk)}")

    try:
        # まず JSON としてパースを試行
        if chunk.strip().startswith("{"):
            logger.debug("parse_streaming_chunk: JSONパースを試行中")
            data = json.loads(chunk)
            logger.debug(f"parse_streaming_chunk: JSONパース成功: {data}")

            # 特定のフォーマットを処理: {'role': 'assistant', 'content': [{'text': '...'}]}
            if isinstance(data, dict) and "role" in data and "content" in data:
                content = data["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_item = content[0]
                    if isinstance(first_item, dict) and "text" in first_item:
                        extracted_text = first_item["text"]
                        logger.debug(
                            f"parse_streaming_chunk: テキスト抽出: {extracted_text}"
                        )
                        return extracted_text
                    else:
                        return str(first_item)
                else:
                    return str(content)
            else:
                # その他のフォーマットには汎用抽出関数を使用
                return extract_text_from_response(data)

        # JSON でない場合はチャンクをそのまま返す
        logger.debug("parse_streaming_chunk: JSONではないため、そのまま返却")
        return chunk
    except json.JSONDecodeError as e:
        logger.error(f"parse_streaming_chunk: JSONデコードエラー: {e}")

        # Python 辞書文字列表現（シングルクォート付き）の処理を試行
        if chunk.strip().startswith("{") and "'" in chunk:
            logger.debug(
                "parse_streaming_chunk: Python辞書文字列の処理を試行中"
            )
            try:
                # JSON パース用にシングルクォートをダブルクォートに変換を試行
                # これはシンプルなアプローチで、複雑なケースでは改良が必要な場合がある
                json_chunk = chunk.replace("'", '"')
                data = json.loads(json_chunk)
                logger.debug(
                    f"parse_streaming_chunk: 変換とパースに成功: {data}"
                )

                # 特定のフォーマットを処理
                if isinstance(data, dict) and "role" in data and "content" in data:
                    content = data["content"]
                    if isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and "text" in first_item:
                            extracted_text = first_item["text"]
                            logger.debug(
                                f"parse_streaming_chunk: 変換した辞書からテキスト抽出: {extracted_text}"
                            )
                            return extracted_text
                        else:
                            return str(first_item)
                    else:
                        return str(content)
                else:
                    return extract_text_from_response(data)
            except json.JSONDecodeError:
                logger.debug(
                    "parse_streaming_chunk: Python辞書文字列の変換に失敗"
                )
                pass

        # すべてのパースが失敗した場合、チャンクをそのまま返す
        logger.debug("parse_streaming_chunk: すべてのパースに失敗、チャンクをそのまま返却")
        return chunk


def invoke_agent_streaming(
    prompt: str,
    agent_arn: str,
    runtime_session_id: str,
    region: str = "us-east-1",
    show_tool: bool = True,
) -> Iterator[str]:
    """エージェントを呼び出し、ストリーミングレスポンスチャンクを生成します"""
    try:
        agentcore_client = boto3.client("bedrock-agentcore", region_name=region)

        boto3_response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            runtimeSessionId=runtime_session_id,
            payload=json.dumps({"prompt": prompt}),
        )

        logger.debug(f"contentType: {boto3_response.get('contentType', '未検出')}")

        if "text/event-stream" in boto3_response.get("contentType", ""):
            logger.debug("ストリーミングレスポンスパスを使用")
            # ストリーミングレスポンスを処理
            for line in boto3_response["response"].iter_lines(chunk_size=1):
                if line:
                    line = line.decode("utf-8")
                    logger.debug(f"生の行: {line}")
                    if line.startswith("data: "):
                        line = line[6:]
                        logger.debug(f"'data: ' 削除後の行: {line}")
                        # 各チャンクをパースしてクリーンアップ
                        parsed_chunk = parse_streaming_chunk(line)
                        if parsed_chunk.strip():  # Only yield non-empty chunks
                            if "🔧 Using tool:" in parsed_chunk and not show_tool:
                                yield ""
                            else:
                                yield parsed_chunk
                    else:
                        logger.debug(
                            f"行が 'data: ' で始まっていないためスキップ: {line}"
                        )
        else:
            logger.debug("非ストリーミングレスポンスパスを使用")
            # 非ストリーミング JSON レスポンスを処理
            try:
                response_obj = boto3_response.get("response")
                logger.debug(f"response_obj の型: {type(response_obj)}")

                if hasattr(response_obj, "read"):
                    # レスポンスコンテンツを読み取り
                    content = response_obj.read()
                    if isinstance(content, bytes):
                        content = content.decode("utf-8")

                    logger.debug(f"生のコンテンツ: {content}")

                    try:
                        # JSON としてパースしてテキストを抽出
                        response_data = json.loads(content)
                        logger.debug(f"パース済みJSON: {response_data}")

                        # 受信している特定のフォーマットを処理
                        if isinstance(response_data, dict):
                            # まず 'result' ラッパーを確認
                            if "result" in response_data:
                                actual_data = response_data["result"]
                            else:
                                actual_data = response_data

                            # ネストされた構造からテキストを抽出
                            if "role" in actual_data and "content" in actual_data:
                                content_list = actual_data["content"]
                                if (
                                    isinstance(content_list, list)
                                    and len(content_list) > 0
                                ):
                                    first_item = content_list[0]
                                    if (
                                        isinstance(first_item, dict)
                                        and "text" in first_item
                                    ):
                                        extracted_text = first_item["text"]
                                        logger.debug(
                                            f"テキスト抽出: {extracted_text}"
                                        )
                                        yield extracted_text
                                    else:
                                        yield str(first_item)
                                else:
                                    yield str(content_list)
                            else:
                                # 汎用抽出を使用
                                text = extract_text_from_response(actual_data)
                                yield text
                        else:
                            yield str(response_data)

                    except json.JSONDecodeError as e:
                        logger.error(f"JSONデコードエラー: {e}")
                        # JSON でない場合は生のコンテンツを yield
                        yield content
                elif isinstance(response_obj, dict):
                    # 直接の辞書レスポンス
                    text = extract_text_from_response(response_obj)
                    yield text
                else:
                    logger.debug(f"予期しない response_obj の型: {type(response_obj)}")
                    yield "No response content"

            except Exception as e:
                logger.error(f"非ストリーミング処理での例外: {e}")
                yield f"Error reading response: {e}"

    except Exception as e:
        yield f"Error invoking agent: {e}"


def main():
    st.logo("static/agentcore-service-icon.png", size="large")
    st.title("Amazon Bedrock AgentCore Chat")

    # 設定用サイドバー
    with st.sidebar:
        st.header("Settings")

        # リージョン選択（エージェント取得に影響するため上部に配置）
        region = st.selectbox(
            "AWS Region",
            ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
            index=0,
        )

        # エージェント選択
        st.subheader("Agent Selection")

        # 利用可能なエージェントを取得
        with st.spinner("Loading available agents..."):
            available_agents = fetch_agent_runtimes(region)

        if available_agents:
            # ユニークなエージェント名とその Runtime ID を取得
            unique_agents = {}
            for agent in available_agents:
                name = agent.get("agentRuntimeName", "Unknown")
                runtime_id = agent.get("agentRuntimeId", "")
                if name not in unique_agents:
                    unique_agents[name] = runtime_id

            # エージェント名のオプションを作成
            agent_names = list(unique_agents.keys())

            # エージェント名選択ドロップダウン
            col1, col2 = st.columns([2, 1])

            with col1:
                selected_agent_name = st.selectbox(
                    "Agent Name",
                    options=agent_names,
                    help="Choose an agent to chat with",
                )

            # 特定の API を使用して選択されたエージェントのバージョンを取得
            if selected_agent_name and selected_agent_name in unique_agents:
                agent_runtime_id = unique_agents[selected_agent_name]

                with st.spinner("Loading versions..."):
                    agent_versions = fetch_agent_runtime_versions(
                        agent_runtime_id, region
                    )

                if agent_versions:
                    version_options = []
                    version_arn_map = {}

                    for version in agent_versions:
                        version_num = version.get("agentRuntimeVersion", "Unknown")
                        arn = version.get("agentRuntimeArn", "")
                        updated = version.get("lastUpdatedAt", "")
                        description = version.get("description", "")

                        # 更新時刻付きでバージョン表示をフォーマット
                        version_display = f"v{version_num}"
                        if updated:
                            try:
                                if hasattr(updated, "strftime"):
                                    updated_str = updated.strftime("%m/%d %H:%M")
                                    version_display += f" ({updated_str})"
                            except:
                                pass

                        version_options.append(version_display)
                        version_arn_map[version_display] = {
                            "arn": arn,
                            "description": description,
                        }

                    with col2:
                        selected_version = st.selectbox(
                            "Version",
                            options=version_options,
                            help="Choose the version to use",
                        )

                    # 選択されたエージェントとバージョンの ARN を取得
                    version_info = version_arn_map.get(selected_version, {})
                    agent_arn = version_info.get("arn", "")
                    description = version_info.get("description", "")

                    # 選択されたエージェント情報を表示
                    if agent_arn:
                        st.info(f"Selected: {selected_agent_name} {selected_version}")
                        if description:
                            st.caption(f"Description: {description}")
                        with st.expander("View ARN"):
                            st.code(agent_arn)
                else:
                    st.warning(f"No versions found for {selected_agent_name}")
                    agent_arn = ""
            else:
                agent_arn = ""
        else:
            st.error("No agent runtimes found or error loading agents")
            agent_arn = ""

            # 手動入力へのフォールバック
            st.subheader("Manual ARN Input")
            agent_arn = st.text_input(
                "Agent ARN", value="", help="Enter your Bedrock AgentCore ARN manually"
            )
        if st.button("Refresh", key="refresh_agents", help="Refresh agent list"):
            st.rerun()

        # Runtime セッション ID
        st.subheader("Session Configuration")

        # セッション state にセッション ID が存在しない場合は初期化
        if "runtime_session_id" not in st.session_state:
            st.session_state.runtime_session_id = str(uuid.uuid4())

        # 生成ボタン付きセッション ID 入力
        runtime_session_id = st.text_input(
            "Runtime Session ID",
            value=st.session_state.runtime_session_id,
            help="Unique identifier for this runtime session",
        )

        if st.button("Refresh", help="Generate new session ID and clear chat"):
            st.session_state.runtime_session_id = str(uuid.uuid4())
            st.session_state.messages = []  # セッションリセット時にチャットメッセージをクリア
            st.rerun()

        # ユーザーが手動で ID を変更した場合はセッション state を更新
        if runtime_session_id != st.session_state.runtime_session_id:
            st.session_state.runtime_session_id = runtime_session_id

        # レスポンスフォーマットオプション
        st.subheader("Display Options")
        auto_format = st.checkbox(
            "Auto-format responses",
            value=True,
            help="Automatically clean and format responses",
        )
        show_raw = st.checkbox(
            "Show raw response",
            value=False,
            help="Display the raw unprocessed response",
        )
        show_tools = st.checkbox(
            "Show tools",
            value=True,
            help="Display tools used",
        )
        show_thinking = st.checkbox(
            "Show thinking",
            value=False,
            help="Display the AI thinking text",
        )

        # チャットクリアボタン
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

        # 接続ステータス
        st.divider()
        if agent_arn:
            st.success("✅ Agent selected and ready")
        else:
            st.error("❌ Please select an agent")

    # チャット履歴を初期化
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # チャットメッセージを表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=message["avatar"]):
            st.markdown(message["content"])

    # チャット入力
    if prompt := st.chat_input("Type your message here..."):
        if not agent_arn:
            st.error("Please select an agent in the sidebar first.")
            return

        # ユーザーメッセージをチャット履歴に追加
        st.session_state.messages.append(
            {"role": "user", "content": prompt, "avatar": HUMAN_AVATAR}
        )
        with st.chat_message("user", avatar=HUMAN_AVATAR):
            st.markdown(prompt)

        # アシスタントレスポンスを生成
        with st.chat_message("assistant", avatar=AI_AVATAR):
            message_placeholder = st.empty()
            chunk_buffer = ""

            try:
                # レスポンスをストリーミング
                for chunk in invoke_agent_streaming(
                    prompt,
                    agent_arn,
                    st.session_state.runtime_session_id,
                    region,
                    show_tools,
                ):
                    # 受信内容を確認
                    logger.debug(f"メインループ: チャンクの型: {type(chunk)}")
                    logger.debug(f"メインループ: チャンクの内容: {chunk}")

                    # 連結前にチャンクが文字列であることを確認
                    if not isinstance(chunk, str):
                        logger.debug(
                            f"メインループ: 文字列以外のチャンクを文字列に変換"
                        )
                        chunk = str(chunk)

                    # チャンクをバッファに追加
                    chunk_buffer += chunk

                    # 数チャンクごと、または特定の文字に達したときにのみ表示を更新
                    if (
                        len(chunk_buffer) % 3 == 0
                        or chunk.endswith(" ")
                        or chunk.endswith("\n")
                    ):
                        if auto_format:
                            # 蓄積されたレスポンスをクリーンアップ
                            cleaned_response = clean_response_text(
                                chunk_buffer, show_thinking
                            )
                            message_placeholder.markdown(cleaned_response + " ▌")
                        else:
                            # 生のレスポンスを表示
                            message_placeholder.markdown(chunk_buffer + " ▌")

                    time.sleep(0.01)  # バッチ更新のため遅延を短縮

                # カーソルなしの最終レスポンス
                if auto_format:
                    full_response = clean_response_text(chunk_buffer, show_thinking)
                else:
                    full_response = chunk_buffer

                message_placeholder.markdown(full_response)

                # 要求された場合は生のレスポンスを展開表示
                if show_raw and auto_format:
                    with st.expander("View raw response"):
                        st.text(chunk_buffer)

            except Exception as e:
                error_msg = f"❌ **Error:** {str(e)}"
                message_placeholder.markdown(error_msg)
                full_response = error_msg

        # アシスタントレスポンスをチャット履歴に追加
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response, "avatar": AI_AVATAR}
        )


if __name__ == "__main__":
    main()
