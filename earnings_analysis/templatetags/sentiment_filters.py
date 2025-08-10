# earnings_analysis/templatetags/sentiment_filters.py（Langextract対応版）
from django import template
from django.utils.safestring import mark_safe
import json
import re
import logging

logger = logging.getLogger(__name__)
register = template.Library()

# ====================
# 感情分析関連フィルター（既存）
# ====================

@register.filter
def sentiment_color(score):
    """感情スコアに応じた色クラスを返す"""
    try:
        score = float(score)
        if score >= 0.6:
            return 'text-success'
        elif score >= 0.2:
            return 'text-info'
        elif score >= -0.2:
            return 'text-secondary'
        elif score >= -0.6:
            return 'text-warning'
        else:
            return 'text-danger'
    except (ValueError, TypeError):
        return 'text-secondary'

@register.filter
def sentiment_badge(sentiment_label):
    """感情ラベルに応じたバッジクラスを返す"""
    badge_map = {
        'very_positive': 'bg-success',
        'positive': 'bg-success',
        'neutral': 'bg-secondary',
        'negative': 'bg-danger',
        'very_negative': 'bg-danger'
    }
    return badge_map.get(sentiment_label, 'bg-secondary')

# ====================
# Langextract関連フィルター（新規追加）
# ====================

@register.filter
def analysis_method_badge(method):
    """分析手法に応じたバッジクラス"""
    badge_map = {
        'langextract': 'bg-primary',
        'traditional_gemini': 'bg-info',
        'fallback': 'bg-secondary'
    }
    return badge_map.get(method, 'bg-secondary')

@register.filter
def analysis_method_display(method):
    """分析手法の表示名"""
    display_map = {
        'langextract': 'AI高精度分析',
        'traditional_gemini': 'AI標準分析',
        'fallback': '基本分析'
    }
    return display_map.get(method, method)

@register.filter
def confidence_level_color(confidence):
    """信頼度レベルの色"""
    try:
        confidence = float(confidence)
        if confidence >= 0.8:
            return 'text-success'
        elif confidence >= 0.6:
            return 'text-info'
        elif confidence >= 0.4:
            return 'text-warning'
        else:
            return 'text-danger'
    except (ValueError, TypeError):
        return 'text-secondary'

@register.filter
def confidence_level_display(confidence):
    """信頼度レベルの表示"""
    try:
        confidence = float(confidence)
        if confidence >= 0.8:
            return '高信頼度'
        elif confidence >= 0.6:
            return '中程度'
        elif confidence >= 0.4:
            return '低信頼度'
        else:
            return '要注意'
    except (ValueError, TypeError):
        return '不明'

@register.filter
def impact_level_color(impact):
    """影響度レベルの色"""
    color_map = {
        'high': 'text-danger',
        'medium': 'text-warning',
        'low': 'text-success'
    }
    return color_map.get(impact, 'text-secondary')

@register.filter
def impact_level_display(impact):
    """影響度レベルの表示"""
    display_map = {
        'high': '高影響',
        'medium': '中影響',
        'low': '低影響'
    }
    return display_map.get(impact, impact)

@register.filter
def theme_sentiment_icon(sentiment):
    """テーマ感情のアイコン"""
    icon_map = {
        'positive': 'fas fa-thumbs-up text-success',
        'negative': 'fas fa-thumbs-down text-danger',
        'neutral': 'fas fa-equals text-secondary'
    }
    return icon_map.get(sentiment, 'fas fa-circle text-secondary')

@register.filter
def time_horizon_display(horizon):
    """時間軸の表示"""
    display_map = {
        'short_term': '短期',
        'medium_term': '中期',
        'long_term': '長期'
    }
    return display_map.get(horizon, horizon)

@register.filter
def theme_importance_badge(importance):
    """テーマ重要度のバッジ"""
    badge_map = {
        'high': 'bg-danger',
        'medium': 'bg-warning',
        'low': 'bg-info'
    }
    return badge_map.get(importance, 'bg-secondary')

@register.filter
def analysis_quality_display(quality):
    """分析品質の表示"""
    display_map = {
        'high': '高品質',
        'medium': '標準品質',
        'basic': '基本品質',
        'low': '低品質'
    }
    return display_map.get(quality, quality)

@register.filter
def analysis_quality_color(quality):
    """分析品質の色"""
    color_map = {
        'high': 'text-success',
        'medium': 'text-info',
        'basic': 'text-warning',
        'low': 'text-danger'
    }
    return color_map.get(quality, 'text-secondary')

@register.filter
def format_contextual_analysis(contextual_data):
    """文脈分析データのフォーマット"""
    if not contextual_data:
        return []
    
    formatted = []
    for context in contextual_data[:5]:  # 上位5件表示
        formatted.append({
            'text': context.get('text', ''),
            'score': context.get('score', 0),
            'context': context.get('context', ''),
            'key_phrases': context.get('key_phrases', []),
            'highlighted_text': context.get('highlighted_text', context.get('text', '')),
            'impact': context.get('business_impact', 'medium'),
            'score_color': sentiment_color(context.get('score', 0))
        })
    
    return formatted

@register.filter
def format_key_themes(themes_data):
    """主要テーマデータのフォーマット"""
    if not themes_data:
        return []
    
    formatted = []
    for theme in themes_data:
        formatted.append({
            'theme': theme.get('theme', ''),
            'sentiment': theme.get('sentiment', 'neutral'),
            'importance': theme.get('importance', 'medium'),
            'evidence': theme.get('evidence', []),
            'icon': theme.get('icon', 'fas fa-file-text'),
            'sentiment_icon': theme_sentiment_icon(theme.get('sentiment', 'neutral')),
            'importance_badge': theme_importance_badge(theme.get('importance', 'medium'))
        })
    
    return formatted

@register.simple_tag
def render_langextract_analysis_card(analysis_result):
    """Langextract分析結果カードのレンダリング"""
    if not analysis_result or analysis_result.get('analysis_method') != 'langextract':
        return ""
    
    confidence = analysis_result.get('confidence_score', 0)
    overall_score = analysis_result.get('overall_score', 0)
    
    html = f'''
    <div class="card mb-4 border-primary">
        <div class="card-header bg-primary text-white">
            <h6 class="mb-0">
                <i class="fas fa-robot me-2"></i>AI高精度分析結果
                <span class="badge bg-light text-primary ms-2">Langextract</span>
            </h6>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-6">
                    <div class="text-center">
                        <div class="display-6 {sentiment_color(overall_score)} mb-2">{overall_score:.3f}</div>
                        <div class="text-muted">総合感情スコア</div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="text-center">
                        <div class="display-6 {confidence_level_color(confidence)} mb-2">{confidence*100:.0f}%</div>
                        <div class="text-muted">信頼度</div>
                    </div>
                </div>
            </div>
            
            <div class="mt-3">
                <small class="text-muted">
                    <strong>分析理由:</strong> {analysis_result.get('reasoning', '詳細な文脈分析により算出されました。')}
                </small>
            </div>
        </div>
    </div>
    '''
    
    return mark_safe(html)

@register.inclusion_tag('earnings_analysis/tags/contextual_analysis.html')
def render_contextual_analysis(contextual_data):
    """文脈分析の表示"""
    return {
        'contextual_data': format_contextual_analysis(contextual_data)
    }

@register.inclusion_tag('earnings_analysis/tags/key_themes.html')
def render_key_themes(themes_data):
    """主要テーマの表示"""
    return {
        'themes_data': format_key_themes(themes_data)
    }

@register.filter
def get_langextract_stats(analysis_result):
    """Langextract統計情報の取得"""
    if not analysis_result or analysis_result.get('analysis_method') != 'langextract':
        return {}
    
    return {
        'segments_analyzed': analysis_result.get('segments_analyzed', 0),
        'themes_identified': analysis_result.get('themes_identified', 0),
        'processing_time': analysis_result.get('processing_time', 0),
        'analysis_quality': analysis_result.get('analysis_quality', 'medium')
    }

@register.filter
def has_langextract_analysis(analysis_result):
    """Langextract分析が実行されたかどうか"""
    return (analysis_result and 
            analysis_result.get('analysis_method') == 'langextract' and
            analysis_result.get('api_success', False))

@register.filter
def format_processing_time(seconds):
    """処理時間のフォーマット"""
    try:
        seconds = float(seconds)
        if seconds < 60:
            return f"{seconds:.1f}秒"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}分{remaining_seconds:.0f}秒"
    except (ValueError, TypeError):
        return "不明"

# ====================
# 既存のフィルター（継続）
# ====================

@register.filter
def sentiment_description(level):
    """感情レベル（数値）を説明文に変換"""
    descriptions = {
        -2: '非常にネガティブ',
        -1: 'ネガティブ',
        0: '中立',
        1: 'ポジティブ',
        2: '非常にポジティブ'
    }
    try:
        level = int(level)
        return descriptions.get(level, '不明')
    except (ValueError, TypeError):
        return '不明'

@register.simple_tag
def sentiment_meter_color(level):
    """5段階レベルに応じたメーター色を返す"""
    colors = {
        -2: '#ef4444',  # 赤
        -1: '#f59e0b',  # オレンジ
        0: '#6b7280',   # グレー
        1: '#84cc16',   # 明るい緑
        2: '#22c55e'    # 濃い緑
    }
    try:
        level = int(level)
        return colors.get(level, '#6b7280')
    except (ValueError, TypeError):
        return '#6b7280'

@register.simple_tag
def sentiment_progress_bar(positive_count, negative_count, total_count):
    """感情分析結果のプログレスバーHTML生成"""
    if total_count == 0:
        return mark_safe('<div class="progress"><div class="progress-bar bg-secondary" style="width: 100%">データなし</div></div>')
    
    positive_percent = (positive_count / total_count) * 100
    negative_percent = (negative_count / total_count) * 100
    neutral_percent = 100 - positive_percent - negative_percent
    
    html = f'''
    <div class="progress">
        <div class="progress-bar bg-success" style="width: {positive_percent:.1f}%" title="ポジティブ: {positive_count}件"></div>
        <div class="progress-bar bg-danger" style="width: {negative_percent:.1f}%" title="ネガティブ: {negative_count}件"></div>
        <div class="progress-bar bg-secondary" style="width: {neutral_percent:.1f}%" title="中立: {total_count - positive_count - negative_count}件"></div>
    </div>
    '''
    return mark_safe(html)

# ====================
# 書類種別表示名関連フィルター（既存継続）
# ====================

@register.filter
def doc_type_display_name(doc_type_code):
    """書類種別コードを表示名に変換"""
    try:
        from ..models import DocumentMetadata
        return DocumentMetadata.DOC_TYPE_DISPLAY_NAMES.get(
            str(doc_type_code), 
            f'書類種別{doc_type_code}'
        )
    except Exception:
        return f'書類種別{doc_type_code}'

# 通貨・財務データ表示フィルター、UIフィルター、テキスト処理フィルター、
# 数値・計算関連フィルター、ユーティリティフィルターは既存コードを継続使用

@register.filter
def format_japanese_currency(value, show_debug=False):
    """日本円を適切な単位で表示（異常値対策強化版）"""
    try:
        value = float(value)
        abs_value = abs(value)
        
        if abs_value == 0:
            return "0円"
        
        # 異常値の段階的自動調整
        adjustment_made = False
        adjustment_factor = 1
        
        if abs_value > 1_000_000_000_000_000:  # 1000兆円以上は明らかに異常
            test_divisors = [1_000_000_000, 1_000_000, 1_000, 100, 10]
            
            for divisor in test_divisors:
                test_value = abs_value / divisor
                # 日本企業として現実的な範囲：10億円〜100兆円
                if 1_000_000_000 <= test_value <= 100_000_000_000_000:
                    value = value / divisor
                    abs_value = abs(value)
                    adjustment_made = True
                    adjustment_factor = divisor
                    break
            
            if not adjustment_made:
                value = value / 1_000_000
                abs_value = abs(value)
                adjustment_made = True
                adjustment_factor = 1_000_000
        
        # 通常の表示処理
        formatted_result = _format_currency_base(value)
        
        # 調整が行われた場合の表示
        if adjustment_made:
            if adjustment_factor >= 1_000_000_000:
                factor_text = f"{adjustment_factor // 1_000_000_000}十億分の1"
            elif adjustment_factor >= 1_000_000:
                factor_text = f"{adjustment_factor // 1_000_000}百万分の1"
            elif adjustment_factor >= 1_000:
                factor_text = f"{adjustment_factor // 1_000}千分の1"
            else:
                factor_text = f"{adjustment_factor}分の1"
            
            return f"{formatted_result} <small class='text-warning'>({factor_text}調整)</small>"
        
        # 警告が必要な場合
        if abs_value > 50_000_000_000_000:  # 50兆円を超える場合は警告
            return f"<span class='text-warning'>⚠️</span> {formatted_result} <small class='text-muted'>(要確認)</small>"
        
        return formatted_result
            
    except (ValueError, TypeError):
        return str(value)

def _format_currency_base(value):
    """通貨フォーマットの共通処理"""
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    
    if abs_value >= 1_000_000_000_000:  # 1兆円以上
        formatted_value = abs_value / 1_000_000_000_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}兆円"
        else:
            return f"{sign}{formatted_value:.1f}兆円"
    elif abs_value >= 100_000_000:  # 1億円以上
        formatted_value = abs_value / 100_000_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}億円"
        else:
            return f"{sign}{formatted_value:.1f}億円"
    elif abs_value >= 1_000_000:  # 100万円以上
        formatted_value = abs_value / 1_000_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}百万円"
        else:
            return f"{sign}{formatted_value:.1f}百万円"
    elif abs_value >= 10_000:  # 1万円以上
        formatted_value = abs_value / 1_000
        if formatted_value >= 100:
            return f"{sign}{formatted_value:,.0f}千円"
        else:
            return f"{sign}{formatted_value:.1f}千円"
    else:  # 1万円未満
        return f"{sign}{abs_value:,.0f}円"

@register.filter
def highlight_all_keywords(text, keywords):
    """複数キーワードを一度にハイライト"""
    if not text or not keywords:
        return text
    
    highlighted_text = str(text)
    
    # キーワードをリストに変換（文字列の場合）
    if isinstance(keywords, str):
        keyword_list = [keywords]
    else:
        keyword_list = list(keywords) if keywords else []
    
    # キーワードを長い順にソートして、部分マッチによる重複を避ける
    sorted_keywords = sorted(set(keyword_list), key=len, reverse=True)
    
    for keyword in sorted_keywords:
        if keyword and keyword in highlighted_text:
            # 既にハイライトされている部分は除外
            if f'<span class="keyword-highlight">{keyword}</span>' not in highlighted_text:
                highlighted_text = highlighted_text.replace(
                    str(keyword),
                    f'<span class="keyword-highlight">{keyword}</span>'
                )
    
    return mark_safe(highlighted_text)

@register.filter
def json_safe(value):
    """Python辞書をJavaScriptで安全に使用できるJSON文字列に変換"""
    try:
        return mark_safe(json.dumps(value))
    except (ValueError, TypeError):
        return mark_safe('{}')

@register.filter
def score_percentage(value):
    """スコアをパーセンテージに変換"""
    try:
        score = float(value)
        if score <= 1:  # 0-1の範囲の場合
            return int(score * 100)
        else:  # 既にパーセンテージの場合
            return int(score)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, divisor):
    """値を除数で割る"""
    try:
        return int(float(value) / float(divisor))
    except (ValueError, TypeError, ZeroDivisionError):
        return 0