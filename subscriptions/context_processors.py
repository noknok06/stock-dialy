# subscriptions/context_processors.py - 修正版
def subscription_status(request):
    """サブスクリプション情報をテンプレートに提供（機能制限なし、広告表示あり）"""
    context = {
        'show_ads': True,  # 広告表示あり
        'is_pro': False,   # プロステータスなし（広告表示のため）
        'subscription_name': 'フリー',
        'is_premium': False,  # 広告表示あり
        'plan_limits': {
            'max_tags': -1,           # 無制限
            'max_templates': -1,      # 無制限
            'max_snapshots': -1,      # 無制限
            'max_records': -1,        # 無制限
            'export_enabled': True,   # エクスポート機能有効
            'advanced_analytics': True # 高度な分析機能有効
        },
        'usage': {
            'tags': 0,
            'templates': 0,
            'snapshots': 0,
            'records': 0
        },
        'usage_percent': {
            'tags': 0,
            'templates': 0,
            'snapshots': 0,
            'records': 0
        }
    }
    
    # ユーザーが認証済みかつユーザー属性にアクセス可能な場合、ユーザーの設定を取得
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            # ユーザーの広告設定を反映
            from ads.models import UserAdPreference
            try:
                ad_preference = UserAdPreference.objects.get(user=request.user)
                context['show_ads'] = ad_preference.should_show_ads()
                context['personalized_ads'] = ad_preference.allow_personalized_ads
            except UserAdPreference.DoesNotExist:
                # デフォルトの設定を使用
                pass
                
            # 使用状況を取得（該当のリレーションが存在する場合のみ）
            user = request.user
            tags_count = user.tag_set.count() if hasattr(user, 'tag_set') else 0
            templates_count = user.analysistemplate_set.count() if hasattr(user, 'analysistemplate_set') else 0
            snapshots_count = user.portfoliosnapshot_set.count() if hasattr(user, 'portfoliosnapshot_set') else 0
            records_count = user.stockdiary_set.count() if hasattr(user, 'stockdiary_set') else 0
            
            context['usage'] = {
                'tags': tags_count,
                'templates': templates_count,
                'snapshots': snapshots_count,
                'records': records_count
            }
            
            # 使用率は常に0（無制限のため）
            context['usage_percent'] = {
                'tags': 0,
                'templates': 0,
                'snapshots': 0,
                'records': 0
            }
                
        except Exception as e:
            # エラーが発生した場合はデフォルト値を使用
            print(f"Error getting usage info: {str(e)}")
    
    return context