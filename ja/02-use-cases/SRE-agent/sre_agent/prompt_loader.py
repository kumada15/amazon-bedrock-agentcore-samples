#!/usr/bin/env python3

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class PromptLoader:
    """プロンプトテンプレートの読み込みと管理を行うユーティリティクラス。"""

    def __init__(self, prompts_dir: Optional[str] = None):
        """プロンプトローダーを初期化します。

        Args:
            prompts_dir: プロンプトファイルを含むディレクトリ。None の場合はデフォルトの相対パスを使用。
        """
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # Default to config/prompts relative to this file
            self.prompts_dir = Path(__file__).parent / "config" / "prompts"

        logger.debug(f"PromptLoader を prompts_dir で初期化しました: {self.prompts_dir}")

    @lru_cache(maxsize=32)
    def _load_prompt_file(self, filename: str) -> str:
        """キャッシュを使用してプロンプトファイルを読み込みます。

        Args:
            filename: 読み込むプロンプトファイルの名前

        Returns:
            プロンプトファイルの内容

        Raises:
            FileNotFoundError: プロンプトファイルが存在しない場合
            IOError: ファイルの読み込みでエラーが発生した場合
        """
        filepath = self.prompts_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Prompt file not found: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()

            logger.debug(f"プロンプトファイルを読み込みました: {filename}")
            return content
        except Exception as e:
            logger.error(f"プロンプトファイル {filename} の読み込みエラー: {e}")
            raise IOError(f"Failed to read prompt file {filename}: {e}")

    def load_prompt(self, prompt_name: str) -> str:
        """名前でプロンプトを読み込みます。

        Args:
            prompt_name: プロンプトの名前（.txt 拡張子なし）

        Returns:
            プロンプトファイルの内容
        """
        filename = f"{prompt_name}.txt"
        return self._load_prompt_file(filename)

    def load_template(self, template_name: str, **kwargs) -> str:
        """プロンプトテンプレートを読み込み、変数を置換します。

        Args:
            template_name: テンプレートの名前（.txt 拡張子なし）
            **kwargs: テンプレート内で置換する変数

        Returns:
            変数が置換されたテンプレート内容
        """
        template_content = self.load_prompt(template_name)

        try:
            return template_content.format(**kwargs)
        except KeyError as e:
            logger.error(f"テンプレート {template_name} でテンプレート変数 {e} が見つかりません")
            raise ValueError(f"Missing required template variable: {e}")
        except Exception as e:
            logger.error(f"テンプレート {template_name} のフォーマットエラー: {e}")
            raise ValueError(f"Error formatting template {template_name}: {e}")

    def get_agent_prompt(
        self,
        agent_type: str,
        agent_name: str,
        agent_description: str,
        memory_context: str = "",
    ) -> str:
        """ベースエージェントプロンプトとエージェント固有プロンプト、メモリコンテキストを結合します。

        Args:
            agent_type: エージェントのタイプ（kubernetes, logs, metrics, runbooks）
            agent_name: エージェントの表示名
            agent_description: エージェントの機能の説明
            memory_context: このエージェントの関連メモリコンテキスト

        Returns:
            メモリコンテキストを含むエージェントの完全なシステムプロンプト
        """
        try:
            # Load base prompt template
            base_prompt = self.load_template(
                "agent_base_prompt",
                agent_name=agent_name,
                agent_description=agent_description,
            )

            # Load agent-specific prompt if it exists
            try:
                agent_specific_prompt = self.load_prompt(f"{agent_type}_agent_prompt")
                combined_prompt = f"{base_prompt}\n\n{agent_specific_prompt}"
            except FileNotFoundError:
                logger.warning(f"エージェントタイプ {agent_type} の専用プロンプトが見つかりません")
                combined_prompt = base_prompt

            # Add memory context if provided
            if memory_context:
                combined_prompt += f"\n\n## Relevant Memory Context\n\n{memory_context}\n\nUse this context to inform your responses and avoid repeating work that has already been done."
                logger.debug(
                    f"{agent_type} エージェントプロンプトにメモリコンテキストを追加しました ({len(memory_context)} 文字)"
                )

            return combined_prompt

        except Exception as e:
            logger.error(f"{agent_type} のエージェントプロンプト構築エラー: {e}")
            raise

    def get_supervisor_aggregation_prompt(
        self,
        is_plan_based: bool,
        query: str,
        agent_results: str,
        auto_approve_plan: bool = False,
        user_preferences: str = "",
        **kwargs,
    ) -> str:
        """コンテキストに基づいてスーパーバイザー集約プロンプトを取得します。

        Args:
            is_plan_based: これが計画ベースの集約かどうか
            query: 元のユーザークエリ
            agent_results: エージェント結果の JSON 文字列
            auto_approve_plan: 自動承認命令を含めるかどうか
            **kwargs: 追加のテンプレート変数（例：current_step, total_steps, plan）

        Returns:
            フォーマットされた集約プロンプト
        """
        try:
            # Determine auto-approve instruction
            auto_approve_instruction = ""
            if auto_approve_plan:
                auto_approve_instruction = "\n\nIMPORTANT: Do not ask any follow-up questions or suggest that the user can ask for more details. Provide a complete, conclusive response."

            template_vars = {
                "query": query,
                "agent_results": agent_results,
                "auto_approve_instruction": auto_approve_instruction,
                "user_preferences": user_preferences,
                **kwargs,
            }

            if is_plan_based:
                return self.load_template(
                    "supervisor_plan_aggregation", **template_vars
                )
            else:
                return self.load_template(
                    "supervisor_standard_aggregation", **template_vars
                )

        except Exception as e:
            logger.error(f"スーパーバイザー集約プロンプトの構築エラー: {e}")
            raise

    def get_executive_summary_prompts(
        self, query: str, results_text: str
    ) -> tuple[str, str]:
        """エグゼクティブサマリー生成用のシステムプロンプトとユーザープロンプトを取得します。

        Args:
            query: 元のユーザークエリ
            results_text: フォーマットされた調査結果

        Returns:
            (system_prompt, user_prompt) のタプル
        """
        try:
            system_prompt = self.load_prompt("executive_summary_system")
            user_prompt = self.load_template(
                "executive_summary_user_template",
                query=query,
                results_text=results_text,
            )

            return system_prompt, user_prompt

        except Exception as e:
            logger.error(f"エグゼクティブサマリープロンプトの構築エラー: {e}")
            raise

    def list_available_prompts(self) -> list[str]:
        """利用可能なすべてのプロンプトファイルを一覧表示します。

        Returns:
            プロンプト名のリスト（.txt 拡張子なし）
        """
        try:
            prompt_files = list(self.prompts_dir.glob("*.txt"))
            return [f.stem for f in prompt_files]
        except Exception as e:
            logger.error(f"プロンプトファイル一覧取得エラー: {e}")
            return []


# Convenience instance for easy import
prompt_loader = PromptLoader()


# Convenience functions for backward compatibility
def load_prompt(prompt_name: str) -> str:
    """デフォルトローダーを使用して名前でプロンプトを読み込みます。"""
    return prompt_loader.load_prompt(prompt_name)


def load_template(template_name: str, **kwargs) -> str:
    """デフォルトローダーを使用してテンプレートを読み込みフォーマットします。"""
    return prompt_loader.load_template(template_name, **kwargs)


def get_agent_prompt(
    agent_type: str, agent_name: str, agent_description: str, memory_context: str = ""
) -> str:
    """デフォルトローダーを使用して完全なエージェントプロンプトを取得します。"""
    return prompt_loader.get_agent_prompt(
        agent_type, agent_name, agent_description, memory_context
    )
