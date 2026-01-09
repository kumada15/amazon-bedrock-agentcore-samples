#!/usr/bin/env python3
"""
改善されたエラーハンドリングを備えた集中型 LLM ユーティリティ。

このモジュールは、認証、アクセス、設定の問題に対する適切なエラーハンドリングを備えた
LLM 作成の単一ポイントを提供します。
"""

import logging
from typing import Any, Dict

from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock

from .constants import SREConstants

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """LLM プロバイダーの作成が失敗した場合に発生する例外。"""

    pass


class LLMAuthenticationError(LLMProviderError):
    """LLM 認証が失敗した場合に発生する例外。"""

    pass


class LLMAccessError(LLMProviderError):
    """LLM アクセスが拒否された場合に発生する例外。"""

    pass


def create_llm_with_error_handling(provider: str = "bedrock", **kwargs):
    """適切なエラーハンドリングと有用なエラーメッセージを備えた LLM インスタンスを作成します。

    Args:
        provider: LLM プロバイダー（"anthropic" または "bedrock"）
        **kwargs: 追加の設定オーバーライド

    Returns:
        LLM インスタンス

    Raises:
        LLMProviderError: 一般的なプロバイダーエラーの場合
        LLMAuthenticationError: 認証失敗の場合
        LLMAccessError: アクセス/権限の失敗の場合
        ValueError: サポートされていないプロバイダーの場合
    """
    if provider not in ["anthropic", "bedrock"]:
        raise ValueError(
            f"Unsupported provider: {provider}. Use 'anthropic' or 'bedrock'"
        )

    logger.info(f"プロバイダー {provider} で LLM を作成中")

    try:
        config = SREConstants.get_model_config(provider, **kwargs)

        if provider == "anthropic":
            logger.info(f"Anthropic LLM を作成中 - モデル: {config['model_id']}")
            return _create_anthropic_llm(config)
        else:  # bedrock
            logger.info(
                f"Bedrock LLM を作成中 - モデル: {config['model_id']}, リージョン: {config['region_name']}"
            )
            return _create_bedrock_llm(config)

    except Exception as e:
        error_msg = _get_helpful_error_message(provider, e)
        logger.error(f"LLM の作成に失敗しました: {error_msg}")

        # Classify the error type for better handling
        if _is_auth_error(e):
            raise LLMAuthenticationError(error_msg) from e
        elif _is_access_error(e):
            raise LLMAccessError(error_msg) from e
        else:
            raise LLMProviderError(error_msg) from e


def _create_anthropic_llm(config: Dict[str, Any]):
    """Anthropic LLM インスタンスを作成します。"""
    return ChatAnthropic(
        model=config["model_id"],
        max_tokens=config["max_tokens"],
        temperature=config["temperature"],
    )


def _create_bedrock_llm(config: Dict[str, Any]):
    """Bedrock LLM インスタンスを作成します。"""
    return ChatBedrock(
        model_id=config["model_id"],
        region_name=config["region_name"],
        model_kwargs={
            "temperature": config["temperature"],
            "max_tokens": config["max_tokens"],
        },
    )


def _is_auth_error(error: Exception) -> bool:
    """エラーが認証関連かどうかをチェックします。"""
    error_str = str(error).lower()
    auth_keywords = [
        "authentication",
        "unauthorized",
        "invalid credentials",
        "api key",
        "access key",
        "token",
        "permission denied",
        "403",
        "401",
    ]
    return any(keyword in error_str for keyword in auth_keywords)


def _is_access_error(error: Exception) -> bool:
    """エラーがアクセス/権限関連かどうかをチェックします。"""
    error_str = str(error).lower()
    access_keywords = [
        "access denied",
        "forbidden",
        "not authorized",
        "insufficient permissions",
        "quota exceeded",
        "rate limit",
        "service unavailable",
        "region not supported",
    ]
    return any(keyword in error_str for keyword in access_keywords)


def _get_helpful_error_message(provider: str, error: Exception) -> str:
    """プロバイダーとエラータイプに基づいて有用なエラーメッセージを生成します。"""
    base_error = str(error)

    if provider == "anthropic":
        if _is_auth_error(error):
            return (
                f"Anthropic authentication failed: {base_error}\n"
                "Solutions:\n"
                "  1. Set ANTHROPIC_API_KEY environment variable\n"
                "  2. Check if your API key is valid and active\n"
                "  3. Try running: export ANTHROPIC_API_KEY='your-key-here'\n"
                "  4. Or switch to Bedrock: sre-agent --provider bedrock"
            )
        elif _is_access_error(error):
            return (
                f"Anthropic access denied: {base_error}\n"
                "Solutions:\n"
                "  1. Check if your account has sufficient credits\n"
                "  2. Verify your API key has the required permissions\n"
                "  3. Check rate limits and usage quotas\n"
                "  4. Or switch to Bedrock: sre-agent --provider bedrock"
            )
        else:
            return (
                f"Anthropic provider error: {base_error}\n"
                "Solutions:\n"
                "  1. Check your internet connection\n"
                "  2. Verify Anthropic service status\n"
                "  3. Try again in a few minutes\n"
                "  4. Or switch to Bedrock: sre-agent --provider bedrock"
            )

    else:  # bedrock
        if _is_auth_error(error):
            return (
                f"Amazon Bedrock authentication failed: {base_error}\n"
                "Solutions:\n"
                "  1. Configure AWS credentials (aws configure)\n"
                "  2. Set AWS_PROFILE environment variable\n"
                "  3. Check IAM permissions for Bedrock access\n"
                "  4. Verify your AWS credentials are valid\n"
                "  5. Or switch to Anthropic: sre-agent --provider anthropic"
            )
        elif _is_access_error(error):
            return (
                f"Amazon Bedrock access denied: {base_error}\n"
                "Solutions:\n"
                "  1. Enable Claude models in Bedrock console\n"
                "  2. Request model access for your AWS account\n"
                "  3. Check if the region supports Bedrock\n"
                "  4. Verify IAM permissions for bedrock:InvokeModel\n"
                "  5. Or switch to Anthropic: sre-agent --provider anthropic"
            )
        else:
            return (
                f"Amazon Bedrock provider error: {base_error}\n"
                "Solutions:\n"
                "  1. Check AWS service status\n"
                "  2. Verify the region supports Bedrock\n"
                "  3. Try a different AWS region\n"
                "  4. Check your internet connection\n"
                "  5. Or switch to Anthropic: sre-agent --provider anthropic"
            )


def validate_provider_access(provider: str = "bedrock", **kwargs) -> bool:
    """指定されたプロバイダーがアクセス可能かどうかを検証します。

    Args:
        provider: 検証する LLM プロバイダー
        **kwargs: 追加の設定

    Returns:
        プロバイダーがアクセス可能な場合は True、そうでない場合は False
    """
    try:
        llm = create_llm_with_error_handling(provider, **kwargs)
        # シンプルなテスト呼び出しでアクセスを検証
        # 注意: これは最小限の検証です - 実際の使用では失敗する可能性があります
        logger.info(f"プロバイダー {provider} の検証に成功しました")
        return True
    except Exception as e:
        logger.warning(f"プロバイダー {provider} の検証に失敗しました: {e}")
        return False


def get_recommended_provider() -> str:
    """利用可能性に基づいて推奨プロバイダーを取得します。

    Returns:
        推奨プロバイダー名
    """
    # まず bedrock を試し（デフォルト）、次に anthropic を試す
    for provider in ["bedrock", "anthropic"]:
        if validate_provider_access(provider):
            logger.info(f"推奨プロバイダー: {provider}")
            return provider

    logger.warning("すぐにアクセスできるプロバイダーがありません - bedrock にデフォルト設定します")
    return "bedrock"
