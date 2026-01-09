"""
AgentCore 設定マネージャー
すべての AgentCore コンシューマー向けの統合設定管理
"""

import os
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from . import mylogger
 
logger = mylogger.get_logger()

class AgentCoreConfigManager:
    """すべての AgentCore コンシューマー向けの統合設定管理"""

    def __init__(self, environment: str = "debug"):
        """
        設定マネージャーを初期化する

        Args:
            environment: 環境タイプ ("debug" または "performance")
        """
        self.environment = environment
        self.project_root = self._find_project_root()
        self._validator = None  # Will be imported when needed to avoid circular imports
        
    def _find_project_root(self) -> Path:
        """.agentcore.yaml を含むプロジェクトルートディレクトリを検索する"""
        current = Path(__file__).parent
        while current != current.parent:
            if (current / '.agentcore.yaml').exists():
                return current
            current = current.parent
        
        # Fallback to parent of shared directory
        return Path(__file__).parent.parent
    
    def _load_yaml(self, relative_path: str) -> Dict[str, Any]:
        """プロジェクトルートからの相対パスで YAML ファイルを読み込む"""
        file_path = self.project_root / relative_path
        
        if not file_path.exists():
            logger.warning(f"設定ファイルが見つかりません: {file_path}")
            return {}
        
        try:
            with open(file_path, 'r') as f:
                content = yaml.safe_load(f) or {}
            logger.debug(f"設定を読み込みました: {file_path}")
            return content
        except Exception as e:
            logger.error(f"設定の読み込みに失敗しました（{file_path}）: {e}")
            return {}
    
    def _save_yaml(self, relative_path: str, data: Dict[str, Any]) -> None:
        """プロジェクトルートからの相対パスで YAML ファイルを保存する"""
        file_path = self.project_root / relative_path
        
        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, indent=2)
            logger.debug(f"設定を保存しました: {file_path}")
        except Exception as e:
            logger.error(f"設定の保存に失敗しました（{file_path}）: {e}")
            raise
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """2つの辞書を深いマージする。override が優先される"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    # Static Configuration Methods
    def get_static_config(self) -> Dict[str, Any]:
        """静的設定を取得する（バージョン管理対象）"""
        # Load consolidated static config file
        return self._load_yaml("config/static-config.yaml")
    
    def get_base_settings(self) -> Dict[str, Any]:
        """基本設定のみを取得する（後方互換性）"""
        return self.get_static_config()
    
    # Dynamic Configuration Methods
    def get_dynamic_config(self) -> Dict[str, Any]:
        """動的設定を取得する（デプロイ時に生成）"""
        # Load consolidated dynamic config file
        return self._load_yaml("config/dynamic-config.yaml")
    
    def update_dynamic_config(self, updates: Dict[str, Any]) -> None:
        """動的設定ファイルを更新する"""
        file_path = "config/dynamic-config.yaml"
        current = self._load_yaml(file_path)
        updated = self._deep_merge(current, updates)
        self._save_yaml(file_path, updated)
    
    # Merged Configuration Methods
    def get_merged_config(self) -> Dict[str, Any]:
        """完全な設定を取得する（静的 + 動的のマージ）"""
        static = self.get_static_config()
        dynamic = self.get_dynamic_config()
        return self._deep_merge(static, dynamic)
    
    # Convenience Methods for Backward Compatibility
    def get_model_settings(self) -> Dict[str, Any]:
        """モデル設定を取得する（後方互換性）"""
        config = self.get_merged_config()
        aws_config = config.get("aws", {})
        agents_config = config.get("agents", {})
        
        return {
            "region_name": aws_config.get("region", "us-east-1"),
            "model_id": agents_config.get("modelid", "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
            "temperature": 0.7,  # Default from current usage
            "max_tokens": 4096   # Default from current usage
        }
    
    def get_gateway_url(self) -> str:
        """Gateway URL を取得する（後方互換性）"""
        config = self.get_merged_config()
        return config.get("gateway", {}).get("url", "")
    
    def get_oauth_settings(self) -> Dict[str, Any]:
        """OAuth 設定を取得する（後方互換性）"""
        config = self.get_merged_config()
        return config.get("okta", {})
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Bedrock エージェントツールスキーマを取得する（Gateway ターゲット作成用）"""
        config = self.get_static_config()
        return config.get("tools_schema", [])
    
    def get_mcp_lambda_config(self) -> Dict[str, Any]:
        """MCP Lambda 設定を取得する（デプロイと Gateway 操作用）"""
        config = self.get_merged_config()
        return config.get("mcp_lambda", {})
    
    def validate(self) -> bool:
        """現在の設定を検証する"""
        try:
            # Import validator here to avoid circular imports
            if self._validator is None:
                from .config_validator import ConfigValidator
                self._validator = ConfigValidator()
            
            static = self.get_static_config()
            dynamic = self.get_dynamic_config()
            merged = self.get_merged_config()
            
            self._validator.validate_static(static)
            self._validator.validate_dynamic(dynamic)
            
            return True
        except Exception as e:
            logger.error(f"設定の検証に失敗しました: {e}")
            return False