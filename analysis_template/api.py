# analysis_template/api.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from .models import AnalysisTemplate, AnalysisItem, DiaryAnalysisValue
from stockdiary.models import StockDiary
from django.shortcuts import get_object_or_404

@login_required
@require_GET
# analysis_template/api.py の get_template_items 関数修正版

@login_required
@require_GET
def get_template_items(request):
    """
    テンプレートの分析項目を取得するAPI
    
    クエリパラメータ:
    - template_id: 分析テンプレートID
    - diary_id: (任意) 日記ID - 指定された場合、その日記の分析値も取得
    """
    try:
        # クエリパラメータからテンプレートIDを取得
        template_id = request.GET.get('template_id')
        diary_id = request.GET.get('diary_id')
        
        if not template_id:
            return JsonResponse({
                'success': False,
                'error': 'テンプレートIDが指定されていません'
            }, status=400)
        
        # ユーザーが所有するテンプレートのみを取得
        template = get_object_or_404(
            AnalysisTemplate,
            id=template_id,
            user=request.user
        )
        
        # テンプレートの分析項目を取得
        items_data = []
        for item in template.items.all().order_by('order'):
            item_data = {
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'item_type': item.item_type,
                'order': item.order,
                'choices': item.choices,
                'value_label': item.value_label
            }
            items_data.append(item_data)
        
        # レスポンスデータを準備
        response_data = {
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name
            },
            'items': items_data
        }
        
        # 日記IDが指定されている場合、その日記の分析値も取得
        if diary_id:
            try:
                diary = StockDiary.objects.get(id=diary_id, user=request.user)
                
                # 日記の分析値を取得
                values = {}
                analysis_values = DiaryAnalysisValue.objects.filter(
                    diary=diary,
                    analysis_item__template=template
                )
                
                for value in analysis_values:
                    if value.analysis_item.item_type == 'boolean_with_value':
                        # 複合型の場合はオブジェクトで返す
                        values[value.analysis_item_id] = {
                            'boolean_value': value.boolean_value,
                            'number_value': value.number_value,
                            'text_value': value.text_value
                        }
                    elif value.analysis_item.item_type == 'boolean':
                        # ブール型の場合は単純なbool値で返す
                        values[value.analysis_item_id] = value.boolean_value
                    elif value.analysis_item.item_type == 'number':
                        # 数値型の場合は数値で返す
                        values[value.analysis_item_id] = float(value.number_value) if value.number_value is not None else None
                    else:
                        # テキスト型または選択型の場合は文字列で返す
                        values[value.analysis_item_id] = value.text_value
                
                response_data['values'] = values
                
            except StockDiary.DoesNotExist:
                # 無効な日記IDの場合は値を含めない
                pass
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        print(f"Error in get_template_items API: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)