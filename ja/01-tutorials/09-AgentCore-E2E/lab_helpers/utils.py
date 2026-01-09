import base64
import hashlib
import hmac
import json
import os
from typing import Any, Dict

import boto3
import yaml
from boto3.session import Session

sts_client = boto3.client("sts")

# AWS アカウント詳細を取得
REGION = boto3.session.Session().region_name

username = "testuser"
sm_name = "customer_support_agent"


role_name = f"CustomerSupportAssistantBedrockAgentCoreRole-{REGION}"
policy_name = f"CustomerSupportAssistantBedrockAgentCorePolicy-{REGION}"


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def put_ssm_parameter(
    name: str, value: str, parameter_type: str = "String", with_encryption: bool = False
) -> None:
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


def delete_ssm_parameter(name: str) -> None:
    ssm = boto3.client("ssm")
    try:
        ssm.delete_parameter(Name=name)
    except ssm.exceptions.ParameterNotFound:
        pass


def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data


def get_aws_region() -> str:
    session = Session()
    return session.region_name


def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def get_cognito_client_secret() -> str:
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/customersupport/agentcore/pool_id"),
        ClientId=get_ssm_parameter("/app/customersupport/agentcore/client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def read_config(file_path: str) -> Dict[str, Any]:
    """
    ファイルパスから設定を読み込みます。JSON、YAML、YML フォーマットをサポートします。

    Args:
        file_path (str): 設定ファイルへのパス

    Returns:
        Dict[str, Any]: 辞書としての設定データ

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: ファイルフォーマットがサポートされていないか無効な場合
        yaml.YAMLError: YAML パースに失敗した場合
        json.JSONDecodeError: JSON パースに失敗した場合
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # ファイル拡張子を取得してフォーマットを判定
    _, ext = os.path.splitext(file_path.lower())

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            if ext == ".json":
                return json.load(file)
            elif ext in [".yaml", ".yml"]:
                return yaml.safe_load(file)
            else:
                # JSON を先に試し、次に YAML を試してフォーマットを自動検出
                content = file.read()
                file.seek(0)

                # JSON を先に試す
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # YAML を試す
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        raise ValueError(
                            f"Unsupported configuration file format: {ext}. "
                            f"Supported formats: .json, .yaml, .yml"
                        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file {file_path}: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file {file_path}: {e}")


def save_customer_support_secret(secret_value):
    """AWS Secrets Manager にシークレットを保存します。"""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)

    try:
        secrets_client.create_secret(
            Name=sm_name,
            SecretString=secret_value,
            Description="Secret containing the Cognito Configuration for the Customer Support Agent",
        )
        print("✅ シークレットを作成しました")
    except secrets_client.exceptions.ResourceExistsException:
        secrets_client.update_secret(SecretId=sm_name, SecretString=secret_value)
        print("✅ 既存のシークレットを更新しました")
    except Exception as e:
        print(f"❌ シークレット保存エラー: {str(e)}")
        return False
    return True


def get_customer_support_secret():
    """AWS Secrets Manager からシークレット値を取得します。"""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        response = secrets_client.get_secret_value(SecretId=sm_name)
        return response["SecretString"]
    except Exception as e:
        print(f"❌ シークレット取得エラー: {str(e)}")
        return None


def delete_customer_support_secret():
    """AWS Secrets Manager からシークレットを削除します。"""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        secrets_client.delete_secret(
            SecretId=sm_name, ForceDeleteWithoutRecovery=True
        )
        print("✅ シークレットを削除しました！")
        return True
    except Exception as e:
        print(f"❌ シークレット削除エラー: {str(e)}")
        return False


def get_or_create_cognito_pool(refresh_token=False):
    boto_session = Session()
    region = boto_session.region_name
    # Cognito クライアントを初期化
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        # 既存の Cognito プールを確認
        cognito_config_str = get_customer_support_secret()
        cognito_config = json.loads(cognito_config_str)
        if refresh_token:
            cognito_config["bearer_token"] = reauthenticate_user(
                cognito_config["client_id"], cognito_config["client_secret"]
            )
        return cognito_config
    except Exception:
        print("既存の Cognito 設定が見つかりません。新規作成中...")

    try:
        # ユーザープールを作成
        user_pool_response = cognito_client.create_user_pool(
            PoolName="MCPServerPool", Policies={"PasswordPolicy": {"MinimumLength": 8}}
        )
        pool_id = user_pool_response["UserPool"]["Id"]
        # アプリクライアントを作成
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="MCPServerPoolClient",
            GenerateSecret=True,
            ExplicitAuthFlows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
                "ALLOW_USER_SRP_AUTH",
            ],
        )
        print(app_client_response["UserPoolClient"])
        client_id = app_client_response["UserPoolClient"]["ClientId"]
        client_secret = app_client_response["UserPoolClient"]["ClientSecret"]

        # ユーザーを作成
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            TemporaryPassword="Temp123!",
            MessageAction="SUPPRESS",
        )

        # 永続パスワードを設定
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password="MyPassword123!",
            Permanent=True,
        )

        message = bytes(username + client_id, "utf-8")
        key = bytes(client_secret, "utf-8")
        secret_hash = base64.b64encode(
            hmac.new(key, message, digestmod=hashlib.sha256).digest()
        ).decode()

        # ユーザーを認証してアクセストークンを取得
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": "MyPassword123!",
                "SECRET_HASH": secret_hash,
            },
        )
        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        # 必要な値を出力
        print(f"プール ID: {pool_id}")
        print(f"ディスカバリー URL: {discovery_url}")
        print(f"クライアント ID: {client_id}")
        print(f"ベアラートークン: {bearer_token}")
        # 追加処理が必要な場合は値を返す
        cognito_config = {
            "pool_id": pool_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "secret_hash": secret_hash,
            "bearer_token": bearer_token,
            "discovery_url": discovery_url,
        }
        put_ssm_parameter("/app/customersupport/agentcore/client_id", client_id)
        put_ssm_parameter("/app/customersupport/agentcore/pool_id", pool_id)
        put_ssm_parameter(
            "/app/customersupport/agentcore/cognito_discovery_url", discovery_url
        )
        put_ssm_parameter("/app/customersupport/agentcore/client_secret", client_secret)

        save_customer_support_secret(json.dumps(cognito_config))

        return cognito_config
    except Exception as e:
        print(f"エラー: {e}")
        return None


def cleanup_cognito_resources(pool_id):
    """
    ユーザー、アプリクライアント、ユーザープールを含む Cognito リソースを削除します
    """
    try:
        # Cognito クライアントを初期化 using the same session configuration
        boto_session = Session()
        region = boto_session.region_name
        cognito_client = boto3.client("cognito-idp", region_name=region)

        if pool_id:
            try:
                # すべてのアプリクライアントを一覧表示して削除
                clients_response = cognito_client.list_user_pool_clients(
                    UserPoolId=pool_id, MaxResults=60
                )

                for client in clients_response["UserPoolClients"]:
                    print(f"アプリクライアントを削除中: {client['ClientName']}")
                    cognito_client.delete_user_pool_client(
                        UserPoolId=pool_id, ClientId=client["ClientId"]
                    )

                # すべてのユーザーを一覧表示して削除
                users_response = cognito_client.list_users(
                    UserPoolId=pool_id, AttributesToGet=["email"]
                )

                for user in users_response.get("Users", []):
                    print(f"ユーザーを削除中: {user['Username']}")
                    cognito_client.admin_delete_user(
                        UserPoolId=pool_id, Username=user["Username"]
                    )

                # ユーザープールを削除
                print(f"ユーザープールを削除中: {pool_id}")
                cognito_client.delete_user_pool(UserPoolId=pool_id)

                print("すべての Cognito リソースのクリーンアップが完了しました")
                return True

            except cognito_client.exceptions.ResourceNotFoundException:
                print(
                    f"ユーザープール {pool_id} が見つかりません。既に削除されている可能性があります。"
                )
                return True

            except Exception as e:
                print(f"クリーンアップ中にエラーが発生: {str(e)}")
                return False
        else:
            print("一致するユーザープールが見つかりません")
            return True

    except Exception as e:
        print(f"クリーンアップの初期化中にエラーが発生: {str(e)}")
        return False


def reauthenticate_user(client_id, client_secret):
    boto_session = Session()
    region = boto_session.region_name
    # Cognito クライアントを初期化
    cognito_client = boto3.client("cognito-idp", region_name=region)
    # ユーザーを認証してアクセストークンを取得

    message = bytes(username + client_id, "utf-8")
    key = bytes(client_secret, "utf-8")
    secret_hash = base64.b64encode(
        hmac.new(key, message, digestmod=hashlib.sha256).digest()
    ).decode()

    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": "MyPassword123!",
            "SECRET_HASH": secret_hash,
        },
    )
    bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
    return bearer_token


def create_agentcore_runtime_execution_role():
    iam = boto3.client("iam")
    boto_session = Session()
    region = boto_session.region_name
    account_id = get_aws_account_id()

    # 信頼関係ポリシー
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    },
                },
            }
        ],
    }

    # IAM ポリシードキュメント
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                "Resource": [f"arn:aws:ecr:{region}:{account_id}:repository/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogGroups"],
                "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ],
            },
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": ["ecr:GetAuthorizationToken"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                "Resource": ["*"],
            },
            {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                },
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/customer_support_agent-*",
                ],
            },
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:ApplyGuardrail",
                    "bedrock:Retrieve",
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{region}:{account_id}:*",
                ],
            },
            {
                "Sid": "AllowAgentToUseMemory",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                    "bedrock-agentcore:ListMemoryRecords",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"],
            },
            {
                "Sid": "GetMemoryId",
                "Effect": "Allow",
                "Action": ["ssm:GetParameter"],
                "Resource": [f"arn:aws:ssm:{region}:{account_id}:parameter/*"],
            },
            {
                "Sid": "GatewayAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:InvokeGateway",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/*"
                ],
            },
        ],
    }

    try:
        # ロールが既に存在するか確認
        try:
            existing_role = iam.get_role(RoleName=role_name)
            print(f"ℹ️ ロール {role_name} は既に存在します")
            print(f"ロール ARN: {existing_role['Role']['Arn']}")
            return existing_role["Role"]["Arn"]
        except iam.exceptions.NoSuchEntityException:
            pass

        # IAM ロールを作成
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="IAM role for Amazon Bedrock AgentCore with required permissions",
        )

        print(f"✅ IAM ロールを作成しました: {role_name}")
        print(f"ロール ARN: {role_response['Role']['Arn']}")

        # ポリシーが既に存在するか確認
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        try:
            iam.get_policy(PolicyArn=policy_arn)
            print(f"ℹ️ ポリシー {policy_name} は既に存在します")
        except iam.exceptions.NoSuchEntityException:
            # ポリシーを作成
            policy_response = iam.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description="Policy for Amazon Bedrock AgentCore permissions",
            )
            print(f"✅ ポリシーを作成しました: {policy_name}")
            policy_arn = policy_response["Policy"]["Arn"]

        # ポリシーをロールにアタッチ
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ ポリシーをロールにアタッチしました")
        except Exception as e:
            if "already attached" in str(e).lower():
                print("ℹ️ ポリシーは既にロールにアタッチされています")
            else:
                raise

        print(f"ポリシー ARN: {policy_arn}")

        put_ssm_parameter(
            "/app/customersupport/agentcore/runtime_execution_role_arn",
            role_response["Role"]["Arn"],
        )
        return role_response["Role"]["Arn"]

    except Exception as e:
        print(f"❌ IAM ロール作成エラー: {str(e)}")
        return None


def delete_agentcore_runtime_execution_role():
    iam = boto3.client("iam")

    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        # ポリシーをロールからデタッチ
        try:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ ポリシーをロールからデタッチしました")
        except Exception:
            pass

        # ロールを削除
        try:
            iam.delete_role(RoleName=role_name)
            print(f"✅ ロールを削除しました: {role_name}")
        except Exception:
            pass

        # ポリシーを削除
        try:
            iam.delete_policy(PolicyArn=policy_arn)
            print(f"✅ ポリシーを削除しました: {policy_name}")
        except Exception:
            pass

        delete_ssm_parameter(
            "/app/customersupport/agentcore/runtime_execution_role_arn"
        )

    except Exception as e:
        print(f"❌ クリーンアップ中にエラーが発生: {str(e)}")


def agentcore_memory_cleanup(memory_id: str = None):
    """すべてのメモリとそれに関連する戦略を一覧表示します"""
    control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    if memory_id:
        response = control_client.delete_memory(memoryId=memory_id)
        print(f"✅ メモリを正常に削除しました: {memory_id}")
    else:
        next_token = None
        while True:
            # リクエストパラメータを構築
            params = {}
            if next_token:
                params["nextToken"] = next_token

            # メモリを一覧表示
            try:
                response = control_client.list_memories(**params)

                # 各メモリを処理
                for memory in response.get("memories", []):
                    memory_id = memory.get("id")
                    print(f"\nメモリ ID: {memory_id}")
                    print(f"ステータス: {memory.get('status')}")
                    response = control_client.delete_memory(memoryId=memory_id)
                    response = control_client.list_memories(**params)
                    print(f"✅ メモリを正常に削除しました: {memory_id}")

                response = control_client.list_memories(**params)
                # 各メモリのステータスを処理
                for memory in response.get("memories", []):
                    memory_id = memory.get("id")
                    print(f"\nメモリ ID: {memory_id}")
                    print(f"ステータス: {memory.get('status')}")

            except Exception as e:
                print(f"⚠️  メモリ詳細の取得エラー: {e}")
            # 追加結果を確認
            next_token = response.get("nextToken")
            if not next_token:
                break


def gateway_target_cleanup(gateway_id: str = None):
    if not gateway_id:
        gateway_client = boto3.client(
            "bedrock-agentcore-control",
            region_name=REGION,
        )
        response = gateway_client.list_gateways()
        gateway_id = response["items"][0]["gatewayId"]
    print(f"🗑️  ゲートウェイのすべてのターゲットを削除中: {gateway_id}")

    # すべてのターゲットを一覧表示して削除
    list_response = gateway_client.list_gateway_targets(
        gatewayIdentifier=gateway_id, maxResults=100
    )

    for item in list_response["items"]:
        target_id = item["targetId"]
        print(f"   ターゲットを削除中: {target_id}")
        gateway_client.delete_gateway_target(
            gatewayIdentifier=gateway_id, targetId=target_id
        )
        print(f"   ✅ ターゲット {target_id} を削除しました")

    # Gateway を削除
    print(f"🗑️  ゲートウェイを削除中: {gateway_id}")
    gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
    print(f"✅ ゲートウェイ {gateway_id} を正常に削除しました")


def runtime_resource_cleanup(runtime_arn: str = None):
    try:
        # AWS クライアントを初期化
        agentcore_control_client = boto3.client(
            "bedrock-agentcore-control", region_name=REGION
        )
        if runtime_arn:
            runtime_id = runtime_arn.split(":")[-1].split("/")[-1]
            response = agentcore_control_client.delete_agent_runtime(
                agentRuntimeId=runtime_id
            )
            print(f"  ✅ エージェントランタイムを削除しました: {response['status']}")
        else:
            ecr_client = boto3.client("ecr", region_name=REGION)

            # Delete the AgentCore Runtime
            # print("  🗑️  Deleting AgentCore Runtime...")
            runtimes = agentcore_control_client.list_agent_runtimes()
            for runtime in runtimes["agentRuntimes"]:
                response = agentcore_control_client.delete_agent_runtime(
                    agentRuntimeId=runtime["agentRuntimeId"]
                )
                print(f"  ✅ エージェントランタイムを削除しました: {response['status']}")

        # ECR リポジトリを削除
        print("  🗑️  ECR リポジトリを削除中...")
        repositories = ecr_client.describe_repositories()
        for repo in repositories["repositories"]:
            if "bedrock-agentcore-customer_support_agent" in repo["repositoryName"]:
                ecr_client.delete_repository(
                    repositoryName=repo["repositoryName"], force=True
                )
                print(f"  ✅ ECR リポジトリを削除しました: {repo['repositoryName']}")

    except Exception as e:
        print(f"  ⚠️  ランタイムクリーンアップ中にエラーが発生: {e}")


def delete_observability_resources():
    # 設定
    log_group_name = "agents/customer-support-assistant-logs"
    log_stream_name = "default"

    logs_client = boto3.client("logs", region_name=REGION)

    # まずログストリームを削除（ロググループ削除前に行う必要がある）
    try:
        print(f"  🗑️  ログストリーム '{log_stream_name}' を削除中...")
        logs_client.delete_log_stream(
            logGroupName=log_group_name, logStreamName=log_stream_name
        )
        print(f"  ✅ ログストリーム '{log_stream_name}' を正常に削除しました")
    except Exception as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"  ℹ️  ログストリーム '{log_stream_name}' は存在しません")
        else:
            print(f"  ⚠️  ログストリーム削除エラー: {e}")

    # ロググループを削除
    try:
        print(f"  🗑️  ロググループ '{log_group_name}' を削除中...")
        logs_client.delete_log_group(logGroupName=log_group_name)
        print(f"  ✅ ロググループ '{log_group_name}' を正常に削除しました")
    except Exception as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"  ℹ️  ロググループ '{log_group_name}' は存在しません")
        else:
            print(f"  ⚠️  ロググループ削除エラー: {e}")


def local_file_cleanup():
    # クリーンアップするファイルのリスト
    files_to_delete = [
        "Dockerfile",
        ".dockerignore",
        ".bedrock_agentcore.yaml",
        "customer_support_agent.py",
        "agent_runtime.py",
    ]

    deleted_files = []
    missing_files = []

    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.unlink(file)
                deleted_files.append(file)
                print(f"  ✅ {file} を削除しました")
            except Exception as e:
                print(f"  ⚠️  {file} の削除エラー: {e}")
        else:
            missing_files.append(file)

    if deleted_files:
        print(f"\n📁 {len(deleted_files)} 個のファイルを正常に削除しました")
    if missing_files:
        print(
            f"ℹ️  {len(missing_files)} 個のファイルは既に存在しませんでした: {', '.join(missing_files)}"
        )
