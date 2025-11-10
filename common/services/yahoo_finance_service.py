# common/services/yahoo_finance_service.py
import yfinance as yf
from decimal import Decimal
from typing import Dict, Optional

import logging

# ⭐ loggerを初期化
logger = logging.getLogger(__name__)

class YahooFinanceService:
    """Yahoo Finance APIからデータを取得するサービスクラス"""
    
    # APIフィールドと指標定義のマッピング
    METRIC_MAPPING = {
        # 収益性指標
        'roe': ('returnOnEquity', lambda x: x * 100 if x else None),  # 小数→%
        'roa': ('returnOnAssets', lambda x: x * 100 if x else None),
        'operating_margin': ('operatingMargins', lambda x: x * 100 if x else None),
        'profit_margin': ('profitMargins', lambda x: x * 100 if x else None),
        
        # バリュエーション指標
        'per': ('trailingPE', None),
        'forward_per': ('forwardPE', None),
        'pbr': ('priceToBook', None),
        'psr': ('priceToSalesTrailing12Months', None),
        
        # 配当指標
        'dividend_yield': ('dividendYield', lambda x: x * 100 if x else None),
        'dividend_rate': ('dividendRate', None),
        'payout_ratio': ('payoutRatio', lambda x: x * 100 if x else None),
        
        # 財務健全性指標
        'equity_ratio': ('debtToEquity', lambda x: 100 - x if x else None),  # 負債比率→自己資本比率
        'debt_equity_ratio': ('debtToEquity', None),
        'current_ratio': ('currentRatio', lambda x: x * 100 if x else None),
        'quick_ratio': ('quickRatio', lambda x: x * 100 if x else None),
        
        # 成長性指標
        'revenue_growth': ('revenueGrowth', lambda x: x * 100 if x else None),
        'earnings_growth': ('earningsGrowth', lambda x: x * 100 if x else None),
        
        # 規模・実績指標
        'market_cap': ('marketCap', lambda x: x / 100000000 if x else None),  # 円→億円
        'revenue': ('totalRevenue', lambda x: x / 100000000 if x else None),
        'total_assets': ('totalAssets', lambda x: x / 100000000 if x else None),
        'eps': ('trailingEps', None),
        'forward_eps': ('forwardEps', None),
        'beta': ('beta', None),
        
        # 効率性指標
        'asset_turnover': ('assetTurnover', None),
    }
    
    @staticmethod
    def get_ticker_symbol(company_code: str) -> str:
        """企業コードからYahoo Financeのティッカーシンボルを生成"""
        # 日本株の場合は .T を付ける
        return f"{company_code}.T"
    
    @classmethod
    def fetch_company_data(cls, company_code: str, fiscal_year: Optional[str] = None) -> Dict[str, Decimal]:
        """
        企業の財務データを取得
        
        Args:
            company_code: 企業コード（例: 7203）
            fiscal_year: 会計年度（現在は未使用、将来的に履歴データ取得に使用）
        
        Returns:
            指標名とその値の辞書
        """
        ticker_symbol = cls.get_ticker_symbol(company_code)
        
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            if not info:
                logger.warning(f"No data found for {ticker_symbol}")
                return {}
            
            result = {}
            
            # マッピングに基づいてデータを取得
            for metric_name, (api_field, transform) in cls.METRIC_MAPPING.items():
                value = info.get(api_field)
                
                if value is not None:
                    # 変換関数があれば適用
                    if transform:
                        value = transform(value)
                    
                    # Decimalに変換
                    if value is not None:
                        try:
                            result[metric_name] = Decimal(str(round(value, 2)))
                        except (ValueError, TypeError):
                            logger.warning(f"Failed to convert {metric_name}={value} to Decimal")
                            continue
            
            logger.info(f"Successfully fetched {len(result)} metrics for {company_code}")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker_symbol}: {str(e)}")
            return {}
    
    @classmethod
    def fetch_bulk_data(cls, company_codes: list, fiscal_year: Optional[str] = None) -> Dict[str, Dict[str, Decimal]]:
        """
        複数企業のデータを一括取得
        
        Args:
            company_codes: 企業コードのリスト
            fiscal_year: 会計年度
        
        Returns:
            {企業コード: {指標名: 値}} の辞書
        """
        results = {}
        
        for code in company_codes:
            data = cls.fetch_company_data(code, fiscal_year)
            if data:
                results[code] = data
        
        return results
    
    @classmethod
    def get_available_metrics(cls) -> list:
        """取得可能な指標のリストを返す"""
        return list(cls.METRIC_MAPPING.keys())
    
    @classmethod
    def validate_ticker(cls, company_code: str) -> bool:
        """ティッカーシンボルが有効かチェック"""
        ticker_symbol = cls.get_ticker_symbol(company_code)
        
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            return bool(info and 'symbol' in info)
        except:
            return False