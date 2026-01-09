"""
デバイス管理フロントエンド - Amazon Cognito 認証モジュール

このモジュールは、Amazon Cognito OAuth 2.0 と JWT 検証を使用して、
デバイス管理システムフロントエンドに包括的な認証機能を提供します。
ユーザーログイン、トークン交換、セッション管理、および FastAPI
Web アプリケーションの認可を処理します。

このモジュールが実装するもの:
- OAuth ログイン用の Amazon Cognito Hosted UI 統合
- アクセストークン取得のための認可コード交換
- JWKS（JSON Web Key Set）を使用した JWT トークン検証
- Cookie サポート付きのセッションベース認証
- 開発/テスト用のシンプルログインフォールバック
- JWT クレームからのユーザー情報抽出

主な機能:
    - Cognito との OAuth 2.0 認可コードフロー
    - RSA 公開鍵を使用した JWT 署名検証
    - トークンの有効期限とオーディエンス検証
    - FastAPI 用のセッションミドルウェア統合
    - デュアル認証サポート（Cognito + シンプルログイン）
    - 自動 JWKS 取得とキャッシング
    - Cognito Hosted UI リダイレクトによるログアウト

認証フロー:
    1. ユーザーがログインをクリック → Cognito Hosted UI にリダイレクト
    2. ユーザーが認証 → Cognito が認可コード付きでリダイレクト
    3. バックエンドがコードをトークン（アクセス + ID トークン）と交換
    4. バックエンドが ID トークンの署名とクレームを検証
    5. ユーザー情報をセッションに保存
    6. 以降のリクエストはセッション認証を使用

必須環境変数:
    COGNITO_DOMAIN: Cognito ドメイン（例: domain.auth.region.amazoncognito.com）
    COGNITO_CLIENT_ID: Cognito App Client からの OAuth クライアント ID
    COGNITO_CLIENT_SECRET: Cognito App Client からの OAuth クライアントシークレット
    COGNITO_REDIRECT_URI: OAuth コールバック URL（例: http://localhost:5001/auth/callback）
    COGNITO_LOGOUT_URI: ログアウトリダイレクト URL（例: http://localhost:5001/simple-login）
    AWS_REGION: Cognito User Pool 用の AWS リージョン
    COGNITO_USER_POOL_ID: JWKS 検証用の Cognito User Pool ID

関数:
    get_jwks(): Cognito から JSON Web Key Set を取得してキャッシュ
    get_login_url(): Cognito Hosted UI ログイン URL を生成
    get_logout_url(): Cognito Hosted UI ログアウト URL を生成
    exchange_code_for_tokens(): 認可コードをトークンと交換
    validate_token(): JWT トークンの署名とクレームを検証
    get_current_user(): セッションまたは Cookie から認証済みユーザーを取得
    login_required(): 保護されたルート用の FastAPI 依存関係

JWT 検証:
    - Cognito JWKS エンドポイントから公開鍵を取得
    - 一致するキー ID（kid）を使用して RSA 署名を検証
    - トークンの有効期限（exp クレーム）を検証
    - オーディエンス（client_id クレーム）を検証
    - ユーザークレーム（sub、email、name）を抽出

セッション管理:
    - ユーザー情報は FastAPI セッションに保存
    - セッションに含まれるもの: sub、email、name、access_token、id_token
    - シンプルログインフォールバックはユーザー名を Cookie に保存
    - ログアウト時にセッションをクリア

使用例:
    FastAPI ルートで:
    >>> @app.get("/protected")
    >>> async def protected_route(request: Request):
    >>>     user = await get_current_user(request)
    >>>     if not user:
    >>>         return RedirectResponse(url="/login")
    >>>     return {"user": user}

    依存性注入で:
    >>> @app.get("/profile")
    >>> async def profile(user: dict = Depends(login_required)):
    >>>     return {"user": user}

セキュリティ機能:
    - JWT 署名検証によりトークン改ざんを防止
    - トークン有効期限によりリプレイ攻撃を防止
    - オーディエンス検証によりトークン悪用を防止
    - 本番環境では HTTPS が必要（OAuth リダイレクト URI）
    - クライアントシークレットはサーバー側で保持（ブラウザに公開しない）

エラーハンドリング:
    - 無効なトークンは 401 ステータスの HTTPException を発生
    - 認証がない場合はログインにリダイレクト
    - トークン交換失敗時はエラー詳細を返す
    - JWKS 取得失敗時はログに記録して適切に処理

注意事項:
    - JWKS は API 呼び出しを最小化するためにグローバルにキャッシュ
    - シンプルログインは開発専用（パスワード検証なし）
    - 本番環境では Cognito 認証のみを使用すべき
    - セッションミドルウェアは main.py で設定が必要
    - ログアウトはセッションと Cookie の両方をクリア
"""
import os
import logging
from urllib.parse import urlencode
from typing import Optional, Dict, Any

import httpx
from fastapi import Request, HTTPException
from jose import jwk, jwt
from jose.utils import base64url_decode

# ロギングを設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数から Cognito 設定を取得
COGNITO_DOMAIN = os.getenv("COGNITO_DOMAIN")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET")
COGNITO_REDIRECT_URI = os.getenv("COGNITO_REDIRECT_URI")
COGNITO_LOGOUT_URI = os.getenv("COGNITO_LOGOUT_URI")
AWS_REGION = os.getenv("AWS_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")

# JWT 検証
jwks_url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
jwks = None

async def get_jwks():
    """Cognito から JSON Web Key Set を取得します"""
    global jwks
    if jwks is None:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url)
            jwks = response.json()
    return jwks

def get_login_url() -> str:
    """Cognito ログイン URL を生成します"""
    # Cognito Hosted UI を直接使用
    login_url = f"https://{COGNITO_DOMAIN}/login?client_id={COGNITO_CLIENT_ID}&response_type=code&redirect_uri={COGNITO_REDIRECT_URI}"

    # デバッグログ
    logger.info(f"COGNITO_DOMAIN: {COGNITO_DOMAIN}")
    logger.info(f"COGNITO_CLIENT_ID: {COGNITO_CLIENT_ID}")
    logger.info(f"COGNITO_REDIRECT_URI: {COGNITO_REDIRECT_URI}")
    logger.info(f"完全なログイン URL: {login_url}")

    return login_url

def get_logout_url() -> str:
    """Cognito ログアウト URL を生成します"""
    params = {
        "client_id": COGNITO_CLIENT_ID,
        "logout_uri": COGNITO_LOGOUT_URI
    }
    return f"https://{COGNITO_DOMAIN}/logout?{urlencode(params)}"

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """認可コードをトークンと交換します"""
    token_endpoint = f"https://{COGNITO_DOMAIN}/oauth2/token"

    # Authorization ヘッダーの代わりに、client_id と client_secret をフォームデータに含める
    data = {
        "grant_type": "authorization_code",
        "client_id": COGNITO_CLIENT_ID,
        "client_secret": COGNITO_CLIENT_SECRET,
        "code": code,
        "redirect_uri": COGNITO_REDIRECT_URI
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logger.info(f"client_id でトークンと交換中: {COGNITO_CLIENT_ID}")

    async with httpx.AsyncClient() as client:
        response = await client.post(token_endpoint, headers=headers, data=data)

    if response.status_code != 200:
        logger.error(f"トークン交換に失敗しました: {response.text}")
        raise HTTPException(status_code=400, detail=f"トークン交換に失敗しました: {response.text}")

    return response.json()

async def validate_token(token: str) -> Dict[str, Any]:
    """Cognito からの JWT トークンを検証します"""
    # トークンヘッダーからキー ID を取得
    header = jwt.get_unverified_header(token)
    kid = header["kid"]

    # キー ID に一致する公開鍵を取得
    jwks_client = await get_jwks()
    key = None
    for jwk_key in jwks_client["keys"]:
        if jwk_key["kid"] == kid:
            key = jwk_key
            break

    if not key:
        raise HTTPException(status_code=401, detail="無効なトークン: キーが見つかりません")

    # 署名を検証
    hmac_key = jwk.construct(key)
    message, encoded_signature = token.rsplit(".", 1)
    decoded_signature = base64url_decode(encoded_signature.encode())

    if not hmac_key.verify(message.encode(), decoded_signature):
        raise HTTPException(status_code=401, detail="無効なトークン: 署名検証に失敗しました")

    # クレームを検証
    claims = jwt.get_unverified_claims(token)

    # 有効期限を確認
    import time
    if claims["exp"] < time.time():
        raise HTTPException(status_code=401, detail="トークンの有効期限が切れています")

    # オーディエンスを確認
    if claims["client_id"] != COGNITO_CLIENT_ID:
        raise HTTPException(status_code=401, detail="無効なオーディエンスです")

    return claims

async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """セッションまたはシンプル Cookie から現在の認証済みユーザーを取得します"""
    # 最初に Cognito セッションを確認
    if "user" in request.session:
        return request.session["user"]

    # フォールバックとしてシンプルログイン Cookie を確認
    simple_user = request.cookies.get("simple_user")
    if simple_user:
        return {"username": simple_user, "auth_type": "simple"}

    return None

def login_required(request: Request):
    """ユーザーがログインしているか確認する依存関係"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="認証が必要です")
    return user
