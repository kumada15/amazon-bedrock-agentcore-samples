import boto3
from boto3.session import Session


def setup_cognito_user_pool():
    """Cognito ユーザープールをセットアップし、必要な認証情報を返します。"""
    boto_session = Session()
    region = boto_session.region_name
    # Cognito クライアントを初期化
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        # ユーザープールを作成
        user_pool_response = cognito_client.create_user_pool(
            PoolName="agentpool", Policies={"PasswordPolicy": {"MinimumLength": 8}}
        )
        pool_id = user_pool_response["UserPool"]["Id"]
        # アプリクライアントを作成
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="MCPServerPoolClient",
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )
        client_id = app_client_response["UserPoolClient"]["ClientId"]
        # ユーザーを作成
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username="testuser",
            TemporaryPassword="Temp123!",
            MessageAction="SUPPRESS",
        )
        # 永続パスワードを設定
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username="testuser",
            Password="MyPassword123!",
            Permanent=True,
        )
        # ユーザーを認証してアクセストークンを取得
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": "testuser", "PASSWORD": "MyPassword123!"},
        )
        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        # 必要な値を出力
        print(f"プール ID: {pool_id}")
        print(
            f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        )
        print(f"クライアント ID: {client_id}")
        print(f"Bearer トークン: {bearer_token}")

        # 後続処理用に値を返す
        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "bearer_token": bearer_token,
            "discovery_url": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration",
        }
    except Exception as e:
        print(f"エラー: {e}")
        return None


def reauthenticate_user(client_id):
    """ユーザーを再認証して新しいアクセストークンを取得します。"""
    boto_session = Session()
    region = boto_session.region_name
    # Cognito クライアントを初期化
    cognito_client = boto3.client("cognito-idp", region_name=region)
    # ユーザーを認証してアクセストークンを取得
    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": "testuser", "PASSWORD": "MyPassword123!"},
    )
    bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
    return bearer_token


def delete_cognito_user_pool(pool_id=None):
    """
    ID で Cognito ユーザープールを削除するか、ID が指定されていない場合は agentpool を検索して削除します。

    Args:
        pool_id: 削除するプール ID（オプション）

    Returns:
        bool: 削除が成功した場合は True、それ以外は False
    """
    boto_session = Session()
    region = boto_session.region_name
    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        # pool_id が指定されていない場合は agentpool を検索
        if not pool_id:
            response = cognito_client.list_user_pools(MaxResults=60)
            for pool in response.get("UserPools", []):
                if pool.get("Name") == "agentpool":
                    pool_id = pool.get("Id")
                    break

            if not pool_id:
                print("agentpool が見つかりません")
                return False

        # ユーザープールを削除
        print(f"Cognito ユーザープールを削除中: {pool_id}")
        cognito_client.delete_user_pool(UserPoolId=pool_id)
        print(f"ユーザープールを正常に削除しました: {pool_id}")
        return True

    except Exception as e:
        print(f"ユーザープールの削除中にエラー: {e}")
        return False
