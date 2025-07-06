import os
from celery import Celery
from django.conf import settings

# Django設定モジュールを指定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('earnings_analysis')

# Django設定からCelery設定を読み込み
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django アプリからタスクを自動検出
app.autodiscover_tasks()

# Celery設定
app.conf.update(
    # タスクの設定
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tokyo',
    enable_utc=True,
    
    # タスクのタイムアウト設定
    task_soft_time_limit=3600,  # 1時間
    task_time_limit=4200,       # 70分
    
    # ワーカー設定
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # 結果の保存期間
    result_expires=3600,  # 1時間
    
    # タスクルーティング
    task_routes={
        'earnings_analysis.tasks.analyze_sentiment': {'queue': 'sentiment'},
        'earnings_analysis.tasks.analyze_financial': {'queue': 'financial'},
        'earnings_analysis.tasks.cleanup_expired_sessions': {'queue': 'cleanup'},
    },
    
    # 定期タスク設定（オプション）
    beat_schedule={
        'cleanup-expired-sessions': {
            'task': 'earnings_analysis.tasks.cleanup_expired_sessions',
            'schedule': 3600.0,  # 1時間ごと
        },
    },
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')