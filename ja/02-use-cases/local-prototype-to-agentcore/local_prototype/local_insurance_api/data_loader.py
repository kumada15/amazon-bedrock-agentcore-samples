"""
保険 API 用データローダー - data フォルダからデータを読み込む
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

class InsuranceDataLoader:
    def __init__(self, data_path: str = None):
        """データディレクトリへのパスでデータローダーを初期化"""
        if data_path is None:
            # Default to data folder in parent directory
            current_dir = Path(__file__).parent
            self.data_path = current_dir.parent / "data"
        else:
            self.data_path = Path(data_path)
        
        self._customers = None
        self._credit_reports = None
        self._vehicles = None
        self._products = None
        self._pricing_rules = None
        self._policies = None
        
    def _load_json_file(self, filename: str) -> Dict:
        """データディレクトリから JSON ファイルを読み込む"""
        file_path = self.data_path / filename
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                print(f"{filename} を正常に読み込みました ({len(str(data))} 文字)")
                return data
        except FileNotFoundError:
            print(f"警告: {filename} が {file_path} に見つかりません")
            # Try alternative paths
            alternative_paths = [
                Path("/opt/data") / filename,  # Lambda /opt directory
                Path("./data") / filename,     # Current directory
                Path("../data") / filename,    # Parent directory
            ]
            for alt_path in alternative_paths:
                try:
                    with open(alt_path, 'r') as f:
                        data = json.load(f)
                        print(f"代替パスで {filename} を見つけました: {alt_path}")
                        return data
                except:
                    continue
            print(f"どの場所にも {filename} が見つかりませんでした")
            return {}
        except json.JSONDecodeError as e:
            print(f"{filename} の解析エラー: {e}")
            return {}
    
    @property
    def customers(self) -> List[Dict]:
        """顧客データを取得"""
        if self._customers is None:
            data = self._load_json_file("customers.json")
            self._customers = data.get("customers", [])
        return self._customers
    
    @property
    def credit_reports(self) -> List[Dict]:
        """信用レポートデータを取得"""
        if self._credit_reports is None:
            data = self._load_json_file("credit_reports.json")
            self._credit_reports = data.get("reports", [])
        return self._credit_reports
    
    @property
    def vehicles(self) -> List[Dict]:
        """車両データを取得"""
        if self._vehicles is None:
            data = self._load_json_file("vehicles.json")
            self._vehicles = data.get("vehicles", [])
        return self._vehicles
    
    @property
    def products(self) -> Dict:
        """商品データを取得"""
        if self._products is None:
            self._products = self._load_json_file("products.json")
        return self._products
    
    @property
    def pricing_rules(self) -> Dict:
        """料金ルールデータを取得"""
        if self._pricing_rules is None:
            self._pricing_rules = self._load_json_file("pricing_rules.json")
        return self._pricing_rules
    
    @property
    def policies(self) -> Dict:
        """ポリシーデータを取得"""
        if self._policies is None:
            self._policies = self._load_json_file("policies.json")
        return self._policies
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        """ID で顧客を取得"""
        for customer in self.customers:
            if customer.get("id") == customer_id:
                return customer
        return None
    
    def get_credit_report_by_customer_id(self, customer_id: str) -> Optional[Dict]:
        """顧客 ID で信用レポートを取得"""
        for report in self.credit_reports:
            if report.get("customer_id") == customer_id:
                return report
        return None
    
    def get_vehicle_info(self, make: str, model: str, year: str) -> Optional[Dict]:
        """メーカー、モデル、年式で車両情報を取得"""
        year_int = int(year)
        for vehicle in self.vehicles:
            if (vehicle.get("make", "").lower() == make.lower() and 
                vehicle.get("model", "").lower() == model.lower() and
                year_int in vehicle.get("years", [])):
                
                # Create vehicle info with year-specific data
                vehicle_info = vehicle.copy()
                vehicle_info["year"] = year
                vehicle_info["value"] = vehicle.get("base_value", {}).get(str(year), 25000)
                vehicle_info["current_value"] = int(vehicle_info["value"] * 0.85)  # Depreciation
                vehicle_info["age"] = 2025 - year_int
                vehicle_info["is_new"] = year_int >= 2024
                vehicle_info["display_name"] = f"{year} {make} {model}"
                
                return vehicle_info
        return None
    
    def calculate_age_from_dob(self, dob: str) -> int:
        """生年月日文字列（YYYY-MM-DD）から年齢を計算"""
        try:
            birth_date = datetime.strptime(dob, "%Y-%m-%d")
            today = datetime.now()
            age = today.year - birth_date.year
            if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
                age -= 1
            return age
        except:
            return 30  # Default age if parsing fails
