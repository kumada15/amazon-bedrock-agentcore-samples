"""
Lab 03: Runtime OAuth2 Configuration - Token Validation Setup

Gateway からの M2M OAuth2 トークンを受け入れて検証するように AgentCore Runtime を設定します。

アーキテクチャ:
- Runtime は Gateway から Authorization: Bearer {M2M_token} 付きのリクエストを受信
- Runtime は Cognito 公開鍵を使用して JWT 署名を検証
- Runtime はトークンスコープをチェックし、操作を認可
- 有効なトークンと必要なスコープを持つリクエストのみを許可

トークン検証フロー:
1. Gateway が Authorization ヘッダーに Bearer トークンを送信
2. Runtime がリクエストをインターセプトし JWT を抽出
3. Runtime が JWT ヘッダーの kid を使用して Cognito 公開鍵を取得
4. Runtime が JWT 署名を検証
5. Runtime がトークンクレームのスコープをチェック
6. Runtime がスコープに基づいて操作を許可/拒否
"""

import json
import boto3
from typing import Dict, Optional
from lab_helpers.config import AWS_REGION, AWS_PROFILE
from lab_helpers.parameter_store import get_parameter, put_parameter
from lab_helpers.constants import PARAMETER_PATHS


class RuntimeOAuth2Configuration:
    """受信 M2M OAuth2 トークンを検証するように Runtime を設定"""

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
        print("CONFIGURING RUNTIME TO VALIDATE M2M TOKENS")
        print("="*70 + "\n")

        # 指定されていない場合は Cognito 設定を取得
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

                print("✅ Retrieved Cognito configuration from SSM")
            except Exception as e:
                print(f"❌ Failed to retrieve Cognito configuration: {e}")
                raise

        print("\nRuntime OAuth2 Configuration:")
        print(f"  Runtime ID: {runtime_id}")
        print(f"  User Pool: {cognito_config['user_pool_id']}")
        print(f"  M2M Client: {cognito_config['m2m_client_id']}")
        print(f"  Resource Server: {cognito_config['resource_server_id']}\n")

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
                "scope_strategy": "REQUIRE_ANY"  # 少なくとも 1 つのスコープを要求
            },
            "token_validation": {
                "validate_signature": True,
                "validate_expiration": True,
                "validate_issuer": True,
                "validate_audience": True,
                "clock_skew_seconds": 60  # 60 秒のクロックスキューを許可
            }
        }

        print("Runtime OAuth2 検証設定を構築しました")
        
        # 設定を SSM に保存
        put_parameter(
            f"/{self.prefix}/lab-03/runtime-oauth2-config",
            json.dumps(runtime_oauth2_config, indent=2)
        )

        print("✅ Runtime OAuth2 configuration saved to SSM Parameter Store")

        return runtime_oauth2_config

    def create_runtime_iam_policy_for_token_validation(
        self,
        runtime_role_arn: str
    ) -> None:
        """
        Runtime がトークンを検証するための IAM ポリシーを作成

        必要な権限:
        - Cognito 公開鍵の取得（JWKS エンドポイント）
        - トークン検証サービスへのアクセス

        Args:
            runtime_role_arn: Runtime IAM ロール ARN
        """
        print("\n" + "="*70)
        print("UPDATING RUNTIME IAM ROLE FOR TOKEN VALIDATION")
        print("="*70 + "\n")

        # ARN からロール名を抽出
        role_name = runtime_role_arn.split('/')[-1]

        print(f"Updating IAM role: {role_name}\n")

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

            print("✅ Runtime IAM role updated with token validation permissions")
            print(f"   Policy: {self.prefix}-runtime-token-validation-policy")
            print("   Permissions:")
            print("     • Cognito JWKS access")
            print("     • User pool inspection")
            print("     • Token validation logging\n")

        except Exception as e:
            print(f"❌ Failed to update IAM role: {e}")
            raise

    def generate_runtime_token_validation_code(self) -> str:
        """
        Runtime がトークンを検証するための Python コードを生成

        このコードは Runtime MCP サーバーで実行され、受信トークンを検証します。

        Returns:
            トークン検証用 Python コード
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
    """Gateway からの受信 OAuth2 M2M トークンを検証する"""

    def __init__(self, user_pool_id: str, region: str):
        self.user_pool_id = user_pool_id
        self.region = region
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self.jwks_uri = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        self.jwks_cache = {}
        self.cache_expiration = None

    @lru_cache(maxsize=1)
    def _fetch_jwks(self) -> Dict:
        """Cognito 公開鍵を取得してキャッシュする"""
        try:
            response = requests.get(self.jwks_uri, timeout=5)
            response.raise_for_status()
            self.jwks_cache = response.json()
            # Cache for 1 hour
            self.cache_expiration = datetime.now() + timedelta(hours=1)
            return self.jwks_cache
        except Exception as e:
            print(f"JWKS の取得中にエラー: {e}")
            raise

    def get_signing_key(self, token_header: Dict) -> Dict:
        """トークン kid と一致する JWKS から署名鍵を取得する"""
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

            print(f"✅ Token validated successfully")
            print(f"   Client: {claims.get('client_id')}")
            print(f"   Scopes: {token_scope}")
            print(f"   Exp: {datetime.fromtimestamp(claims.get('exp'))}")

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
        """Authorization ヘッダーから Bearer トークンを抽出する"""
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
        """Runtime でのトークン検証実装ガイドを出力"""
        print("\n" + "="*70)
        print("RUNTIME TOKEN VALIDATION IMPLEMENTATION GUIDE")
        print("="*70 + "\n")

        print("Runtime MCP サーバーでトークン検証を実装するには:\n")

        print("1️⃣  Add OAuth2 token validation library:")
        print("   pip install PyJWT requests\n")

        print("2️⃣  Import TokenValidator module (see generated code):\n")

        print("3️⃣  Initialize validator in your MCP server:\n")
        print("   ```python")
        print("   validator = TokenValidator(")
        print("       user_pool_id='us-west-2_u7o1G39EX',")
        print("       region='us-west-2'")
        print("   )\n")
        print("   ```\n")

        print("4️⃣  Validate tokens in request handler:\n")
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
        print("       # Process request with validated claims")
        print("   ```\n")

        print("5️⃣  Token validation checks:")
        print("   ✓ JWT signature (RS256)")
        print("   ✓ Token expiration")
        print("   ✓ Issuer (Cognito User Pool)")
        print("   ✓ Audience (M2M Client ID)")
        print("   ✓ Required scopes\n")

        print("6️⃣  Audit logging:")
        print("   Include in logs:")
        print("   - client_id (from token)")
        print("   - scopes (authorization)")
        print("   - operation requested")
        print("   - timestamp\n")

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
    print("SETTING UP RUNTIME OAUTH2 TOKEN VALIDATION")
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

    # ステップ 3: 実装ガイドを出力
    config.print_runtime_token_validation_guide()

    # ステップ 4: トークン検証コードを保存
    validation_code = config.generate_runtime_token_validation_code()
    put_parameter(
        f"/aiml301/lab-03/runtime-token-validation-code",
        validation_code
    )

    print("✅ Token validation code saved to SSM Parameter Store")
    print("   Path: /aiml301/lab-03/runtime-token-validation-code\n")

    return runtime_oauth2_config
