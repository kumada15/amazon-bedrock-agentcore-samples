"""
Insurance API のポリシー関連エンドポイント
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from services import data_service, policy_service
# Removed unused import
# from services.utils import create_success_response

# Define constant for repeated error message
INTERNAL_SERVER_ERROR = "Internal server error"

# Set up logger
logger = logging.getLogger("insurance_api")

# Create router
router = APIRouter()

@router.get("/policies")
async def get_all_policies():
    """すべてのポリシーを取得"""
    try:
        policies = policy_service.get_all_policies()
        response_data = {
            "status": "success",
            "count": len(policies),
            "policies": policies
        }
        return JSONResponse(content=response_data)
    except Exception as e:
        logger.error(f"get_all_policies エンドポイントでエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.post("/policies")
async def get_filtered_policies(request: Request):
    """
    オプションのフィルタリングでポリシーを取得

    Optional parameters:
    - policy_id: string - 特定のポリシー ID でフィルタリング
    - customer_id: string - 顧客 ID でフィルタリング
    - status: string - ステータスでフィルタリング（active, expired など）
    - include_vehicles: boolean - レスポンスに車両詳細を含める（デフォルト: true）
    """
    try:
        # Parse request data
        data = {}
        try:
            data = await request.json()
        except ValueError:
            # Empty request body or invalid JSON is fine
            pass
        
        # Get all policies
        policies = policy_service.get_all_policies()
        
        # Filter by policy ID if provided
        policy_id = data.get("policy_id")
        if policy_id:
            policy = policy_service.get_policy_by_id(policy_id)
            policies = [policy] if policy else []
        
        # Filter by customer ID if provided
        customer_id = data.get("customer_id")
        if customer_id:
            policies = policy_service.get_policies_by_customer_id(customer_id)
        
        # Filter by status if provided
        status = data.get("status")
        if status:
            policies = policy_service.filter_policies_by_status(policies, status)
        
        # Create formatted response
        response_data = policy_service.create_policy_response(policies, data)
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"get_filtered_policies エンドポイントでエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.get("/policies/{policy_id}")
async def get_policy_by_id(policy_id: str):
    """ID で特定のポリシーを取得"""
    try:
        policy = policy_service.get_policy_by_id(policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
        
        response_data = {
            "status": "success",
            "policy": policy
        }
        return JSONResponse(content=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_policy_by_id エンドポイントでエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.get("/customer/{customer_id}/policies")
async def get_customer_policies(customer_id: str):
    """特定の顧客のすべてのポリシーを取得"""
    try:
        # Verify customer exists
        customer = data_service.get_customer_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
            
        # Get customer policies
        policies = policy_service.get_policies_by_customer_id(customer_id)
        
        response_data = {
            "status": "success",
            "customer_id": customer_id,
            "count": len(policies),
            "policies": policies
        }
        return JSONResponse(content=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_customer_policies エンドポイントでエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)