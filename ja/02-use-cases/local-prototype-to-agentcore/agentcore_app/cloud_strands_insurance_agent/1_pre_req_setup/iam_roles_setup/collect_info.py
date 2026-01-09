#!/usr/bin/env python3
"""
IAM ロールセットアップ情報を収集するインタラクティブスクリプト

このスクリプトは Bedrock AgentCore IAM ロールの設定に必要な
すべての情報の収集をガイドします。
"""

import os
import sys
import subprocess
from typing import Dict, Optional, List, Any

# Import configuration module
from config import (
    load_config, save_config, get_regions,
    get_account_id, get_role_name
)

def clear_screen():
    """ターミナル画面をクリア"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_aws_account_id() -> Optional[str]:
    """
    AWS CLI を使用して AWS アカウント ID を取得

    Returns:
        AWS アカウント ID、取得できない場合は None
    """
    try:
        result = subprocess.run(
            ['aws', 'sts', 'get-caller-identity', '--query', 'Account', '--output', 'text'],
            capture_output=True,
            text=True,
            check=True
        )
        account_id = result.stdout.strip()
        return account_id
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def validate_aws_account_id(account_id: str) -> bool:
    """
    AWS アカウント ID の形式を検証

    Args:
        account_id: 検証するアカウント ID

    Returns:
        有効な場合は True、それ以外は False
    """
    # AWS account IDs are 12 digits
    return account_id.isdigit() and len(account_id) == 12

def collect_account_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    AWS アカウント情報を収集

    Args:
        config_data: 現在の設定

    Returns:
        更新された設定辞書
    """
    clear_screen()
    print("=== AWS アカウント情報 ===\n")
    
    # Try to get account ID automatically
    current_id = config_data.get('account', {}).get('id', '')
    detected_id = get_aws_account_id()
    
    if detected_id and not current_id:
        print(f"検出された AWS アカウント ID: {detected_id}")
        use_detected = input("Use this account ID? (Y/n): ").strip().lower() != 'n'
        if use_detected:
            account_id = detected_id
        else:
            account_id = input("Enter AWS Account ID: ").strip()
    else:
        if current_id:
            print(f"現在の AWS アカウント ID: {current_id}")
            change_id = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
            if change_id:
                account_id = input("Enter AWS Account ID: ").strip()
            else:
                account_id = current_id
        else:
            account_id = input("Enter AWS Account ID: ").strip()
    
    # Validate account ID
    while not validate_aws_account_id(account_id):
        print("無効な AWS アカウント ID です。12 桁の数字である必要があります。")
        account_id = input("Enter AWS Account ID: ").strip()
    
    # Get regions
    current_regions = ','.join(get_regions(config_data))
    print(f"\n現在の AWS リージョン: {current_regions}")
    change_regions = input("Do you want to change the regions? (y/N): ").strip().lower() == 'y'
    
    if change_regions:
        print("\nカンマ区切りの AWS リージョンリストを入力してください。")
        print("例: us-east-1,us-west-2")
        regions = input("AWS Regions: ").strip()
    else:
        regions = current_regions
    
    # Update config
    if 'account' not in config_data:
        config_data['account'] = {}
        
    config_data['account']['id'] = account_id
    config_data['account']['regions'] = regions
    
    return config_data

def collect_role_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    IAM ロール情報を収集

    Args:
        config_data: 現在の設定

    Returns:
        更新された設定辞書
    """
    clear_screen()
    print("=== IAM ロール情報 ===\n")
    
    # Get role name
    current_name = get_role_name(config_data)
    print(f"現在のロール名: {current_name}")
    change_name = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_name:
        role_name = input("Enter IAM Role Name: ").strip()
    else:
        role_name = current_name
    
    # Get role description
    current_desc = config_data.get('role', {}).get('description', 
                                            'Execution role for Bedrock AgentCore applications')
    print(f"\n現在のロール説明: {current_desc}")
    change_desc = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_desc:
        description = input("Enter Role Description: ").strip()
    else:
        description = current_desc
    
    # Update config
    if 'role' not in config_data:
        config_data['role'] = {}
        
    config_data['role']['name'] = role_name
    config_data['role']['description'] = description
    
    return config_data

def collect_policy_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    ポリシー設定情報を収集

    Args:
        config_data: 現在の設定

    Returns:
        更新された設定辞書
    """
    clear_screen()
    print("=== ポリシー設定 ===\n")
    print("実行ロールに含める権限を選択してください。")
    print("（デフォルトはすべての権限を有効化）\n")
    
    # Get current policies
    policies = config_data.get('policies', {})
    
    # Configure each policy option
    policy_options = [
        ('enable_ecr', 'Amazon ECR (Container Registry) Access'),
        ('enable_logs', 'CloudWatch Logs Access'),
        ('enable_xray', 'AWS X-Ray Tracing'),
        ('enable_cloudwatch', 'CloudWatch Metrics'),
        ('enable_bedrock_agentcore', 'Bedrock AgentCore Access'),
        ('enable_bedrock_models', 'Bedrock Models Access')
    ]
    
    for policy_key, policy_name in policy_options:
        current = policies.get(policy_key, 'true').lower() == 'true'
        enabled = 'enabled' if current else 'disabled'
        
        print(f"{policy_name} - 現在 {enabled}")
        toggle = input(f"Toggle this permission? (y/N): ").strip().lower() == 'y'
        
        if toggle:
            policies[policy_key] = str(not current).lower()
        else:
            policies[policy_key] = str(current).lower()
    
    # Update config
    config_data['policies'] = policies
    
    return config_data

def collect_ecr_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    ECR リポジトリ情報を収集

    Args:
        config_data: 現在の設定

    Returns:
        更新された設定辞書
    """
    clear_screen()
    print("=== ECR リポジトリ情報 ===\n")
    
    # Get repository name
    current_repo = config_data.get('ecr', {}).get('repository_name', 'bedrock-agentcore')
    print(f"現在のリポジトリ名: {current_repo}")
    change_repo = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_repo:
        repository_name = input("Enter ECR Repository Name: ").strip()
    else:
        repository_name = current_repo
    
    # Update config
    if 'ecr' not in config_data:
        config_data['ecr'] = {}
        
    config_data['ecr']['repository_name'] = repository_name
    
    return config_data

def collect_agent_info(config_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    エージェント情報を収集

    Args:
        config_data: 現在の設定

    Returns:
        更新された設定辞書
    """
    clear_screen()
    print("=== エージェント情報 ===\n")
    
    # Get agent name
    current_agent = config_data.get('agent', {}).get('name', 'insurance-agent')
    print(f"現在のエージェント名: {current_agent}")
    change_agent = input("Do you want to change it? (y/N): ").strip().lower() == 'y'
    
    if change_agent:
        agent_name = input("Enter Agent Name: ").strip()
    else:
        agent_name = current_agent
    
    # Update config
    if 'agent' not in config_data:
        config_data['agent'] = {}
        
    config_data['agent']['name'] = agent_name
    
    return config_data

def run_interactive_setup() -> Dict[str, Dict[str, str]]:
    """
    インタラクティブセットアッププロセスを実行

    Returns:
        最終的な設定辞書
    """
    print("=== Bedrock AgentCore IAM ロール セットアップ ===\n")
    print("このスクリプトは、AWS Bedrock AgentCore 実行に必要な")
    print("IAM ロールのセットアップをガイドします。\n")
    print("Enter キーを押して続行...")
    input()
    
    # Load current configuration
    config_data = load_config()
    
    # Collect information
    config_data = collect_account_info(config_data)
    config_data = collect_role_info(config_data)
    config_data = collect_ecr_info(config_data)
    config_data = collect_agent_info(config_data)
    config_data = collect_policy_info(config_data)
    
    # Summary
    clear_screen()
    print("=== 設定サマリー ===\n")
    print(f"AWS アカウント ID: {get_account_id(config_data)}")
    print(f"AWS リージョン: {','.join(get_regions(config_data))}")
    print(f"ロール名: {get_role_name(config_data)}")
    print(f"ロール説明: {config_data.get('role', {}).get('description')}")
    print(f"ECR リポジトリ: {config_data.get('ecr', {}).get('repository_name')}")
    print(f"エージェント名: {config_data.get('agent', {}).get('name')}")
    print("\nポリシー権限:")
    
    policies = config_data.get('policies', {})
    for policy_key, policy_name in [
        ('enable_ecr', 'Amazon ECR'),
        ('enable_logs', 'CloudWatch Logs'),
        ('enable_xray', 'X-Ray Tracing'),
        ('enable_cloudwatch', 'CloudWatch Metrics'),
        ('enable_bedrock_agentcore', 'Bedrock AgentCore'),
        ('enable_bedrock_models', 'Bedrock Models')
    ]:
        enabled = policies.get(policy_key, 'true').lower() == 'true'
        status = "✓" if enabled else "✗"
        print(f"  {status} {policy_name}")
    
    # Save configuration
    print("\nこの設定を保存しますか？")
    save = input("(Y/n): ").strip().lower() != 'n'
    
    if save:
        save_config(config_data)
        print("\n設定を保存しました！")
    else:
        print("\n設定は保存されませんでした。")
    
    return config_data

if __name__ == "__main__":
    try:
        run_interactive_setup()
    except KeyboardInterrupt:
        print("\n\nセットアップが中断されました。変更は保存されませんでした。")
        sys.exit(1)