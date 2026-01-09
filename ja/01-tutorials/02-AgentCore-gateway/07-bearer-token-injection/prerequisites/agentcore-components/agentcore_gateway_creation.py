"""
AgentCore Gateway 作成モジュール。

このモジュールは、Asana 統合用の AWS Bedrock AgentCore Gateway の作成と設定を処理します。
ターゲット設定と認証情報管理を含みます。
"""

import json
import os
import sys

import boto3

# utils をインポートするために親ディレクトリをパスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(current_dir, "..", "..")
sys.path.insert(0, parent_dir)

try:
    from utils import get_ssm_parameter, put_ssm_parameter
except ImportError as e:
    print(f"utils のインポートエラー: {e}")
    print(f"カレントディレクトリ: {current_dir}")
    print(f"親ディレクトリ: {parent_dir}")
    print(f"Python パス: {sys.path}")
    raise

STS_CLIENT = boto3.client("sts")

# AWS アカウント詳細を取得
REGION = boto3.session.Session().region_name

GATEWAY_CLIENT = boto3.client(
    "bedrock-agentcore-control",
    region_name=REGION,
)

print("✅ AgentCore Gateway を取得中！")

GATEWAY_NAME = "agentcore-gw-asana-integration"


def create_agentcore_gateway():
    """AgentCore Gateway を作成または既存のものを取得します。

    Returns:
        Gateway 情報を含む辞書（id、name、url、arn）

    Raises:
        ValueError: 必要な SSM パラメータが不足している場合
        Exception: Gateway の作成または取得に失敗した場合
    """
    try:
        # 必要な SSM パラメータの存在を検証
        machine_client_id = get_ssm_parameter(
            "/app/asana/demo/agentcoregwy/machine_client_id"
        )
        cognito_discovery_url = get_ssm_parameter(
            "/app/asana/demo/agentcoregwy/cognito_discovery_url"
        )
        gateway_iam_role = get_ssm_parameter(
            "/app/asana/demo/agentcoregwy/gateway_iam_role"
        )

        if not all([machine_client_id, cognito_discovery_url, gateway_iam_role]):
            raise ValueError("必要な SSM パラメータが不足しているか空です")

        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [machine_client_id],
                "discoveryUrl": cognito_discovery_url,
            }
        }

        # 新しい Gateway を作成
        print(f"リージョン {REGION} に Gateway を作成中、名前: {GATEWAY_NAME}")

        create_response = GATEWAY_CLIENT.create_gateway(
            name=GATEWAY_NAME,
            roleArn=gateway_iam_role,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=auth_config,
            description="Asana Integration Demo AgentCore Gateway",
        )

        gateway_id = create_response["gatewayId"]

        gateway_info = {
            "id": gateway_id,
            "name": GATEWAY_NAME,
            "gateway_url": create_response["gatewayUrl"],
            "gateway_arn": create_response["gatewayArn"],
        }
        put_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_id", gateway_id)

        print(f"✅ Gateway が正常に作成されました、ID: {gateway_id}")

        return gateway_info

    except (
        GATEWAY_CLIENT.exceptions.ConflictException,
        GATEWAY_CLIENT.exceptions.ValidationException,
    ) as exc:
        # Gateway が存在する場合、SSM から既存の Gateway ID を取得
        print(f"Gateway の作成に失敗: {exc}")
        try:
            existing_gateway_id = get_ssm_parameter(
                "/app/asana/demo/agentcoregwy/gateway_id"
            )
            if not existing_gateway_id:
                raise ValueError("Gateway ID パラメータは存在しますが空です") from exc

            print(f"既存の Gateway を発見、ID: {existing_gateway_id}")

            # 既存の Gateway 詳細を取得
            gateway_response = GATEWAY_CLIENT.get_gateway(
                gatewayIdentifier=existing_gateway_id
            )
            gateway_info = {
                "id": existing_gateway_id,
                "name": gateway_response["name"],
                "gateway_url": gateway_response["gatewayUrl"],
                "gateway_arn": gateway_response["gatewayArn"],
            }
            return gateway_info
        except ValueError as ve:
            raise ve
        except Exception as e:
            raise RuntimeError(f"既存の Gateway の取得に失敗: {str(e)}") from e
    except ValueError as ve:
        raise ve
    except Exception as e:
        raise RuntimeError(f"Gateway 作成中に予期しないエラー: {str(e)}") from e


def load_api_spec(file_path: str) -> list:
    """JSON ファイルから API 仕様を読み込みます。

    Args:
        file_path: API 仕様を含む JSON ファイルへのパス

    Returns:
        API 仕様データを含むリスト

    Raises:
        ValueError: JSON ファイルがリストを含まない場合
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON ファイルにはリストが必要です")
    return data


def add_gateway_target(gateway_id):
    """API 仕様と認証情報設定でゲートウェイターゲットを追加します。

    Args:
        gateway_id: ターゲットを追加する Gateway の ID
    """
    try:
        api_spec_file = "../openapi-spec/openapi_simple.json"

        # API 仕様ファイルの存在を検証
        if not os.path.exists(api_spec_file):
            print(f"❌ API 仕様ファイルが見つかりません: {api_spec_file}")
            sys.exit(1)

        api_spec = load_api_spec(api_spec_file)
        print(f"✅ API 仕様ファイルを読み込みました: {api_spec}")

        # API 仕様構造を検証
        if not api_spec or not isinstance(api_spec[0], dict):
            raise ValueError("無効な API 仕様構造です")

        if "servers" not in api_spec[0] or not api_spec[0]["servers"]:
            raise ValueError("API 仕様に servers 設定がありません")

        api_gateway_url = get_ssm_parameter(
            "/app/asana/demo/agentcoregwy/apigateway_url"
        )

        # API Gateway URL を検証
        if not api_gateway_url or not api_gateway_url.startswith("https://"):
            raise ValueError("無効な API Gateway URL - HTTPS が必要です")

        api_spec[0]["servers"][0]["url"] = api_gateway_url

        print(f"✅ API Gateway URL を置換しました: {api_gateway_url}")

        print("✅ 認証情報プロバイダーを作成中...")
        acps = boto3.client(service_name="bedrock-agentcore-control")

        credential_provider_name = "AgentCoreAPIGatewayAPIKey"

        existing_credential_provider_response = acps.get_api_key_credential_provider(
            name=credential_provider_name
        )
        provider_arn = existing_credential_provider_response["credentialProviderArn"]
        print(f"既存の認証情報プロバイダーを発見、ARN: {provider_arn}")

        if provider_arn is None:
            print(
                f"❌ 認証情報プロバイダーが見つかりません、新規作成中: "
                f"{credential_provider_name}"
            )
            response = acps.create_api_key_credential_provider(
                name=credential_provider_name,
                apiKey=get_ssm_parameter("/app/asana/demo/agentcoregwy/api_key"),
            )

            print(response)
            credential_provider_arn = response["credentialProviderArn"]
            print(f"アウトバウンド認証情報プロバイダー ARN: {credential_provider_arn}")
        else:
            credential_provider_arn = provider_arn

        # API キー認証情報プロバイダー設定
        api_key_credential_config = [
            {
                "credentialProviderType": "API_KEY",
                "credentialProvider": {
                    "apiKeyCredentialProvider": {
                        # API Gateway オーソライザーが期待する API キー名
                        "credentialParameterName": "x-api-key",
                        "providerArn": credential_provider_arn,
                        # API キーの場所 - API Gateway の期待と一致する必要あり
                        "credentialLocation": "HEADER",
                        # "credentialPrefix": " "  # トークンのプレフィックス、例: "Basic"
                    }
                },
            }
        ]

        inline_spec = json.dumps(api_spec[0])
        print(f"✅ inline_spec を作成しました: {inline_spec}")
        # OpenAPI 仕様ファイルの S3 URI
        agentcoregwy_openapi_target_config = {
            "mcp": {"openApiSchema": {"inlinePayload": inline_spec}}
        }
        print("✅ Gateway ターゲットを作成中...")
        create_target_response = GATEWAY_CLIENT.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name="AgentCoreGwyAPIGatewayTarget",
            description="APIGateway Target for Asana and other 3P APIs",
            targetConfiguration=agentcoregwy_openapi_target_config,
            credentialProviderConfigurations=api_key_credential_config,
        )

        print(f"✅ Gateway ターゲットが作成されました: {create_target_response['targetId']}")

    except GATEWAY_CLIENT.exceptions.ConflictException as exc:
        print(f"❌ Gateway ターゲットは既に存在します: {str(exc)}")
        # 必要に応じて既存ターゲットを更新するロジックを実装可能
    except GATEWAY_CLIENT.exceptions.ValidationException as exc:
        print(f"❌ Gateway ターゲット作成中の検証エラー: {str(exc)}")
        raise
    except FileNotFoundError as exc:
        print(f"❌ API 仕様ファイルが見つかりません: {str(exc)}")
        raise
    except ValueError as exc:
        print(f"❌ 無効な設定: {str(exc)}")
        raise
    except Exception as exc:
        print(f"❌ Gateway ターゲット作成中に予期しないエラー: {str(exc)}")
        raise


if __name__ == "__main__":
    gateway = create_agentcore_gateway()
    add_gateway_target(gateway["id"])
