# Amazon EKS への Strands エージェントのデプロイ

このサンプルでは、[Strands Agents SDK](https://github.com/strands-agents/sdk-python) で構築した Python アプリケーションを Amazon EKS にデプロイする方法を示します。このサンプルでは、Application Load Balancer を備えた Amazon EKS でコンテナ化されたサービスとして実行される旅行調査エージェントアプリケーションをデプロイします。

アプリケーションは FastAPI で構築されており、提供されたプロンプトに基づいて旅行情報を返す `/travel` エンドポイントを提供します。

## 前提条件

- [AWS CLI](https://aws.amazon.com/cli/) がインストールされ設定済み
- [eksctl](https://eksctl.io/installation/)（v0.208.x 以降）がインストール済み
- [Helm](https://helm.sh/)（v3 以降）がインストール済み
- [kubectl](https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html) がインストール済み
- 以下のいずれか：
    - [Podman](https://podman.io/) がインストールされ実行中
    - （または）[Docker](https://www.docker.com/) がインストールされ実行中
- AWS 環境で Amazon Bedrock Anthropic Claude モデルが有効化済み

## クイックスタート（自動デプロイ）

自動デプロイを利用するには、付属の Jupyter ノートブックを使用してください：

```bash
# このディレクトリに移動
cd strands-travel-agent-eks

# Jupyter を起動
jupyter notebook deploy.ipynb
```

ノートブックは以下を含むデプロイプロセス全体を自動化します：
- CloudWatch ロググループの作成
- EKS クラスターの作成
- Docker イメージのビルドと ECR へのプッシュ
- IAM ポリシーと Pod Identity の設定
- Helm チャートのデプロイ
- ポートフォワーディングとエージェントのテスト

> **注意:** CloudWatch Observability アドオン（ノートブックのセクション 8）は**オプション**です。Bedrock AgentCore Observability には必要ありません。AgentCore は Dockerfile の OTEL 設定を使用して CloudWatch にテレメトリを直接送信します。

**環境変数（オプション）:**

ノートブックを実行する前に以下の環境変数を設定してデプロイをカスタマイズできます：

| 変数 | デフォルト | 説明 |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | デプロイ先の AWS リージョン |
| `CLUSTER_NAME` | `eks-strands-agents-demo` | EKS クラスター名 |
| `SERVICE_NAME` | `strands-agents-travel` | Helm リリースのサービス名 |
| `LOG_GROUP_NAME` | `/strands-agents/travel` | CloudWatch ロググループ |
| `LOG_STREAM_NAME` | `agent-logs` | CloudWatch ログストリーム |
| `METRIC_NAMESPACE` | `StrandsAgents/Travel` | CloudWatch メトリクス名前空間 |
| `LOCAL_PORT` | `8080` | ポートフォワーディング用のローカルポート |

## プロジェクト構成

```
.
├── README.md
├── deploy.ipynb              # 自動デプロイノートブック
├── chart/                    # Kubernetes デプロイ用 Helm チャート
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
└── docker/                   # Docker コンテナファイル
    ├── Dockerfile
    ├── app/
    │   └── app.py           # FastAPI 旅行エージェントアプリケーション
    └── requirements.txt
```

## 手動デプロイ

以下のセクションでは手動デプロイ手順を説明します。自動ノートブックより CLI コマンドを好む場合にこれらを使用してください。

### 設定

Docker イメージをビルドする前に、`docker/Dockerfile` の以下の値を更新してください：

| 変数 | 説明 | 必要なアクション |
|----------|-------------|-----------------|
| `OTEL_RESOURCE_ATTRIBUTES` | AgentCore Observability のサービス名 | `<YOUR_SERVICE_NAME>` をサービス名に置き換え |
| `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | OpenTelemetry オブザーバビリティ設定 | `<YOUR_LOG_GROUP>`、`<YOUR_LOG_STREAM>`、`<YOUR_METRIC_NAMESPACE>` を値に置き換え |

アプリケーションは以下のランタイム環境変数もサポートします（デフォルトは `docker/app/app.py` で設定）：

| 変数 | 説明 | デフォルト |
|----------|-------------|---------|
| `MODEL_ID` | Amazon Bedrock モデル ID | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `MODEL_TEMPERATURE` | レスポンスのモデル温度 | `0` |
| `MODEL_MAX_TOKENS` | レスポンスの最大トークン数 | `1028` |

### EKS Auto Mode クラスターの作成

環境変数を設定：
```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
export AWS_REGION=us-east-1
export CLUSTER_NAME=eks-strands-agents-demo
```

EKS Auto Mode クラスターを作成：
```bash
eksctl create cluster --name $CLUSTER_NAME --enable-auto-mode
```

kubeconfig コンテキストを設定：
```bash
aws eks update-kubeconfig --name $CLUSTER_NAME
```

### Docker イメージのビルドと ECR へのプッシュ

以下の手順で Docker イメージをビルドし、Amazon ECR にプッシュします：

1. Amazon ECR に認証：
```bash
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

2. ECR リポジトリがない場合は作成：
```bash
aws ecr create-repository --repository-name strands-agents-travel --region ${AWS_REGION}
```

3. Docker イメージをビルド：
```bash
docker build --platform linux/amd64 -t strands-agents-travel:latest docker/
```

4. ECR 用にイメージをタグ付け：
```bash
docker tag strands-agents-travel:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel:latest
```

5. イメージを ECR にプッシュ：
```bash
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel:latest
```

### Amazon Bedrock にアクセスするための EKS Pod Identity の設定

すべての Amazon Bedrock モデルへの InvokeModel と InvokeModelWithResponseStream を許可する IAM ポリシーを作成：
```bash
cat > bedrock-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name strands-agents-travel-bedrock-policy \
  --policy-document file://bedrock-policy.json
rm -f bedrock-policy.json
```

EKS Pod Identity アソシエーションを作成：
```bash
eksctl create podidentityassociation --cluster $CLUSTER_NAME \
  --namespace default \
  --service-account-name strands-agents-travel \
  --permission-policy-arns arn:aws:iam::$AWS_ACCOUNT_ID:policy/strands-agents-travel-bedrock-policy \
  --role-name eks-strands-agents-travel
```

### strands-agents-travel アプリケーションのデプロイ

ECR のイメージを使用して Helm チャートをデプロイ：
```bash
helm install strands-agents-travel ./chart \
  --set image.repository=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel \
  --set image.tag=latest
```

Deployment が利用可能になるまで待機（Pod が Running）：
```bash
kubectl wait --for=condition=available deployments strands-agents-travel --all
```

### エージェントのテスト

kubernetes port-forward を使用：
```bash
kubectl --namespace default port-forward service/strands-agents-travel 8080:80 &
```

travel サービスを呼び出し：
```bash
curl -X POST \
  http://localhost:8080/travel \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "3月に東京で訪れるべきベストスポットは？"}'
```

### Application Load Balancer を通じてエージェントを公開

[Application Load Balancer を設定するための IngressClass を作成](https://docs.aws.amazon.com/eks/latest/userguide/auto-configure-alb.html)：
```bash
cat <<EOF | kubectl apply -f -
apiVersion: eks.amazonaws.com/v1
kind: IngressClassParams
metadata:
  name: alb
spec:
  scheme: internet-facing
EOF
```

```bash
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: alb
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"
spec:
  controller: eks.amazonaws.com/alb
  parameters:
    apiGroup: eks.amazonaws.com
    kind: IngressClassParams
    name: alb
EOF
```

作成した IngressClass を使用して Ingress を作成するように Helm デプロイメントを更新：
```bash
helm upgrade strands-agents-travel ./chart \
  --set image.repository=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel \
  --set image.tag=latest \
  --set ingress.enabled=true \
  --set ingress.className=alb
```

ALB URL を取得：
```bash
export ALB_URL=$(kubectl get ingress strands-agents-travel -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "共有 ALB は以下で利用可能：http://$ALB_URL"
```

ALB がアクティブになるまで待機：
```bash
aws elbv2 wait load-balancer-available --load-balancer-arns $(aws elbv2 describe-load-balancers --query 'LoadBalancers[?DNSName==`'"$ALB_URL"'`].LoadBalancerArn' --output text)
```

Application Load Balancer 経由で travel サービスを呼び出し：
```bash
curl -X POST \
  http://$ALB_URL/travel \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "バルセロナのトップアトラクションは？"}'
```

### 高可用性と回復性の設定

高可用性を設定するには：
- レプリカ数を 3 に増加
- [Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)：マルチ AZ にワークロードを分散
- [Pod Disruption Budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/#pod-disruption-budgets)：minAvailable を 1 に設定

```bash
helm upgrade strands-agents-travel ./chart -f - <<EOF
image:
  repository: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel
  tag: latest

ingress:
  enabled: true
  className: alb

replicaCount: 3

topologySpreadConstraints:
  - maxSkew: 1
    minDomains: 3
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: strands-agents-travel
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        app.kubernetes.io/instance: strands-agents-travel

podDisruptionBudget:
  enabled: true
  minAvailable: 1
EOF
```

## クリーンアップ

Helm チャートをアンインストール：
```bash
helm uninstall strands-agents-travel
```

EKS Auto Mode クラスターを削除：
```bash
eksctl delete cluster --name $CLUSTER_NAME --wait
```

IAM ポリシーを削除：
```bash
aws iam delete-policy --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/strands-agents-travel-bedrock-policy
```

## ライセンス

このプロジェクトは Apache License 2.0 の下でライセンスされています。詳細は LICENSE ファイルを参照してください。
