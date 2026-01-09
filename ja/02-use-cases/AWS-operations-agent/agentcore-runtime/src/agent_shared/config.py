# ============================================================================
# IMPORTS
# ============================================================================

import os
import yaml
import logging

from . import mylogger
 
logger = mylogger.get_logger()

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_configs():
    """
    統合 AgentCore 設定システムを使用して設定を読み込む。

    Returns:
        tuple: (merged_config, okta_config) - 設定データを含む2つの辞書
    """
    try:
        # Import the unified config manager
        import sys
        import os
        
        # In Docker container, config_manager is in /app/shared/
        # No need to manipulate path since it's in the same shared directory structure
        from .config_manager import AgentCoreConfigManager
        
        # Initialize config manager
        config_manager = AgentCoreConfigManager()
        
        # Get merged configuration (static + dynamic)
        merged_config = config_manager.get_merged_config()
        
        # Get OAuth settings
        okta_config = config_manager.get_oauth_settings()
        
        logger.info("統合 AgentCore 設定システムで設定を読み込みました")
        return merged_config, okta_config
        
    except Exception as e:
        logger.error(f"統合設定の読み込みに失敗しました: {e}")
        # Fallback to empty configs
        return {}, {}

# ============================================================================
# MODEL SETTINGS
# ============================================================================

def get_model_settings():
    """
    Strands 用のモデル設定を取得する。

    Returns:
        dict: region、model_id、temperature、max_tokens を含むモデル設定
    """
    agentcore_config, _ = load_configs()
    
    # Default values
    defaults = {
        'region_name': 'us-east-1',
        'model_id': 'global.anthropic.claude-haiku-4-5-20251001-v1:0',
        'temperature': 0.7,
        'max_tokens': 4096
    }
    
    try:
        # Extract from config
        aws_config = agentcore_config.get('aws', {})
        agents_config = agentcore_config.get('agents', {})
        
        model_settings = {
            'region_name': aws_config.get('region', defaults['region_name']),
            'model_id': agents_config.get('modelid', defaults['model_id']),
            'temperature': defaults['temperature'],  # Use default for now
            'max_tokens': defaults['max_tokens']     # Use default for now
        }
        
        logger.info(f"モデル設定: {model_settings}")
        return model_settings
        
    except Exception as e:
        logger.error(f"モデル設定の取得に失敗しました: {e}")
        logger.info(f"デフォルトのモデル設定を使用します: {defaults}")
        return defaults

# ============================================================================
# OAUTH SETTINGS
# ============================================================================

def get_oauth_settings():
    """
    OAuth プロバイダー設定を取得する。

    Returns:
        dict: OAuth プロバイダー設定
    """
    agentcore_config, okta_config = load_configs()
    
    try:
        # Get OAuth provider name from agentcore config
        oauth_config = agentcore_config.get('oauth', {})
        provider_name = oauth_config.get('provider_name', 'bac-identity-provider-okta')
        
        oauth_settings = {
            'provider_name': provider_name,
            'scopes': ['api'],  # Default scopes
            'auth_flow': 'M2M'  # Machine-to-Machine flow
        }
        
        return oauth_settings
        
    except Exception as e:
        logger.error(f"OAuth 設定の取得に失敗しました: {e}")
        # Return default settings
        default_settings = {
            'provider_name': 'bac-identity-provider-okta',
            'scopes': ['api'],
            'auth_flow': 'M2M'
        }
        logger.info(f"デフォルトの OAuth 設定を使用します: {default_settings}")
        return default_settings

# ============================================================================
# GATEWAY SETTINGS
# ============================================================================

def get_gateway_url():
    """
    MCP Gateway URL を取得する。

    Returns:
        str: Gateway URL、または設定されていない場合は None
    """
    agentcore_config, _ = load_configs()
    
    try:
        gateway_config = agentcore_config.get('gateway', {})
        gateway_url = gateway_config.get('url')
        
        if gateway_url:
            logger.info(f"Gateway URL: {gateway_url}")
        else:
            logger.info("Gateway URL が設定されていません - ローカルツールのみ使用します")
            
        return gateway_url
        
    except Exception as e:
        logger.error(f"Gateway URL の取得に失敗しました: {e}")
        return None
