"""
Insurance API の保険関連エンドポイント
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
# Import using a function pattern to avoid circular imports
def get_services():
    from local_insurance_api.services import data_service, product_service
    return data_service, product_service
from local_insurance_api.services.utils import create_success_response

# Set up logger
logger = logging.getLogger("insurance_api")

# Create router
router = APIRouter()

@router.post("/risk_factors")
async def get_risk_factors(request: Request):
    """保険見積もりのリスク要因を取得"""
    try:
        data = await request.json()
        customer_id = data.get("customer_id")
        vehicle_info = data.get("vehicle_info", {})
        
        if not customer_id:
            raise HTTPException(status_code=400, detail="Missing customer_id parameter")
        
        # Mock risk assessment based on customer and vehicle
        risk_factors = {
            "age_risk": "low",
            "driving_history_risk": "low", 
            "credit_risk": "low",
            "vehicle_risk": "medium",
            "overall_risk": "low"
        }
        
        response_data = {
            "status": "success",
            "risk_factors": risk_factors
        }
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"risk_factors エンドポイントでエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/insurance_products")
async def get_insurance_products(request: Request):
    """利用可能な保険商品を取得

    オプションパラメータ:
    - product_id: string または list - 特定の商品 ID でフィルタリング
    - price_range: dict - 'min' および/または 'max' キーで価格帯をフィルタリング
    - coverage_includes: list - 特定の補償タイプを含む商品をフィルタリング
    - discount_includes: list - 特定の割引を提供する商品をフィルタリング
    - sort_by: string - 'price'、'rating'、または 'name' でソート
    - sort_order: string - 'asc' または 'desc'（デフォルト: 'asc'）
    - include_details: boolean - 完全な詳細または基本情報を含める（デフォルト: true）
    - format: string - 'full' または 'summary' レスポンス形式（デフォルト: 'full'）
    """
    try:
        # Parse request data
        data = {}
        try:
            data = await request.json()
        except:
            # Empty request body is fine
            pass
        
        # Get services using the function to avoid circular imports
        data_service, product_service = get_services()
        
        # Get products from real data
        products_data = data_service.get_all_products()
        products = products_data.get("products", [])
        discounts = products_data.get("discounts", [])
        
        # Apply filters
        products = product_service.filter_products_by_id(products, data.get("product_id"))
        products = product_service.filter_products_by_price_range(products, data.get("price_range"))
        products = product_service.filter_products_by_coverage(products, data.get("coverage_includes"))
        products = product_service.filter_products_by_discounts(products, data.get("discount_includes"))
        
        # Apply sorting
        products = product_service.sort_products(products, data.get("sort_by"), data.get("sort_order", "asc"))
        
        # Create formatted response
        response_data = product_service.create_product_response(products, discounts, data)
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"insurance_products エンドポイントでエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")