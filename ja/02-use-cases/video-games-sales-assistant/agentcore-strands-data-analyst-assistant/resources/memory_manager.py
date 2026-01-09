#!/usr/bin/env python3
"""
Bedrock AgentCore 用メモリマネージャー

このモジュールは、Strands データアナリストアシスタント用のメモリリソースの作成と管理を行います。
Bedrock AgentCore Memory Client を使用してメモリリソースを作成・取得する機能を提供します。

使用方法:
    python3 memory_manager.py create <memory_name> <parameter_store_name>
    python3 memory_manager.py list
"""

import sys
import logging
import boto3
from typing import Dict, Any, Optional, List
from bedrock_agentcore.memory import MemoryClient
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MEMORY_NAME = "AssistantAgentMemory"
DEFAULT_EXPIRY_DAYS = 7

def create_memory(memory_name: str = DEFAULT_MEMORY_NAME, expiry_days: int = DEFAULT_EXPIRY_DAYS,
                 parameter_store_name: Optional[str] = None) -> Optional[str]:
    """
    エージェント用の新しいメモリリソースを作成し、メモリ ID をパラメータストアに保存する

    Args:
        memory_name (str): メモリリソースの名前
        expiry_days (int): 短期メモリの保持期間
        parameter_store_name (str): メモリ ID を更新するパラメータストアの名前

    Returns:
        str: 成功した場合はメモリ ID、それ以外は None
    """
    logger.info(f"メモリリソースを作成中: {memory_name}")
    client = MemoryClient()
    
    try:
        # Create memory resource for short-term conversation storage
        memory = client.create_memory_and_wait(
            name=memory_name,
            strategies=[],  # No strategies means only short-term memory is used
            description="Short-term memory for data analyst assistant",
            event_expiry_days=expiry_days,  # Retention period for short-term memory (up to 365 days)
        )
        memory_id = memory['id']
        logger.info(f"メモリを作成しました: {memory_id}")
        
        # Store memory ID in parameter store if parameter_store_name is provided
        if parameter_store_name:
            try:
                ssm_client = boto3.client('ssm')
                ssm_client.put_parameter(
                    Name=parameter_store_name,
                    Value=memory_id,
                    Type='String',
                    Overwrite=True
                )
                logger.info(f"メモリ ID をパラメータストアに保存しました: {parameter_store_name}")
            except Exception as e:
                logger.error(f"メモリ ID のパラメータストアへの保存に失敗しました: {e}")
        
        return memory_id
    except ClientError as e:
        logger.info(f"エラー: {e}")
        return None
    except Exception as e:
        # Log any errors during memory creation
        logger.error(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return None

def list_memories() -> List[Dict[str, Any]]:
    """
    利用可能なすべてのメモリリソースを一覧表示する

    Returns:
        List[Dict]: メモリリソースのリスト
    """
    logger.info("メモリリソースを一覧表示中...")
    client = MemoryClient()
    
    try:
        memories = client.list_memories()
        logger.info(f"{len(memories)} 件のメモリリソースが見つかりました:")
        
        if memories:
            print("\n📋 メモリリソース:")
            print("-" * 60)
            for i, memory in enumerate(memories, 1):
                memory_id = memory.get('id', 'N/A')
                memory_name = memory.get('name', 'N/A')
                status = memory.get('status', 'N/A')
                created_time = memory.get('createdTime', 'N/A')

                print(f"{i}. 名前: {memory_name}")
                print(f"   ID: {memory_id}")
                print(f"   ステータス: {status}")
                print(f"   作成日時: {created_time}")
                print("-" * 60)
        else:
            print("メモリリソースが見つかりませんでした。")
            
        return memories
    except Exception as e:
        logger.error(f"メモリ一覧表示エラー: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    """コマンドライン引数を処理するメイン関数"""
    if len(sys.argv) < 2:
        print("使用方法: python3 memory_manager.py [create|list]")
        print("  create <memory_name> <parameter_store_name> - 新しいメモリリソースを作成")
        print("  list   - 既存のすべてのメモリリソースを一覧表示")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == 'create':
        if len(sys.argv) != 4:
            print("使用方法: python3 memory_manager.py create <memory_name> <parameter_store_name>")
            print("  <memory_name> - メモリリソースの名前")
            print("  <parameter_store_name> - メモリ ID を更新するパラメータストアの名前")
            sys.exit(1)
            
        memory_name = sys.argv[2]
        parameter_store_name = sys.argv[3]
        
        print(f"🚀 メモリリソースを作成中: {memory_name}")
        print(f"📝 パラメータストア名: {parameter_store_name}")
        
        memory_id = create_memory(memory_name=memory_name, parameter_store_name=parameter_store_name)
        if memory_id:
            print(f"✅ メモリが正常に作成されました！")
            print(f"メモリ ID: {memory_id}")
            print(f"パラメータストアに保存されたメモリ ID: {parameter_store_name}")
        else:
            print("❌ メモリの作成に失敗しました")
            sys.exit(1)
    elif action == 'list':
        print("📋 メモリリソースを一覧表示中...")
        memories = list_memories()
        if not memories:
            print("メモリが見つからないか、エラーが発生しました")
    else:
        print(f"❌ 不明なアクション: {action}")
        print("利用可能なアクション: create, list")
        sys.exit(1)

if __name__ == "__main__":
    main()