#!/usr/bin/python

import base64
import hashlib
from typing import Any, Optional
import webbrowser
import urllib
import json
from urllib.parse import urlencode
import requests
import uuid
import sys
import os
import click
import logging

# Ensure we can import local utilities
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.utils import get_aws_region, read_config, get_ssm_parameter


def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8").rstrip("=")
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode("utf-8")
        .rstrip("=")
    )
    return code_verifier, code_challenge


def invoke_endpoint(
    agent_arn: str,
    payload,
    session_id: str,
    bearer_token: Optional[str],
    endpoint_name: str = "DEFAULT",
) -> Any:
    escaped_arn = urllib.parse.quote(agent_arn, safe="")
    url = f"https://bedrock-agentcore.{get_aws_region()}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    try:
        body = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError:
        body = {"payload": payload}

    try:
        response = requests.post(
            url,
            params={"qualifier": endpoint_name},
            headers=headers,
            json=body,
            timeout=100,
            stream=True,
        )
        logger = logging.getLogger("bedrock_agentcore.stream")
        logger.setLevel(logging.INFO)

        last_data = False
        # for line in response.text.splitlines():
        #     # line = line.strip()
        #     if line.startswith("data:"):
        #         last_data = True
        #         content = line[6:]
        #         print(content, end="")
        #     elif line:  # lines without "data:" that still have text
        #         if last_data:
        #             print("\n" + line, end="")
        #         last_data = False

        for line in response.iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                # print(line)
                if line.startswith("data: "):
                    last_data = True
                    line = line[6:].replace('"', "")
                    print(line, end="")
                elif line:
                    if last_data:
                        print("\n" + line.replace('"', ""), end="")
                    last_data = False

        # print({"response": "\n".join(content)})

    except requests.exceptions.RequestException as e:
        print("エージェントエンドポイントの呼び出しに失敗しました:", str(e))
        raise


@click.command()
@click.argument("agent_name")
@click.option("--prompt", "-p", default="こんにちは", help="エージェントに送信するプロンプト")
def main(agent_name: str, prompt: str):
    """Bedrock エージェントを名前で呼び出すための CLI ツール。"""
    runtime_config = read_config(".bedrock_agentcore.yaml")

    print(runtime_config)

    if agent_name not in runtime_config["agents"]:
        print(f"❌ エージェント '{agent_name}' が設定に見つかりません。")
        sys.exit(1)

    code_verifier, code_challenge = generate_pkce_pair()
    state = str(uuid.uuid4())

    client_id = get_ssm_parameter("/app/customersupport/agentcore/web_client_id")
    cognito_domain = get_ssm_parameter("/app/customersupport/agentcore/cognito_domain")
    redirect_uri = "https://example.com/auth/callback"

    login_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "email openid profile",
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state,
    }

    login_url = f"{cognito_domain}/oauth2/authorize?{urlencode(login_params)}"

    print("🔐 認証するには、以下のURLをブラウザで開いてください:")
    print(login_url)
    webbrowser.open(login_url)

    auth_code = input("📥 リダイレクトされたURLから `code` を貼り付けてください: ").strip()

    token_url = get_ssm_parameter("/app/customersupport/agentcore/cognito_token_url")
    response = requests.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code != 200:
        print(f"❌ コードの交換に失敗しました: {response.text}")
        sys.exit(1)

    access_token = response.json()["access_token"]
    print("✅ アクセストークンを取得しました。")

    agent_arn = runtime_config["agents"][agent_name]["bedrock_agentcore"]["agent_arn"]

    invoke_endpoint(
        agent_arn=agent_arn,
        payload=json.dumps({"prompt": prompt, "actor_id": "DEFAULT"}),
        bearer_token=access_token,
        session_id=str(uuid.uuid4()),
    )


if __name__ == "__main__":
    main()
