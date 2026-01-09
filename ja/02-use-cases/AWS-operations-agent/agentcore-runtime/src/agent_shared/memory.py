# ============================================================================
# IMPORTS
# ============================================================================

import logging
from datetime import datetime
from .config import load_configs

from . import mylogger
 
logger = mylogger.get_logger()

# Global variables for memory state
_memory_initialized = False
_memory_client = None
_current_session_id = None

# ============================================================================
# MEMORY SETUP
# ============================================================================

def setup_memory():
    """
    AgentCore Memory クライアントをセットアップする。

    Returns:
        bool: 成功した場合は True、利用できない場合は False
    """
    global _memory_initialized, _memory_client
    
    if _memory_initialized:
        return True
    
    try:
        # Import AgentCore memory client
        from bedrock_agentcore.memory import MemoryClient
        
        # Load configuration
        agentcore_config, _ = load_configs()
        
        # Get memory configuration
        memory_config = agentcore_config.get('memory', {})
        region = agentcore_config.get('aws', {}).get('region', 'us-east-1')
        
        # Create memory client
        _memory_client = MemoryClient(region_name=region)
        _memory_initialized = True
        
        logger.info("AgentCore Memory クライアントを初期化しました")
        return True
        
    except ImportError:
        logger.warning("bedrock_agentcore.memory が利用できません - Memory は無効です")
        return False
    except Exception as e:
        logger.error(f"Memory の初期化に失敗しました: {e}")
        return False

# ============================================================================
# CONTEXT RETRIEVAL
# ============================================================================

def get_conversation_context(session_id, actor_id, max_results=3):
    """
    AgentCore Memory API を使用して以前の会話コンテキストを取得する。

    Args:
        session_id (str): 会話のセッション ID
        actor_id (str): アクター ID（通常は "user"）
        max_results (int): 取得する以前のターンの最大数

    Returns:
        str: 会話コンテキスト、または利用できない場合は空の文字列
    """
    global _memory_client, _current_session_id
    
    if not _memory_initialized or not _memory_client or not session_id:
        return ""
    
    try:
        # Set current session if different
        if _current_session_id != session_id:
            _current_session_id = session_id
            logger.info(f"Memory セッションを開始しました: {session_id}")
        
        # Get memory ID from configuration
        agentcore_config, _ = load_configs()
        memory_config = agentcore_config.get('memory', {})
        memory_id = memory_config.get('id')
        
        if not memory_id:
            logger.info("設定に Memory ID が見つかりません - コンテキストは利用できません")
            return ""
        
        # Get last few conversation turns using AgentCore Memory API
        turns = _memory_client.get_last_k_turns(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            k=max_results
        )
        
        if turns:
            # DEBUG: Log the raw memory data to understand what's causing validation errors
            logger.info(f"DEBUG: メモリターンの構造: {len(turns)} ターン")
            for i, turn in enumerate(turns):
                logger.info(f"DEBUG: ターン {i}: {len(turn)} メッセージ")
                for j, message in enumerate(turn):
                    logger.info(f"DEBUG: ターン {i} メッセージ {j}: role={message.get('role')}, content_type={type(message.get('content'))}")
                    if isinstance(message.get('content'), dict):
                        logger.info(f"DEBUG: Content dict キー: {list(message.get('content', {}).keys())}")
                    
            # Format context from memory turns
            context_parts = []
            for turn in turns:
                turn_messages = []
                for message in turn:
                    role = message.get('role', 'unknown').upper()
                    # Handle content that might be a dict or string
                    content_raw = message.get('content', '')
                    if isinstance(content_raw, dict):
                        # If content is a dict, try to extract text from common fields
                        content = content_raw.get('text', str(content_raw))
                    else:
                        content = str(content_raw)
                    
                    content = content.strip()
                    if content:
                        turn_messages.append(f"{role}: {content}")
                
                if turn_messages:
                    context_parts.append(" → ".join(turn_messages))
            
            if context_parts:
                context = "\n".join(context_parts)
                logger.info(f"Memory から {len(turns)} 件の会話ターンを取得しました")
                return f"Previous conversation context:\n{context}\n"
        
        logger.info("Memory に以前のコンテキストが見つかりません")
        return ""
        
    except Exception as e:
        logger.error(f"会話コンテキストの取得に失敗しました: {e}")
        return ""

# ============================================================================
# CONVERSATION STORAGE
# ============================================================================

def save_conversation(session_id, user_message, assistant_response, actor_id="user"):
    """
    AgentCore Memory API を使用して会話ターンを Memory に保存する。

    Args:
        session_id (str): 会話のセッション ID
        user_message (str): ユーザーのメッセージ
        assistant_response (str): アシスタントのレスポンス
        actor_id (str): アクター ID（通常は "user"）
    """
    global _memory_client
    
    if not _memory_initialized or not _memory_client or not session_id:
        logger.info("Memory が利用できません - 会話は保存されません")
        return
    
    try:
        # Get memory ID from configuration
        agentcore_config, _ = load_configs()
        memory_config = agentcore_config.get('memory', {})
        memory_id = memory_config.get('id')
        
        if not memory_id:
            logger.warning("設定に Memory ID が見つかりません - 会話は保存されません")
            return
        
        # Create event with conversation messages using AgentCore Memory API
        messages = [
            (user_message, "USER"),
            (assistant_response, "ASSISTANT")
        ]
        
        result = _memory_client.create_event(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=messages,
            event_timestamp=datetime.now()
        )
        
        event_id = result.get('eventId', 'unknown')
        logger.info(f"会話を Memory に保存しました（event: {event_id}, session: {session_id}）")
        
    except Exception as e:
        logger.error(f"会話の保存に失敗しました: {e}")

# ============================================================================
# ERROR HANDLING
# ============================================================================

def is_memory_available():
    """
    Memory 機能が利用可能かどうかを確認する。

    Returns:
        bool: Memory が利用可能で初期化されている場合は True
    """
    return _memory_initialized and _memory_client is not None