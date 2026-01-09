#!/bin/bash
# ============================================================================
# AgentCore Runtime 用 Docker イメージのビルドと確認
# ============================================================================
# このスクリプトはデプロイ時に Terraform から呼び出され、以下を行います：
# 1. CodeBuild をトリガーして Docker イメージをビルド
# 2. ビルドの完了を待機
# 3. イメージが ECR に正常にプッシュされたことを確認
#
# パラメータ:
#   $1 - CodeBuild プロジェクト名
#   $2 - AWS リージョン
#   $3 - ECR リポジトリ名
#   $4 - イメージタグ
#   $5 - ECR リポジトリ URL

set -e

# 出力用の色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# パラメータ
PROJECT_NAME="$1"
REGION="$2"
REPO_NAME="$3"
IMAGE_TAG="$4"
REPO_URL="$5"

# ============================================================================
# 出力関数
# ============================================================================

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

# ============================================================================
# ビルドプロセスの開始
# ============================================================================

print_header "AgentCore Runtime 用の Docker イメージをビルドしています"

print_info "CodeBuild プロジェクト: $PROJECT_NAME"
print_info "リージョン: $REGION"
print_info "ターゲットイメージ: $REPO_URL:$IMAGE_TAG"
echo ""

# CodeBuild を開始
print_info "CodeBuild プロジェクトを開始しています..."

BUILD_ID=$(aws codebuild start-build \
  --project-name "$PROJECT_NAME" \
  --region "$REGION" \
  --query 'build.id' \
  --output text 2>&1)

if [ $? -ne 0 ]; then
  print_error "CodeBuild の開始に失敗しました"
  echo "$BUILD_ID"
  exit 1
fi

print_success "ビルドを開始しました: $BUILD_ID"
print_info "ビルドの完了を待っています（通常 5-10 分かかります）..."
echo ""

# ============================================================================
# ビルドの進捗を監視
# ============================================================================

ATTEMPT=0
MAX_ATTEMPTS=60  # 10 minutes (60 * 10s)

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  ATTEMPT=$((ATTEMPT + 1))

  STATUS=$(aws codebuild batch-get-builds \
    --ids "$BUILD_ID" \
    --region "$REGION" \
    --query 'builds[0].buildStatus' \
    --output text 2>/dev/null)

  if [ "$STATUS" != "IN_PROGRESS" ]; then
    print_info "ビルドプロセスがステータス: $STATUS で完了しました"
    break
  fi

  # 進捗インジケータ
  if [ $((ATTEMPT % 6)) -eq 0 ]; then
    MINUTES=$((ATTEMPT / 6))
    print_info "ビルド中... （${MINUTES} 分経過）"
  fi

  sleep 10
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
  print_error "10 分後にビルドがタイムアウトしました"
  print_warning "ビルドステータスを確認: https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/history?region=$REGION"
  exit 1
fi

echo ""

# ============================================================================
# ECR でイメージを確認
# ============================================================================

print_header "ECR で Docker イメージを確認しています"

print_info "イメージを確認中: $REPO_NAME:$IMAGE_TAG"
print_info "ECR への反映を待っています..."
echo ""

sleep 5  # ECR がプッシュを登録するまで少し待機

VERIFY_ATTEMPT=0
MAX_VERIFY_ATTEMPTS=12  # 1 minute (12 * 5s)

while [ $VERIFY_ATTEMPT -lt $MAX_VERIFY_ATTEMPTS ]; do
  VERIFY_ATTEMPT=$((VERIFY_ATTEMPT + 1))

  if aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --image-ids imageTag="$IMAGE_TAG" \
    --region "$REGION" >/dev/null 2>&1; then

    print_success "ECR で Docker イメージを正常に確認しました！"
    echo ""
    print_info "イメージ URI: $REPO_URL:$IMAGE_TAG"

    # イメージの詳細を取得
    IMAGE_SIZE=$(aws ecr describe-images \
      --repository-name "$REPO_NAME" \
      --image-ids imageTag="$IMAGE_TAG" \
      --region "$REGION" \
      --query 'imageDetails[0].imageSizeInBytes' \
      --output text 2>/dev/null || echo "Unknown")

    if [ "$IMAGE_SIZE" != "Unknown" ]; then
      IMAGE_SIZE_MB=$((IMAGE_SIZE / 1024 / 1024))
      print_info "イメージサイズ: ${IMAGE_SIZE_MB} MB"
    fi

    echo ""
    print_success "ビルドと確認が正常に完了しました！"
    exit 0
  fi

  if [ $((VERIFY_ATTEMPT % 3)) -eq 0 ]; then
    print_info "ECR でイメージが表示されるのを待っています... （試行 $VERIFY_ATTEMPT/$MAX_VERIFY_ATTEMPTS）"
  fi

  sleep 5
done

# ============================================================================
# エラー: イメージが見つかりません
# ============================================================================

print_error "ビルド完了後に ECR で Docker イメージが見つかりませんでした"
echo ""
print_warning "これはビルドまたはプッシュステップが失敗したことを示しています。"
print_info "トラブルシューティング手順:"
print_info "  1. CodeBuild ログを確認:"
print_info "     https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/history?region=$REGION"
print_info ""
print_info "  2. ECR リポジトリを確認:"
print_info "     aws ecr describe-images --repository-name $REPO_NAME --region $REGION"
print_info ""
print_info "  3. CodeBuild ロールの IAM 権限を確認"

exit 1
