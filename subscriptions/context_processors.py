# subscriptions/context_processors.py
def subscription_status(request):
    """サブスクリプション情報をテンプレートに提供"""
    context = {
        'show_ads': True,  # デフォルトは広告表示
        'is_pro': False,
        'subscription_name': 'フリー',
        'is_premium': False,  # 広告削除プランまたはプロプラン
        'plan_limits': {
            'max_tags': 5,
            'max_templates': 3,
            'max_snapshots': 3,
            'max_records': 30,
            'export_enabled': False,
            'advanced_analytics': False
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
    
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return context
    
    try:
        subscription = request.user.subscription
        if subscription and subscription.is_valid():
            plan = subscription.plan
            
            # 基本情報を設定
            context['show_ads'] = plan.show_ads
            context['is_pro'] = plan.slug == 'pro'
            context['is_premium'] = not plan.show_ads  # 広告削除プランまたはプロプラン
            context['subscription_name'] = plan.name
            
            # プラン制限情報を設定
            context['plan_limits'] = {
                'max_tags': plan.max_tags,
                'max_templates': plan.max_templates,
                'max_snapshots': plan.max_snapshots,
                'max_records': plan.max_records,
                'export_enabled': plan.export_enabled,
                'advanced_analytics': plan.advanced_analytics
            }
            
            # 使用状況を取得（該当のリレーションが存在する場合のみ）
            try:
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
                
                # 使用率を計算（0除算を防止）
                context['usage_percent'] = {
                    'tags': int(tags_count / plan.max_tags * 100) if plan.max_tags > 0 else (0 if plan.max_tags == -1 else 100),
                    'templates': int(templates_count / plan.max_templates * 100) if plan.max_templates > 0 else (0 if plan.max_templates_tags == -1 else 100),
                    'snapshots': int(snapshots_count / plan.max_snapshots * 100) if plan.max_snapshots > 0 else (0 if plan.max_snapshots == -1 else 100),
                    'records': int(records_count / plan.max_records * 100) if plan.max_records > 0 else (0 if plan.max_records == -1 else 100),
                }
            except Exception as e:
                # 使用状況の取得に失敗した場合はデフォルト値を使用
                print(f"Error getting usage info: {str(e)}")
                
    except (AttributeError, Exception) as e:
        # エラーが発生した場合はデフォルト値を使用
        print(f"Error in subscription context processor: {str(e)}")
    
    return context