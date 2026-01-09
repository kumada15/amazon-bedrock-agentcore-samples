"""
AIML301 ワークショップ用 Cognito セットアップヘルパー
Labs 3-5 の認証インフラストラクチャをセットアップします

認証フロー:
- Lab 3: エンドユーザー向け Cognito JWT 認証付き Gateway
- Lab 3-5: クライアント認証情報を使用した Gateway から Runtime への M2M 認証
- Labs 4+: 高度なユースケース向けのオプションのユーザーベースアクセス制御

作成される Cognito リソース:
1. User Pool: aiml301-UserPool
2. User Auth Client: aiml301-UserAuthClient (パブリック、エンドユーザー認証用)
3. M2M Client: aiml301-M2MClient (コンフィデンシャル、サービス間認証用)
4. Resource Server: aiml301-agentcore-runtime (カスタムスコープ付き)
5. User Pool Domain: aiml301-agentcore-{timestamp}
6. Test User: testuser@aiml301.example.com
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
        Create Cognito User Pool with security best practices
        Returns: User Pool ID
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
                # Auto-verify email on signup
                AutoVerifiedAttributes=['email'],
                # Email-based username (case insensitive)
                UsernameAttributes=['email'],
                EmailConfiguration={
                    'EmailSendingAccount': 'COGNITO_DEFAULT'
                },
                MfaConfiguration='OFF',  # Disabled for workshop simplicity
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

            print(f"✅ User Pool を作成しました: {user_pool_id}")

            return user_pool_id, user_pool_arn

        except self.cognito.exceptions.UserPoolTaggingException as e:
            print(f"❌ User Pool の作成中にエラーが発生しました: {e}")
            raise

    def create_resource_server(self, user_pool_id: str) -> str:
        """
        Create Resource Server with custom scopes for fine-grained authorization

        Scopes:
        - mcp.invoke: Permission to invoke MCP server tools
        - runtime.access: Permission to access AgentCore Runtime

        Returns: Resource Server Identifier
        """
        resource_server_id = f"{self.prefix}-agentcore-runtime"
        resource_server_name = f"{self.prefix} AgentCore Runtime API"

        print(f"リソースサーバーを作成中: {resource_server_id}...")

        try:
            response = self.cognito.create_resource_server(
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

            print(f"✅ リソースサーバーを作成しました: {resource_server_id}")
            return resource_server_id

        except Exception as e:
            print(f"❌ リソースサーバーの作成中にエラーが発生しました: {e}")
            raise

    def create_user_auth_client(self, user_pool_id: str) -> str:
        """
        Create User Auth Client (PUBLIC)
        For end-user authentication with username/password

        Returns: Client ID
        """
        client_name = f"{self.prefix}-UserAuthClient"

        print(f"ユーザー認証クライアントを作成中: {client_name}...")

        try:
            response = self.cognito.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=False,  # Public client - no secret
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
            print(f"✅ ユーザー認証クライアントを作成しました: {client_id}")

            return client_id

        except Exception as e:
            print(f"❌ ユーザー認証クライアントの作成中にエラーが発生しました: {e}")
            raise

    def create_m2m_client(self, user_pool_id: str, resource_server_id: str) -> tuple:
        """
        Create M2M Client (CONFIDENTIAL)
        For service-to-service authentication using client credentials grant

        Returns: (Client ID, Client Secret)
        """
        client_name = f"{self.prefix}-M2MClient"

        print(f"M2M クライアントを作成中: {client_name}...")

        try:
            response = self.cognito.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=True,  # Confidential client - requires secret
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

            print(f"✅ M2M クライアントを作成しました: {client_id}")
            print(f"   ⚠️  クライアントシークレット: ****")
            print(f"   ⚠️  クライアントシークレットは安全に保管してください（AWS Secrets Manager を推奨）")

            return client_id, client_secret

        except Exception as e:
            print(f"❌ M2M クライアントの作成中にエラーが発生しました: {e}")
            raise

    def create_user_pool_domain(self, user_pool_id: str) -> str:
        """
        Create User Pool Domain for OAuth2 token endpoint

        Returns: Domain URL
        """
        # Generate unique domain prefix using timestamp
        timestamp = str(int(time.time()))
        domain_prefix = f"{self.prefix}-agentcore-{timestamp}"

        print(f"User Pool ドメインを作成中: {domain_prefix}...")

        try:
            response = self.cognito.create_user_pool_domain(
                Domain=domain_prefix,
                UserPoolId=user_pool_id
            )

            # Construct full domain URL
            domain_url = f"https://{domain_prefix}.auth.{self.region}.amazoncognito.com"
            print(f"✅ User Pool ドメインを作成しました: {domain_url}")

            return domain_url

        except Exception as e:
            print(f"❌ User Pool ドメインの作成中にエラーが発生しました: {e}")
            raise

    def create_groups(self, user_pool_id: str) -> None:
        """
        Create Cognito groups for role-based access control.

        Groups:
        - sre: SRE users who create remediation plans (Precedence 10)
        - approvers: Users who approve and execute plans (Precedence 5)

        Lower precedence number = higher priority
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
                print(f"✅ グループを作成しました: {group['GroupName']} (優先度: {group['Precedence']})")
            except self.cognito.exceptions.GroupExistsException:
                print(f"ℹ️  グループは既に存在します: {group['GroupName']}")
            except Exception as e:
                print(f"❌ グループ {group['GroupName']} の作成中にエラーが発生しました: {e}")
                raise

    def assign_user_to_group(self, user_pool_id: str, username: str, group_name: str) -> None:
        """ユーザーを Cognito グループに割り当て"""
        try:
            self.cognito.admin_add_user_to_group(
                UserPoolId=user_pool_id,
                Username=username,
                GroupName=group_name
            )
            print(f"✅ ユーザー {username} をグループ '{group_name}' に追加しました")
        except Exception as e:
            print(f"❌ ユーザーをグループに追加中にエラーが発生しました: {e}")
            raise

    def create_test_user(self, user_pool_id: str) -> None:
        """ワークショップ用のテストユーザーを作成（SRE ロール）"""
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
                MessageAction='SUPPRESS'  # Don't send welcome email
            )

            # Set permanent password (same as temporary for simplicity in workshop)
            self.cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=self.test_user_email,
                Password=self.test_user_password,
                Permanent=True
            )

            print(f"✅ テストユーザーを作成しました: {self.test_user_email}")

        except self.cognito.exceptions.UsernameExistsException:
            print(f"ℹ️  テストユーザーは既に存在します: {self.test_user_email}")
        except Exception as e:
            print(f"❌ テストユーザーの作成中にエラーが発生しました: {e}")
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
                MessageAction='SUPPRESS'  # Don't send welcome email
            )

            # Set permanent password
            self.cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=approver_email,
                Password=approver_password,
                Permanent=True
            )

            print(f"✅ 承認者ユーザーを作成しました: {approver_email}")

            return {
                "email": approver_email,
                "password": approver_password
            }

        except self.cognito.exceptions.UsernameExistsException:
            print(f"ℹ️  承認者ユーザーは既に存在します: {approver_email}")
            return {"email": approver_email, "password": approver_password}
        except Exception as e:
            print(f"❌ 承認者ユーザーの作成中にエラーが発生しました: {e}")
            raise

    def update_user_auth_client_for_oauth(
        self,
        user_pool_id: str,
        client_id: str,
        resource_server_id: str
    ) -> None:
        """
        Update User Auth Client to support OAuth flows and custom scopes.
        This enables ID tokens with rich claims (email, groups, etc.)
        """
        print(f"ユーザー認証クライアントを OAuth サポート用に更新中...")

        try:
            self.cognito.update_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                # Keep existing auth flows
                ExplicitAuthFlows=[
                    'ALLOW_USER_PASSWORD_AUTH',
                    'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH',
                    'ALLOW_USER_SRP_AUTH'
                ],
                # Add OAuth flows
                AllowedOAuthFlows=['code', 'implicit'],
                AllowedOAuthFlowsUserPoolClient=True,
                # Add custom scopes
                AllowedOAuthScopes=[
                    'openid',
                    'profile',
                    'email',
                    f'{resource_server_id}/mcp.invoke',
                    f'{resource_server_id}/runtime.access'
                ],
                # Add callback URL for local testing
                CallbackURLs=['http://localhost:8080/callback'],
                LogoutURLs=['http://localhost:8080/logout'],
                SupportedIdentityProviders=['COGNITO'],
                # Token validity
                IdTokenValidity=60,
                AccessTokenValidity=60,
                RefreshTokenValidity=30,
                TokenValidityUnits={
                    'AccessToken': 'minutes',
                    'IdToken': 'minutes',
                    'RefreshToken': 'days'
                },
                # Disable for public client (no secret)
                EnablePropagateAdditionalUserContextData=False,
                EnableTokenRevocation=True,
                PreventUserExistenceErrors='ENABLED'
            )

            print(f"✅ ユーザー認証クライアントを OAuth サポートで更新しました")
            print(f"   • OAuth フロー: code, implicit")
            print(f"   • スコープ: openid, profile, email, カスタムスコープ")
            print(f"   • ID トークンには email と cognito:groups クレームが含まれます")

        except Exception as e:
            print(f"❌ ユーザー認証クライアントの更新中にエラーが発生しました: {e}")
            raise

    def setup_cognito(self) -> Dict[str, Any]:
        """
        Execute full Cognito setup and return configuration
        """
        print("\n" + "="*70)
        print("AIML301 ワークショップ用 COGNITO セットアップ")
        print("="*70 + "\n")

        # Create user pool
        user_pool_id, user_pool_arn = self.create_user_pool()

        # Create resource server (must be before M2M client)
        resource_server_id = self.create_resource_server(user_pool_id)

        # Create auth clients
        user_auth_client_id = self.create_user_auth_client(user_pool_id)
        m2m_client_id, m2m_client_secret = self.create_m2m_client(user_pool_id, resource_server_id)

        # Create domain
        domain_url = self.create_user_pool_domain(user_pool_id)
        token_endpoint = f"{domain_url}/oauth2/token"

        # Create groups for role-based access control
        self.create_groups(user_pool_id)

        # Create test user (developer role)
        self.create_test_user(user_pool_id)
        self.assign_user_to_group(user_pool_id, self.test_user_email, "sre")

        # Create approver user
        approver_user = self.create_approver_user(user_pool_id)
        self.assign_user_to_group(user_pool_id, approver_user["email"], "approvers")

        # Update User Auth Client for OAuth support (enables ID tokens with rich claims)
        self.update_user_auth_client_for_oauth(user_pool_id, user_auth_client_id, resource_server_id)

        # Build configuration
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

        # Save individual parameters
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

        # Save approver user credentials
        put_parameter(params['approver_user_email'], cognito_config['approver_user']['email'])
        put_parameter(params['approver_user_password'], cognito_config['approver_user']['password'])

        print("✅ Cognito 設定を SSM パラメータストアに保存しました")

    def save_to_file(self, cognito_config: Dict[str, Any], filename: str = "cognito_config.json") -> None:
        """Cognito 設定をローカル JSON ファイルに保存（参照用）"""
        print(f"\n設定を {filename} に保存中...")

        with open(filename, 'w') as f:
            json.dump(cognito_config, f, indent=2)

        print(f"✅ 設定を {filename} に保存しました")


def setup_cognito_complete() -> Dict[str, Any]:
    """
    Complete Cognito setup workflow
    1. Create all Cognito resources
    2. Save to SSM Parameter Store
    3. Return configuration
    """
    setup = CognitoSetup()

    # Execute setup
    cognito_config = setup.setup_cognito()

    # Save to SSM
    setup.save_to_ssm(cognito_config)

    # Save to file for reference
    setup.save_to_file(cognito_config)

    print("\n" + "="*70)
    print("✅ COGNITO セットアップ完了")
    print("="*70)
    print(f"\n主要な設定:")
    print(f"  User Pool ID: {cognito_config['user_pool_id']}")
    print(f"  ドメイン: {cognito_config['domain']}")
    print(f"  トークンエンドポイント: {cognito_config['token_endpoint']}")
    print(f"\n  ユーザー認証クライアント:")
    print(f"    • クライアント ID: {cognito_config['user_auth_client']['client_id']}")
    print(f"    • OAuth フロー: {', '.join(cognito_config['user_auth_client']['oauth_flows'])}")
    print(f"    • OAuth スコープ: openid, profile, email, カスタムスコープ")
    print(f"\n  M2M クライアント:")
    print(f"    • クライアント ID: {cognito_config['m2m_client']['client_id']}")
    print(f"    • クライアントシークレット: ****")
    print(f"\n  作成されたグループ:")
    print(f"    • sre (優先度: 10) - ツール: generate_remediation_plan")
    print(f"    • approvers (優先度: 5) - ツール: execute_remediation_step, validate_remediation_environment")
    print(f"\n  作成されたユーザー:")
    print(f"    • テストユーザー (SRE): **** (パスワード: ****)")
    print(f"    • 承認者ユーザー: **** (パスワード: ****)")
    print(f"\nすべての設定は SSM パラメータストア /aiml301/cognito/* に保存されています")
    print(f"参照用コピーは cognito_config.json に保存されています\n")

    return cognito_config


def cleanup_cognito(user_pool_id: Optional[str] = None) -> None:
    """
    Clean up Cognito resources

    Args:
        user_pool_id: User Pool ID to delete (if None, fetches from SSM)
    """
    setup = CognitoSetup()

    # Get user pool ID from SSM if not provided
    if user_pool_id is None:
        try:
            user_pool_id = get_parameter(PARAMETER_PATHS['cognito']['user_pool_id'])
        except Exception as e:
            print(f"❌ SSM から User Pool ID を取得できませんでした: {e}")
            return

    print(f"User Pool: {user_pool_id} の Cognito リソースをクリーンアップ中...")
    print("")

    try:
        # Step 1: Get domain from User Pool (if exists)
        print("ステップ 1: User Pool ドメインを確認中...")
        try:
            domain_response = setup.cognito.describe_user_pool(UserPoolId=user_pool_id)
            domain = domain_response.get('UserPool', {}).get('Domain')

            if domain:
                print(f"  ドメインが見つかりました: {domain}")
                print(f"  ドメインを削除中...")
                setup.cognito.delete_user_pool_domain(
                    Domain=domain,
                    UserPoolId=user_pool_id
                )
                print(f"  ✅ ドメインを削除しました: {domain}")
            else:
                print(f"  ドメインは設定されていません")
        except Exception as e:
            print(f"  ⚠️  ドメインの確認/削除ができませんでした: {e}")

        print("")

        # Step 2: Delete User Pool
        print(f"ステップ 2: User Pool を削除中: {user_pool_id}...")
        setup.cognito.delete_user_pool(UserPoolId=user_pool_id)
        print(f"  ✅ User Pool を削除しました: {user_pool_id}")

        print("")

        # Step 3: Delete SSM parameters
        print("ステップ 3: SSM パラメータを削除中...")
        params = PARAMETER_PATHS['cognito']
        deleted_count = 0
        for key, param_path in params.items():
            try:
                delete_parameter(param_path)
                deleted_count += 1
            except:
                pass  # Parameter might not exist

        print(f"  ✅ {deleted_count} 件の SSM パラメータを削除しました")
        print("")
        print("✅ Cognito クリーンアップ完了")

    except Exception as e:
        print(f"❌ クリーンアップ中にエラーが発生しました: {e}")
        raise
