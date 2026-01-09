"""
Insurance API のユーティリティ関数
"""
from typing import Dict, List, Optional, Any

def get_product_recommendation(product_id: str) -> str:
    """商品 ID に基づいて推奨テキストを返す"""
    if product_id == "basic-auto":
        return "New drivers, budget-conscious individuals, or second vehicles"
    elif product_id == "standard-auto":
        return "Families, daily commuters, and drivers with assets to protect"
    elif product_id == "premium-auto":
        return "Luxury vehicle owners, high-value asset protection, and maximum peace of mind"
    else:
        return "Drivers seeking quality coverage"

def create_success_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """標準化された成功レスポンスを作成"""
    return {
        "status": "success",
        **data
    }