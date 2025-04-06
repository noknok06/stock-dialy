# tags/api.py - 新規ファイル

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from .models import Tag

@login_required
def list_tags(request):
    """
    ユーザーのタグ一覧をJSON形式で返すAPI
    """
    try:
        tags = Tag.objects.filter(user=request.user).order_by('name')
        
        # タグデータを整形
        tag_list = [
            {
                'id': tag.id,
                'name': tag.name,
                'color': tag.color if hasattr(tag, 'color') else None
            }
            for tag in tags
        ]
        
        return JsonResponse({
            'success': True,
            'tags': tag_list
        })
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': str(e)
        }, status=500)