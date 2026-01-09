import json
import time
from typing import Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError

LAMBDA_EXECUTION_ROLE_POLICY = (
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)
LAMBDA_RUNTIME = "python3.12"
LAMBDA_HANDLER = "lambda_function_code.lambda_handler"
LAMBDA_PACKAGE_TYPE = "Zip"

IAM_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

# AgentCore Gateway IAM Role constants
GATEWAY_AGENTCORE_ROLE_NAME = "GatewaySearchAgentCoreRole"
GATEWAY_AGENTCORE_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

GATEWAY_AGENTCORE_POLICY_NAME = "BedrockAgentPolicy"

# Cognito configuration constants
COGNITO_POOL_NAME = "MCPServerPool"
COGNITO_CLIENT_NAME = "MCPServerPoolClient"
COGNITO_PASSWORD_MIN_LENGTH = 8
COGNITO_DEFAULT_USERNAME = "testuser"
COGNITO_DEFAULT_TEMP_PASSWORD = "Temp123!"
COGNITO_DEFAULT_PASSWORD = "MyPassword123!"

COGNITO_AUTH_FLOWS = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]

COGNITO_PASSWORD_POLICY = {
    "PasswordPolicy": {"MinimumLength": COGNITO_PASSWORD_MIN_LENGTH}
}


def _format_error_message(error: ClientError) -> str:
    """ClientError からエラーメッセージをフォーマット。"""
    return f"{error.response['Error']['Code']}-{error.response['Error']['Message']}"


def _create_or_get_iam_role(iam_client, role_name: str) -> str:
    """IAM ロールを作成するか、既存のロール ARN を返す。"""
    try:
        print("Lambda関数用のIAMロールを作成中")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(IAM_TRUST_POLICY),
            Description="IAM role to be assumed by lambda function",
        )
        role_arn = response["Role"]["Arn"]

        print("IAMロールにポリシーをアタッチ中")
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=LAMBDA_EXECUTION_ROLE_POLICY,
        )

        print(f"ロール '{role_name}' を正常に作成しました: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            print(f"IAMロール {role_name} は既に存在します。同じARN {role_arn} を使用します")
            return role_arn
        else:
            raise error


def _create_or_get_lambda_function(
    lambda_client, function_name: str, role_arn: str, code: bytes
) -> str:
    """Lambda 関数を作成するか、既存の関数 ARN を返す。"""
    try:
        print("Lambda関数を作成中")
        response = lambda_client.create_function(
            FunctionName=function_name,
            Role=role_arn,
            Runtime=LAMBDA_RUNTIME,
            Handler=LAMBDA_HANDLER,
            Code={"ZipFile": code},
            Description="Lambda function example for Bedrock AgentCore Gateway",
            PackageType=LAMBDA_PACKAGE_TYPE,
        )
        return response["FunctionArn"]

    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceConflictException":
            response = lambda_client.get_function(FunctionName=function_name)
            lambda_arn = response["Configuration"]["FunctionArn"]
            print(
                f"AWS Lambda関数 {function_name} は既に存在します。同じARN {lambda_arn} を使用します"
            )
            return lambda_arn
        else:
            raise error


def create_gateway_lambda(
    lambda_function_code_path: str, lambda_function_name: str
) -> Dict[str, Union[str, int]]:
    """AgentCore Gateway 用の IAM ロール付き AWS Lambda 関数を作成。

    Args:
        lambda_function_code_path: Lambda 関数コード zip ファイルへのパス
        lambda_function_name: Lambda 関数の名前

    Returns:
        'lambda_function_arn' と 'exit_code' キーを持つ辞書
    """
    session = boto3.Session()
    region = session.region_name

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    role_name = f"{lambda_function_name}_lambda_iamrole"

    print("zipファイルからコードを読み込み中")
    with open(lambda_function_code_path, "rb") as f:
        lambda_function_code = f.read()

    try:
        role_arn = _create_or_get_iam_role(iam_client, role_name)
        time.sleep(20)
        try:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )
        except ClientError:
            lambda_arn = _create_or_get_lambda_function(
                lambda_client, lambda_function_name, role_arn, lambda_function_code
            )

        return {"lambda_function_arn": lambda_arn, "exit_code": 0}

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"エラー: {error_message}")
        return {"lambda_function_arn": error_message, "exit_code": 1}
    except Exception as error:
        print(f"予期しないエラー: {str(error)}")
        return {"lambda_function_arn": str(error), "exit_code": 1}


def _create_cognito_user_pool(cognito_client, pool_name: str) -> str:
    """Cognito User Pool を作成してプール ID を返す。"""
    print(f"Cognito User Poolを作成中: {pool_name}")
    response = cognito_client.create_user_pool(
        PoolName=pool_name, Policies=COGNITO_PASSWORD_POLICY
    )
    pool_id = response["UserPool"]["Id"]
    print(f"User Poolを作成しました。ID: {pool_id}")
    return pool_id


def _create_cognito_app_client(cognito_client, pool_id: str, client_name: str) -> str:
    """Cognito アプリクライアントを作成してクライアント ID を返す。"""
    print(f"Cognitoアプリクライアントを作成中: {client_name}")
    response = cognito_client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=client_name,
        GenerateSecret=False,
        ExplicitAuthFlows=COGNITO_AUTH_FLOWS,
    )
    client_id = response["UserPoolClient"]["ClientId"]
    print(f"アプリクライアントを作成しました。ID: {client_id}")
    return client_id


def _create_cognito_user(
    cognito_client,
    pool_id: str,
    username: str,
    temp_password: str,
    permanent_password: str,
) -> None:
    """一時パスワードで Cognito ユーザーを作成し、恒久パスワードを設定。"""
    print(f"Cognitoユーザーを作成中: {username}")
    cognito_client.admin_create_user(
        UserPoolId=pool_id,
        Username=username,
        TemporaryPassword=temp_password,
        MessageAction="SUPPRESS",
    )

    print(f"ユーザーの恒久パスワードを設定中: {username}")
    cognito_client.admin_set_user_password(
        UserPoolId=pool_id,
        Username=username,
        Password=permanent_password,
        Permanent=True,
    )


def _authenticate_user(
    cognito_client, client_id: str, username: str, password: str
) -> str:
    """ユーザーを認証してアクセストークンを返す。"""
    print(f"ユーザーを認証中: {username}")
    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return auth_response["AuthenticationResult"]["AccessToken"]


def get_bearer_token(
    client_id: str, username: str, password: str, region: Optional[str] = None
) -> Optional[str]:
    """既存の Cognito User Pool からベアラートークンを取得。

    Args:
        client_id: Cognito アプリクライアント ID
        username: 認証用ユーザー名
        password: ユーザーパスワード
        region: AWS リージョン（None の場合、セッションのデフォルトを使用）

    Returns:
        ベアラートークン文字列、認証失敗の場合は None
    """
    if not region:
        session = boto3.Session()
        region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        print(f"ユーザーを認証中: {username}")
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        print(f"ベアラートークンを正常に取得しました")
        return bearer_token

    except ClientError as error:
        if error.response["Error"]["Code"] == "NotAuthorizedException":
            print(f"認証失敗: ユーザー {username} の認証情報が無効です")
        elif error.response["Error"]["Code"] == "UserNotFoundException":
            print(f"認証失敗: ユーザー {username} が見つかりません")
        elif error.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"認証失敗: クライアントID {client_id} が見つかりません")
        else:
            error_message = _format_error_message(error)
            print(f"Cognitoクライアントエラー: {error_message}")
        return None
    except Exception as error:
        print(f"ベアラートークン取得中に予期しないエラー: {str(error)}")
        return None


def create_gateway_iam_role(
    lambda_arns: List[str],
    role_name: str = GATEWAY_AGENTCORE_ROLE_NAME,
    policy_name: str = GATEWAY_AGENTCORE_POLICY_NAME,
) -> Optional[str]:
    """Lambda 呼び出し権限付き AgentCore Gateway 用の IAM ロールを作成。

    Args:
        lambda_arns: 呼び出し権限を付与する Lambda 関数 ARN のリスト
        role_name: IAM ロールの名前
        policy_name: インラインポリシーの名前

    Returns:
        ロール ARN 文字列、作成失敗の場合は None
    """
    session = boto3.Session()
    region = session.region_name

    iam_client = boto3.client("iam", region_name=region)

    try:
        # Create the IAM role
        print(f"IAMロールを作成中: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(GATEWAY_AGENTCORE_TRUST_POLICY),
            Description="IAM role for AgentCore Gateway to invoke Lambda functions",
        )
        role_arn = response["Role"]["Arn"]

        # Create the inline policy document
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeFunction",
                    "Effect": "Allow",
                    "Action": "lambda:InvokeFunction",
                    "Resource": lambda_arns,
                }
            ],
        }

        # Attach the inline policy
        print(f"ポリシーをアタッチ中: {policy_name}")
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )

        print(f"Gateway IAMロールを正常に作成しました: {role_arn}")
        return role_arn

    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"IAMロール {role_name} は既に存在します。既存のロールを取得中...")
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]

            # Update the policy if role exists
            try:
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "InvokeFunction",
                            "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": lambda_arns,
                        }
                    ],
                }

                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document),
                )
                print(f"既存ロールのポリシーを更新しました: {role_arn}")

            except ClientError as policy_error:
                print(
                    f"警告: ポリシーを更新できませんでした: {_format_error_message(policy_error)}"
                )

            return role_arn
        else:
            error_message = _format_error_message(error)
            print(f"IAMロール作成エラー: {error_message}")
            return None
    except Exception as error:
        print(f"IAMロール作成中に予期しないエラー: {str(error)}")
        return None


def _extract_function_name_from_arn(lambda_arn: str) -> str:
    """Lambda ARN から関数名を抽出。

    Args:
        lambda_arn: Lambda 関数 ARN

    Returns:
        ARN から抽出した関数名

    Example:
        arn:aws:lambda:us-east-1:123456789012:function:my-function -> my-function
    """
    # ARN format: arn:aws:lambda:region:account:function:function-name
    if lambda_arn.startswith("arn:aws:lambda:"):
        return lambda_arn.split(":")[-1]
    else:
        # If it's already a function name, return as is
        return lambda_arn


def delete_gateway_lambda(lambda_function_arn: str) -> bool:
    """Lambda 関数と関連する IAM ロールを削除。

    Args:
        lambda_function_arn: 削除する Lambda 関数の ARN または名前

    Returns:
        削除成功の場合は True、それ以外は False
    """
    session = boto3.Session()
    region = session.region_name

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    # Extract function name from ARN
    lambda_function_name = _extract_function_name_from_arn(lambda_function_arn)
    role_name = f"{lambda_function_name}_lambda_iamrole"

    try:
        # Delete Lambda function (can use ARN or name)
        print(f"Lambda関数を削除中: {lambda_function_name}")
        lambda_client.delete_function(FunctionName=lambda_function_arn)
        print(f"Lambda関数 {lambda_function_name} を正常に削除しました")

        # Delete IAM role and detach policies
        try:
            print(f"IAMロールからポリシーをデタッチ中: {role_name}")
            iam_client.detach_role_policy(
                RoleName=role_name,
                PolicyArn=LAMBDA_EXECUTION_ROLE_POLICY,
            )

            print(f"IAMロールを削除中: {role_name}")
            iam_client.delete_role(RoleName=role_name)
            print(f"IAMロール {role_name} を正常に削除しました")

        except ClientError as role_error:
            if role_error.response["Error"]["Code"] == "NoSuchEntity":
                print(f"IAMロール {role_name} が見つかりません。スキップします")
            else:
                print(
                    f"警告: IAMロールを削除できませんでした: {_format_error_message(role_error)}"
                )

        return True

    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Lambda関数 {lambda_function_name} が見つかりません")
            return False
        else:
            error_message = _format_error_message(error)
            print(f"Lambda関数削除エラー: {error_message}")
            return False
    except Exception as error:
        print(f"Lambda関数削除中に予期しないエラー: {str(error)}")
        return False


def delete_gateway_iam_role(
    role_name: str = GATEWAY_AGENTCORE_ROLE_NAME,
    policy_name: str = GATEWAY_AGENTCORE_POLICY_NAME,
) -> bool:
    """AgentCore Gateway 用の IAM ロールを削除。

    Args:
        role_name: 削除する IAM ロールの名前
        policy_name: 削除するインラインポリシーの名前

    Returns:
        削除成功の場合は True、それ以外は False
    """
    session = boto3.Session()
    region = session.region_name

    iam_client = boto3.client("iam", region_name=region)

    try:
        # Delete inline policy first
        print(f"インラインポリシーを削除中: {policy_name}")
        iam_client.delete_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
        )
        print(f"インラインポリシー {policy_name} を正常に削除しました")

        # Delete IAM role
        print(f"IAMロールを削除中: {role_name}")
        iam_client.delete_role(RoleName=role_name)
        print(f"IAMロール {role_name} を正常に削除しました")

        return True

    except ClientError as error:
        if error.response["Error"]["Code"] == "NoSuchEntity":
            print(f"IAMロール {role_name} またはポリシー {policy_name} が見つかりません")
            return False
        else:
            error_message = _format_error_message(error)
            print(f"IAMロール削除エラー: {error_message}")
            return False
    except Exception as error:
        print(f"IAMロール削除中に予期しないエラー: {str(error)}")
        return False


def delete_cognito_user_pool(
    pool_name: str = COGNITO_POOL_NAME,
    username: str = COGNITO_DEFAULT_USERNAME,
) -> bool:
    """Cognito User Pool と関連リソースを削除。

    Args:
        pool_name: 削除する Cognito User Pool の名前
        username: プールから削除するユーザー名

    Returns:
        削除成功の場合は True、それ以外は False
    """
    session = boto3.Session()
    region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        # Find the User Pool by name
        print(f"User Poolを検索中: {pool_name}")
        response = cognito_client.list_user_pools(MaxResults=50)

        pool_id = None
        for pool in response["UserPools"]:
            if pool["Name"] == pool_name:
                pool_id = pool["Id"]
                break

        if not pool_id:
            print(f"User Pool {pool_name} が見つかりません")
            return False

        # Delete user first
        try:
            print(f"ユーザーを削除中: {username}")
            cognito_client.admin_delete_user(
                UserPoolId=pool_id,
                Username=username,
            )
            print(f"ユーザー {username} を正常に削除しました")
        except ClientError as user_error:
            if user_error.response["Error"]["Code"] == "UserNotFoundException":
                print(f"ユーザー {username} が見つかりません。スキップします")
            else:
                print(
                    f"警告: ユーザーを削除できませんでした: {_format_error_message(user_error)}"
                )

        # Delete User Pool (this will also delete app clients)
        print(f"User Poolを削除中: {pool_name}")
        cognito_client.delete_user_pool(UserPoolId=pool_id)
        print(f"User Pool {pool_name} を正常に削除しました")

        return True

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Cognito User Pool削除エラー: {error_message}")
        return False
    except Exception as error:
        print(f"Cognito User Pool削除中に予期しないエラー: {str(error)}")
        return False


def setup_cognito_user_pool(
    pool_name: str = COGNITO_POOL_NAME,
    client_name: str = COGNITO_CLIENT_NAME,
    username: str = COGNITO_DEFAULT_USERNAME,
    temp_password: str = COGNITO_DEFAULT_TEMP_PASSWORD,
    permanent_password: str = COGNITO_DEFAULT_PASSWORD,
) -> Optional[Dict[str, str]]:
    """アプリクライアントとテストユーザーを持つ Cognito User Pool をセットアップ。

    Args:
        pool_name: Cognito User Pool の名前
        client_name: アプリクライアントの名前
        username: テストユーザーのユーザー名
        temp_password: テストユーザーの一時パスワード
        permanent_password: テストユーザーの恒久パスワード

    Returns:
        client_id と discovery_url を含む辞書、セットアップ失敗の場合は None
    """
    session = boto3.Session()
    region = session.region_name

    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        pool_id = _create_cognito_user_pool(cognito_client, pool_name)
        client_id = _create_cognito_app_client(cognito_client, pool_id, client_name)

        _create_cognito_user(
            cognito_client, pool_id, username, temp_password, permanent_password
        )

        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"

        # Output the required values
        print(f"プールID: {pool_id}")
        print(f"ディスカバリURL: {discovery_url}")
        print(f"クライアントID: {client_id}")

        return {
            "client_id": client_id,
            "discovery_url": discovery_url,
        }

    except ClientError as error:
        error_message = _format_error_message(error)
        print(f"Cognitoクライアントエラー: {error_message}")
        return None
    except Exception as error:
        print(f"Cognitoセットアップ中に予期しないエラー: {str(error)}")
        return None
