# ads/context_processors.py
from .models import AdPlacement, AdUnit, UserAdPreference

def ads_processor(request):
    """広告関連のグローバル変数をテンプレートに提供"""
    context = {}
    
    # 広告表示の有無を判定
    show_ads = True
    
    # ユーザーが認証済みの場合、ユーザーの設定を取得
    if request.user.is_authenticated:
        try:
            ad_preference = UserAdPreference.objects.get(user=request.user)
            show_ads = ad_preference.should_show_ads()
        except UserAdPreference.DoesNotExist:
            # 設定がない場合は広告表示（通常はシグナルで作成されるはず）
            UserAdPreference.objects.create(user=request.user)
    
    context['show_ads'] = show_ads
    
    # 広告表示が有効な場合のみ、広告ユニットを取得
    if show_ads:
        # 利用可能な広告配置を取得
        ad_placements = {}
        active_placements = AdPlacement.objects.filter(is_active=True)
        
        for placement in active_placements:
            # 各配置の有効な広告ユニットを取得
            ad_units = AdUnit.objects.filter(
                placement=placement,
                is_active=True
            ).first()  # 各配置につき1つの広告ユニットを使用
            
            if ad_units:
                ad_placements[placement.position] = {
                    'placement': placement,
                    'ad_unit': ad_units
                }
        
        context['ad_placements'] = ad_placements
    
    return context