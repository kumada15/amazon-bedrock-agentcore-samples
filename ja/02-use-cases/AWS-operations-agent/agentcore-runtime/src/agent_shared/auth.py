# ============================================================================
# IMPORTS
# ============================================================================

import logging
from .config import get_oauth_settings
from . import mylogger
 
logger = mylogger.get_logger()

# Global variables for OAuth state
_oauth_initialized = False
_token_getter = None

# ============================================================================
# OAUTH SETUP
# ============================================================================

def setup_oauth():
    """
    bedrock_agentcore.identity を使用して OAuth トークン取得機能をセットアップする。

    Returns:
        bool: 成功した場合は True、利用できない場合は False
    """
    global _oauth_initialized, _token_getter
    
    if _oauth_initialized:
        return True
    
    # Try multiple import paths for bedrock_agentcore.identity
    import_attempts = [
        "bedrock_agentcore.identity",
        "bedrock_agentcore.runtime.identity", 
        "agentcore.identity",
        "agentcore.runtime.identity"
    ]
    
    requires_access_token = None
    
    for import_path in import_attempts:
        try:
            logger.info(f"インポートを試行中: {import_path}")
            if import_path == "bedrock_agentcore.identity":
                from bedrock_agentcore.identity import requires_access_token
            elif import_path == "bedrock_agentcore.runtime.identity":
                from bedrock_agentcore.runtime.identity import requires_access_token
            elif import_path == "agentcore.identity":
                from agentcore.identity import requires_access_token
            elif import_path == "agentcore.runtime.identity":
                from agentcore.runtime.identity import requires_access_token
            
            logger.info(f"インポートに成功しました: {import_path}")
            break
            
        except ImportError as e:
            logger.info(f"インポートに失敗しました（{import_path}）: {e}")
            continue
    
    if requires_access_token is None:
        logger.warning("bedrock_agentcore.identity がどのインポートパスでも利用できません - OAuth は無効です")
        return False
    
    try:
        # Get OAuth settings
        oauth_settings = get_oauth_settings()
        provider_name = oauth_settings['provider_name']
        scopes = oauth_settings['scopes']
        auth_flow = oauth_settings['auth_flow']
        
        # logger.info(f"🔐 Setting up OAuth with provider: {provider_name}")
        # logger.info(f"🔐 Scopes: {scopes}")
        # logger.info(f"🔐 Auth flow: {auth_flow}")
        
        # Create token getter function
        @requires_access_token(
            provider_name=provider_name,
            scopes=scopes,
            auth_flow=auth_flow,
            force_authentication=False
        )
        def get_token_sync(*, access_token: str):
            return access_token
        
        _token_getter = get_token_sync
        _oauth_initialized = True
        
        logger.info("OAuth の初期化が完了しました")
        return True
        
    except Exception as e:
        logger.error(f"OAuth の初期化に失敗しました: {e}")
        return False

# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

def get_m2m_token():
    """
    Gateway アクセス用の M2M トークンを取得する。

    Returns:
        str: OAuth トークン、または利用できない場合は None
    """
    global _token_getter
    
    if not _oauth_initialized or not _token_getter:
        logger.warning("OAuth が初期化されていません - トークンは利用できません")
        return None
    
    try:
        logger.info("OAuth プロバイダーから M2M トークンをリクエスト中...")
        token = _token_getter()
        if token:
            logger.info(f"M2M トークンの取得に成功しました")
            logger.info(f"トークン長: {len(token)} 文字")
            logger.info(f"トークンの先頭: {token[:20]}...")
            return token
        else:
            logger.warning("OAuth プロバイダーからトークンが返されませんでした")
            return None
            
    except Exception as e:
        logger.error(f"M2M トークンの取得に失敗しました: {e}")
        import traceback
        logger.error(f"完全なトレースバック: {traceback.format_exc()}")
        return None

# ============================================================================
# ERROR HANDLING
# ============================================================================

def is_oauth_available():
    """
    OAuth 機能が利用可能かどうかを確認する。

    Returns:
        bool: OAuth が利用可能で初期化されている場合は True
    """
    return _oauth_initialized and _token_getter is not None
