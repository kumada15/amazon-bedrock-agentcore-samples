"""
アクター ID 抽出用 JWT ヘルパー関数

Cognito JWT トークンからアクター ID を抽出するユーティリティを提供します。
Labs 2-5 でエージェント呼び出しを特定のユーザー/アクターに紐付けるために使用されます。
"""

import jwt
import json
import urllib.request
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def get_jwt_claims(
    access_token: str,
    region: str,
    user_pool_id: str,
    skip_verification: bool = True
) -> Dict[str, str]:
    """
    Cognito JWT トークンからクレームを抽出します。

    Args:
        access_token: Cognito 認証からの JWT トークン
        region: Cognito プールが作成された AWS リージョン
        user_pool_id: Cognito ユーザープール ID
        skip_verification: True の場合、署名検証なしでデコード（ラボではデフォルト: True）

    Returns:
        キー: actor_id, sub, email, username, token_use, aud を含む辞書

    Example:
        >>> claims = get_jwt_claims(token, "us-west-2", "us-west-2_abc123xyz")
        >>> actor_id = claims['actor_id']  # Cognito からのユーザー名
    """
    try:
        # Decode JWT (skip verification for workshop labs)
        claims = jwt.decode(access_token, options={"verify_signature": False})

        # Extract actor_id from username claim
        # Cognito stores username in 'cognito:username'
        actor_id = claims.get('cognito:username', claims.get('sub', 'unknown-user'))

        return {
            "actor_id": actor_id,
            "sub": claims.get('sub'),
            "email": claims.get('email'),
            "token_use": claims.get('token_use'),
            "aud": claims.get('aud'),
            "username": claims.get('cognito:username')
        }

    except jwt.InvalidTokenError as e:
        logger.error(f"無効な JWT トークン: {e}")
        raise
    except Exception as e:
        logger.error(f"JWT クレームの抽出中にエラーが発生しました: {e}")
        raise


def extract_actor_id_from_jwt(access_token: str) -> str:
    """
    JWT トークンから actor_id のみを抽出するクイックユーティリティ。

    Args:
        access_token: Cognito からの JWT トークン

    Returns:
        トークンからの actor_id（ユーザー名）
    """
    try:
        claims = jwt.decode(access_token, options={"verify_signature": False})
        return claims.get('cognito:username', claims.get('sub', 'unknown-user'))
    except Exception as e:
        logger.error(f"JWT から actor_id を抽出中にエラーが発生しました: {e}")
        raise
