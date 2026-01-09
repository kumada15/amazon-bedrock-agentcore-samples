#!/usr/bin/env python3

import logging
import os
from typing import Any, Dict, List, Optional

from .constants import SREConstants
from .llm_utils import create_llm_with_error_handling
from .prompt_loader import prompt_loader

# basicConfig でロギングを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class SREOutputFormatter:
    """SRE マルチエージェントレスポンス用のシンプルな Markdown 出力フォーマッター。"""

    def __init__(self, llm_provider: Optional[str] = None):
        # パラメータ、環境変数、またはデフォルトの bedrock からプロバイダーを取得
        self.llm_provider = llm_provider or os.getenv("LLM_PROVIDER", "bedrock")
        logger.info(
            f"SREOutputFormatter initialized with LLM provider: {self.llm_provider}"
        )

    def _create_llm(self, **kwargs):
        """改善されたエラーハンドリングを備えた LLM インスタンスを作成します。"""
        # 出力フォーマッター固有の設定を取得（max_tokens を削減）
        formatter_config = SREConstants.get_output_formatter_config(
            self.llm_provider, **kwargs
        )
        logger.info(
            f"Creating LLM for output formatter - Provider: {self.llm_provider}, Max tokens: {formatter_config['max_tokens']}"
        )

        # フォーマッター固有の設定で集中型エラーハンドリングを使用
        return create_llm_with_error_handling(
            self.llm_provider, max_tokens=formatter_config["max_tokens"], **kwargs
        )

    def _extract_steps_from_response(self, response: str) -> List[str]:
        """エージェントレスポンスから番号付きステップを抽出します。"""
        if not response:
            return []

        steps = []
        lines = response.split("\n")

        for line in lines:
            line = line.strip()
            # 番号付きステップ（1.、2. など）または箇条書きを探す
            if line and (
                line[0].isdigit() or line.startswith("-") or line.startswith("•")
            ):
                steps.append(line)

        return steps

    def format_investigation_response(
        self,
        query: str,
        agent_results: Dict[str, Any],
        metadata: Dict[str, Any],
        plan: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """完全な調査レスポンスをクリーンな Markdown でフォーマットします。"""

        # 主要情報を抽出
        plan_info = plan or metadata.get("investigation_plan", {})
        current_step = metadata.get("plan_step", 0) + 1
        total_steps = len(plan_info.get("steps", []))

        output = []

        # ヘッダー
        output.append("# 🔍 調査結果")
        output.append("")
        output.append(f"**Query:** {query}")
        output.append("")

        # エグゼクティブサマリーセクション
        executive_summary = self._generate_executive_summary(
            query, agent_results, metadata, user_preferences
        )
        if executive_summary:
            output.append(executive_summary)
            output.append("")

        # 主要発見事項セクション
        if agent_results:
            output.append("## 🎯 主要発見事項")
            output.append("")

            for agent_name, result in agent_results.items():
                if not result or result == "No response provided":
                    continue

                agent_display = agent_name.replace("_", " ").title()
                output.append(f"### {agent_display}")

                # ランブックレスポンスの場合はステップを抽出
                if (
                    "runbooks" in agent_name.lower()
                    or "operational" in agent_name.lower()
                ):
                    steps = self._extract_steps_from_response(result)
                    if steps:
                        output.append("")
                        output.append("**発見されたランブックステップ:**")
                        for step in steps:
                            # ステップフォーマットを整理
                            clean_step = step.strip()
                            if clean_step.startswith(
                                ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")
                            ):
                                output.append(f"{clean_step}")
                            else:
                                output.append(f"- {clean_step}")
                        output.append("")
                    else:
                        # ステップが見つからない場合は完全なレスポンスを表示
                        output.append(f"- {result}")
                        output.append("")
                else:
                    # ランブック以外のエージェントの場合は完全なレスポンスを表示
                    output.append(f"- {result}")
                    output.append("")

        # 次のステップセクション
        if plan_info and current_step < total_steps:
            output.append("## 📋 次のステップ")
            output.append("")
            remaining_steps = plan_info.get("steps", [])[current_step:]
            for i, step in enumerate(remaining_steps, current_step + 1):
                output.append(f"{i}. {step}")
            output.append("")

        # 調査完了
        if current_step >= total_steps:
            output.append("## ✅ 調査完了")
            output.append("")
            output.append("計画されたすべての調査ステップが実行されました。")
            output.append("")

        return "\n".join(output)

    def _generate_executive_summary(
        self,
        query: str,
        agent_results: Dict[str, Any],
        metadata: Dict[str, Any],
        user_preferences: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """調査結果の LLM 分析を使用してエグゼクティブサマリーを生成します。"""
        if not agent_results:
            return ""

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            # 設定されたプロバイダーを使用して LLM インスタンスを作成
            llm = self._create_llm()

            # 分析用にエージェント結果を準備
            formatted_results = []
            for agent_name, result in agent_results.items():
                if result and result != "No response provided":
                    formatted_results.append(f"**{agent_name}:**\n{result}\n")

            results_text = "\n".join(formatted_results)

            # 利用可能な場合はユーザー設定をコンテキストに追加
            if user_preferences:
                import json

                prefs_text = json.dumps(user_preferences, indent=2, default=str)
                results_text += f"\n\n**ユーザー設定:**\n{prefs_text}\n"

            # プロンプトローダーからプロンプトを取得
            system_prompt, user_prompt = prompt_loader.get_executive_summary_prompts(
                query=query, results_text=results_text
            )

            # デバッグ用に LLM に送信されるプロンプトをログ出力
            logger.info("=== EXECUTIVE SUMMARY PROMPT LOGGING ===")
            logger.info(f"System Prompt Length: {len(system_prompt)} characters")
            logger.info(f"User Prompt Length: {len(user_prompt)} characters")
            if user_preferences:
                logger.info(
                    f"User preferences included in context: {len(user_preferences)} preference items"
                )
                logger.info(
                    f"User preferences preview: {str(user_preferences)[:200]}..."
                )
            else:
                logger.info(
                    "No user preferences provided to executive summary generation"
                )
            logger.info(f"User Prompt Content:\n{user_prompt}")
            logger.info("=== END EXECUTIVE SUMMARY PROMPT LOGGING ===")

            # エグゼクティブサマリーを生成
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = llm.invoke(messages)
            return str(response.content).strip()

        except Exception as e:
            logger.error(f"LLM でエグゼクティブサマリーの生成中にエラーが発生しました: {e}")
            # LLM が失敗した場合はシンプルなサマリーにフォールバック
            return self._generate_fallback_summary(query, agent_results)

    def _generate_fallback_summary(
        self, query: str, agent_results: Dict[str, Any]
    ) -> str:
        """LLM 生成が失敗した場合のフォールバックエグゼクティブサマリー。"""
        return """## 📋 エグゼクティブサマリー

### 🎯 主要インサイト
- **根本原因**: 調査結果には分析が必要です
- **影響**: サービスパフォーマンスに影響を与える可能性があります
- **重大度**: 中

### ⚡ 次のステップ
1. **即時** (< 1時間): 以下の詳細な発見事項を確認
2. **短期** (< 24時間): 推奨される修復ステップを実行
3. **長期** (< 1週間): 改善のためシステムメトリクスを監視
4. **フォローアップ**: 該当する場合はポストインシデントレビューをスケジュール"""

    def format_plan_approval(self, plan: Dict[str, Any], query: str) -> str:
        """計画承認リクエストをクリーンな Markdown でフォーマットします。"""
        output = []

        # ヘッダー
        output.append("# 📋 調査計画")
        output.append("")
        output.append(f"**クエリ:** {query}")
        output.append(f"**複雑度:** {plan.get('complexity', 'unknown').title()}")
        output.append("")

        # 計画ステップ
        steps = plan.get("steps", [])
        if steps:
            output.append("## 調査ステップ")
            output.append("")
            for i, step in enumerate(steps, 1):
                output.append(f"{i}. {step}")
            output.append("")

        # 計画詳細
        reasoning = plan.get("reasoning", "標準的な調査アプローチ")
        auto_execute = plan.get("auto_execute", False)

        output.append("## 計画詳細")
        output.append("")
        output.append(f"**理由:** {reasoning}")
        output.append(f"**自動実行:** {'はい' if auto_execute else 'いいえ'}")
        output.append("")

        # アクション
        output.append("## 利用可能なアクション")
        output.append("")
        output.append("- `proceed` または `yes` と入力して計画を実行")
        output.append("- `modify` と入力して変更を提案")
        output.append("- 任意のステップについて具体的な質問をする")
        output.append("")

        return "\n".join(output)


def create_formatter(llm_provider: Optional[str] = None) -> SREOutputFormatter:
    """新しい SRE 出力フォーマッターインスタンスを作成して返します。"""
    return SREOutputFormatter(llm_provider=llm_provider)
