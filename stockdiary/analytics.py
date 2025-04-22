# stockdiary/analytics.py
"""株式日記の分析機能を提供するモジュール"""
from django.db.models import Count, Avg, Sum, Min, Max, F, Q, Case, When, Value, IntegerField, FloatField
from django.db.models.functions import TruncMonth, Length, Coalesce
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from .models import StockDiary, DiaryNote
from tags.models import Tag
from analysis_template.models import AnalysisTemplate, DiaryAnalysisValue
from .utils import calculate_analysis_completion_rate

import json
import re
from decimal import Decimal
from datetime import timedelta
from collections import Counter, defaultdict
import secrets


class DiaryAnalytics:
    """株式日記データの分析を行うクラス"""
    
    def __init__(self, user):
        self.user = user
    
    def collect_stats(self, diaries, all_diaries):
        """基本的な統計データを収集"""
        # 現在の月の開始日
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        
        # 前月の日付範囲
        prev_month_end = current_month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        
        # 銘柄数の統計 - メモを含めてすべてカウント
        total_stocks = diaries.count()
        prev_month_stocks = all_diaries.filter(
            created_at__gte=prev_month_start,
            created_at__lt=current_month_start
        ).count()
        stocks_change = total_stocks - prev_month_stocks
        
        # タグの統計
        total_tags = Tag.objects.filter(stockdiary__in=diaries).distinct().count()
        prev_month_tags = Tag.objects.filter(
            stockdiary__in=all_diaries,
            stockdiary__created_at__gte=prev_month_start,
            stockdiary__created_at__lt=current_month_start
        ).distinct().count()
        tags_change = total_tags - prev_month_tags
        
        # 分析項目達成率
        # 現在の平均完了率
        current_completion = calculate_analysis_completion_rate(self.user, diaries)
        
        # 前月の平均完了率
        prev_month_diaries = all_diaries.filter(
            created_at__gte=prev_month_start,
            created_at__lt=current_month_start
        )
        prev_completion = calculate_analysis_completion_rate(self.user, prev_month_diaries)
        
        checklist_completion_rate = current_completion
        checklist_rate_change = current_completion - prev_completion
        
        # 平均記録文字数 - すべてのエントリーを対象（メモも含む）
        avg_reason_length = 0
        if diaries.exists():
            # HTMLタグを除去して純粋なテキスト長を計算
            reason_lengths = []
            for diary in diaries:
                raw_text = strip_tags(diary.reason)
                reason_lengths.append(len(raw_text))
            
            if reason_lengths:
                avg_reason_length = int(sum(reason_lengths) / len(reason_lengths))
        
        # 前月の平均記録文字数
        last_month_avg_length = 0
        if prev_month_diaries.exists():
            last_month_lengths = []
            for diary in prev_month_diaries:
                raw_text = strip_tags(diary.reason)
                last_month_lengths.append(len(raw_text))
            
            if last_month_lengths:
                last_month_avg_length = int(sum(last_month_lengths) / len(last_month_lengths))
        
        reason_length_change = avg_reason_length - last_month_avg_length
        
        return {
            'total_stocks': total_stocks,
            'stocks_change': stocks_change,
            'total_tags': total_tags,
            'tags_change': tags_change,
            'checklist_completion_rate': checklist_completion_rate,
            'checklist_rate_change': checklist_rate_change,
            'avg_reason_length': avg_reason_length,
            'reason_length_change': reason_length_change
        }
    
    def get_investment_summary_data(self, diaries, all_diaries, active_diaries, sold_diaries):
        """投資状況サマリー関連のデータを取得"""
        # メモエントリー（is_memo=True または price/quantity が None）をフィルタリング
        transaction_diaries = [d for d in diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        transaction_active_diaries = [d for d in active_diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        transaction_sold_diaries = [d for d in sold_diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        
        # 1. 総投資額の計算 - メモを除外
        total_investment = sum(
            d.purchase_price * d.purchase_quantity 
            for d in transaction_diaries
        )
        
        # 2. 前月比較用のデータ
        last_month = timezone.now().date() - timedelta(days=30)
        last_month_diaries = StockDiary.objects.filter(
            user=self.user, 
            purchase_date__lt=last_month
        )
        # メモを除外して計算
        last_month_transactions = [d for d in last_month_diaries if not (d.is_memo or d.purchase_price is None or d.purchase_quantity is None)]
        last_month_investment = sum(
            d.purchase_price * d.purchase_quantity 
            for d in last_month_transactions
        )
        
        investment_change = total_investment - last_month_investment
        investment_change_percent = (investment_change / last_month_investment * 100) if last_month_investment else 0
        
        # 3. 実現利益（売却済み株式の損益）
        realized_profit = Decimal('0')
        for diary in transaction_sold_diaries:
            profit = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
            realized_profit += profit
        
        # 4. 現在の保有総額（購入額ベース、API依存なし）
        active_investment = sum(
            d.purchase_price * d.purchase_quantity 
            for d in transaction_active_diaries
        )

        # 5. 総利益/損失 = 実現利益のみ（未実現利益は考慮しない）
        total_profit = realized_profit
                
        # 6. 前月の利益比較（売却済みのみ）
        last_month_sold = [d for d in last_month_transactions if d.sell_date]
        last_month_profit = Decimal('0')
        
        # 前月の実現利益
        for diary in last_month_sold:
            last_month_profit += (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
        
        profit_change = total_profit - last_month_profit
        profit_change_percent = (profit_change / last_month_profit * 100) if last_month_profit else 0
        
        # 7. 保有銘柄数 - メモエントリーではない銘柄のみカウント
        active_stocks_count = len(transaction_active_diaries)
        last_month_active_stocks = len([d for d in last_month_transactions if not d.sell_date])
        stocks_count_change = active_stocks_count - last_month_active_stocks
        
        # 8. 平均保有期間（売却済みのみ）
        avg_holding_period = 0
        if transaction_sold_diaries:
            total_days = sum((d.sell_date - d.purchase_date).days for d in transaction_sold_diaries)
            avg_holding_period = total_days / len(transaction_sold_diaries)
        
        # 前月の平均保有期間 - メモエントリーを除外
        last_month_avg_holding_period = 0
        if last_month_sold:
            last_month_total_days = sum((d.sell_date - d.purchase_date).days for d in last_month_sold)
            last_month_avg_holding_period = last_month_total_days / len(last_month_sold)
        
        holding_period_change = avg_holding_period - last_month_avg_holding_period
        
        return {
            'total_investment': total_investment,
            'active_investment': active_investment,
            'investment_change': investment_change,
            'investment_change_percent': investment_change_percent,
            'total_profit': total_profit,
            'profit_change': profit_change,
            'profit_change_percent': profit_change_percent,
            'active_stocks_count': active_stocks_count,
            'stocks_count_change': stocks_count_change,
            'avg_holding_period': avg_holding_period,
            'holding_period_change': holding_period_change,
            'realized_profit': realized_profit,
            'active_holdings_count': active_stocks_count,
        }
    
    def get_tag_analysis_data(self, diaries):
        """タグ分析データを取得"""
        # タグ使用頻度
        tag_counts = Tag.objects.filter(
            stockdiary__in=diaries
        ).annotate(
            count=Count('stockdiary')
        ).order_by('-count')
        
        # 上位10件のタグ
        top_tags = list(tag_counts[:10])
        
        # タグ名とカウントのリスト
        tag_names = [tag.name for tag in top_tags]
        tag_counts_list = [tag.count for tag in top_tags]
        
        # タグの合計使用回数
        total_tag_usage = sum(tag_counts_list) if tag_counts_list else 0
        
        # タグごとのパーセンテージを計算
        for tag in top_tags:
            tag.percentage = (tag.count / total_tag_usage * 100) if total_tag_usage > 0 else 0
        
        # 関連タグを計算 - 修正部分
        for tag in top_tags:
            # このタグを持つ日記をすべて取得
            tag_diaries_ids = diaries.filter(tags=tag).values_list('id', flat=True)
            
            # これらの日記で使われている他のタグをカウント
            related_tags_data = Tag.objects.filter(
                stockdiary__in=tag_diaries_ids
            ).exclude(
                id=tag.id  # 自分自身を除外
            ).annotate(
                related_count=Count('stockdiary')
            ).order_by('-related_count')[:5]  # 上位5つの関連タグ
            
            # 関連タグリストを作成
            tag.related_tags = [
                {'name': related.name, 'count': related.related_count}
                for related in related_tags_data
            ]
        
        # タグごとの投資パフォーマンス
        tag_performance = []
        most_profitable_tag = None
        max_profit_rate = -999  # 最も低い値で初期化
        
        for tag in tag_counts:
            # タグが付いた日記を取得
            tag_diaries = diaries.filter(tags=tag)
            
            # 平均保有期間
            avg_holding_period = 0
            profit_rate_sum = 0
            profit_sum = 0
            count_with_profit = 0
            
            for diary in tag_diaries:
                # 価格・数量情報があるエントリーのみ処理
                if diary.sell_date and diary.purchase_price is not None and diary.purchase_quantity is not None and diary.sell_price is not None:
                    try:
                        # 保有期間
                        holding_period = (diary.sell_date - diary.purchase_date).days
                        avg_holding_period += holding_period
                        
                        # 収益率
                        profit_rate = ((diary.sell_price - diary.purchase_price) / diary.purchase_price) * 100
                        profit_rate_sum += profit_rate
                        
                        # 総利益
                        profit = (diary.sell_price - diary.purchase_price) * diary.purchase_quantity
                        profit_sum += profit
                        
                        count_with_profit += 1
                    except (TypeError, ZeroDivisionError):
                        # 価格が0やNoneの場合のエラー処理
                        continue

            # デフォルト値を設定
            avg_profit_rate = 0
            
            if count_with_profit > 0:
                avg_holding_period /= count_with_profit
                avg_profit_rate = profit_rate_sum / count_with_profit
            
            # 最も収益率の高いタグを更新
            if avg_profit_rate > max_profit_rate:
                max_profit_rate = avg_profit_rate
                most_profitable_tag = tag.name
            
            tag_performance.append({
                'name': tag.name,
                'count': tag.count,
                'avg_holding_period': round(avg_holding_period, 1),
                'avg_profit_rate': round(avg_profit_rate, 2),
                'total_profit': profit_sum
            })
        
        # タグの時系列使用状況
        six_months_ago = timezone.now() - timedelta(days=180)
        tag_timeline = StockDiary.objects.filter(
            user=self.user,
            purchase_date__gte=six_months_ago
        ).prefetch_related('tags').annotate(
            month=TruncMonth('purchase_date')
        )
        
        # 月ごとにタグの使用回数を集計
        tag_month_data = defaultdict(lambda: defaultdict(int))
        
        for diary in tag_timeline:
            month_str = diary.month.strftime('%Y-%m')
            for tag in diary.tags.all():
                tag_month_data[month_str][tag.id] += 1
        
        # 月のリストを生成（過去6ヶ月）
        months = []
        current = timezone.now()
        for i in range(5, -1, -1):
            month = (current - timedelta(days=30 * i)).strftime('%Y-%m')
            months.append(month)
        
        # 上位5タグの時系列データを準備
        top_5_tags = tag_counts[:5]
        tag_timeline_data = []
        
        for tag in top_5_tags:
            data_points = [tag_month_data[month].get(tag.id, 0) for month in months]
            tag_timeline_data.append({
                'label': tag.name,
                'data': data_points,
                'borderColor': f'rgba({hash(tag.name) % 255}, {(hash(tag.name) * 2) % 255}, {(hash(tag.name) * 3) % 255}, 0.7)',
                'backgroundColor': f'rgba({hash(tag.name) % 255}, {(hash(tag.name) * 2) % 255}, {(hash(tag.name) * 3) % 255}, 0.1)',
                'fill': True,
                'tension': 0.4
            })
        
        return {
            'tag_names': json.dumps(tag_names),
            'tag_counts': json.dumps(tag_counts_list),
            'top_tags': top_tags,
            'most_profitable_tag': most_profitable_tag if most_profitable_tag else "データなし",
            'tag_performance': tag_performance,
            'tag_timeline_labels': json.dumps(months),
            'tag_timeline_data': json.dumps(tag_timeline_data)
        }    
 
    def get_activity_analysis_data(self, diaries, all_diaries):
        """活動分析データを取得"""
        # 活動ヒートマップ用のデータ（過去30日間）
        activity_heatmap = []
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        for i in range(31):
            day = thirty_days_ago + timedelta(days=i)
            day_count = all_diaries.filter(purchase_date=day).count()
            
            # ヒートマップの強度レベル（0-5）
            if day_count == 0:
                level = 0
            elif day_count == 1:
                level = 1
            elif day_count == 2:
                level = 2
            elif day_count <= 4:
                level = 3
            elif day_count <= 6:
                level = 4
            else:
                level = 5
            
            activity_heatmap.append({
                'date': day.strftime('%Y-%m-%d'),
                'day': day.day,
                'count': day_count,
                'level': level
            })
        
        # 月ごとの記録数
        monthly_data = all_diaries.annotate(
            month=TruncMonth('purchase_date')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        last_6_months = []
        current = timezone.now()
        for i in range(5, -1, -1):
            month = (current - timedelta(days=30 * i))
            last_6_months.append(month.strftime('%Y-%m'))
        
        monthly_counts = []
        for month_str in last_6_months:
            year, month = map(int, month_str.split('-'))
            count = 0
            for data in monthly_data:
                if data['month'].year == year and data['month'].month == month:
                    count = data['count']
                    break
            monthly_counts.append(count)
        
        # 曜日別記録数
        day_of_week_counts = [0] * 7  # 0: 月曜日, 6: 日曜日
        
        for diary in all_diaries:
            day_of_week = diary.purchase_date.weekday()
            day_of_week_counts[day_of_week] += 1
        
        # 最も記録が多い曜日
        max_day_index = day_of_week_counts.index(max(day_of_week_counts))
        weekdays = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']
        most_active_day = weekdays[max_day_index]
        
        # 平日/週末のパターン
        weekday_sum = sum(day_of_week_counts[:5])
        weekend_sum = sum(day_of_week_counts[5:])
        
        if weekday_sum > weekend_sum * 2:
            weekday_pattern = "主に平日"
        elif weekend_sum > weekday_sum * 2:
            weekday_pattern = "主に週末"
        elif weekday_sum > weekend_sum:
            weekday_pattern = "平日が多め"
        elif weekend_sum > weekday_sum:
            weekday_pattern = "週末が多め"
        else:
            weekday_pattern = "平日と週末で均等"
        
        # 月平均記録数
        monthly_avg_records = sum(monthly_counts) / len(monthly_counts) if monthly_counts else 0
        
        # 最も活発な月
        if monthly_counts:
            max_month_index = monthly_counts.index(max(monthly_counts))
            most_active_month = last_6_months[max_month_index]
            most_active_month = f"{most_active_month[:4]}年{most_active_month[5:]}月"
        else:
            most_active_month = None
        
        # 購入頻度
        total_days = (timezone.now().date() - all_diaries.order_by('purchase_date').first().purchase_date).days if all_diaries.exists() else 0
        purchase_frequency = total_days / all_diaries.count() if all_diaries.exists() else 0
        
        # 記録内容の長さ分布
        lengths = all_diaries.annotate(
            content_length=Length('reason')
        ).values_list('content_length', flat=True)
        
        # 長さの範囲を定義
        length_ranges = ['〜200字', '201-500字', '501-1000字', '1001-2000字', '2001字〜']
        length_counts = [0] * 5
        
        for length in lengths:
            if length <= 200:
                length_counts[0] += 1
            elif length <= 500:
                length_counts[1] += 1
            elif length <= 1000:
                length_counts[2] += 1
            elif length <= 2000:
                length_counts[3] += 1
            else:
                length_counts[4] += 1
        
        return {
            'activity_heatmap': activity_heatmap,
            'monthly_labels': json.dumps(last_6_months),
            'monthly_counts': json.dumps(monthly_counts),
            'day_of_week_counts': json.dumps(day_of_week_counts),
            'most_active_day': most_active_day,
            'weekday_pattern': weekday_pattern,
            'monthly_avg_records': round(monthly_avg_records, 1),
            'most_active_month': most_active_month,
            'purchase_frequency': round(purchase_frequency, 1),
            'content_length_ranges': json.dumps(length_ranges),
            'content_length_counts': json.dumps(length_counts)
        }
    
    def prepare_holding_period_data(self, diaries):
        """保有期間分布データを準備"""
        # 保有期間の範囲を定義
        ranges = ['~1週間', '1週間~1ヶ月', '1~3ヶ月', '3~6ヶ月', '6ヶ月~1年', '1年以上']
        counts = [0, 0, 0, 0, 0, 0]
        
        # 売却済みの日記で保有期間を集計 (None値のチェックを追加)
        sold_diaries = [
            d for d in diaries.filter(sell_date__isnull=False)
            if d.purchase_price is not None and d.purchase_quantity is not None
        ]
        
        for diary in sold_diaries:
            holding_period = (diary.sell_date - diary.purchase_date).days
            
            if holding_period <= 7:
                counts[0] += 1
            elif holding_period <= 30:
                counts[1] += 1
            elif holding_period <= 90:
                counts[2] += 1
            elif holding_period <= 180:
                counts[3] += 1
            elif holding_period <= 365:
                counts[4] += 1
            else:
                counts[5] += 1
        
        return {
            'ranges': ranges,
            'counts': counts
        }
    
    def prepare_recent_trends(self, diaries):
        """最近の投資傾向データを準備"""
        # 価格・数量情報があるエントリーだけをフィルタリング
        valid_diaries = [d for d in diaries if d.purchase_price is not None and d.purchase_quantity is not None]
        
        # 購入頻度
        purchase_frequency = 30  # デフォルト値
        if len(valid_diaries) >= 2:
            sorted_diaries = sorted(valid_diaries, key=lambda x: x.purchase_date, reverse=True)
            first_date = sorted_diaries[0].purchase_date
            last_date = sorted_diaries[-1].purchase_date
            date_range = (first_date - last_date).days
            if date_range > 0 and len(valid_diaries) > 1:
                purchase_frequency = round(date_range / (len(valid_diaries) - 1))
        
        # 平均保有期間
        avg_holding_period = 0
        sold_diaries = [d for d in valid_diaries if d.sell_date]
        if sold_diaries:
            total_days = sum((d.sell_date - d.purchase_date).days for d in sold_diaries)
            avg_holding_period = round(total_days / len(sold_diaries))
        
        # よく使うタグ
        most_used_tag = "なし"
        tag_counts = {}
        for diary in diaries:  # すべての日記を対象（メモも含む）
            for tag in diary.tags.all():
                if tag.name in tag_counts:
                    tag_counts[tag.name] += 1
                else:
                    tag_counts[tag.name] = 1
        
        if tag_counts:
            most_used_tag = max(tag_counts.items(), key=lambda x: x[1])[0]
        
        # 最も詳細な記録
        most_detailed_record = "なし"
        max_length = 0
        for diary in diaries:  # すべての日記を対象（メモも含む）
            text_length = len(strip_tags(diary.reason))
            if text_length > max_length:
                max_length = text_length
                most_detailed_record = diary.stock_name
        
        # キーワード抽出
        keywords = []
        if diaries.count() > 0:
            # 最新10件の日記から頻出単語を抽出
            recent_diaries = diaries.order_by('-purchase_date')[:10]
            text_content = ' '.join([strip_tags(d.reason) for d in recent_diaries])
            
            # 簡易的な形態素解析（実際は形態素解析ライブラリを使用するべき）
            # 一般的な日本語のストップワード
            stop_words = ['の', 'に', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し', 'れ', 'さ', 'ある', 'いる', 'する', 'から', 'など', 'こと', 'これ', 'それ', 'もの']
            
            # 単語の簡易的な抽出（より精緻な形態素解析が必要）
            words = re.findall(r'\w+', text_content)
            word_counts = Counter(word for word in words if len(word) > 1 and word not in stop_words)
            
            # 上位5キーワードを抽出
            keywords = [{'word': word, 'count': count} for word, count in word_counts.most_common(5)]
        
        return {
            'purchase_frequency': purchase_frequency,
            'avg_holding_period': avg_holding_period,
            'most_used_tag': most_used_tag,
            'most_detailed_record': most_detailed_record,
            'keywords': keywords
        }

    def get_template_analysis_data(self, filter_params=None):
        """分析テンプレートのデータを取得・分析する関数"""
        # 基本的なフィルタリング - ユーザーのデータのみ
        templates = AnalysisTemplate.objects.filter(user=self.user)
        template_ids = list(templates.values_list('id', flat=True))
        
        # 日記に紐づく分析値を取得
        analysis_values = DiaryAnalysisValue.objects.filter(
            analysis_item__template__id__in=template_ids,
            diary__user=self.user
        ).select_related('diary', 'analysis_item', 'analysis_item__template')
        
        # フィルターが提供されている場合の絞り込み
        if filter_params:
            if 'date_from' in filter_params and filter_params['date_from']:
                analysis_values = analysis_values.filter(diary__purchase_date__gte=filter_params['date_from'])
            if 'tag_id' in filter_params and filter_params['tag_id']:
                analysis_values = analysis_values.filter(diary__tags__id=filter_params['tag_id'])
            if 'status' in filter_params and filter_params['status'] == 'active':
                analysis_values = analysis_values.filter(diary__sell_date__isnull=True)
            elif 'status' in filter_params and filter_params['status'] == 'sold':
                analysis_values = analysis_values.filter(diary__sell_date__isnull=False)
        
        # テンプレート使用統計データの収集
        template_stats = []
        template_usage_counts = {}
        
        # テンプレートIDごとに分析値をグループ化
        template_values = defaultdict(list)
        for value in analysis_values:
            template_id = value.analysis_item.template.id
            template_values[template_id].append(value)
        
        # 各アイテムごとの使用状況と完了率の準備
        items_analysis = []
        
        for template in templates:
            # このテンプレートの分析値
            values = template_values.get(template.id, [])
            
            # 使用回数計算 - ユニークな日記IDの数
            diary_ids = set(v.diary_id for v in values)
            usage_count = len(diary_ids)
            template_usage_counts[template.id] = usage_count
            
            # 最新の使用日を取得
            last_used = None
            if values:
                latest_values = sorted(values, key=lambda x: x.diary.purchase_date, reverse=True)
                if latest_values:
                    last_used = latest_values[0].diary.purchase_date
            
            # 平均完了率の計算 - 各日記ごとの完了項目数/全項目数
            total_items = template.items.count()
            completion_rates = []
            
            # 日記ごとに完了率を計算
            for diary_id in diary_ids:
                diary_values = [v for v in values if v.diary_id == diary_id]
                completed_items = 0
                
                for value in diary_values:
                    if value.analysis_item.item_type == 'boolean' or value.analysis_item.item_type == 'boolean_with_value':
                        if value.boolean_value:
                            completed_items += 1
                    elif value.analysis_item.item_type == 'number':
                        if value.number_value is not None:
                            completed_items += 1
                    elif value.analysis_item.item_type == 'select' or value.analysis_item.item_type == 'text':
                        if value.text_value:
                            completed_items += 1
                
                if total_items > 0:
                    completion_rate = (completed_items / total_items) * 100
                    completion_rates.append(completion_rate)
            
            avg_completion_rate = sum(completion_rates) / len(completion_rates) if completion_rates else 0
            
            # 使用トレンドの計算（過去3ヶ月と比較した前月）
            trend = 0
            if usage_count > 0:
                # 前月の使用回数
                one_month_ago = timezone.now() - timedelta(days=30)
                two_months_ago = timezone.now() - timedelta(days=60)
                
                prev_month_count = DiaryAnalysisValue.objects.filter(
                    analysis_item__template_id=template.id,
                    diary__user=self.user,
                    diary__purchase_date__gte=two_months_ago,
                    diary__purchase_date__lt=one_month_ago
                ).values('diary').distinct().count()
                
                if prev_month_count > 0:
                    # 前月と比較した成長率
                    trend = ((usage_count - prev_month_count) / prev_month_count) * 100
                else:
                    trend = 100 if usage_count > 0 else 0
            
            template_stats.append({
                'id': template.id,
                'name': template.name,
                'usage_count': usage_count,
                'avg_completion_rate': avg_completion_rate,
                'last_used': last_used,
                'trend': trend
            })
            
            # 各アイテムの分析データを追加
            for item in template.items.all():
                # このアイテムに関連する分析値を集める
                item_values = [v for v in values if v.analysis_item_id == item.id]
                item_usage_count = len(item_values)
                
                # 完了率を計算
                item_completion_count = 0
                for value in item_values:
                    if item.item_type == 'boolean' or item.item_type == 'boolean_with_value':
                        if value.boolean_value:
                            item_completion_count += 1
                    elif item.item_type == 'number':
                        if value.number_value is not None:
                            item_completion_count += 1
                    elif item.item_type == 'select' or item.item_type == 'text':
                        if value.text_value:
                            item_completion_count += 1
                
                completion_rate = (item_completion_count / item_usage_count * 100) if item_usage_count > 0 else 0
                
                # 平均値の計算（数値項目の場合）
                average_value = None
                most_common_value = None
                
                if item.item_type == 'number' and item_values:
                    number_values = [v.number_value for v in item_values if v.number_value is not None]
                    if number_values:
                        average_value = sum(number_values) / len(number_values)
                
                # 最も一般的な値（選択肢項目の場合）
                if item.item_type == 'select' and item_values:
                    text_values = [v.text_value for v in item_values if v.text_value]
                    if text_values:
                        value_counts = Counter(text_values)
                        most_common_value = value_counts.most_common(1)[0][0] if value_counts else None
                
                items_analysis.append({
                    'template_id': template.id,
                    'template_name': template.name,
                    'name': item.name,
                    'description': item.description,
                    'item_type': item.item_type,
                    'usage_count': item_usage_count,
                    'completion_rate': completion_rate,
                    'average_value': average_value,
                    'most_common_value': most_common_value
                })
        
        # テンプレート種類別の分布
        template_categories = {
            '財務分析': ['PER', 'PBR', 'ROE', '配当', '収益', '財務', '利益'],
            'テクニカル分析': ['RSI', 'MACD', 'ボリンジャー', '移動平均', 'チャート'],
            'ファンダメンタル分析': ['成長', '競争', '優位', '市場'],
            'バリュー投資': ['割安', 'バフェット', '長期'],
            '投資心理': ['心理', 'バイアス', '感情'],
            'ESG評価': ['ESG', '環境', '社会', 'ガバナンス']
        }
        
        template_type_data = defaultdict(int)
        template_type_labels = []
        
        for template in templates:
            categorized = False
            for category, keywords in template_categories.items():
                if any(keyword in template.name or keyword in template.description for keyword in keywords):
                    template_type_data[category] += template_usage_counts.get(template.id, 0)
                    if category not in template_type_labels:
                        template_type_labels.append(category)
                    categorized = True
                    break
            
            if not categorized:
                template_type_data['その他'] += template_usage_counts.get(template.id, 0)
                if 'その他' not in template_type_labels:
                    template_type_labels.append('その他')
        
        # 最もよく使われるテンプレート
        most_used_template = None
        if template_stats:
            most_used = max(template_stats, key=lambda x: x['usage_count'])
            if most_used['usage_count'] > 0:
                most_used_template = {
                    'name': most_used['name'],
                    'count': most_used['usage_count']
                }
        
        # 最も完了率が高いテンプレート
        highest_completion_template = None
        if template_stats:
            highest_completion = max(template_stats, key=lambda x: x['avg_completion_rate'])
            if highest_completion['avg_completion_rate'] > 0:
                highest_completion_template = {
                    'name': highest_completion['name'],
                    'rate': highest_completion['avg_completion_rate']
                }
        
        # 最も改善が見られたテンプレート（トレンド値が最も高い）
        most_improved_template = None
        improved_templates = [t for t in template_stats if t['trend'] > 0]
        if improved_templates:
            most_improved = max(improved_templates, key=lambda x: x['trend'])
            most_improved_template = {
                'name': most_improved['name'],
                'improvement': most_improved['trend']
            }
        
        # テンプレート使用回数の時系列データ
        # 過去6ヶ月の月ごとの使用回数を集計
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_usage = DiaryAnalysisValue.objects.filter(
            analysis_item__template__id__in=template_ids,
            diary__user=self.user,
            diary__purchase_date__gte=six_months_ago
        ).annotate(
            month=TruncMonth('diary__purchase_date')
        ).values('month', 'analysis_item__template_id').annotate(
            count=Count('diary_id', distinct=True)
        ).order_by('month')
        
        # 月ごとの使用回数をテンプレート別に集計
        monthly_data = defaultdict(lambda: defaultdict(int))
        for entry in monthly_usage:
            month_str = entry['month'].strftime('%Y-%m')
            template_id = entry['analysis_item__template_id']
            monthly_data[month_str][template_id] = entry['count']
        
        # 月のリストを生成（過去6ヶ月）
        months = []
        current = timezone.now()
        for i in range(5, -1, -1):
            month = (current - timedelta(days=30 * i)).strftime('%Y-%m')
            months.append(month)
        
        # テンプレート使用回数の時系列データをJSON形式で準備
        template_usage_labels = months
        template_usage_data = []
        for template in templates:
            data_points = [monthly_data[month].get(template.id, 0) for month in months]
            template_usage_data.append({
                'name': template.name,
                'data': data_points
            })
        
        # チャート用に集計した総使用回数
        template_usage_totals = [sum(monthly_data[month].values()) for month in months]
        
        # テンプレート完了率の計算（チェックリスト完了率のチャート用）
        checklist_names = []
        checklist_completion_rates = []
        
        for template in template_stats:
            if template['usage_count'] > 0:  # 使用されたテンプレートのみ
                checklist_names.append(template['name'])
                checklist_completion_rates.append(round(template['avg_completion_rate'], 1))
        
        # テンプレート名とその使用回数（円グラフ用）
        template_names = [template.name for template in templates]
        template_counts = [template_usage_counts.get(template.id, 0) for template in templates]
        
        return {
            'template_stats': template_stats,
            'most_used_template': most_used_template,
            'highest_completion_template': highest_completion_template,
            'most_improved_template': most_improved_template,
            'template_usage_labels': json.dumps(template_usage_labels),
            'template_usage_data': json.dumps(template_usage_totals),
            'template_type_labels': json.dumps(template_type_labels),
            'template_type_data': json.dumps([template_type_data[label] for label in template_type_labels]),
            'checklist_names': json.dumps(checklist_names),
            'checklist_completion_rates': json.dumps(checklist_completion_rates),
            'all_templates': templates,
            'items_analysis': items_analysis,  # 新しく追加した分析アイテムデータ
            'template_names': json.dumps(template_names),  # チャート用のテンプレート名
            'template_counts': json.dumps(template_counts)  # チャート用の使用回数
        }        
# analytics.py の DiaryAnalytics クラスに追加するメソッド

    def get_sector_analysis_data(self, diaries, all_diaries):
        """
        セクター分析データを取得
        """
        from django.db.models import Count, Avg, F, ExpressionWrapper, FloatField, Q, StdDev
        from django.db.models.functions import Length
        from collections import defaultdict
        from stockdiary.templatetags.sector_analysis_tags import get_sector_correlation_data
        import json
        from decimal import Decimal
        
        # 結果格納用の辞書
        result = {
            'sector_allocation_data': {'labels': [], 'values': []},
            'sector_stocks_data': {'labels': [], 'counts': [], 'investments': []},
            'sector_performance_data': {'labels': [], 'returns': [], 'success_rates': []},
            'sector_correlation_data': [],
            'highest_return_sector': {'name': '', 'value': 0},
            'highest_success_sector': {'name': '', 'value': 0},
            'most_stable_sector': {'name': '', 'value': 0},
            'portfolio_hints': [],
            'total_investment': 0
        }
        
        # 投資データがない場合は空のデータを返す
        if not diaries:
            return result
        
        # 総投資額を計算（配分比率の計算に使用）
        total_investment = sum([
            diary.purchase_price * diary.purchase_quantity 
            for diary in diaries 
            if diary.purchase_price and diary.purchase_quantity
        ])
        result['total_investment'] = total_investment
        
        # セクターごとに日記をグループ化
        sector_groups = defaultdict(list)
        for diary in diaries:
            sector_name = diary.sector or '未分類'
            sector_groups[sector_name].append(diary)
        
        # セクター別の分析を行う
        sector_stats = []
        
        for sector_name, sector_diaries in sector_groups.items():
            # 銘柄数
            count = len(sector_diaries)
            
            # 投資額 - Decimal型を維持
            investment = sum([
                diary.purchase_price * diary.purchase_quantity 
                for diary in sector_diaries 
                if diary.purchase_price and diary.purchase_quantity
            ])

            # 平均投資額 - Decimal型の除算
            avg_investment = Decimal(investment) / Decimal(count) if count > 0 else Decimal('0')
            
            # 配分率 - Decimal型の除算
            allocation = (Decimal(investment) / Decimal(total_investment)) * Decimal('100') if total_investment > 0 else Decimal('0')
            
            # リターン計算
            returns = []
            for diary in sector_diaries:
                if diary.sell_date and diary.purchase_price and diary.sell_price:
                    # Decimal同士の計算を保証
                    return_rate = ((Decimal(diary.sell_price) - Decimal(diary.purchase_price)) / Decimal(diary.purchase_price)) * Decimal('100')
                    returns.append(return_rate)
            
            # 平均リターン - Decimal型の除算
            avg_return = sum(returns) / Decimal(len(returns)) if returns else Decimal('0')
            
            # リターンの標準偏差（変動性）
            if len(returns) >= 2:
                import statistics
                # 計算前にfloatに変換
                return_volatility = statistics.stdev([float(r) for r in returns])
            else:
                return_volatility = 0
            
            # 成功率
            sold_diaries = [d for d in sector_diaries if d.sell_date and d.purchase_price and d.sell_price]
            if sold_diaries:
                successful = sum(1 for d in sold_diaries if d.sell_price >= d.purchase_price)
                # floatとDecimalの混合を避けるため、Decimal型で統一
                success_rate = (Decimal(successful) / Decimal(len(sold_diaries))) * Decimal('100')
            else:
                success_rate = Decimal('0')
            
            sector_stats.append({
                'name': sector_name,
                'count': count,
                'investment': investment,
                'avg_investment': avg_investment,
                'allocation': allocation,
                'avg_return': avg_return,
                'return_volatility': return_volatility,
                'success_rate': success_rate
            })
        
        # 分析結果から各種データを生成
        if not sector_stats:
            # デフォルトセクターデータ
            default_sector = {
                'name': 'サンプル',
                'count': 1,
                'investment': Decimal('0'),
                'avg_investment': Decimal('0'),
                'allocation': Decimal('100.0'),
                'avg_return': Decimal('0.0'),
                'return_volatility': 0,
                'success_rate': Decimal('0.0')
            }
            sector_stats = [default_sector]
        
        # 少なくとも1つのセクターがある場合にチャートを生成
        if len(sector_stats) >= 1:
            # 1. セクター別投資配分
            allocation_data = sorted(sector_stats, key=lambda x: x['allocation'], reverse=True)
            result['sector_allocation_data'] = {
                'labels': [stat['name'] for stat in allocation_data],
                'values': [float(round(stat['allocation'], 1)) for stat in allocation_data]  # Decimalをfloatに変換
            }

            # 2. セクター別銘柄数と平均投資額
            filtered_stats = [stat for stat in sector_stats if stat['name'] != '未分類']
            stocks_data = sorted(filtered_stats, key=lambda x: x['count'], reverse=True)
            result['sector_stocks_data'] = {
                'labels': [stat['name'] for stat in stocks_data],
                'counts': [int(stat['count']) for stat in stocks_data],
                'investments': [float(round(stat['avg_investment'], 0)) for stat in stocks_data]  # Decimalをfloatに変換
            }

            # 3. セクター別リターンと成功率
            performance_data = sorted(sector_stats, key=lambda x: x['avg_return'], reverse=True)
            result['sector_performance_data'] = {
                'labels': [stat['name'] for stat in performance_data],
                'returns': [float(round(stat['avg_return'], 1)) for stat in performance_data],  # Decimalをfloatに変換
                'success_rates': [float(round(stat['success_rate'], 1)) for stat in performance_data]  # Decimalをfloatに変換
            }
            
            # 4. セクター間相関行列
            result['sector_correlation_data'] = get_sector_correlation_data(diaries)
        
        # 最も成績の良いセクターを特定
        if sector_stats:
            # リターンが最も高いセクター
            highest_return = max(sector_stats, key=lambda x: x['avg_return'])
            if highest_return['avg_return'] > 0:
                result['highest_return_sector'] = {
                    'name': highest_return['name'],
                    'value': float(highest_return['avg_return'])  # Decimalをfloatに変換
                }
            
            # 成功率が最も高いセクター
            highest_success = max(sector_stats, key=lambda x: x['success_rate'])
            if highest_success['success_rate'] > 0:
                result['highest_success_sector'] = {
                    'name': highest_success['name'],
                    'value': float(highest_success['success_rate'])  # Decimalをfloatに変換
                }
            
            # 最も安定性の高い（変動性の低い）セクター
            stable_sectors = [s for s in sector_stats if s['return_volatility'] > 0]
            if stable_sectors:
                most_stable = min(stable_sectors, key=lambda x: x['return_volatility'])
                result['most_stable_sector'] = {
                    'name': most_stable['name'],
                    'value': float(most_stable['return_volatility'])
                }
                
        return result
        