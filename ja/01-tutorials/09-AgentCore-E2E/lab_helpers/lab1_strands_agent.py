from strands.tools import tool
from ddgs.exceptions import DDGSException, RatelimitException
from ddgs import DDGS
from strands_tools import retrieve
import boto3

MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# エージェントの役割と機能を定義するシステムプロンプト
SYSTEM_PROMPT = """あなたは電子機器 EC 会社の親切でプロフェッショナルなカスタマーサポートアシスタントです。
あなたの役割は:
- 利用可能なツールを使用して正確な情報を提供する
- 技術情報と製品仕様でお客様をサポートする
- お客様に対して親切、忍耐強く、理解のある対応をする
- 質問に回答した後は常に追加のサポートを提案する
- 対応できないことがあれば、お客様を適切な連絡先に案内する

以下のツールにアクセスできます:
1. get_return_policy() - 保証と返品ポリシーに関する質問用
2. get_product_info() - 特定の製品に関する情報を取得
3. web_search() - 最新の技術ドキュメントや更新情報にアクセス
電子製品や仕様について仮定を立てるのではなく、常に適切なツールを使用して正確で最新の情報を取得してください。"""


@tool
def web_search(keywords: str, region: str = "us-en", max_results: int = 5) -> str:
    """ウェブで最新情報を検索します。

    Args:
        keywords (str): 検索クエリのキーワード。
        region (str): 検索リージョン: wt-wt, us-en, uk-en, ru-ru など。
        max_results (int | None): 返す結果の最大数。
    Returns:
        検索結果の辞書のリスト。

    """
    try:
        results = DDGS().text(keywords, region=region, max_results=max_results)
        return results if results else "No results found."
    except RatelimitException:
        return "Rate limit reached. Please try again later."
    except DDGSException as e:
        return f"Search error: {e}"
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def get_return_policy(product_category: str) -> str:
    """
    特定の製品カテゴリの返品ポリシー情報を取得します。

    Args:
        product_category: 電子機器カテゴリ（例：'smartphones'、'laptops'、'accessories'）

    Returns:
        期間と条件を含むフォーマットされた返品ポリシーの詳細
    """
    # モック返品ポリシーデータベース - 実際の実装ではポリシーデータベースをクエリします
    return_policies = {
        "smartphones": {
            "window": "30 days",
            "condition": "Original packaging, no physical damage, factory reset required",
            "process": "Online RMA portal or technical support",
            "refund_time": "5-7 business days after inspection",
            "shipping": "Free return shipping, prepaid label provided",
            "warranty": "1-year manufacturer warranty included",
        },
        "laptops": {
            "window": "30 days",
            "condition": "Original packaging, all accessories, no software modifications",
            "process": "Technical support verification required before return",
            "refund_time": "7-10 business days after inspection",
            "shipping": "Free return shipping with original packaging",
            "warranty": "1-year manufacturer warranty, extended options available",
        },
        "accessories": {
            "window": "30 days",
            "condition": "Unopened packaging preferred, all components included",
            "process": "Online return portal",
            "refund_time": "3-5 business days after receipt",
            "shipping": "Customer pays return shipping under $50",
            "warranty": "90-day manufacturer warranty",
        },
    }

    # 未登録カテゴリのデフォルトポリシー
    default_policy = {
        "window": "30 days",
        "condition": "Original condition with all included components",
        "process": "Contact technical support",
        "refund_time": "5-7 business days after inspection",
        "shipping": "Return shipping policies vary",
        "warranty": "Standard manufacturer warranty applies",
    }

    policy = return_policies.get(product_category.lower(), default_policy)
    return (
        f"Return Policy - {product_category.title()}:\n\n"
        f"• Return window: {policy['window']} from delivery\n"
        f"• Condition: {policy['condition']}\n"
        f"• Process: {policy['process']}\n"
        f"• Refund timeline: {policy['refund_time']}\n"
        f"• Shipping: {policy['shipping']}\n"
        f"• Warranty: {policy['warranty']}"
    )


@tool
def get_product_info(product_type: str) -> str:
    """
    電子機器製品の詳細な技術仕様と情報を取得します。

    Args:
        product_type: 電子機器製品タイプ（例：'laptops'、'smartphones'、'headphones'、'monitors'）
    Returns:
        保証、機能、ポリシーを含むフォーマットされた製品情報
    """
    # モック製品カタログ - 実際の実装では製品データベースをクエリします
    products = {
        "laptops": {
            "warranty": "1-year manufacturer warranty + optional extended coverage",
            "specs": "Intel/AMD processors, 8-32GB RAM, SSD storage, various display sizes",
            "features": "Backlit keyboards, USB-C/Thunderbolt, Wi-Fi 6, Bluetooth 5.0",
            "compatibility": "Windows 11, macOS, Linux support varies by model",
            "support": "Technical support and driver updates included",
        },
        "smartphones": {
            "warranty": "1-year manufacturer warranty",
            "specs": "5G/4G connectivity, 128GB-1TB storage, multiple camera systems",
            "features": "Wireless charging, water resistance, biometric security",
            "compatibility": "iOS/Android, carrier unlocked options available",
            "support": "Software updates and technical support included",
        },
        "headphones": {
            "warranty": "1-year manufacturer warranty",
            "specs": "Wired/wireless options, noise cancellation, 20Hz-20kHz frequency",
            "features": "Active noise cancellation, touch controls, voice assistant",
            "compatibility": "Bluetooth 5.0+, 3.5mm jack, USB-C charging",
            "support": "Firmware updates via companion app",
        },
        "monitors": {
            "warranty": "3-year manufacturer warranty",
            "specs": "4K/1440p/1080p resolutions, IPS/OLED panels, various sizes",
            "features": "HDR support, high refresh rates, adjustable stands",
            "compatibility": "HDMI, DisplayPort, USB-C inputs",
            "support": "Color calibration and technical support",
        },
    }
    product = products.get(product_type.lower())
    if not product:
        return f"Technical specifications for {product_type} not available. Please contact our technical support team for detailed product information and compatibility requirements."

    return (
        f"Technical Information - {product_type.title()}:\n\n"
        f"• Warranty: {product['warranty']}\n"
        f"• Specifications: {product['specs']}\n"
        f"• Key Features: {product['features']}\n"
        f"• Compatibility: {product['compatibility']}\n"
        f"• Support: {product['support']}"
    )


@tool
def get_technical_support(issue_description: str) -> str:
    try:
        # パラメータストアから KB ID を取得
        ssm = boto3.client("ssm")
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        region = boto3.Session().region_name

        kb_id = ssm.get_parameter(Name=f"/{account_id}-{region}/kb/knowledge-base-id")[
            "Parameter"
        ]["Value"]
        print(f"KB ID を正常に取得しました: {kb_id}")

        # strands retrieve ツールを使用
        tool_use = {
            "toolUseId": "tech_support_query",
            "input": {
                "text": issue_description,
                "knowledgeBaseId": kb_id,
                "region": region,
                "numberOfResults": 3,
                "score": 0.4,
            },
        }

        result = retrieve.retrieve(tool_use)

        if result["status"] == "success":
            return result["content"][0]["text"]
        else:
            return f"Unable to access technical support documentation. Error: {result['content'][0]['text']}"

    except Exception as e:
        print(f"get_technical_support の詳細エラー: {str(e)}")
        return f"Unable to access technical support documentation. Error: {str(e)}"
