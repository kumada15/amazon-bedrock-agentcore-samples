"""
Asana 統合デモ AgentCore セットアップと管理用のユーティリティ関数。

このモジュールは以下のヘルパー関数を提供します:
- AWS SSM パラメータ管理
- Cognito ユーザープールのセットアップと認証
- AgentCore 用の IAM ロールとポリシーの作成
- DynamoDB 操作
- AWS Secrets Manager 操作
- リソースクリーンアップ関数
"""

import json
import os

import boto3
import requests
import time

STS_CLIENT = boto3.client("sts")

# Get AWS account details
REGION = boto3.session.Session().region_name

# Configuration constants - use environment variables in production
USERNAME = os.environ.get("DEMO_USERNAME", "testuser")
SECRET_NAME = os.environ.get("DEMO_SECRET_NAME", "asana_integration_demo_agent")

ROLE_NAME = os.environ.get("ROLE_NAME", "AgentCoreGwyAsanaIntegrationRole")
POLICY_NAME = os.environ.get("POLICY_NAME", "AgentCoreGwyAsanaIntegrationPolicy")


def load_api_spec(file_path: str) -> list:
    """JSON ファイルから API 仕様を読み込む。

    Args:
        file_path: API 仕様を含む JSON ファイルへのパス

    Returns:
        API 仕様データを含むリスト

    Raises:
        ValueError: JSON ファイルがリストを含まないか無効な場合
        FileNotFoundError: ファイルが存在しない場合
        json.JSONDecodeError: ファイルに無効な JSON が含まれている場合
    """
    # Validate file path
    if not file_path or not isinstance(file_path, str):
        raise ValueError("file_path must be a non-empty string")

    # Check if file exists and is readable
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"API specification file not found: {file_path}")

    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"Cannot read API specification file: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in API specification file: {e}", e.doc, e.pos
        )

    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")

    # Basic validation of API spec structure
    if not data:
        raise ValueError("API specification list cannot be empty")

    return data


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    """AWS Systems Manager Parameter Store からパラメータ値を取得。

    Args:
        name: 取得するパラメータ名
        with_decryption: セキュアな文字列パラメータを復号化するかどうか

    Returns:
        文字列としてのパラメータ値
    """
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]


def put_ssm_parameter(
    name: str, value: str, parameter_type: str = "String", with_encryption: bool = False
) -> None:
    """AWS Systems Manager Parameter Store にパラメータ値を保存。

    Args:
        name: 保存するパラメータ名
        value: 保存するパラメータ値
        parameter_type: パラメータのタイプ（String、StringList、SecureString）
        with_encryption: パラメータを SecureString として暗号化するかどうか
    """
    ssm = boto3.client("ssm")

    put_params = {
        "Name": name,
        "Value": value,
        "Type": parameter_type,
        "Overwrite": True,
    }

    if with_encryption:
        put_params["Type"] = "SecureString"

    ssm.put_parameter(**put_params)


def get_cognito_client_secret() -> str:
    """Cognito ユーザープールのクライアントシークレットを取得。

    Returns:
        Cognito ユーザープールクライアントからのクライアントシークレット文字列
    """
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/asana/demo/agentcoregwy/userpool_id"),
        ClientId=get_ssm_parameter("/app/asana/demo/agentcoregwy/machine_client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def fetch_access_token(client_id, client_secret, token_url):
    """クライアント認証情報フローを使用して OAuth アクセストークンを取得。

    Args:
        client_id: OAuth クライアント ID
        client_secret: OAuth クライアントシークレット
        token_url: OAuth トークンエンドポイント URL

    Returns:
        アクセストークン文字列

    Raises:
        ValueError: 必須パラメータが欠落しているか無効な場合
        requests.RequestException: HTTP リクエストが失敗した場合
        KeyError: レスポンスにアクセストークンが含まれていない場合
    """
    # Input validation
    if not all([client_id, client_secret, token_url]):
        raise ValueError("client_id, client_secret, and token_url are required")

    if not token_url.startswith(("https://", "http://")):
        raise ValueError("token_url must be a valid HTTP/HTTPS URL")

    data = (
        f"grant_type=client_credentials&client_id={client_id}"
        f"&client_secret={client_secret}"
    )

    try:
        response = requests.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
            verify=True,  # Ensure SSL verification is enabled
        )
        response.raise_for_status()  # Raise an exception for bad status codes

        response_data = response.json()

        if "access_token" not in response_data:
            raise KeyError("Response does not contain 'access_token' field")

        return response_data["access_token"]

    except requests.exceptions.Timeout:
        raise requests.RequestException("Request timed out while fetching access token")
    except requests.exceptions.ConnectionError:
        raise requests.RequestException("Connection error while fetching access token")
    except requests.exceptions.HTTPError as e:
        raise requests.RequestException(f"HTTP error while fetching access token: {e}")
    except json.JSONDecodeError:
        raise requests.RequestException("Invalid JSON response from token endpoint")


def delete_gateway(gateway_client, gateway_name):
    """AgentCore Gateway とそのすべてのターゲットを削除。

    Args:
        gateway_client: bedrock-agentcore-control 用の Boto3 クライアント
        gateway_id: 削除する Gateway の ID
    """
    gateway_id = get_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_id")

    print("Gateway のすべてのターゲットを削除中", gateway_id)
    list_response = gateway_client.list_gateway_targets(
        gatewayIdentifier=gateway_id, maxResults=100
    )
    for item in list_response["items"]:
        target_id = item["targetId"]
        print("ターゲットを削除中 ", target_id)
        gateway_client.delete_gateway_target(
            gatewayIdentifier=gateway_id, targetId=target_id
        )
    # wait for 30 secs
    time.sleep(30)

    list_response = gateway_client.list_gateway_targets(
        gatewayIdentifier=gateway_id, maxResults=100
    )
    if len(list_response["items"]) > 0:
        print(f"{len(list_response['items'])} 件のターゲットが正常に削除されませんでした)")
    else:
        print("すべてのターゲットを正常に削除しました)")

    print("Gateway を削除中 ", gateway_id)
    gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
