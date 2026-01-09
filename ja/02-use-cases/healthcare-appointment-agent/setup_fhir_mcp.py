from dotenv import load_dotenv
import os
import json
import yaml
import argparse
import time
import utils
import botocore

load_dotenv()

# パラメータ設定
parser = argparse.ArgumentParser(
                    prog='setup_fhir_mcp',
                    description='FHIR ツール用 MCP Gateway のセットアップ',
                    epilog='入力パラメータ')

parser.add_argument('--op_type', help = "操作タイプ - Create または Delete")
parser.add_argument('--gateway_name', help = "Gateway の名前")
parser.add_argument('--gateway_id', help = "Gateway ID")

# boto3 セッションとクライアントの作成
(boto_session, agentcore_client) = utils.create_agentcore_client()

def read_and_stringify_openapispec(yaml_file_path):
    try:
        with open(yaml_file_path, 'r') as file:
            # YAML を Python 辞書にパース
            openapi_dict = yaml.safe_load(file)

            # 辞書を JSON 文字列に変換
            openapi_string = str(json.dumps(openapi_dict))

            return openapi_string

    except FileNotFoundError:
        return f"エラー: ファイル {yaml_file_path} が見つかりません"
    except yaml.YAMLError as e:
        return f"YAML パースエラー: {str(e)}"
    except Exception as e:
        return f"予期せぬエラーが発生しました: {str(e)}"

def create_gateway(gateway_name, gateway_desc):
    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [os.getenv("cognito_client_id")],
            "discoveryUrl": os.getenv("cognito_discovery_url")
        }
    }

    search_config = {
        "mcp": {
            "searchType": "SEMANTIC",
            "supportedVersions": ["2025-03-26"]
        }
    }

    response = agentcore_client.create_gateway(
        name=gateway_name,
        roleArn=os.getenv("gateway_iam_role"),
        #kmsKeyArn="<kms key here>",
        authorizerType="CUSTOM_JWT",
        description=gateway_desc,
        protocolType="MCP",
        authorizerConfiguration=auth_config,
        protocolConfiguration=search_config
    )

    #print(json.dumps(response, indent=2, default=str))
    return response['gatewayId']


def create_gatewaytarget(gateway_id, cred_provider_arn):
    openapi_spec = read_and_stringify_openapispec(os.getenv("openapi_spec_file"))

    credentiaConfig = {
        "credentialProviderType" : "OAUTH",
        "credentialProvider": {
            "oauthCredentialProvider": {
                "providerArn": cred_provider_arn,
                "scopes": [os.getenv("cognito_auth_scope")]
            }
        }
    }

    response = agentcore_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="Target1",
        description="Target 1",
        targetConfiguration={
            "mcp": {
                "openApiSchema": {
                    "inlinePayload":openapi_spec
                }
            }
        },
        credentialProviderConfigurations=[credentiaConfig]
    )

    #print(response)
    return response['targetId']

def delete_gatewaytarget(gateway_id):
    response = agentcore_client.list_gateway_targets(
        gatewayIdentifier=gateway_id
    )
    
    print(f"Gateway に対して {len(response['items'])} 件のターゲットが見つかりました")

    for target in response['items']:
        print(f"ターゲットを削除中 - 名前: {target['name']}、ID: {target['targetId']}")

        response = agentcore_client.delete_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target['targetId']
        )

def delete_gateway(gateway_id):
    response = agentcore_client.delete_gateway(
        gatewayIdentifier=gateway_id
    )

def create_egress_oauth_provider(gateway_name):
    cred_provider_name = f"{gateway_name}-oauth-credential-provider"

    try:
        agentcore_client.delete_oauth2_credential_provider(name=cred_provider_name)
        print(f"既存の egress 資格情報プロバイダーを削除しました: {cred_provider_name}")
        time.sleep(15)
    except botocore.exceptions.ClientError as err:
        raise Exception (f"エラーが発生しました - コード: {err.response['Error']['Code']}、メッセージ: {err.response['Error']['Message']}")

    try:
        provider_config= {
            "customOauth2ProviderConfig": {
                "oauthDiscovery": {
                    "authorizationServerMetadata": {
                        "issuer": os.getenv("cognito_issuer"),
                        "authorizationEndpoint": os.getenv("cognito_auth_endpoint"),
                        "tokenEndpoint": os.getenv("cognito_token_url"),
                        "responseTypes": ["token"]
                    }
                },
                "clientId": os.getenv("cognito_client_id"),
                "clientSecret": utils.get_cognito_client_secret(boto_session)
            }
        }

        response = agentcore_client.create_oauth2_credential_provider(
            name = cred_provider_name,
            credentialProviderVendor = 'CustomOauth2',
            oauth2ProviderConfigInput = provider_config
        )

        credentialProviderArn= response['credentialProviderArn']
        return credentialProviderArn
    except botocore.exceptions.ClientError as err:
        raise Exception (f"エラーが発生しました - コード: {err.response['Error']['Code']}、メッセージ: {err.response['Error']['Message']}")


if __name__ == "__main__":
    args = parser.parse_args()

    # バリデーション
    if args.op_type is None:
        raise Exception("操作タイプは必須です")
    else:
        if args.op_type.lower() == "create" or args.op_type.lower() == "delete":
            print(f"操作タイプ = {args.op_type}")
        else:
            raise Exception("操作タイプは Create または Delete のいずれかである必要があります")

    if args.gateway_name is None and args.op_type.lower() == "create":
        raise Exception("操作タイプが Create の場合、Gateway 名は必須です")
    elif args.gateway_name is not None:
        print(f"Gateway 名 = {args.gateway_name}")

    if args.gateway_id is None and args.op_type.lower() == "delete":
        raise Exception("操作タイプが Delete の場合、Gateway ID は必須です")
    elif args.gateway_id is not None:
        print(f"Gateway ID = {args.gateway_id}")

    if args.op_type.lower() == "create":
        print(f"Gateway を作成中: {args.gateway_name}")
        gatewayId = create_gateway(gateway_name=args.gateway_name, gateway_desc=args.gateway_name)
        print(f"Gateway が作成されました (ID: {gatewayId})。資格情報プロバイダーを作成中。")

        credProviderARN = create_egress_oauth_provider(gateway_name=args.gateway_name)
        print("Egress 資格情報プロバイダーが作成されました。Gateway ターゲットを作成中。")

        targetId = create_gatewaytarget(gateway_id=gatewayId, cred_provider_arn=credProviderARN)
        print(f"ターゲットが作成されました (ID: {targetId})")
    elif args.op_type.lower() == "delete":
        print(f"Gateway ID {args.gateway_id} のターゲットを検索・削除中")
        delete_gatewaytarget(gateway_id=args.gateway_id)
        print(f"Gateway を削除中 (ID: {args.gateway_id})")
        delete_gateway(gateway_id=args.gateway_id)
        print("Gateway が削除されました")
