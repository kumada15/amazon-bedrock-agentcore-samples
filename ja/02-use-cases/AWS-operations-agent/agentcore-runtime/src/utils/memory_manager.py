#!/usr/bin/env python3
"""
AgentCore Memory Manager

Amazon Bedrock AgentCore Memory を使用して AgentCore エージェントに短期メモリ機能を提供する。
会話のフローを維持するための会話コンテキストの保存と取得を処理する。
"""

# ============================================================================
# IMPORTS
# ============================================================================

import os
import sys
import yaml
import uuid
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from agent_shared import mylogger
 
logger = mylogger.get_logger()

try:
    from bedrock_agentcore.memory import MemoryClient
except ImportError:
    logger.warning("bedrock-agentcore がインストールされていません。Memory 機能は無効になります。")
    MemoryClient = None

# ============================================================================
# CLASSES
# ============================================================================

class MemoryManager:
    """AgentCore エージェントの短期メモリを管理するクラス"""

    def __init__(self, config_path: str = None):
        """設定を使用して Memory Manager を初期化する"""
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 
            'config'
        )
        self.config = self._load_config()
        self.memory_client = None
        self.memory_id = None
        self.session_id = None
        self._initialize_memory()
    
    def _load_config(self) -> Dict[str, Any]:
        """AgentCore 設定を読み込む"""
        try:
            config_file = os.path.join(self.config_path, 'agentcore-config.yaml')
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"設定ファイルが見つかりません: {config_file}。Memory 機能が制限される可能性があります。")
            return {}
        except yaml.YAMLError as e:
            logger.warning(f"設定ファイルの解析エラー: {e}。Memory 機能が制限される可能性があります。")
            return {}
    
    def _initialize_memory(self):
        """Memory クライアントとリソースを初期化する"""
        if MemoryClient is None:
            logger.info("Memory クライアントが利用できません。Memory の初期化をスキップします。")
            return
        
        try:
            region = self.config.get('aws', {}).get('region', 'us-east-1')
            self.memory_client = MemoryClient(region_name=region)
            
            # Try to find existing memory or create new one
            self._setup_memory_resource()
            
        except Exception as e:
            logger.error(f"Memory クライアントの初期化に失敗しました: {e}")
            self.memory_client = None
    
    def _setup_memory_resource(self):
        """エージェント用の Memory リソースをセットアップする"""
        if not self.memory_client:
            return
        
        try:
            # Look for existing memory with our naming convention
            memories = list(self.memory_client.list_memories())
            agent_memory = None
            
            for memory in memories:
                if memory.get('name') == 'AgentCoreConversationMemory':
                    agent_memory = memory
                    break
            
            if agent_memory:
                self.memory_id = agent_memory.get('id')
                logger.info(f"既存の Memory リソースを使用します: {self.memory_id}")
            else:
                # Create new short-term memory
                memory = self.memory_client.create_memory(
                    name="AgentCoreConversationMemory",
                    description="Short-term memory for AgentCore agent conversations"
                )
                self.memory_id = memory.get('id')
                logger.info(f"新しい Memory リソースを作成しました: {self.memory_id}")
                
        except Exception as e:
            logger.error(f"Memory リソースのセットアップに失敗しました: {e}")
            self.memory_client = None
    
    def start_session(self, session_id: str = None) -> str:
        """新しい会話セッションを開始する"""
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        return self.session_id
    
    def get_session_id(self) -> Optional[str]:
        """現在のセッション ID を取得する"""
        return self.session_id
    
    def store_conversation_turn(
        self,
        user_message: str,
        assistant_response: str,
        actor_id: str = "user",
        tool_calls: List[str] = None
    ) -> bool:
        """会話ターンを短期メモリに保存する"""
        if not self.memory_client or not self.memory_id or not self.session_id:
            return False
        
        try:
            # Build messages list for this turn
            messages = [
                (user_message, "USER"),
                (assistant_response, "ASSISTANT")
            ]
            
            # Add tool calls if any
            if tool_calls:
                for tool_call in tool_calls:
                    messages.insert(-1, (tool_call, "TOOL"))
            
            # Store in memory
            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=self.session_id,
                messages=messages
            )
            
            return True
            
        except Exception as e:
            logger.error(f"会話ターンの保存に失敗しました: {e}")
            return False
    
    def get_conversation_context(
        self,
        actor_id: str = "user",
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """短期メモリから会話コンテキストを取得する"""
        if not self.memory_client or not self.memory_id or not self.session_id:
            return []
        
        try:
            conversations = self.memory_client.list_events(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=self.session_id,
                max_results=max_results
            )
            
            return conversations if conversations else []
            
        except Exception as e:
            logger.error(f"会話コンテキストの取得に失敗しました: {e}")
            return []
    
    def format_context_for_agent(
        self,
        actor_id: str = "user",
        max_results: int = 5
    ) -> str:
        """エージェント入力用に会話コンテキストを文字列としてフォーマットする"""
        conversations = self.get_conversation_context(actor_id, max_results)
        
        if not conversations:
            return ""
        
        context_parts = ["Previous conversation context:"]
        
        try:
            for event in conversations:
                messages = event.get('messages', [])
                timestamp = event.get('createdAt', 'Unknown time')
                
                context_parts.append(f"\n[{timestamp}]")
                for message in messages:
                    content = message.get('content', '')
                    role = message.get('role', 'UNKNOWN')
                    
                    if role == "USER":
                        context_parts.append(f"User: {content}")
                    elif role == "ASSISTANT":
                        context_parts.append(f"Assistant: {content}")
                    elif role == "TOOL":
                        context_parts.append(f"Tool: {content}")
        
        except Exception as e:
            logger.error(f"コンテキストのフォーマットエラー: {e}")
            return ""
        
        return "\n".join(context_parts)
    
    def clear_session(self):
        """現在のセッションコンテキストをクリアする"""
        self.session_id = None
    
    def is_memory_available(self) -> bool:
        """Memory 機能が利用可能かどうかを確認する"""
        return self.memory_client is not None and self.memory_id is not None
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Memory 使用統計を取得する"""
        if not self.is_memory_available():
            return {"status": "unavailable", "reason": "Memory client not initialized"}
        
        try:
            # Get recent conversation count
            conversations = self.get_conversation_context(max_results=100)
            
            return {
                "status": "available",
                "memory_id": self.memory_id,
                "session_id": self.session_id,
                "conversation_count": len(conversations),
                "region": self.config.get('aws', {}).get('region', 'unknown')
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}