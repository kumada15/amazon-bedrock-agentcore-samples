# ============================================================================
# IMPORTS
# ============================================================================

import json
import logging

from . import mylogger
 
logger = mylogger.get_logger()

# ============================================================================
# DIY RESPONSE FORMATTING
# ============================================================================

def format_diy_response(event):
    """
    強化されたテキスト処理を使用して DIY エージェントストリーミング (Server-Sent Events) 用にイベントをフォーマットする。

    Args:
        event: Strands ストリーミングイベント

    Returns:
        str: 適切な改行処理を含むフォーマット済み SSE 文字列
    """
    try:
        # Extract structured content from event
        content_data = extract_content_from_event(event)
        
        # Create enhanced SSE payload
        if content_data['has_text']:
            # Text content - use structured format
            sse_payload = {
                'content': content_data['content'],
                'type': 'text_delta',
                'metadata': {
                    'event_type': content_data['event_type'],
                    'has_formatting': '\n' in content_data['content']
                }
            }
            logger.debug(f"テキストコンテンツをフォーマットしました: {len(content_data['content'])} 文字")
        else:
            # Non-text event - use legacy format for compatibility
            sse_payload = {
                'event': content_data['raw_event'],
                'type': 'event',
                'metadata': {
                    'event_type': content_data['event_type']
                }
            }
            logger.debug(f"非テキストイベントをフォーマットしました: {content_data['event_type']}")
        
        # Format as Server-Sent Events with proper JSON encoding
        sse_data = json.dumps(sse_payload, ensure_ascii=False)
        formatted = f"data: {sse_data}\n\n"
        
        return formatted
        
    except Exception as e:
        logger.error(f"DIY レスポンスのフォーマットに失敗しました: {e}")
        logger.error(f"イベント詳細: {type(event).__name__}")
        logger.error(f"イベントコンテンツ: {str(event)[:200]}...")
        # Re-raise the exception to expose the real issue
        raise

# ============================================================================
# SDK RESPONSE FORMATTING
# ============================================================================

def format_sdk_response(event):
    """
    SDK エージェントストリーミング（直接ストリーミング）用にイベントをフォーマットする。

    Args:
        event: Strands ストリーミングイベント

    Returns:
        Any: 直接ストリーミング用のそのままのイベント
    """
    try:
        # For SDK agent, return event directly
        # BedrockAgentCoreApp handles the formatting
        return event
        
    except Exception as e:
        logger.error(f"SDK レスポンスのフォーマットに失敗しました: {e}")
        # Return error string
        return f"Error: {str(e)}"

# ============================================================================
# ENHANCED TEXT PROCESSING
# ============================================================================

def process_text_formatting(text: str) -> str:
    """
    表示用に改行とフォーマットを適切に処理するためのテキスト処理。

    Args:
        text (str): リテラルな \n 文字を含む可能性のある生テキスト

    Returns:
        str: 表示用の適切な改行を含むテキスト
    """
    if not text:
        return text
    
    try:
        # Convert literal \n strings to actual newlines
        # Handle both single and double backslash cases
        processed_text = text
        processed_text = text.replace('\\n', '\n')
        
        # Handle other common escape sequences that might appear
        processed_text = processed_text.replace('\\t', '\t')
        processed_text = processed_text.replace('\\r', '\r')
        
        # Clean up any excessive whitespace while preserving intentional formatting
        # Don't strip all whitespace as it might be intentional formatting
        
        logger.debug(f"テキスト処理: {len(text)} 文字 → {len(processed_text)} 文字")
        if '\\n' in text:
            logger.debug(f"テキスト内のリテラル改行を変換しました: {text[:50]}...")
        
        return processed_text
        
    except Exception as e:
        logger.error(f"テキストフォーマット処理に失敗しました: {e}")
        logger.error(f"入力テキスト: {repr(text)}")
        # Re-raise to expose the real issue
        raise

def extract_content_from_event(event) -> dict:
    """
    Strands ストリーミングイベントから構造化されたコンテンツを抽出する。
    重複を避けるために優先度ベースの抽出を使用する。

    Args:
        event: Strands ストリーミングイベント

    Returns:
        dict: メタデータを含む構造化されたコンテンツ
    """
    try:
        content_data = {
            'content': '',
            'event_type': type(event).__name__,
            'has_text': False,
            'raw_event': str(event)[:200] + '...' if len(str(event)) > 200 else str(event)
        }
        
        extracted_text = None
        extraction_method = None
        
        # Priority 1: Extract from nested dictionary structure (DIY agent format)
        if not extracted_text and isinstance(event, dict) and 'event' in event:
            inner_event = event['event']
            if 'contentBlockDelta' in inner_event:
                delta = inner_event['contentBlockDelta'].get('delta', {})
                if 'text' in delta and delta['text']:
                    extracted_text = delta['text']
                    extraction_method = "nested_dict"
        
        # Priority 1.5: Handle contentBlockStart events (tool selection)
        if not extracted_text and isinstance(event, dict) and 'event' in event:
            inner_event = event['event']
            if 'contentBlockStart' in inner_event:
                start_info = inner_event['contentBlockStart'].get('start', {})
                if 'toolUse' in start_info:
                    tool_info = start_info['toolUse']
                    tool_name = tool_info.get('name', 'unknown_tool')
                    tool_id = tool_info.get('toolUseId', 'unknown_id')
                    
                    # Clean up tool name by removing namespace prefix
                    # e.g., "bac-tool___ec2_read_operations" -> "ec2_read_operations"
                    clean_tool_name = tool_name.split('___')[-1] if '___' in tool_name else tool_name
                    
                    # Create user-friendly message about tool selection
                    extracted_text = f"\n🔍 Using {clean_tool_name} tool...(ID: {tool_id})\n"
                    extraction_method = "tool_start"
                    logger.debug(f"ツール選択: {clean_tool_name}（ID: {tool_id[:8]}...）")

        # Priority 2: Extract from delta attribute (SDK format)
        if not extracted_text and hasattr(event, 'delta') and hasattr(event.delta, 'text'):
            if event.delta.text:
                #logger.info('# Priority 2: Ecan you creatextract from delta attribute (SDK format)')
                extracted_text = event.delta.text
                extraction_method = "delta_attribute"

        # Priority 3: Extract from string representation (fallback)
        if not extracted_text:
            #logger.info('# Priority 3: Extract from string representation (fallback)')
            event_str = str(event)
            # <uncomment later>
            # if 'contentBlockDelta' in event_str and "'text':" in event_str:
            #     import re
            #     # Try patterns in order of specificity
            #     patterns = [
            #         r"'text':\s*'([^']*)'",  # Most specific first
            #         r'"text":\s*"([^"]*)"',
            #         r"delta=\{[^}]*'text':\s*'([^']*)'[^}]*\}",
            #     ]
                
            #     for pattern in patterns:
            #         delta_match = re.search(pattern, event_str)
            #         if delta_match and delta_match.group(1):
            #             extracted_text = delta_match.group(1)
            #             extraction_method = f"regex_{pattern[:20]}..."
            #             break
        
        # Process extracted text if found
        if extracted_text:
            content_data['content'] = process_text_formatting(extracted_text)
            content_data['has_text'] = True
            logger.debug(f"テキストを抽出しました（{extraction_method}経由）: {extracted_text[:30]}...")
        else:
            logger.debug(f"イベントにテキストコンテンツがありません: {content_data['event_type']}")
        
        return content_data
        
    except Exception as e:
        logger.error(f"イベントからコンテンツの抽出に失敗しました: {e}")
        logger.error(f"イベントタイプ: {type(event).__name__}")
        logger.error(f"イベント詳細: {str(event)[:200]}...")
        # Re-raise to expose the real issue
        raise

# ============================================================================
# UTILITIES (ENHANCED)
# ============================================================================

def extract_text_from_event(event):
    """
    Strands ストリーミングイベントからテキストコンテンツを抽出する。
    新しいコンテンツ抽出を使用する強化版。

    Args:
        event: Strands ストリーミングイベント

    Returns:
        str: 抽出されてフォーマットされたテキスト、または空の文字列
    """
    try:
        content_data = extract_content_from_event(event)
        return content_data.get('content', '')
        
    except Exception as e:
        logger.error(f"イベントからテキストの抽出に失敗しました: {e}")
        logger.error(f"イベントタイプ: {type(event).__name__}")
        # Re-raise to expose the real issue
        raise

def format_error_response(error_message, agent_type="diy"):
    """
    ストリーミング用にエラーレスポンスをフォーマットする。

    Args:
        error_message (str): エラーメッセージ
        agent_type (str): "diy" または "sdk"

    Returns:
        str: フォーマットされたエラーレスポンス
    """
    try:
        if agent_type == "diy":
            # Format as SSE for DIY agent
            error_data = json.dumps({'error': error_message, 'type': 'error'})
            return f"data: {error_data}\n\n"
        else:
            # Format as plain text for SDK agent
            return f"Error: {error_message}"
            
    except Exception as e:
        logger.error(f"エラーレスポンスのフォーマットに失敗しました: {e}")
        return f"Error: {error_message}"