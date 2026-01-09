"""
AWS re:Invent 2025 AIML301 ワークショップ用設定モジュール
AgentCore SRE ユースケース - 一元化された設定

モジュールレベル変数としての静的設定値。
お客様はこれらを直接インポートして、値の出所を確認できます。

Usage:
    from lab_helpers.config import AWS_REGION, MODEL_ID, WORKSHOP_NAME
    from lab_helpers import config

    print(config.AWS_REGION)
    print(config.MODEL_ID)
"""

# ============================================================================
# AWS 設定
# ============================================================================
AWS_REGION = "us-west-2"  # 動作するデプロイに合わせて変更
AWS_PROFILE = None

# ============================================================================
# Bedrock モデル設定
# ============================================================================
# Global CRIS（Cross-Region Inference Server）経由の Claude Sonnet 4
# Model ID: global.anthropic.claude-sonnet-4-20250514-v1:0
# - 200K コンテキストウィンドウ
# - リリース日: 2025年5月22日
#MODEL_ID = "global.anthropic.claude-sonnet-4-20250514-v1:0"
MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
# ============================================================================
# ワークショップ設定
# ============================================================================
WORKSHOP_NAME = "aiml301_sre_agentcore"
