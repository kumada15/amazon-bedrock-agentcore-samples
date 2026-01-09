import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field
from retrieve_api_key import retrieve_api_key

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

app = FastAPI(title="Kubernetes Analysis API", version="1.0.0")

# フェイクデータのベースパス
DATA_PATH = Path(__file__).parent.parent / "data" / "k8s_data"

# 認証用 API キー
CREDENTIAL_PROVIDER_NAME = "sre-agent-api-key-credential-provider"

# 起動時に認証プロバイダーから API キーを取得
try:
    EXPECTED_API_KEY = retrieve_api_key(CREDENTIAL_PROVIDER_NAME)
    if not EXPECTED_API_KEY:
        logging.error("Failed to retrieve API key from credential provider")
        raise RuntimeError(
            "Cannot start server without valid API key from credential provider"
        )
except Exception as e:
    logging.error(f"Error retrieving API key: {e}")
    raise RuntimeError(f"Cannot start server: {e}") from e


def _validate_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """ヘッダーから API キーを検証します。"""
    if not x_api_key or x_api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


def _parse_timestamp(timestamp_str: str) -> datetime:
    """ISO タイムスタンプ文字列を datetime オブジェクトに解析します。"""
    try:
        # タイムゾーンありとなしの両方を処理
        if timestamp_str.endswith("Z"):
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        elif "+" in timestamp_str or timestamp_str.endswith("0"):
            return datetime.fromisoformat(timestamp_str)
        else:
            return datetime.fromisoformat(timestamp_str + "+00:00")
    except:
        # フォールバック: 解析に失敗した場合は現在時刻を使用
        return datetime.now(timezone.utc)


def _filter_events_by_time(events: list, since: Optional[str] = None) -> list:
    """since タイムスタンプでイベントをフィルタリングします。"""
    if not since:
        return events

    filtered_events = []
    since_dt = _parse_timestamp(since)

    for event in events:
        event_timestamp = event.get("timestamp")
        if not event_timestamp:
            continue

        try:
            event_dt = _parse_timestamp(event_timestamp)

            if event_dt >= since_dt:
                filtered_events.append(event)
        except:
            # 解析できないタイムスタンプのイベントも含める
            filtered_events.append(event)

    return filtered_events


# Pydantic モデル
class PodStatus(str, Enum):
    """Pod ステータスの列挙型。"""

    RUNNING = "Running"
    PENDING = "Pending"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"
    CRASHLOOPBACKOFF = "CrashLoopBackOff"


class PodPhase(str, Enum):
    """Pod フェーズの列挙型。"""

    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ResourceUsage(BaseModel):
    """リソース使用量の情報。"""

    cpu: str = Field(..., description="CPU request/limit", example="250m")
    memory: str = Field(..., description="Memory request/limit", example="512Mi")
    cpu_utilization: str = Field(
        ..., description="CPU utilization percentage", example="75%"
    )
    memory_utilization: str = Field(
        ..., description="Memory utilization percentage", example="85%"
    )


class Pod(BaseModel):
    """Pod 情報モデル。"""

    name: str = Field(
        ..., description="Pod name", example="web-app-deployment-5c8d7f9b6d-k2n8p"
    )
    namespace: str = Field(
        ..., description="Kubernetes namespace", example="production"
    )
    status: PodStatus = Field(..., description="Pod status")
    phase: PodPhase = Field(..., description="Pod phase")
    node: str = Field(..., description="Node where pod is running", example="node-1")
    created_at: str = Field(..., description="Pod creation timestamp")
    resource_usage: ResourceUsage = Field(..., description="Resource usage metrics")


class PodStatusResponse(BaseModel):
    """Pod ステータスエンドポイントのレスポンスモデル。"""

    pods: List[Pod] = Field(..., description="List of pods")


class DeploymentStatus(str, Enum):
    """Deployment ステータスの列挙型。"""

    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    FAILED = "Failed"


class Deployment(BaseModel):
    """Deployment 情報モデル。"""

    name: str = Field(..., description="Deployment name", example="web-app-deployment")
    namespace: str = Field(
        ..., description="Kubernetes namespace", example="production"
    )
    replicas: int = Field(..., description="Desired number of replicas", example=3)
    available_replicas: int = Field(
        ..., description="Number of available replicas", example=2
    )
    unavailable_replicas: int = Field(
        ..., description="Number of unavailable replicas", example=1
    )
    status: DeploymentStatus = Field(..., description="Deployment status")


class DeploymentStatusResponse(BaseModel):
    """Deployment ステータスエンドポイントのレスポンスモデル。"""

    deployments: List[Deployment] = Field(..., description="List of deployments")


class EventType(str, Enum):
    """イベントタイプの列挙型。"""

    NORMAL = "Normal"
    WARNING = "Warning"
    ERROR = "Error"


class Event(BaseModel):
    """Kubernetes イベントモデル。"""

    type: EventType = Field(..., description="Event type")
    reason: str = Field(..., description="Event reason", example="FailedScheduling")
    object: str = Field(
        ...,
        description="Kubernetes object reference",
        example="pod/web-app-deployment-5c8d7f9b6d-k2n8p",
    )
    message: str = Field(
        ...,
        description="Event message",
        example="0/3 nodes are available: 3 Insufficient memory",
    )
    timestamp: str = Field(..., description="Event timestamp")
    namespace: str = Field(
        ..., description="Kubernetes namespace", example="production"
    )
    count: int = Field(..., description="Number of occurrences", example=5)


class EventsResponse(BaseModel):
    """イベントエンドポイントのレスポンスモデル。"""

    events: List[Event] = Field(..., description="List of events")


class ErrorResponse(BaseModel):
    """エラーレスポンスモデル。"""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


@app.get("/pods/status", response_model=PodStatusResponse)
async def get_pod_status(
    namespace: Optional[str] = Query(
        None, description="Kubernetes namespace to filter pods"
    ),
    pod_name: Optional[str] = Query(None, description="Specific pod name to retrieve"),
    api_key: str = Depends(_validate_api_key),
):
    """
    Kubernetes クラスターから Pod 情報を取得します。

    このエンドポイントは、Pod のステータス、リソース使用量、クラスター内の配置場所を含む
    詳細情報を提供します。namespace および特定の Pod 名でフィルタリングできます。

    Args:
        namespace: Pod をフィルタリングするオプションの Kubernetes namespace
        pod_name: 取得する特定の Pod 名（オプション）
        api_key: 認証に必要な API キー

    Returns:
        PodStatusResponse: 詳細なステータス情報を含む Pod のリスト

    Raises:
        HTTPException: API キーが無効な場合は 401
        HTTPException: データ取得に失敗した場合は 500
    """
    try:
        with open(DATA_PATH / "pods.json", "r") as f:
            data = json.load(f)

        pods = data.get("pods", [])

        # namespace が指定されている場合はフィルタリング
        if namespace:
            pods = [p for p in pods if p.get("namespace") == namespace]

        # Pod 名が指定されている場合はフィルタリング
        if pod_name:
            pods = [p for p in pods if p.get("name") == pod_name]

        return PodStatusResponse(pods=pods)
    except Exception as e:
        logging.error(f"Error retrieving pod status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/deployments/status", response_model=DeploymentStatusResponse)
async def get_deployment_status(
    namespace: Optional[str] = Query(None, description="Kubernetes namespace"),
    deployment_name: Optional[str] = Query(
        None, description="Specific deployment name"
    ),
    api_key: str = Depends(_validate_api_key),
):
    """
    Deployment の健全性とレプリカステータスを確認します。

    このエンドポイントは、Deployment の現在のステータス、レプリカ数、健全性メトリクスを含む
    包括的な情報を提供します。namespace および特定の Deployment 名でフィルタリングできます。

    Args:
        namespace: Deployment をフィルタリングするオプションの Kubernetes namespace
        deployment_name: 取得する特定の Deployment 名（オプション）
        api_key: 認証に必要な API キー

    Returns:
        DeploymentStatusResponse: 健全性ステータスを含む Deployment のリスト

    Raises:
        HTTPException: API キーが無効な場合は 401
        HTTPException: データ取得に失敗した場合は 500
    """
    try:
        with open(DATA_PATH / "deployments.json", "r") as f:
            data = json.load(f)

        deployments = data.get("deployments", [])

        if namespace:
            deployments = [d for d in deployments if d.get("namespace") == namespace]

        if deployment_name:
            deployments = [d for d in deployments if d.get("name") == deployment_name]

        return DeploymentStatusResponse(deployments=deployments)
    except Exception as e:
        logging.error(f"Error retrieving deployment status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events", response_model=EventsResponse)
async def get_cluster_events(
    since: Optional[str] = Query(
        None, description="Filter events since this timestamp"
    ),
    severity: Optional[str] = Query(
        None,
        enum=["Warning", "Error", "Normal"],
        description="Filter by event severity",
    ),
    api_key: str = Depends(_validate_api_key),
):
    """
    最近の Kubernetes クラスターイベントを取得します。

    このエンドポイントは、タイムスタンプと重要度レベルでフィルタリング可能な
    クラスターイベントを取得します。イベントは、クラスター操作、スケジューリング決定、
    潜在的な問題に関する洞察を提供します。

    Args:
        since: イベントをフィルタリングするオプションの ISO 8601 タイムスタンプ
        severity: オプションの重要度フィルター（Warning、Error、Normal）
        api_key: 認証に必要な API キー

    Returns:
        EventsResponse: タイムスタンプと詳細を含むクラスターイベントのリスト

    Raises:
        HTTPException: API キーが無効な場合は 401
        HTTPException: データ取得に失敗した場合は 500
    """
    try:
        with open(DATA_PATH / "events.json", "r") as f:
            data = json.load(f)

        events = data.get("events", [])

        if severity:
            events = [e for e in events if e.get("type") == severity]

        # since タイムスタンプでフィルタリング
        events = _filter_events_by_time(events, since)

        return EventsResponse(events=events)
    except Exception as e:
        logging.error(f"Error retrieving cluster events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resource_usage")
async def get_resource_usage(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    resource_type: Optional[str] = Query(
        None, enum=["cpu", "memory", "pods"], description="Type of resource to monitor"
    ),
    api_key: str = Depends(_validate_api_key),
):
    """
    クラスターのリソース消費量と使用率を監視します。

    このエンドポイントは、CPU、メモリ、Pod の消費量を含むクラスター全体の
    リソース使用量に関する詳細なメトリクスを提供します。namespace および
    特定のリソースタイプでフィルタリングできます。

    Args:
        namespace: リソース使用量データをフィルタリングするオプションの namespace
        resource_type: オプションのリソースタイプフィルター（cpu、memory、pods）
        api_key: 認証に必要な API キー

    Returns:
        Dict: クラスターと namespace の内訳を含むリソース使用量メトリクス

    Raises:
        HTTPException: API キーが無効な場合は 401
        HTTPException: データ取得に失敗した場合は 500
    """
    try:
        with open(DATA_PATH / "resource_usage.json", "r") as f:
            data = json.load(f)

        resource_usage = data.get("resource_usage", {})

        # namespace が指定されている場合はフィルタリング
        if namespace and "namespace_usage" in resource_usage:
            namespace_data = resource_usage["namespace_usage"].get(namespace, {})
            if resource_type:
                return {
                    "resource_usage": {resource_type: namespace_data.get(resource_type)}
                }
            return {"resource_usage": {"namespace": namespace, "usage": namespace_data}}

        return {"resource_usage": resource_usage}
    except Exception as e:
        logging.error(f"Error retrieving resource usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nodes/status")
async def get_node_status(
    node_name: Optional[str] = Query(None, description="Specific node name"),
    api_key: str = Depends(_validate_api_key),
):
    """
    クラスターノードの健全性とステータスを確認します。

    このエンドポイントは、ノードの健全性ステータス、容量、割り当て可能なリソース、
    現在の使用量を含むクラスターノードの包括的な情報を提供します。
    特定のノード名でフィルタリングできます。

    Args:
        node_name: 取得する特定のノード名（オプション）
        api_key: 認証に必要な API キー

    Returns:
        Dict: 健全性とリソースメトリクスを含むノードステータス情報

    Raises:
        HTTPException: API キーが無効な場合は 401
        HTTPException: データ取得に失敗した場合は 500
    """
    try:
        with open(DATA_PATH / "nodes.json", "r") as f:
            data = json.load(f)

        nodes = data.get("nodes", [])

        if node_name:
            nodes = [n for n in nodes if n.get("name") == node_name]

        return {"nodes": nodes}
    except Exception as e:
        logging.error(f"Error retrieving node status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def health_check(api_key: str = Depends(_validate_api_key)):
    """
    Kubernetes API サービスのヘルスチェックエンドポイント。

    このエンドポイントは、API サービスが稼働中でアクセス可能であることを確認する
    シンプルなヘルスチェックを提供します。他のエンドポイントと同様に認証が必要です。

    Args:
        api_key: 認証に必要な API キー

    Returns:
        Dict: サービスの健全性ステータス情報

    Raises:
        HTTPException: API キーが無効な場合は 401
    """
    return {"status": "healthy", "service": "k8s-api"}


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    import uvicorn

    # config_utils をインポートするために親ディレクトリをパスに追加
    sys.path.append(str(Path(__file__).parent.parent))
    from config_utils import get_server_port

    parser = argparse.ArgumentParser(description="K8s API Server")
    parser.add_argument(
        "--host",
        type=str,
        required=True,
        help="Host to bind to (REQUIRED - must match SSL certificate hostname if using SSL)",
    )
    parser.add_argument("--ssl-keyfile", type=str, help="Path to SSL private key file")
    parser.add_argument("--ssl-certfile", type=str, help="Path to SSL certificate file")
    parser.add_argument("--port", type=int, help="Port to bind to (overrides config)")

    args = parser.parse_args()

    port = args.port if args.port else get_server_port("k8s")

    # 両方の証明書ファイルが提供されている場合は SSL を設定
    ssl_config = {}
    if args.ssl_keyfile and args.ssl_certfile:
        ssl_config = {
            "ssl_keyfile": args.ssl_keyfile,
            "ssl_certfile": args.ssl_certfile,
        }
        protocol = "HTTPS"
        logging.warning(
            f"⚠️  SSL CERTIFICATE HOSTNAME WARNING: Ensure your SSL certificate is valid for hostname '{args.host}'"
        )
        logging.warning(
            f"⚠️  If using self-signed certificates, generate with: openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN={args.host}'"
        )
    else:
        protocol = "HTTP"

    logging.info(f"Starting K8s server on {protocol}://{args.host}:{port}")
    uvicorn.run(app, host=args.host, port=port, **ssl_config)
