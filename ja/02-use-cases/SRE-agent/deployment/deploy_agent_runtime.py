#!/usr/bin/env python3

import argparse
import json
import logging
import os
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# 設定定数
DELETION_WAIT_TIME = 150  # ランタイム削除後、再作成前に待機する秒数

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)


def _write_agent_arn_to_file(agent_arn: str, output_dir: str = None) -> None:
    """Agent ARN を .agent_arn ファイルに書き込みます。"""
    if output_dir is None:
        output_dir = Path(__file__).parent
    else:
        output_dir = Path(output_dir)

    arn_file = output_dir / ".agent_arn"

    try:
        with open(arn_file, "w") as f:
            f.write(agent_arn)
        logging.info(f"💾 Agent Runtime ARN saved to {arn_file}")
    except Exception as e:
        logging.error(f"Failed to write agent ARN to file: {e}")


def _get_agent_runtime_id_by_name(client: boto3.client, runtime_name: str) -> str:
    """名前で Agent Runtime ID を取得します。"""
    try:
        response = client.list_agent_runtimes()
        agent_runtimes = response.get("agentRuntimes", [])

        for runtime in agent_runtimes:
            if runtime["agentRuntimeName"] == runtime_name:
                return runtime["agentRuntimeId"]

        return None

    except ClientError as e:
        logging.error(f"Failed to get agent runtime ID: {e}")
        return None


def _delete_agent_runtime(client: boto3.client, runtime_id: str) -> bool:
    """ID で Agent Runtime を削除します。"""
    try:
        logging.info(f"Deleting agent runtime with ID: {runtime_id}")
        client.delete_agent_runtime(agentRuntimeId=runtime_id)
        logging.info("Agent runtime deleted successfully")
        return True

    except ClientError as e:
        logging.error(f"Failed to delete agent runtime: {e}")
        return False


def _list_existing_agent_runtimes(client: boto3.client) -> None:
    """既存のすべての Agent Runtime を一覧表示します。"""
    try:
        response = client.list_agent_runtimes()
        agent_runtimes = response.get("agentRuntimes", [])

        if not agent_runtimes:
            logging.info("No existing agent runtimes found.")
            return

        logging.info("Existing agent runtimes:")
        for runtime in agent_runtimes:
            logging.info(json.dumps(runtime, indent=2, default=str))

    except ClientError as e:
        logging.error(f"Failed to list agent runtimes: {e}")


def _create_agent_runtime(
    client: boto3.client,
    runtime_name: str,
    container_uri: str,
    role_arn: str,
    anthropic_api_key: str,
    gateway_access_token: str,
    llm_provider: str = "bedrock",
    force_recreate: bool = False,
) -> None:
    """競合エラー処理を含む Agent Runtime を作成します。"""
    # 環境変数を構築
    env_vars = {
        "GATEWAY_ACCESS_TOKEN": gateway_access_token,
        "LLM_PROVIDER": llm_provider,
    }

    # ANTHROPIC_API_KEY が存在する場合のみ追加
    if anthropic_api_key:
        env_vars["ANTHROPIC_API_KEY"] = anthropic_api_key

    # DEBUG 環境変数をチェック
    debug_mode = os.getenv("DEBUG", "false")
    if debug_mode.lower() in ("true", "1", "yes"):
        env_vars["DEBUG"] = "true"
        logging.info("エージェントランタイムのデバッグモードを有効化しました")

    # AgentCore に渡される環境変数をログ出力（機密データはマスク）
    logging.info("AgentCore Runtime に渡される環境変数:")
    for key, value in env_vars.items():
        if key in ["ANTHROPIC_API_KEY", "GATEWAY_ACCESS_TOKEN"]:
            masked_value = f"{'*' * 20}...{value[-8:] if len(value) > 8 else '***'}"
            logging.info(f"   {key}: {masked_value}")
        else:
            logging.info(f"   {key}: {value}")
    try:
        response = client.create_agent_runtime(
            agentRuntimeName=runtime_name,
            agentRuntimeArtifact={
                "containerConfiguration": {"containerUri": container_uri}
            },
            networkConfiguration={"networkMode": "PUBLIC"},
            roleArn=role_arn,
            environmentVariables=env_vars,
        )

        logging.info("Agent Runtime の作成に成功しました！")
        logging.info(f"Agent Runtime ARN: {response['agentRuntimeArn']}")
        logging.info(f"ステータス: {response['status']}")
        _write_agent_arn_to_file(response["agentRuntimeArn"])

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        # 競合以外のエラーは即座に処理
        if error_code != "ConflictException":
            logging.error(f"Agent Runtime の作成に失敗しました: {e}")
            raise

        # 競合処理 - ランタイムが既に存在
        logging.error(f"Agent Runtime '{runtime_name}' は既に存在します。")
        logging.info("既存の Agent Runtime を一覧表示:")
        _list_existing_agent_runtimes(client)

        # 強制再作成でない場合、ガイダンスを表示して終了
        if not force_recreate:
            logging.info(
                "--runtime-name パラメータで新しいエージェント名を指定するか、--force-recreate を使用して削除・再作成してください。"
            )
            return

        # 強制再作成シナリオを処理
        logging.info(
            "強制再作成が要求されました、既存のランタイムを削除中..."
        )
        runtime_id = _get_agent_runtime_id_by_name(client, runtime_name)

        if not runtime_id:
            logging.error(f"'{runtime_name}' のランタイム ID が見つかりませんでした")
            return

        if not _delete_agent_runtime(client, runtime_id):
            logging.error("既存のランタイムの削除に失敗しました")
            return

        # 削除の完了を待機
        logging.info(
            f"削除の完了を待機中... ({DELETION_WAIT_TIME} 秒)"
        )
        time.sleep(DELETION_WAIT_TIME)

        # 削除成功後にランタイムを再作成
        logging.info("Agent Runtime の再作成を試行中...")
        try:
            response = client.create_agent_runtime(
                agentRuntimeName=runtime_name,
                agentRuntimeArtifact={
                    "containerConfiguration": {"containerUri": container_uri}
                },
                networkConfiguration={"networkMode": "PUBLIC"},
                roleArn=role_arn,
                environmentVariables=env_vars,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                logging.error("\n" + "=" * 70)
                logging.error("エージェント名の競合 - AWS クリーンアップがまだ進行中")
                logging.error("=" * 70)
                logging.error(
                    f"{DELETION_WAIT_TIME} 秒待機しましたが、エージェント名"
                )
                logging.error(f"'{runtime_name}' はまだ利用できません。")
                logging.error("")
                logging.error(
                    "これは AWS 内部のクリーンアップ遅延です。以下のいずれかを試してください:"
                )
                logging.error("1. 1-2 分待ってからスクリプトを再実行")
                logging.error("2. 別のエージェント名を使用（例：タイムスタンプを追加）")
                logging.error(f"   ./deployment/build_and_deploy.sh {runtime_name}_v2")
                logging.error("=" * 70)
                print(
                    "\nAWS がエージェントの削除を完了するまで 1-2 分お待ちください。"
                )
                print("   その後、デプロイスクリプトを再実行してください。")
            raise

        logging.info("Agent Runtime の再作成に成功しました！")
        logging.info(f"Agent Runtime ARN: {response['agentRuntimeArn']}")
        logging.info(f"ステータス: {response['status']}")
        _write_agent_arn_to_file(response["agentRuntimeArn"])


def main():
    parser = argparse.ArgumentParser(
        description="Deploy SRE Agent to AgentCore Runtime"
    )
    parser.add_argument(
        "--runtime-name",
        default="sre-agent",
        help="Name for the agent runtime (default: sre-agent)",
    )
    parser.add_argument(
        "--container-uri",
        required=True,
        help="Container URI (e.g., account-id.dkr.ecr.us-west-2.amazonaws.com/my-agent:latest)",
    )
    parser.add_argument(
        "--role-arn", required=True, help="IAM role ARN for the agent runtime"
    )
    parser.add_argument(
        "--region", 
        default=os.environ.get("AWS_REGION", "us-east-1"), 
        help="AWS region (default: AWS_REGION env var or us-east-1)"
    )
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Delete existing runtime if it exists and recreate it",
    )

    args = parser.parse_args()

    # .env ファイルから環境変数を読み込み
    script_dir = Path(__file__).parent
    env_file = script_dir / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        logging.info(f"{env_file} から環境変数を読み込みました")
    else:
        logging.error(f".env ファイルが見つかりません: {env_file}")
        raise FileNotFoundError(
            f"{env_file} に GATEWAY_ACCESS_TOKEN（および任意で ANTHROPIC_API_KEY）を含む .env ファイルを作成してください"
        )

    # 環境変数を取得
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    gateway_access_token = os.getenv("GATEWAY_ACCESS_TOKEN")
    llm_provider = os.getenv("LLM_PROVIDER", "bedrock")

    # 環境変数の値をログ出力（機密データはマスク）
    logging.info("読み込んだ環境変数:")
    logging.info(f"   LLM_PROVIDER: {llm_provider}")
    if anthropic_api_key:
        logging.info(
            f"   ANTHROPIC_API_KEY: {'*' * 20}...{anthropic_api_key[-8:] if len(anthropic_api_key) > 8 else '***'}"
        )
    else:
        logging.info(
            "   ANTHROPIC_API_KEY: 未設定 - Amazon Bedrock がプロバイダーとして使用されます"
        )

    if gateway_access_token:
        logging.info(
            f"   GATEWAY_ACCESS_TOKEN: {'*' * 20}...{gateway_access_token[-8:] if len(gateway_access_token) > 8 else '***'}"
        )

    if not gateway_access_token:
        logging.error("GATEWAY_ACCESS_TOKEN が .env に見つかりません")
        raise ValueError("GATEWAY_ACCESS_TOKEN は .env で設定する必要があります")

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)

    _create_agent_runtime(
        client=client,
        runtime_name=args.runtime_name,
        container_uri=args.container_uri,
        role_arn=args.role_arn,
        anthropic_api_key=anthropic_api_key,
        gateway_access_token=gateway_access_token,
        llm_provider=llm_provider,
        force_recreate=args.force_recreate,
    )


if __name__ == "__main__":
    main()
