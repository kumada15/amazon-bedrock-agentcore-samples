#!/usr/bin/env python3

import argparse
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import boto3
from dotenv import load_dotenv

# sre_agent ディレクトリから環境変数を読み込み
load_dotenv(Path(__file__).parent.parent / "sre_agent" / ".env")

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _get_user_from_env() -> str:
    """環境変数から user_id を取得します。

    Returns:
        USER_ID 環境変数からの user_id、またはデフォルト値
    """
    user_id = os.getenv("USER_ID")
    if user_id:
        logger.info(f"環境変数から user_id を使用しています: {user_id}")
        return user_id
    else:
        # デフォルトの user_id にフォールバック
        default_user_id = "default-sre-user"
        logger.warning(
            f"USER_ID が環境変数に設定されていないため、デフォルトを使用: {default_user_id}"
        )
        return default_user_id


def _get_session_from_env(mode: str) -> str:
    """環境変数から session_id を取得するか、新しく生成します。

    Args:
        mode: 自動生成プレフィックス用の "interactive" または "prompt"

    Returns:
        SESSION_ID 環境変数からの session_id、または自動生成された値
    """
    session_id = os.getenv("SESSION_ID")
    if session_id:
        logger.info(f"環境変数から session_id を使用しています: {session_id}")
        return session_id
    else:
        # session_id を自動生成（最低 33 文字必要）
        import uuid

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4()).replace("-", "")[:12]  # 12 文字の UUID セグメント
        auto_session_id = f"{mode}-{timestamp}-{unique_id}"
        logger.info(
            f"SESSION_ID が環境変数に設定されていないため、自動生成: {auto_session_id}"
        )
        return auto_session_id


def main():
    parser = argparse.ArgumentParser(
        description="Invoke SRE Agent Runtime via AgentCore"
    )
    parser.add_argument("--prompt", required=True, help="Prompt to send to the agent")
    parser.add_argument(
        "--runtime-arn",
        help="Agent Runtime ARN (reads from .sre_agent_uri if not provided)",
    )
    parser.add_argument(
        "--region", 
        default=os.environ.get("AWS_REGION", "us-east-1"), 
        help="AWS region (default: AWS_REGION env var or us-east-1)"
    )
    parser.add_argument(
        "--session-id", help="Runtime session ID (generates one if not provided)"
    )

    args = parser.parse_args()

    # 提供されていない場合はファイルからランタイム ARN を取得
    runtime_arn = args.runtime_arn
    if not runtime_arn:
        script_dir = Path(__file__).parent

        # まず .agent_arn ファイルから読み取りを試みる（推奨）
        arn_file = script_dir / ".agent_arn"
        if arn_file.exists():
            runtime_arn = arn_file.read_text().strip()
            logging.info(f".agent_arn からランタイム ARN を使用: {runtime_arn}")
        else:
            # コンテナ URI から導出するフォールバック
            uri_file = script_dir / ".sre_agent_uri"
            if uri_file.exists():
                container_uri = uri_file.read_text().strip()
                # アカウント ID を抽出してランタイム ARN を構築
                # コンテナ URI 形式: account-id.dkr.ecr.region.amazonaws.com/repo:tag
                account_id = container_uri.split(".")[0]
                runtime_arn = f"arn:aws:bedrock-agentcore:{args.region}:{account_id}:runtime/sre-agent"
                logging.info(
                    f"コンテナ URI から導出したランタイム ARN を使用: {runtime_arn}"
                )
            else:
                logging.error(
                    "ランタイム ARN が提供されておらず、.agent_arn も .sre_agent_uri ファイルも見つかりません"
                )
                logging.error(
                    "--runtime-arn を指定するか、エージェントがデプロイされていることを確認してください"
                )
                return

    # 提供されていない場合はセッション ID を生成
    session_id = args.session_id
    if not session_id:
        timestamp = str(int(time.time()))
        session_id = f"sre-agent-session-{timestamp}-invoke"
        logging.info(f"セッション ID を生成しました: {session_id}")

    # セッション ID の長さを検証（33 文字以上必要）
    if len(session_id) < 33:
        session_id = session_id + "-" + "x" * (33 - len(session_id))
        logging.info(f"最小長を満たすためにセッション ID をパディングしました: {session_id}")

    # カスタムタイムアウトで AgentCore クライアントを作成
    from botocore.config import Config

    # 長時間実行されるエージェント操作に対応するため読み取りタイムアウトを増加
    config = Config(
        read_timeout=300,  # 5 分の読み取りタイムアウト（デフォルトは 60 秒）
        retries={"max_attempts": 3, "mode": "adaptive"},
    )

    agent_core_client = boto3.client(
        "bedrock-agentcore", region_name=args.region, config=config
    )

    # 環境変数から user_id と session_id を取得
    user_id = _get_user_from_env()
    env_session_id = _get_session_from_env("invoke")

    # 引数で提供されていない場合は環境変数の session_id を使用
    if not args.session_id:
        session_id = env_session_id

    # user_id と session_id を含むペイロードを準備
    payload = json.dumps(
        {"input": {"prompt": args.prompt, "user_id": user_id, "session_id": session_id}}
    )

    logging.info(f"エージェントランタイムを呼び出し中: {runtime_arn}")
    logging.info(f"セッション ID: {session_id}")
    logging.info(f"プロンプト: {args.prompt}")

    try:
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=payload,
            qualifier="DEFAULT",
        )

        response_body = response["response"].read()
        response_data = json.loads(response_body)

        logging.info("エージェントレスポンス:")
        print(json.dumps(response_data, indent=2))

        # メッセージを個別に抽出して表示
        if "output" in response_data and "message" in response_data["output"]:
            print("\nメッセージ:")
            print(response_data["output"]["message"])

    except Exception as e:
        logging.error(f"エージェントランタイムの呼び出しに失敗しました: {e}")
        raise


if __name__ == "__main__":
    main()
