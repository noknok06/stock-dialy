import re
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # メンテナンスモードの設定（デフォルトはFalse）
        self.maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
        
        # メンテナンス終了予定時刻
        self.maintenance_end_time = getattr(settings, 'MAINTENANCE_END_TIME', None)
        
        # サポート用メールアドレス
        self.contact_email = getattr(settings, 'MAINTENANCE_CONTACT_EMAIL', 'support@kablog.example.com')
        
        # アクセスを許可するIPアドレスのリスト
        self.allowed_ips = getattr(settings, 'MAINTENANCE_ALLOWED_IPS', [
            '127.0.0.1',          # ローカル開発用
            # 'xxx.xxx.xxx.xxx',  # 管理者のIPアドレス
        ])
        
        # メンテナンスモードでもアクセス可能なURLパターン
        self.exempt_urls = getattr(settings, 'MAINTENANCE_EXEMPT_URLS', [
            r'^/static/.*',  # 静的ファイル
            r'^/media/.*',   # メディアファイル
            r'^/admin/.*',   # 管理サイト（オプション）
        ])
        
        # コンパイル済みの免除URLパターン
        self.compiled_exempt_urls = [re.compile(url) for url in self.exempt_urls]

    def __call__(self, request):
        # 先に通常のレスポンス処理を行う（認証ミドルウェアなどが先に実行されるようにする）
        response = self.get_response(request)
        
        # メンテナンスモードがオフの場合は通常の処理を続行
        if not self.maintenance_mode:
            return response
            
        # クライアントのIPアドレスを取得
        # X-Forwarded-Forヘッダーがある場合（プロキシ背後の場合）はそれを使用
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if client_ip:
            # カンマで区切られた場合は最初のIPを使用
            client_ip = client_ip.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR', '')
            
        # 許可されたIPアドレスからのアクセスの場合は通常の処理を続行
        if client_ip in self.allowed_ips:
            return response
            
        # 除外URLパターンのいずれかに一致する場合は通常の処理を続行
        for exempt_url in self.compiled_exempt_urls:
            if exempt_url.match(request.path_info):
                return response
            
        # コンテキストデータ作成
        context = {
            'end_time': self.maintenance_end_time,
            'contact_email': self.contact_email,
            'current_time': timezone.now(),
        }
        
        # メンテナンスページを表示
        maintenance_response = render(request, 'maintenance.html', context=context, status=503)
        
        # キャッシュ制御ヘッダーを追加（キャッシュさせない）
        maintenance_response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        maintenance_response['Pragma'] = 'no-cache'
        maintenance_response['Expires'] = '0'
        
        # 再試行推奨ヘッダーを追加
        maintenance_response['Retry-After'] = '3600'  # 1時間後に再試行を推奨
        
        return maintenance_response