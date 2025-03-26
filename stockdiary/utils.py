# stockdiary/utils.py
"""共通ユーティリティ関数"""
from analysis_template.models import AnalysisTemplate, DiaryAnalysisValue


def process_analysis_values(request, diary, template_id):
    """分析テンプレート値を処理する共通関数
    
    Args:
        request: HttpRequest オブジェクト
        diary: StockDiary オブジェクト
        template_id: 分析テンプレートのID
    """
    try:
        template = AnalysisTemplate.objects.get(id=template_id, user=request.user)
        
        # テンプレートの各項目を取得
        items = template.items.all()
        
        # 各項目の値を保存
        for item in items:
            item_id = item.id
            
            # 複合型の場合、boolean値と実際の値（数値またはテキスト）を両方処理
            if item.item_type == 'boolean_with_value':
                boolean_field_name = f'analysis_item_{item_id}_boolean'
                value_field_name = f'analysis_item_{item_id}_value'
                
                boolean_value = boolean_field_name in request.POST
                actual_value = request.POST.get(value_field_name, '')
                
                # 少なくとも1つの値がある場合のみレコードを作成
                if boolean_value or actual_value:
                    analysis_value = DiaryAnalysisValue(
                        diary=diary,
                        analysis_item=item,
                        boolean_value=boolean_value
                    )
                    
                    # 実際の値が数値かテキストか判断して適切なフィールドに設定
                    try:
                        float_value = float(actual_value)
                        analysis_value.number_value = float_value
                    except (ValueError, TypeError):
                        if actual_value:
                            analysis_value.text_value = actual_value
                    
                    analysis_value.save()
                
            elif item.item_type == 'boolean':
                # 通常のチェックボックス
                field_name = f'analysis_item_{item_id}'
                boolean_value = field_name in request.POST
                
                analysis_value = DiaryAnalysisValue(
                    diary=diary,
                    analysis_item=item,
                    boolean_value=boolean_value
                )
                
                analysis_value.save()
                
            elif item.item_type == 'number':
                # 数値型
                field_name = f'analysis_item_{item_id}'
                value = request.POST.get(field_name, '')
                
                if value:
                    try:
                        number_value = float(value)
                        analysis_value = DiaryAnalysisValue(
                            diary=diary,
                            analysis_item=item,
                            number_value=number_value
                        )
                        analysis_value.save()
                    except ValueError:
                        # 数値変換エラーの場合はスキップ
                        pass
                        
            else:  # text または select
                # テキスト型または選択肢型
                field_name = f'analysis_item_{item_id}'
                value = request.POST.get(field_name, '')
                
                if value:
                    analysis_value = DiaryAnalysisValue(
                        diary=diary,
                        analysis_item=item,
                        text_value=value
                    )
                    analysis_value.save()
                
    except AnalysisTemplate.DoesNotExist:
        pass  # テンプレートが存在しない場合は何もしない


# 分析データ関連の追加ユーティリティ関数

def calculate_analysis_completion_rate(user, diaries):
    """分析項目の平均完了率を計算する
    
    Args:
        user: ユーザーオブジェクト
        diaries: 日記のクエリセットまたはリスト
    
    Returns:
        float: 平均完了率（パーセント）
    """
    if not diaries:
        return 0
    
    # 日記IDのリスト
    diary_ids = [d.id for d in diaries] if not hasattr(diaries, 'values_list') else diaries.values_list('id', flat=True)
    
    if not diary_ids:
        return 0
        
    # 日記に対する分析値を取得
    analysis_values = DiaryAnalysisValue.objects.filter(
        diary_id__in=diary_ids
    ).select_related('analysis_item')
    
    # 日記IDごとに分析値をグループ化
    diary_values = {}
    for value in analysis_values:
        diary_id = value.diary_id
        if diary_id not in diary_values:
            diary_values[diary_id] = {
                'template_items': {},
                'completed_items': 0,
                'total_items': 0
            }
        
        template_id = value.analysis_item.template_id
        if template_id not in diary_values[diary_id]['template_items']:
            diary_values[diary_id]['template_items'][template_id] = {
                'items': [],
                'completed': 0,
                'total': 0
            }
        
        diary_values[diary_id]['template_items'][template_id]['items'].append(value)
    
    # 各日記の各テンプレートの項目数を取得
    for diary_id, data in diary_values.items():
        for template_id, template_data in data['template_items'].items():
            template = AnalysisTemplate.objects.get(id=template_id)
            total_items = template.items.count()
            template_data['total'] = total_items
            
            # 完了項目数を計算
            for value in template_data['items']:
                if value.analysis_item.item_type == 'boolean' or value.analysis_item.item_type == 'boolean_with_value':
                    if value.boolean_value:
                        template_data['completed'] += 1
                elif value.analysis_item.item_type == 'number':
                    if value.number_value is not None:
                        template_data['completed'] += 1
                elif value.analysis_item.item_type == 'select' or value.analysis_item.item_type == 'text':
                    if value.text_value:
                        template_data['completed'] += 1
            
            data['completed_items'] += template_data['completed']
            data['total_items'] += template_data['total']
    
    # 全体の完了率を計算
    total_completed = 0
    total_items = 0
    for data in diary_values.values():
        total_completed += data['completed_items']
        total_items += data['total_items']
    
    completion_rate = (total_completed / total_items * 100) if total_items > 0 else 0
    return completion_rate