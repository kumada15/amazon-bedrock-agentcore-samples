"""
Lab 03: OAuth2 クレデンシャルプロバイダーと M2M 認証セットアップ

Cognito を使用した OAuth2 クライアントクレデンシャルグラントで
Gateway と Runtime 間のマシン間（M2M）認証をセットアップします。

アーキテクチャ:
- Gateway は M2M クライアントクレデンシャルを使用して Cognito からアクセストークンを取得
- M2M トークンには細かい認可のためのカスタムスコープが含まれる
- Runtime は M2M トークンを検証し、認可されたスコープ内の操作のみを許可
- OAuth2 クレデンシャルプロバイダーが AWS Secrets Manager でクレデンシャルストレージを管理

ベース: gateway-to-runtime/07_connect_gateway_to_runtime.py
"""

import json
import boto3
import time
from typing import Dict, Optional
from botocore.exceptions import ClientError

from lab_helpers.config import AWS_REGION, AWS_PROFILE
from lab_helpers.parameter_store import get_parameter, put_parameter
from lab_helpers.constants import PARAMETER_PATHS


class OAuth2CredentialProviderSetup:
    """M2M 認証用の OAuth2 クレデンシャルプロバイダーを管理"""

    def __init__(self, region: str = AWS_REGION, profile: str = AWS_PROFILE):
        """OAuth2 セットアップヘルパーを初期化"""
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.agentcore = self.session.client('bedrock-agentcore-control', region_name=region)
        self.iam = self.session.client('iam', region_name=region)
        self.ssm = self.session.client('ssm', region_name=region)
        self.sts = self.session.client('sts', region_name=region)

        self.region = region
        self.account_id = self.sts.get_caller_identity()['Account']
        self.prefix = "aiml301"

    def create_oauth2_credential_provider(self) -> Dict:
        """
        M2M 認証用の OAuth2 クレデンシャルプロバイダーを作成

        このプロバイダーは M2M クライアントクレデンシャルを管理し、
        クライアントクレデンシャルグラントを使用して Gateway が Runtime と認証できるようにします。

        Returns:
            provider_arn、secret_arn、設定を含む Dict
        """
        print("\n" + "="*70)
        print("OAUTH2 クレデンシャルプロバイダーの作成")
        print("="*70 + "\n")

        # Lab-01 でセットアップした Cognito 設定から M2M クレデンシャルを取得
        try:
            m2m_client_id = get_parameter(PARAMETER_PATHS['cognito']['m2m_client_id'])
            m2m_client_secret = get_parameter(PARAMETER_PATHS['cognito']['m2m_client_secret'])
            user_pool_id = get_parameter(PARAMETER_PATHS['cognito']['user_pool_id'])
        except Exception as e:
            print(f"Cognito M2M クレデンシャルを SSM から取得できませんでした: {e}")
            print("   Lab-01 Cognito セットアップが完了していることを確認してください")
            raise

        print(f"Cognito から M2M クレデンシャルを取得しました")
        print(f"   - M2M クライアント ID: {m2m_client_id}")
        print(f"   - M2M クライアントシークレット: ****")
        print(f"   - ユーザープール ID: {user_pool_id}")

        # OAuth2 ディスカバリーエンドポイント用のディスカバリー URL を構築
        # これにより AgentCore に Cognito OIDC 設定の場所を伝える
        discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"

        provider_name = f"{self.prefix}-runtime-m2m-credentials"

        print(f"\nOAuth2 クレデンシャルプロバイダーを作成中: {provider_name}")
        print(f"ディスカバリー URL: {discovery_url}\n")

        try:
            # OAuth2 クレデンシャルプロバイダーを作成
            # AgentCore は自動的に:
            # 1. AWS Secrets Manager にクレデンシャルを保存
            # 2. クレデンシャルのローテーションを管理（必要に応じて）
            # 3. クライアントクレデンシャルグラントを使用してトークンを生成
            response = self.agentcore.create_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor="CustomOauth2",
                oauth2ProviderConfigInput={
                    "customOauth2ProviderConfig": {
                        "oauthDiscovery": {
                            "discoveryUrl": discovery_url
                        },
                        "clientId": m2m_client_id,
                        "clientSecret": m2m_client_secret
                    }
                }
            )

            provider_arn = response['oAuth2CredentialProviderArn']
            secret_arn = response.get('secretArn', '')

            print(f"OAuth2 クレデンシャルプロバイダーを作成しました")
            print(f"   - プロバイダー ARN: {provider_arn}")
            print(f"   - シークレット ARN: {secret_arn}")

            # 設定を保存
            oauth2_config = {
                "provider_name": provider_name,
                "provider_arn": provider_arn,
                "secret_arn": secret_arn,
                "discovery_url": discovery_url,
                "m2m_client_id": m2m_client_id,
                "region": self.region,
                "account_id": self.account_id
            }

            # Save to SSM
            put_parameter(
                f"/{self.prefix}/lab-03/oauth2-provider-arn",
                provider_arn
            )
            put_parameter(
                f"/{self.prefix}/lab-03/oauth2-secret-arn",
                secret_arn
            )
            put_parameter(
                f"/{self.prefix}/lab-03/oauth2-config",
                json.dumps(oauth2_config)
            )

            print(f"\nOAuth2 設定を SSM Parameter Store に保存しました")

            return oauth2_config

        except Exception as e:
            print(f"OAuth2 クレデンシャルプロバイダーの作成に失敗しました: {e}")
            raise

    def add_runtime_as_oauth2_target(
        self,
        gateway_id: str,
        runtime_arn: str,
        oauth2_provider_arn: Optional[str] = None
    ) -> Dict:
        """
        OAuth2 M2M 認証を使用して Runtime を Gateway ターゲットとして追加

        Gateway が Runtime を呼び出すリクエストを受け取ると:
        1. OAuth2 プロバイダーを使用して M2M アクセストークンを取得
        2. リクエストにトークンを含める: Authorization: Bearer {M2M_token}
        3. Runtime がトークンを検証し、スコープに基づいて操作を認可

        Args:
            gateway_id: Gateway 識別子
            runtime_arn: ターゲットとして登録する Runtime ARN
            oauth2_provider_arn: OAuth2 プロバイダー ARN（指定されない場合は SSM から取得）

        Returns:
            ターゲット設定を含む Dict
        """
        print("\n" + "="*70)
        print("OAUTH2 を使用して RUNTIME を GATEWAY ターゲットとして追加")
        print("="*70 + "\n")

        # OAuth2 プロバイダー ARN が指定されていない場合は取得
        if not oauth2_provider_arn:
            try:
                oauth2_provider_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-provider-arn")
                print(f"SSM から OAuth2 プロバイダー ARN を取得しました: {oauth2_provider_arn}")
            except Exception as e:
                print(f"OAuth2 プロバイダー ARN が SSM に見つかりません: {e}")
                print("   OAuth2 クレデンシャルプロバイダーが先に作成されていることを確認してください")
                raise

        # スコープ用のリソースサーバー識別子を取得
        try:
            resource_server_id = get_parameter(
                PARAMETER_PATHS['cognito']['resource_server_identifier']
            )
        except Exception as e:
            print(f"リソースサーバー識別子の取得に失敗しました: {e}")
            raise

        # M2M スコープを定義
        # これらのスコープは M2M トークンに含まれ、Runtime によって検証される
        scopes = [
            f"{resource_server_id}/mcp.invoke",
            f"{resource_server_id}/runtime.access"
        ]

        target_name = f"{self.prefix}-runtime-m2m-target"

        print(f"OAuth2 M2M 認証で Gateway ターゲットを作成中:")
        print(f"  - Gateway ID: {gateway_id}")
        print(f"  - Runtime ARN: {runtime_arn}")
        print(f"  - ターゲット名: {target_name}")
        print(f"  - スコープ: {', '.join(scopes)}\n")

        try:
            # Create gateway target with OAuth2 credential provider
            response = self.agentcore.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                targetConfiguration={
                    "mcp": {
                        "mcpServer": {
                            "runtimeArn": runtime_arn
                        }
                    }
                },
                credentialProviderConfigurations=[
                    {
                        "credentialProviderType": "OAUTH",
                        "credentialProvider": {
                            "oauthCredentialProvider": {
                                "providerArn": oauth2_provider_arn,
                                "scopes": scopes
                            }
                        }
                    }
                ]
            )

            target_id = response['targetId']

            print(f"OAuth2 M2M 認証で Runtime を Gateway ターゲットとして追加しました")
            print(f"   - ターゲット ID: {target_id}")
            print(f"   - ターゲット名: {target_name}")

            target_config = {
                "target_id": target_id,
                "target_name": target_name,
                "gateway_id": gateway_id,
                "runtime_arn": runtime_arn,
                "oauth2_provider_arn": oauth2_provider_arn,
                "scopes": scopes,
                "credential_type": "OAUTH"
            }

            # SSM に保存
            put_parameter(
                f"/{self.prefix}/lab-03/gateway-m2m-target",
                json.dumps(target_config)
            )

            print(f"\nGateway M2M ターゲット設定を SSM Parameter Store に保存しました")

            return target_config

        except Exception as e:
            print(f"Runtime を Gateway ターゲットとして追加できませんでした: {e}")
            raise

    def update_gateway_oauth2_permissions(self, gateway_role_arn: Optional[str] = None) -> None:
        """
        OAuth2 クレデンシャルにアクセスするための権限で Gateway IAM ロールを更新

        Gateway ロールに必要なもの:
        - bedrock-agentcore:GetResourceOauth2Token
        - secretsmanager:GetSecretValue

        Args:
            gateway_role_arn: Gateway ロール ARN（指定されない場合は SSM から取得）
        """
        print("\n" + "="*70)
        print("OAUTH2 権限で GATEWAY IAM ロールを更新")
        print("="*70 + "\n")

        # OAuth2 シークレット ARN を取得
        try:
            secret_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-secret-arn")
            provider_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-provider-arn")
        except Exception as e:
            print(f"OAuth2 設定の取得に失敗しました: {e}")
            raise

        # Gateway ロール ARN が指定されていない場合は取得
        if not gateway_role_arn:
            try:
                # まず既存のパラメータから取得を試みる
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-03/gateway-role-arn")
                gateway_role_arn = response['Parameter']['Value']
                print(f"SSM から Gateway ロール ARN を取得しました: {gateway_role_arn}")
            except ClientError:
                print(f"Gateway ロール ARN が SSM に見つかりません")
                raise

        # ARN からロール名を抽出
        # ARN 形式: arn:aws:iam::ACCOUNT:role/ROLE_NAME
        role_name = gateway_role_arn.split('/')[-1]

        print(f"IAM ロールを更新中: {role_name}\n")

        # OAuth2 権限ポリシーを定義
        oauth2_permissions = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "GetResourceOauth2Token",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetResourceOauth2Token"
                    ],
                    "Resource": [
                        provider_arn
                    ]
                },
                {
                    "Sid": "AccessSecretsManager",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Resource": [
                        secret_arn
                    ]
                }
            ]
        }

        try:
            self.iam.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{self.prefix}-oauth2-credentials-policy",
                PolicyDocument=json.dumps(oauth2_permissions)
            )

            print(f"OAuth2 権限を Gateway ロールにアタッチしました")
            print(f"   - GetResourceOauth2Token: {provider_arn}")
            print(f"   - GetSecretValue: {secret_arn}")

        except Exception as e:
            print(f"Gateway ロール権限の更新に失敗しました: {e}")
            raise

    def setup_m2m_authentication_complete(
        self,
        gateway_id: str,
        runtime_arn: str,
        gateway_role_arn: str
    ) -> Dict:
        """
        M2M 認証の完全なセットアップワークフロー

        ステップ:
        1. OAuth2 クレデンシャルプロバイダーを作成
        2. OAuth2 を使用して Runtime を Gateway ターゲットとして追加
        3. OAuth2 権限で Gateway IAM ロールを更新

        Args:
            gateway_id: Gateway 識別子
            runtime_arn: Runtime ARN
            gateway_role_arn: Gateway IAM ロール ARN

        Returns:
            完全な M2M 認証設定
        """
        print("\n" + "="*70)
        print("M2M 認証のセットアップ (GATEWAY <-> RUNTIME)")
        print("="*70 + "\n")

        print(f"設定:")
        print(f"  Gateway ID: {gateway_id}")
        print(f"  Runtime ARN: {runtime_arn}")
        print(f"  Gateway ロール: {gateway_role_arn}\n")

        # ステップ 1: OAuth2 クレデンシャルプロバイダーを作成
        oauth2_config = self.create_oauth2_credential_provider()
        time.sleep(5)  # プロバイダーの準備完了を待機

        # ステップ 2: OAuth2 を使用して Runtime を Gateway ターゲットとして追加
        target_config = self.add_runtime_as_oauth2_target(
            gateway_id=gateway_id,
            runtime_arn=runtime_arn,
            oauth2_provider_arn=oauth2_config['provider_arn']
        )

        # ステップ 3: OAuth2 権限で Gateway IAM ロールを更新
        self.update_gateway_oauth2_permissions(gateway_role_arn=gateway_role_arn)

        complete_config = {
            "oauth2_provider": oauth2_config,
            "gateway_target": target_config,
            "gateway_id": gateway_id,
            "runtime_arn": runtime_arn,
            "gateway_role_arn": gateway_role_arn
        }

        # 完全な設定を保存
        put_parameter(
            f"/{self.prefix}/lab-03/m2m-auth-complete-config",
            json.dumps(complete_config, indent=2)
        )

        print("\n" + "="*70)
        print("M2M 認証セットアップ完了")
        print("="*70 + "\n")

        print("Gateway から Runtime への M2M フロー:")
        print("  1. クライアントがユーザー JWT を使用して Gateway にリクエストを送信")
        print("  2. Gateway がユーザー JWT を検証")
        print("  3. Gateway が OAuth2 プロバイダーを使用して Cognito から M2M トークンを取得")
        print("  4. Gateway が M2M Bearer トークンを使用して Runtime を呼び出し")
        print("  5. Runtime が M2M トークンを検証して操作を認可")
        print(f"\nM2M スコープ: {', '.join(target_config['scopes'])}")
        print(f"\nすべての設定が SSM Parameter Store に保存されました")

        return complete_config

    def cleanup_oauth2_resources(self) -> None:
        """OAuth2 クレデンシャルプロバイダーと関連リソースをクリーンアップ"""
        print("\nOAuth2 リソースをクリーンアップ中...")

        try:
            # SSM からプロバイダー ARN を取得
            provider_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-provider-arn")

            # OAuth2 クレデンシャルプロバイダーを削除
            provider_id = provider_arn.split('/')[-1]
            self.agentcore.delete_oauth2_credential_provider(
                oAuth2CredentialProviderId=provider_id
            )
            print(f"OAuth2 クレデンシャルプロバイダーを削除しました")

        except Exception as e:
            print(f"OAuth2 プロバイダーを削除できませんでした: {e}")

        # SSM パラメータを削除
        ssm_params = [
            f"/{self.prefix}/lab-03/oauth2-provider-arn",
            f"/{self.prefix}/lab-03/oauth2-secret-arn",
            f"/{self.prefix}/lab-03/oauth2-config",
            f"/{self.prefix}/lab-03/gateway-m2m-target",
            f"/{self.prefix}/lab-03/m2m-auth-complete-config"
        ]

        for param in ssm_params:
            try:
                self.ssm.delete_parameter(Name=param)
            except:
                pass

        print(f"OAuth2 クリーンアップ完了")
