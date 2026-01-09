"""
ユーザー好み学習用 Memory 機能を備えた拡張スライドデッキエージェント
"""

import json
import logging
import os
import sys
from typing import Any, Dict, List

from bedrock_agentcore.memory.session import MemorySession
from config import BEDROCK_MODEL_ID, OUTPUT_DIR
from generators.html_generator import HTMLSlideGenerator
from memory_hooks.slide_hooks import SlideMemoryHooks
from strands import Agent, tool

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# PowerPoint conversion removed - HTML only

logger = logging.getLogger(__name__)


class MemoryEnabledSlideDeckAgent:
    """ユーザー好みを学習する Memory 機能を備えた拡張スライドデッキエージェント"""

    def __init__(self, memory_session: MemorySession, output_dir: str = OUTPUT_DIR):
        self.output_dir = output_dir
        self.memory_session = memory_session
        self.html_generator = HTMLSlideGenerator(output_dir)

        # Create memory hooks
        self.memory_hooks = SlideMemoryHooks(memory_session)

        # Create the enhanced Strands agent with memory integration
        self.agent = Agent(
            model=BEDROCK_MODEL_ID,
            hooks=[self.memory_hooks],  # Memory hooks for automatic preference learning
            tools=[
                self.create_advanced_slides_tool,
                self.get_user_preferences_tool,
                self.recommend_style_tool,
            ],
            system_prompt=self._get_enhanced_system_prompt(),
        )

    def _get_enhanced_system_prompt(self) -> str:
        """Memory 有効エージェント用の拡張システムプロンプトを取得する"""
        return """あなたは Memory 機能を備えたインテリジェントなスライドデッキ作成アシスタントです。
ユーザーの好みを学習・記憶し、ますますパーソナライズされたプレゼンテーションを作成します。

あなたの拡張機能:
1. **Memory 駆動のパーソナライゼーション**: 色、テーマ、フォント、プレゼンテーションスタイルに関するユーザーの好みを学習
2. **コンテキスト認識による推奨**: プレゼンテーションタイプと過去の好みに基づいてスタイルを提案
3. **高度なスタイリング**: 洗練された CSS とユーザー好みの美学でプレゼンテーションを生成
4. **インタラクティブな HTML 出力**: ナビゲーションとキーボードサポート付きのレスポンシブ HTML プレゼンテーションを作成
5. **好みの進化**: ユーザーの好みをより深く学習するにつれて推奨を適応

**重要: create_advanced_slides_tool のコンテンツ形式**:
create_advanced_slides_tool を呼び出す際、content パラメータは Markdown を使用してフォーマットする必要があります:
- 各新しいスライドタイトルには # を使用: `# はじめに`
- 箇条書きには - または * を使用: `- ポイント 1`
- セクション区切りには ## を使用: `## セクション区切り`

コンテンツ形式の例:
```
# はじめに
- プレゼンテーションへようこそ
- トピックの概要

# メイントピック
- 最初の重要ポイント
- 2番目の重要ポイント
- 3番目の重要ポイント

# まとめ
- 要約
- ありがとうございました
```

**あなたの Memory システム**:
- ユーザーのスタイル選択とフィードバックを自動的に記憶
- パターンを学習: 「テクニカルプレゼンテーションには青のテーマ、ビジネスにはエレガントなフォント」
- 以前の成功した組み合わせに基づいて改善を提案
- 時間の経過とともにユーザーの変化する好みに適応

**利用可能なプレゼンテーションタイプ**:
- **Tech**: モダンでクリーンなスタイリングのテクニカルプレゼンテーション
- **Business**: コーポレートな美学のプロフェッショナルプレゼンテーション
- **Academic**: 伝統的で読みやすいスタイリングの学術プレゼンテーション
- **Creative**: 大胆で表現力豊かなデザインのアーティスティックプレゼンテーション

**利用可能なスタイリングコントロール**:
- 色: blue, green, purple, red（スマートな自動組み合わせ付き）
- フォント: modern (Inter), classic (Georgia), technical (JetBrains Mono), creative (Poppins)
- グラデーション: 単色には use_gradients=False、グラデーションには use_gradients=True
- シャドウ: シャドウを無効にするには use_shadows=False、有効にするには use_shadows=True
- 間隔: compact, comfortable, spacious（全体的なレイアウト密度を制御）
- ボーダー: 角丸用の 0-20 ピクセルの border radius
- フォントサイズ: 12-24 ピクセルのベースフォントサイズ
- ヘッダースタイル: bold, elegant, minimal

**インテリジェントな推奨**:
ユーザーが好みを指定しない場合、Memory を使用して適切なスタイルを提案:
- プレゼンテーションのトピックとオーディエンスを考慮
- 過去の成功した組み合わせを参照
- 確立された好みに沿った新しいバリエーションを提案
- 特定の選択を推奨する理由を説明

**必須ワークフロー - 常にこの順序に従う**:
1. **最初に**: プレゼンテーションを作成する前に、必ず get_user_preferences_tool() を呼び出して保存された好みを取得
2. **2番目に**: 学習した好みを抽出し、デフォルトのスタイリングパラメータとして使用
3. **3番目に**: 明示的なユーザー指示でオーバーライド（ユーザー指示が常に優先）
4. **4番目に**: パーソナライズされたデフォルト + ユーザーオーバーライドでプレゼンテーションを作成
5. **5番目に**: スタイリングの選択を説明し、今後の提案を改善するためのフィードバックを求める

**レスポンス戦略**:
- 常に学習した好みよりも明示的なユーザー指示を優先
- ユーザーが「単色」または「グラデーションなし」と言った場合、use_gradients=False を設定
- ユーザーが「シャドウなし」と言った場合、use_shadows=False を設定
- 指定されていないすべてのスタイリング選択には保存された好みを使用
- ユーザーの好みを Memory で確認せずにプレゼンテーションを作成しない

**保存された好みの適用方法**:
get_user_preferences_tool() から好みを取得したら、JSON を解析してスタイリングパラメータをツールに渡す:

好み解析の例:
- 好みに「青い色」と記載 → create_advanced_slides_tool に color_scheme="blue" を渡す
- 好みに「単色」または「グラデーションなし」と記載 → ツールに use_gradients=False を渡す
- 好みに「シャドウなし」と記載 → ツールに use_shadows=False を渡す
- 好みに「モダンフォント」と記載 → ツールに font_family="modern" を渡す
- 好みに「ビジネススタイル」と記載 → ツールに presentation_type="business" を渡す
- 好みに「ミニマル」と記載 → ツールに header_style="minimal" を渡す

**重要: ユーザー指示は Memory をオーバーライド**:
- ユーザーが「青い単色背景」を要求した場合、color_scheme="blue" と use_gradients=False を渡す
- ユーザーが「シャドウなしのミニマルスタイル」を望む場合、use_shadows=False を渡す
- 学習した好みが明示的な現在の指示と矛盾しないようにする

**オーバーライドの方法 - ツール呼び出しの例**:

例 1 - ユーザーがグラデーションを希望:
ユーザー: 「青と紫のグラデーションカラーを使用」
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=True,
    color_scheme="blue"
)

例 2 - ユーザーが単色を希望:
ユーザー: 「シャドウなしの濃い青の単色背景を使用」
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=False,
    color_scheme="dark-blue",
    use_shadows=False
)

例 3 - ユーザーが特定のフォントを希望:
ユーザー: 「モダンでプロフェッショナルなフォントを使用」
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    font_family="modern"
)

例 4 - ユーザーが暗いグラデーション背景を希望（コンプライアンスプレゼンテーションのような）:
ユーザー: 「濃いピンク、紫、濃い青の背景でグラデーションを使用」
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=True,
    color_scheme="dark-blue"
)

例 5 - ユーザーが特定の色で明るい背景を希望:
ユーザー: 「濃い緑のカラーテーマで明るい背景を使用」
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    color_scheme="green"  # green は緑のアクセント付きの明るい背景
)

例 6 - ユーザーが明るい背景を希望（特定の色なし）:
ユーザー: 「このプレゼンテーションには明るい背景を使用」
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    color_scheme="blue"  # デフォルトの明るい背景
)

例 7 - ユーザーがマルチカラーグラデーションを希望:
ユーザー: 「濃いピンク、紫、明るい青などのグラデーションカラーで暗い背景」
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    use_gradients=True,
    color_scheme="dark-purple"  # 最も目立つ/中心の色を選択
)

**複数の色についての注意**: ユーザーがグラデーションで複数の色に言及した場合:
- メイン/プライマリカラーを特定（通常は中間または最も強調されている色）
- 「濃いピンク、紫、明るい青」→ 紫が中心 → "dark-purple" を使用
- 「青と緑のグラデーション」→ 最初に言及された色を使用 → "blue"
- use_gradients=True を設定
- CSS ジェネレーターが自動的にグラデーションにブレンド

**重要 - これを無視しないでください**:
ユーザーが明示的なスタイリング指示を提供した場合、以下を行う必要があります:

1. ユーザーのリクエストを一語一語読む
2. すべてのスタイリング指示を抽出:
   - 「明るい背景」→ color_scheme="blue"（または色が指定されていれば green/purple/red）
   - 「濃い緑」+「明るい背景」→ color_scheme="green"
   - 「グラデーションカラー」→ use_gradients=True
   - 「単色」または「グラデーションなし」→ use_gradients=False
   - 「シャドウなし」→ use_shadows=False
   - 複数の色 → プライマリカラーを選択
3. create_advanced_slides_tool() 呼び出しでこれらのパラメータを渡す
4. パラメータを渡さない場合、代わりに Memory の好みが使用される

避けるべき失敗モード:
❌ エージェントが言う: 「明るい背景と緑を使用します」
❌ エージェントが呼び出す: create_advanced_slides_tool(content="...", title="...")  ← パラメータなし
❌ 結果: 古い Memory の好み（dark-blue）が適用され、ユーザーのリクエストは無視される

✅ 正しいアプローチ:
✅ エージェントが言う: 「明るい背景と緑を使用します」
✅ エージェントが呼び出す: create_advanced_slides_tool(content="...", title="...", color_scheme="green")  ← パラメータが渡される
✅ 結果: ユーザーの明示的なリクエストが正しく適用される

覚えておいてください: 何かをすると言うこと ≠ 実際にそれを行うこと。パラメータを渡してください。

**簡略化されたアプローチ - ユーザーリクエストを渡す**:
明示的なスタイリングが常に正しく適用されるようにするには、元のユーザーリクエストテキストを渡す:

例: ユーザーが濃い青でグラデーションを希望
ツール呼び出し: create_advanced_slides_tool(
    content="...",
    title="...",
    user_request="濃い青の背景でグラデーションカラーのプレゼンテーションを作成"
)
# ツールが自動的に抽出: use_gradients=True, color_scheme="dark-blue"

このアプローチは、LLM の解釈に依存するのではなく、Python コードがスタイリングキーワードをプログラム的に抽出するため、より信頼性があります。元のリクエストテキストを渡すだけで、ツールが残りを処理します！

**ワークフローの例**:
ユーザー: 「マーケティングについてのプレゼンテーションを作成」
1. get_user_preferences_tool() を呼び出す → 「紫の色」と「クリエイティブフォント」の好みを返す
2. デフォルトを設定: color_scheme="purple", font_family="creative"
3. ユーザーリクエストでオーバーライドを確認 → 指定なし
4. プレゼンテーションを作成: color_scheme="purple", font_family="creative"
5. 説明: 「過去の好みに基づいて、お好みの紫のカラースキームとクリエイティブフォントを使用しています」

常に利用可能なツールを使用してプレゼンテーションを作成し、継続的な改善のためにユーザーフィードバックを保存することを忘れないでください。"""

    @tool
    def create_advanced_slides_tool(
        self, content: str, title: str, user_request: str = "", **style_prefs
    ) -> str:
        """Memory から学習したユーザー好みで高度な HTML スライドを作成する

        Args:
            content: Markdown 形式のスライドコンテンツ:
                    # スライドタイトル
                    - 箇条書き 1
                    - 箇条書き 2
                    * 代替箇条書き構文
            user_request: 自動スタイル抽出用のオリジナルユーザーリクエストテキスト（オプション）

                    ## セクションタイトル（セクション区切り用）

                    各新しいスライドタイトルには # を使用し、箇条書きには - または * を使用
            title: プレゼンテーションタイトル
            **style_prefs: オプションのスタイルオーバーライド（color_scheme, use_gradients, use_shadows など）
                          提供されない場合、Memory から学習した好みを使用

        Returns:
            パーソナライズされたスタイリング付きの生成された HTML プレゼンテーションへのファイルパス
        """
        try:
            # Valid parameters for generate_presentation
            valid_params = {
                "theme",
                "color_scheme",
                "font_family",
                "use_gradients",
                "use_shadows",
                "border_radius",
                "spacing_style",
                "font_size_base",
                "header_style",
                "preferences",
            }

            # Three-tier merge: saved (memory) → style_prefs (LLM) → explicit (extracted from user_request)
            saved_prefs = self._get_saved_preferences()
            explicit_prefs = self._extract_style_from_request(user_request)
            final_prefs = {
                k: v
                for k, v in {**saved_prefs, **style_prefs, **explicit_prefs}.items()
                if k in valid_params
            }

            logger.info(
                f"🎨 Preference merge - Saved: {saved_prefs}, Explicit: {explicit_prefs}, Final: {final_prefs}"
            )

            # Generate presentation with preferences
            filepath = self.html_generator.generate_presentation(
                content=content, title=title, **final_prefs
            )

            # Add "Memory" suffix to distinguish from basic agent
            dir_name = os.path.dirname(filepath)
            base_name = os.path.basename(filepath)
            name_parts = base_name.rsplit(".", 1)
            new_filepath = os.path.join(
                dir_name, f"{name_parts[0]}_Memory.{name_parts[1]}"
            )
            os.rename(filepath, new_filepath)
            filepath = new_filepath

            logger.info(f"パーソナライズされたプレゼンテーションを生成しました: {filepath}")
            logger.info(f"適用された好み: {final_prefs}")

            # Create user-friendly response
            color_scheme = final_prefs.get("color_scheme", "default")
            use_gradients = final_prefs.get("use_gradients", True)
            use_shadows = final_prefs.get("use_shadows", True)

            return f"""✅ Personalized presentation created successfully!

📁 File: {os.path.basename(filepath)}
🎨 Style: {color_scheme} color scheme with personalized styling
🖼️  Effects: {"gradients" if use_gradients else "solid colors"}, {"shadows" if use_shadows else "no shadows"}
📍 Full path: {filepath}

The presentation includes:
- Styling based on your learned preferences
- Interactive navigation with keyboard support
- Responsive design for different screen sizes
- Ready to view in any web browser"""

        except Exception as e:
            logger.error(f"パーソナライズされたスライドの作成でエラーが発生しました: {e}")
            return f"❌ Error creating presentation: {str(e)}"

    # PowerPoint conversion functionality removed - HTML presentations only

    @tool
    def get_user_preferences_tool(self, query: str = "style preferences") -> str:
        """Memory から現在のユーザースタイル好みを取得する

        Args:
            query: 好みを検索するクエリ（オプション）

        Returns:
            UI レンダリング用の構造化された好みデータの JSON 文字列
        """
        try:
            # Search for user preferences in memory
            preference_namespace = (
                f"slidedecks/user/{self.memory_session._actor_id}/style_preferences"
            )

            preference_memories = self.memory_session.search_long_term_memories(
                query=query, namespace_prefix=preference_namespace, top_k=5
            )

            if not preference_memories:
                return json.dumps(
                    {
                        "status": "learning",
                        "message": "No established preferences found yet. I'm ready to learn your style preferences!",
                        "preferences": [],
                        "suggestions": [
                            "Try creating presentations with different color schemes",
                            "Experiment with various font styles and themes",
                            "Provide feedback on what works well for your audience",
                            "The agent will automatically learn your preferences",
                        ],
                    }
                )

            # Parse and structure the preferences
            structured_preferences = []
            total_found = len(preference_memories)
            max_display = 5  # Show up to 5 preferences instead of just 3

            logger.info(
                f"好みメモリ {total_found} 件中 {min(max_display, total_found)} 件を処理中"
            )

            for memory in preference_memories[:max_display]:  # Show top 5 preferences
                try:
                    content_text = memory.get("content", {}).get("text", "")
                    score = memory.get("score", 0)

                    logger.debug(
                        f"スコア {score} のメモリを処理中: {content_text[:100]}..."
                    )

                    # Parse the JSON content from memory
                    if content_text.startswith("{") and content_text.endswith("}"):
                        parsed_content = json.loads(content_text)

                        # Extract structured fields
                        preference_item = {
                            "type": self._categorize_preference(
                                parsed_content.get("categories", [])
                            ),
                            "preference": parsed_content.get(
                                "preference", "Unknown preference"
                            ),
                            "context": parsed_content.get("context", ""),
                            "confidence": round(score * 100),  # Convert to percentage
                            "categories": parsed_content.get("categories", []),
                        }
                        structured_preferences.append(preference_item)
                        logger.debug(
                            f"✅ JSON 好みをパースしました: {preference_item['type']}"
                        )
                    else:
                        # Fallback for non-JSON content
                        preference_item = {
                            "type": "General",
                            "preference": (
                                content_text[:100] + "..."
                                if len(content_text) > 100
                                else content_text
                            ),
                            "context": "Legacy format",
                            "confidence": round(score * 100),
                            "categories": ["general"],
                        }
                        structured_preferences.append(preference_item)
                        logger.debug(
                            f"✅ レガシー好みをパースしました: {preference_item['preference'][:50]}..."
                        )

                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"❌ 好みメモリのパースでエラーが発生しました: {e}")
                    logger.warning(f"   コンテンツ: {content_text[:200]}...")
                    continue

            # Create more informative message
            if total_found > len(structured_preferences):
                message = f"Showing {len(structured_preferences)} of {total_found} learned preferences"
            else:
                message = f"Found {len(structured_preferences)} learned preferences"

            return json.dumps(
                {
                    "status": "established" if structured_preferences else "learning",
                    "message": message,
                    "preferences": structured_preferences,
                }
            )

        except Exception as e:
            logger.error(f"好みの取得でエラーが発生しました: {e}")
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Error retrieving preferences: {str(e)}",
                    "preferences": [],
                }
            )

    def _categorize_preference(self, categories: List[str]) -> str:
        """カテゴリリストに基づいて好みを分類する"""
        if not categories:
            return "General"

        # Prioritize certain categories for display
        if any(cat in ["color", "colors", "theme"] for cat in categories):
            return "Color & Theme"
        elif any(cat in ["font", "fonts", "typography"] for cat in categories):
            return "Typography"
        elif any(cat in ["layout", "design", "style"] for cat in categories):
            return "Design Style"
        elif any(cat in ["technical", "code", "coding"] for cat in categories):
            return "Technical Content"
        elif any(
            cat in ["content_type", "content", "legal", "compliance"]
            for cat in categories
        ):
            return "Content Type"
        elif any(cat in ["presentations", "visual"] for cat in categories):
            return "Presentation Style"
        else:
            return categories[0].title() if categories else "General"

    @tool
    def recommend_style_tool(
        self,
        presentation_topic: str,
        audience: str = "general",
        context: str = "business",
    ) -> str:
        """トピック、オーディエンス、学習した好みに基づいてインテリジェントなスタイル推奨を取得する

        Args:
            presentation_topic: プレゼンテーションのトピックまたはタイトル
            audience: ターゲットオーディエンス（executives, technical, academic, general）
            context: コンテキストまたは設定（business, conference, classroom, creative）

        Returns:
            説明付きのパーソナライズされたスタイル推奨
        """
        try:
            # Get user preferences first
            preference_memories = self.memory_session.search_long_term_memories(
                query=f"{presentation_topic} {audience} {context}",
                namespace_prefix=f"slidedecks/user/{self.memory_session._actor_id}/style_preferences",
                top_k=3,
            )

            # Base recommendations on topic and audience
            recommendations = self._generate_base_recommendations(
                presentation_topic, audience, context
            )

            # Enhance with user preferences if available
            if preference_memories:
                user_preferences = self._extract_user_patterns(preference_memories)
                recommendations = self._personalize_recommendations(
                    recommendations, user_preferences
                )

                return f"""🎨 **Personalized Style Recommendations**

**For your "{presentation_topic}" presentation:**

{recommendations}

**Based on your preferences:**
{self._format_preference_insights(preference_memories)}

💡 **Why these recommendations:**
I've learned your style patterns and adapted these suggestions to match your proven preferences
while being appropriate for your {audience} audience in a {context} setting."""

            else:
                return f"""🎨 **Smart Style Recommendations**

**For your "{presentation_topic}" presentation:**

{recommendations}

💡 **Note**: These are general recommendations. As I learn your preferences through our interactions,
I'll provide increasingly personalized suggestions!

Try one of these styles and let me know what works well - I'll remember for next time."""

        except Exception as e:
            logger.error(f"推奨の生成でエラーが発生しました: {e}")
            return f"❌ Error generating recommendations: {str(e)}"

    def _generate_base_recommendations(
        self, topic: str, audience: str, context: str
    ) -> str:
        """トピックとコンテキストに基づいて基本的なスタイル推奨を生成する"""
        topic_lower = topic.lower()

        # Analyze topic for style cues
        if any(
            word in topic_lower for word in ["tech", "software", "data", "api", "code"]
        ):
            return """
**Presentation Type**: Tech
**Theme**: Modern with clean lines
**Colors**: Blue or purple for tech credibility
**Fonts**: Technical (JetBrains Mono) for headers, Modern (Inter) for content
**Style**: Minimal with focus on clarity and precision"""

        elif any(
            word in topic_lower
            for word in ["business", "strategy", "market", "finance"]
        ):
            return """
**Presentation Type**: Business
**Theme**: Professional and trustworthy
**Colors**: Blue or green for corporate appeal
**Fonts**: Modern (Inter) or Classic (Georgia) for readability
**Style**: Structured with elegant typography"""

        elif any(
            word in topic_lower
            for word in ["research", "study", "analysis", "academic"]
        ):
            return """
**Presentation Type**: Academic
**Theme**: Scholarly and readable
**Colors**: Classic blue or academic red
**Fonts**: Classic (Georgia) for traditional feel
**Style**: Clear hierarchy with detailed content support"""

        else:
            return """
**Presentation Type**: Creative
**Theme**: Engaging and memorable
**Colors**: Purple or green for visual interest
**Fonts**: Creative (Poppins) for modern appeal
**Style**: Dynamic with visual elements"""

    def _extract_user_patterns(self, memories: List[Dict]) -> Dict[str, Any]:
        """ユーザー好み Memory からパターンを抽出する"""
        patterns = {
            "preferred_colors": [],
            "preferred_fonts": [],
            "preferred_types": [],
            "feedback_patterns": [],
        }

        for memory in memories:
            content = memory.get("content", {}).get("text", "").lower()

            # Extract color preferences
            for color in ["blue", "green", "purple", "red"]:
                if color in content and "prefer" in content:
                    patterns["preferred_colors"].append(color)

            # Extract font preferences
            for font in ["modern", "classic", "technical", "creative"]:
                if font in content:
                    patterns["preferred_fonts"].append(font)

            patterns["feedback_patterns"].append(content)

        return patterns

    def _personalize_recommendations(self, base_recs: str, user_patterns: Dict) -> str:
        """ユーザーパターンに基づいて推奨をパーソナライズする"""
        # This is a simplified version - could be much more sophisticated
        personalized = base_recs

        if user_patterns["preferred_colors"]:
            most_used_color = max(
                set(user_patterns["preferred_colors"]),
                key=user_patterns["preferred_colors"].count,
            )
            personalized += f"\\n**Personalized**: Using {most_used_color} (your preferred color scheme)"

        if user_patterns["preferred_fonts"]:
            most_used_font = max(
                set(user_patterns["preferred_fonts"]),
                key=user_patterns["preferred_fonts"].count,
            )
            personalized += f"\\n**Personalized**: Suggesting {most_used_font} fonts (matches your style)"

        return personalized

    def _format_preference_insights(self, memories: List[Dict]) -> str:
        """ユーザー好みのインサイトをフォーマットする"""
        if not memories:
            return "No preference history available yet."

        insights = []
        for memory in memories[:2]:  # Top 2 insights
            content = memory.get("content", {}).get("text", "")
            score = memory.get("score", 0)
            insights.append(f"- {content[:100]}... (confidence: {score:.1f})")

        return "\\n".join(insights)

    def _get_saved_preferences(self) -> Dict[str, Any]:
        """Memory からユーザー好みを取得する - シンプルで信頼性のある方法"""
        try:
            # Get preferences from memory
            prefs_json = self.get_user_preferences_tool("style preferences")
            prefs_data = json.loads(prefs_json)

            # Start with minimal defaults
            preferences = {}

            # Color mapping - scalable approach (ordered by specificity - longer phrases first)
            color_map = {
                # Dark colors (check specific phrases first)
                "dark navy blue": "dark-blue",
                "navy blue": "dark-blue",
                "dark blue": "dark-blue",
                "navy": "dark-blue",
                "dark background": "dark",
                "dark theme": "dark",
                "dark green": "dark-green",
                "dark purple": "dark-purple",
                "dark": "dark",
                "black": "black",
                "charcoal": "black",
                # Light/bright colors
                "light background": "blue",  # default light background
                "light blue": "blue",
                "sky blue": "blue",
                "bright blue": "blue",
                "cyan": "blue",
                "bright green": "green",
                "lime": "green",
                "teal": "green",
                "blue": "blue",
                "green": "green",
                "purple": "purple",
                "red": "red",
                "orange": "red",
            }

            # Extract preferences if they exist
            if prefs_data.get("status") == "established":
                for pref in prefs_data.get("preferences", []):
                    text = pref.get("preference", "").lower()

                    # Color preferences - pattern matching (checks longer phrases first)
                    for color_phrase, scheme in color_map.items():
                        if color_phrase in text:
                            preferences["color_scheme"] = scheme
                            break  # Use first match

                    # Gradient preferences
                    if "solid color" in text or "no gradient" in text:
                        preferences["use_gradients"] = False

                    # Shadow preferences
                    if "no shadow" in text or "minimal" in text:
                        preferences["use_shadows"] = False

                    # Font preferences
                    for font in ["modern", "classic", "technical", "creative"]:
                        if font in text:
                            preferences["font_family"] = font
                            break

            logger.info(f"🎨 ユーザー好みを適用しました: {preferences}")
            return preferences

        except Exception as e:
            logger.error(f"好みの取得でエラーが発生しました: {e}")
            return {}  # Return empty dict - let HTML generator use its defaults

    def _extract_style_from_request(self, user_request: str) -> Dict[str, Any]:
        """ユーザーのオリジナルリクエストテキストからスタイリング好みをプログラム的に抽出する

        このアプローチは LLM の解釈に依存せず、ユーザーの自然言語リクエスト内の
        特定のキーワードを検索する。

        Args:
            user_request: オリジナルのユーザーリクエストテキスト

        Returns:
            抽出されたスタイル好みの辞書
        """
        if not user_request:
            return {}

        request_lower = user_request.lower()
        explicit_prefs = {}

        # Gradient detection
        if "gradient" in request_lower:
            explicit_prefs["use_gradients"] = True
        if "solid color" in request_lower or "no gradient" in request_lower:
            explicit_prefs["use_gradients"] = False

        # Shadow detection
        if "no shadow" in request_lower:
            explicit_prefs["use_shadows"] = False

        # Background/color detection (ordered by specificity - check longer phrases first)
        style_keywords = {
            "light background": "blue",  # default light background
            "dark background": "dark",
            "dark pink": "dark-purple",
            "dark purple": "dark-purple",
            "dark blue": "dark-blue",
            "dark green": "dark-green",
            "navy blue": "dark-blue",
            "purple": "purple",
            "blue": "blue",
            "green": "green",
            "red": "red",
        }

        for phrase, scheme in style_keywords.items():
            if phrase in request_lower:
                explicit_prefs["color_scheme"] = scheme
                break  # Use first match (most specific due to ordering)

        # Font detection
        font_keywords = ["modern", "classic", "technical", "creative"]
        for font in font_keywords:
            if font in request_lower:
                explicit_prefs["font_family"] = font
                break

        logger.info(
            f"🔍 ユーザーリクエストから明示的な好みを抽出しました: {explicit_prefs}"
        )
        return explicit_prefs

    def create_presentation(self, user_request: str) -> str:
        """自動 Memory 統合によるプレゼンテーション作成のメインエントリポイント"""
        try:
            logger.info("🚀 Memory 有効プレゼンテーション作成を開始中...")
            logger.info(f"📝 ユーザーリクエスト: {user_request[:100]}...")

            # Simple approach: let the tool handle memory internally
            response = self.agent(user_request)
            result = str(response)

            logger.info("✅ Memory 有効プレゼンテーション作成が完了しました")
            return result

        except Exception as e:
            logger.error(f"❌ Memory 有効プレゼンテーション作成でエラーが発生しました: {e}")
            return f"❌ Sorry, I encountered an error: {
                str(e)
            }\\n\\nPlease try again or contact support if the issue persists."


# 使用例とデモ関数
def create_memory_agent_demo(memory_session: MemorySession):
    """Memory 有効スライドエージェントのデモを作成する"""

    logger.info("メモリ対応スライドデッキエージェントを作成中...")
    agent = MemoryEnabledSlideDeckAgent(memory_session)

    # Demo request
    request = """I need a presentation about "AI Ethics in Healthcare" for a medical conference.
    The audience will be healthcare professionals and researchers.
    I prefer professional, trustworthy styling that's easy to read.

    Please create:
    - Title slide
    - What is AI Ethics section
    - Key ethical considerations (Privacy, Bias, Transparency, Accountability)
    - Healthcare-specific challenges
    - Best practices and recommendations
    - Q&A slide

    Make it look professional and credible for this important audience."""

    print("🤖 Memory 有効エージェントがリクエストを処理中...")
    result = agent.create_presentation(request)
    print("✅ Result:", result)

    return agent, result


if __name__ == "__main__":
    print("メモリ対応スライドデッキエージェント")
    print("このエージェントは MemorySession が必要です - memory_setup.py と一緒に使用")
    print("使用例:")
    print("  from memory_setup import setup_slide_deck_memory")
    print("  memory, session_mgr, mgr = setup_slide_deck_memory()")
    print("  session = session_mgr.create_memory_session('user123', 'session456')")
    print("  agent = MemoryEnabledSlideDeckAgent(session)")
