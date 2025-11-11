# common/services/yahoo_finance_service.py
import yfinance as yf
from decimal import Decimal
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class YahooFinanceService:
    """Yahoo Finance APIからデータを取得するサービスクラス"""
    
    # APIフィールドと指標定義のマッピング
    METRIC_MAPPING = {
        # ========================================
        # 収益性指標
        # ========================================
        'roe': ('returnOnEquity', lambda x: x * 100 if x else None),
        'roa': ('returnOnAssets', lambda x: x * 100 if x else None),
        'operating_margin': ('operatingMargins', lambda x: x * 100 if x else None),
        
        # ========================================
        # 成長性指標
        # ========================================
        'revenue_growth': ('revenueGrowth', lambda x: x * 100 if x else None),
        'profit_growth': ('earningsGrowth', lambda x: x * 100 if x else None),
        
        # ========================================
        # バリュエーション指標
        # ========================================
        'per': ('trailingPE', None),
        'pbr': ('priceToBook', None),
        
        # ========================================
        # 配当指標
        # ========================================
        # ✅ dividendYieldは既に%形式で返ってくる（3.03 = 3.03%）
        'dividend_rate': ('dividendRate', None),
        'dividend_yield': ('dividendYield', None),
        'payout_ratio': ('payoutRatio', lambda x: x * 100 if x else None),
        
        # ========================================
        # 財務健全性指標
        # ========================================
        # ⚠️ 日本株ではtotalStockholderEquity, totalAssetsが取得不可
        'equity_ratio': ('_calc_equity_ratio', None),  # debtToEquityから逆算
        'debt_equity_ratio': ('debtToEquity', None),
        'current_ratio': ('currentRatio', lambda x: x * 100 if x else None),
        
        # ========================================
        # 規模・実績指標
        # ========================================
        'market_cap': ('marketCap', lambda x: x / 100000000 if x else None),  # 円→億円
        'revenue': ('totalRevenue', lambda x: x / 100000000 if x else None),  # 円→億円
        'operating_profit': ('_calc_operating_profit', None),  # 売上高×営業利益率
    }
    
    @staticmethod
    def get_ticker_symbol(company_code: str) -> str:
        """企業コードからYahoo Financeのティッカーシンボルを生成"""
        return f"{company_code}.T"
    
    @classmethod
    def fetch_company_data(cls, company_code: str, fiscal_year: Optional[str] = None) -> Dict[str, Decimal]:
        """
        企業の財務データを取得
        
        Args:
            company_code: 企業コード（例: 7203）
            fiscal_year: 会計年度（現在は未使用）
        
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
                # ✅ 自己資本比率は特殊処理
                if api_field == '_calc_equity_ratio':
                    equity_ratio = cls._calculate_equity_ratio(info)
                    if equity_ratio is not None:
                        result[metric_name] = Decimal(str(round(equity_ratio, 2)))
                    continue
                
                # ✅ 営業利益は特殊処理
                if api_field == '_calc_operating_profit':
                    operating_profit = cls._calculate_operating_profit(info)
                    if operating_profit is not None:
                        result[metric_name] = Decimal(str(round(operating_profit, 2)))
                    continue
                
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
    
    @staticmethod
    def _calculate_equity_ratio(info: dict) -> Optional[float]:
        """
        自己資本比率を計算（日本株では精度制限あり）
        
        計算式: 100 / (1 + 負債比率/100) × 100
        
        ⚠️ 注意: totalStockholderEquityとtotalAssetsが取得できないため、
        debtToEquityから逆算していますが、完全に正確ではありません。
        
        正確な計算式:
        - 負債比率(D/E) = 総負債 ÷ 自己資本
        - 自己資本比率 = 自己資本 ÷ (自己資本 + 総負債)
        -              = 1 ÷ (1 + D/E)
        
        Args:
            info: yfinanceから取得した企業情報
        
        Returns:
            自己資本比率（%）、または計算不可の場合None
        """
        debt_to_equity = info.get('debtToEquity')
        
        if debt_to_equity is not None and debt_to_equity >= 0:
            # debtToEquityは既に%形式（103.66 = 103.66%）
            equity_ratio = (1 / (1 + debt_to_equity / 100)) * 100
            return equity_ratio
        
        return None
    
    @staticmethod
    def _calculate_operating_profit(info: dict) -> Optional[float]:
        """
        営業利益を計算（億円単位）
        
        計算式: 売上高 × 営業利益率 ÷ 100,000,000
        
        Args:
            info: yfinanceから取得した企業情報
        
        Returns:
            営業利益（億円）、または計算不可の場合None
        """
        revenue = info.get('totalRevenue')
        operating_margin = info.get('operatingMargins')
        
        if revenue and operating_margin:
            # 営業利益 = 売上高 × 営業利益率
            operating_profit = revenue * operating_margin
            # 円 → 億円
            return operating_profit / 100000000
        
        return None
    
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