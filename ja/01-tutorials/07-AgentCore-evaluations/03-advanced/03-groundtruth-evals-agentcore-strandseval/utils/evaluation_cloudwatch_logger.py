"""元のトレース ID を使用した評価結果用のカスタム CloudWatch ロガー。

このモジュールは、AgentCore Observability Dashboard が期待する正確な EMF フォーマットを使用した
CloudWatch ロギングを提供しますが、新しいトレース ID を生成する代わりに、
元の AgentCore トレースデータセットからのトレース ID を使用します。

strands_evals.telemetry._cloudwatch_logger をベースに、ケースメタデータから
trace_id をパラメータとして受け取るように変更されています。
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import boto3

logger = logging.getLogger(__name__)

# Module-level CloudWatch client (lazy initialization)
_cloudwatch_client = None


def _get_cloudwatch_client():
    """CloudWatch Logs クライアントを取得または作成します（シングルトンパターン）。"""
    global _cloudwatch_client
    if _cloudwatch_client is None:
        region = os.environ.get("AWS_REGION", "us-east-1")
        _cloudwatch_client = boto3.client("logs", region_name=region)
    return _cloudwatch_client


@dataclass
class EvaluationLogConfig:
    """評価ロギングの設定。"""
    destination_log_group: str
    log_stream: str
    service_name: str
    resource_log_group: Optional[str] = None

    @classmethod
    def from_environment(cls) -> "EvaluationLogConfig":
        """環境変数からログ設定を解析します。

        Environment variables:
        - EVALUATION_RESULTS_LOG_GROUP: 結果ロググループのベース名
        - LOG_STREAM_NAME: 明示的なログストリーム名（優先される）
        - OTEL_RESOURCE_ATTRIBUTES: service.name およびオプションで aws.log.group.names を含む
        - OTEL_EXPORTER_OTLP_LOGS_HEADERS: x-aws-log-stream を含む（フォールバック）
        """
        # Destination log group from EVALUATION_RESULTS_LOG_GROUP
        base_log_group = os.environ.get("EVALUATION_RESULTS_LOG_GROUP", "default_strands_evals_results")
        destination_log_group = f"/aws/bedrock-agentcore/evaluations/results/{base_log_group}"

        # Log stream: First check LOG_STREAM_NAME env var (explicit override)
        log_stream = os.environ.get("LOG_STREAM_NAME", "")

        # Fallback: Parse log stream from OTEL_EXPORTER_OTLP_LOGS_HEADERS
        if not log_stream:
            logs_headers = os.environ.get("OTEL_EXPORTER_OTLP_LOGS_HEADERS", "")
            if logs_headers:
                for header in logs_headers.split(","):
                    if "=" in header:
                        key, value = header.split("=", 1)
                        if key.strip() == "x-aws-log-stream":
                            log_stream = value.strip()
                            break

        # Final fallback: use "default"
        if not log_stream:
            log_stream = "default"

        # Parse OTEL_RESOURCE_ATTRIBUTES for service.name and aws.log.group.names
        resource_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
        service_name = None
        resource_log_group = None

        for attr in resource_attrs.split(","):
            if "=" in attr:
                key, value = attr.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key == "service.name":
                    service_name = value
                elif key == "aws.log.group.names":
                    resource_log_group = value

        if not service_name:
            raise ValueError("service.name must be set in OTEL_RESOURCE_ATTRIBUTES environment variable")

        return cls(
            destination_log_group=destination_log_group,
            log_stream=log_stream,
            service_name=service_name,
            resource_log_group=resource_log_group,
        )


def send_evaluation_to_cloudwatch(
    trace_id: str,
    session_id: str,
    evaluator_name: str,
    score: float,
    explanation: str,
    evaluation_level: str = "Trace",
    label: Optional[str] = None,
    config_id: str = "strands-offline-evaluation",
) -> bool:
    """評価結果を EMF フォーマットで CloudWatch に送信します。

    この関数は、AgentCore Observability Dashboard が期待する正確な EMF フォーマットを使用しますが、
    元の AgentCore トレースデータセットからの trace_id を使用します。

    Args:
        trace_id: AgentCore Observability からの元のトレース ID（ケースメタデータから渡される）
        session_id: 元のトレースデータセットからのセッション ID
        evaluator_name: 完全な評価器名（例: "Custom.StrandsEvalOfflineTravelEvaluator"）
        score: 評価スコア（0.0 から 1.0）
        explanation: スコアの説明
        evaluation_level: "Trace" または "Span"（デフォルト: "Trace"）
        label: スコアラベル（"YES"、"NO"、またはカスタム）。None の場合、スコアから導出されます。
        config_id: ARN 構築用の設定 ID（デフォルト: "strands-offline-evaluation"）

    Returns:
        ロギングが成功した場合は True、それ以外は False
    """
    try:
        config = EvaluationLogConfig.from_environment()

        if not config.destination_log_group:
            logger.warning("宛先ロググループが設定されていません。CloudWatch ロギングをスキップします")
            return False

        cloudwatch_client = _get_cloudwatch_client()

        # Ensure log group exists
        try:
            cloudwatch_client.create_log_group(logGroupName=config.destination_log_group)
            logger.info(f"ロググループを作成しました: {config.destination_log_group}")
        except cloudwatch_client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as e:
            logger.warning(f"ロググループの作成に失敗しました: {str(e)}")

        # Ensure log stream exists
        try:
            cloudwatch_client.create_log_stream(
                logGroupName=config.destination_log_group,
                logStreamName=config.log_stream
            )
            logger.info(f"ログストリームを作成しました: {config.log_stream}")
        except cloudwatch_client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as e:
            logger.warning(f"ログストリームの作成に失敗しました: {str(e)}")

        # Get sequence token for the log stream
        sequence_token = None
        try:
            response = cloudwatch_client.describe_log_streams(
                logGroupName=config.destination_log_group,
                logStreamNamePrefix=config.log_stream
            )
            if response["logStreams"]:
                sequence_token = response["logStreams"][0].get("uploadSequenceToken")
        except Exception as e:
            logger.warning(f"シーケンストークンの取得に失敗しました: {str(e)}")

        # Derive label from score if not provided
        if label is None:
            label = "YES" if score >= 0.5 else "NO"

        # Build ARNs (using bedrock-agentcore format)
        region = os.environ.get("AWS_REGION", "us-east-1")
        account_id = os.environ.get("AWS_ACCOUNT_ID", "")
        config_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:online-evaluation-config/{config_id}"
        evaluator_arn = f"arn:aws:bedrock-agentcore:::evaluator/{evaluator_name}"

        # Derive config_name from config_id (e.g., "EKS_Agent_Evaluation" from "EKS_Agent_Evaluation-5MB8aF5rLE")
        config_name = config_id.rsplit("-", 1)[0] if "-" in config_id else config_id

        # Get current timestamp
        current_time_ns = time.time_ns()
        current_time_ms = int(current_time_ns / 1_000_000)

        # Build log_data (attributes that go inside EMF)
        log_data = {
            "gen_ai.evaluation.name": evaluator_name,
            "session.id": session_id,
            "gen_ai.response.id": trace_id,
            "gen_ai.evaluation.score.value": score,
            "gen_ai.evaluation.explanation": explanation or "",
            "gen_ai.evaluation.score.label": label,
            "aws.bedrock_agentcore.online_evaluation_config.arn": config_arn,
            "aws.bedrock_agentcore.online_evaluation_config.name": config_name,
            "aws.bedrock_agentcore.evaluator.arn": evaluator_arn,
            "aws.bedrock_agentcore.evaluator.rating_scale": "Numerical",
            "aws.bedrock_agentcore.evaluation_level": evaluation_level,
        }

        # Build EMF log structure (exact format from strands_evals)
        emf_log = {
            "resource": {
                "attributes": {
                    "aws.service.type": "gen_ai_agent",
                    "aws.local.service": config.service_name,
                    "service.name": config.service_name,
                }
            },
            "traceId": trace_id,
            "timeUnixNano": current_time_ns,
            "observedTimeUnixNano": current_time_ns,
            "severityNumber": 9,
            "name": "gen_ai.evaluation.result",
            "attributes": {
                **log_data,
            },
            "onlineEvaluationConfigId": config_id,
            evaluator_name: score,  # Dynamic key for metric
            "label": label,
            "service.name": config.service_name,
            "_aws": {
                "Timestamp": current_time_ms,
                "CloudWatchMetrics": [
                    {
                        "Namespace": "Bedrock-AgentCore/Evaluations",
                        "Dimensions": [
                            ["service.name"],
                            ["label", "service.name"],
                            ["service.name", "onlineEvaluationConfigId"],
                            ["label", "service.name", "onlineEvaluationConfigId"],
                        ],
                        "Metrics": [{"Name": evaluator_name, "Unit": "None"}],
                    }
                ],
            },
        }

        # Send to CloudWatch
        log_event = {
            "timestamp": current_time_ms,
            "message": json.dumps(emf_log)
        }

        put_log_params = {
            "logGroupName": config.destination_log_group,
            "logStreamName": config.log_stream,
            "logEvents": [log_event]
        }

        if sequence_token:
            put_log_params["sequenceToken"] = sequence_token

        cloudwatch_client.put_log_events(**put_log_params)

        logger.info(
            f"評価を CloudWatch に送信しました: trace_id={trace_id[:16]}..., "
            f"evaluator={evaluator_name}, score={score}, label={label}"
        )
        return True

    except Exception as e:
        logger.error(f"CloudWatch への評価の送信に失敗しました: {str(e)}")
        return False


def log_evaluation_batch(
    results: list[dict],
    evaluator_name: str,
    config_id: str = "strands-offline-evaluation",
) -> int:
    """複数の評価結果を CloudWatch に送信します。

    Args:
        results: キー trace_id、session_id、score、explanation、label（オプション）を持つ辞書のリスト
        evaluator_name: 完全な評価器名
        config_id: 設定 ID

    Returns:
        正常にログ記録された結果の数
    """
    success_count = 0
    for result in results:
        success = send_evaluation_to_cloudwatch(
            trace_id=result["trace_id"],
            session_id=result["session_id"],
            evaluator_name=evaluator_name,
            score=result["score"],
            explanation=result.get("explanation", ""),
            label=result.get("label"),
            config_id=config_id,
        )
        if success:
            success_count += 1

    logger.info(f"{success_count}/{len(results)} 件の評価結果を CloudWatch にログ記録しました")
    return success_count
