from ddgs import DDGS


def web_search(keywords: str, region: str = "us-en", max_results: int = 5) -> str:
    """最新の情報を Web 検索する。

    Args:
        keywords (str): 検索クエリのキーワード。
        region (str): 検索リージョン: wt-wt, us-en, uk-en, ru-ru など。
        max_results (int): 返す結果の最大数。

    Returns:
        検索結果の辞書リスト。
    """
    try:
        results = DDGS().text(keywords, region=region, max_results=max_results)
        return results if results else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"


print("✅ Web search tool ready")
