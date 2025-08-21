# admin.py
from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
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
        return format_html(
            '<span style="color: {};">{:.2f}</span>',
            color, ratio
        )
    margin_ratio.short_description = '信用倍率'

@admin.register(DataImportLog)
class DataImportLogAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'status_colored', 'records_count', 
        'message_short', 'executed_at'
    ]
    list_filter = ['status', 'date']
    ordering = ['-executed_at']
    readonly_fields = ['executed_at']
    
    def status_colored(self, obj):
        colors = {
            'SUCCESS': 'green',
            'FAILED': 'red', 
            'SKIPPED': 'orange'
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

# ===== settings.py に追加する設定 =====

# INSTALLED_APPS に追加
INSTALLED_APPS = [
    # ... existing apps ...
    'myapp',  # アプリ名を適切に設定
]

# データベース設定例（PostgreSQL推奨）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'jpx_margin_db',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/jpx_import.log',
        },
    },
    'loggers': {
        'myapp.management.commands.import_jpx_margin_data': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ===== requirements.txt =====
"""
Django>=4.2.0
psycopg2-binary>=2.9.0
requests>=2.31.0
pdfplumber>=0.9.0
python-crontab>=2.7.0
"""

# ===== cronジョブ設定例 =====
"""
# /etc/cron.d/jpx-margin-import
# 毎日午後6時に実行（JPXのデータ公開時間を考慮）
0 18 * * * www-data cd /path/to/your/project && /path/to/venv/bin/python manage.py import_jpx_margin_data >> /var/log/django/cron.log 2>&1

# 毎週土曜日午前9時に先週分の再取得（データ修正対応）
0 9 * * 6 www-data cd /path/to/your/project && /path/to/venv/bin/python manage.py import_jpx_margin_data --force >> /var/log/django/cron.log 2>&1
"""

# ===== Djangoプロジェクト初期化コマンド =====
"""
# プロジェクト作成
django-admin startproject jpx_margin_system
cd jpx_margin_system
python manage.py startapp margin_data

# マイグレーション実行
python manage.py makemigrations
python manage.py migrate

# スーパーユーザー作成
python manage.py createsuperuser

# 手動でのデータ取得テスト
python manage.py import_jpx_margin_data --date 20250718

# 強制再取得
python manage.py import_jpx_margin_data --date 20250718 --force
"""