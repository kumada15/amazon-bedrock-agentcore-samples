#!/usr/bin/env python3
import boto3
import json
import argparse
import uuid
import sys

def verify_secret(secret_name, region='us-west-2', test_connection=True):
    """
    シークレットが存在し、必要なフィールドを含んでいることを確認する

    Args:
        secret_name: 検証するシークレット名
        region: AWS リージョン
        test_connection: データベース接続をテストするかどうか

    Returns:
        bool: 検証に成功した場合は True、失敗した場合は False
    """
    secretsmanager = boto3.client('secretsmanager', region_name=region)
    try:
        # 特殊文字を含む場合は最初に ARN で試行
        try:
            # 特殊文字を含む場合は ARN を検索するためにシークレットを一覧表示
            if any(c in secret_name for c in ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+']):
                print(f"シークレット名に特殊文字が含まれています。ARN を検索中...")
                list_response = secretsmanager.list_secrets(
                    Filters=[
                        {
                            'Key': 'name',
                            'Values': [secret_name]
                        },
                    ]
                )
                
                if list_response['SecretList']:
                    secret_arn = list_response['SecretList'][0]['ARN']
                    print(f"シークレットを検出")
                    response = secretsmanager.get_secret_value(SecretId=secret_arn)
                else:
                    # フォールバックとして名前で直接試行
                    response = secretsmanager.get_secret_value(SecretId=secret_name)
            else:
                # 特殊文字がない場合は名前で直接使用
                response = secretsmanager.get_secret_value(SecretId=secret_name)
        except Exception as e:
            print(f"名前でシークレットにアクセスできませんでした。部分一致で検索中: {str(e)}")
            # すべてのシークレットを一覧表示して部分一致でシークレットを検索
            list_response = secretsmanager.list_secrets()
            found = False
            
            for s in list_response['SecretList']:
                if secret_name in s['Name']:
                    print(f"一致するシークレットを検出")
                    response = secretsmanager.get_secret_value(SecretId=s['ARN'])
                    found = True
                    break
            
            if not found:
                raise Exception(f"{secret_name} に一致するシークレットが見つかりません")
        secret_data = json.loads(response['SecretString'])

        # 必須フィールドを確認
        required_fields = ['host', 'dbname', 'username', 'password', 'port']
        missing_fields = [field for field in required_fields if field not in secret_data]
        
        if missing_fields:
            print(f"警告: シークレットに以下のフィールドがありません: {', '.join(missing_fields)}")
            return False

        # パスワードが空でないことを確認
        if not secret_data['password']:
            print(f"警告: シークレットのパスワードが空です")
            return False

        print(f"シークレットの検証が成功しました")

        # 要求された場合にデータベース接続をテスト
        if test_connection:
            try:
                # 必要な場合のみ psycopg2 をインポート
                import psycopg2
                
                print(f"データベースへの接続をテスト中")
                conn = psycopg2.connect(
                    host=secret_data['host'],
                    database=secret_data['dbname'],
                    user=secret_data['username'],
                    password=secret_data['password'],
                    port=secret_data['port'],
                    connect_timeout=10
                )

                # 接続を確認するための簡単なクエリを実行
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result and result[0] == 1:
                        print("データベース接続に成功しました！")
                    else:
                        print("データベース接続テストで予期しない結果が返されました")
                        return False
                
                conn.close()
                return True
            except ImportError:
                print("警告: psycopg2 がインストールされていません。接続テストをスキップします")
                return True
            except Exception as e:
                print(f"データベース接続エラー: {str(e)}")
                print("シークレットは有効ですが、データベース接続に失敗しました。")
                print("データベースの認証情報とネットワーク接続を確認してください。")
                return False
        
        return True
    except Exception as e:
        print(f"シークレットの検証エラー")
        return False

def setup_database_access(cluster_name, environment, username=None, password=None, existing_secret=None, region='us-west-2'):
    """
    データベースアクセスを設定する
    1. RDS からクラスターエンドポイントを取得
    2. 必要な形式でシークレットを作成
    3. シークレット名を SSM Parameter Store に保存

    Args:
        cluster_name: RDS/Aurora クラスター名
        environment: 環境（prod または dev）
        username: データベースユーザー名
        password: データベースパスワード
        existing_secret: 既存の AWS Secrets Manager シークレット名
        region: AWS リージョン

    Returns:
        bool: 設定に成功した場合は True、失敗した場合は False
    """
    print(f"クラスター {cluster_name} のデータベースアクセスを {environment} 環境で設定中")
    
    # AWS クライアントを初期化
    rds = boto3.client('rds', region_name=region)
    secretsmanager = boto3.client('secretsmanager', region_name=region)
    ssm = boto3.client('ssm', region_name=region)

    try:
        # クラスター情報を取得
        response = rds.describe_db_clusters(DBClusterIdentifier=cluster_name)
        
        if not response['DBClusters']:
            print(f"エラー: クラスター {cluster_name} が見つかりません")
            return False
        
        cluster = response['DBClusters'][0]
        endpoint = cluster['Endpoint']
        port = cluster['Port']

        # データベース名を取得（利用可能な場合はデフォルトを使用、そうでなければ 'postgres' を使用）
        db_name = 'postgres'  # デフォルトのフォールバック
        if 'DatabaseName' in cluster:
            db_name = cluster['DatabaseName']

        # シークレット名と値を決定
        if existing_secret:
            # 既存のシークレットを使用
            secret_name = existing_secret
            print(f"既存のシークレットを使用")
            
            try:
                # 既存のシークレットを取得して存在を確認
                # 特殊文字を含む場合は最初に ARN で試行
                try:
                    # 特殊文字を含む場合は ARN を検索するためにシークレットを一覧表示
                    if any(c in secret_name for c in ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+']):
                        print(f"シークレット名に特殊文字が含まれています。ARN を検索中...")
                        list_response = secretsmanager.list_secrets(
                            Filters=[
                                {
                                    'Key': 'name',
                                    'Values': [secret_name]
                                },
                            ]
                        )
                        
                        if list_response['SecretList']:
                            secret_arn = list_response['SecretList'][0]['ARN']
                            print(f"シークレットを検出")
                            secret_response = secretsmanager.get_secret_value(SecretId=secret_arn)
                        else:
                            # フォールバックとして名前で直接試行
                            secret_response = secretsmanager.get_secret_value(SecretId=secret_name)
                    else:
                        # 特殊文字がない場合は名前で直接使用
                        secret_response = secretsmanager.get_secret_value(SecretId=secret_name)
                except Exception as e:
                    print(f"名前でシークレットにアクセスできませんでした。部分一致で検索中: {str(e)}")
                    # すべてのシークレットを一覧表示して部分一致でシークレットを検索
                    list_response = secretsmanager.list_secrets()
                    found = False
                    
                    for s in list_response['SecretList']:
                        if secret_name in s['Name']:
                            secret_response = secretsmanager.get_secret_value(SecretId=s['ARN'])
                            found = True
                            break
                    
                    if not found:
                        raise Exception(f"{secret_name} に一致するシークレットが見つかりません")
                
                secret_data = json.loads(secret_response['SecretString'])

                # 既存のシークレットから認証情報を抽出
                if 'username' in secret_data and 'password' in secret_data:
                    username = secret_data['username']
                    password = secret_data['password']
                    print(f"既存のシークレットから認証情報を正常に取得しました")
                else:
                    print(f"エラー: 既存のシークレットにユーザー名とパスワードが含まれていません")
                    return False

                # 必要な形式で新しいシークレットを作成
                new_secret_name = f"db-performance-analyzer-{environment}-{uuid.uuid4().hex[:8]}"
                secret_value = {
                    "host": endpoint,
                    "dbname": db_name,
                    "username": username,
                    "password": password,  # 既存のシークレットからのパスワードを使用
                    "port": port
                }

                # 確認を表示（パスワードはマスク）
                print(f"新しいシークレットを作成中 - エンドポイント: {endpoint}, ポート: {port}, データベース: {db_name}")
                print(f"元のシークレットには影響しません")

                # 新しいシークレットを作成するか既存のものを直接使用するかを決定
                # 非対話モードで実行しているか確認
                if '--non-interactive' in sys.argv:
                    if '--use-existing-directly' in sys.argv:
                        print(f"非対話モード: 既存のシークレットを直接使用")
                        new_secret_name = secret_name
                    elif '--create-new-secret' in sys.argv:
                        print(f"非対話モード: 新しいシークレットを作成")
                    else:
                        # 非対話モードのデフォルト動作は新しいシークレットを作成
                        print(f"非対話モード: 新しいシークレットを作成（デフォルト）")
                else:
                    # 対話モード - ユーザーに確認
                    choice = input("選択してください: (1) これらの認証情報で新しいシークレットを作成, (2) 既存のシークレットを直接使用 (1/2): ")

                    if choice == "2":
                        print(f"既存のシークレットを直接使用")
                        # 新しいシークレットを作成する必要はない、既存のものを使用
                        new_secret_name = secret_name
                    elif choice == "1":
                        print(f"新しいシークレットを作成")
                    else:
                        print("無効な選択です。操作をキャンセルしました。")
                        return False

                # 必要な場合に新しいシークレットを作成
                if new_secret_name != secret_name:  # 既存のシークレットを直接使用していない場合のみ作成
                    try:
                        secret_response = secretsmanager.create_secret(
                            Name=new_secret_name,
                            Description=f"Database credentials for {cluster_name} in {environment} environment",
                            SecretString=json.dumps(secret_value)
                        )
                        print(f"新しいシークレットを正常に作成しました")
                    except Exception as e:
                        print(f"新しいシークレットの作成エラー: {str(e)}")
                        return False

                # secret_name を新しいものに更新（または既存のものを維持）
                secret_name = new_secret_name
                
            except secretsmanager.exceptions.ResourceNotFoundException:
                print(f"エラー: シークレットが見つかりません")
                return False
        else:
            # 提供された認証情報で新しいシークレットを作成
            if not username or not password:
                print("エラー: 既存のシークレットを使用しない場合、ユーザー名とパスワードが必要です")
                return False
                
            secret_name = f"db-performance-analyzer-{environment}-{uuid.uuid4().hex[:8]}"
            secret_value = {
                "host": endpoint,
                "dbname": db_name,
                "username": username,
                "password": password,
                "port": port
            }
            
            print(f"シークレットを作成中 - エンドポイント: {endpoint}, ポート: {port}, データベース: {db_name}")

            # シークレットを作成
            secret_response = secretsmanager.create_secret(
                Name=secret_name,
                Description=f"Database credentials for {cluster_name} in {environment} environment",
                SecretString=json.dumps(secret_value)
            )
        
        # シークレットが正しく作成されたことを確認
        if not verify_secret(secret_name, region):
            print(f"エラー: シークレットの検証に失敗しました")
            return False

        # SSM Parameter Store にシークレット名を保存
        ssm_parameter_name = f"/AuroraOps/{environment}"
        ssm.put_parameter(
            Name=ssm_parameter_name,
            Value=secret_name,
            Type="String",
            Overwrite=True
        )
        
        print(f"データベースアクセスの設定が完了しました:")
        print(f"- シークレットを作成しました")
        print(f"- SSM パラメータを作成しました: {ssm_parameter_name}")

        # 設定ファイルに保存
        import os
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, f"db_{environment}_config.env"), "w") as f:
            f.write(f"export DB_CLUSTER_NAME={cluster_name}\n")
            f.write(f"# DB_SECRET_NAME stored securely in SSM Parameter Store: {ssm_parameter_name}\n")
            f.write(f"export DB_SSM_PARAMETER={ssm_parameter_name}\n")
            f.write(f"export DB_ENDPOINT={endpoint}\n")
            f.write(f"export DB_PORT={port}\n")
            f.write(f"export DB_NAME={db_name}\n")
        
        return True
        
    except Exception as e:
        print(f"データベースアクセスの設定エラー: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up database access for DB Performance Analyzer")
    parser.add_argument("--cluster-name", required=True, help="RDS/Aurora cluster name")
    parser.add_argument("--environment", required=True, choices=["prod", "dev"], help="Environment (prod or dev)")
    parser.add_argument("--username", help="Database username")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--existing-secret", help="Name of existing secret in AWS Secrets Manager")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    parser.add_argument("--test-connection", action="store_true", help="Test database connection after setup")
    parser.add_argument("--verify-only", help="Only verify an existing secret without creating a new one")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode (no prompts)")
    parser.add_argument("--use-existing-directly", action="store_true", help="Use existing secret directly without creating a new one")
    parser.add_argument("--create-new-secret", action="store_true", help="Always create a new secret even when using an existing one as source")
    
    args = parser.parse_args()

    # 検証のみモードを処理
    if args.verify_only:
        print(f"シークレット {args.verify_only} を検証中...")
        success = verify_secret(args.verify_only, args.region, args.test_connection)
        sys.exit(0 if success else 1)

    # 引数を検証
    if not args.existing_secret and (not args.username or not args.password):
        parser.error("Either --existing-secret or both --username and --password must be provided")
    
    success = setup_database_access(
        args.cluster_name,
        args.environment,
        args.username,
        args.password,
        args.existing_secret,
        args.region
    )

    # 要求された場合に接続をテスト
    if success and args.test_connection:
        # SSM Parameter Store からシークレット名を取得
        ssm = boto3.client('ssm', region_name=args.region)
        try:
            response = ssm.get_parameter(Name=f"/AuroraOps/{args.environment}")
            secret_name = response['Parameter']['Value']
            print("取得したシークレットを使用してデータベース接続をテスト中")
            verify_secret(secret_name, args.region, True)
        except Exception as e:
            print(f"接続テストエラー: {str(e)}")
            success = False
    
    if not success:
        sys.exit(1)
