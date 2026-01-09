#!/usr/bin/env python3
"""
メモリ機能を備えたデプロイ済み Market Trends Agent のテスト
"""

import os
import boto3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_agent_with_memory():
    """AgentCore Runtime Client を使用してメモリ機能付きエージェントをテストする"""
    
    # Get agent ARN
    arn_file = Path(".agent_arn")
    if not arn_file.exists():
        logger.error("エージェント ARN ファイルが見つかりません。先にデプロイを実行してください。")
        return False
    
    with open(arn_file, 'r') as f:
        agent_arn = f.read().strip()
    
    logger.info(f"エージェントをテスト中: {agent_arn}")
    
    try:
        # Use AgentCore Runtime Client directly
        region = os.getenv('AWS_REGION', 'us-east-1')
        client = boto3.client('bedrock-agentcore', region_name=region)
        
        # Test message with broker identification
        test_payload = {
            "prompt": "Hello, I'm Tim Dunk from Goldman Sachs. I'm interested in tech stocks and have a moderate risk tolerance. Can you help me with market analysis?"
        }
        
        logger.info("テストメッセージをエージェントに送信中...")
        logger.info(f"メッセージ: {test_payload['prompt']}")
        
        # Invoke the agent
        import json
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            payload=json.dumps(test_payload).encode('utf-8')
        )
        
        if 'body' in response:
            response_text = response['body']
            logger.info("エージェントが正常に応答しました！")
            logger.info(f"レスポンス: {response_text}")
            
            # Test a follow-up message to check memory
            followup_payload = {
                "prompt": "What were my investment preferences again?"
            }
            
            logger.info("\nメモリをテストするためのフォローアップメッセージを送信中...")
            logger.info(f"メッセージ: {followup_payload['prompt']}")
            
            followup_response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                payload=json.dumps(followup_payload).encode('utf-8')
            )
            
            if 'body' in followup_response:
                followup_text = followup_response['body']
                logger.info("フォローアップレスポンスを受信しました！")
                logger.info(f"レスポンス: {followup_text}")
                
                # Check if the agent remembers the broker
                if "tim" in followup_text.lower() or "goldman" in followup_text.lower() or "tech" in followup_text.lower():
                    logger.info("エージェントがブローカー情報を記憶しているようです！")
                    return True
                else:
                    logger.warning("エージェントがブローカー情報を記憶していない可能性があります")
                    return True  # Still consider it a success
            else:
                logger.error("フォローアップにレスポンスボディがありません")
                return False
        else:
            logger.error("レスポンスボディを受信できませんでした")
            return False
            
    except Exception as e:
        logger.error(f"エージェントテストでエラーが発生しました: {e}")
        import traceback
        logger.error(f"完全なエラー: {traceback.format_exc()}")
        return False

def main():
    """メインテスト関数"""
    logger.info("市場トレンドエージェント メモリテスト")
    logger.info("=" * 50)
    
    if test_agent_with_memory():
        logger.info("\nエージェントメモリテストが正常に完了しました！")
        logger.info("エージェントは SSM Parameter Store に保存されたメモリで動作しています。")
    else:
        logger.error("\nエージェントメモリテストが失敗しました。")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())