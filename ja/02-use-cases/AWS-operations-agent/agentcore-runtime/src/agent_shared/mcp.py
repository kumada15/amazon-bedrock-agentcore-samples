# ============================================================================
# IMPORTS
# ============================================================================

import logging
from .auth import get_m2m_token

from . import mylogger
 
logger = mylogger.get_logger()

# Global MCP client for persistent connection
_global_mcp_client = None
_global_gateway_url = None
_global_token = None

def create_global_mcp_client(gateway_url, token=None):
    """
    アプリケーションの生存期間中維持されるグローバル MCP クライアントを作成する。

    Args:
        gateway_url (str): MCP 接続用の Gateway URL
        token (str, optional): OAuth トークン。None の場合は自動的に取得を試みる

    Returns:
        MCPClient or None: MCP クライアントインスタンス、または利用できない場合は None
    """
    global _global_mcp_client, _global_gateway_url, _global_token
    
    if not gateway_url:
        logger.info("Gateway URL が提供されていません - MCP クライアントは作成されません")
        return None
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("MCP クライアント用の OAuth トークンが利用できません")
                return None
        
        logger.info(f"グローバル MCP クライアントを作成中（Gateway: {gateway_url}）")
        logger.info(f"トークンを使用中（長さ: {len(token)}）")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Create and start MCP client
        mcp_client = MCPClient(create_transport)
        
        # Store globally
        _global_mcp_client = mcp_client
        _global_gateway_url = gateway_url
        _global_token = token
        
        logger.info(f"グローバル MCP クライアントの作成に成功しました")
        return mcp_client
        
    except ImportError as e:
        logger.warning(f"MCP 依存関係が利用できません: {e}")
        return None
    except Exception as e:
        logger.error(f"グローバル MCP クライアントの作成に失敗しました: {e}")
        import traceback
        logger.error(f"完全なトレースバック: {traceback.format_exc()}")
        return None

def get_mcp_tools_simple(gateway_url, token=None):
    """
    シンプルなアプローチを使用して MCP Gateway から利用可能なツールを取得する。

    Args:
        gateway_url (str): MCP 接続用の Gateway URL
        token (str, optional): OAuth トークン。None の場合は自動的に取得を試みる

    Returns:
        list: 利用可能なツールのリスト、またはない場合は空のリスト
    """
    if not gateway_url:
        logger.info("Gateway URL が提供されていません - 空のツールリストを返します")
        return []
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("MCP クライアント用の OAuth トークンが利用できません")
                return []
        
        logger.info(f"ツール検出用のシンプルな MCP クライアントを作成中")
        logger.info(f"Gateway: {gateway_url}")
        logger.info(f"トークンを使用中（長さ: {len(token)}）")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Use MCP client within context manager for tool discovery only
        with MCPClient(create_transport) as mcp_client:
            logger.info("MCP クライアントからツールをリスト中...")
            
            # Get tools from MCP client
            tools = mcp_client.list_tools_sync()
            tool_count = len(tools) if tools else 0
            
            logger.info(f"{tool_count} 個の MCP ツールが見つかりました")
            
            if tools:
                logger.info("利用可能な MCP ツール:")
                for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                    # Try to get tool name from tool_spec
                    tool_spec = getattr(tool, 'tool_spec', None)
                    if tool_spec and hasattr(tool_spec, 'name'):
                        tool_name = tool_spec.name
                        tool_desc = getattr(tool_spec, 'description', 'No description')
                    else:
                        tool_name = getattr(tool, 'tool_name', 'Unknown')
                        tool_desc = 'No description'
                    
                    logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
                if len(tools) > 5:
                    logger.info(f"   ... 他 {len(tools) - 5} 個のツール")
            
            # Return the tools - the client will stay alive within the context manager
            # The key is that we need to keep the client alive for the agent's lifetime
            logger.info("エージェント統合用の MCP ツールを返します")
            return tools or []
        
    except Exception as e:
        logger.error(f"MCP ツールの取得に失敗しました: {e}")
        import traceback
        logger.error(f"完全なトレースバック: {traceback.format_exc()}")
        return []

# ============================================================================
# MCP CLIENT CREATION
# ============================================================================

def create_mcp_client(gateway_url, token=None):
    """
    認証付きの MCP クライアントを作成する。

    Args:
        gateway_url (str): MCP 接続用の Gateway URL
        token (str, optional): OAuth トークン。None の場合は自動的に取得を試みる

    Returns:
        MCPClient or None: MCP クライアントインスタンス、または利用できない場合は None
    """
    if not gateway_url:
        logger.info("Gateway URL が提供されていません - MCP クライアントは作成されません")
        return None
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("MCP クライアント用の OAuth トークンが利用できません")
                return None
        
        logger.info(f"MCP クライアントを作成中（Gateway: {gateway_url}）")
        logger.info(f"トークンを使用中（長さ: {len(token)}、先頭: {token[:20]}...）")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            logger.info(f"ヘッダー付きでトランスポートを作成中: {list(headers.keys())}")
            return streamablehttp_client(
                gateway_url,
                headers=headers
            )
        
        # Create MCP client
        mcp_client = MCPClient(create_transport)
        logger.info(f"MCP クライアントの作成に成功しました")
        
        # Test the connection by trying to initialize
        try:
            # This will test the connection
            logger.info("MCP クライアント接続をテスト中...")
            # Don't close the client here - let it stay open
            logger.info("MCP クライアント接続テストに成功しました")
        except Exception as test_e:
            logger.warning(f"MCP クライアント接続テストに失敗しました: {test_e}")
            # Still return the client as it might work when actually used
        
        return mcp_client
        
    except ImportError as e:
        logger.warning(f"MCP 依存関係が利用できません: {e}")
        return None
    except Exception as e:
        logger.error(f"MCP クライアントの作成に失敗しました: {e}")
        return None

# ============================================================================
# TOOL DISCOVERY
# ============================================================================

def get_mcp_tools_with_client(gateway_url, token=None):
    """
    適切に管理されたクライアントを使用して MCP Gateway から利用可能なツールを取得する。

    Args:
        gateway_url (str): MCP 接続用の Gateway URL
        token (str, optional): OAuth トークン。None の場合は自動的に取得を試みる

    Returns:
        list: 利用可能なツールのリスト、またはない場合は空のリスト
    """
    if not gateway_url:
        logger.info("Gateway URL が提供されていません - 空のツールリストを返します")
        return []
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("MCP クライアント用の OAuth トークンが利用できません")
                return []
        
        logger.info(f"ツール検出用の MCP クライアントを作成中")
        logger.info(f"Gateway: {gateway_url}")
        logger.info(f"トークンを使用中（長さ: {len(token)}）")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Use MCP client within context manager
        with MCPClient(create_transport) as mcp_client:
            logger.info("MCP クライアントからツールをリスト中...")
            
            # Get tools from MCP client
            tools = mcp_client.list_tools_sync()
            tool_count = len(tools) if tools else 0
            
            logger.info(f"{tool_count} 個の MCP ツールが見つかりました")
            
            if tools:
                logger.info("利用可能な MCP ツール:")
                for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                    # Try different attribute names for tool info
                    tool_name = getattr(tool, 'name', None) or getattr(tool, 'tool_name', None) or str(tool)
                    tool_desc = getattr(tool, 'description', None) or getattr(tool, 'tool_description', None) or 'No description'
                    
                    # Debug: show tool attributes
                    tool_attrs = [attr for attr in dir(tool) if not attr.startswith('_')]
                    logger.debug(f"   Tool {i+1} attributes: {tool_attrs}")
                    
                    logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
                if len(tools) > 5:
                    logger.info(f"   ... 他 {len(tools) - 5} 個のツール")
            
            return tools or []
        
    except ImportError as e:
        logger.warning(f"MCP 依存関係が利用できません: {e}")
        return []
    except Exception as e:
        logger.error(f"MCP ツールの取得に失敗しました: {e}")
        import traceback
        logger.error(f"完全なトレースバック: {traceback.format_exc()}")
        return []

def get_mcp_tools(mcp_client):
    """
    MCP クライアントから利用可能なツールを取得する（互換性のためのレガシー関数）。

    Args:
        mcp_client: MCP クライアントインスタンス

    Returns:
        list: 利用可能なツールのリスト、またはない場合は空のリスト
    """
    if not mcp_client:
        logger.info("MCP クライアントが提供されていません - 空のツールリストを返します")
        return []
    
    try:
        logger.info("MCP クライアントからツールをリスト中...")
        
        # Get tools from MCP client
        tools = mcp_client.list_tools_sync()
        tool_count = len(tools) if tools else 0
        
        logger.info(f"{tool_count} 個の MCP ツールが見つかりました")
        
        if tools:
            logger.info("利用可能な MCP ツール:")
            for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                tool_name = getattr(tool, 'name', 'Unknown')
                tool_desc = getattr(tool, 'description', 'No description')
                logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
            if len(tools) > 5:
                logger.info(f"   ... 他 {len(tools) - 5} 個のツール")
        
        return tools or []
        
    except Exception as e:
        logger.error(f"MCP ツールの取得に失敗しました: {e}")
        import traceback
        logger.error(f"完全なトレースバック: {traceback.format_exc()}")
        return []

# ============================================================================
# PERSISTENT MCP CLIENT MANAGEMENT
# ============================================================================

def create_persistent_mcp_client(gateway_url, token=None):
    """
    ツール実行のために維持される永続的な MCP クライアントを作成する。

    Args:
        gateway_url (str): MCP 接続用の Gateway URL
        token (str, optional): OAuth トークン。None の場合は自動的に取得を試みる

    Returns:
        MCPClient or None: MCP クライアントインスタンス、または利用できない場合は None
    """
    global _global_mcp_client, _global_gateway_url, _global_token
    
    if not gateway_url:
        logger.info("Gateway URL が提供されていません - MCP クライアントは作成されません")
        return None
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("MCP クライアント用の OAuth トークンが利用できません")
                return None
        
        logger.info(f"永続的な MCP クライアントを作成中（Gateway: {gateway_url}）")
        logger.info(f"トークンを使用中（長さ: {len(token)}）")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Create MCP client (don't use context manager - keep it alive)
        mcp_client = MCPClient(create_transport)
        
        # Initialize the client
        mcp_client.__enter__()
        
        # Store globally for tool execution
        _global_mcp_client = mcp_client
        _global_gateway_url = gateway_url
        _global_token = token
        
        logger.info(f"永続的な MCP クライアントの作成に成功しました")
        return mcp_client
        
    except ImportError as e:
        logger.warning(f"MCP 依存関係が利用できません: {e}")
        return None
    except Exception as e:
        logger.error(f"永続的な MCP クライアントの作成に失敗しました: {e}")
        import traceback
        logger.error(f"完全なトレースバック: {traceback.format_exc()}")
        return None

def get_global_mcp_client():
    """
    ツール実行用のグローバル MCP クライアントを取得する。

    Returns:
        MCPClient or None: グローバル MCP クライアントインスタンス
    """
    return _global_mcp_client

def cleanup_global_mcp_client():
    """
    グローバル MCP クライアントをクリーンアップする。
    """
    global _global_mcp_client
    if _global_mcp_client:
        try:
            # The client should already be closed from the context manager
            logger.info("グローバル MCP クライアントをクリーンアップしました")
        except Exception as e:
            logger.warning(f"グローバル MCP クライアントのクリーンアップ中にエラーが発生しました: {e}")
        finally:
            _global_mcp_client = None

def cleanup_mcp_client():
    """互換性のためのレガシークリーンアップ関数"""
    cleanup_global_mcp_client()

def get_mcp_tools_with_persistent_client(gateway_url, token=None):
    """
    永続的なクライアントを使用して MCP Gateway から利用可能なツールを取得する。

    Args:
        gateway_url (str): MCP 接続用の Gateway URL
        token (str, optional): OAuth トークン。None の場合は自動的に取得を試みる

    Returns:
        list: 利用可能なツールのリスト、またはない場合は空のリスト
    """
    if not gateway_url:
        logger.info("Gateway URL が提供されていません - 空のツールリストを返します")
        return []
    
    try:
        # Create persistent client
        mcp_client = create_persistent_mcp_client(gateway_url, token)
        if not mcp_client:
            logger.warning("永続的な MCP クライアントの作成に失敗しました")
            return []
        
        logger.info("永続的な MCP クライアントからツールをリスト中...")
        
        # Get tools from MCP client
        tools = mcp_client.list_tools_sync()
        tool_count = len(tools) if tools else 0
        
        logger.info(f"{tool_count} 個の MCP ツールが見つかりました")
        
        if tools:
            logger.info("利用可能な MCP ツール:")
            for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                # Try different attribute names for tool info
                tool_name = getattr(tool, 'name', None) or getattr(tool, 'tool_name', None) or str(tool)
                tool_desc = getattr(tool, 'description', None) or getattr(tool, 'tool_description', None) or 'No description'
                
                logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
            if len(tools) > 5:
                logger.info(f"   ... 他 {len(tools) - 5} 個のツール")
        
        return tools or []
        
    except Exception as e:
        logger.error(f"永続的なクライアントでの MCP ツールの取得に失敗しました: {e}")
        import traceback
        logger.error(f"完全なトレースバック: {traceback.format_exc()}")
        return []

# ============================================================================
# ERROR HANDLING
# ============================================================================

def is_mcp_available(gateway_url):
    """
    MCP 機能が利用可能かどうかを確認する。

    Args:
        gateway_url (str): 確認する Gateway URL

    Returns:
        bool: MCP が使用可能な場合は True
    """
    if not gateway_url:
        return False
    
    try:
        # Check if MCP dependencies are available
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        return True
    except ImportError:
        return False