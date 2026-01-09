#!/usr/bin/env python3
"""
メモリデプロイメントとエージェント機能を検証するためのテストスクリプト
"""

import os
import sys
import boto3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ssm_memory_parameter():
    """メモリ ARN が SSM Parameter Store に保存されているかテストする"""
    logger.info("SSM メモリパラメータをテスト中...")

    region = os.getenv("AWS_REGION", "us-east-1")
    ssm_client = boto3.client("ssm", region_name=region)
    param_name = "/bedrock-agentcore/market-trends-agent/memory-arn"

    try:
        response = ssm_client.get_parameter(Name=param_name)
        memory_arn = response["Parameter"]["Value"]
        logger.info(f"SSM でメモリ ARN を発見: {memory_arn}")

        # Validate ARN format
        if (
            memory_arn.startswith("arn:aws:bedrock-agentcore:")
            and "memory/" in memory_arn
        ):
            logger.info("メモリ ARN フォーマットは有効です")
            return memory_arn
        else:
            logger.error(f"無効なメモリ ARN フォーマット: {memory_arn}")
            return None

    except ssm_client.exceptions.ParameterNotFound:
        logger.error("SSM Parameter Store にメモリ ARN が見つかりません")
        return None
    except Exception as e:
        logger.error(f"メモリ ARN の取得中にエラーが発生しました: {e}")
        return None


def test_memory_access():
    """SSM パラメータを使用してメモリにアクセスできるかテストする"""
    logger.info("メモリアクセスをテスト中...")

    try:
        # Import the memory function
        sys.path.append(str(Path(__file__).parent))
        from tools.memory_tools import get_memory_from_ssm

        # Try to get memory client and ID
        memory_client, memory_id = get_memory_from_ssm()
        logger.info(f"メモリを正常に取得しました: {memory_id}")

        # Test listing memories to verify access
        memories = memory_client.list_memories()
        logger.info(f"メモリクライアントが動作中 - 合計 {len(memories)} 件のメモリを発見")

        return True

    except Exception as e:
        logger.error(f"メモリアクセス中にエラーが発生しました: {e}")
        return False


def test_agent_runtime():
    """エージェントランタイムがデプロイされアクセス可能かテストする"""
    logger.info("エージェントランタイムをテスト中...")

    # Check if agent ARN file exists
    arn_file = Path(".agent_arn")
    if not arn_file.exists():
        logger.error("エージェント ARN ファイルが見つかりません")
        return False

    try:
        with open(arn_file, "r") as f:
            agent_arn = f.read().strip()

        logger.info(f"エージェント ARN を発見: {agent_arn}")

        # Validate ARN format
        if (
            agent_arn.startswith("arn:aws:bedrock-agentcore:")
            and "runtime/" in agent_arn
        ):
            logger.info("エージェント ARN フォーマットは有効です")
            return agent_arn
        else:
            logger.error(f"無効なエージェント ARN フォーマット: {agent_arn}")
            return None

    except Exception as e:
        logger.error(f"エージェント ARN の読み取り中にエラーが発生しました: {e}")
        return None


def test_agent_invocation():
    """AgentCore Runtime 経由でエージェントを呼び出すテスト"""
    logger.info("AgentCore Runtime 経由でエージェント呼び出しをテスト中...")

    try:
        # Get agent ARN
        arn_file = Path(".agent_arn")
        if not arn_file.exists():
            logger.error("エージェント ARN ファイルが見つかりません")
            return False

        with open(arn_file, "r") as f:
            agent_arn = f.read().strip()

        # Use boto3 bedrock-agentcore client to invoke
        import boto3
        import json

        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("bedrock-agentcore", region_name=region)

        # Test with a simple message
        test_payload = {
            "prompt": "Hello, I'm Tim Dunk from Goldman Sachs. Can you help me with market analysis?"
        }

        logger.info("デプロイ済みエージェントにテストメッセージを送信中...")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, payload=json.dumps(test_payload).encode("utf-8")
        )

        if response and "response" in response:
            # Read the streaming body
            response_body = response["response"].read().decode("utf-8")
            if response_body and len(response_body.strip()) > 0:
                logger.info("エージェントが AgentCore Runtime 経由で正常に応答しました")
                logger.info(f"レスポンスプレビュー: {response_body[:200]}...")
                return True
            else:
                logger.error("エージェントが空のレスポンスボディを返しました")
                logger.info(f"ステータスコード: {response.get('statusCode')}")
                return False
        else:
            logger.error("エージェントがレスポンスを返しませんでした")
            logger.info(f"完全なレスポンス: {response}")
            return False

    except Exception as e:
        logger.error(f"ランタイム経由でのエージェント呼び出し中にエラーが発生しました: {e}")
        logger.warning(
            "エージェント呼び出しが失敗しました - エージェントが正しくデプロイされていない可能性があります"
        )
        return False


def main():
    """すべてのテストを実行する"""
    logger.info("Market Trends Agent メモリデプロイメントテスト")
    logger.info("=" * 60)

    tests_passed = 0
    total_tests = 4

    # Test 1: SSM Parameter
    memory_arn = test_ssm_memory_parameter()
    if memory_arn:
        tests_passed += 1

    logger.info("-" * 60)

    # Test 2: Memory Access
    if test_memory_access():
        tests_passed += 1

    logger.info("-" * 60)

    # Test 3: Agent Runtime
    agent_arn = test_agent_runtime()
    if agent_arn:
        tests_passed += 1

    logger.info("-" * 60)

    # Test 4: Agent Invocation
    if test_agent_invocation():
        tests_passed += 1

    logger.info("=" * 60)
    logger.info(f"テスト結果: {tests_passed}/{total_tests} 件のテストが合格")

    if tests_passed == total_tests:
        logger.info("すべてのテストに合格しました！メモリデプロイメントは正常に動作しています。")
        logger.info(
            "エージェントは SSM Parameter Store に保存されたメモリで使用できる状態です。"
        )
    else:
        logger.error(
            f"{total_tests - tests_passed} 件のテストが失敗しました。デプロイメントを確認してください。"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
