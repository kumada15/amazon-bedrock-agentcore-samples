#!/usr/bin/python
from urllib.parse import urlencode
import argparse
import json
import logging
import requests
import sys
import uuid

from utils import (
    generate_pkce_pair,
    get_auth_code_automatically,
    get_ssm_parameter,
    invoke_endpoint,
    load_access_token,
    save_access_token,
)

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Bedrock AgentCore との対話型チャット用 CLI ツール。"""

    parser = argparse.ArgumentParser(
        description="Interactive Agent Runtime CLI Tool - Start a conversation with the customer support agent"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Set logging level based on arguments
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    print("🚀 エージェントランタイムCLIツール")
    print("=" * 30)

    # Get Agent ARN from SSM Parameter Store
    agent_arn = get_ssm_parameter("/app/customersupportvpc/agentcore/agent_runtime_arn")
    print(f"🤖 エージェントARN: {agent_arn}")

    # Extract runtime_id, region, and account_id from ARN
    # ARN format: arn:aws:bedrock-agentcore:region:account-id:runtime/runtime-id
    runtime_id = agent_arn.split('/')[-1]
    arn_parts = agent_arn.split(':')
    region = arn_parts[3]
    account_id = arn_parts[4]

    print(f"📋 AWSアカウントID: {account_id}")
    print(f"🌍 AWSリージョン: {region}")
    print(f"🤖 エージェントランタイムID: {runtime_id}")

    # Try to load existing access token
    access_token = load_access_token(runtime_id)

    if access_token:
        print("✅ キャッシュされたアクセストークンを使用しています。")
    else:
        print("🔐 キャッシュされたトークンが見つかりません。認証フローを開始しています...")

        code_verifier, code_challenge = generate_pkce_pair()
        state = str(uuid.uuid4())

        client_id = get_ssm_parameter("/app/customersupportvpc/agentcore/web_client_id")
        cognito_domain = get_ssm_parameter(
            "/app/customersupportvpc/agentcore/cognito_domain"
        )
        redirect_uri = "http://localhost:8080/callback"

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

        # Try automated OAuth flow first
        auth_code = get_auth_code_automatically(login_url)

        # Fallback to manual flow if automation fails
        if not auth_code:
            print("\n🔧 自動フローに失敗しました。手動認証にフォールバックしています:")
            print("🔐 認証するには、以下のURLをブラウザで開いてください:")
            print(login_url)
            auth_code = input("📥 リダイレクトされたURLから `code` を貼り付けてください: ").strip()

        token_url = get_ssm_parameter(
            "/app/customersupportvpc/agentcore/cognito_token_url"
        )
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

        # Save the token for future use
        save_access_token(access_token, runtime_id)
        print("✅ アクセストークンを取得して保存しました。")

    session_id = str(uuid.uuid4())
    print("\n🤖 エージェントとの対話セッションを開始します。終了するには 'q' または 'quit' と入力してください。\n")

    while True:
        user_input = input("👤 You: ").strip()

        if user_input.lower() in ["q", "quit"]:
            print("👋 さようなら！")
            break

        if not user_input:
            continue

        print("🤖 Assistant: ", end="", flush=True)
        # asyncio.run(
        invoke_endpoint(
            agent_arn=agent_arn,
            payload=json.dumps({"prompt": user_input, "actor_id": "DEFAULT"}),
            bearer_token=access_token,
            session_id=session_id,
            stream=True,
        )
        # )
        print("\n")


if __name__ == "__main__":
    main()
