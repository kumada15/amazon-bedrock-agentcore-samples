"""
デュアルプラットフォームサポートを備えたシンプルな AgentCore オブザーバビリティデモ。

このデモでは、Amazon Bedrock AgentCore の自動 OpenTelemetry インストルメンテーションが
AWS ネイティブの CloudWatch とパートナープラットフォーム Braintrust の両方で
どのように機能するかを示します。

アーキテクチャ:
    ローカルスクリプト（このファイル）
        ↓ boto3 API 呼び出し
    AgentCore Runtime（マネージドサービス）
        ↓ 自動 OTEL でのエージェント実行
    MCP ツール（天気、時刻、電卓）
        ↓ トレースのエクスポート
    CloudWatch（GenAI Observability または APM） + Braintrust

エージェントは AgentCore Runtime（エージェントをホスティングするフルマネージドサービス）で実行されます。
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Constants
DEFAULT_REGION: str = "us-east-1"
DEFAULT_TIMEOUT: int = 300


def _get_env_var(var_name: str, default: str | None = None, required: bool = False) -> str | None:
    """
    オプションのデフォルト値と必須チェック付きで環境変数を取得します。

    Args:
        var_name: 環境変数の名前
        default: 見つからない場合のデフォルト値
        required: 見つからずデフォルトもない場合にエラーを発生させるかどうか

    Returns:
        環境変数の値またはデフォルト

    Raises:
        ValueError: 必須で見つからない場合
    """
    value = os.getenv(var_name, default)

    if required and value is None:
        raise ValueError(
            f"Required environment variable '{var_name}' not found. "
            f"Set it via environment or command-line argument."
        )

    return value


def _load_deployment_metadata() -> dict[str, Any] | None:
    """
    .deployment_metadata.json からエージェントデプロイメントメタデータを読み込みます。

    Returns:
        デプロイメントメタデータ辞書、またはファイルが存在しない場合は None
    """
    metadata_file = Path("scripts/.deployment_metadata.json")

    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"デプロイメントメタデータの読み込みに失敗: {e}")
            return None
    return None


def _is_braintrust_enabled(metadata: dict[str, Any] | None) -> bool:
    """
    デプロイされたエージェントで Braintrust オブザーバビリティが有効かどうかを確認します。

    Args:
        metadata: デプロイメントメタデータ辞書

    Returns:
        Braintrust が有効な場合は True、そうでない場合は False
    """
    if metadata is None:
        return False

    return metadata.get("braintrust_enabled", False)


def _create_bedrock_client(region: str) -> boto3.client:
    """
    Amazon Bedrock AgentCore クライアントを作成します。

    Args:
        region: AWS リージョン

    Returns:
        設定済みの boto3 クライアント
    """
    try:
        client = boto3.client("bedrock-agentcore", region_name=region)
        logger.info(f"Bedrock AgentCore クライアントを作成: リージョン {region}")
        return client

    except Exception as e:
        logger.exception(f"Bedrock クライアントの作成に失敗: {e}")
        raise


def _generate_session_id() -> str:
    """
    トレース相関用の一意のセッション ID を生成します。

    bedrock-agentcore API ではセッション ID は最小 33 文字必要です。

    Returns:
        UUID ベースのセッション ID（36 文字）
    """
    session_id = str(uuid.uuid4())
    logger.debug(f"セッション ID を生成: {session_id}")
    return session_id


def _invoke_agent(
    client: boto3.client, agent_arn: str, query: str, session_id: str, enable_trace: bool = True
) -> dict[str, Any]:
    """
    自動 OTEL インストルメンテーションで AgentCore Runtime エージェントを呼び出します。

    エージェントは AgentCore Runtime（マネージドサービス）で自動 OpenTelemetry
    トレーシングとともに実行されます。トレースは CloudWatch（GenAI Observability
    または APM 経由）と Braintrust（設定されている場合）の両方にエクスポートされます。

    Args:
        client: Bedrock AgentCore クライアント
        agent_arn: デプロイされたエージェントランタイムの ARN
        query: ユーザークエリ
        session_id: 相関用のセッション ID
        enable_trace: 詳細トレースを有効にする（現在の API では未使用）

    Returns:
        出力とメタデータを含むエージェントレスポンス

    Raises:
        ClientError: エージェント呼び出しが失敗した場合
    """
    logger.info(f"エージェントを呼び出し中: {agent_arn}")
    logger.info(f"クエリ: {query}")
    logger.info(f"セッション ID: {session_id}")

    start_time = time.time()

    try:
        # Prepare payload
        payload = json.dumps({"prompt": query})

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, runtimeSessionId=session_id, payload=payload
        )

        elapsed_time = time.time() - start_time
        logger.info(f"エージェントのレスポンスを受信: {elapsed_time:.2f} 秒")

        # Parse response - handle StreamingBody
        agent_response = None
        if "response" in response:
            response_body = response["response"]

            if hasattr(response_body, "read"):
                raw_data = response_body.read()
                if isinstance(raw_data, bytes):
                    agent_response = raw_data.decode("utf-8")
                else:
                    agent_response = str(raw_data)
            elif isinstance(response_body, str):
                agent_response = response_body

        return {
            "output": agent_response or "",
            "trace_id": response.get("traceId", ""),
            "session_id": session_id,
            "elapsed_time": elapsed_time,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(f"エージェントの呼び出しに失敗: {error_code} - {error_message}")
        raise

    except Exception as e:
        logger.exception(f"エージェント呼び出し中に予期しないエラー: {e}")
        raise


def _print_result(result: dict[str, Any], scenario_name: str) -> None:
    """
    エージェント呼び出し結果をフォーマットされた出力で表示します。

    Args:
        result: エージェントレスポンス辞書
        scenario_name: コンテキスト用のシナリオ名
    """
    print("\n" + "=" * 80)
    print(f"SCENARIO: {scenario_name}")
    print("=" * 80)
    print(f"\nOutput:\n{result['output']}\n")
    print(f"Trace ID: {result['trace_id']}")
    print(f"Session ID: {result['session_id']}")
    print(f"Elapsed Time: {result['elapsed_time']:.2f}s")
    print("\n" + "=" * 80 + "\n")


def _print_observability_links(region: str, trace_id: str) -> None:
    """
    トレース確認用のオブザーバビリティプラットフォームへのリンクを表示します。

    Args:
        region: AWS リージョン
        trace_id: 検索するトレース ID
    """
    print("\n表示: トレースの確認先:")
    print("\n1. CloudWatch GenAI Observability（推奨）:")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#cloudwatch-home:")
    print("   GenAI Observability > Bedrock AgentCoreに移動")
    print("   Agentsでメトリクスを、Sessions > Tracesでトレースを確認")
    print("   またはAPM > Serversでモニタリングするエージェントを選択")

    print("\n2. Braintrust Dashboard:")
    print("   https://www.braintrust.dev/app")

    print("\n3. CloudWatch Logs:")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups")
    print("   セッションIDまたはトレースIDでフィルタ\n")


def scenario_success(
    client: boto3.client, agent_arn: str, region: str, braintrust_enabled: bool = False
) -> None:
    """
    シナリオ 1: マルチツールクエリの成功。

    デモ内容:
    - 複数ツール（天気 + 時刻）を選択するエージェント
    - 成功したツール実行
    - レスポンスの集約
    - すべてのスパンを含むクリーンなトレース

    期待されるトレース:
    - エージェント呼び出しスパン
    - ツール選択スパン
    - ツール実行スパン（天気、時刻）
    - レスポンスフォーマットスパン

    Args:
        client: Bedrock AgentCore クライアント
        agent_arn: デプロイされたエージェントの ARN
        region: AWS リージョン
        braintrust_enabled: Braintrust オブザーバビリティが有効かどうか
    """
    logger.info("シナリオ 1 を開始: マルチツールクエリの成功")

    session_id = _generate_session_id()
    query = "What's the weather in Seattle and what time is it there?"

    result = _invoke_agent(client=client, agent_arn=agent_arn, query=query, session_id=session_id)

    _print_result(result, "Scenario 1: Successful Multi-Tool Query")
    _print_observability_links(region, result["trace_id"])

    print("✓ CloudWatch GenAI Observabilityで期待される内容:")
    print("   - エージェント呼び出しスパン")
    print("   - ツール選択スパン（推論）")
    print("   - ツール実行スパン: weatherツール、timeツール")
    print("   - 合計レイテンシ: 約1-2秒")

    if braintrust_enabled:
        print("\n✓ Braintrustで期待される内容:")
        print("   - LLM呼び出しの詳細（モデル、トークン、コスト）")
        print("   - ツール実行タイムライン")
        print("   - コンポーネント別レイテンシ内訳")
        print("   - View at: https://www.braintrust.dev/app")
    else:
        print("\n⚠ Braintrust連携:")
        print("   - このデプロイでは設定されていません")
        print("   - 有効にするには: --braintrust-api-keyと--braintrust-project-idを指定して再デプロイ")
        print("   - セットアップ手順はREADME.mdを参照してください")


def scenario_error(
    client: boto3.client, agent_arn: str, region: str, braintrust_enabled: bool = False
) -> None:
    """
    シナリオ 2: エラーハンドリングのデモンストレーション。

    デモ内容:
    - 電卓ツールを正しく選択するエージェント
    - エラーを返すツール（無効な入力）
    - スパンを通じたエラー伝播
    - 優雅なエラーハンドリング

    期待されるトレース:
    - エージェント呼び出しスパン
    - ツール選択スパン
    - ツール実行スパン（電卓）- ERROR
    - スパン属性内のエラー詳細

    Args:
        client: Bedrock AgentCore クライアント
        agent_arn: デプロイされたエージェントの ARN
        region: AWS リージョン
        braintrust_enabled: Braintrust オブザーバビリティが有効かどうか
    """
    logger.info("シナリオ 2 を開始: エラーハンドリング")

    session_id = _generate_session_id()
    query = "Calculate the factorial of -5"

    result = _invoke_agent(client=client, agent_arn=agent_arn, query=query, session_id=session_id)

    _print_result(result, "Scenario 2: Error Handling")
    _print_observability_links(region, result["trace_id"])

    print("✓ CloudWatch GenAI Observabilityで期待される内容:")
    print("   - エラースパンが赤でハイライト表示")
    print("   - 属性にエラーステータスコードとメッセージ")
    print("   - Calculatorツールスパンで失敗を表示")
    print("   - エージェントがエラーを適切に処理")

    if braintrust_enabled:
        print("\n✓ Braintrustで期待される内容:")
        print("   - 詳細情報付きのエラーフラグ")
        print("   - 失敗率メトリクスが更新")
        print("   - エラーの分類と追跡")
        print("   - View at: https://www.braintrust.dev/app")
    else:
        print("\n⚠ Braintrust連携:")
        print("   - このデプロイでは設定されていません")
        print("   - 有効にするには: --braintrust-api-keyと--braintrust-project-idを指定して再デプロイ")
        print("   - セットアップ手順はREADME.mdを参照してください")


def scenario_dashboard(region: str, braintrust_enabled: bool = False) -> None:
    """
    シナリオ 3: ダッシュボードの解説。

    事前設定済みダッシュボードで確認すべき内容:
    - CloudWatch: リクエストレート、レイテンシ、エラー、トークン使用量
    - Braintrust: LLM 固有のメトリクス、品質スコア（有効な場合）

    Args:
        region: AWS リージョン
        braintrust_enabled: Braintrust オブザーバビリティが有効かどうか
    """
    logger.info("シナリオ 3 を開始: ダッシュボードの解説")

    print("\n" + "=" * 80)
    print("SCENARIO: Dashboard Walkthrough")
    print("=" * 80)

    print("\n表示: CloudWatchダッシュボード:")
    print(f"   https://console.aws.amazon.com/cloudwatch/home?region={region}#dashboards:")
    print("\n   Key Metrics to Review:")
    print("   1. リクエストレート（リクエスト/分）")
    print("   2. レイテンシ分布（P50、P90、P99）")
    print("   3. ツール別エラー率")
    print("   4. 時間経過によるトークン消費量")
    print("   5. クエリタイプ別成功率")

    if braintrust_enabled:
        print("\n✓ Braintrustダッシュボード:")
        print("   https://www.braintrust.dev/app")
        print("\n   Key Metrics to Review:")
        print("   1. LLMコスト追跡（呼び出しごと）")
        print("   2. モデルパフォーマンスメトリクス")
        print("   3. 品質スコアと評価")
        print("   4. プロンプト/レスポンス分析")
        print("   5. トークン使用量の内訳")
    else:
        print("\n⚠ Braintrustダッシュボード（未設定）:")
        print("   https://www.braintrust.dev/app")
        print("\n   Braintrustオブザーバビリティを有効にするには:")
        print("   1. Braintrust APIキーを取得: https://www.braintrust.dev/app/settings/api-keys")
        print("   2. BraintrustプロジェクトURLからプロジェクトIDを取得")
        print(
            "   3. Redeploy agent with: scripts/deploy_agent.sh --braintrust-api-key KEY --braintrust-project-id ID"
        )
        print("\n   詳細なセットアップ手順はREADME.mdを参照してください")

    print("\n" + "=" * 80 + "\n")


def main() -> None:
    """
    オブザーバビリティデモのメインエントリーポイント。

    3 つのシナリオをサポート:
    1. success - 成功した実行を伴うマルチツールクエリ
    2. error - エラーハンドリングのデモンストレーション
    3. dashboard - ダッシュボードの解説
    4. all - すべてのシナリオを順次実行
    """
    parser = argparse.ArgumentParser(
        description="Amazon Bedrock AgentCore Observability Demo with Dual Platform Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all scenarios (reads agent ID from .deployment_metadata.json)
    python simple_observability.py --scenario all

    # Run specific scenario
    python simple_observability.py --scenario success

    # Override agent ID
    python simple_observability.py --agent-id abc123 --scenario all

    # With environment variables
    export AGENTCORE_AGENT_ID=abc123
    python simple_observability.py

    # Enable debug logging
    python simple_observability.py --debug
        """,
    )

    parser.add_argument(
        "--agent-id",
        type=str,
        help="AgentCore Runtime agent ID (reads from .deployment_metadata.json if not specified)",
    )

    parser.add_argument(
        "--region",
        type=str,
        help="AWS region (reads from .deployment_metadata.json or uses us-east-1)",
    )

    parser.add_argument(
        "--scenario",
        type=str,
        choices=["success", "error", "dashboard", "all"],
        default="all",
        help="Which scenario to run (default: all)",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load deployment metadata if not provided via arguments
    metadata = _load_deployment_metadata()

    # Get agent ARN from args, env var, or metadata
    agent_arn = None
    if args.agent_id:
        # If agent_id is provided as arg, treat it as ARN
        agent_arn = args.agent_id
    elif metadata:
        agent_arn = metadata.get("agent_arn")

    if not agent_arn:
        # Try environment variable (could be ARN or ID)
        env_value = _get_env_var("AGENTCORE_AGENT_ID") or _get_env_var("AGENTCORE_AGENT_ARN")
        if env_value:
            agent_arn = env_value

    if not agent_arn:
        logger.error("エージェント ARN は必須です。")
        logger.error("以下のいずれかで指定してください:")
        logger.error("  1. --agent-id コマンドライン引数（ARN）")
        logger.error("  2. AGENTCORE_AGENT_ARN 環境変数")
        logger.error("  3. まずエージェントをデプロイ: scripts/deploy_agent.sh")
        sys.exit(1)

    # Get region from args, env var, or metadata
    region = args.region or _get_env_var("AWS_REGION")
    if not region and metadata:
        region = metadata.get("region")
    if not region:
        region = DEFAULT_REGION

    # Check if Braintrust observability is enabled
    braintrust_enabled = _is_braintrust_enabled(metadata)

    logger.info("シンプルオブザーバビリティデモを開始")
    logger.info(f"エージェント ARN: {agent_arn}")
    logger.info(f"リージョン: {region}")
    logger.info(f"シナリオ: {args.scenario}")
    logger.info(
        f"Braintrust オブザーバビリティ: {'有効' if braintrust_enabled else '無効（CloudWatch のみ）'}"
    )

    client = _create_bedrock_client(region)

    try:
        if args.scenario in ["success", "all"]:
            scenario_success(client, agent_arn, region, braintrust_enabled)

            if args.scenario == "all":
                print("\n待機中: トレースが伝播するまで10秒間待機中...\n")
                time.sleep(10)

        if args.scenario in ["error", "all"]:
            scenario_error(client, agent_arn, region, braintrust_enabled)

            if args.scenario == "all":
                print("\n待機中: トレースが伝播するまで10秒間待機中...\n")
                time.sleep(10)

        if args.scenario in ["dashboard", "all"]:
            scenario_dashboard(region, braintrust_enabled)

        logger.info("デモが正常に完了！")
        print("\n✓ デモ完了！")
        print("\n次のステップ:")
        print("1. CloudWatch GenAI ObservabilityまたはAPMを開いてトレースを確認")
        if braintrust_enabled:
            print("2. Braintrustダッシュボードを開く: https://www.braintrust.dev/app")
            print("3. 両プラットフォームでオブザーバビリティデータを比較")
        else:
            print(
                "2. To enable Braintrust: Redeploy with --braintrust-api-key and --braintrust-project-id"
            )
        print("3. スパン属性とカスタムメトリクスを確認")
        print("4. ダッシュボードパネルで集約されたメトリクスを確認\n")

    except Exception as e:
        logger.exception(f"デモが失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
