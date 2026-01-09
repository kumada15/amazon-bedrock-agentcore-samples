import logging
from pathlib import Path
from typing import Dict, Optional

import yaml

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)


def _load_openapi_spec(spec_file: str) -> Dict:
    """YAML ファイルから OpenAPI 仕様を読み込みます。"""
    spec_path = Path(__file__).parent / "openapi_specs" / spec_file
    try:
        with open(spec_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error loading OpenAPI spec {spec_file}: {str(e)}")
        return {}


def _get_localhost_port(spec_file: str) -> Optional[int]:
    """OpenAPI 仕様から localhost のポート番号を抽出します。"""
    spec = _load_openapi_spec(spec_file)

    if not spec or "servers" not in spec:
        logging.error(f"No servers defined in {spec_file}")
        return None

    for server in spec["servers"]:
        url = server.get("url", "")
        if "localhost:" in url:
            try:
                # "http://localhost:8011" のような URL からポートを抽出
                port_str = url.split("localhost:")[1].split("/")[0]
                return int(port_str)
            except (IndexError, ValueError) as e:
                logging.error(f"Error parsing port from URL {url}: {str(e)}")
                continue

    logging.error(f"No localhost server found in {spec_file}")
    return None


def get_server_ports() -> Dict[str, int]:
    """OpenAPI 仕様からすべてのサーバーポートを取得します。"""
    port_mapping = {
        "k8s": _get_localhost_port("k8s_api.yaml"),
        "logs": _get_localhost_port("logs_api.yaml"),
        "metrics": _get_localhost_port("metrics_api.yaml"),
        "runbooks": _get_localhost_port("runbooks_api.yaml"),
    }

    # None 値をフィルタリングして警告をログ出力
    valid_ports = {}
    for service, port in port_mapping.items():
        if port is not None:
            valid_ports[service] = port
        else:
            logging.warning(f"Could not determine port for {service} service")

    return valid_ports


def get_server_port(service: str) -> int:
    """特定のサービスのポートを取得します。"""
    ports = get_server_ports()
    if service not in ports:
        raise ValueError(f"Port not found for service: {service}")
    return ports[service]
