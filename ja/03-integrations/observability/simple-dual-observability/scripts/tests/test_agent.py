#!/usr/bin/env python3
"""
デプロイされた AgentCore Runtime エージェントをテストする。

このスクリプトはテストプロンプトでエージェントを呼び出し、レスポンスを表示する。
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Test prompts for different tools
TEST_PROMPTS: dict[str, str] = {
    "weather": "What's the weather like in Seattle?",
    "time": "What time is it in Tokyo?",
    "calculator": "What is 25 times 8?",
    "combined": "What's the weather in Paris and what time is it there?",
}


def _load_agent_metadata(script_dir: Path) -> dict[str, Any]:
    """デプロイメントメタデータファイルからエージェントメタデータを読み込む。

    Args:
        script_dir: スクリプトディレクトリのパス

    Returns:
        エージェントメタデータの辞書

    Raises:
        FileNotFoundError: デプロイメントメタデータが見つからない場合
    """
    metadata_file = script_dir / ".deployment_metadata.json"

    if metadata_file.exists():
        with open(metadata_file) as f:
            return json.load(f)
    else:
        raise FileNotFoundError(
            "No deployment metadata found. Deploy the agent first with: ./deploy_agent.sh"
        )


def _invoke_agent(
    agent_arn: str, prompt: str, region: str, session_id: str | None = None
) -> dict[str, Any]:
    """プロンプトでエージェントを呼び出す。

    Args:
        agent_arn: エージェントの ARN
        prompt: 送信するプロンプト
        region: AWS リージョン
        session_id: 会話コンテキスト用のオプションのセッション ID

    Returns:
        エージェントからのレスポンス

    Raises:
        RuntimeError: エージェントが見つからない場合、またはアクセスが拒否された場合
    """
    import uuid

    client = boto3.client("bedrock-agentcore", region_name=region)

    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        # Prepare payload
        payload = json.dumps({"prompt": prompt})

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, runtimeSessionId=session_id, payload=payload
        )

        # Parse response - handle StreamingBody
        agent_response = None
        if "response" in response:
            response_body = response["response"]

            # Handle StreamingBody
            if hasattr(response_body, "read"):
                raw_data = response_body.read()
                if isinstance(raw_data, bytes):
                    agent_response = raw_data.decode("utf-8")
                else:
                    agent_response = str(raw_data)
            elif isinstance(response_body, str):
                agent_response = response_body

        return {"response": agent_response, "session_id": session_id, "raw_response": response}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "ResourceNotFoundException":
            raise RuntimeError(
                f"Agent not found: {agent_arn}\n"
                f"Make sure the agent is deployed and the ARN is correct."
            ) from e
        elif error_code == "AccessDeniedException":
            raise RuntimeError(
                "Access denied when invoking agent.\n"
                "Make sure your IAM role has bedrock-agentcore:InvokeAgentRuntime permission."
            ) from e
        else:
            raise RuntimeError(f"Failed to invoke agent: {error_msg}") from e


def _display_response(response: dict[str, Any], show_full: bool = False) -> None:
    """エージェントレスポンスを表示する。

    Args:
        response: エージェントからのレスポンス辞書
        show_full: 完全な生のレスポンスを表示するかどうか
    """
    logger.info("=" * 70)
    logger.info("エージェントレスポンス")
    logger.info("=" * 70)

    # Extract response text
    if "response" in response and response["response"]:
        logger.info("\n%s\n", response["response"])
    else:
        logger.info("生のレスポンス:\n%s", json.dumps(response, indent=2, default=str))

    # Show session ID
    if "session_id" in response:
        logger.info("セッション ID: %s", response["session_id"])

    # Show full raw response if requested
    if show_full and "raw_response" in response:
        logger.info("\n完全な生のレスポンス:")
        logger.info(json.dumps(response["raw_response"], indent=2, default=str))

    logger.info("=" * 70)


def _run_interactive_mode(agent_arn: str, region: str) -> None:
    """インタラクティブテストモードを実行する。

    Args:
        agent_arn: エージェントの ARN
        region: AWS リージョン
    """
    logger.info("=" * 70)
    logger.info("インタラクティブモード")
    logger.info("=" * 70)
    logger.info("プロンプトを入力して Enter を押してください。")
    logger.info("終了するには 'quit' または 'exit' と入力してください。")
    logger.info("利用可能なテストプロンプトを表示するには 'test' と入力してください。")
    logger.info("=" * 70)
    logger.info("")

    while True:
        try:
            prompt = input("\n🤖 Prompt: ").strip()

            if not prompt:
                continue

            if prompt.lower() in ["quit", "exit", "q"]:
                logger.info("インタラクティブモードを終了します。")
                break

            if prompt.lower() == "test":
                logger.info("\n利用可能なテストプロンプト:")
                for name, test_prompt in TEST_PROMPTS.items():
                    logger.info("  %s: %s", name, test_prompt)
                continue

            logger.info("\nエージェントを呼び出し中...")
            response = _invoke_agent(agent_arn, prompt, region)
            _display_response(response)

        except KeyboardInterrupt:
            logger.info("\n\nインタラクティブモードを終了します。")
            break
        except Exception as e:
            logger.error("エラー: %s", str(e))


def main() -> None:
    """エージェントテストのメインエントリポイント。

    コマンドライン引数を解析し、指定されたモードでエージェントをテストする。
    """
    parser = argparse.ArgumentParser(
        description="Test the deployed AgentCore Runtime agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Run a specific test prompt
    uv run python -m scripts.test_agent --test weather

    # Run a custom prompt
    uv run python -m scripts.test_agent --prompt "What is 100 divided by 4?"

    # Interactive mode
    uv run python -m scripts.test_agent --interactive

    # Show full response including traces
    uv run python -m scripts.test_agent --test combined --full

Available test prompts:
    weather   - Test weather tool
    time      - Test time tool
    calculator - Test calculator tool
    combined  - Test multiple tools
""",
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )

    parser.add_argument(
        "--agent-id",
        help="Agent ID (if not provided, reads from deployment metadata)",
    )

    parser.add_argument(
        "--test",
        choices=list(TEST_PROMPTS.keys()),
        help="Run a predefined test prompt",
    )

    parser.add_argument(
        "--prompt",
        help="Custom prompt to test",
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full response including traces",
    )

    args = parser.parse_args()

    # Get script directory (parent of tests/)
    script_dir = Path(__file__).parent.parent

    # Load agent metadata
    try:
        metadata = _load_agent_metadata(script_dir)
        agent_arn = args.agent_id or metadata.get("agent_arn")
        region = args.region or metadata.get("region", "us-east-1")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    if not agent_arn:
        logger.error("エージェント ARN が見つかりません。まずエージェントをデプロイしてください。")
        sys.exit(1)

    logger.info("エージェントをテスト中: %s", agent_arn)
    logger.info("リージョン: %s", region)
    logger.info("")

    # Run in interactive mode
    if args.interactive:
        _run_interactive_mode(agent_arn, region)
        return

    # Determine which prompt to use
    if args.test:
        prompt = TEST_PROMPTS[args.test]
        logger.info("テストを実行中: %s", args.test)
    elif args.prompt:
        prompt = args.prompt
        logger.info("カスタムプロンプトを実行中")
    else:
        logger.error("--test、--prompt、または --interactive を指定する必要があります")
        parser.print_help()
        sys.exit(1)

    logger.info("プロンプト: %s", prompt)
    logger.info("")

    # Invoke the agent
    try:
        response = _invoke_agent(agent_arn, prompt, region)
        _display_response(response, show_full=args.full)
    except Exception as e:
        logger.error("エージェントのテストに失敗: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
