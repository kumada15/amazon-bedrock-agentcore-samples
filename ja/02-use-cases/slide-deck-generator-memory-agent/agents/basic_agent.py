"""
Memory 機能を持たない基本的なスライドデッキエージェント
"""

import logging
import os
import sys

from config import OUTPUT_DIR
from generators.html_generator import HTMLSlideGenerator
from strands import Agent, tool

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


logger = logging.getLogger(__name__)


class BasicSlideDeckAgent:
    """Memory 機能なしでスライドデッキを作成するエージェント"""

    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        self.html_generator = HTMLSlideGenerator(output_dir)

        # Create the Strands agent with tools
        self.agent = Agent(
            model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            tools=[self.create_slides_tool, self.get_presentation_info],
            system_prompt=self._get_system_prompt(),
        )

    def _get_system_prompt(self) -> str:
        """Basic エージェント用のシステムプロンプトを取得する"""
        return """あなたは親切なスライドデッキ作成アシスタントです。
構造化されたコンテンツと HTML スライドを生成することで、ユーザーがプロフェッショナルなプレゼンテーションを作成するのを支援します。

あなたの機能:
1. ユーザーの説明からスライドコンテンツを作成
2. プロフェッショナルなスタイリングで HTML プレゼンテーションを生成
3. コンテンツを論理的なスライドシーケンスに整理
4. 基本的なテーマとカラースキームを適用

プレゼンテーションを作成する際:
- タイトルスライドから始める
- 明確で簡潔なスライドタイトルを使用
- 適切な場合はコンテンツを箇条書きに整理
- 主要なトピックにはセクションスライドを作成
- スライド間の論理的な流れを確保

利用可能なテーマ: professional, modern, minimal
利用可能なカラースキーム: blue, green, purple, red

コンテンツのフォーマット:
- # スライドタイトル（コンテンツスライド用）
- ## セクションタイトル（セクション区切りスライド用）
- - 箇条書き（リストアイテム用）
- 段落には通常のテキスト

実際の HTML プレゼンテーションを生成するには、常に create_slides_tool を使用してください。"""

    @tool
    def create_slides_tool(
        self,
        content: str,
        title: str,
        theme: str = "professional",
        color_scheme: str = "blue",
    ) -> str:
        """構造化されたコンテンツから HTML スライドを作成する

        Args:
            content: Markdown 形式のスライドコンテンツ:
                    # スライドタイトル
                    - 箇条書き 1
                    - 箇条書き 2

                    各新しいスライドタイトルには # を使用し、箇条書きには - または * を使用
            title: プレゼンテーションタイトル
            theme: ビジュアルテーマ（professional, modern, minimal）
            color_scheme: カラースキーム（blue, green, purple, red）

        Returns:
            生成された HTML プレゼンテーションへのファイルパス
        """
        try:
            # Validate inputs
            valid_themes = ["professional", "modern", "minimal"]
            valid_colors = ["blue", "green", "purple", "red"]

            if theme not in valid_themes:
                theme = "professional"
            if color_scheme not in valid_colors:
                color_scheme = "blue"

            # Generate the presentation
            filepath = self.html_generator.generate_presentation(
                content=content, title=title, theme=theme, color_scheme=color_scheme
            )

            logger.info(f"プレゼンテーションを生成しました: {filepath}")
            return f"Presentation created successfully: {os.path.basename(filepath)}\\nFull path: {filepath}"

        except Exception as e:
            logger.error(f"スライドの作成でエラーが発生しました: {e}")
            return f"Error creating presentation: {str(e)}"

    @tool
    def get_presentation_info(self) -> str:
        """利用可能なテーマとオプションに関する情報を取得する

        Returns:
            利用可能なプレゼンテーションオプションに関する情報
        """
        return """Available Presentation Options:

THEMES:
- professional: Clean, business-appropriate design
- modern: Contemporary styling with bold elements
- minimal: Simple, focused design

COLOR SCHEMES:
- blue: Professional blue tones
- green: Fresh, natural green palette
- purple: Creative, modern purple theme
- red: Bold, attention-grabbing red scheme

CONTENT FORMATTING:
- Use '# Title' for slide titles
- Use '## Section' for section dividers
- Use '- Point' for bullet points
- Write paragraphs as regular text

The agent will automatically create a title slide and organize your content into a logical presentation flow."""

    def create_presentation(self, user_request: str) -> str:
        """ユーザーリクエストに基づいてプレゼンテーションを作成する"""
        try:
            response = self.agent(user_request)
            return str(response)  # Convert AgentResult to string
        except Exception as e:
            logger.error(f"プレゼンテーション作成でエラーが発生しました: {e}")
            return f"Sorry, I encountered an error: {str(e)}"


def demo_basic_agent():
    """Basic エージェントの機能をデモンストレーションする"""
    agent = BasicSlideDeckAgent()

    # Example request
    request = """Create a 5-slide presentation about "Introduction to AI" with:
    - Title slide
    - What is AI section
    - Types of AI (Machine Learning, Deep Learning, NLP)
    - Applications of AI (Healthcare, Finance, Transportation)
    - Future of AI

    Use a blue color scheme and professional theme."""

    print("基本エージェントでプレゼンテーションを作成中...")
    result = agent.create_presentation(request)
    print(result)
    return result


if __name__ == "__main__":
    demo_basic_agent()
