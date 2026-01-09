"""
Insurance API 用の FastAPI アプリケーション初期化
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data_loader import InsuranceDataLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("insurance_api")

# Initialize data loader
data_loader = InsuranceDataLoader()

# Log data loading status
logger.info("データローダーが初期化されました")
logger.info(f"顧客データ読み込み完了: {len(data_loader.customers)} 件")
logger.info(f"車両データ読み込み完了: {len(data_loader.vehicles)} 件")
logger.info(f"信用レポート読み込み完了: {len(data_loader.credit_reports)} 件")
if data_loader.customers:
    logger.info(f"最初の顧客: {data_loader.customers[0].get('id', 'no-id')}")

def create_app() -> FastAPI:
    """FastAPI アプリケーションを作成・設定"""
    
    # Initialize FastAPI app
    app = FastAPI(title="Auto Insurance API")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and include routers
    from routes.general import router as general_router
    from routes.customer import router as customer_router
    from routes.vehicle import router as vehicle_router
    from routes.insurance import router as insurance_router
    from routes.policy import router as policy_router
    
    app.include_router(general_router)
    app.include_router(customer_router)
    app.include_router(vehicle_router)
    app.include_router(insurance_router)
    app.include_router(policy_router)
    
    return app

# Create the FastAPI app instance
app = create_app()