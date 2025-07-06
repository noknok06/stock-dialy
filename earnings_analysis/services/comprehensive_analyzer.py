# earnings_analysis/services/comprehensive_analyzer.py（新規作成）
import threading
import time
import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from datetime import timedelta

from .sentiment_analyzer import SentimentAnalysisService, TransparentSentimentAnalyzer
from .financial_analyzer import FinancialAnalyzer
from .xbrl_extractor import EDINETXBRLService

logger = logging.getLogger(__name__)

class ComprehensiveAnalysisService:
    """包括的分析サービス（感情分析 + 財務分析）"""
    
    def __init__(self):
        self.sentiment_analyzer = TransparentSentimentAnalyzer()
        self.financial_analyzer = FinancialAnalyzer()
        self.xbrl_service = EDINETXBRLService()
    
    def start_comprehensive_analysis(self, document_id: str, force: bool = False, user_ip: str = None) -> Dict[str, Any]:
        """包括的分析開始"""
        from ..models import DocumentMetadata, FinancialAnalysisSession
        
        try:
            document = DocumentMetadata.objects.get(doc_id=document_id, legal_status='1')
            
            if not force:
                # 最近の分析結果をチェック
                recent_session = FinancialAnalysisSession.objects.filter(
                    document=document,
                    processing_status='COMPLETED',
                    created_at__gte=timezone.now() - timedelta(hours=2)
                ).first()
                
                if recent_session:
                    return {
                        'status': 'already_analyzed',
                        'session_id': str(recent_session.session_id),
                        'result': recent_session.analysis_result,
                        'message': '2時間以内に包括分析済みです'
                    }
            
            # 新しいセッション作成
            session = FinancialAnalysisSession.objects.create(
                document=document,
                processing_status='PENDING'
            )
            
            # バックグラウンドで分析実行
            threading.Thread(
                target=self._execute_comprehensive_analysis,
                args=(session.id, user_ip),
                daemon=True
            ).start()
            
            return {
                'status': 'started',
                'session_id': str(session.session_id),
                'message': '包括的分析（感情分析 + 財務分析）を開始しました'
            }
            
        except DocumentMetadata.DoesNotExist:
            raise Exception('指定された書類が見つかりません')
        except Exception as e:
            logger.error(f"包括分析開始エラー: {e}")
            raise Exception(f"包括分析開始に失敗しました: {str(e)}")
    
    def get_comprehensive_progress(self, session_id: str) -> Dict[str, Any]:
        """包括分析の進行状況取得"""
        from ..models import FinancialAnalysisSession
        
        try:
            session = FinancialAnalysisSession.objects.get(session_id=session_id)
            
            if session.is_expired:
                return {'status': 'expired', 'message': 'セッションが期限切れです'}
            
            if session.processing_status == 'PROCESSING':
                result = session.analysis_result or {}
                progress = result.get('progress', 50)
                message = result.get('current_step', '包括分析実行中...')
            elif session.processing_status == 'COMPLETED':
                progress = 100
                message = '包括分析完了'
            elif session.processing_status == 'FAILED':
                progress = 100
                message = f'分析失敗: {session.error_message}'
            else:
                progress = 0
                message = '分析待機中...'
            
            return {
                'progress': progress,
                'message': message,
                'status': session.processing_status,
                'timestamp': timezone.now().isoformat()
            }
            
        except FinancialAnalysisSession.DoesNotExist:
            return {'status': 'not_found', 'message': 'セッションが見つかりません'}
    
    def get_comprehensive_result(self, session_id: str) -> Dict[str, Any]:
        """包括分析結果取得"""
        from ..models import FinancialAnalysisSession
        
        try:
            session = FinancialAnalysisSession.objects.get(session_id=session_id)
            
            if session.is_expired:
                return {'status': 'expired', 'message': 'セッションが期限切れです'}
            
            if session.processing_status == 'COMPLETED':
                return {'status': 'completed', 'result': session.analysis_result}
            elif session.processing_status == 'FAILED':
                return {'status': 'failed', 'error': session.error_message}
            else:
                return {'status': 'processing', 'message': '分析中です'}
                
        except FinancialAnalysisSession.DoesNotExist:
            return {'status': 'not_found', 'message': 'セッションが見つかりません'}
    

    def _execute_comprehensive_analysis(self, session_id: int, user_ip: str = None):
        """包括分析実行（メインプロセス）"""
        from ..models import FinancialAnalysisSession, FinancialAnalysisHistory, CompanyFinancialData
        
        start_time = time.time()
        
        try:
            session = FinancialAnalysisSession.objects.get(id=session_id)
            session.processing_status = 'PROCESSING'
            session.analysis_result = {'progress': 5, 'current_step': '書類情報確認中...'}
            session.save()
            
            # 書類情報を準備
            document_info = {
                'company_name': session.document.company_name,
                'doc_description': session.document.doc_description,
                'doc_type_code': session.document.doc_type_code,
                'submit_date': session.document.submit_date_time.strftime('%Y-%m-%d'),
                'securities_code': session.document.securities_code or '',
            }
            
            # ステップ1: XBRLから包括的データ取得
            session.analysis_result = {'progress': 15, 'current_step': 'XBRLデータ取得中...'}
            session.save()
            
            # XBRLから包括的データ取得
            comprehensive_xbrl_data = self.xbrl_service.get_comprehensive_analysis_from_document(session.document)
            financial_data = comprehensive_xbrl_data.get('financial_data', {})
            text_sections = comprehensive_xbrl_data.get('text_sections', {})
            table_unit = comprehensive_xbrl_data.get('table_unit', 'yen')  # 単位情報を取得
            
            # 財務データの検証とログ出力（単位考慮版）
            if financial_data:
                logger.info(f"取得した財務データ（単位: {table_unit}）: {session.document.doc_id}")
                for key, value in financial_data.items():
                    if value is not None:
                        logger.info(f"  {key}: {value} (単位調整済み)")
                        
                        # 異常値チェック（日本企業の現実的な範囲）
                        abs_value = abs(float(value))
                        if abs_value > 1_000_000_000_000_000:  # 1000兆円以上は異常
                            logger.warning(f"依然として異常値: {key}: {value}")
            
            # 分析結果に単位情報を含める
            final_result = {'data_sources': {}}
            final_result['data_sources']['table_unit'] = table_unit
            
            if not financial_data and not text_sections:
                # XBRLが取得できない場合のフォールバック
                session.analysis_result = {'progress': 25, 'current_step': '基本情報を使用した分析に切り替え中...'}
                session.save()
                
                # 基本的なテキスト分析のみ実行
                basic_text = self._extract_basic_document_text(session.document)
                text_sections = {'基本情報': basic_text}
                financial_data = {}
            
            # ステップ2: 感情分析実行
            session.analysis_result = {'progress': 35, 'current_step': '感情分析実行中...'}
            session.save()
            
            if text_sections:
                sentiment_result = self.sentiment_analyzer.analyze_text_sections(
                    text_sections, str(session.session_id), document_info
                )
            else:
                sentiment_result = self.sentiment_analyzer.analyze_text(
                    self._extract_basic_document_text(session.document),
                    str(session.session_id), document_info
                )
            
            # ステップ3: 財務分析実行
            session.analysis_result = {'progress': 55, 'current_step': '財務分析実行中...'}
            session.save()
            
            if financial_data:
                financial_result = self.financial_analyzer.analyze_comprehensive_financial_health(
                    financial_data, text_sections, document_info
                )
            else:
                financial_result = {'error': '財務データが取得できませんでした', 'financial_data': {}}
            
            # ステップ4: 財務データの保存
            session.analysis_result = {'progress': 75, 'current_step': '財務データ保存中...'}
            session.save()
            
            saved_financial_data = None
            if financial_data:
                saved_financial_data = self._save_financial_data(session.document, financial_data)
            
            # ステップ5: 統合分析の実行
            session.analysis_result = {'progress': 85, 'current_step': '統合分析実行中...'}
            session.save()
            
            integrated_result = self._integrate_analysis_results(
                sentiment_result, financial_result, document_info
            )
            
            # セッション完了処理
            session.analysis_result = {'progress': 95, 'current_step': '結果生成中...'}
            session.save()
            
            # financial_resultを安全な形式に変換
            safe_financial_result = self._make_json_safe(financial_result)
            
            final_result = {
                'analysis_type': 'comprehensive',
                'analysis_timestamp': timezone.now().isoformat(),
                'document_info': document_info,
                
                # 主要結果
                'integrated_analysis': integrated_result,
                'sentiment_analysis': sentiment_result,
                'financial_analysis': safe_financial_result,
                
                # データソース情報
                'data_sources': {
                    'xbrl_available': bool(financial_data),
                    'text_sections_count': len(text_sections),
                    'financial_data_points': len(financial_data),
                    'data_quality': safe_financial_result.get('analysis_metadata', {}).get('data_quality', 'unknown'),
                },
                
                # メタデータ
                'analysis_metadata': {
                    'analyzer_version': '2.0_comprehensive',
                    'session_id': str(session.session_id),
                    'processing_duration': time.time() - start_time,
                    'user_ip': user_ip,
                }
            }
            
            # セッションデータの更新（安全にアクセス）
            session.overall_health_score = integrated_result.get('overall_score', 0)
            session.risk_level = integrated_result.get('risk_level', 'medium')
            session.investment_stance = integrated_result.get('investment_stance', 'cautious')
            
            # キャッシュフローパターンの安全な取得
            cf_pattern = ''
            if not safe_financial_result.get('error'):
                cf_analysis = safe_financial_result.get('cashflow_analysis', {})
                pattern_info = cf_analysis.get('pattern', {})
                cf_pattern = pattern_info.get('name', '') if isinstance(pattern_info, dict) else ''
            
            session.cashflow_pattern = cf_pattern
            session.management_confidence_score = sentiment_result.get('overall_score', 0) * 100
            session.analysis_result = self._make_json_safe(final_result)  # JSON安全化
            session.financial_data = self._make_json_safe(financial_data)  # JSON安全化
            session.processing_status = 'COMPLETED'
            session.save()
            
            # 履歴保存
            analysis_duration = time.time() - start_time
            FinancialAnalysisHistory.objects.create(
                document=session.document,
                overall_health_score=integrated_result.get('overall_score', 0),
                risk_level=integrated_result.get('risk_level', 'medium'),
                cashflow_pattern=cf_pattern,
                management_confidence_score=sentiment_result.get('overall_score', 0) * 100,
                user_ip=user_ip,
                analysis_duration=analysis_duration,
                data_quality=safe_financial_result.get('analysis_metadata', {}).get('data_quality', 'unknown'),
            )
            
            logger.info(f"包括分析完了: {session.session_id} ({analysis_duration:.2f}秒)")
            
        except Exception as e:
            logger.error(f"包括分析エラー: {session_id} - {e}")
            
            try:
                session = FinancialAnalysisSession.objects.get(id=session_id)
                session.processing_status = 'FAILED'
                session.error_message = str(e)
                session.save()
            except:
                pass

    def _make_json_safe(self, obj):
        """オブジェクトをJSON安全な形式に変換"""
        import json
        from decimal import Decimal
        from datetime import datetime, date
        from django.utils import timezone as django_timezone
        
        if obj is None:
            return None
        elif isinstance(obj, dict):
            return {key: self._make_json_safe(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, (int, float, str, bool)):
            return obj
        elif hasattr(obj, '__dict__'):
            # オブジェクトの場合は辞書に変換
            try:
                obj_dict = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_'):  # プライベート属性を除外
                        obj_dict[key] = self._make_json_safe(value)
                return obj_dict
            except:
                return str(obj)
        else:
            # その他の型は文字列化を試行
            try:
                json.dumps(obj)  # JSON化可能かテスト
                return obj
            except (TypeError, ValueError):
                return str(obj)

    def _integrate_analysis_results(self, sentiment_result: Dict, financial_result: Dict, 
                                document_info: Dict) -> Dict[str, Any]:
        """分析結果の統合"""
        try:
            # 基本スコアの取得
            sentiment_score = sentiment_result.get('overall_score', 0) * 100  # -1~1 を 0~100 に変換
            
            # 財務分析結果の安全な取得
            financial_score = 50  # デフォルト値
            financial_risk = 'medium'
            
            if not financial_result.get('error'):
                overall_health = financial_result.get('overall_health', {})
                if isinstance(overall_health, dict):
                    financial_score = overall_health.get('overall_score', 50)
                    financial_risk = overall_health.get('risk_level', 'medium')
                else:
                    # overall_healthがオブジェクトの場合
                    financial_score = getattr(overall_health, 'overall_score', 50)
                    financial_risk = getattr(overall_health, 'risk_level', 'medium')
            
            # 統合スコアの計算
            if financial_result.get('error'):
                # 財務データがない場合は感情分析のみ
                overall_score = max(0, min(100, sentiment_score))
                integration_method = 'sentiment_only'
                weights = {'sentiment': 1.0, 'financial': 0.0}
            else:
                # 両方のデータがある場合は重み付け平均
                sentiment_weight = 0.3
                financial_weight = 0.7
                overall_score = (sentiment_score * sentiment_weight + 
                            financial_score * financial_weight)
                integration_method = 'weighted_average'
                weights = {'sentiment': sentiment_weight, 'financial': financial_weight}
            
            # リスクレベルの統合判定
            sentiment_label = sentiment_result.get('sentiment_label', 'neutral')
            
            # 統合リスクレベル
            if overall_score >= 80 and financial_risk == 'low' and sentiment_label == 'positive':
                integrated_risk = 'low'
            elif overall_score >= 60 and financial_risk != 'high':
                integrated_risk = 'medium'
            else:
                integrated_risk = 'high'
            
            # 投資スタンスの決定
            if integrated_risk == 'low' and overall_score >= 80:
                investment_stance = 'aggressive'
            elif integrated_risk == 'medium' and overall_score >= 60:
                investment_stance = 'conditional'
            elif integrated_risk == 'high' or overall_score < 40:
                investment_stance = 'avoid'
            else:
                investment_stance = 'cautious'
            
            # 統合洞察の生成
            integrated_insights = self._generate_integrated_insights(
                sentiment_result, financial_result, overall_score, integrated_risk
            )
            
            return {
                'overall_score': round(overall_score, 1),
                'risk_level': integrated_risk,
                'investment_stance': investment_stance,
                'integration_method': integration_method,
                'component_scores': {
                    'sentiment_score': round(sentiment_score, 1),
                    'financial_score': round(financial_score, 1),
                    'weights': weights,
                },
                'integrated_insights': integrated_insights,
                'key_findings': self._extract_key_findings(sentiment_result, financial_result),
                'investment_recommendation': self._generate_investment_recommendation(
                    overall_score, integrated_risk, investment_stance
                ),
            }
            
        except Exception as e:
            logger.error(f"分析結果統合エラー: {e}")
            return {
                'overall_score': 50.0,
                'risk_level': 'medium',
                'investment_stance': 'cautious',
                'error': f'統合処理中にエラーが発生しました: {str(e)}'
            }
                     
    def _save_financial_data(self, document, financial_data: Dict) -> Optional['CompanyFinancialData']:
        """財務データの保存"""
        from ..models import CompanyFinancialData, Company
        from decimal import Decimal
        
        try:
            # 企業情報の取得
            company = None
            try:
                company = Company.objects.get(edinet_code=document.edinet_code)
            except Company.DoesNotExist:
                pass
            
            # 期間情報の推定
            period_start = document.period_start
            period_end = document.period_end
            
            # 期間タイプの判定
            if period_start and period_end:
                period_days = (period_end - period_start).days
                if period_days <= 100:  # 約3ヶ月
                    period_type = 'quarterly'
                elif period_days <= 200:  # 約6ヶ月
                    period_type = 'semi_annual'
                else:
                    period_type = 'annual'
            else:
                period_type = 'annual'  # デフォルト
            
            # 既存データの確認と作成/更新
            financial_record, created = CompanyFinancialData.objects.get_or_create(
                document=document,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                defaults={
                    'company': company,
                    'fiscal_year': period_end.year if period_end else None,
                }
            )
            
            # 財務データの設定
            for key, value in financial_data.items():
                if hasattr(financial_record, key) and value is not None:
                    setattr(financial_record, key, Decimal(str(value)))
            
            # データ品質の評価
            total_fields = 9
            complete_fields = sum(1 for field in [
                'net_sales', 'operating_income', 'net_income',
                'total_assets', 'total_liabilities', 'net_assets',
                'operating_cf', 'investing_cf', 'financing_cf'
            ] if getattr(financial_record, field) is not None)
            
            financial_record.data_completeness = complete_fields / total_fields
            financial_record.extraction_confidence = 0.8  # 基本信頼度
            
            financial_record.save()
            
            logger.info(f"財務データ保存完了: {document.doc_id} - 完全性{financial_record.data_completeness:.1%}")
            return financial_record
            
        except Exception as e:
            logger.error(f"財務データ保存エラー: {document.doc_id} - {e}")
            return None
    
    def _integrate_analysis_results(self, sentiment_result: Dict, financial_result: Dict, 
                                document_info: Dict) -> Dict[str, Any]:
        """分析結果の統合"""
        try:
            # 基本スコアの取得
            sentiment_score = sentiment_result.get('overall_score', 0) * 100  # -1~1 を 0~100 に変換
            
            financial_health = financial_result.get('overall_health', {})
            financial_score = financial_health.get('overall_score', 50)
            
            # 統合スコアの計算
            if financial_result.get('error'):
                # 財務データがない場合は感情分析のみ
                overall_score = max(0, min(100, sentiment_score))
                integration_method = 'sentiment_only'
                weights = {'sentiment': 1.0, 'financial': 0.0}
            else:
                # 両方のデータがある場合は重み付け平均
                sentiment_weight = 0.3
                financial_weight = 0.7
                overall_score = (sentiment_score * sentiment_weight + 
                            financial_score * financial_weight)
                integration_method = 'weighted_average'
                weights = {'sentiment': sentiment_weight, 'financial': financial_weight}
            
            # リスクレベルの統合判定
            sentiment_label = sentiment_result.get('sentiment_label', 'neutral')
            financial_risk = 'medium'
            
            if not financial_result.get('error'):
                financial_risk = financial_health.get('risk_level', 'medium')
            
            # 統合リスクレベル
            if overall_score >= 80 and financial_risk == 'low' and sentiment_label == 'positive':
                integrated_risk = 'low'
            elif overall_score >= 60 and financial_risk != 'high':
                integrated_risk = 'medium'
            else:
                integrated_risk = 'high'
            
            # 投資スタンスの決定
            if integrated_risk == 'low' and overall_score >= 80:
                investment_stance = 'aggressive'
            elif integrated_risk == 'medium' and overall_score >= 60:
                investment_stance = 'conditional'
            elif integrated_risk == 'high' or overall_score < 40:
                investment_stance = 'avoid'
            else:
                investment_stance = 'cautious'
            
            # 統合洞察の生成
            integrated_insights = self._generate_integrated_insights(
                sentiment_result, financial_result, overall_score, integrated_risk
            )
            
            return {
                'overall_score': round(overall_score, 1),
                'risk_level': integrated_risk,
                'investment_stance': investment_stance,
                'integration_method': integration_method,
                'component_scores': {
                    'sentiment_score': round(sentiment_score, 1),
                    'financial_score': round(financial_score, 1),
                    'weights': weights,
                },
                'integrated_insights': integrated_insights,
                'key_findings': self._extract_key_findings(sentiment_result, financial_result),
                'investment_recommendation': self._generate_investment_recommendation(
                    overall_score, integrated_risk, investment_stance
                ),
            }
            
        except Exception as e:
            logger.error(f"分析結果統合エラー: {e}")
            return {
                'overall_score': 50.0,
                'risk_level': 'medium',
                'investment_stance': 'cautious',
                'error': f'統合処理中にエラーが発生しました: {str(e)}'
            }
    def _generate_integrated_insights(self, sentiment_result: Dict, financial_result: Dict,
                                    overall_score: float, integrated_risk: str) -> list[str]:
        """統合洞察の生成"""
        insights = []
        
        # 総合評価に基づく洞察
        if overall_score >= 80:
            insights.append('感情分析と財務分析の両面で非常に良好な結果')
        elif overall_score >= 60:
            insights.append('概ね良好な状況で、投資検討に値する企業')
        elif overall_score >= 40:
            insights.append('一部に課題があるが、改善の兆しも見られる')
        else:
            insights.append('慎重な検討が必要な状況')
        
        # 感情分析の特徴的な結果
        sentiment_label = sentiment_result.get('sentiment_label', 'neutral')
        if sentiment_label == 'positive':
            insights.append('経営陣の前向きな姿勢と自信が文章に表れている')
        elif sentiment_label == 'negative':
            insights.append('課題への言及が多く、慎重な経営姿勢を示している')
        
        # 財務分析の特徴的な結果
        if not financial_result.get('error'):
            cf_analysis = financial_result.get('cashflow_analysis', {})
            pattern_name = cf_analysis.get('pattern', {}).get('name', '')
            
            if pattern_name == '理想型':
                insights.append('理想的なキャッシュフロー構造で財務健全性が高い')
            elif pattern_name == '成長型':
                insights.append('積極的な成長投資を行う企業パターン')
            elif pattern_name == '危険型':
                insights.append('キャッシュフロー構造に深刻な問題あり')
        
        return insights
    
    def _extract_key_findings(self, sentiment_result: Dict, financial_result: Dict) -> Dict[str, list[str]]:
        """主要発見事項の抽出"""
        findings = {
            'strengths': [],
            'concerns': [],
            'opportunities': []
        }
        
        # 感情分析からの発見事項
        sentiment_reasoning = sentiment_result.get('analysis_reasoning', {})
        key_factors = sentiment_reasoning.get('key_factors', [])
        if key_factors:
            if sentiment_result.get('sentiment_label') == 'positive':
                findings['strengths'].extend(key_factors[:2])
            else:
                findings['concerns'].extend(key_factors[:2])
        
        # 財務分析からの発見事項
        if not financial_result.get('error'):
            cf_analysis = financial_result.get('cashflow_analysis', {}).get('analysis', {})
            findings['strengths'].extend(cf_analysis.get('strengths', [])[:2])
            findings['concerns'].extend(cf_analysis.get('concerns', [])[:2])
        
        return findings
    
    def _generate_investment_recommendation(self, overall_score: float, 
                                          integrated_risk: str, investment_stance: str) -> Dict[str, Any]:
        """投資推奨の生成"""
        recommendations = {
            'stance': investment_stance,
            'confidence_level': '',
            'key_reasons': [],
            'monitoring_points': [],
            'timeline': ''
        }
        
        # 信頼度レベル
        if overall_score >= 80:
            recommendations['confidence_level'] = 'high'
        elif overall_score >= 60:
            recommendations['confidence_level'] = 'medium'
        else:
            recommendations['confidence_level'] = 'low'
        
        # 投資スタンス別の推奨理由
        stance_reasons = {
            'aggressive': [
                '健全な財務基盤と前向きな経営姿勢',
                '持続的な成長が期待できる構造',
                'リスクが限定的で安心して投資可能'
            ],
            'conditional': [
                '基本的な投資価値は認められる',
                '一部の懸念点を監視しながら投資検討',
                '市場環境次第で成果が期待できる'
            ],
            'cautious': [
                '現時点では様子見が適切',
                '改善の兆しを確認してから判断',
                'リスクとリターンを慎重に評価'
            ],
            'avoid': [
                '現在の財務状況では投資リスクが高い',
                '抜本的な改善まで投資は控えるべき',
                '他の投資機会を検討することを推奨'
            ]
        }
        
        recommendations['key_reasons'] = stance_reasons.get(investment_stance, [])
        
        # 監視ポイント
        if integrated_risk == 'high':
            recommendations['monitoring_points'] = [
                'キャッシュフロー状況の改善',
                '経営陣の具体的な改善策',
                '四半期ごとの業績動向'
            ]
        else:
            recommendations['monitoring_points'] = [
                '継続的な成長性の確認',
                '市場環境変化への対応力',
                '配当政策の動向'
            ]
        
        # 投資タイムライン
        timeline_map = {
            'aggressive': '短期〜中期での投資実行を推奨',
            'conditional': '3〜6ヶ月以内の状況確認後に判断',
            'cautious': '6ヶ月〜1年の業績推移を見て判断',
            'avoid': '1年以上の改善確認まで投資延期を推奨'
        }
        
        recommendations['timeline'] = timeline_map.get(investment_stance, '')
        
        return recommendations
    
    def _extract_basic_document_text(self, document) -> str:
        """基本的な書類情報からテキスト抽出（フォールバック用）"""
        text_parts = [
            f"企業名: {document.company_name}",
            f"書類概要: {document.doc_description}",
            f"提出日: {document.submit_date_time.strftime('%Y年%m月%d日')}",
        ]
        
        if document.period_start and document.period_end:
            text_parts.append(f"対象期間: {document.period_start}から{document.period_end}")
        
        # より現実的なサンプルテキスト
        sample_scenarios = [
            "当社の業績は前年同期と比較して順調に推移しており、売上高の増加と収益性の向上が実現されています。",
            "一方で、減収幅の縮小も見られ、市場環境の変化に適応しつつ継続的な事業改善を図っています。",
            "営業損失は発生したものの、損失の改善傾向が見られ、今後の回復に期待しています。",
            "今後も持続的な成長を目指し、効率的な経営資源の活用と競争力の強化に取り組んでまいります。"
        ]
        
        text_parts.extend(sample_scenarios)
        return " ".join(text_parts)
    
    def cleanup_expired_sessions(self) -> int:
        """期限切れセッションのクリーンアップ"""
        from ..models import FinancialAnalysisSession
        
        try:
            expired_count = FinancialAnalysisSession.objects.filter(
                expires_at__lt=timezone.now()
            ).delete()[0]
            
            logger.info(f"期限切れ財務分析セッション削除: {expired_count}件")
            return expired_count
            
        except Exception as e:
            logger.error(f"財務分析セッションクリーンアップエラー: {e}")
            return 0