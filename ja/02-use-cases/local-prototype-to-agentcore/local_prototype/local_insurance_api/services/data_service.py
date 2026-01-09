"""
Insurance API のデータアクセスサービス
"""
from typing import Dict, List, Optional, Any
import logging
from data_loader import InsuranceDataLoader
from app import data_loader

logger = logging.getLogger("insurance_api")

def get_customer_by_id(customer_id: str) -> Optional[Dict[str, Any]]:
    """ID で顧客情報を取得"""
    return data_loader.get_customer_by_id(customer_id)

def get_credit_report_by_customer_id(customer_id: str) -> Optional[Dict[str, Any]]:
    """顧客 ID で信用レポートを取得"""
    return data_loader.get_credit_report_by_customer_id(customer_id)

def get_vehicle_info(make: str, model: str, year: str or int) -> Optional[Dict[str, Any]]:
    """メーカー、モデル、年式で車両情報を取得"""
    return data_loader.get_vehicle_info(make, model, str(year))

def get_default_vehicle_info(make: str, model: str, year: int) -> Dict[str, Any]:
    """データベースに見つからない場合のデフォルト車両情報を取得"""
    return {
        "make": make,
        "model": model,
        "year": str(year),
        "display_name": f"{year} {make} {model}",
        "category": "standard",
        "safety_rating": "4_star",
        "value": 25000,
        "current_value": 20000,
        "age": 2025 - int(year),
        "is_new": int(year) >= 2024
    }

def get_all_products() -> Dict[str, Any]:
    """すべての保険商品データを取得"""
    return data_loader.products

def calculate_age_from_dob(dob: str) -> int:
    """生年月日から年齢を計算"""
    return data_loader.calculate_age_from_dob(dob)