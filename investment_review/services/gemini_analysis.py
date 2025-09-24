# investment_review/services/gemini_analysis.py
import google.generativeai as genai
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timedelta
from stockdiary.models import StockDiary, DiaryNote
from analysis_template.models import DiaryAnalysisValue
from tags.models import Tag
from django.db.models import Count, Avg, Sum, Q
from .portfolio_analyzer import PortfolioAnalyzer

logger = logging.getLogger(__name__)


class GeminiInvestmentAnalyzer:
    """Gemini APIを使った投資記録分析サービス"""
    
    def __init__(self):
        # 環境変数からAPIキーを取得
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.api_available = api_key is not None
        self.model = None
        self.initialization_error = None
        self.portfolio_analyzer = PortfolioAnalyzer()
        
        if not api_key:
            logger.warning("GEMINI_API_KEYが設定されていません")
            self.initialization_error = "API_KEY_MISSING"
            return
        
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info("Gemini API投資分析サービスが正常に初期化されました")
        except Exception as e:
            logger.error(f"Gemini API初期化エラー: {e}")
            self.model = None
            self.api_available = False
            self.initialization_error = str(e)
    
    def analyze_investment_records(self, user, start_date, end_date) -> Dict[str, Any]:
        """指定期間の投資記録を分析"""
        try:
            # データ収集
            records_data = self._collect_period_data(user, start_date, end_date)
            
            if not self.model:
                return self._generate_fallback_analysis(records_data)
            
            # Gemini APIを使った分析
            analysis_result = self._generate_professional_insights(records_data)
            
            return {
                'status': 'success',
                'analysis_data': records_data,
                'professional_insights': analysis_result.get('insights', ''),
                'detailed_feedback': analysis_result.get('detailed_feedback', []),
                'action_items': analysis_result.get('action_items', []),
                'strengths': analysis_result.get('strengths', []),
                'improvement_areas': analysis_result.get('improvement_areas', []),
                'api_used': True
            }
            
        except Exception as e:
            logger.error(f"投資記録分析エラー: {e}")
            records_data = self._collect_period_data(user, start_date, end_date)
            fallback_result = self._generate_fallback_analysis(records_data)
            fallback_result['error_message'] = str(e)
            return fallback_result
    
    def _collect_period_data(self, user, start_date, end_date) -> Dict[str, Any]:
        """期間内のデータを収集"""
        # 基本的な日記データ
        diaries = StockDiary.objects.filter(
            user=user,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).select_related('user').prefetch_related('tags', 'notes', 'analysis_values')
        
        # 統計データの計算
        total_entries = diaries.count()
        active_holdings = diaries.filter(sell_date__isnull=True, purchase_price__isnull=False).count()
        completed_trades = diaries.filter(sell_date__isnull=False).count()
        memo_entries = diaries.filter(Q(is_memo=True) | Q(purchase_price__isnull=True)).count()
        
        # 損益計算
        profit_loss_data = self._calculate_profit_loss(diaries)
        
        # タグ使用状況
        tag_usage = self._analyze_tag_usage(diaries)
        
        # 分析テンプレート使用状況  
        template_usage = self._analyze_template_usage(diaries)
        
        # 継続記録状況
        note_analysis = self._analyze_notes(diaries)
        
        # 銘柄分析
        stock_analysis = self._analyze_stocks(diaries)
        
        # 投資パターン分析
        pattern_analysis = self._analyze_investment_patterns(diaries)
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days + 1
            },
            'basic_stats': {
                'total_entries': total_entries,
                'active_holdings': active_holdings, 
                'completed_trades': completed_trades,
                'memo_entries': memo_entries,
                'analysis_rate': round((total_entries - memo_entries) / total_entries * 100, 1) if total_entries > 0 else 0
            },
            'profit_loss': profit_loss_data,
            'tag_usage': tag_usage,
            'template_usage': template_usage,
            'note_analysis': note_analysis,
            'stock_analysis': stock_analysis,
            'pattern_analysis': pattern_analysis,
            'raw_entries': self._prepare_entries_for_analysis(diaries)
        }
    
    def _calculate_profit_loss(self, diaries) -> Dict[str, Any]:
        """損益データを計算"""
        total_profit = 0
        profitable_trades = 0
        losing_trades = 0
        total_investment = 0
        realized_trades = []
        
        for diary in diaries:
            if diary.sell_date and diary.sell_price and diary.purchase_price and diary.purchase_quantity:
                profit = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
                total_profit += profit
                investment = diary.purchase_price * diary.purchase_quantity
                total_investment += investment
                
                if profit > 0:
                    profitable_trades += 1
                else:
                    losing_trades += 1
                
                realized_trades.append({
                    'symbol': diary.stock_symbol,
                    'name': diary.stock_name,
                    'profit': float(profit),
                    'profit_rate': float(profit / investment * 100) if investment > 0 else 0,
                    'holding_days': (diary.sell_date - diary.purchase_date).days
                })
        
        return {
            'total_profit_loss': float(total_profit),
            'profitable_trades': profitable_trades,
            'losing_trades': losing_trades,
            'win_rate': round(profitable_trades / (profitable_trades + losing_trades) * 100, 1) if (profitable_trades + losing_trades) > 0 else 0,
            'total_investment': float(total_investment),
            'roi': round(total_profit / total_investment * 100, 2) if total_investment > 0 else 0,
            'realized_trades': realized_trades,
            'avg_profit_per_trade': round(total_profit / len(realized_trades), 2) if realized_trades else 0
        }
    
    def _analyze_tag_usage(self, diaries) -> Dict[str, Any]:
        """タグ使用状況を分析"""
        tag_counts = {}
        total_tagged_entries = 0
        
        for diary in diaries:
            diary_tags = diary.tags.all()
            if diary_tags.exists():
                total_tagged_entries += 1
                for tag in diary_tags:
                    tag_counts[tag.name] = tag_counts.get(tag.name, 0) + 1
        
        most_used_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_tagged_entries': total_tagged_entries,
            'tagging_rate': round(total_tagged_entries / diaries.count() * 100, 1) if diaries.count() > 0 else 0,
            'unique_tags': len(tag_counts),
            'most_used_tags': most_used_tags,
            'tag_distribution': tag_counts
        }
    
    def _analyze_template_usage(self, diaries) -> Dict[str, Any]:
        """分析テンプレート使用状況を分析"""
        template_usage = {}
        analyzed_entries = 0
        
        for diary in diaries:
            analysis_values = diary.analysis_values.all()
            if analysis_values.exists():
                analyzed_entries += 1
                for value in analysis_values:
                    template_name = value.analysis_item.template.name
                    if template_name not in template_usage:
                        template_usage[template_name] = {
                            'count': 0,
                            'completion_items': 0,
                            'total_items': 0
                        }
                    template_usage[template_name]['count'] += 1
                    template_usage[template_name]['total_items'] += 1
                    
                    # 完了判定
                    if self._is_analysis_item_completed(value):
                        template_usage[template_name]['completion_items'] += 1
        
        # 完了率を計算
        for template_name, data in template_usage.items():
            if data['total_items'] > 0:
                data['completion_rate'] = round(data['completion_items'] / data['total_items'] * 100, 1)
        
        return {
            'analyzed_entries': analyzed_entries,
            'analysis_rate': round(analyzed_entries / diaries.count() * 100, 1) if diaries.count() > 0 else 0,
            'template_usage': template_usage
        }
    
    def _analyze_notes(self, diaries) -> Dict[str, Any]:
        """継続記録の分析"""
        total_notes = 0
        notes_by_type = {}
        entries_with_notes = 0
        
        for diary in diaries:
            notes = diary.notes.all()
            if notes.exists():
                entries_with_notes += 1
                total_notes += notes.count()
                
                for note in notes:
                    note_type = note.get_note_type_display()
                    notes_by_type[note_type] = notes_by_type.get(note_type, 0) + 1
        
        return {
            'total_notes': total_notes,
            'entries_with_notes': entries_with_notes,
            'follow_up_rate': round(entries_with_notes / diaries.count() * 100, 1) if diaries.count() > 0 else 0,
            'avg_notes_per_entry': round(total_notes / entries_with_notes, 1) if entries_with_notes > 0 else 0,
            'notes_by_type': notes_by_type
        }
    
    def _analyze_stocks(self, diaries) -> Dict[str, Any]:
        """銘柄分析"""
        stock_counts = {}
        sectors = {}
        
        for diary in diaries:
            symbol = diary.stock_symbol or 'unknown'
            stock_counts[symbol] = stock_counts.get(symbol, 0) + 1
            
            if diary.sector:
                sectors[diary.sector] = sectors.get(diary.sector, 0) + 1
        
        most_traded_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'unique_stocks': len(stock_counts),
            'most_traded_stocks': most_traded_stocks,
            'sector_distribution': sectors,
            'diversification_score': min(len(stock_counts) / diaries.count() * 100, 100) if diaries.count() > 0 else 0
        }
    
    def _analyze_investment_patterns(self, diaries) -> Dict[str, Any]:
        """投資パターンの分析"""
        patterns = {
            'entry_frequency': {},
            'holding_periods': [],
            'investment_sizes': [],
            'decision_quality': {
                'with_reason': 0,
                'without_reason': 0,
                'detailed_analysis': 0
            }
        }
        
        for diary in diaries:
            # 投資頻度（曜日別）
            weekday = diary.purchase_date.strftime('%A')
            patterns['entry_frequency'][weekday] = patterns['entry_frequency'].get(weekday, 0) + 1
            
            # 保有期間
            if diary.sell_date:
                holding_days = (diary.sell_date - diary.purchase_date).days
                patterns['holding_periods'].append(holding_days)
            
            # 投資金額
            if diary.purchase_price and diary.purchase_quantity:
                investment = float(diary.purchase_price * diary.purchase_quantity)
                patterns['investment_sizes'].append(investment)
            
            # 意思決定の質
            if diary.reason and len(diary.reason.strip()) > 50:
                patterns['decision_quality']['detailed_analysis'] += 1
            elif diary.reason:
                patterns['decision_quality']['with_reason'] += 1  
            else:
                patterns['decision_quality']['without_reason'] += 1
        
        # 平均値の計算
        avg_holding_period = sum(patterns['holding_periods']) / len(patterns['holding_periods']) if patterns['holding_periods'] else 0
        avg_investment_size = sum(patterns['investment_sizes']) / len(patterns['investment_sizes']) if patterns['investment_sizes'] else 0
        
        return {
            'entry_frequency': patterns['entry_frequency'],
            'avg_holding_period': round(avg_holding_period, 1),
            'avg_investment_size': round(avg_investment_size, 2),
            'decision_quality': patterns['decision_quality'],
            'analysis_depth_rate': round(patterns['decision_quality']['detailed_analysis'] / diaries.count() * 100, 1) if diaries.count() > 0 else 0
        }
    
    def _prepare_entries_for_analysis(self, diaries) -> List[Dict]:
        """Gemini分析用にエントリーデータを準備"""
        entries = []
        for diary in diaries[:10]:  # 最新10件のみ送信（トークン制限対策）
            entry = {
                'symbol': diary.stock_symbol,
                'name': diary.stock_name,
                'sector': diary.sector,
                'date': diary.purchase_date.isoformat() if diary.purchase_date else None,
                'reason': diary.reason[:200] if diary.reason else '',  # 200文字まで
                'memo': diary.memo[:200] if diary.memo else '',
                'is_memo': diary.is_memo,
                'tags': [tag.name for tag in diary.tags.all()],
                'has_analysis': diary.analysis_values.exists(),
                'notes_count': diary.notes.count(),
                'is_sold': diary.sell_date is not None
            }
            entries.append(entry)
        
        return entries
    
    def _generate_professional_insights(self, records_data) -> Dict[str, Any]:
        """Gemini APIを使ってプロ目線の洞察を生成"""
        try:
            prompt = self._build_analysis_prompt(records_data)
            
            logger.info("Gemini API投資振り返り分析開始")
            response = self.model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                logger.info("Gemini APIから分析結果を受信")
                return self._parse_gemini_analysis_response(response.text)
            else:
                logger.warning("Gemini APIから有効な応答を取得できませんでした")
                return self._generate_basic_insights(records_data)
                
        except Exception as e:
            logger.error(f"Gemini API分析エラー: {e}")
            return self._generate_basic_insights(records_data)
    
    def _build_analysis_prompt(self, records_data) -> str:
        """分析用プロンプトを構築"""
        basic_stats = records_data['basic_stats']
        profit_loss = records_data['profit_loss']
        period_info = records_data['period']
        
        prompt = f"""
あなたは経験豊富な投資アドバイザーとして、以下の投資記録データを分析し、プロフェッショナルな観点から振り返りとアドバイスを提供してください。

【分析期間】
{period_info['start_date']} から {period_info['end_date']} まで（{period_info['days']}日間）

【基本統計】
- 総記録数: {basic_stats['total_entries']}件
- アクティブ保有: {basic_stats['active_holdings']}銘柄
- 売却完了: {basic_stats['completed_trades']}件
- メモのみ記録: {basic_stats['memo_entries']}件
- 分析記録率: {basic_stats['analysis_rate']}%

【損益情報】
- 総損益: {profit_loss['total_profit_loss']:,.0f}円
- 勝率: {profit_loss['win_rate']}%
- ROI: {profit_loss['roi']}%
- 1取引あたり平均損益: {profit_loss['avg_profit_per_trade']:,.0f}円

【タグ使用状況】
- タグ付け率: {records_data['tag_usage']['tagging_rate']}%
- 最も使用されたタグ: {records_data['tag_usage']['most_used_tags'][:3]}

【投資パターン】
- 平均保有期間: {records_data['pattern_analysis']['avg_holding_period']}日
- 平均投資額: {records_data['pattern_analysis']['avg_investment_size']:,.0f}円
- 詳細分析率: {records_data['pattern_analysis']['analysis_depth_rate']}%

以下の形式で分析結果を提供してください：

## 総合評価
この期間の投資活動に対する総合的な評価を3-4文で。

## 強み・良いポイント（3-5項目）
- [具体的な強み1]: [根拠と数値]
- [具体的な強み2]: [根拠と数値]

## 改善すべき点（3-5項目）  
- [改善点1]: [具体的な問題と提案]
- [改善点2]: [具体的な問題と提案]

## 今後のアクションプラン（3-5項目）
- [アクション1]: [具体的な実行方法]
- [アクション2]: [具体的な実行方法]

## プロからのアドバイス
投資のプロとしての視点から、今後の投資活動に向けた具体的なアドバイスを2-3文で。

数値は具体的に示し、改善提案は実行可能なものにしてください。
"""
        return prompt.strip()
    
    def _parse_gemini_analysis_response(self, response_text) -> Dict[str, Any]:
        """Gemini応答を解析"""
        sections = {
            'insights': response_text,
            'detailed_feedback': [],
            'action_items': [],
            'strengths': [],
            'improvement_areas': []
        }
        
        try:
            # セクションを分割
            lines = response_text.split('\n')
            current_section = None
            current_items = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # セクションヘッダーを検出
                if '強み' in line or '良い' in line:
                    current_section = 'strengths'
                    current_items = []
                elif '改善' in line:
                    current_section = 'improvement_areas'  
                    current_items = []
                elif 'アクション' in line or '今後' in line:
                    current_section = 'action_items'
                    current_items = []
                elif line.startswith('- ') or line.startswith('• '):
                    # リスト項目を抽出
                    item = line[2:].strip()
                    if current_section and item:
                        current_items.append(item)
                        sections[current_section] = current_items.copy()
            
            return sections
            
        except Exception as e:
            logger.error(f"Gemini応答解析エラー: {e}")
            return sections
    
    def _generate_basic_insights(self, records_data) -> Dict[str, Any]:
        """基本的な洞察を生成（フォールバック）"""
        basic_stats = records_data['basic_stats']
        profit_loss = records_data['profit_loss']
        
        insights = f"""
【期間サマリー】
総記録数: {basic_stats['total_entries']}件
分析記録率: {basic_stats['analysis_rate']}%
勝率: {profit_loss['win_rate']}%
総損益: {profit_loss['total_profit_loss']:,.0f}円

【基本的な振り返り】
この期間の投資活動について、記録の継続性や分析の深さを評価し、今後の改善点を検討することをお勧めします。
"""
        
        return {
            'insights': insights,
            'detailed_feedback': ['記録の継続を心がけましょう', '投資理由の記載を充実させましょう'],
            'action_items': ['定期的な振り返りの実施', '投資ルールの見直し'],
            'strengths': ['記録の習慣化'],
            'improvement_areas': ['分析の深化']
        }
    
    def _generate_fallback_analysis(self, records_data) -> Dict[str, Any]:
        """API利用不可時のフォールバック分析"""
        basic_insights = self._generate_basic_insights(records_data)
        
        return {
            'status': 'fallback',
            'analysis_data': records_data,
            'professional_insights': basic_insights['insights'],
            'detailed_feedback': basic_insights['detailed_feedback'],
            'action_items': basic_insights['action_items'],
            'strengths': basic_insights['strengths'],
            'improvement_areas': basic_insights['improvement_areas'],
            'api_used': False,
            'fallback_reason': self.initialization_error or 'API_UNAVAILABLE'
        }
    
    def _is_analysis_item_completed(self, analysis_value):
        """分析項目が完了しているかチェック"""
        item = analysis_value.analysis_item
        
        if item.item_type == 'boolean':
            return analysis_value.boolean_value is True
        elif item.item_type == 'boolean_with_value':
            return analysis_value.boolean_value is True
        elif item.item_type == 'number':
            return analysis_value.number_value is not None
        elif item.item_type in ['text', 'select']:
            return bool(analysis_value.text_value and analysis_value.text_value.strip())
        
        return False

    def analyze_current_portfolio(self, user) -> Dict[str, Any]:
        """現在保有株式のポートフォリオを評価分析"""
        try:
            # ポートフォリオデータを取得
            portfolio_data = self.portfolio_analyzer.analyze_current_portfolio(user)
            
            if portfolio_data.get('status') != 'success':
                return portfolio_data
            
            # 市場環境情報を取得
            market_context = self.portfolio_analyzer.get_market_context()
            
            if not self.model:
                return self._generate_fallback_portfolio_evaluation(portfolio_data, market_context)
            
            # Gemini APIを使ってプロ目線の評価を生成
            evaluation_result = self._generate_professional_portfolio_evaluation(portfolio_data, market_context)
            
            return {
                'status': 'success',
                'portfolio_data': portfolio_data,
                'market_context': market_context,
                'professional_evaluation': evaluation_result.get('evaluation', ''),
                'strengths': evaluation_result.get('strengths', []),
                'weaknesses': evaluation_result.get('weaknesses', []),
                'neutral_assessment': evaluation_result.get('neutral_assessment', []),
                'actionable_recommendations': evaluation_result.get('recommendations', []),
                'risk_assessment': evaluation_result.get('risk_assessment', ''),
                'market_positioning': evaluation_result.get('market_positioning', ''),
                'api_used': True,
                'analysis_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"ポートフォリオ評価分析エラー: {e}")
            portfolio_data = self.portfolio_analyzer.analyze_current_portfolio(user)
            fallback_result = self._generate_fallback_portfolio_evaluation(portfolio_data, {})
            fallback_result['error_message'] = str(e)
            return fallback_result
    
    def _generate_professional_portfolio_evaluation(self, portfolio_data: Dict, market_context: Dict) -> Dict[str, Any]:
        """Gemini APIを使ってプロ目線のポートフォリオ評価を生成"""
        try:
            prompt = self._build_portfolio_evaluation_prompt(portfolio_data, market_context)
            
            logger.info("Gemini APIポートフォリオ評価分析開始")
            response = self.model.generate_content(prompt)
            
            if hasattr(response, "text") and response.text:
                logger.info("Gemini APIから評価結果を受信")
                return self._parse_portfolio_evaluation_response(response.text)
            else:
                logger.warning("Gemini APIから有効な応答を取得できませんでした")
                return self._generate_basic_portfolio_evaluation(portfolio_data)
                
        except Exception as e:
            logger.error(f"Gemini APIポートフォリオ評価エラー: {e}")
            return self._generate_basic_portfolio_evaluation(portfolio_data)
    

    def _build_portfolio_evaluation_prompt(self, portfolio_data: Dict, market_context: Dict) -> str:
        """ポートフォリオ評価用の詳細プロンプトを構築"""
        # ポートフォリオの基本情報
        total_holdings = portfolio_data.get('total_holdings', 0)
        total_value = portfolio_data.get('total_portfolio_value', 0)
        holdings = portfolio_data.get('holdings', [])
        
        # 分析データ
        portfolio_analysis = portfolio_data.get('portfolio_analysis', {})
        sector_analysis = portfolio_data.get('sector_analysis', {})
        risk_analysis = portfolio_data.get('risk_analysis', {})
        performance_analysis = portfolio_data.get('performance_analysis', {})
        
        # 有効な銘柄のみをフィルタリング
        valid_holdings = [
            h for h in holdings 
            if h.get('current_value') is not None and 
            h.get('stock_symbol') and 
            h.get('stock_name') and 
            h.get('stock_name').strip() != '' and
            h.get('investment_amount', 0) > 0
        ]
        
        if not valid_holdings:
            # 有効な銘柄がない場合はシンプルなプロンプトを返す
            return """
    ポートフォリオデータが不完全または無効です。
    基本的な評価コメントを提供してください：

    【評価対象】
    有効なポートフォリオデータがありません。

    【評価要求】
    データの整理と記録方法の改善について、建設的なアドバイスを提供してください。
    """
        
        # 主要保有銘柄の詳細（上位5銘柄、current_valueでソート）
        try:
            # Noneではない current_value でソート
            top_holdings = sorted(
                valid_holdings, 
                key=lambda x: x.get('current_value', 0) or 0, 
                reverse=True
            )[:5]
        except Exception as e:
            logger.warning(f"銘柄ソートエラー: {e}")
            # ソートに失敗した場合は先頭5件を使用
            top_holdings = valid_holdings[:5]
        
        top_holdings_summary = []
        
        for holding in top_holdings:
            fundamentals = holding.get('fundamentals', {})
            technical = holding.get('technical', {})
            
            # 安全な値の取得
            def safe_get(d, key, default='N/A'):
                value = d.get(key)
                if value is None:
                    return default
                try:
                    if isinstance(value, (int, float)):
                        return f"{value:.2f}" if isinstance(value, float) else str(value)
                    return str(value)
                except:
                    return default
            
            # 安全な数値取得
            def safe_float(value, default=0):
                if value is None:
                    return default
                try:
                    return float(value)
                except:
                    return default
            
            summary = f"""
    銘柄: {holding.get('stock_name', '未設定')} ({holding.get('stock_symbol', 'N/A')})
    セクター: {holding.get('sector', 'その他')}
    投資額: {safe_float(holding.get('investment_amount', 0)):,.0f}円
    現在価値: {safe_float(holding.get('current_value', 0)):,.0f}円
    損益率: {safe_float(holding.get('unrealized_gain_loss_pct', 0)):.1f}%
    保有期間: {holding.get('holding_period_days', 0)}日
    PER: {safe_get(fundamentals, 'pe_ratio')}
    PBR: {safe_get(fundamentals, 'pb_ratio')}
    配当利回り: {safe_get(fundamentals, 'dividend_yield')}
    RSI: {safe_get(technical, 'rsi')}
    トレンド: {safe_get(technical, 'trend_signal')}
    """
            top_holdings_summary.append(summary.strip())
        
        # 市場環境情報
        market_summary = ""
        if market_context.get('status') == 'success':
            market_data = market_context.get('market_data', {})
            if 'nikkei' in market_data:
                nikkei_change = market_data['nikkei'].get('change_pct', 0)
                market_summary += f"日経平均: {nikkei_change:+.2f}%\n"
            if 'usdjpy' in market_data:
                usdjpy_change = market_data['usdjpy'].get('change_pct', 0)
                usdjpy_rate = market_data['usdjpy'].get('current', 0)
                market_summary += f"USD/JPY: {usdjpy_rate:.2f} ({usdjpy_change:+.2f}%)\n"
        
        prompt = f"""
    あなたは20年以上の経験を持つプロの投資アドバイザーとして、以下のポートフォリオを厳格かつ建設的に評価してください。

    【ポートフォリオ概要】
    保有銘柄数: {total_holdings}銘柄
    総投資額: {safe_float(performance_analysis.get('total_investment', 0)):,.0f}円
    総評価額: {safe_float(total_value):,.0f}円
    総合リターン: {safe_float(performance_analysis.get('total_return_pct', 0)):+.1f}%

    【ポートフォリオ構成分析】
    上位5銘柄集中度: {safe_float(portfolio_analysis.get('top_5_concentration', 0)):.1f}%
    平均保有期間: {safe_float(portfolio_analysis.get('avg_holding_period_days', 0)):.0f}日
    勝率: {safe_float(portfolio_analysis.get('win_rate', 0)):.1f}%
    分散投資スコア: {portfolio_analysis.get('diversification_score', 'N/A')}

    【セクター分散】
    セクター数: {sector_analysis.get('num_sectors', 0)}
    最大セクター集中度: {safe_float(sector_analysis.get('max_sector_concentration', 0)):.1f}%
    セクター分散スコア: {sector_analysis.get('sector_diversification_score', 'N/A')}

    【リスク分析】
    平均ボラティリティ: {safe_get(risk_analysis, 'avg_volatility')}
    平均PER: {safe_get(risk_analysis, 'avg_pe_ratio')}
    平均PBR: {safe_get(risk_analysis, 'avg_pb_ratio')}
    高PER銘柄比率: {safe_float(risk_analysis.get('high_pe_ratio', 0)):.1f}%
    小型株比率: {safe_float(risk_analysis.get('small_cap_ratio', 0)):.1f}%
    リスクレベル: {risk_analysis.get('risk_level', 'N/A')}

    【主要保有銘柄詳細】
    {chr(10).join(top_holdings_summary)}

    【現在の市場環境】
    {market_summary if market_summary else '市場データ取得不可'}

    【分析要求】
    以下の観点から、投資家に刺さる率直で建設的な評価を提供してください：

    1. **強み（ポジティブ要素）** - 3-5点
    - 優れている具体的なポイント
    - 数値的根拠を含めた評価
    - 継続すべき投資戦略

    2. **弱み・リスク要素** - 3-5点  
    - 改善が必要な具体的な問題
    - 潜在的なリスク要因
    - 市場環境変化への脆弱性

    3. **中立的な現状判断** - 2-3点
    - 現在のポジショニングの妥当性
    - 市場環境との整合性
    - 投資スタイルの一貫性

    4. **具体的な改善提案** - 3-5点
    - 実行可能なアクションプラン
    - リスク管理の改善策
    - パフォーマンス向上のための戦略

    5. **総合リスク評価**
    - 現在のリスクレベルの妥当性
    - 金融環境変化への対応力
    - ポートフォリオの持続可能性

    6. **市場ポジショニング**
    - 現在の市場環境における適切性
    - 今後の市場変動への対応力
    - セクターローテーションへの対応

    **出力形式:**
    ## 総合評価
    [3-4文での全体評価]

    ## 強み・ポジティブ要素
    • [具体的な強み1]: [数値的根拠と評価]
    • [具体的な強み2]: [数値的根拠と評価]
    [3-5項目]

    ## 弱み・リスク要素
    • [具体的な弱み1]: [問題の詳細と影響]
    • [具体的な弱み2]: [問題の詳細と影響]
    [3-5項目]

    ## 中立的な現状判断
    • [判断1]: [根拠]
    • [判断2]: [根拠]
    [2-3項目]

    ## 改善提案・アクションプラン
    • [提案1]: [具体的な実行方法]
    • [提案2]: [具体的な実行方法]
    [3-5項目]

    ## リスク評価
    [リスクレベルの妥当性と改善点]

    ## 市場ポジショニング
    [現在の市場環境での適切性評価]

    **注意事項:**
    - 数値は具体的に示し、曖昧な表現は避ける
    - 建設的で実行可能な提案を心がける
    - 投資家の成長を促す厳しくも的確な指摘を含める
    - 現在の金融市場環境（金利、為替、地政学リスク等）を考慮する
    """
        return prompt.strip()
    
    def _parse_portfolio_evaluation_response(self, response_text: str) -> Dict[str, Any]:
        """ポートフォリオ評価応答を解析"""
        sections = {
            'evaluation': response_text,
            'strengths': [],
            'weaknesses': [],
            'neutral_assessment': [],
            'recommendations': [],
            'risk_assessment': '',
            'market_positioning': ''
        }
        
        try:
            # セクションを分割して解析
            lines = response_text.split('\n')
            current_section = None
            current_items = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # セクションヘッダーを検出
                if '強み' in line or 'ポジティブ' in line:
                    if current_section and current_items:
                        sections[current_section] = current_items.copy()
                    current_section = 'strengths'
                    current_items = []
                elif '弱み' in line or 'リスク要素' in line:
                    if current_section and current_items:
                        sections[current_section] = current_items.copy()
                    current_section = 'weaknesses'
                    current_items = []
                elif '中立' in line or '現状判断' in line:
                    if current_section and current_items:
                        sections[current_section] = current_items.copy()
                    current_section = 'neutral_assessment'
                    current_items = []
                elif '改善' in line or 'アクション' in line or '提案' in line:
                    if current_section and current_items:
                        sections[current_section] = current_items.copy()
                    current_section = 'recommendations'
                    current_items = []
                elif 'リスク評価' in line:
                    if current_section and current_items:
                        sections[current_section] = current_items.copy()
                    current_section = 'risk_assessment'
                    current_items = []
                elif '市場ポジショニング' in line:
                    if current_section and current_items:
                        sections[current_section] = current_items.copy()
                    current_section = 'market_positioning'
                    current_items = []
                elif line.startswith('• ') or line.startswith('・') or line.startswith('- '):
                    # リスト項目を抽出
                    item = line[2:].strip() if line.startswith(('• ', '・ ')) else line[2:].strip()
                    if current_section and item:
                        if current_section in ['risk_assessment', 'market_positioning']:
                            # これらのセクションは文章として扱う
                            current_items.append(item)
                        else:
                            current_items.append(item)
                elif current_section in ['risk_assessment', 'market_positioning'] and line:
                    # リスク評価と市場ポジショニングは継続的なテキスト
                    current_items.append(line)
            
            # 最後のセクションを保存
            if current_section and current_items:
                if current_section in ['risk_assessment', 'market_positioning']:
                    sections[current_section] = '\n'.join(current_items)
                else:
                    sections[current_section] = current_items
            
            return sections
            
        except Exception as e:
            logger.error(f"ポートフォリオ評価応答解析エラー: {e}")
            return sections
    
    def _generate_basic_portfolio_evaluation(self, portfolio_data: Dict) -> Dict[str, Any]:
        """基本的なポートフォリオ評価を生成（フォールバック）"""
        total_holdings = portfolio_data.get('total_holdings', 0)
        portfolio_analysis = portfolio_data.get('portfolio_analysis', {})
        risk_analysis = portfolio_data.get('risk_analysis', {})
        performance_analysis = portfolio_data.get('performance_analysis', {})
        
        evaluation = f"""
【基本的なポートフォリオ評価】
保有銘柄数: {total_holdings}銘柄
総合リターン: {performance_analysis.get('total_return_pct', 0):+.1f}%
勝率: {portfolio_analysis.get('win_rate', 0):.1f}%
分散投資スコア: {portfolio_analysis.get('diversification_score', 'N/A')}

【所見】
現在のポートフォリオについて、基本的な分析結果をお示ししています。
より詳細な評価については、APIサービスが利用可能な際に再実行してください。
"""
        
        return {
            'evaluation': evaluation,
            'strengths': ['記録の継続的な管理'],
            'weaknesses': ['詳細分析の実行が必要'],
            'neutral_assessment': ['現在の保有状況は記録されています'],
            'recommendations': ['定期的な見直しを推奨'],
            'risk_assessment': 'リスク評価にはより詳細なデータが必要です',
            'market_positioning': '市場環境との整合性の確認を推奨します'
        }
    
    def _generate_fallback_portfolio_evaluation(self, portfolio_data: Dict, market_context: Dict) -> Dict[str, Any]:
        """API利用不可時のフォールバックポートフォリオ評価"""
        basic_evaluation = self._generate_basic_portfolio_evaluation(portfolio_data)
        
        return {
            'status': 'fallback' if portfolio_data.get('status') == 'success' else portfolio_data.get('status', 'error'),
            'portfolio_data': portfolio_data,
            'market_context': market_context,
            'professional_evaluation': basic_evaluation['evaluation'],
            'strengths': basic_evaluation['strengths'],
            'weaknesses': basic_evaluation['weaknesses'],
            'neutral_assessment': basic_evaluation['neutral_assessment'],
            'actionable_recommendations': basic_evaluation['recommendations'],
            'risk_assessment': basic_evaluation['risk_assessment'],
            'market_positioning': basic_evaluation['market_positioning'],
            'api_used': False,
            'fallback_reason': self.initialization_error or 'API_UNAVAILABLE',
            'analysis_timestamp': timezone.now().isoformat()
        }

    # 既存のメソッドはそのまま維持...
    def analyze_investment_records(self, user, start_date, end_date) -> Dict[str, Any]:
        """指定期間の投資記録を分析（既存メソッド）"""
        try:
            # データ収集
            records_data = self._collect_period_data(user, start_date, end_date)
            
            if not self.model:
                return self._generate_fallback_analysis(records_data)
            
            # Gemini APIを使った分析
            analysis_result = self._generate_professional_insights(records_data)
            
            return {
                'status': 'success',
                'analysis_data': records_data,
                'professional_insights': analysis_result.get('insights', ''),
                'detailed_feedback': analysis_result.get('detailed_feedback', []),
                'action_items': analysis_result.get('action_items', []),
                'strengths': analysis_result.get('strengths', []),
                'improvement_areas': analysis_result.get('improvement_areas', []),
                'api_used': True
            }
            
        except Exception as e:
            logger.error(f"投資記録分析エラー: {e}")
            records_data = self._collect_period_data(user, start_date, end_date)
            fallback_result = self._generate_fallback_analysis(records_data)
            fallback_result['error_message'] = str(e)
            return fallback_result

    # [既存のメソッドはそのまま維持...]
    # _collect_period_data, _calculate_profit_loss, _analyze_tag_usage, 
    # _analyze_template_usage, _analyze_notes, _analyze_stocks,
    # _analyze_investment_patterns, _prepare_entries_for_analysis,
    # _generate_professional_insights, _build_analysis_prompt,
    # _parse_gemini_analysis_response, _generate_basic_insights,
    # _generate_fallback_analysis, _is_analysis_item_completed
    
    def _collect_period_data(self, user, start_date, end_date) -> Dict[str, Any]:
        """期間内のデータを収集"""
        # [既存の実装をそのまま使用]
        diaries = StockDiary.objects.filter(
            user=user,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).select_related('user').prefetch_related('tags', 'notes', 'analysis_values')
        
        # 統計データの計算
        total_entries = diaries.count()
        active_holdings = diaries.filter(sell_date__isnull=True, purchase_price__isnull=False).count()
        completed_trades = diaries.filter(sell_date__isnull=False).count()
        memo_entries = diaries.filter(Q(is_memo=True) | Q(purchase_price__isnull=True)).count()
        
        # 損益計算
        profit_loss_data = self._calculate_profit_loss(diaries)
        
        # タグ使用状況
        tag_usage = self._analyze_tag_usage(diaries)
        
        # 分析テンプレート使用状況  
        template_usage = self._analyze_template_usage(diaries)
        
        # 継続記録状況
        note_analysis = self._analyze_notes(diaries)
        
        # 銘柄分析
        stock_analysis = self._analyze_stocks(diaries)
        
        # 投資パターン分析
        pattern_analysis = self._analyze_investment_patterns(diaries)
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days + 1
            },
            'basic_stats': {
                'total_entries': total_entries,
                'active_holdings': active_holdings, 
                'completed_trades': completed_trades,
                'memo_entries': memo_entries,
                'analysis_rate': round((total_entries - memo_entries) / total_entries * 100, 1) if total_entries > 0 else 0
            },
            'profit_loss': profit_loss_data,
            'tag_usage': tag_usage,
            'template_usage': template_usage,
            'note_analysis': note_analysis,
            'stock_analysis': stock_analysis,
            'pattern_analysis': pattern_analysis,
            'raw_entries': self._prepare_entries_for_analysis(diaries)
        }    