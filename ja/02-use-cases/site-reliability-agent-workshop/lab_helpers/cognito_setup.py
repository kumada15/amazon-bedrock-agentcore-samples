"""
AIML301 ワークショップ用 Cognito セットアップヘルパー
Labs 3-5 の認証インフラストラクチャをセットアップ

認証フロー:
- Lab 3: エンドユーザー向け Cognito JWT 認証付き Gateway
- Lab 3-5: クライアント資格情報を使用した Gateway から Runtime への M2M 認証
- Labs 4+: 高度なユースケース向けのオプションのユーザーベースアクセス制御

作成される Cognito リソース:
1. User Pool: aiml301-UserPool
2. ユーザー認証クライアント: aiml301-UserAuthClient（パブリック、エンドユーザー認証用）
3. M2M クライアント: aiml301-M2MClient（機密、サービス間認証用）
4. リソースサーバー: aiml301-agentcore-runtime（カスタムスコープ付き）
5. User Pool ドメイン: aiml301-agentcore-{timestamp}
6. テストユーザー: testuser@aiml301.example.com
"""

import json
import time
import boto3
from typing import Dict, Any, Optional
from lab_helpers.config import AWS_REGION, AWS_PROFILE
from lab_helpers.parameter_store import put_parameter, get_parameter, delete_parameter
from lab_helpers.constants import PARAMETER_PATHS


class CognitoSetup:
    """Cognito User Pool のセットアップと設定を管理"""

    def __init__(self, region: str = AWS_REGION, profile: str = AWS_PROFILE):
        """Cognito クライアントとセッションを初期化"""
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.cognito = self.session.client('cognito-idp', region_name=region)
        self.region = region
        self.prefix = "aiml301"
        self.test_user_email = f"testuser@{self.prefix}.example.com"
        self.test_user_password = "<enter password>"  # Meets policy: uppercase, lowercase, numbers, symbols

    def create_user_pool(self) -> str:
        """
        セキュリティベストプラクティスに従って Cognito User Pool を作成

        Returns:
            User Pool ID
        """
        user_pool_name = f"{self.prefix}-UserPool"

        print(f"User Pool を作成中: {user_pool_name}...")

        try:
            response = self.cognito.create_user_pool(
                PoolName=user_pool_name,
                Policies={
                    'PasswordPolicy': {
                        'MinimumLength': 8,
                        'RequireUppercase': True,
                        'RequireLowercase': True,
                        'RequireNumbers': True,
                        'RequireSymbols': True,
                        'TemporaryPasswordValidityDays': 7
                    }
                },
                # サインアップ時にメールを自動検証
                AutoVerifiedAttributes=['email'],
                # メールベースのユーザー名（大文字小文字を区別しない）
                UsernameAttributes=['email'],
                EmailConfiguration={
                    'EmailSendingAccount': 'COGNITO_DEFAULT'
                },
                MfaConfiguration='OFF',  # ワークショップの簡略化のため無効
                AccountRecoverySetting={
                    'RecoveryMechanisms': [
                        {
                            'Name': 'verified_email',
                            'Priority': 1
                        }
                    ]
                }
            )

            user_pool_id = response['UserPool']['Id']
            user_pool_arn = response['UserPool']['Arn']

            print(f"User Pool の作成に成功しました: {user_pool_id}")

            return user_pool_id, user_pool_arn

        except self.cognito.exceptions.UserPoolTaggingException as e:
            print(f"User Pool の作成に失敗しました: {e}")
            raise

    def create_resource_server(self, user_pool_id: str) -> str:
        """
        きめ細かな認可のためのカスタムスコープを持つリソースサーバーを作成

        Scopes:
        - mcp.invoke: MCP サーバーツールを呼び出す権限
        - runtime.access: AgentCore Runtime にアクセスする権限

        Returns:
            リソースサーバー識別子
        """
        resource_server_id = f"{self.prefix}-agentcore-runtime"
        resource_server_name = f"{self.prefix} AgentCore Runtime API"

        print(f"リソースサーバーを作成中: {resource_server_id}...")

        try:
            self.cognito.create_resource_server(
                UserPoolId=user_pool_id,
                Identifier=resource_server_id,
                Name=resource_server_name,
                Scopes=[
                    {
                        'ScopeName': 'mcp.invoke',
                        'ScopeDescription': 'Permission to invoke MCP server tools'
                    },
                    {
                        'ScopeName': 'runtime.access',
                        'ScopeDescription': 'Permission to access AgentCore Runtime'
                    }
                ]
            )

            print(f"リソースサーバーの作成に成功しました: {resource_server_id}")
            return resource_server_id

        except Exception as e:
            print(f"リソースサーバーの作成に失敗しました: {e}")
            raise

    def create_user_auth_client(self, user_pool_id: str) -> str:
        """
        ユーザー認証クライアント（PUBLIC）を作成
        ユーザー名/パスワードによるエンドユーザー認証用

        Returns:
            クライアント ID
        """
        client_name = f"{self.prefix}-UserAuthClient"

        print(f"ユーザー認証クライアントを作成中: {client_name}...")

        try:
            response = self.cognito.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=False,  # パブリッククライアント - シークレットなし
                RefreshTokenValidity=30,
                AccessTokenValidity=60,
                IdTokenValidity=60,
                TokenValidityUnits={
                    'AccessToken': 'minutes',
                    'IdToken': 'minutes',
                    'RefreshToken': 'days'
                },
                ExplicitAuthFlows=[
                    'ALLOW_USER_PASSWORD_AUTH',
                    'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH',
                    'ALLOW_USER_SRP_AUTH'
                ],
                PreventUserExistenceErrors='ENABLED',
                EnableTokenRevocation=True,
                EnablePropagateAdditionalUserContextData=False
            )

            client_id = response['UserPoolClient']['ClientId']
            print(f"ユーザー認証クライアントの作成に成功しました: {client_id}")

            return client_id

        except Exception as e:
            print(f"ユーザー認証クライアントの作成に失敗しました: {e}")
            raise

    def create_m2m_client(self, user_pool_id: str, resource_server_id: str) -> tuple:
        """
        M2M クライアント（CONFIDENTIAL）を作成
        クライアント資格情報グラントを使用したサービス間認証用

        Returns:
            (クライアント ID, クライアントシークレット) のタプル
        """
        client_name = f"{self.prefix}-M2MClient"

        print(f"M2M クライアントを作成中: {client_name}...")

        try:
            response = self.cognito.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=True,  # 機密クライアント - シークレット必須
                RefreshTokenValidity=30,
                AccessTokenValidity=60,
                TokenValidityUnits={
                    'AccessToken': 'minutes',
                    'RefreshToken': 'days'
                },
                ExplicitAuthFlows=[
                    'ALLOW_REFRESH_TOKEN_AUTH'
                ],
                AllowedOAuthFlows=['client_credentials'],
                AllowedOAuthFlowsUserPoolClient=True,
                AllowedOAuthScopes=[
                    f'{resource_server_id}/mcp.invoke',
                    f'{resource_server_id}/runtime.access'
                ],
                EnableTokenRevocation=True,
                EnablePropagateAdditionalUserContextData=True
            )

            client_id = response['UserPoolClient']['ClientId']
            client_secret = response['UserPoolClient']['ClientSecret']

            print(f"M2M クライアントの作成に成功しました: {client_id}")
            print("   クライアントシークレットは安全に保管してください（AWS Secrets Manager 推奨）")

            return client_id, client_secret

        except Exception as e:
            print(f"M2M クライアントの作成に失敗しました: {e}")
            raise

    def create_user_pool_domain(self, user_pool_id: str) -> str:
        """
        OAuth2 トークンエンドポイント用の User Pool ドメインを作成

        Returns:
            ドメイン URL
        """
        # タイムスタンプを使用して一意のドメインプレフィックスを生成
        timestamp = str(int(time.time()))
        domain_prefix = f"{self.prefix}-agentcore-{timestamp}"

        print(f"User Pool ドメインを作成中: {domain_prefix}...")

        try:
            self.cognito.create_user_pool_domain(
                Domain=domain_prefix,
                UserPoolId=user_pool_id
            )

            # 完全なドメイン URL を構築
            domain_url = f"https://{domain_prefix}.auth.{self.region}.amazoncognito.com"
            print(f"User Pool ドメインの作成に成功しました: {domain_url}")

            return domain_url

        except Exception as e:
            print(f"User Pool ドメインの作成に失敗しました: {e}")
            raise

    def create_groups(self, user_pool_id: str) -> None:
        """
        ロールベースのアクセス制御用の Cognito グループを作成。

        Groups:
        - sre: 修復計画を作成する SRE ユーザー（優先度 10）
        - approvers: 計画を承認・実行するユーザー（優先度 5）

        優先度の数字が小さいほど優先順位が高い
        """
        groups = [
            {
                "GroupName": "sre",
                "Description": "SRE users who create remediation plans",
                "Precedence": 10
            },
            {
                "GroupName": "approvers",
                "Description": "Approvers who approve and execute remediation plans",
                "Precedence": 5
            }
        ]

        print("Cognito グループを作成中...")

        for group in groups:
            try:
                self.cognito.create_group(
                    UserPoolId=user_pool_id,
                    GroupName=group["GroupName"],
                    Description=group["Description"],
                    Precedence=group["Precedence"]
                )
                print(f"グループの作成に成功しました: {group['GroupName']} (優先度: {group['Precedence']})")
            except self.cognito.exceptions.GroupExistsException:
                print(f"グループは既に存在します: {group['GroupName']}")
            except Exception as e:
                print(f"グループ {group['GroupName']} の作成に失敗しました: {e}")
                raise

    def assign_user_to_group(self, user_pool_id: str, username: str, group_name: str) -> None:
        """ユーザーを Cognito グループに割り当て"""
        try:
            self.cognito.admin_add_user_to_group(
                UserPoolId=user_pool_id,
                Username=username,
                GroupName=group_name
            )
            print("ユーザーをグループに追加しました！")
        except Exception as e:
            print(f"ユーザーのグループ追加に失敗しました: {e}")
            raise

    def create_test_user(self, user_pool_id: str) -> None:
        """ワークショップ用テストユーザーを作成（SRE ロール）"""
        print(f"テストユーザーを作成中: {self.test_user_email}...")

        try:
            self.cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=self.test_user_email,
                TemporaryPassword=self.test_user_password,
                UserAttributes=[
                    {'Name': 'email', 'Value': self.test_user_email},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                MessageAction='SUPPRESS'  # ウェルカムメールを送信しない
            )

            # 永続パスワードを設定（ワークショップの簡略化のため一時パスワードと同じ）
            self.cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=self.test_user_email,
                Password=self.test_user_password,
                Permanent=True
            )

            print(f"テストユーザーの作成に成功しました: {self.test_user_email}")

        except self.cognito.exceptions.UsernameExistsException:
            print(f"テストユーザーは既に存在します: {self.test_user_email}")
        except Exception as e:
            print(f"テストユーザーの作成に失敗しました: {e}")
            raise

    def create_approver_user(self, user_pool_id: str) -> Dict[str, str]:
        """マルチアクターワークフロー用の承認者テストユーザーを作成"""
        approver_email = f"approver@{self.prefix}.example.com"
        approver_password = "<enter password>"  # Meets policy requirements

        print(f"承認者ユーザーを作成中: {approver_email}...")

        try:
            self.cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=approver_email,
                TemporaryPassword=approver_password,
                UserAttributes=[
                    {'Name': 'email', 'Value': approver_email},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                MessageAction='SUPPRESS'  # ウェルカムメールを送信しない
            )

            # 永続パスワードを設定
            self.cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=approver_email,
                Password=approver_password,
                Permanent=True
            )

            print(f"承認者ユーザーの作成に成功しました: {approver_email}")

            return {
                "email": approver_email,
                "password": approver_password
            }

        except self.cognito.exceptions.UsernameExistsException:
            print(f"承認者ユーザーは既に存在します: {approver_email}")
            return {"email": approver_email, "password": approver_password}
        except Exception as e:
            print(f"承認者ユーザーの作成に失敗しました: {e}")
            raise

    def update_user_auth_client_for_oauth(
        self,
        user_pool_id: str,
        client_id: str,
        resource_server_id: str
    ) -> None:
        """
        OAuth フローとカスタムスコープをサポートするようにユーザー認証クライアントを更新。
        これにより、リッチなクレーム（email、groups など）を持つ ID トークンが有効になります。
        """
        print("ユーザー認証クライアントを OAuth サポート用に更新中...")

        try:
            self.cognito.update_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                # 既存の認証フローを維持
                ExplicitAuthFlows=[
                    'ALLOW_USER_PASSWORD_AUTH',
                    'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH',
                    'ALLOW_USER_SRP_AUTH'
                ],
                # OAuth フローを追加
                AllowedOAuthFlows=['code', 'implicit'],
                AllowedOAuthFlowsUserPoolClient=True,
                # カスタムスコープを追加
                AllowedOAuthScopes=[
                    'openid',
                    'profile',
                    'email',
                    f'{resource_server_id}/mcp.invoke',
                    f'{resource_server_id}/runtime.access'
                ],
                # ローカルテスト用のコールバック URL を追加
                CallbackURLs=['http://localhost:8080/callback'],
                LogoutURLs=['http://localhost:8080/logout'],
                SupportedIdentityProviders=['COGNITO'],
                # トークンの有効期限
                IdTokenValidity=60,
                AccessTokenValidity=60,
                RefreshTokenValidity=30,
                TokenValidityUnits={
                    'AccessToken': 'minutes',
                    'IdToken': 'minutes',
                    'RefreshToken': 'days'
                },
                # パブリッククライアントのため無効化（シークレットなし）
                EnablePropagateAdditionalUserContextData=False,
                EnableTokenRevocation=True,
                PreventUserExistenceErrors='ENABLED'
            )

            print("ユーザー認証クライアントを OAuth サポート用に更新しました")
            print("   - OAuth フロー: code, implicit")
            print("   - スコープ: openid, profile, email, カスタムスコープ")
            print("   - ID トークンに email と cognito:groups クレームが含まれます")

        except Exception as e:
            print(f"ユーザー認証クライアントの更新に失敗しました: {e}")
            raise

    def setup_cognito(self) -> Dict[str, Any]:
        """
        完全な Cognito セットアップを実行して設定を返す
        """
        print("\n" + "="*70)
        print("AIML301 ワークショップ用 COGNITO セットアップ")
        print("="*70 + "\n")

        # User Pool を作成
        user_pool_id, user_pool_arn = self.create_user_pool()

        # リソースサーバーを作成（M2M クライアントより前に作成が必要）
        resource_server_id = self.create_resource_server(user_pool_id)

        # 認証クライアントを作成
        user_auth_client_id = self.create_user_auth_client(user_pool_id)
        m2m_client_id, m2m_client_secret = self.create_m2m_client(user_pool_id, resource_server_id)

        # ドメインを作成
        domain_url = self.create_user_pool_domain(user_pool_id)
        token_endpoint = f"{domain_url}/oauth2/token"

        # ロールベースのアクセス制御用グループを作成
        self.create_groups(user_pool_id)

        # テストユーザーを作成（開発者ロール）
        self.create_test_user(user_pool_id)
        self.assign_user_to_group(user_pool_id, self.test_user_email, "sre")

        # 承認者ユーザーを作成
        approver_user = self.create_approver_user(user_pool_id)
        self.assign_user_to_group(user_pool_id, approver_user["email"], "approvers")

        # OAuth サポート用にユーザー認証クライアントを更新（リッチなクレームを持つ ID トークンを有効化）
        self.update_user_auth_client_for_oauth(user_pool_id, user_auth_client_id, resource_server_id)

        # 設定を構築
        cognito_config = {
            "region": self.region,
            "user_pool_id": user_pool_id,
            "user_pool_arn": user_pool_arn,
            "user_pool_name": f"{self.prefix}-UserPool",
            "domain": domain_url,
            "token_endpoint": token_endpoint,
            "user_auth_client": {
                "client_id": user_auth_client_id,
                "client_name": f"{self.prefix}-UserAuthClient",
                "has_secret": False,
                "oauth_flows": ["code", "implicit"],
                "oauth_scopes": [
                    "openid",
                    "profile",
                    "email",
                    f"{resource_server_id}/mcp.invoke",
                    f"{resource_server_id}/runtime.access"
                ]
            },
            "m2m_client": {
                "client_id": m2m_client_id,
                "client_secret": m2m_client_secret,
                "client_name": f"{self.prefix}-M2MClient",
                "has_secret": True
            },
            "resource_server": {
                "identifier": resource_server_id,
                "name": f"{self.prefix} AgentCore Runtime API",
                "scopes": [
                    f"{resource_server_id}/mcp.invoke",
                    f"{resource_server_id}/runtime.access"
                ]
            },
            "groups": [
                {"name": "sre", "precedence": 10},
                {"name": "approvers", "precedence": 5}
            ],
            "test_user": {
                "username": self.test_user_email,
                "password": self.test_user_password,
                "email": self.test_user_email,
                "group": "sre"
            },
            "approver_user": {
                "username": approver_user["email"],
                "password": approver_user["password"],
                "email": approver_user["email"],
                "group": "approvers"
            }
        }

        return cognito_config

    def save_to_ssm(self, cognito_config: Dict[str, Any]) -> None:
        """Cognito 設定を SSM Parameter Store に保存"""
        print("\n" + "="*70)
        print("COGNITO 設定を SSM パラメータストアに保存中")
        print("="*70 + "\n")

        params = PARAMETER_PATHS['cognito']

        # 個別のパラメータを保存
        put_parameter(params['user_pool_id'], cognito_config['user_pool_id'])
        put_parameter(params['user_pool_name'], cognito_config['user_pool_name'])
        put_parameter(params['user_pool_arn'], cognito_config['user_pool_arn'])
        put_parameter(params['domain'], cognito_config['domain'])
        put_parameter(params['token_endpoint'], cognito_config['token_endpoint'])

        put_parameter(params['user_auth_client_id'], cognito_config['user_auth_client']['client_id'])
        put_parameter(params['user_auth_client_name'], cognito_config['user_auth_client']['client_name'])

        put_parameter(params['m2m_client_id'], cognito_config['m2m_client']['client_id'])
        put_parameter(params['m2m_client_secret'], cognito_config['m2m_client']['client_secret'])
        put_parameter(params['m2m_client_name'], cognito_config['m2m_client']['client_name'])

        put_parameter(params['resource_server_id'], cognito_config['resource_server']['identifier'])
        put_parameter(params['resource_server_identifier'], cognito_config['resource_server']['identifier'])

        put_parameter(params['test_user_email'], cognito_config['test_user']['email'])
        put_parameter(params['test_user_password'], cognito_config['test_user']['password'])

        # 承認者ユーザーの認証情報を保存
        put_parameter(params['approver_user_email'], cognito_config['approver_user']['email'])
        put_parameter(params['approver_user_password'], cognito_config['approver_user']['password'])

        print("Cognito 設定を SSM パラメータストアに保存しました")

    def save_to_file(self, cognito_config: Dict[str, Any], filename: str = "cognito_config.json") -> None:
        """Cognito 設定をローカル JSON ファイルに保存（参照用）"""
        print(f"\n設定を {filename} に保存中...")

        with open(filename, 'w') as f:
            json.dump(cognito_config, f, indent=2)

        print(f"設定を {filename} に保存しました")


def setup_cognito_complete() -> Dict[str, Any]:
    """
    完全な Cognito セットアップワークフロー
    1. すべての Cognito リソースを作成
    2. SSM Parameter Store に保存
    3. 設定を返す
    """
    setup = CognitoSetup()

    # セットアップを実行
    cognito_config = setup.setup_cognito()

    # SSM に保存
    setup.save_to_ssm(cognito_config)

    # 参照用にファイルに保存
    setup.save_to_file(cognito_config)

    print("\n" + "="*70)
    print("COGNITO セットアップ完了")
    print("="*70)
    print("\nすべての設定が SSM パラメータストアの /aiml301/cognito/* に保存されました")
    print("参照用コピーが cognito_config.json に保存されました\n")

    return cognito_config


def cleanup_cognito(user_pool_id: Optional[str] = None) -> None:
    """
    Cognito リソースをクリーンアップ

    Args:
        user_pool_id: 削除する User Pool ID（None の場合は SSM から取得）
    """
    setup = CognitoSetup()

    # 提供されていない場合は SSM から User Pool ID を取得
    if user_pool_id is None:
        try:
            user_pool_id = get_parameter(PARAMETER_PATHS['cognito']['user_pool_id'])
        except Exception as e:
            print(f"SSM から User Pool ID を取得できませんでした: {e}")
            return

    print(f"User Pool の Cognito リソースをクリーンアップ中: {user_pool_id}...")
    print("")

    try:
        # ステップ 1: User Pool からドメインを取得（存在する場合）
        print("ステップ 1: User Pool ドメインを確認中...")
        try:
            domain_response = setup.cognito.describe_user_pool(UserPoolId=user_pool_id)
            domain = domain_response.get('UserPool', {}).get('Domain')

            if domain:
                print(f"  ドメインを発見: {domain}")
                print("  ドメインを削除中...")
                setup.cognito.delete_user_pool_domain(
                    Domain=domain,
                    UserPoolId=user_pool_id
                )
                print(f"  ドメインを削除しました: {domain}")
            else:
                print("  ドメインは設定されていません")
        except Exception as e:
            print(f"  ドメインの確認/削除ができませんでした: {e}")

        print("")

        # ステップ 2: User Pool を削除
        print(f"ステップ 2: User Pool を削除中: {user_pool_id}...")
        setup.cognito.delete_user_pool(UserPoolId=user_pool_id)
        print(f"  User Pool を削除しました: {user_pool_id}")

        print("")

        # ステップ 3: SSM パラメータを削除
        print("ステップ 3: SSM パラメータを削除中...")
        params = PARAMETER_PATHS['cognito']
        deleted_count = 0
        for key, param_path in params.items():
            try:
                delete_parameter(param_path)
                deleted_count += 1
            except Exception:
                pass  # Parameter might not exist

        print(f"  {deleted_count} 件の SSM パラメータを削除しました")
        print("")
        print("Cognito クリーンアップ完了")

    except Exception as e:
        print(f"クリーンアップ中にエラーが発生しました: {e}")
        raise
