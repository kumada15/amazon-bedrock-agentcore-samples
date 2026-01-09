#!/bin/bash
set -e

# Function to find secret ARN by name
find_secret_arn() {
    local SECRET_NAME=$1
    local REGION=$2
    echo "シークレットの ARN を検索中: $SECRET_NAME"
    
    # Try to find the secret ARN
    echo "リージョン $REGION のすべてのシークレットを一覧表示中..."
    ALL_SECRETS=$(aws secretsmanager list-secrets \
        --region "$REGION" \
        --output json)
    
    echo "名前でシークレットを検索中..."
    # Extract all secret names and ARNs for debugging
    echo "利用可能なシークレット:"
    echo "$ALL_SECRETS" | jq -r '.SecretList[] | "Name: " + .Name + ", ARN: " + .ARN' | head -5
    echo "... (他にもある可能性があります)"
    
    # Find the secret by name (exact match)
    SECRET_ARN=$(echo "$ALL_SECRETS" | jq -r --arg NAME "$SECRET_NAME" '.SecretList[] | select(.Name == $NAME) | .ARN')
    
    if [ -z "$SECRET_ARN" ]; then
        echo "完全一致が見つかりません。部分一致を試行中..."
        # Try partial match
        SECRET_ARN=$(echo "$ALL_SECRETS" | jq -r --arg NAME "$SECRET_NAME" '.SecretList[] | select(.Name | contains($NAME)) | .ARN' | head -1)
    fi
    
    if [ -z "$SECRET_ARN" ]; then
        echo "名前で見つかりませんでした。ARN パターンで検索中..."
        # Try to construct the ARN pattern
        ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
        if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
            echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
            echo "エラー: $ACCOUNT_ID"
            exit 1
        fi

        REGION_NAME=$REGION
        
        # Construct a potential ARN
        POTENTIAL_ARN="arn:aws:secretsmanager:$REGION_NAME:$ACCOUNT_ID:secret:$SECRET_NAME"
        echo "候補 ARN を試行中: $POTENTIAL_ARN"
        
        # Try to access the secret directly with this ARN
        if aws secretsmanager describe-secret --secret-id "$POTENTIAL_ARN" --region "$REGION" 2>/dev/null; then
            SECRET_ARN="$POTENTIAL_ARN"
            echo "構築した ARN でシークレットにアクセスできました"
        else
            echo "構築した ARN でシークレットにアクセスできませんでした"
        fi
    fi
    
    if [ ! -z "$SECRET_ARN" ]; then
        echo "シークレット ARN が見つかりました: $SECRET_ARN"
        echo "$SECRET_ARN"
        return 0
    else
        echo "シークレットの ARN が見つかりませんでした: $SECRET_NAME"

        # As a last resort, try to use the secret name directly
        echo "フォールバックとしてシークレット名を直接使用してみます..."
        if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$REGION" 2>/dev/null; then
            echo "シークレット名を直接使用してアクセスできました"
            echo "$SECRET_NAME"
            return 0
        fi

        return 1
    fi
}

# Function to process a secret using its ARN
process_secret_by_arn() {
    local SECRET_ARN=$1
    local REGION=$2
    local CLUSTER_NAME=$3
    local ENVIRONMENT=$4
    local TEST_CONNECTION=$5
    local USE_EXISTING_DIRECTLY=$6
    
    echo "シークレット ARN を使用してデータベースアクセスをセットアップ中: $SECRET_ARN"

    # Get the secret value
    echo "ARN からシークレット値を取得中..."
    SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --region "$REGION" --query "SecretString" --output text)
    
    if [ -z "$SECRET_VALUE" ]; then
        echo "エラー: ARN からシークレット値を取得できませんでした"
        return 1
    fi
    
    # Parse the secret value
    USERNAME=$(echo "$SECRET_VALUE" | jq -r '.username')
    PASSWORD=$(echo "$SECRET_VALUE" | jq -r '.password')
    
    # Check if host, port, and dbname are available in the secret
    HOST=$(echo "$SECRET_VALUE" | jq -r '.host')
    PORT=$(echo "$SECRET_VALUE" | jq -r '.port')
    DBNAME=$(echo "$SECRET_VALUE" | jq -r '.dbname')
    
    # If host is null or empty, get it from the RDS API
    if [ "$HOST" = "null" ] || [ -z "$HOST" ]; then
        echo "シークレットにホストが見つかりません。RDS API から取得中..."
        HOST=$(aws rds describe-db-clusters \
            --db-cluster-identifier "$CLUSTER_NAME" \
            --query "DBClusters[0].Endpoint" \
            --output text \
            --region "$REGION" 2>/dev/null || echo "")
        echo "RDS API からホストを取得しました: $HOST"
    fi

    # If port is null or empty, get it from the RDS API
    if [ "$PORT" = "null" ] || [ -z "$PORT" ]; then
        echo "シークレットにポートが見つかりません。RDS API から取得中..."
        PORT=$(aws rds describe-db-clusters \
            --db-cluster-identifier "$CLUSTER_NAME" \
            --query "DBClusters[0].Port" \
            --output text \
            --region "$REGION" 2>/dev/null || echo "5432")
        echo "RDS API からポートを取得しました: $PORT"
    fi

    # If dbname is null or empty, get it from the RDS API or use default
    if [ "$DBNAME" = "null" ] || [ -z "$DBNAME" ]; then
        echo "シークレットにデータベース名が見つかりません。RDS API から取得中..."
        DBNAME=$(aws rds describe-db-clusters \
            --db-cluster-identifier "$CLUSTER_NAME" \
            --query "DBClusters[0].DatabaseName" \
            --output text \
            --region "$REGION" 2>/dev/null || echo "postgres")
        
        # If still null or empty, use default
        if [ "$DBNAME" = "null" ] || [ -z "$DBNAME" ]; then
            DBNAME="postgres"
            echo "デフォルトのデータベース名を使用します: $DBNAME"
        else
            echo "RDS API からデータベース名を取得しました: $DBNAME"
        fi
    fi
    
    if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ]; then
        echo "エラー: シークレットに必要なフィールド (username, password) が含まれていません"
        return 1
    fi

    echo "シークレットからデータベース認証情報を正常に取得しました"
    echo "ホスト: $HOST"
    echo "ポート: $PORT"
    echo "データベース: $DBNAME"
    echo "ユーザー名: $USERNAME"
    
    # Determine whether to create a new secret or use the existing one directly
    if [ "$USE_EXISTING_DIRECTLY" = true ]; then
        # Get the secret name from ARN
        SECRET_NAME=$(echo "$SECRET_ARN" | awk -F':' '{print $NF}')
        echo "既存のシークレットを直接使用します: $SECRET_NAME"
    else
        # Create a new secret with a simple name
        SECRET_NAME="db-performance-analyzer-$ENVIRONMENT-$(date +%s)"
        echo "新しいシークレットを作成中: $SECRET_NAME"
        
        # Create the secret
        aws secretsmanager create-secret \
            --name "$SECRET_NAME" \
            --description "Database credentials for $CLUSTER_NAME in $ENVIRONMENT environment" \
            --secret-string "{\"host\":\"$HOST\",\"port\":$PORT,\"dbname\":\"$DBNAME\",\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
            --region "$REGION"
    fi
    
    # Store secret name in SSM Parameter Store
    SSM_PARAMETER_NAME="/AuroraOps/$ENVIRONMENT"
    echo "シークレット名を SSM Parameter Store に保存中: $SSM_PARAMETER_NAME"
    aws ssm put-parameter \
        --name "$SSM_PARAMETER_NAME" \
        --value "$SECRET_NAME" \
        --type "String" \
        --overwrite \
        --region "$REGION"
    
    # Save to config file
    echo "設定をファイルに保存中: config/db_${ENVIRONMENT}_config.env"
    cat > "config/db_${ENVIRONMENT}_config.env" << EOF
export DB_CLUSTER_NAME=$CLUSTER_NAME
# DB_SECRET_NAME stored securely in SSM Parameter Store: $SSM_PARAMETER_NAME
export DB_SSM_PARAMETER=$SSM_PARAMETER_NAME
export DB_ENDPOINT=$HOST
export DB_PORT=$PORT
export DB_NAME=$DBNAME
EOF
    
    # Test connection if requested
    if [ "$TEST_CONNECTION" = true ]; then
        echo "データベース接続をテスト中..."
        
        # Check if psycopg2 is installed
        if python3 -c "import psycopg2" 2>/dev/null; then
            # Create a temporary Python script to test the connection
            TEMP_SCRIPT=$(mktemp)
            cat > "$TEMP_SCRIPT" << 'EOF'
#!/usr/bin/env python3
import sys
import json
import psycopg2

# Get connection parameters from command line
host = sys.argv[1]
port = sys.argv[2]
dbname = sys.argv[3]
username = sys.argv[4]
password = sys.argv[5]

try:
    print(f"Connecting to {host}:{port}/{dbname} as {username}...")
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=username,
        password=password,
        connect_timeout=10
    )
    
    # Execute a simple query
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        result = cur.fetchone()
        if result and result[0] == 1:
            print("Database connection successful!")
        else:
            print("Database connection test returned unexpected result")
            sys.exit(1)
    
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"Error connecting to database: {str(e)}")
    sys.exit(1)
EOF
            
            # Make the script executable
            chmod +x "$TEMP_SCRIPT"
            
            # Run the script
            python3 "$TEMP_SCRIPT" "$HOST" "$PORT" "$DBNAME" "$USERNAME" "$PASSWORD"
            RESULT=$?
            
            # Remove the temporary script
            rm "$TEMP_SCRIPT"
            
            if [ $RESULT -ne 0 ]; then
                echo "エラー: データベース接続テストに失敗しました"
                return 1
            fi
        else
            echo "警告: psycopg2 がインストールされていません。接続テストをスキップします"
        fi
    fi
    
    return 0
}

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "仮想環境を作成中..."
    python3 -m venv venv
    source venv/bin/activate
    pip install boto3
else
    source venv/bin/activate
fi

# Parse command line arguments
CLUSTER_NAME=""
ENVIRONMENT=""
USERNAME=""
PASSWORD=""
EXISTING_SECRET=""
SECRET_ARN=""
REGION="us-west-2"
TEST_CONNECTION=false
VERIFY_ONLY=""
NON_INTERACTIVE=false
USE_EXISTING_DIRECTLY=false
CREATE_NEW_SECRET=false
SKIP_SECRET_DETECTION=false
DB_HOST=""
DB_PORT="5432"
DB_NAME="postgres"

print_usage() {
    echo "Usage: $0 --cluster-name <cluster_name> --environment <prod|dev> [--username <username>] [--existing-secret <secret_name>] [--secret-arn <secret_arn>] [--region <region>] [--test-connection] [--verify-only <secret_name>] [--non-interactive] [--use-existing-directly] [--create-new-secret] [--skip-secret-detection] [--db-host <hostname>] [--db-port <port>] [--db-name <dbname>]"
    echo ""
    echo "Options:"
    echo "  --cluster-name          RDS/Aurora cluster name"
    echo "  --environment           Environment (prod or dev)"
    echo "  --username              Database username (if not using existing secret)"
    echo "  --existing-secret       Name of existing secret in AWS Secrets Manager"
    echo "  --secret-arn            ARN of existing secret in AWS Secrets Manager (preferred over name)"
    echo "  --region                AWS region (default: us-west-2)"
    echo "  --test-connection       Test database connection after setup"
    echo "  --verify-only           Only verify an existing secret without creating a new one"
    echo "  --non-interactive       Run in non-interactive mode (no prompts)"
    echo "  --use-existing-directly Use existing secret directly without creating a new one"
    echo "  --create-new-secret     Always create a new secret even when using an existing one as source"
    echo "  --skip-secret-detection Skip automatic secret detection and use manual credentials"
    echo "  --db-host               Database hostname (when using manual credentials)"
    echo "  --db-port               Database port (default: 5432, when using manual credentials)"
    echo "  --db-name               Database name (default: postgres, when using manual credentials)"
    echo ""
    echo "Note: If --existing-secret is not provided, the script will try to find the secret"
    echo "      associated with the database cluster. If not found, it will prompt for credentials."
    echo ""
    echo "Helper scripts:"
    echo "  ./scripts/find_db_secret.py --cluster-name <cluster_name>  # Find secret associated with a cluster"
    echo "  ./scripts/list_secrets.sh [--filter <filter_text>]         # List all available secrets"
}

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --cluster-name)
            CLUSTER_NAME="$2"
            shift
            shift
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift
            shift
            ;;
        --username)
            USERNAME="$2"
            shift
            shift
            ;;
        --existing-secret)
            EXISTING_SECRET="$2"
            shift
            shift
            ;;
        --secret-arn)
            SECRET_ARN="$2"
            shift
            shift
            ;;
        --region)
            REGION="$2"
            shift
            shift
            ;;
        --test-connection)
            TEST_CONNECTION=true
            shift
            ;;
        --verify-only)
            VERIFY_ONLY="$2"
            shift
            shift
            ;;
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --use-existing-directly)
            USE_EXISTING_DIRECTLY=true
            shift
            ;;
        --create-new-secret)
            CREATE_NEW_SECRET=true
            shift
            ;;
        --skip-secret-detection)
            SKIP_SECRET_DETECTION=true
            shift
            ;;
        --db-host)
            DB_HOST="$2"
            shift
            shift
            ;;
        --db-port)
            DB_PORT="$2"
            shift
            shift
            ;;
        --db-name)
            DB_NAME="$2"
            shift
            shift
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            echo "不明なオプション: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Handle verify-only mode
if [ ! -z "$VERIFY_ONLY" ]; then
    echo "シークレット $VERIFY_ONLY を検証中..."
    TEST_CONNECTION_ARG=""
    if [ "$TEST_CONNECTION" = true ]; then
        TEST_CONNECTION_ARG="--test-connection"
    fi
    
    python3 scripts/setup_database_access.py \
        --verify-only "$VERIFY_ONLY" \
        --region "$REGION" \
        $TEST_CONNECTION_ARG
    
    exit $?
fi

# Validate required parameters
if [ -z "$CLUSTER_NAME" ] || [ -z "$ENVIRONMENT" ]; then
    echo "エラー: 必須パラメータが不足しています"
    print_usage
    exit 1
fi

# Validate environment
if [ "$ENVIRONMENT" != "prod" ] && [ "$ENVIRONMENT" != "dev" ]; then
    echo "エラー: environment は 'prod' または 'dev' のいずれかである必要があります"
    print_usage
    exit 1
fi

# Create config directory if it doesn't exist
mkdir -p config

# Check for existing secret or try to find one based on cluster name
if [ -z "$EXISTING_SECRET" ] && [ -z "$SECRET_ARN" ] && [ "$SKIP_SECRET_DETECTION" != true ]; then
    # First, try to find the secret directly associated with the cluster using RDS API
    echo "クラスター $CLUSTER_NAME に直接関連付けられたシークレットを検索中..."
    
    # Check if Python is available
    if command -v python3 &> /dev/null; then
        # Create a temporary Python script to find the associated secret
        TEMP_SCRIPT=$(mktemp)
        cat > "$TEMP_SCRIPT" << 'EOF'
#!/usr/bin/env python3
import boto3
import sys
import json

def find_db_secret(cluster_name, region):
    # Initialize AWS clients
    rds = boto3.client('rds', region_name=region)
    
    try:
        # Get cluster information
        response = rds.describe_db_clusters(DBClusterIdentifier=cluster_name)
        
        if not response['DBClusters']:
            print(f"Error: Cluster {cluster_name} not found", file=sys.stderr)
            return None
        
        cluster = response['DBClusters'][0]
        
        # Check if the cluster has a master username secret
        if 'MasterUserSecret' in cluster:
            secret_arn = cluster['MasterUserSecret'].get('SecretArn')
            if secret_arn:
                # Extract secret name from ARN
                secret_name = secret_arn.split(':')[-1]
                print(f"FOUND_SECRET:{secret_name}")
                return secret_name
        
        # If no master user secret, check for associated secrets
        # Get all DB instances in the cluster
        instances_response = rds.describe_db_instances(
            Filters=[{'Name': 'db-cluster-id', 'Values': [cluster_name]}]
        )
        
        for instance in instances_response.get('DBInstances', []):
            instance_id = instance['DBInstanceIdentifier']
            
            # Check for master user secret at instance level
            if 'MasterUserSecret' in instance:
                secret_arn = instance['MasterUserSecret'].get('SecretArn')
                if secret_arn:
                    # Extract secret name from ARN
                    secret_name = secret_arn.split(':')[-1]
                    print(f"FOUND_SECRET:{secret_name}")
                    return secret_name
        
        return None
        
    except Exception as e:
        print(f"Error finding secret for cluster: {str(e)}", file=sys.stderr)
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: script.py <cluster_name> <region>", file=sys.stderr)
        sys.exit(1)
    
    cluster_name = sys.argv[1]
    region = sys.argv[2]
    
    find_db_secret(cluster_name, region)
EOF
        
        # Make the script executable
        chmod +x "$TEMP_SCRIPT"
        
        # Run the script to find the associated secret
        ASSOCIATED_SECRET=$(python3 "$TEMP_SCRIPT" "$CLUSTER_NAME" "$REGION" | grep "FOUND_SECRET:" | cut -d':' -f2 || echo "")
        
        # Remove the temporary script
        rm "$TEMP_SCRIPT"
        
        if [ ! -z "$ASSOCIATED_SECRET" ]; then
            echo "クラスターに直接関連付けられたシークレットが見つかりました: $ASSOCIATED_SECRET"

            # Get the secret ARN directly from RDS API
            echo "RDS API からシークレット ARN を直接取得中..."
            RDS_SECRET_ARN=$(aws rds describe-db-clusters \
                --db-cluster-identifier "$CLUSTER_NAME" \
                --query "DBClusters[0].MasterUserSecret.SecretArn" \
                --output text \
                --region "$REGION" 2>/dev/null || echo "")
            
            if [ "$RDS_SECRET_ARN" != "None" ] && [ ! -z "$RDS_SECRET_ARN" ]; then
                echo "RDS API からシークレット ARN を直接取得しました: $RDS_SECRET_ARN"
                SECRET_ARN="$RDS_SECRET_ARN"
                
                # Process the secret using its ARN
                process_secret_by_arn "$SECRET_ARN" "$REGION" "$CLUSTER_NAME" "$ENVIRONMENT" "$TEST_CONNECTION" "$USE_EXISTING_DIRECTLY" || exit 1
                exit 0
            else
                echo "RDS API からシークレット ARN を取得できませんでした。名前に特殊文字が含まれているか確認中..."

                # Check if the secret name contains special characters
                if [[ "$ASSOCIATED_SECRET" == *[!@#\$%^\&*\(\)\+]* ]]; then
                    echo "シークレット名に特殊文字が含まれています。ARN を検索中..."
                    SECRET_ARN=$(find_secret_arn "$ASSOCIATED_SECRET" "$REGION")
                    
                    if [ ! -z "$SECRET_ARN" ]; then
                        # Process the secret using its ARN
                        process_secret_by_arn "$SECRET_ARN" "$REGION" "$CLUSTER_NAME" "$ENVIRONMENT" "$TEST_CONNECTION" "$USE_EXISTING_DIRECTLY" || exit 1
                        exit 0
                    else
                        echo "シークレットの ARN が見つかりませんでした: $ASSOCIATED_SECRET"
                        echo "名前を直接使用してみます..."
                    fi
                fi
            fi
            
            EXISTING_SECRET="$ASSOCIATED_SECRET"
        else
            echo "クラスターに直接関連付けられたシークレットが見つかりませんでした。"

            # Try to find secrets by name matching
            echo "名前が一致するシークレットを検索中..."
            # First try exact match
            POTENTIAL_SECRETS=$(aws secretsmanager list-secrets \
                --filters Key=name,Values="$CLUSTER_NAME" \
                --query "SecretList[].Name" \
                --output text \
                --region "$REGION" 2>/dev/null || echo "")
            
            # If no exact matches, try a broader search
            if [ -z "$POTENTIAL_SECRETS" ]; then
                echo "完全一致が見つかりません。クラスター名を含むシークレットを検索中..."
                # List all secrets and filter with grep
                ALL_SECRETS=$(aws secretsmanager list-secrets \
                    --query "SecretList[].Name" \
                    --output text \
                    --region "$REGION" 2>/dev/null || echo "")
                
                # Filter secrets containing the cluster name (case insensitive)
                POTENTIAL_SECRETS=$(echo "$ALL_SECRETS" | grep -i "$CLUSTER_NAME" || echo "")
                
                # If still no matches, try to list all RDS related secrets
                if [ -z "$POTENTIAL_SECRETS" ]; then
                    echo "クラスター名を含むシークレットが見つかりません。すべての RDS/Aurora 関連シークレットを一覧表示中..."
                    POTENTIAL_SECRETS=$(echo "$ALL_SECRETS" | grep -i "\(rds\|aurora\|postgres\|database\|db\)" | head -10 || echo "")

                    # If still no matches, we'll prompt for credentials later
                    if [ -z "$POTENTIAL_SECRETS" ]; then
                        echo "データベース関連のシークレットが見つかりませんでした。"
                        echo "代わりに認証情報の入力を求めます。"
                    fi
                fi
            fi
            
            # If we found potential secrets, ask user to select one
            if [ ! -z "$POTENTIAL_SECRETS" ]; then
                # Found potential secrets, ask user to select one
                echo "このクラスターの候補シークレットが見つかりました:"
                SECRET_ARRAY=()
                i=1
                while read -r secret; do
                    if [ ! -z "$secret" ]; then
                        echo "$i) $secret"
                        SECRET_ARRAY[i]="$secret"
                        i=$((i+1))
                    fi
                done <<< "$POTENTIAL_SECRETS"
                
                echo "$i) 上記のいずれでもない（手動で認証情報を入力）"

                # Ask user to select a secret
                read -p "使用するシークレットを選択してください [1-$i]: " SECRET_CHOICE

                if [[ $SECRET_CHOICE -ge 1 && $SECRET_CHOICE -lt $i ]]; then
                    EXISTING_SECRET=${SECRET_ARRAY[$SECRET_CHOICE]}
                    echo "既存のシークレットを使用します: $EXISTING_SECRET"
                else
                    echo "代わりに認証情報の入力を求めます。"
                fi
            fi
        fi
    else
        echo "Python が見つかりません。名前ベースの検索にフォールバックします..."
        # First try exact match
        POTENTIAL_SECRETS=$(aws secretsmanager list-secrets \
            --filters Key=name,Values="$CLUSTER_NAME" \
            --query "SecretList[].Name" \
            --output text \
            --region "$REGION" 2>/dev/null || echo "")
        
        # If no exact matches, try a broader search
        if [ -z "$POTENTIAL_SECRETS" ]; then
            echo "完全一致が見つかりません。クラスター名を含むシークレットを検索中..."
            # List all secrets and filter with grep
            ALL_SECRETS=$(aws secretsmanager list-secrets \
                --query "SecretList[].Name" \
                --output text \
                --region "$REGION" 2>/dev/null || echo "")
            
            # Filter secrets containing the cluster name (case insensitive)
            POTENTIAL_SECRETS=$(echo "$ALL_SECRETS" | grep -i "$CLUSTER_NAME" || echo "")
            
            # If still no matches, try to list all RDS related secrets
            if [ -z "$POTENTIAL_SECRETS" ]; then
                echo "クラスター名を含む一致が見つかりません。すべての RDS/Aurora 関連シークレットを一覧表示中..."
                POTENTIAL_SECRETS=$(echo "$ALL_SECRETS" | grep -i "\(rds\|aurora\|postgres\|database\|db\)" | head -10 || echo "")

                # If still no matches, we'll prompt for credentials later
                if [ -z "$POTENTIAL_SECRETS" ]; then
                    echo "データベース関連のシークレットが見つかりませんでした。"
                    echo "代わりに認証情報の入力を求めます。"
                fi
            fi
        fi

        # If we found potential secrets, ask user to select one
        if [ ! -z "$POTENTIAL_SECRETS" ]; then
            # Found potential secrets, ask user to select one
            echo "このクラスターの候補シークレットが見つかりました:"
            SECRET_ARRAY=()
            i=1
            while read -r secret; do
                if [ ! -z "$secret" ]; then
                    echo "$i) $secret"
                    SECRET_ARRAY[i]="$secret"
                    i=$((i+1))
                fi
            done <<< "$POTENTIAL_SECRETS"

            echo "$i) 上記のいずれでもない（手動で認証情報を入力）"

            # Ask user to select a secret
            read -p "使用するシークレットを選択してください [1-$i]: " SECRET_CHOICE

            if [[ $SECRET_CHOICE -ge 1 && $SECRET_CHOICE -lt $i ]]; then
                EXISTING_SECRET=${SECRET_ARRAY[$SECRET_CHOICE]}
                echo "既存のシークレットを使用します: $EXISTING_SECRET"
            else
                echo "代わりに認証情報の入力を求めます。"
            fi
        fi
    fi
fi

# If we have a secret ARN, use it directly
if [ ! -z "$SECRET_ARN" ]; then
    process_secret_by_arn "$SECRET_ARN" "$REGION" "$CLUSTER_NAME" "$ENVIRONMENT" "$TEST_CONNECTION" "$USE_EXISTING_DIRECTLY" || exit 1
    
# If we have an existing secret by name, use it
elif [ ! -z "$EXISTING_SECRET" ]; then
    echo "既存のシークレットを使用してデータベースアクセスをセットアップ中: $EXISTING_SECRET"

    # Check if the secret name contains special characters
    if [[ "$EXISTING_SECRET" == *[!@#\$%^\&*\(\)\+]* ]]; then
        echo "シークレット名に特殊文字が含まれています。ARN を検索中..."
        
        # Try to find the secret ARN
        SECRET_ARN=$(find_secret_arn "$EXISTING_SECRET" "$REGION")
        
        if [ ! -z "$SECRET_ARN" ]; then
            # Process the secret using its ARN
            process_secret_by_arn "$SECRET_ARN" "$REGION" "$CLUSTER_NAME" "$ENVIRONMENT" "$TEST_CONNECTION" "$USE_EXISTING_DIRECTLY" || exit 1
        else
            echo "シークレットの ARN が見つかりませんでした: $EXISTING_SECRET"
            echo "標準メソッドにフォールバックします..."
        fi
    fi
    
    # If we didn't process by ARN, use the standard method
    if [ -z "$SECRET_ARN" ]; then
        # Add flags if needed
        ADDITIONAL_ARGS=""
        if [ "$TEST_CONNECTION" = true ]; then
            ADDITIONAL_ARGS="$ADDITIONAL_ARGS --test-connection"
        fi
        if [ "$NON_INTERACTIVE" = true ]; then
            ADDITIONAL_ARGS="$ADDITIONAL_ARGS --non-interactive"
        fi
        if [ "$USE_EXISTING_DIRECTLY" = true ]; then
            ADDITIONAL_ARGS="$ADDITIONAL_ARGS --use-existing-directly"
        fi
        if [ "$CREATE_NEW_SECRET" = true ]; then
            ADDITIONAL_ARGS="$ADDITIONAL_ARGS --create-new-secret"
        fi
        
        python3 scripts/setup_database_access.py \
            --cluster-name "$CLUSTER_NAME" \
            --environment "$ENVIRONMENT" \
            --existing-secret "$EXISTING_SECRET" \
            --region "$REGION" \
            $ADDITIONAL_ARGS
    fi
elif [ ! -z "$DB_HOST" ]; then
    # Use manual database configuration
    echo "手動設定を使用してデータベースアクセスをセットアップ中..."

    # Prompt for username if not provided
    if [ -z "$USERNAME" ]; then
        read -p "データベースユーザー名を入力してください: " USERNAME
    fi

    # Always prompt for password (never pass as command line argument)
    read -s -p "データベースパスワードを入力してください: " PASSWORD
    echo ""

    echo "ホスト: $DB_HOST、ポート: $DB_PORT、データベース: $DB_NAME でデータベースアクセスをセットアップ中"
    
    # Create a temporary config file
    CONFIG_FILE=$(mktemp)
    cat > "$CONFIG_FILE" << EOF
{
    "host": "$DB_HOST",
    "port": $DB_PORT,
    "dbname": "$DB_NAME",
    "username": "$USERNAME",
    "password": "$PASSWORD"
}
EOF
    
    # Create a secret with the manual configuration
    SECRET_NAME="db-performance-analyzer-$ENVIRONMENT-manual-$(date +%s)"
    aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --description "Manual database configuration for $CLUSTER_NAME in $ENVIRONMENT environment" \
        --secret-string file://$CONFIG_FILE \
        --region "$REGION"
    
    # Remove the temporary config file
    rm "$CONFIG_FILE"

    echo "シークレットを作成しました: $SECRET_NAME"
    
    # Add flags if needed
    ADDITIONAL_ARGS=""
    if [ "$TEST_CONNECTION" = true ]; then
        ADDITIONAL_ARGS="$ADDITIONAL_ARGS --test-connection"
    fi
    if [ "$NON_INTERACTIVE" = true ]; then
        ADDITIONAL_ARGS="$ADDITIONAL_ARGS --non-interactive"
    fi
    if [ "$USE_EXISTING_DIRECTLY" = true ]; then
        ADDITIONAL_ARGS="$ADDITIONAL_ARGS --use-existing-directly"
    fi
    
    python3 scripts/setup_database_access.py \
        --cluster-name "$CLUSTER_NAME" \
        --environment "$ENVIRONMENT" \
        --existing-secret "$SECRET_NAME" \
        --region "$REGION" \
        $ADDITIONAL_ARGS
else
    # Otherwise prompt for credentials if needed
    if [ -z "$USERNAME" ]; then
        read -p "データベースユーザー名を入力してください: " USERNAME
    fi

    # Always prompt for password (never pass as command line argument)
    read -s -p "データベースパスワードを入力してください: " PASSWORD
    echo ""

    echo "データベースアクセスをセットアップ中..."
    
    # Add flags if needed
    ADDITIONAL_ARGS=""
    if [ "$TEST_CONNECTION" = true ]; then
        ADDITIONAL_ARGS="$ADDITIONAL_ARGS --test-connection"
    fi
    if [ "$NON_INTERACTIVE" = true ]; then
        ADDITIONAL_ARGS="$ADDITIONAL_ARGS --non-interactive"
    fi
    
    python3 scripts/setup_database_access.py \
        --cluster-name "$CLUSTER_NAME" \
        --environment "$ENVIRONMENT" \
        --username "$USERNAME" \
        --password "$PASSWORD" \
        --region "$REGION" \
        $ADDITIONAL_ARGS
fi

# Deactivate virtual environment
deactivate

echo "データベースセットアップ完了！"