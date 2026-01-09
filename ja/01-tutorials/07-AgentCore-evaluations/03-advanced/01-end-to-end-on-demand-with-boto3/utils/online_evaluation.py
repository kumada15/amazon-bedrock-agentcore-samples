"""エージェント呼び出しと評価ワークフロー用のオンライン評価ヘルパー関数。"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .evaluation_client import EvaluationClient


def generate_session_id() -> str:
    """UUID フォーマットで有効なセッション ID を生成します。

    Returns:
        UUID v4 文字列（例: 'de45c51c-27c3-4670-aa72-c8b302b23890'）
    """
    return str(uuid.uuid4())


def invoke_agent(
    agentcore_client: Any,
    agent_arn: str,
    prompt: str,
    session_id: str = '',
    qualifier: str = "DEFAULT"
) -> Tuple[str, List[str]]:
    """エージェントランタイムを呼び出し、セッション ID とレスポンスコンテンツを返します。

    Args:
        agentcore_client: Boto3 agentcore クライアント
        agent_arn: エージェントランタイム ARN
        prompt: ユーザー入力プロンプト
        session_id: マルチターン会話用のオプションのセッション ID（UUID フォーマット）
                   - 空文字列 '' = 新しいセッションを作成
                   - 有効な UUID = 既存のセッションを継続または特定のセッション ID を使用
        qualifier: エージェントランタイム修飾子（デフォルト: DEFAULT）

    Returns:
        (session_id, content_list) のタプル
    """
    api_params = {
        'agentRuntimeArn': agent_arn,
        'qualifier': qualifier,
        'payload': json.dumps({"prompt": prompt})
    }

    if session_id:
        api_params['runtimeSessionId'] = session_id

    boto3_response = agentcore_client.invoke_agent_runtime(**api_params)

    returned_session_id = (
        boto3_response['ResponseMetadata']['HTTPHeaders'].get('x-amzn-bedrock-agentcore-runtime-session-id')
        or boto3_response.get('runtimeSessionId')
        or session_id
    )

    content = []
    if "text/event-stream" in boto3_response.get("contentType", ""):
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    content.append(line[6:])
    else:
        try:
            events = [event for event in boto3_response.get("response", [])]
            if events:
                content = [json.loads(events[0].decode("utf-8"))]
        except Exception as e:
            content = [f"Error reading EventStream: {e}"]

    return returned_session_id, content


def evaluate_session(
    eval_client: EvaluationClient,
    session_id: str,
    evaluators: List[str],
    scope: str,
    agent_id: str,
    region: str,
    experiment_name: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Any:
    """指定された評価器でセッションを評価します。

    Args:
        eval_client: EvaluationClient インスタンス
        session_id: 評価するセッション ID
        evaluators: 評価器 ID のリスト
        scope: 評価スコープ（session、trace、または span）
        agent_id: エージェント ID
        region: AWS リージョン
        experiment_name: 追跡用の実験識別子
        metadata: オプションのメタデータ辞書

    Returns:
        EvaluationResults オブジェクト
    """
    eval_metadata = {"experiment": experiment_name}
    if metadata:
        eval_metadata.update(metadata)

    results = eval_client.evaluate_session(
        session_id=session_id,
        evaluator_ids=evaluators,
        agent_id=agent_id,
        region=region,
        scope=scope,
        auto_save_input=True,
        auto_save_output=True,
        auto_create_dashboard=True,
        metadata=eval_metadata
    )

    return results


def evaluate_session_comprehensive(
    eval_client: EvaluationClient,
    session_id: str,
    agent_id: str,
    region: str,
    experiment_name: str,
    flexible_evaluators: List[str],
    session_only_evaluators: List[str],
    span_only_evaluators: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> List[Any]:
    """すべての評価器を適切なスコープで実行します。

    Args:
        eval_client: EvaluationClient インスタンス
        session_id: 評価するセッション ID
        agent_id: エージェント ID
        region: AWS リージョン
        experiment_name: 実験識別子
        flexible_evaluators: フレキシブルスコープ評価器のリスト
        session_only_evaluators: セッション専用評価器のリスト
        span_only_evaluators: スパン専用評価器のリスト
        metadata: オプションのメタデータ辞書

    Returns:
        結合された評価結果のリスト
    """
    all_results = []

    evaluation_configs = [
        {"evaluators": flexible_evaluators, "scope": "session"},
        {"evaluators": session_only_evaluators, "scope": "session"},
        {"evaluators": span_only_evaluators, "scope": "span"}
    ]

    for config in evaluation_configs:
        if config["evaluators"]:
            try:
                results = evaluate_session(
                    eval_client=eval_client,
                    session_id=session_id,
                    evaluators=config["evaluators"],
                    scope=config["scope"],
                    agent_id=agent_id,
                    region=region,
                    experiment_name=experiment_name,
                    metadata=metadata
                )
                all_results.extend(results.results)
            except Exception as e:
                print(f"{config['scope']} 評価中にエラー: {e}")

    return all_results


def invoke_and_evaluate(
    agentcore_client: Any,
    eval_client: EvaluationClient,
    agent_arn: str,
    agent_id: str,
    region: str,
    prompt: str,
    experiment_name: str,
    session_id: str = '',
    metadata: Optional[Dict[str, Any]] = None,
    evaluators: Optional[List[str]] = None,
    scope: str = "session",
    delay: int = 90,
    flexible_evaluators: Optional[List[str]] = None,
    session_only_evaluators: Optional[List[str]] = None,
    span_only_evaluators: Optional[List[str]] = None
) -> Tuple[str, List[Any]]:
    """完全なワークフロー: エージェントを呼び出し、ログ伝播を待機してから評価します。

    Args:
        agentcore_client: Boto3 agentcore クライアント
        eval_client: EvaluationClient インスタンス
        agent_arn: エージェントランタイム ARN
        agent_id: エージェント ID
        region: AWS リージョン
        prompt: ユーザー入力プロンプト
        experiment_name: 実験識別子
        session_id: オプションのセッション ID（空 = 新規セッション、UUID = 継続/指定セッション）
        metadata: オプションのメタデータ辞書
        evaluators: 評価器 ID のリスト（None = 包括的評価を使用）
        scope: 評価スコープ（session、trace、span）
        delay: CloudWatch 伝播を待機する秒数
        flexible_evaluators: evaluators が None の場合必須
        session_only_evaluators: evaluators が None の場合必須
        span_only_evaluators: evaluators が None の場合必須

    Returns:
        (session_id, results_list) のタプル
    """
    returned_session_id, content = invoke_agent(
        agentcore_client=agentcore_client,
        agent_arn=agent_arn,
        prompt=prompt,
        session_id=session_id
    )

    time.sleep(delay)

    if evaluators is None:
        if not all([flexible_evaluators, session_only_evaluators, span_only_evaluators]):
            raise ValueError("Must provide evaluator lists for comprehensive evaluation")

        results = evaluate_session_comprehensive(
            eval_client=eval_client,
            session_id=returned_session_id,
            agent_id=agent_id,
            region=region,
            experiment_name=experiment_name,
            flexible_evaluators=flexible_evaluators,
            session_only_evaluators=session_only_evaluators,
            span_only_evaluators=span_only_evaluators,
            metadata=metadata
        )
    else:
        eval_results = evaluate_session(
            eval_client=eval_client,
            session_id=returned_session_id,
            evaluators=evaluators,
            scope=scope,
            agent_id=agent_id,
            region=region,
            experiment_name=experiment_name,
            metadata=metadata
        )
        results = eval_results.results

    return returned_session_id, content, results
