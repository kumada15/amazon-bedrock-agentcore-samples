"""
Lab 03: Runtime OAuth2 設定 - トークン検証セットアップ

Gateway からの M2M OAuth2 トークンを受け入れて検証するように AgentCore Runtime を設定します。

アーキテクチャ:
- Runtime は Gateway から Authorization: Bearer {M2M_token} 付きのリクエストを受け取る
- Runtime は Cognito 公開鍵を使用して JWT 署名を検証
- Runtime はトークンスコープをチェックして操作を認可
- 有効なトークンと必要なスコープを持つリクエストのみを許可

トークン検証フロー:
1. Gateway が Authorization ヘッダーで Bearer トークンを送信
2. Runtime がリクエストをインターセプトして JWT を抽出
3. Runtime が JWT ヘッダーの kid を使用して Cognito 公開鍵を取得
4. Runtime が JWT 署名を検証
5. Runtime がトークンクレームのスコープをチェック
6. Runtime がスコープに基づいて操作を許可/拒否
"""

import json
import boto3
from typing import Dict, Optional, List
from lab_helpers.config import AWS_REGION, AWS_PROFILE
from lab_helpers.parameter_store import get_parameter, put_parameter
from lab_helpers.constants import PARAMETER_PATHS


class RuntimeOAuth2Configuration:
    """受信する M2M OAuth2 トークンを検証するように Runtime を設定"""

    def __init__(self, region: str = AWS_REGION, profile: str = AWS_PROFILE):
        """Runtime OAuth2 設定を初期化"""
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.agentcore = self.session.client('bedrock-agentcore-control', region_name=region)
        self.ssm = self.session.client('ssm', region_name=region)
        self.sts = self.session.client('sts', region_name=region)

        self.region = region
        self.account_id = self.sts.get_caller_identity()['Account']
        self.prefix = "aiml301"

    def configure_runtime_token_validation(
        self,
        runtime_id: str,
        cognito_config: Optional[Dict] = None
    ) -> Dict:
        """
        Gateway からの M2M トークンを検証するように Runtime を設定

        Args:
            runtime_id: AgentCore Runtime ID
            cognito_config: Cognito 設定（指定されない場合は SSM から取得）

        Returns:
            Runtime OAuth2 検証設定
        """
        print("\n" + "="*70)
        print("M2M トークンを検証するように RUNTIME を設定")
        print("="*70 + "\n")

        # Cognito 設定が指定されていない場合は取得
        if not cognito_config:
            try:
                user_pool_id = get_parameter(PARAMETER_PATHS['cognito']['user_pool_id'])
                token_endpoint = get_parameter(PARAMETER_PATHS['cognito']['token_endpoint'])
                resource_server_id = get_parameter(PARAMETER_PATHS['cognito']['resource_server_identifier'])
                m2m_client_id = get_parameter(PARAMETER_PATHS['cognito']['m2m_client_id'])

                cognito_config = {
                    "user_pool_id": user_pool_id,
                    "token_endpoint": token_endpoint,
                    "resource_server_id": resource_server_id,
                    "m2m_client_id": m2m_client_id,
                    "region": self.region
                }

                print(f"SSM から Cognito 設定を取得しました")
            except Exception as e:
                print(f"Cognito 設定の取得に失敗しました: {e}")
                raise

        print(f"\nRuntime OAuth2 設定:")
        print(f"  Runtime ID: {runtime_id}")
        print(f"  ユーザープール: {cognito_config['user_pool_id']}")
        print(f"  M2M クライアント: {cognito_config['m2m_client_id']}")
        print(f"  リソースサーバー: {cognito_config['resource_server_id']}\n")

        # Runtime OAuth2 設定を構築
        runtime_oauth2_config = {
            "runtime_id": runtime_id,
            "inbound_auth_type": "OAUTH2_JWT",
            "oauth2_config": {
                "issuer": f"https://cognito-idp.{self.region}.amazonaws.com/{cognito_config['user_pool_id']}",
                "jwks_uri": f"https://cognito-idp.{self.region}.amazonaws.com/{cognito_config['user_pool_id']}/.well-known/jwks.json",
                "audience": [cognito_config['m2m_client_id']],
                "token_use": "access"
            },
            "scope_config": {
                "required_scopes": [
                    f"{cognito_config['resource_server_id']}/mcp.invoke",
                    f"{cognito_config['resource_server_id']}/runtime.access"
                ],
                "scope_strategy": "REQUIRE_ANY"  # Require at least one scope
            },
            "token_validation": {
                "validate_signature": True,
                "validate_expiration": True,
                "validate_issuer": True,
                "validate_audience": True,
                "clock_skew_seconds": 60  # 60 秒のクロックスキューを許可
            }
        }

        print("Runtime OAuth2 検証設定:")
        print(f"  インバウンド認証タイプ: {runtime_oauth2_config['inbound_auth_type']}")
        print(f"  発行者: {runtime_oauth2_config['oauth2_config']['issuer']}")
        print(f"  JWKS URI: {runtime_oauth2_config['oauth2_config']['jwks_uri']}")
        print(f"  必要なスコープ: {', '.join(runtime_oauth2_config['scope_config']['required_scopes'])}")
        print(f"  署名検証: {runtime_oauth2_config['token_validation']['validate_signature']}")
        print(f"  有効期限検証: {runtime_oauth2_config['token_validation']['validate_expiration']}\n")

        # 設定を SSM に保存
        put_parameter(
            f"/{self.prefix}/lab-03/runtime-oauth2-config",
            json.dumps(runtime_oauth2_config, indent=2)
        )

        print(f"Runtime OAuth2 設定を SSM Parameter Store に保存しました")

        return runtime_oauth2_config

    def create_runtime_iam_policy_for_token_validation(
        self,
        runtime_role_arn: str
    ) -> None:
        """
        トークン検証用の Runtime IAM ポリシーを作成

        必要な権限:
        - Cognito 公開鍵の取得（JWKS エンドポイント）
        - トークン検証サービスへのアクセス

        Args:
            runtime_role_arn: Runtime IAM ロール ARN
        """
        print("\n" + "="*70)
        print("トークン検証用に RUNTIME IAM ロールを更新")
        print("="*70 + "\n")

        # ARN からロール名を抽出
        role_name = runtime_role_arn.split('/')[-1]

        print(f"IAM ロールを更新中: {role_name}\n")

        # トークン検証ポリシーを作成
        token_validation_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "CognitoJWKSAccess",
                    "Effect": "Allow",
                    "Action": [
                        "cognito-idp:GetSigningCertificate",
                        "cognito-idp:GetUserPoolMxconfigAttribute"
                    ],
                    "Resource": f"arn:aws:cognito-idp:{self.region}:{self.account_id}:userpool/*"
                },
                {
                    "Sid": "CognitoUserPoolAccess",
                    "Effect": "Allow",
                    "Action": [
                        "cognito-idp:DescribeUserPool"
                    ],
                    "Resource": f"arn:aws:cognito-idp:{self.region}:{self.account_id}:userpool/*"
                },
                {
                    "Sid": "CloudWatchLogsForTokenValidation",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/bedrock-agentcore/runtime/token-validation*"
                }
            ]
        }

        try:
            iam = boto3.client('iam')
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{self.prefix}-runtime-token-validation-policy",
                PolicyDocument=json.dumps(token_validation_policy)
            )

            print(f"トークン検証権限で Runtime IAM ロールを更新しました")
            print(f"   ポリシー: {self.prefix}-runtime-token-validation-policy")
            print(f"   権限:")
            print(f"     - Cognito JWKS アクセス")
            print(f"     - ユーザープール検査")
            print(f"     - トークン検証ログ記録\n")

        except Exception as e:
            print(f"IAM ロールの更新に失敗しました: {e}")
            raise

    def generate_runtime_token_validation_code(self) -> str:
        """
        トークン検証用の Runtime Python コードを生成

        このコードは Runtime MCP サーバーで実行され、受信トークンを検証します。

        Returns:
            トークン検証用の Python コード
        """
        return '''
# Token Validation Module for AgentCore Runtime
import json
import jwt
from typing import Dict, Optional
from functools import lru_cache
import requests
from datetime import datetime, timedelta

class TokenValidator:
    """Gateway からの受信 OAuth2 M2M トークンを検証"""

    def __init__(self, user_pool_id: str, region: str):
        self.user_pool_id = user_pool_id
        self.region = region
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self.jwks_uri = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        self.jwks_cache = {}
        self.cache_expiration = None

    @lru_cache(maxsize=1)
    def _fetch_jwks(self) -> Dict:
        """Cognito 公開鍵を取得してキャッシュ"""
        try:
            response = requests.get(self.jwks_uri, timeout=5)
            response.raise_for_status()
            self.jwks_cache = response.json()
            # 1 時間キャッシュ
            self.cache_expiration = datetime.now() + timedelta(hours=1)
            return self.jwks_cache
        except Exception as e:
            print(f"JWKS の取得中にエラー: {e}")
            raise

    def get_signing_key(self, token_header: Dict) -> Dict:
        """トークン kid と一致する JWKS から署名鍵を取得"""
        kid = token_header.get('kid')
        jwks = self._fetch_jwks()

        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                return key

        raise ValueError(f"Signing key not found for kid: {kid}")

    def validate_token(
        self,
        token: str,
        required_scopes: list,
        m2m_client_id: str
    ) -> Dict:
        """
        Validate incoming M2M token

        Args:
            token: JWT access token from Authorization header
            required_scopes: List of required scopes
            m2m_client_id: Expected M2M client ID

        Returns:
            Decoded token claims if valid

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            # Decode header to get kid (without verification first)
            header = jwt.get_unverified_header(token)
            signing_key = self.get_signing_key(header)

            # Verify and decode token
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=['RS256'],
                issuer=self.issuer,
                audience=m2m_client_id,
                options={
                    'verify_exp': True,
                    'verify_iss': True,
                    'verify_aud': True
                }
            )

            # Verify scopes
            token_scope = claims.get('scope', '')
            token_scopes = set(token_scope.split())
            required_scope_set = set(required_scopes)

            # Check if token has at least one required scope
            if not token_scopes & required_scope_set:
                raise jwt.InvalidScopeError(
                    f"Token missing required scopes. "
                    f"Token scopes: {token_scopes}, Required: {required_scope_set}"
                )

            print(f"トークン検証が成功しました")
            print(f"   クライアント: {claims.get('client_id')}")
            print(f"   スコープ: {token_scope}")
            print(f"   有効期限: {datetime.fromtimestamp(claims.get('exp'))}")

            return claims

        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidSignatureError:
            raise jwt.InvalidTokenError("Invalid token signature")
        except jwt.InvalidIssuerError:
            raise jwt.InvalidTokenError("Invalid token issuer")
        except jwt.InvalidAudienceError:
            raise jwt.InvalidTokenError("Invalid token audience")
        except Exception as e:
            raise jwt.InvalidTokenError(f"Token validation failed: {str(e)}")

    def extract_token_from_header(self, auth_header: str) -> str:
        """Authorization ヘッダーから Bearer トークンを抽出"""
        if not auth_header:
            raise ValueError("Missing Authorization header")

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise ValueError("Invalid Authorization header format")

        return parts[1]


# Example usage in MCP server request handler:
"""
from fastmcp import FastMCP

validator = TokenValidator(
    user_pool_id="us-west-2_u7o1G39EX",
    region="us-west-2"
)

@mcp_server.post("/mcp")
async def handle_mcp_request(request: Request):
    # Extract and validate token
    auth_header = request.headers.get("Authorization")

    try:
        token = validator.extract_token_from_header(auth_header)
        claims = validator.validate_token(
            token=token,
            required_scopes=[
                "aiml301-agentcore-runtime/mcp.invoke",
                "aiml301-agentcore-runtime/runtime.access"
            ],
            m2m_client_id="41msff1c7p1brqi0jj7pr1bl9f"
        )

        # Token is valid, proceed with MCP request
        # Extract client from claims for audit logging
        client_id = claims.get("client_id")
        print(f"Processing MCP request from {client_id}")

    except jwt.InvalidTokenError as e:
        return {"error": f"Unauthorized: {str(e)}"}, 401
    except ValueError as e:
        return {"error": f"Bad Request: {str(e)}"}, 400
"""
'''

    def print_runtime_token_validation_guide(self) -> None:
        """Runtime でのトークン検証実装ガイドを表示"""
        print("\n" + "="*70)
        print("RUNTIME トークン検証実装ガイド")
        print("="*70 + "\n")

        print("Runtime MCP サーバーにトークン検証を実装するには:\n")

        print("1.  OAuth2 トークン検証ライブラリを追加:")
        print("   pip install PyJWT requests\n")

        print("2.  TokenValidator モジュールをインポート（生成されたコードを参照）:\n")

        print("3.  MCP サーバーでバリデーターを初期化:\n")
        print("   ```python")
        print("   validator = TokenValidator(")
        print("       user_pool_id='us-west-2_u7o1G39EX',")
        print("       region='us-west-2'")
        print("   )\n")
        print("   ```\n")

        print("4.  リクエストハンドラーでトークンを検証:\n")
        print("   ```python")
        print("   @mcp_server.post('/mcp')")
        print("   async def handle_request(request):")
        print("       auth_header = request.headers.get('Authorization')")
        print("       token = validator.extract_token_from_header(auth_header)")
        print("       claims = validator.validate_token(")
        print("           token=token,")
        print("           required_scopes=['aiml301-agentcore-runtime/mcp.invoke'],")
        print("           m2m_client_id='41msff1c7p1brqi0jj7pr1bl9f'")
        print("       )")
        print("       # 検証されたクレームでリクエストを処理")
        print("   ```\n")

        print("5.  トークン検証チェック項目:")
        print("   - JWT 署名 (RS256)")
        print("   - トークン有効期限")
        print("   - 発行者 (Cognito User Pool)")
        print("   - オーディエンス (M2M クライアント ID)")
        print("   - 必要なスコープ\n")

        print("6.  監査ログ記録:")
        print("   ログに含めるもの:")
        print("   - client_id（トークンから）")
        print("   - scopes（認可）")
        print("   - リクエストされた操作")
        print("   - タイムスタンプ\n")

        print("="*70 + "\n")


def setup_runtime_oauth2_validation_complete(
    runtime_id: str,
    runtime_role_arn: str
) -> Dict:
    """
    Runtime OAuth2 トークン検証の完全なセットアップワークフロー

    Args:
        runtime_id: Runtime ID
        runtime_role_arn: Runtime IAM ロール ARN

    Returns:
        完全な OAuth2 検証設定
    """
    print("\n" + "="*70)
    print("RUNTIME OAUTH2 トークン検証のセットアップ")
    print("="*70 + "\n")

    config = RuntimeOAuth2Configuration()

    # ステップ 1: トークン検証を設定
    runtime_oauth2_config = config.configure_runtime_token_validation(
        runtime_id=runtime_id
    )

    # ステップ 2: トークン検証権限で IAM ロールを更新
    config.create_runtime_iam_policy_for_token_validation(
        runtime_role_arn=runtime_role_arn
    )

    # ステップ 3: 実装ガイドを表示
    config.print_runtime_token_validation_guide()

    # ステップ 4: トークン検証コードを保存
    validation_code = config.generate_runtime_token_validation_code()
    put_parameter(
        f"/aiml301/lab-03/runtime-token-validation-code",
        validation_code
    )

    print(f"トークン検証コードを SSM Parameter Store に保存しました")
    print(f"   パス: /aiml301/lab-03/runtime-token-validation-code\n")

    return runtime_oauth2_config
