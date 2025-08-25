# margin_trading/views.py
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, View
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, Max, Min, F, Case, When, Value, FloatField
from django.db.models.functions import Coalesce
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import datetime, timedelta
import statistics
from collections import defaultdict

from .models import MarketIssue, MarginTradingData
from company_master.models import CompanyMaster


class DebugInfoView(TemplateView):
    """デバッグ情報表示ビュー（開発用）"""
    template_name = 'margin_trading/debug_info.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # データベース状態の取得
        company_count = CompanyMaster.objects.count()
        market_issue_count = MarketIssue.objects.count()
        margin_data_count = MarginTradingData.objects.count()
        
        # マッチング済みの数（CompanyMasterとMarketIssueの両方に存在）
        company_codes = set(CompanyMaster.objects.values_list('code', flat=True))
        market_issue_codes = set(MarketIssue.objects.values_list('code', flat=True))
        # '0'付きのコードも考慮
        market_issue_codes_alt = set()
        for code in market_issue_codes:
            market_issue_codes_alt.add(code.rstrip('0'))
        all_market_codes = market_issue_codes.union(market_issue_codes_alt)
        matched_count = len(company_codes.intersection(all_market_codes))
        
        # 最新データ日付
        latest_date = MarginTradingData.objects.aggregate(
            latest=Max('date')
        )['latest']
        
        # サンプルデータの作成
        sample_companies = []
        if latest_date and matched_count > 0:
            # マッチング済みの企業から5社を取得（33業種または17業種）
            matched_companies = CompanyMaster.objects.filter(
                Q(code__in=all_market_codes) & (
                    Q(industry_name_33__isnull=False) & ~Q(industry_name_33='') |
                    Q(industry_name_17__isnull=False) & ~Q(industry_name_17='')
                )
            )[:5]
            
            for company in matched_companies:
                try:
                    # MarketIssueを検索（複数パターンで試行）
                    market_issue = MarketIssue.objects.filter(
                        Q(code=company.code) | Q(code=company.code + '0')
                    ).first()
                    
                    if market_issue:
                        margin_data = MarginTradingData.objects.filter(
                            issue=market_issue,
                            date=latest_date
                        ).first()
                        
                        if margin_data:
                            # 信用倍率を計算（マイナス値・無限大対応）
                            if margin_data.outstanding_sales != 0:
                                ratio = margin_data.outstanding_purchases / margin_data.outstanding_sales
                            else:
                                ratio = float('inf') if margin_data.outstanding_purchases > 0 else 0
                            
                            # 業種名を決定（33業種を優先）
                            sector = company.industry_name_33 or company.industry_name_17 or '不明'
                            
                            sample_companies.append({
                                'code': company.code,
                                'name': company.name,
                                'sector': sector,
                                'ratio': ratio,
                                'sales': margin_data.outstanding_sales,
                                'purchases': margin_data.outstanding_purchases
                            })
                except Exception:
                    continue
        
        context.update({
            'company_count': company_count,
            'market_issue_count': market_issue_count,
            'margin_data_count': margin_data_count,
            'matched_count': matched_count,
            'latest_date': latest_date,
            'sample_companies': sample_companies
        })
        
        return context


class SectorScreenerView(LoginRequiredMixin, TemplateView):
    """業種別信用倍率スクリーニング メインビュー"""
    template_name = 'margin_trading/screener.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 33業種リストを取得
        sectors_33 = CompanyMaster.objects.exclude(
            Q(industry_name_33__isnull=True) | Q(industry_name_33='')
        ).values(
            'industry_code_33', 'industry_name_33'
        ).distinct().order_by('industry_name_33')
        
        # 17業種リストを取得
        sectors_17 = CompanyMaster.objects.exclude(
            Q(industry_name_17__isnull=True) | Q(industry_name_17='')
        ).values(
            'industry_code_17', 'industry_name_17'
        ).distinct().order_by('industry_name_17')
        
        # 規模リストを取得
        scales = CompanyMaster.objects.exclude(
            Q(scale_name__isnull=True) | Q(scale_name='')
        ).values(
            'scale_code', 'scale_name'
        ).distinct().order_by('scale_name')
        
        # 市場区分リストを取得
        markets = CompanyMaster.objects.exclude(
            Q(market__isnull=True) | Q(market='')
        ).values('market').distinct().order_by('market')
        
        # 最新データ日付を取得
        latest_date = MarginTradingData.objects.aggregate(
            latest=Max('date')
        )['latest']
        
        context.update({
            'sectors_33': list(sectors_33),
            'sectors_17': list(sectors_17),
            'scales': list(scales),
            'markets': [m['market'] for m in markets],
            'latest_date': latest_date,
            'page_actions': [
                {
                    'type': 'back',
                    'url': '/stockdiary/',
                    'icon': 'bi-arrow-left',
                    'label': '戻る'
                },
                {
                    'type': 'refresh',
                    'url': '#',
                    'icon': 'bi-arrow-clockwise',
                    'label': '更新',
                    'onclick': 'location.reload()'
                }
            ]
        })
        
        return context


class SectorDataView(LoginRequiredMixin, View):
    """スクリーニングデータ取得ビュー"""
    
    def get(self, request, *args, **kwargs):
        # フィルターパラメータの取得
        sector_code = request.GET.get('sector')
        sector_type = request.GET.get('sector_type', '33')  # デフォルトは33業種
        scale_code = request.GET.get('scale')
        market = request.GET.get('market')
        ratio_min = request.GET.get('ratio_min')
        ratio_max = request.GET.get('ratio_max')
        sort_by = request.GET.get('sort', 'ratio_desc')
        
        try:
            # 基本データの取得
            data = self._get_sector_data(
                sector_code=sector_code,
                sector_type=sector_type,
                scale_code=scale_code,
                market=market,
                ratio_min=ratio_min,
                ratio_max=ratio_max,
                sort_by=sort_by
            )
            
            return JsonResponse(data)
            
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'message': 'データ取得中にエラーが発生しました'
            }, status=500)
    
    def _get_sector_data(self, sector_code=None, sector_type='33', scale_code=None, market=None, 
                        ratio_min=None, ratio_max=None, sort_by='ratio_desc'):
        """業種データを取得・集計"""
        
        try:
            # 最新データ日付を取得
            latest_date = MarginTradingData.objects.aggregate(
                latest=Max('date')
            )['latest']
            
            if not latest_date:
                return {
                    'error': '信用取引データが見つかりません',
                    'companies': [],
                    'stats': {
                        'total_count': 0,
                        'avg_ratio': 0,
                        'median_ratio': 0,
                        'min_ratio': 0,
                        'max_ratio': 0,
                        'std_ratio': 0
                    },
                    'latest_date': None
                }
            
            # 業種分類に基づくCompanyMasterの基本クエリ
            if sector_type == '17':
                base_query = CompanyMaster.objects.exclude(
                    Q(industry_name_17__isnull=True) | Q(industry_name_17='')
                )
            else:  # デフォルトは33業種
                base_query = CompanyMaster.objects.exclude(
                    Q(industry_name_33__isnull=True) | Q(industry_name_33='')
                )
            
            # フィルター適用
            if sector_code:
                if sector_type == '17':
                    base_query = base_query.filter(industry_code_17=sector_code)
                else:
                    base_query = base_query.filter(industry_code_33=sector_code)
            
            if scale_code:
                base_query = base_query.filter(scale_code=scale_code)
            if market:
                base_query = base_query.filter(market=market)
            
            companies_with_margin = []
            
            # 各企業のデータを処理
            for company in base_query:
                try:
                    # MarketIssueを検索（複数パターンで試行）
                    market_issue = MarketIssue.objects.filter(
                        Q(code=company.code) | Q(code=company.code + '0')
                    ).first()
                    
                    if not market_issue:
                        continue
                    
                    # 最新の信用取引データを取得
                    margin_data = MarginTradingData.objects.filter(
                        issue=market_issue,
                        date=latest_date
                    ).first()
                    
                    if not margin_data:
                        continue
                    
                    # 信用倍率を計算（マイナス値も含めて対応）
                    if margin_data.outstanding_sales != 0:
                        ratio = margin_data.outstanding_purchases / margin_data.outstanding_sales
                    else:
                        # 売残高が0の場合の処理
                        if margin_data.outstanding_purchases > 0:
                            ratio = float('inf')  # 無限大として扱う
                        else:
                            ratio = 0
                    
                    # 倍率フィルター（範囲制限なし）
                    if ratio_min is not None:
                        try:
                            if ratio != float('inf') and ratio < float(ratio_min):
                                continue
                        except (ValueError, TypeError):
                            pass
                    
                    if ratio_max is not None:
                        try:
                            if ratio != float('inf') and ratio > float(ratio_max):
                                continue
                        except (ValueError, TypeError):
                            pass
                    
                    # 業種名を取得（選択された分類に基づく）
                    if sector_type == '17':
                        sector_name = company.industry_name_17
                        sector_code_field = company.industry_code_17
                    else:
                        sector_name = company.industry_name_33
                        sector_code_field = company.industry_code_33
                    
                    # 無限大の場合は表示用の値に変換
                    display_ratio = "∞" if ratio == float('inf') else round(ratio, 2)
                    
                    companies_with_margin.append({
                        'code': company.code,
                        'name': company.name,
                        'sector_name': sector_name,
                        'sector_code': sector_code_field,
                        'sector_type': sector_type,
                        'scale_name': company.scale_name or '不明',
                        'market': company.market or '不明',
                        'ratio': display_ratio,
                        'ratio_numeric': ratio if ratio != float('inf') else 999999,  # ソート用
                        'outstanding_sales': margin_data.outstanding_sales,
                        'outstanding_purchases': margin_data.outstanding_purchases,
                        'sales_change': margin_data.outstanding_sales_change,
                        'purchases_change': margin_data.outstanding_purchases_change,
                        'data_date': latest_date.strftime('%Y-%m-%d')
                    })
                    
                except Exception as e:
                    # 個別企業の処理エラーは無視して継続
                    continue
            
            # ソート処理（無限大値を考慮）
            try:
                if sort_by == 'ratio_desc':
                    companies_with_margin.sort(key=lambda x: x['ratio_numeric'], reverse=True)
                elif sort_by == 'ratio_asc':
                    companies_with_margin.sort(key=lambda x: x['ratio_numeric'])
                elif sort_by == 'name':
                    companies_with_margin.sort(key=lambda x: x['name'])
                elif sort_by == 'sales_desc':
                    companies_with_margin.sort(key=lambda x: x['outstanding_sales'], reverse=True)
                elif sort_by == 'purchases_desc':
                    companies_with_margin.sort(key=lambda x: x['outstanding_purchases'], reverse=True)
            except Exception:
                # ソートエラーは無視
                pass
            
            # 統計情報を計算（無限大値を除外）
            if companies_with_margin:
                try:
                    # 有限の値のみで統計計算
                    finite_ratios = [c['ratio_numeric'] for c in companies_with_margin 
                                   if c['ratio_numeric'] != 999999 and isinstance(c['ratio_numeric'], (int, float))]
                    
                    if finite_ratios:
                        stats = {
                            'total_count': len(companies_with_margin),
                            'avg_ratio': round(statistics.mean(finite_ratios), 2),
                            'median_ratio': round(statistics.median(finite_ratios), 2),
                            'min_ratio': round(min(finite_ratios), 2),
                            'max_ratio': round(max(finite_ratios), 2),
                            'std_ratio': round(statistics.stdev(finite_ratios) if len(finite_ratios) > 1 else 0, 2),
                            'infinite_count': len(companies_with_margin) - len(finite_ratios)
                        }
                    else:
                        stats = {
                            'total_count': len(companies_with_margin),
                            'avg_ratio': 0,
                            'median_ratio': 0,
                            'min_ratio': 0,
                            'max_ratio': 0,
                            'std_ratio': 0,
                            'infinite_count': len(companies_with_margin)
                        }
                except Exception:
                    stats = {
                        'total_count': len(companies_with_margin),
                        'avg_ratio': 0,
                        'median_ratio': 0,
                        'min_ratio': 0,
                        'max_ratio': 0,
                        'std_ratio': 0,
                        'infinite_count': 0
                    }
            else:
                stats = {
                    'total_count': 0,
                    'avg_ratio': 0,
                    'median_ratio': 0,
                    'min_ratio': 0,
                    'max_ratio': 0,
                    'std_ratio': 0,
                    'infinite_count': 0
                }
            
            return {
                'companies': companies_with_margin[:100],  # 最大100件まで表示
                'stats': stats,
                'latest_date': latest_date.strftime('%Y-%m-%d'),
                'sector_type': sector_type
            }
            
        except Exception as e:
            # 全体的なエラーハンドリング
            import traceback
            print(f"Sector data error: {traceback.format_exc()}")
            
            return {
                'error': f'データ処理中にエラーが発生しました: {str(e)}',
                'companies': [],
                'stats': {
                    'total_count': 0,
                    'avg_ratio': 0,
                    'median_ratio': 0,
                    'min_ratio': 0,
                    'max_ratio': 0,
                    'std_ratio': 0,
                    'infinite_count': 0
                },
                'latest_date': None,
                'sector_type': sector_type
            }


class SectorStatsAPIView(LoginRequiredMixin, View):
    """業種統計情報API"""
    
    def get(self, request, *args, **kwargs):
        try:
            # 最新データ日付を取得
            latest_date = MarginTradingData.objects.aggregate(
                latest=Max('date')
            )['latest']
            
            if not latest_date:
                return JsonResponse({'error': 'データがありません'}, status=404)
            
            # 業種別統計を計算
            sector_stats = self._calculate_sector_stats(latest_date)
            
            return JsonResponse({
                'sector_stats': sector_stats,
                'latest_date': latest_date.strftime('%Y-%m-%d')
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def _calculate_sector_stats(self, latest_date):
        """業種別統計を計算"""
        sector_data = defaultdict(list)
        
        # 全ての業種のデータを取得
        companies = CompanyMaster.objects.exclude(
            Q(industry_name_33__isnull=True) | Q(industry_name_33='')
        ).select_related()
        
        for company in companies:
            try:
                market_issue = MarketIssue.objects.filter(code=company.code).first()
                if not market_issue:
                    continue
                
                margin_data = MarginTradingData.objects.filter(
                    issue=market_issue,
                    date=latest_date
                ).first()
                
                if not margin_data or margin_data.outstanding_sales <= 0:
                    continue
                
                ratio = margin_data.outstanding_purchases / margin_data.outstanding_sales
                sector_key = company.industry_name_33
                
                sector_data[sector_key].append({
                    'ratio': ratio,
                    'company': company.name,
                    'code': company.code
                })
                
            except Exception:
                continue
        
        # 業種統計を算出
        sector_stats = []
        for sector_name, companies_data in sector_data.items():
            if len(companies_data) < 2:  # 最低2社以上
                continue
            
            ratios = [c['ratio'] for c in companies_data]
            
            sector_stats.append({
                'sector_name': sector_name,
                'company_count': len(companies_data),
                'avg_ratio': round(statistics.mean(ratios), 2),
                'median_ratio': round(statistics.median(ratios), 2),
                'min_ratio': round(min(ratios), 2),
                'max_ratio': round(max(ratios), 2),
                'std_ratio': round(statistics.stdev(ratios), 2),
                'top_companies': sorted(companies_data, key=lambda x: x['ratio'], reverse=True)[:3]
            })
        
        # 平均信用倍率でソート
        sector_stats.sort(key=lambda x: x['avg_ratio'], reverse=True)
        
        return sector_stats


class SectorRankingAPIView(LoginRequiredMixin, View):
    """業種内ランキングAPI"""
    
    def get(self, request, *args, **kwargs):
        sector_code = request.GET.get('sector')
        if not sector_code:
            return JsonResponse({'error': 'sector パラメータが必要です'}, status=400)
        
        try:
            ranking_data = self._get_sector_ranking(sector_code)
            return JsonResponse(ranking_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def _get_sector_ranking(self, sector_code):
        """指定業種内のランキングを取得"""
        latest_date = MarginTradingData.objects.aggregate(
            latest=Max('date')
        )['latest']
        
        companies = CompanyMaster.objects.filter(
            industry_code_33=sector_code
        ).exclude(
            Q(industry_name_33__isnull=True) | Q(industry_name_33='')
        )
        
        ranking_data = []
        ratios_for_stats = []
        
        for company in companies:
            try:
                market_issue = MarketIssue.objects.filter(code=company.code).first()
                if not market_issue:
                    continue
                
                margin_data = MarginTradingData.objects.filter(
                    issue=market_issue,
                    date=latest_date
                ).first()
                
                if not margin_data:
                    continue
                
                if margin_data.outstanding_sales > 0:
                    ratio = margin_data.outstanding_purchases / margin_data.outstanding_sales
                else:
                    ratio = 0
                
                ranking_data.append({
                    'rank': 0,  # 後で設定
                    'code': company.code,
                    'name': company.name,
                    'ratio': round(ratio, 2),
                    'outstanding_sales': margin_data.outstanding_sales,
                    'outstanding_purchases': margin_data.outstanding_purchases,
                    'sales_change': margin_data.outstanding_sales_change,
                    'purchases_change': margin_data.outstanding_purchases_change
                })
                
                ratios_for_stats.append(ratio)
                
            except Exception:
                continue
        
        # ランキング設定
        ranking_data.sort(key=lambda x: x['ratio'], reverse=True)
        for i, item in enumerate(ranking_data):
            item['rank'] = i + 1
        
        # 業種統計
        sector_stats = {}
        if ratios_for_stats:
            sector_stats = {
                'company_count': len(ratios_for_stats),
                'avg_ratio': round(statistics.mean(ratios_for_stats), 2),
                'median_ratio': round(statistics.median(ratios_for_stats), 2),
                'std_ratio': round(statistics.stdev(ratios_for_stats) if len(ratios_for_stats) > 1 else 0, 2)
            }
        
        return {
            'ranking': ranking_data,
            'sector_stats': sector_stats,
            'sector_name': companies.first().industry_name_33 if companies.exists() else '',
            'latest_date': latest_date.strftime('%Y-%m-%d')
        }


class OutlierAnalysisAPIView(LoginRequiredMixin, View):
    """異常値分析API"""
    
    def get(self, request, *args, **kwargs):
        try:
            outlier_data = self._analyze_outliers()
            return JsonResponse(outlier_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def _analyze_outliers(self):
        """全市場の異常値を分析"""
        latest_date = MarginTradingData.objects.aggregate(
            latest=Max('date')
        )['latest']
        
        all_ratios = []
        company_ratios = []
        
        # 全銘柄のデータを取得
        companies = CompanyMaster.objects.exclude(
            Q(industry_name_33__isnull=True) | Q(industry_name_33='')
        )
        
        for company in companies:
            try:
                market_issue = MarketIssue.objects.filter(code=company.code).first()
                if not market_issue:
                    continue
                
                margin_data = MarginTradingData.objects.filter(
                    issue=market_issue,
                    date=latest_date
                ).first()
                
                if not margin_data or margin_data.outstanding_sales <= 0:
                    continue
                
                ratio = margin_data.outstanding_purchases / margin_data.outstanding_sales
                all_ratios.append(ratio)
                
                company_ratios.append({
                    'code': company.code,
                    'name': company.name,
                    'sector': company.industry_name_33,
                    'ratio': round(ratio, 2),
                    'outstanding_sales': margin_data.outstanding_sales,
                    'outstanding_purchases': margin_data.outstanding_purchases
                })
                
            except Exception:
                continue
        
        if not all_ratios:
            return {'outliers': [], 'market_stats': {}}
        
        # 全市場統計
        mean_ratio = statistics.mean(all_ratios)
        std_ratio = statistics.stdev(all_ratios) if len(all_ratios) > 1 else 0
        
        # 異常値の閾値設定（2σ）
        upper_threshold = mean_ratio + (2 * std_ratio)
        lower_threshold = mean_ratio - (2 * std_ratio)
        
        # 異常値を抽出
        high_outliers = []
        low_outliers = []
        
        for company in company_ratios:
            ratio = company['ratio']
            if ratio > upper_threshold:
                company['deviation'] = round(ratio - mean_ratio, 2)
                company['type'] = 'high'
                high_outliers.append(company)
            elif ratio < lower_threshold:
                company['deviation'] = round(ratio - mean_ratio, 2)
                company['type'] = 'low'
                low_outliers.append(company)
        
        # 偏差でソート
        high_outliers.sort(key=lambda x: x['deviation'], reverse=True)
        low_outliers.sort(key=lambda x: x['deviation'])
        
        return {
            'outliers': {
                'high': high_outliers[:20],  # 上位20件
                'low': low_outliers[:20]     # 下位20件
            },
            'market_stats': {
                'total_companies': len(all_ratios),
                'mean_ratio': round(mean_ratio, 2),
                'std_ratio': round(std_ratio, 2),
                'upper_threshold': round(upper_threshold, 2),
                'lower_threshold': round(lower_threshold, 2)
            },
            'latest_date': latest_date.strftime('%Y-%m-%d')
        }


class HistoricalTrendsAPIView(LoginRequiredMixin, View):
    """履歴トレンドAPI"""
    
    def get(self, request, *args, **kwargs):
        days = int(request.GET.get('days', 30))  # デフォルト30日
        sector_code = request.GET.get('sector')
        
        try:
            trend_data = self._get_historical_trends(days, sector_code)
            return JsonResponse(trend_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def _get_historical_trends(self, days, sector_code=None):
        """履歴トレンドデータを取得"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # 対象期間のデータ日付を取得
        dates = MarginTradingData.objects.filter(
            date__range=(start_date, end_date)
        ).values_list('date', flat=True).distinct().order_by('date')
        
        if not dates:
            return {'trend_data': [], 'dates': []}
        
        # 業種フィルターがある場合
        target_companies = None
        if sector_code:
            target_companies = CompanyMaster.objects.filter(
                industry_code_33=sector_code
            ).values_list('code', flat=True)
        
        trend_data = []
        
        for date in dates:
            daily_ratios = []
            
            # その日のデータを取得
            margin_data_queryset = MarginTradingData.objects.filter(date=date)
            
            if target_companies:
                margin_data_queryset = margin_data_queryset.filter(
                    issue__code__in=target_companies
                )
            
            for margin_data in margin_data_queryset:
                if margin_data.outstanding_sales > 0:
                    ratio = margin_data.outstanding_purchases / margin_data.outstanding_sales
                    daily_ratios.append(ratio)
            
            if daily_ratios:
                trend_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'avg_ratio': round(statistics.mean(daily_ratios), 2),
                    'median_ratio': round(statistics.median(daily_ratios), 2),
                    'company_count': len(daily_ratios)
                })
        
        return {
            'trend_data': trend_data,
            'dates': [d.strftime('%Y-%m-%d') for d in dates],
            'sector_code': sector_code
        }


class IssueDetailView(LoginRequiredMixin, TemplateView):
    """個別銘柄詳細ビュー"""
    template_name = 'margin_trading/issue_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        code = kwargs.get('code')
        
        # 銘柄情報を取得
        market_issue = get_object_or_404(MarketIssue, code=code)
        company = CompanyMaster.objects.filter(code=code).first()
        
        # 最新の信用取引データ
        latest_data = MarginTradingData.objects.filter(
            issue=market_issue
        ).order_by('-date').first()
        
        # 過去30日間のデータ
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        historical_data = MarginTradingData.objects.filter(
            issue=market_issue,
            date__range=(start_date, end_date)
        ).order_by('date')
        
        context.update({
            'market_issue': market_issue,
            'company': company,
            'latest_data': latest_data,
            'historical_data': historical_data
        })
        
        return context