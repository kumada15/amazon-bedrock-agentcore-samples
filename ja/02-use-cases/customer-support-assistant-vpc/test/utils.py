#!/usr/bin/python
from boto3.session import Session
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse
import base64
import boto3
import hashlib
import json
import logging
import os
import requests
import sys
import threading
import time
import urllib
import webbrowser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    """AWS Systems Manager Parameter Store からパラメータを取得する。"""
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]


def get_token_config_path():
    """トークン設定ファイルへのパスを取得する。"""
    return Path.home() / ".bedrock_agent_tokens.json"


def save_access_token(token: str, agent_name: str):
    """アクセストークンをローカル設定ファイルに保存する。"""
    config_path = get_token_config_path()

    # Load existing config or create new one
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}

    # Save token for this agent
    import time

    config[agent_name] = {"access_token": token, "timestamp": int(time.time())}

    # Write back to file
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Set restrictive permissions (readable only by owner)
    config_path.chmod(0o600)


def load_access_token(agent_name: str) -> Optional[str]:
    """ローカル設定ファイルからアクセストークンを読み込む。"""
    config_path = get_token_config_path()

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        if agent_name in config and "access_token" in config[agent_name]:
            return config[agent_name]["access_token"]
    except (json.JSONDecodeError, KeyError, IOError):
        pass

    return None


def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8").rstrip("=")
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode("utf-8")
        .rstrip("=")
    )
    return code_verifier, code_challenge


class OAuth2CallbackHandler(BaseHTTPRequestHandler):
    """OAuth2 コールバック用 HTTP リクエストハンドラー。"""

    def __init__(self, callback_result, *args, **kwargs):
        self.callback_result = callback_result
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """OAuth2 コールバック用の GET リクエストを処理する。"""
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        if "code" in query_params:
            # Success - we got the authorization code
            self.callback_result["code"] = query_params["code"][0]
            self.callback_result["success"] = True

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
                <head><title>Authentication Success</title></head>
                <body>
                    <h1>Authentication Successful!</h1>
                    <p>You can close this window and return to your terminal.</p>
                    <script>setTimeout(() => window.close(), 3000);</script>
                </body>
            </html>
            """)
        elif "error" in query_params:
            # Error occurred
            error = query_params.get("error", ["unknown"])[0]
            error_description = query_params.get("error_description", [""])[0]

            self.callback_result["error"] = error
            self.callback_result["error_description"] = error_description
            self.callback_result["success"] = False

            # Send error response
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
            <html>
                <head><title>Authentication Error</title></head>
                <body>
                    <h1>Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p>Description: {error_description}</p>
                    <p>You can close this window and return to your terminal.</p>
                </body>
            </html>
            """.encode()
            )
        else:
            # Unexpected request
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Invalid Request</h1></body></html>")

    def log_message(self, format, *args):
        """ログメッセージを抑制する。"""
        pass


def start_oauth_server(port=8080, timeout=300):
    """OAuth2 コールバックを処理するローカル HTTP サーバーを起動する。"""
    callback_result = {"success": False, "code": None, "error": None}

    def handler(*args, **kwargs):
        return OAuth2CallbackHandler(callback_result, *args, **kwargs)

    server = HTTPServer(("localhost", port), handler)

    def run_server():
        server.timeout = 1  # Check for shutdown every second
        start_time = time.time()
        while (
            time.time() - start_time < timeout
            and not callback_result["success"]
            and not callback_result["error"]
        ):
            server.handle_request()
        server.server_close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    return callback_result, server_thread


def get_auth_code_automatically(login_url, port=8080, timeout=300):
    """ローカルサーバーを使用して OAuth 認証コードを自動取得する。"""
    print(f"🚀 ポート {port} でローカルサーバーを起動して OAuth コールバックを処理します...")

    callback_result, server_thread = start_oauth_server(port, timeout)

    print("🔐 認証用にブラウザを開いています...")
    webbrowser.open(login_url)
    print(f"🔐 URL を開いています: {login_url}")

    print("⏳ 認証コールバックを待機中...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if callback_result["success"]:
            print("✅ 認証コードを正常に受信しました！")
            return callback_result["code"]
        elif callback_result["error"]:
            print(f"❌ 認証に失敗しました: {callback_result['error']}")
            if callback_result["error_description"]:
                print(f"   説明: {callback_result['error_description']}")
            return None
        time.sleep(0.5)

    print("⏰ 認証がタイムアウトしました。再試行してください。")
    return None


def invoke_endpoint(
    agent_arn: str,
    payload,
    session_id: str,
    bearer_token: Optional[str],
    endpoint_name: str = "DEFAULT",
    stream: bool = True,
) -> Any:
    escaped_arn = urllib.parse.quote(agent_arn, safe="")

    _, region = get_aws_info()

    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    try:
        body = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError:
        body = {"payload": payload}

    response = requests.post(
        url,
        params={"qualifier": endpoint_name},
        headers=headers,
        json=body,
        timeout=100,
        stream=stream,
    )

    if not stream:
        print(
            response.content.decode("utf-8").replace("\\n", "\n").replace('"', ""),
            flush=True,
        )
    else:
        last_data = False

        for line in response.iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    last_data = True
                    data_content = line[6:]
                    parsed = json.loads(data_content)

                    # Check for event structure with contentBlockDelta
                    if isinstance(parsed, dict) and "event" in parsed:
                        event = parsed["event"]
                        if isinstance(event, dict) and "contentBlockDelta" in event:
                            delta = event["contentBlockDelta"].get("delta", {})
                            if "text" in delta:
                                text = delta["text"]
                                # Replace literal \n with actual newlines
                                text = text.replace("\\n", "\n")
                                print(text, end="", flush=True)
                elif line:
                    if last_data:
                        parsed = json.loads(line)
                        # Check for event structure with contentBlockDelta
                        if isinstance(parsed, dict) and "event" in parsed:
                            event = parsed["event"]
                            if isinstance(event, dict) and "contentBlockDelta" in event:
                                delta = event["contentBlockDelta"].get("delta", {})
                                if "text" in delta:
                                    text = delta["text"]
                                    # Replace literal \n with actual newlines
                                    text = text.replace("\\n", "\n")
                                    print(text, end="", flush=True)
                    last_data = False


def get_aws_info():
    """boto3 セッションから AWS アカウント ID とリージョンを取得する。"""
    try:
        boto_session = Session()

        # Get region
        region = boto_session.region_name
        if not region:
            # Try to get from default session
            region = (
                boto3.DEFAULT_SESSION.region_name if boto3.DEFAULT_SESSION else None
            )
            if not region:
                raise ValueError(
                    "AWS region not configured. Please set AWS_DEFAULT_REGION or configure AWS CLI."
                )

        # Get account ID using STS
        sts = boto_session.client("sts")
        account_id = sts.get_caller_identity()["Account"]

        return account_id, region

    except Exception as e:
        print(f"❌ AWS 情報の取得中にエラーが発生しました: {e}")
        print(
            "AWS 認証情報が設定されていることを確認してください（aws configure または環境変数）"
        )
        sys.exit(1)
