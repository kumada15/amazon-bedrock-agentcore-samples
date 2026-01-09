#!/usr/bin/env python3
import boto3
import json
import os
import sys
import time

def test_ssm_connectivity():
    """SSM サービスへの接続をテストする"""
    print("SSM サービスへの接続をテスト中...")
    try:
        ssm_client = boto3.client('ssm')
        # Try to get a parameter that might not exist, but this will test connectivity
        try:
            response = ssm_client.get_parameter(Name='/AuroraOps/dev')
            print("✅ SSM に接続してパラメータを取得しました")
            print(f"パラメータ値: {response['Parameter']['Value']}")
        except ssm_client.exceptions.ParameterNotFound:
            print("✅ SSM に接続しました（パラメータは見つかりませんでしたが、接続は成功）")
        return True
    except Exception as e:
        print(f"❌ SSM への接続に失敗: {str(e)}")
        return False

def test_secrets_manager_connectivity():
    """Secrets Manager サービスへの接続をテストする"""
    print("\nSecrets Manager サービスへの接続をテスト中...")
    try:
        sm_client = boto3.client('secretsmanager')
        # List secrets to test connectivity
        response = sm_client.list_secrets(MaxResults=1)
        print("✅ Secrets Manager に接続しました")
        return True
    except Exception as e:
        print(f"❌ Secrets Manager への接続に失敗: {str(e)}")
        return False

def test_cloudwatch_logs_connectivity():
    """CloudWatch Logs サービスへの接続をテストする"""
    print("\nCloudWatch Logs サービスへの接続をテスト中...")
    try:
        logs_client = boto3.client('logs')
        # List log groups to test connectivity
        response = logs_client.describe_log_groups(limit=1)
        print("✅ CloudWatch Logs に接続しました")
        return True
    except Exception as e:
        print(f"❌ CloudWatch Logs への接続に失敗: {str(e)}")
        return False

def main():
    """AWS サービスへの接続をテストするメイン関数"""
    print("=== VPC エンドポイント接続テスト ===")
    
    # Set region from environment or use default
    region = os.environ.get('AWS_REGION', 'us-west-2')
    print(f"使用する AWS リージョン: {region}")
    
    # Test connectivity to each service
    ssm_success = test_ssm_connectivity()
    sm_success = test_secrets_manager_connectivity()
    logs_success = test_cloudwatch_logs_connectivity()
    
    # Print summary
    print("\n=== 接続テストサマリー ===")
    print(f"SSM: {'✅ 接続成功' if ssm_success else '❌ 失敗'}")
    print(f"Secrets Manager: {'✅ 接続成功' if sm_success else '❌ 失敗'}")
    print(f"CloudWatch Logs: {'✅ 接続成功' if logs_success else '❌ 失敗'}")
    
    # Return exit code based on success
    if ssm_success and sm_success and logs_success:
        print("\n✅ すべての接続テストに成功しました！")
        return 0
    else:
        print("\n❌ 一部の接続テストに失敗しました。VPC エンドポイント設定を確認してください。")
        return 1

if __name__ == "__main__":
    sys.exit(main())