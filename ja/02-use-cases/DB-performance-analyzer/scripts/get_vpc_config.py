#!/usr/bin/env python3
import boto3
import json
import os
import sys
import argparse

def get_vpc_config(cluster_name, region):
    """
    データベースクラスターの VPC 設定を取得し、セキュリティグループを設定する

    Args:
        cluster_name: RDS/Aurora クラスター名
        region: AWS リージョン

    Returns:
        bool: 成功した場合は True、失敗した場合は False
    """
    print(f"クラスターの VPC 設定を取得中: {cluster_name}")
    
    # AWS クライアントを初期化
    rds = boto3.client('rds', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)

    try:
        # クラスター情報を取得
        response = rds.describe_db_clusters(DBClusterIdentifier=cluster_name)
        
        if not response['DBClusters']:
            print(f"エラー: クラスター {cluster_name} が見つかりません")
            return False
        
        cluster = response['DBClusters'][0]

        # VPC ID とサブネット ID を取得
        vpc_id = None
        subnet_ids = []
        db_security_group_ids = []

        # DB サブネットグループから VPC ID とセキュリティグループを取得
        subnet_group_name = cluster.get('DBSubnetGroup')
        if subnet_group_name:
            subnet_response = rds.describe_db_subnet_groups(DBSubnetGroupName=subnet_group_name)
            if subnet_response['DBSubnetGroups']:
                subnet_group = subnet_response['DBSubnetGroups'][0]
                vpc_id = subnet_group['VpcId']
                subnet_ids = [subnet['SubnetIdentifier'] for subnet in subnet_group['Subnets']]

        # セキュリティグループを取得
        db_security_group_ids = cluster.get('VpcSecurityGroups', [])
        db_security_group_ids = [sg['VpcSecurityGroupId'] for sg in db_security_group_ids]
        
        if not vpc_id or not subnet_ids:
            print("エラー: VPC ID またはサブネット ID を特定できませんでした")
            return False

        print(f"VPC ID を検出: {vpc_id}")
        print(f"サブネット ID を検出: {subnet_ids}")
        print(f"DB セキュリティグループ ID を検出: {db_security_group_ids}")

        # Lambda 用のセキュリティグループを作成
        lambda_sg_name = f"lambda-{cluster_name}-sg"

        # セキュリティグループが既に存在するか確認
        existing_sgs = ec2.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': [lambda_sg_name]},
                {'Name': 'vpc-id', 'Values': [vpc_id]}
            ]
        )
        
        if existing_sgs['SecurityGroups']:
            lambda_sg_id = existing_sgs['SecurityGroups'][0]['GroupId']
            print(f"既存の Lambda セキュリティグループを使用: {lambda_sg_id}")
        else:
            # 新しいセキュリティグループを作成
            lambda_sg_response = ec2.create_security_group(
                GroupName=lambda_sg_name,
                Description=f"Security group for Lambda functions accessing {cluster_name}",
                VpcId=vpc_id
            )
            lambda_sg_id = lambda_sg_response['GroupId']

            # アウトバウンドルールが既に存在するか確認
            try:
                # 既存のルールを取得
                sg_rules = ec2.describe_security_group_rules(
                    Filters=[{
                        'Name': 'group-id',
                        'Values': [lambda_sg_id]
                    }, {
                        'Name': 'egress',
                        'Values': ['true']
                    }]
                )

                # ルールが既に存在するか確認
                rule_exists = False
                for rule in sg_rules.get('SecurityGroupRules', []):
                    if rule.get('IpProtocol') == '-1' and rule.get('CidrIpv4') == '0.0.0.0/0':
                        rule_exists = True
                        break
                
                # 存在しない場合はアウトバウンドルールを追加
                if not rule_exists:
                    ec2.authorize_security_group_egress(
                        GroupId=lambda_sg_id,
                        IpPermissions=[{
                            'IpProtocol': '-1',
                            'FromPort': -1,
                            'ToPort': -1,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        }]
                    )
                    print(f"Lambda セキュリティグループ {lambda_sg_id} にアウトバウンドルールを追加しました")
                else:
                    print(f"Lambda セキュリティグループ {lambda_sg_id} にアウトバウンドルールは既に存在します")
            except Exception as e:
                print(f"警告: Lambda セキュリティグループにアウトバウンドルールを追加できませんでした: {str(e)}")
                # デフォルトのアウトバウンドルールは通常許可されているため続行

            print(f"Lambda セキュリティグループを作成しました: {lambda_sg_id}")
        
        # Lambda からのインバウンドを許可するよう DB セキュリティグループを更新
        for db_sg_id in db_security_group_ids:
            try:
                # セキュリティグループを取得してルールが既に存在するか確認
                sg_response = ec2.describe_security_groups(
                    GroupIds=[db_sg_id]
                )

                # Lambda セキュリティグループが既にルールで参照されているか確認
                rule_exists = False
                if sg_response['SecurityGroups']:
                    for rule in sg_response['SecurityGroups'][0].get('IpPermissions', []):
                        for group_pair in rule.get('UserIdGroupPairs', []):
                            if group_pair.get('GroupId') == lambda_sg_id and rule.get('IpProtocol') == 'tcp' and rule.get('FromPort') == 5432:
                                rule_exists = True
                                break

                if not rule_exists:
                    ec2.authorize_security_group_ingress(
                        GroupId=db_sg_id,
                        IpPermissions=[{
                            'IpProtocol': 'tcp',
                            'FromPort': 5432,
                            'ToPort': 5432,
                            'UserIdGroupPairs': [{'GroupId': lambda_sg_id}]
                        }]
                    )
                    print(f"DB セキュリティグループ {db_sg_id} に Lambda セキュリティグループ {lambda_sg_id} からのアクセスを許可するインバウンドルールを追加しました")
                else:
                    print(f"DB セキュリティグループ {db_sg_id} には Lambda セキュリティグループ {lambda_sg_id} のインバウンドルールが既に存在します")
            except Exception as e:
                print(f"警告: DB セキュリティグループ {db_sg_id} を更新できませんでした: {str(e)}")
        
        # VPC 設定をファイルに保存
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        os.makedirs(config_dir, exist_ok=True)
        
        with open(os.path.join(config_dir, "vpc_config.env"), "w") as f:
            f.write(f"export VPC_ID={vpc_id}\n")
            f.write(f"export SUBNET_IDS={','.join(subnet_ids)}\n")
            f.write(f"export LAMBDA_SECURITY_GROUP_ID={lambda_sg_id}\n")
            f.write(f"export DB_SECURITY_GROUP_IDS={','.join(db_security_group_ids)}\n")
        
        return True
        
    except Exception as e:
        print(f"VPC 設定の取得中にエラー: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get VPC configuration for a database cluster")
    parser.add_argument("--cluster-name", required=True, help="RDS/Aurora cluster name")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    
    args = parser.parse_args()
    
    success = get_vpc_config(args.cluster_name, args.region)
    
    if not success:
        sys.exit(1)