# investment_review/services/portfolio_analyzer.py
import yfinance as yf
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, List, Optional
import requests
from datetime import datetime, timedelta
from stockdiary.models import StockDiary
from django.db.models import Q, Sum, Avg, Count
import time

logger = logging.getLogger(__name__)


class PortfolioAnalyzer:
    """現在保有株式のポートフォリオ分析サービス"""
    
    def __init__(self):
        self.api_delay = 1  # API呼び出し間隔（秒）
        
    def analyze_current_portfolio(self, user) -> Dict[str, Any]:
        """現在保有している株式のポートフォリオを分析"""
        try:
            # 現在保有中の株式を取得
            holdings = self._get_current_holdings(user)
            
            if not holdings:
                return {
                    'status': 'no_holdings',
                    'message': '現在保有している株式がありません。',
                    'holdings': []
                }
            
            logger.info(f"ポートフォリオ分析開始: {len(holdings)}銘柄")
            
            # 各銘柄の詳細情報を取得
            detailed_holdings = []
            total_value = 0
            
            for holding in holdings:
                detail = self._analyze_single_holding(holding)
                if detail:
                    detailed_holdings.append(detail)
                    # None値をチェックしてから加算
                    current_value = detail.get('current_value')
                    if current_value is not None:
                        total_value += current_value
                time.sleep(self.api_delay)  # API制限対策
            
            # 有効なデータがある銘柄のみをフィルタリング
            valid_holdings = [
                h for h in detailed_holdings 
                if h.get('current_value') is not None and 
                h.get('stock_symbol') and 
                h.get('stock_name') and 
                h.get('stock_name').strip() != ''
            ]
            
            # 無効なデータがある場合はログに記録
            invalid_count = len(detailed_holdings) - len(valid_holdings)
            if invalid_count > 0:
                logger.warning(f"無効なデータの銘柄を {invalid_count} 件除外しました")
            
            # 有効な銘柄がない場合
            if not valid_holdings:
                return {
                    'status': 'no_valid_holdings',
                    'message': '有効なポートフォリオデータがありません。',
                    'holdings': []
                }
            
            # ポートフォリオ全体の分析（有効な銘柄のみ使用）
            portfolio_analysis = self._analyze_portfolio_composition(valid_holdings, total_value)
            
            # セクター分析
            sector_analysis = self._analyze_sector_distribution(valid_holdings)
            
            # リスク分析
            risk_analysis = self._analyze_portfolio_risk(valid_holdings)
            
            # パフォーマンス分析
            performance_analysis = self._analyze_portfolio_performance(valid_holdings)
            
            return {
                'status': 'success',
                'total_holdings': len(valid_holdings),
                'total_portfolio_value': total_value,
                'holdings': valid_holdings,
                'portfolio_analysis': portfolio_analysis,
                'sector_analysis': sector_analysis,
                'risk_analysis': risk_analysis,
                'performance_analysis': performance_analysis,
                'analysis_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"ポートフォリオ分析エラー: {e}")
            return {
                'status': 'error',
                'message': f'分析中にエラーが発生しました: {str(e)}',
                'holdings': []
            }

    
    def _get_current_holdings(self, user) -> List[StockDiary]:
        """現在保有している株式を取得"""
        return StockDiary.objects.filter(
            user=user,
            sell_date__isnull=True,  # 未売却
            purchase_price__isnull=False,  # 購入価格あり
            purchase_quantity__isnull=False,  # 購入数量あり
            is_memo=False  # メモ記録除外
        ).select_related('user').prefetch_related('tags')
    
    def _analyze_single_holding(self, diary: StockDiary) -> Dict[str, Any]:
        """個別銘柄の分析"""
        try:
            # まず基本的な検証を実行
            stock_symbol = (diary.stock_symbol or '').strip()
            stock_name = (diary.stock_name or '').strip()
            
            # 無効なデータの場合はNoneを返す
            if not stock_symbol or not stock_name or len(stock_name) < 2:
                logger.warning(f"無効な銘柄データをスキップ: symbol={stock_symbol}, name={stock_name}")
                return None
            
            # 購入価格と数量の検証
            if not diary.purchase_price or not diary.purchase_quantity:
                logger.warning(f"購入価格または数量が無効: {stock_name}")
                return self._create_basic_holding_info(diary)
            
            # 日本株式のティッカー形式に変換
            ticker_symbol = self._format_ticker_symbol(stock_symbol)
            
            if not ticker_symbol:
                return self._create_basic_holding_info(diary)
            
            # Yahoo Finance から株価情報を取得
            ticker = yf.Ticker(ticker_symbol)
            
            # 基本情報取得
            info = ticker.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            # 株価が取得できない場合は基本情報のみ返す
            if not current_price or current_price <= 0:
                return self._create_basic_holding_info(diary)
            
            # 投資額と現在価値を計算
            investment_amount = float(diary.purchase_price * diary.purchase_quantity)
            current_value = current_price * diary.purchase_quantity
            
            # 損益計算
            unrealized_gain_loss = current_value - investment_amount
            unrealized_gain_loss_pct = (unrealized_gain_loss / investment_amount) * 100
            
            # ファンダメンタル指標
            fundamentals = self._extract_fundamental_metrics(info)
            
            # テクニカル指標
            technical = self._calculate_technical_indicators(ticker, current_price)
            
            return {
                'diary_id': diary.id,
                'stock_symbol': stock_symbol,
                'stock_name': stock_name,
                'sector': diary.sector or info.get('sector', 'その他'),
                'purchase_date': diary.purchase_date.isoformat(),
                'purchase_price': float(diary.purchase_price),
                'purchase_quantity': diary.purchase_quantity,
                'current_price': current_price,
                'investment_amount': investment_amount,
                'current_value': current_value,
                'unrealized_gain_loss': unrealized_gain_loss,
                'unrealized_gain_loss_pct': unrealized_gain_loss_pct,
                'holding_period_days': (timezone.now().date() - diary.purchase_date).days,
                'fundamentals': fundamentals,
                'technical': technical,
                'market_cap': info.get('marketCap'),
                'industry': info.get('industry'),
                'country': info.get('country', 'Japan'),
                'tags': [tag.name for tag in diary.tags.all()],
                'data_available': True
            }
            
        except Exception as e:
            logger.warning(f"銘柄分析エラー ({diary.stock_symbol}): {e}")
            return self._create_basic_holding_info(diary)

    
    def _format_ticker_symbol(self, symbol: str) -> Optional[str]:
        """株式コードをYahoo Finance用ティッカーに変換"""
        if not symbol:
            return None
        
        # 日本株の場合
        if symbol.isdigit() and len(symbol) == 4:
            return f"{symbol}.T"  # 東証
        
        # 既にティッカー形式の場合
        if '.' in symbol:
            return symbol
        
        # その他の形式
        return symbol
    
    def _create_basic_holding_info(self, diary: StockDiary) -> Dict[str, Any]:
        """基本的な保有情報を作成（外部データ取得失敗時のフォールバック）"""
        purchase_price = diary.purchase_price or 0
        purchase_quantity = diary.purchase_quantity or 0
        investment_amount = float(purchase_price * purchase_quantity) if purchase_price and purchase_quantity else 0
        
        # 株式シンボルや名前の検証
        stock_symbol = (diary.stock_symbol or '').strip()
        stock_name = (diary.stock_name or '').strip()
        
        # 無効なデータの場合はNoneを返す
        if not stock_symbol or not stock_name or len(stock_name) < 2:
            logger.warning(f"無効な銘柄データ: symbol={stock_symbol}, name={stock_name}")
            return None
        
        return {
            'diary_id': diary.id,
            'stock_symbol': stock_symbol,
            'stock_name': stock_name,
            'sector': diary.sector or 'その他',
            'purchase_date': diary.purchase_date.isoformat(),
            'purchase_price': float(purchase_price),
            'purchase_quantity': purchase_quantity,
            'current_price': None,
            'investment_amount': investment_amount,
            'current_value': 0.0,  # Noneではなく0.0に設定
            'unrealized_gain_loss': 0.0,  # Noneではなく0.0に設定
            'unrealized_gain_loss_pct': 0.0,  # Noneではなく0.0に設定
            'holding_period_days': (timezone.now().date() - diary.purchase_date).days,
            'fundamentals': {},
            'technical': {},
            'market_cap': None,
            'industry': None,
            'country': 'Japan',
            'tags': [tag.name for tag in diary.tags.all()],
            'data_available': False
        }
    
    def _extract_fundamental_metrics(self, info: dict) -> Dict[str, Any]:
        """ファンダメンタル指標を抽出"""
        return {
            'pe_ratio': info.get('trailingPE'),
            'pb_ratio': info.get('priceToBook'),
            'dividend_yield': info.get('dividendYield'),
            'roe': info.get('returnOnEquity'),
            'debt_to_equity': info.get('debtToEquity'),
            'profit_margins': info.get('profitMargins'),
            'revenue_growth': info.get('revenueGrowth'),
            'earnings_growth': info.get('earningsGrowth'),
            'current_ratio': info.get('currentRatio'),
            'book_value': info.get('bookValue'),
            'enterprise_value': info.get('enterpriseValue'),
            'ebitda': info.get('ebitda')
        }
    
    def _calculate_technical_indicators(self, ticker, current_price) -> Dict[str, Any]:
        """テクニカル指標を計算"""
        try:
            # 過去6ヶ月のデータを取得
            hist = ticker.history(period="6mo")
            
            if hist.empty:
                return {}
            
            # 移動平均の計算
            ma_5 = hist['Close'].rolling(window=5).mean().iloc[-1] if len(hist) >= 5 else None
            ma_25 = hist['Close'].rolling(window=25).mean().iloc[-1] if len(hist) >= 25 else None
            ma_75 = hist['Close'].rolling(window=75).mean().iloc[-1] if len(hist) >= 75 else None
            
            # RSIの計算
            rsi = self._calculate_rsi(hist['Close']) if len(hist) >= 14 else None
            
            # ボラティリティ（標準偏差）
            volatility = hist['Close'].pct_change().std() * (252 ** 0.5) if len(hist) > 1 else None
            
            # 52週高値・安値との比較
            week_52_high = hist['High'].max()
            week_52_low = hist['Low'].min()
            price_vs_52w_high = ((current_price - week_52_high) / week_52_high * 100) if week_52_high else None
            price_vs_52w_low = ((current_price - week_52_low) / week_52_low * 100) if week_52_low else None
            
            return {
                'ma_5': ma_5,
                'ma_25': ma_25,
                'ma_75': ma_75,
                'rsi': rsi,
                'volatility': volatility,
                'week_52_high': week_52_high,
                'week_52_low': week_52_low,
                'price_vs_52w_high': price_vs_52w_high,
                'price_vs_52w_low': price_vs_52w_low,
                'trend_signal': self._determine_trend_signal(current_price, ma_5, ma_25, ma_75)
            }
            
        except Exception as e:
            logger.warning(f"テクニカル指標計算エラー: {e}")
            return {}
    
    def _calculate_rsi(self, prices, period=14):
        """RSI（相対力指数）を計算"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1] if not rsi.empty else None
        except:
            return None
    
    def _determine_trend_signal(self, current_price, ma_5, ma_25, ma_75):
        """トレンドシグナルを判定"""
        if not all([ma_5, ma_25]):
            return 'insufficient_data'
        
        if current_price > ma_5 > ma_25:
            return 'strong_uptrend'
        elif current_price > ma_25 and ma_5 > ma_25:
            return 'uptrend'
        elif current_price < ma_5 < ma_25:
            return 'strong_downtrend'
        elif current_price < ma_25 and ma_5 < ma_25:
            return 'downtrend'
        else:
            return 'sideways'
    
    def _analyze_portfolio_composition(self, holdings: List[Dict], total_value: float) -> Dict[str, Any]:
        """ポートフォリオ構成の分析"""
        if not holdings or total_value == 0:
            return {}
        
        # 銘柄数と集中度
        num_holdings = len(holdings)
        
        # 投資額上位銘柄の集中度（None値を除外）
        holdings_with_value = [h for h in holdings if h.get('current_value') is not None and h.get('current_value') > 0]
        holdings_by_value = sorted(holdings_with_value, key=lambda x: x.get('current_value', 0), reverse=True)
        
        top_3_value = sum(h.get('current_value', 0) for h in holdings_by_value[:3])
        top_5_value = sum(h.get('current_value', 0) for h in holdings_by_value[:5])
        
        top_3_concentration = (top_3_value / total_value * 100) if total_value > 0 else 0
        top_5_concentration = (top_5_value / total_value * 100) if total_value > 0 else 0
        
        # 平均保有期間
        avg_holding_period = sum(h.get('holding_period_days', 0) for h in holdings) / len(holdings) if holdings else 0
        
        # 損益状況（None値を除外）
        profitable_count = len([h for h in holdings if h.get('unrealized_gain_loss') is not None and h.get('unrealized_gain_loss') > 0])
        losing_count = len([h for h in holdings if h.get('unrealized_gain_loss') is not None and h.get('unrealized_gain_loss') < 0])
        
        return {
            'num_holdings': num_holdings,
            'top_3_concentration': top_3_concentration,
            'top_5_concentration': top_5_concentration,
            'avg_holding_period_days': avg_holding_period,
            'profitable_positions': profitable_count,
            'losing_positions': losing_count,
            'win_rate': (profitable_count / num_holdings * 100) if num_holdings > 0 else 0,
            'diversification_score': self._calculate_diversification_score(num_holdings, top_5_concentration)
        }
    
    def _analyze_sector_distribution(self, holdings: List[Dict]) -> Dict[str, Any]:
        """セクター分散の分析"""
        sector_distribution = {}
        total_value = 0
        
        # 有効な値のみを計算に使用
        for holding in holdings:
            current_value = holding.get('current_value')
            if current_value is not None:
                total_value += current_value
        
        for holding in holdings:
            sector = holding.get('sector', 'その他')
            value = holding.get('current_value', 0)
            
            # None値の場合は0として扱う
            if value is None:
                value = 0
            
            if sector in sector_distribution:
                sector_distribution[sector]['value'] += value
                sector_distribution[sector]['count'] += 1
            else:
                sector_distribution[sector] = {'value': value, 'count': 1}
        
        # パーセンテージを計算
        for sector, data in sector_distribution.items():
            data['percentage'] = (data['value'] / total_value * 100) if total_value > 0 else 0
        
        # セクター集中度
        max_sector_concentration = max([data['percentage'] for data in sector_distribution.values()]) if sector_distribution else 0
        
        return {
            'sector_distribution': sector_distribution,
            'num_sectors': len(sector_distribution),
            'max_sector_concentration': max_sector_concentration,
            'sector_diversification_score': self._calculate_sector_diversification_score(sector_distribution)
        }
    
    def _analyze_portfolio_risk(self, holdings: List[Dict]) -> Dict[str, Any]:
        """ポートフォリオリスクの分析"""
        if not holdings:
            return {}
        
        # ボラティリティの分析
        volatilities = [h.get('technical', {}).get('volatility') for h in holdings if h.get('technical', {}).get('volatility')]
        avg_volatility = sum(volatilities) / len(volatilities) if volatilities else None
        
        # バリュエーションリスク（PER, PBR分析）
        pe_ratios = [h.get('fundamentals', {}).get('pe_ratio') for h in holdings if h.get('fundamentals', {}).get('pe_ratio')]
        pb_ratios = [h.get('fundamentals', {}).get('pb_ratio') for h in holdings if h.get('fundamentals', {}).get('pb_ratio')]
        
        avg_pe = sum(pe_ratios) / len(pe_ratios) if pe_ratios else None
        avg_pb = sum(pb_ratios) / len(pb_ratios) if pb_ratios else None
        
        # 高PER銘柄（PER > 30）の比率
        high_pe_count = len([pe for pe in pe_ratios if pe > 30]) if pe_ratios else 0
        high_pe_ratio = (high_pe_count / len(holdings) * 100) if holdings else 0
        
        # 流動性リスク（小型株比率）
        small_cap_count = len([h for h in holdings if h.get('market_cap') and h.get('market_cap') < 100e9])  # 時価総額1000億円未満
        small_cap_ratio = (small_cap_count / len(holdings) * 100) if holdings else 0
        
        return {
            'avg_volatility': avg_volatility,
            'avg_pe_ratio': avg_pe,
            'avg_pb_ratio': avg_pb,
            'high_pe_ratio': high_pe_ratio,
            'small_cap_ratio': small_cap_ratio,
            'risk_level': self._determine_risk_level(avg_volatility, high_pe_ratio, small_cap_ratio)
        }
    
    def _analyze_portfolio_performance(self, holdings: List[Dict]) -> Dict[str, Any]:
        """ポートフォリオパフォーマンスの分析"""
        if not holdings:
            return {}
        
        # 全体の損益（None値を除外）
        total_investment = 0
        total_current_value = 0
        
        for h in holdings:
            investment = h.get('investment_amount', 0)
            current_value = h.get('current_value', 0)
            
            if investment is not None:
                total_investment += investment
            if current_value is not None:
                total_current_value += current_value
        
        if total_investment > 0:
            total_return_pct = ((total_current_value - total_investment) / total_investment * 100)
        else:
            total_return_pct = 0
        
        # 個別銘柄のパフォーマンス分析（None値を除外）
        returns = []
        for h in holdings:
            gain_loss_pct = h.get('unrealized_gain_loss_pct')
            if gain_loss_pct is not None:
                returns.append(gain_loss_pct)
        
        if returns:
            best_performer = max(returns)
            worst_performer = min(returns)
            avg_return = sum(returns) / len(returns)
        else:
            best_performer = worst_performer = avg_return = 0
        
        return {
            'total_investment': total_investment,
            'total_current_value': total_current_value,
            'total_return_pct': total_return_pct,
            'best_performer_pct': best_performer,
            'worst_performer_pct': worst_performer,
            'avg_return_pct': avg_return,
            'performance_consistency': self._calculate_performance_consistency(returns)
        }
    
    def _calculate_diversification_score(self, num_holdings: int, top_5_concentration: float) -> str:
        """分散投資スコアを計算"""
        if num_holdings >= 20 and top_5_concentration < 60:
            return 'excellent'
        elif num_holdings >= 15 and top_5_concentration < 70:
            return 'good'
        elif num_holdings >= 10 and top_5_concentration < 80:
            return 'moderate'
        elif num_holdings >= 5:
            return 'limited'
        else:
            return 'poor'
    
    def _calculate_sector_diversification_score(self, sector_distribution: Dict) -> str:
        """セクター分散スコアを計算"""
        if not sector_distribution:
            return 'none'
        
        num_sectors = len(sector_distribution)
        max_concentration = max([data['percentage'] for data in sector_distribution.values()])
        
        if num_sectors >= 8 and max_concentration < 30:
            return 'excellent'
        elif num_sectors >= 6 and max_concentration < 40:
            return 'good'
        elif num_sectors >= 4 and max_concentration < 50:
            return 'moderate'
        elif num_sectors >= 2:
            return 'limited'
        else:
            return 'poor'
    
    def _determine_risk_level(self, avg_volatility: Optional[float], high_pe_ratio: float, small_cap_ratio: float) -> str:
        """リスクレベルを判定"""
        risk_score = 0
        
        # ボラティリティリスク
        if avg_volatility and avg_volatility > 0.4:
            risk_score += 3
        elif avg_volatility and avg_volatility > 0.25:
            risk_score += 2
        elif avg_volatility and avg_volatility > 0.15:
            risk_score += 1
        
        # バリュエーションリスク
        if high_pe_ratio > 50:
            risk_score += 3
        elif high_pe_ratio > 30:
            risk_score += 2
        elif high_pe_ratio > 15:
            risk_score += 1
        
        # 流動性リスク
        if small_cap_ratio > 70:
            risk_score += 3
        elif small_cap_ratio > 50:
            risk_score += 2
        elif small_cap_ratio > 30:
            risk_score += 1
        
        if risk_score >= 7:
            return 'very_high'
        elif risk_score >= 5:
            return 'high'
        elif risk_score >= 3:
            return 'moderate'
        elif risk_score >= 1:
            return 'low'
        else:
            return 'very_low'
    
    def _calculate_performance_consistency(self, returns: List[float]) -> str:
        """パフォーマンスの一貫性を評価"""
        if not returns or len(returns) < 2:
            return 'insufficient_data'
        
        import statistics
        std_dev = statistics.stdev(returns)
        
        if std_dev < 10:
            return 'very_consistent'
        elif std_dev < 20:
            return 'consistent'
        elif std_dev < 35:
            return 'moderate'
        elif std_dev < 50:
            return 'inconsistent'
        else:
            return 'very_inconsistent'

    def get_market_context(self) -> Dict[str, Any]:
        """現在の市場環境情報を取得"""
        try:
            # 主要指数の情報を取得
            nikkei = yf.Ticker("^N225")  # 日経平均
            spy = yf.Ticker("SPY")  # S&P 500
            usdjpy = yf.Ticker("USDJPY=X")  # ドル円
            
            market_data = {}
            
            # 日経平均の情報
            nikkei_info = nikkei.history(period="5d")
            if not nikkei_info.empty:
                current_nikkei = nikkei_info['Close'].iloc[-1]
                prev_nikkei = nikkei_info['Close'].iloc[-2] if len(nikkei_info) > 1 else current_nikkei
                nikkei_change = ((current_nikkei - prev_nikkei) / prev_nikkei * 100)
                
                market_data['nikkei'] = {
                    'current': current_nikkei,
                    'change_pct': nikkei_change
                }
            
            # ドル円レート
            usdjpy_info = usdjpy.history(period="5d")
            if not usdjpy_info.empty:
                current_usdjpy = usdjpy_info['Close'].iloc[-1]
                prev_usdjpy = usdjpy_info['Close'].iloc[-2] if len(usdjpy_info) > 1 else current_usdjpy
                usdjpy_change = ((current_usdjpy - prev_usdjpy) / prev_usdjpy * 100)
                
                market_data['usdjpy'] = {
                    'current': current_usdjpy,
                    'change_pct': usdjpy_change
                }
            
            return {
                'status': 'success',
                'market_data': market_data,
                'retrieved_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.warning(f"市場情報取得エラー: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'market_data': {}
            }