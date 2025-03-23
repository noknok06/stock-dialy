from django.apps import AppConfig

class SecurityConfig(AppConfig):
    name = 'security'
    verbose_name = 'Security'
    
    def ready(self):
        # シグナルの接続や初期化作業があればここで実行
        pass

