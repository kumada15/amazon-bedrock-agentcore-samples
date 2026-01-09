"""CloudWatch から Strands Eval Session へのマッパー。

このモジュールは、CloudWatch OTEL スパン（ObservabilityClient によって返される）を
Strands Eval の Session フォーマットに変換する SessionMapper 実装を提供します。
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from strands_evals.mappers.session_mapper import SessionMapper
from strands_evals.types.trace import (
    AgentInvocationSpan,
    Session,
    SpanInfo,
    ToolCall,
    ToolConfig,
    ToolExecutionSpan,
    ToolResult,
    Trace,
)

from .models import Span

logger = logging.getLogger(__name__)


class CloudWatchSessionMapper(SessionMapper):
    """CloudWatch OTEL スパンを Strands Eval Session フォーマットにマッピングします。

    このマッパーは、以下を含む完全なエージェントフローを保持します：
    - 入力と出力を持つツール呼び出し
    - ユーザープロンプトとレスポンスを持つエージェント呼び出し
    - 各トレース内の操作の順序
    """

    def map_to_session(self, spans: list[Any], session_id: str) -> Session:
        """CloudWatch スパンを Strands Eval Session に変換します。

        Args:
            spans: ObservabilityClient からの Span オブジェクトのリスト
            session_id: セッション識別子

        Returns:
            評価用の Session オブジェクト
        """
        # Group spans by trace_id
        traces_by_id = defaultdict(list)
        for span in spans:
            if isinstance(span, Span) and span.raw_message:
                trace_id = span.trace_id or span.raw_message.get("traceId", "unknown")
                traces_by_id[trace_id].append(span)

        # Convert each group to a Trace
        traces = []
        for trace_id, trace_spans in traces_by_id.items():
            trace = self._create_trace(trace_spans, trace_id, session_id)
            if trace.spans:  # Only add if we extracted spans
                traces.append(trace)

        logger.info(
            "Mapped %d CloudWatch spans to Session with %d traces",
            len(spans),
            len(traces),
        )
        return Session(traces=traces, session_id=session_id)

    def _create_trace(self, spans: list[Span], trace_id: str, session_id: str) -> Trace:
        """CloudWatch スパンのグループから Trace を作成します。

        Args:
            spans: 同じ trace_id を持つ Span オブジェクトのリスト
            trace_id: トレース識別子
            session_id: セッション識別子

        Returns:
            抽出されたスパンを含む Trace オブジェクト
        """
        eval_spans = []

        # Sort by timestamp to preserve ordering
        sorted_spans = sorted(spans, key=lambda s: s.start_time_unix_nano or 0)

        # Collect all tool calls and results across spans for matching
        all_tool_calls = {}  # tool_use_id -> ToolCall
        all_tool_results = {}  # tool_use_id -> ToolResult

        # First pass: collect all tool calls and results
        for span in sorted_spans:
            raw = span.raw_message
            if not raw:
                continue

            # Extract tool calls from output messages
            tool_calls = self._extract_tool_calls_from_span(raw)
            for tc in tool_calls:
                if tc.tool_call_id:
                    all_tool_calls[tc.tool_call_id] = tc

            # Extract tool results from input messages
            tool_results = self._extract_tool_results_from_span(raw)
            for tr in tool_results:
                if tr.tool_call_id:
                    all_tool_results[tr.tool_call_id] = tr

        # Create ToolExecutionSpans by matching calls with results
        seen_tool_ids = set()
        for span in sorted_spans:
            raw = span.raw_message
            if not raw:
                continue

            tool_calls = self._extract_tool_calls_from_span(raw)
            for tc in tool_calls:
                if tc.tool_call_id and tc.tool_call_id not in seen_tool_ids:
                    seen_tool_ids.add(tc.tool_call_id)
                    # Find matching result
                    tr = all_tool_results.get(tc.tool_call_id)
                    if tr is None:
                        # No result found, create a placeholder
                        tr = ToolResult(content="", tool_call_id=tc.tool_call_id)

                    span_info = self._create_span_info(span, session_id)
                    tool_exec_span = ToolExecutionSpan(
                        span_info=span_info,
                        tool_call=tc,
                        tool_result=tr,
                    )
                    eval_spans.append(tool_exec_span)

        # Extract AgentInvocationSpan from the final span (has full response)
        agent_span = self._extract_agent_invocation_span(sorted_spans, session_id)
        if agent_span:
            eval_spans.append(agent_span)

        return Trace(spans=eval_spans, trace_id=trace_id, session_id=session_id)

    def _extract_tool_calls_from_span(self, raw: dict) -> list[ToolCall]:
        """スパンの出力メッセージからツール呼び出しを抽出します。

        Args:
            raw: CloudWatch スパンからの raw_message 辞書

        Returns:
            ToolCall オブジェクトのリスト
        """
        tool_calls = []
        body = raw.get("body", {})
        output_messages = body.get("output", {}).get("messages", [])

        for msg in output_messages:
            if msg.get("role") != "assistant":
                continue

            content = msg.get("content", {})
            if not isinstance(content, dict):
                continue

            # Check for toolUse directly in content
            if "toolUse" in content:
                tool_use = content["toolUse"]
                tc = ToolCall(
                    name=tool_use.get("name", ""),
                    arguments=tool_use.get("input", {}),
                    tool_call_id=tool_use.get("toolUseId"),
                )
                tool_calls.append(tc)

            # Check inside parsed JSON string (content.content or content.message)
            raw_content = content.get("content") or content.get("message")
            if isinstance(raw_content, str):
                tool_calls.extend(self._parse_tool_calls_from_json(raw_content))

        return tool_calls

    def _parse_tool_calls_from_json(self, json_str: str) -> list[ToolCall]:
        """JSON 文字列からツール呼び出しを解析します。

        Args:
            json_str: '[{"toolUse": {...}}, {"text": "..."}]' のような JSON 文字列

        Returns:
            ToolCall オブジェクトのリスト
        """
        tool_calls = []
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "toolUse" in item:
                        tool_use = item["toolUse"]
                        tc = ToolCall(
                            name=tool_use.get("name", ""),
                            arguments=tool_use.get("input", {}),
                            tool_call_id=tool_use.get("toolUseId"),
                        )
                        tool_calls.append(tc)
        except (json.JSONDecodeError, TypeError):
            pass
        return tool_calls

    def _extract_tool_results_from_span(self, raw: dict) -> list[ToolResult]:
        """スパンの入力メッセージからツール結果を抽出します。

        Args:
            raw: CloudWatch スパンからの raw_message 辞書

        Returns:
            ToolResult オブジェクトのリスト
        """
        tool_results = []
        body = raw.get("body", {})
        input_messages = body.get("input", {}).get("messages", [])

        for msg in input_messages:
            content = msg.get("content", {})

            # Handle direct toolResult in content
            if isinstance(content, dict) and "toolResult" in content:
                tr_data = content["toolResult"]
                tr = self._parse_tool_result(tr_data)
                if tr:
                    tool_results.append(tr)

            # Handle JSON string in content.content
            if isinstance(content, dict):
                raw_content = content.get("content") or content.get("message")
                if isinstance(raw_content, str):
                    tool_results.extend(self._parse_tool_results_from_json(raw_content))

            # Handle direct JSON string content (role=tool)
            if isinstance(content, str):
                tool_results.extend(self._parse_tool_results_from_json(content))

        return tool_results

    def _parse_tool_results_from_json(self, json_str: str) -> list[ToolResult]:
        """JSON 文字列からツール結果を解析します。

        Args:
            json_str: '[{"toolResult": {...}}]' のような JSON 文字列

        Returns:
            ToolResult オブジェクトのリスト
        """
        tool_results = []
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "toolResult" in item:
                        tr = self._parse_tool_result(item["toolResult"])
                        if tr:
                            tool_results.append(tr)
        except (json.JSONDecodeError, TypeError):
            pass
        return tool_results

    def _parse_tool_result(self, tr_data: dict) -> ToolResult | None:
        """単一のツール結果辞書を ToolResult オブジェクトに解析します。

        Args:
            tr_data: toolResult データを含む辞書

        Returns:
            ToolResult オブジェクトまたは None
        """
        if not isinstance(tr_data, dict):
            return None

        # Extract content - may be string or list of content blocks
        content_raw = tr_data.get("content", "")
        if isinstance(content_raw, list):
            # Extract text from content blocks
            texts = []
            for block in content_raw:
                if isinstance(block, dict) and "text" in block:
                    texts.append(block["text"])
            content = "\n".join(texts)
        else:
            content = str(content_raw)

        return ToolResult(
            content=content,
            error=tr_data.get("error"),
            tool_call_id=tr_data.get("toolUseId"),
        )

    def _extract_agent_invocation_span(
        self, spans: list[Span], session_id: str
    ) -> AgentInvocationSpan | None:
        """スパンのリストから AgentInvocationSpan を抽出します。

        最初のスパンからユーザープロンプトを、最も長い出力を持つスパンから
        最終レスポンスを見つけます。

        Args:
            spans: ソートされた Span オブジェクトのリスト
            session_id: セッション識別子

        Returns:
            AgentInvocationSpan、抽出に失敗した場合は None
        """
        if not spans:
            return None

        # Get user prompt from first message
        user_prompt = None
        for span in spans:
            raw = span.raw_message
            if not raw:
                continue
            prompt = self._extract_user_prompt(raw)
            if prompt:
                user_prompt = prompt
                break

        if not user_prompt:
            return None

        # Get agent response from span with longest output (final answer)
        best_response = ""
        best_span = None
        for span in spans:
            raw = span.raw_message
            if not raw:
                continue
            response = self._extract_agent_response(raw)
            if response and len(response) > len(best_response):
                best_response = response
                best_span = span

        if not best_response or not best_span:
            return None

        # Extract available tools (from system message if present)
        available_tools = self._extract_available_tools(spans)

        span_info = self._create_span_info(best_span, session_id)
        return AgentInvocationSpan(
            span_info=span_info,
            user_prompt=user_prompt,
            agent_response=best_response,
            available_tools=available_tools,
        )

    def _extract_user_prompt(self, raw: dict) -> str | None:
        """スパンからユーザープロンプトテキストを抽出します。

        Args:
            raw: raw_message 辞書

        Returns:
            ユーザープロンプト文字列または None
        """
        body = raw.get("body", {})
        input_messages = body.get("input", {}).get("messages", [])

        for msg in input_messages:
            if msg.get("role") != "user":
                continue

            content = msg.get("content", {})
            text = self._extract_text_from_content(content)
            if text:
                return text

        return None

    def _extract_agent_response(self, raw: dict) -> str | None:
        """スパンからエージェントレスポンステキストを抽出します。

        Args:
            raw: raw_message 辞書

        Returns:
            エージェントレスポンス文字列または None
        """
        body = raw.get("body", {})
        output_messages = body.get("output", {}).get("messages", [])

        # Get the last assistant message that has actual text (not just tool calls)
        best_response = ""
        for msg in output_messages:
            if msg.get("role") != "assistant":
                continue

            content = msg.get("content", {})

            # Check for direct message field (final response)
            if isinstance(content, dict):
                direct_msg = content.get("message")
                if isinstance(direct_msg, str) and not direct_msg.startswith("[{"):
                    # Not a JSON string, this is the actual response
                    if len(direct_msg) > len(best_response):
                        best_response = direct_msg
                    continue

            text = self._extract_text_from_content(content)
            if text and len(text) > len(best_response):
                best_response = text

        return best_response if best_response else None

    def _extract_text_from_content(self, content: Any) -> str | None:
        """content フィールドからテキストを抽出します。

        Args:
            content: content 辞書または文字列

        Returns:
            抽出されたテキストまたは None
        """
        if isinstance(content, str):
            return content

        if not isinstance(content, dict):
            return None

        # Try content.content or content.message
        raw_content = content.get("content") or content.get("message")

        if isinstance(raw_content, str):
            # Try to parse as JSON
            try:
                parsed = json.loads(raw_content)
                if isinstance(parsed, list):
                    texts = []
                    for item in parsed:
                        if isinstance(item, dict) and "text" in item:
                            texts.append(item["text"])
                    if texts:
                        return " ".join(texts)
            except (json.JSONDecodeError, TypeError):
                # Not JSON, return as-is
                return raw_content

        return None

    def _extract_available_tools(self, spans: list[Span]) -> list[ToolConfig]:
        """システムメッセージまたはスパン属性から利用可能なツールを抽出します。

        Args:
            spans: Span オブジェクトのリスト

        Returns:
            ToolConfig オブジェクトのリスト
        """
        # For now, we'll extract tool names from actual tool calls
        # A more complete implementation would parse the system message
        tool_names = set()
        for span in spans:
            raw = span.raw_message
            if not raw:
                continue
            tool_calls = self._extract_tool_calls_from_span(raw)
            for tc in tool_calls:
                tool_names.add(tc.name)

        return [ToolConfig(name=name) for name in sorted(tool_names)]

    def _create_span_info(self, span: Span, session_id: str) -> SpanInfo:
        """CloudWatch Span から SpanInfo を作成します。

        Args:
            span: Span オブジェクト
            session_id: セッション識別子

        Returns:
            SpanInfo オブジェクト
        """
        raw = span.raw_message or {}

        # Convert nanoseconds to datetime
        start_nano = span.start_time_unix_nano or raw.get("startTimeUnixNano", 0)
        end_nano = raw.get("endTimeUnixNano", start_nano)

        start_time = datetime.fromtimestamp(start_nano / 1e9, tz=timezone.utc)
        end_time = datetime.fromtimestamp(end_nano / 1e9, tz=timezone.utc)

        return SpanInfo(
            trace_id=span.trace_id,
            span_id=span.span_id,
            session_id=session_id,
            parent_span_id=raw.get("parentSpanId"),
            start_time=start_time,
            end_time=end_time,
        )
