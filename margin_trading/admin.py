# admin.py
from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.core.management import call_command
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import subprocess
import sys
import json
from datetime import datetime, date
import threading
from .models import MarketIssue, MarginTradingData, DataImportLog

@admin.register(MarketIssue)
class MarketIssueAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'jp_code', 'category', 'latest_data_date']
    list_filter = ['category']
    search_fields = ['code', 'name', 'jp_code']
    ordering = ['code']
    
    def latest_data_date(self, obj):
        latest = MarginTradingData.objects.filter(issue=obj).order_by('-date').first()
        return latest.date if latest else '-'
    latest_data_date.short_description = '最新データ日付'

@admin.register(MarginTradingData)
class MarginTradingDataAdmin(admin.ModelAdmin):
    list_display = [
        'issue_code', 'issue_name', 'date',
        'outstanding_sales_formatted', 'outstanding_purchases_formatted',
        'margin_ratio'
    ]
    list_filter = ['date', 'issue__category']
    search_fields = ['issue__code', 'issue__name']
    date_hierarchy = 'date'
    ordering = ['-date', 'issue__code']
    
    # カスタムアクション
    actions = ['execute_batch_import']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('batch-import/', self.batch_import_view, name='batch_import'),
            path('batch-status/', self.batch_status_view, name='batch_status'),
        ]
        return custom_urls + urls
    
    def issue_code(self, obj):
        return obj.issue.code
    issue_code.short_description = '証券コード'
    
    def issue_name(self, obj):
        return obj.issue.name
    issue_name.short_description = '銘柄名'
    
    def outstanding_sales_formatted(self, obj):
        return f'{obj.outstanding_sales:,}' if obj.outstanding_sales else '0'
    outstanding_sales_formatted.short_description = '売残高'
    
    def outstanding_purchases_formatted(self, obj):
        return f'{obj.outstanding_purchases:,}' if obj.outstanding_purchases else '0'
    outstanding_purchases_formatted.short_description = '買残高'
    
    def margin_ratio(self, obj):
        if obj.outstanding_purchases == 0:
            return '-'
        ratio = obj.outstanding_sales / obj.outstanding_purchases
        color = 'red' if ratio > 1 else 'blue'
        # format_htmlではf-stringのフォーマット指定が使えないので、先にフォーマット
        ratio_formatted = f"{ratio:.2f}"
        return format_html(
            '<span style="color: {};">{}</span>',
            color, ratio_formatted
        )
    margin_ratio.short_description = '信用倍率'
    
    def execute_batch_import(self, request, queryset):
        """アクションからバッチ実行"""
        return HttpResponseRedirect('/admin/margin_trading/margintradingdata/batch-import/')
    execute_batch_import.short_description = "JPXデータ取得実行"
    
    def batch_import_view(self, request):
        """バッチ実行画面"""
        # 管理者権限チェック
        if not request.user.is_staff:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        if request.method == 'POST':
            date_str = request.POST.get('date')
            force = request.POST.get('force') == 'on'
            command_type = request.POST.get('command_type', 'standard')
            
            try:
                # バックグラウンドでバッチ実行
                thread = threading.Thread(
                    target=self._run_batch_command,
                    args=(date_str, force, command_type, request.user.id)
                )
                thread.daemon = True
                thread.start()
                
                messages.success(request, 'バッチ処理を開始しました。ログを確認してください。')
                return redirect('/admin/margin_trading/dataimportlog/')
                
            except Exception as e:
                messages.error(request, f'バッチ実行エラー: {str(e)}')
        
        # 最新のログを取得
        recent_logs = DataImportLog.objects.order_by('-executed_at')[:10]
        
        context = {
            'title': 'JPXデータ取得実行',
            'recent_logs': recent_logs,
            'today': date.today().strftime('%Y%m%d'),
        }
        
        return render(request, 'admin/batch_import.html', context)
    
    def batch_status_view(self, request):
        """バッチ実行状況API"""
        # 管理者権限チェック
        if not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        recent_log = DataImportLog.objects.order_by('-executed_at').first()
        
        status_data = {
            'has_log': recent_log is not None,
            'last_execution': recent_log.executed_at.isoformat() if recent_log else None,
            'last_status': recent_log.status if recent_log else None,
            'last_message': recent_log.message if recent_log else None,
            'records_count': recent_log.records_count if recent_log else 0,
        }
        
        return JsonResponse(status_data)
    
    def _run_batch_command(self, date_str, force, command_type, user_id):
        """バックグラウンドでバッチコマンド実行"""
        try:
            target_date = datetime.strptime(date_str, '%Y%m%d').date() if date_str else date.today()
            
            # ログエントリを先に作成
            log_entry = DataImportLog.objects.create(
                date=target_date,
                status='PROCESSING',  # 処理中ステータスを追加する必要がある
                message=f'バッチ処理開始（実行者: User#{user_id}）',
                records_count=0
            )
            
            # コマンド構築
            cmd = [sys.executable, 'manage.py']
            
            if command_type == 'monitor':
                cmd.append('monitor_import')
                if date_str:
                    cmd.extend(['--date', date_str])
                if force:
                    cmd.append('--force')
            else:  # standard
                cmd.append('import_jpx_margin_data')
                if date_str:
                    cmd.extend(['--date', date_str])
                if force:
                    cmd.append('--force')
            
            # バッチ実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1時間タイムアウト
            )
            
            # 結果をログに記録
            if result.returncode == 0:
                # 成功時は取得件数を計算
                count = MarginTradingData.objects.filter(date=target_date).count()
                log_entry.status = 'SUCCESS'
                log_entry.message = f'正常完了\n\n--- STDOUT ---\n{result.stdout}\n\n--- STDERR ---\n{result.stderr}'
                log_entry.records_count = count
            else:
                log_entry.status = 'FAILED'
                log_entry.message = f'エラー（終了コード: {result.returncode}）\n\n--- STDOUT ---\n{result.stdout}\n\n--- STDERR ---\n{result.stderr}'
                log_entry.records_count = 0
            
            log_entry.save()
            
        except subprocess.TimeoutExpired:
            log_entry.status = 'FAILED'
            log_entry.message = 'タイムアウトエラー（1時間）'
            log_entry.save()
            
        except Exception as e:
            try:
                log_entry.status = 'FAILED'
                log_entry.message = f'システムエラー: {str(e)}'
                log_entry.save()
            except:
                # ログ保存も失敗した場合はパス
                pass

@admin.register(DataImportLog)
class DataImportLogAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'status_colored', 'records_count', 
        'message_short', 'executed_at'
    ]
    list_filter = ['status', 'date']
    ordering = ['-executed_at']
    readonly_fields = ['executed_at']
    
    # アクション追加
    actions = ['execute_new_batch']
    
    def status_colored(self, obj):
        colors = {
            'SUCCESS': 'green',
            'FAILED': 'red', 
            'SKIPPED': 'orange',
            'PROCESSING': 'blue',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_status_display()
        )
    status_colored.short_description = 'ステータス'
    
    def message_short(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_short.short_description = 'メッセージ'
    
    def execute_new_batch(self, request, queryset):
        """新しいバッチ実行"""
        return HttpResponseRedirect('/admin/margin_trading/margintradingdata/batch-import/')
    execute_new_batch.short_description = "新しいJPXデータ取得を実行"

# カスタムAdminサイト設定
admin.site.site_header = "株ログデータ管理"
admin.site.site_title = "株ログ管理画面"
admin.site.index_title = "データ管理"