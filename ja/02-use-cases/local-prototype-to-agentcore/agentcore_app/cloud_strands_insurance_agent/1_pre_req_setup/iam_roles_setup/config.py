#!/usr/bin/env python3
"""
IAM ロール設定用の構成モジュール

このモジュールは IAM ロール作成に必要なすべての設定を保存し、
設定の読み込み/保存を行う関数を提供します。
"""

import os
import json
import configparser
from typing import Dict, Any, List, Optional

# Default config file path
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iam_config.ini')

# Default configuration
DEFAULT_CONFIG = {
    'role': {
        'name': 'BedrockAgentCoreExecutionRole',
        'description': 'Execution role for Bedrock AgentCore applications'
    },
    'account': {
        'id': '',
        'regions': 'us-east-1,us-west-2'
    },
    'ecr': {
        'repository_name': 'bedrock-agentcore'
    },
    'agent': {
        'name': 'insurance-agent'
    },
    'policies': {
        'enable_ecr': 'true',
        'enable_logs': 'true',
        'enable_xray': 'true',
        'enable_cloudwatch': 'true',
        'enable_bedrock_agentcore': 'true',
        'enable_bedrock_models': 'true'
    }
}

def create_default_config() -> None:
    """デフォルト設定ファイルが存在しない場合に作成"""
    if not os.path.exists(CONFIG_FILE):
        config = configparser.ConfigParser()
        
        for section, options in DEFAULT_CONFIG.items():
            config[section] = options
            
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        
        print(f"デフォルト設定を作成しました: {CONFIG_FILE}")

def load_config() -> Dict[str, Dict[str, str]]:
    """
    ファイルから設定を読み込む

    Returns:
        設定値を含む辞書
    """
    # Create default config if it doesn't exist
    if not os.path.exists(CONFIG_FILE):
        create_default_config()
    
    # Load configuration
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    # Convert to dictionary
    config_dict = {
        section: dict(config[section]) 
        for section in config.sections()
    }
    
    return config_dict

def save_config(config_data: Dict[str, Dict[str, str]]) -> None:
    """
    設定をファイルに保存

    Args:
        config_data: 設定値を含む辞書
    """
    config = configparser.ConfigParser()
    
    for section, options in config_data.items():
        config[section] = options
        
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    
    print(f"設定を保存しました: {CONFIG_FILE}")

def get_regions(config_data: Dict[str, Dict[str, str]]) -> List[str]:
    """
    設定からリージョンのリストを取得

    Args:
        config_data: 設定を含む辞書

    Returns:
        リージョン文字列のリスト
    """
    regions_str = config_data.get('account', {}).get('regions', 'us-east-1,us-west-2')
    return [r.strip() for r in regions_str.split(',') if r.strip()]

def get_account_id(config_data: Dict[str, Dict[str, str]]) -> str:
    """
    設定からアカウント ID を取得

    Args:
        config_data: 設定を含む辞書

    Returns:
        AWS アカウント ID 文字列
    """
    return config_data.get('account', {}).get('id', '')

def get_role_name(config_data: Dict[str, Dict[str, str]]) -> str:
    """
    設定からロール名を取得

    Args:
        config_data: 設定を含む辞書

    Returns:
        IAM ロール名
    """
    return config_data.get('role', {}).get('name', 'BedrockAgentCoreExecutionRole')

# Initialize configuration
if __name__ == "__main__":
    create_default_config()