# earnings_analysis/views/sentiment_ui.py（リダイレクト問題修正版）
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import DocumentMetadata, SentimentAnalysisSession, SentimentAnalysisHistory

logger = logging.getLogger(__name__)

class SentimentAnalysisView(TemplateView):
    """感情分析専用ページ"""
    template_name = 'earnings_analysis/sentiment/analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_id = kwargs.get('doc_id')
        
        # 書類情報取得
        document = get_object_or_404(
            DocumentMetadata,
            doc_id=doc_id,
            legal_status='1'
        )
        
        # 最新の分析結果確認
        latest_session = SentimentAnalysisSession.objects.filter(
            document=document,
            processing_status='COMPLETED'
        ).order_by('-created_at').first()
        
        # 過去の分析履歴
        analysis_history = SentimentAnalysisHistory.objects.filter(
            document=document
        ).order_by('-analysis_date')[:5]
        
        context.update({
            'document': document,
            'latest_session': latest_session,
            'analysis_history': analysis_history,
            'has_recent_analysis': latest_session and latest_session.created_at >= timezone.now() - timedelta(hours=1),
        })
        
        return context


class SentimentResultView(TemplateView):
    """感情分析結果表示ページ（修正版）"""
    template_name = 'earnings_analysis/sentiment/result.html'
    
    def get(self, request, *args, **kwargs):
        """GETリクエスト処理（期限切れチェック）"""
        session_id = kwargs.get('session_id')
        
        # セッション情報取得
        try:
            session = get_object_or_404(
                SentimentAnalysisSession,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"セッション取得エラー: {e}")
            messages.error(request, 'セッションが見つかりません。')
            return redirect('earnings_analysis:index')
        
        # 期限切れチェック
        if session.is_expired:
            messages.error(request, 'セッションが期限切れです。')
            return redirect('earnings_analysis:document-detail-ui', doc_id=session.document.doc_id)
        
        # 分析完了チェック
        if session.processing_status != 'COMPLETED':
            if session.processing_status == 'FAILED':
                messages.error(request, '分析処理中にエラーが発生しました。')
                return redirect('earnings_analysis:sentiment-analysis', doc_id=session.document.doc_id)
            else:
                messages.info(request, '分析がまだ完了していません。')
                return redirect('earnings_analysis:sentiment-analysis', doc_id=session.document.doc_id)
        
        # 通常のテンプレート表示
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """コンテキストデータ取得"""
        context = super().get_context_data(**kwargs)
        session_id = kwargs.get('session_id')
        
        # セッション情報取得（ここでは既にgetメソッドでチェック済み）
        session = get_object_or_404(
            SentimentAnalysisSession,
            session_id=session_id
        )
        
        # 関連書類の感情分析履歴
        related_analyses = SentimentAnalysisHistory.objects.filter(
            document__edinet_code=session.document.edinet_code
        ).exclude(
            document=session.document
        ).order_by('-analysis_date')[:5]
        
        # 見解データの処理
        formatted_insights = None
        reliability_score = None
        
        if session.analysis_result and 'user_insights' in session.analysis_result:
            formatted_insights = self._format_user_insights(session.analysis_result['user_insights'])
            reliability_score = self._calculate_reliability_score(session.analysis_result)
        
        context.update({
            'session': session,
            'document': session.document,
            'related_analyses': related_analyses,
            'formatted_insights': formatted_insights,
            'reliability_score': reliability_score,
        })
        
        return context
    
    def _format_user_insights(self, insights):
        """ユーザー向け見解のフォーマット"""
        try:
            formatted = {}
            
            # 市場への影響分析
            if 'market_implications' in insights:
                market_data = insights['market_implications']
                formatted['market_implications'] = {
                    'sentiment': market_data.get('market_sentiment', ''),
                    'stock_impact': market_data.get('stock_impact_likelihood', ''),
                    'sector_comparison': market_data.get('sector_comparison', ''),
                }
            
            # 経営戦略の読み取り
            if 'business_strategy_reading' in insights:
                strategy_data = insights['business_strategy_reading']
                formatted['strategy_reading'] = {
                    'management_stance': strategy_data.get('management_stance', ''),
                    'strategic_direction': strategy_data.get('strategic_direction', ''),
                    'operational_focus': strategy_data.get('operational_focus', ''),
                }
            
            # リスク評価
            if 'risk_assessment' in insights:
                risk_data = insights['risk_assessment']
                formatted['risk_assessment'] = {
                    'risk_level': risk_data.get('risk_level', 'medium'),
                    'identified_risks': risk_data.get('identified_risks', []),
                    'mitigation_evidence': risk_data.get('mitigation_evidence', []),
                }
                
            # Gemini生成ポイントの処理を追加
            if 'gemini_investment_points' in insights:
                formatted['gemini_investment_points'] = insights['gemini_investment_points']
            
            if 'gemini_metadata' in insights:
                formatted['gemini_metadata'] = insights['gemini_metadata']
            
            return formatted
            
        except Exception as e:
            logger.error(f"見解フォーマットエラー: {e}")
            return None
    
    def _calculate_reliability_score(self, analysis_result):
        """分析の信頼性スコア計算"""
        try:
            statistics = analysis_result.get('statistics', {})
            
            score = 0
            factors = []
            
            # 分析語数による評価
            total_words = statistics.get('total_words_analyzed', 0)
            if total_words >= 100:
                score += 30
                factors.append('十分な語彙数')
            elif total_words >= 50:
                score += 20
                factors.append('適度な語彙数')
            elif total_words >= 20:
                score += 10
                factors.append('限定的な語彙数')
            
            # 文脈パターンの検出
            context_patterns = statistics.get('context_patterns_found', 0)
            if context_patterns >= 5:
                score += 25
                factors.append('多数の文脈パターン')
            elif context_patterns >= 2:
                score += 15
                factors.append('文脈パターンあり')
            
            # 文章レベルの分析
            sentences_analyzed = statistics.get('sentences_analyzed', 0)
            if sentences_analyzed >= 20:
                score += 20
                factors.append('豊富な文章分析')
            elif sentences_analyzed >= 10:
                score += 15
                factors.append('適度な文章分析')
            
            # ポジティブ・ネガティブのバランス
            pos_count = statistics.get('positive_words_count', 0)
            neg_count = statistics.get('negative_words_count', 0)
            total_sentiment_words = pos_count + neg_count
            
            if total_sentiment_words >= 10:
                score += 15
                factors.append('バランスの取れた感情語')
            elif total_sentiment_words >= 5:
                score += 10
                factors.append('感情語の存在')
            
            # セクション分析の有無
            if 'section_analysis' in analysis_result:
                score += 10
                factors.append('セクション別分析')
            
            # 信頼性レベルの判定
            if score >= 80:
                level = 'very_high'
                description = '非常に高い信頼性があります。多角的な分析により確度の高い結果が得られています。'
            elif score >= 60:
                level = 'high'
                description = '高い信頼性があります。十分なデータに基づいた信頼できる分析結果です。'
            elif score >= 40:
                level = 'medium'
                description = '中程度の信頼性があります。参考情報として活用してください。'
            else:
                level = 'low'
                description = '限定的な信頼性です。追加の情報と合わせて慎重に評価してください。'
            
            return {
                'score': score,
                'level': level,
                'description': description,
                'factors': factors
            }
            
        except Exception as e:
            logger.error(f"信頼性スコア計算エラー: {e}")
            return {
                'score': 50,
                'level': 'medium',
                'description': '信頼性の計算ができませんでした。',
                'factors': []
            }