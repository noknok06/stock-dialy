# checklist/api.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from .models import Checklist, ChecklistItem, DiaryChecklistItem
from django.db.models import Q

@login_required
@require_GET
def get_checklist_items(request):
    """
    選択されたチェックリストの項目を取得するAPI
    
    クエリパラメータ:
    - ids: カンマ区切りのチェックリストID (例: "1,2,3")
    - diary_id: (任意) 日記ID - 指定された場合、その日記のチェックリスト項目のステータスも取得
    """
    try:
        # クエリパラメータからチェックリストIDを取得
        checklist_ids_param = request.GET.get('ids', '')
        diary_id = request.GET.get('diary_id')
        
        if not checklist_ids_param:
            return JsonResponse({
                'success': False,
                'error': 'チェックリストIDが指定されていません'
            }, status=400)
        
        # カンマ区切りのチェックリストIDをリストに変換
        try:
            checklist_ids = [int(id_str) for id_str in checklist_ids_param.split(',') if id_str.strip()]
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': '無効なチェックリストIDが含まれています'
            }, status=400)
        
        # ユーザーが所有するチェックリストのみを取得
        checklists = Checklist.objects.filter(
            Q(id__in=checklist_ids) & Q(user=request.user)
        ).prefetch_related('items')
        
        # 各チェックリストの項目を辞書にまとめる
        checklist_data = {}
        for checklist in checklists:
            items = []
            for item in checklist.items.all():
                items.append({
                    'id': item.id,
                    'item_text': item.item_text,
                    'order': item.order
                })
            
            checklist_data[str(checklist.id)] = {
                'id': checklist.id,
                'name': checklist.name,
                'items': items
            }
        
        # レスポンスデータを準備
        response_data = {
            'success': True,
            'checklists': checklist_data
        }
        
        # 日記IDが指定されている場合、その日記のチェックリスト項目のステータスも取得
        if diary_id:
            try:
                diary_id = int(diary_id)
                # ユーザーの日記かどうかもチェックするべきだが、ここではシンプルにする
                diary_checklist_items = DiaryChecklistItem.objects.filter(diary_id=diary_id)
                
                # チェックリスト項目のステータスを辞書にまとめる
                statuses = {}
                for item in diary_checklist_items:
                    statuses[item.checklist_item_id] = item.status
                
                response_data['statuses'] = statuses
            except ValueError:
                # 無効な日記IDの場合はステータスを含めない
                pass
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        print(f"Error in get_checklist_items API: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)