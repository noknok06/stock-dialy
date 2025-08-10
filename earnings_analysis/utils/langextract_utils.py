# earnings_analysis/utils/langextract_utils.py (新規作成)
"""
Langextract関連のユーティリティ機能
"""
import logging
from django.conf import settings
from typing import Dict, Any, Optional, Tuple
import time

logger = logging.getLogger(__name__)

class LangextractHealthChecker:
    """Langextractの動作状況をチェックするクラス"""
    
    def __init__(self):
        self.last_check_time = 0
        self.last_check_result = None
        self.check_interval = 300  # 5分間キャッシュ
    
    def is_langextract_available(self) -> Tuple[bool, str]:
        """Langextractが利用可能かチェック"""
        current_time = time.time()
        
        # キャッシュされた結果を使用（5分以内）
        if (current_time - self.last_check_time) < self.check_interval and self.last_check_result:
            return self.last_check_result
        
        # 新しいチェックを実行
        available, message = self._perform_health_check()
        
        self.last_check_time = current_time
        self.last_check_result = (available, message)
        
        return available, message
    
    def _perform_health_check(self) -> Tuple[bool, str]:
        """実際のヘルスチェックを実行"""
        try:
            # 1. 設定確認
            if not getattr(settings, 'LANGEXTRACT_ENABLED', False):
                return False, "LANGEXTRACT_ENABLEDがFalseに設定されています"
            
            # 2. Gemini APIキー確認
            gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
            if not gemini_key:
                return False, "GEMINI_API_KEYが設定されていません"
            
            if len(gemini_key) < 20:
                return False, "GEMINI_API_KEYが無効のようです"
            
            # 3. ライブラリのインポート確認
            try:
                import langextract
                logger.info("Langextractライブラリのインポート成功")
            except ImportError as e:
                return False, f"Langextractライブラリがインストールされていません: {e}"
            
            # 4. Google AI Platform確認
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                logger.info("Google Generative AI設定成功")
            except Exception as e:
                return False, f"Google Generative AI設定エラー: {e}"
            
            # 5. 簡単なテスト実行
            try:
                test_result = self._perform_simple_test()
                if test_result:
                    return True, "Langextractが正常に動作しています"
                else:
                    return False, "Langextractテストが失敗しました"
            except Exception as e:
                return False, f"Langextractテストエラー: {e}"
                
        except Exception as e:
            logger.error(f"Langextractヘルスチェックエラー: {e}")
            return False, f"ヘルスチェック中にエラーが発生: {e}"
    
    def _perform_simple_test(self) -> bool:
        """簡単なLangextractテストを実行"""
        try:
            import langextract
            
            # 最小限のテストスキーマ
            test_schema = {
                "type": "object",
                "properties": {
                    "test_result": {"type": "string"}
                },
                "required": ["test_result"]
            }
            
            # 短いテストテキスト
            test_text = "これはLangextractのテストです。"
            
            # Langextract実行（タイムアウト付き）
            extractor = langextract.LangExtractor(model_name="gemini-2.5-flash")
            
            result = extractor.extract(
                text=test_text,
                schema=test_schema,
                instruction="テストが成功した場合は「成功」と回答してください。"
            )
            
            # 結果確認
            if result and isinstance(result, dict) and 'test_result' in result:
                logger.info("Langextract簡易テスト成功")
                return True
            else:
                logger.warning("Langextract簡易テスト：予期しない結果")
                return False
                
        except Exception as e:
            logger.error(f"Langextract簡易テストエラー: {e}")
            return False


class LangextractFallbackManager:
    """Langextract失敗時のフォールバック管理"""
    
    def __init__(self):
        self.fallback_strategies = [
            'traditional_gemini',
            'dictionary_only',
            'basic_analysis'
        ]
    
    def get_best_fallback_strategy(self, error_type: str, context: Dict[str, Any]) -> str:
        """エラータイプに基づいて最適なフォールバック戦略を選択"""
        
        if error_type == 'timeout':
            # タイムアウトの場合は軽量な分析に切り替え
            return 'dictionary_only'
        
        elif error_type == 'api_quota_exceeded':
            # API制限の場合は辞書ベース分析
            return 'dictionary_only'
        
        elif error_type == 'authentication_error':
            # 認証エラーの場合は基本分析のみ
            return 'basic_analysis'
        
        elif error_type == 'invalid_response':
            # 無効な応答の場合は従来のGemini
            return 'traditional_gemini'
        
        else:
            # その他のエラーは従来のGemini
            return 'traditional_gemini'
    
    def execute_fallback_strategy(self, strategy: str, text_content: str, 
                                document_info: Dict[str, str]) -> Dict[str, Any]:
        """フォールバック戦略を実行"""
        
        try:
            if strategy == 'traditional_gemini':
                return self._execute_traditional_gemini(text_content, document_info)
            
            elif strategy == 'dictionary_only':
                return self._execute_dictionary_only(text_content, document_info)
            
            elif strategy == 'basic_analysis':
                return self._execute_basic_analysis(text_content, document_info)
            
            else:
                logger.warning(f"不明なフォールバック戦略: {strategy}")
                return self._execute_basic_analysis(text_content, document_info)
                
        except Exception as e:
            logger.error(f"フォールバック戦略実行エラー ({strategy}): {e}")
            return self._execute_basic_analysis(text_content, document_info)
    
    def _execute_traditional_gemini(self, text_content: str, document_info: Dict[str, str]) -> Dict[str, Any]:
        """従来のGemini分析を実行"""
        try:
            from ..services.gemini_insights import GeminiInsightsGenerator
            
            generator = GeminiInsightsGenerator()
            if generator.api_available:
                result = generator._perform_traditional_gemini_analysis(
                    text_content, document_info, time.time()
                )
                result['fallback_strategy'] = 'traditional_gemini'
                return result
            else:
                raise Exception("Gemini APIが利用できません")
                
        except Exception as e:
            logger.error(f"従来Gemini分析エラー: {e}")
            return self._execute_dictionary_only(text_content, document_info)
    
    def _execute_dictionary_only(self, text_content: str, document_info: Dict[str, str]) -> Dict[str, Any]:
        """辞書ベース分析のみを実行"""
        try:
            from ..services.sentiment_analyzer import SentimentAnalysisService
            
            service = SentimentAnalysisService()
            result = service._perform_basic_sentiment_analysis(text_content)
            result['analysis_method'] = 'dictionary_only'
            result['fallback_strategy'] = 'dictionary_only'
            
            return result
            
        except Exception as e:
            logger.error(f"辞書ベース分析エラー: {e}")
            return self._execute_basic_analysis(text_content, document_info)
    
    def _execute_basic_analysis(self, text_content: str, document_info: Dict[str, str]) -> Dict[str, Any]:
        """最小限の基本分析を実行"""
        return {
            'overall_score': 0.0,
            'sentiment_label': 'neutral',
            'confidence_score': 0.2,
            'analysis_method': 'basic_fallback',
            'fallback_strategy': 'basic_analysis',
            'reasoning': 'AI分析が利用できないため、基本的な処理のみ実行されました。',
            'statistics': {
                'total_words_analyzed': len(text_content.split()) if text_content else 0,
                'fallback_used': True
            },
            'investment_points': [
                {
                    'title': '分析制限',
                    'description': '高度なAI分析が利用できないため、限定的な情報のみ提供されています。',
                    'source': 'basic_fallback'
                },
                {
                    'title': '代替手段の推奨',
                    'description': 'より詳細な分析のため、時間をおいて再実行することを推奨します。',
                    'source': 'basic_fallback'
                }
            ]
        }


class LangextractMetrics:
    """Langextract使用状況の監視・メトリクス"""
    
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'fallback_usage': {},
            'average_processing_time': 0,
            'error_types': {}
        }
    
    def record_request(self, success: bool, processing_time: float = 0, 
                      error_type: Optional[str] = None, fallback_strategy: Optional[str] = None):
        """リクエスト情報を記録"""
        self.metrics['total_requests'] += 1
        
        if success:
            self.metrics['successful_requests'] += 1
            # 処理時間の移動平均を計算
            current_avg = self.metrics['average_processing_time']
            total_successful = self.metrics['successful_requests']
            self.metrics['average_processing_time'] = (
                (current_avg * (total_successful - 1) + processing_time) / total_successful
            )
        else:
            self.metrics['failed_requests'] += 1
            
            if error_type:
                self.metrics['error_types'][error_type] = (
                    self.metrics['error_types'].get(error_type, 0) + 1
                )
            
            if fallback_strategy:
                self.metrics['fallback_usage'][fallback_strategy] = (
                    self.metrics['fallback_usage'].get(fallback_strategy, 0) + 1
                )
    
    def get_success_rate(self) -> float:
        """成功率を取得"""
        if self.metrics['total_requests'] == 0:
            return 0.0
        
        return (self.metrics['successful_requests'] / self.metrics['total_requests']) * 100
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """メトリクスサマリーを取得"""
        return {
            'success_rate': self.get_success_rate(),
            'total_requests': self.metrics['total_requests'],
            'successful_requests': self.metrics['successful_requests'],
            'failed_requests': self.metrics['failed_requests'],
            'average_processing_time': self.metrics['average_processing_time'],
            'most_common_error': max(self.metrics['error_types'].items(), 
                                   key=lambda x: x[1], default=('なし', 0))[0],
            'most_used_fallback': max(self.metrics['fallback_usage'].items(), 
                                    key=lambda x: x[1], default=('なし', 0))[0]
        }


# グローバルインスタンス
health_checker = LangextractHealthChecker()
fallback_manager = LangextractFallbackManager()
metrics_tracker = LangextractMetrics()


def check_langextract_health() -> Tuple[bool, str]:
    """Langextractの健康状態をチェック（外部インターフェース）"""
    return health_checker.is_langextract_available()


def get_langextract_fallback(error_type: str, text_content: str, 
                           document_info: Dict[str, str]) -> Dict[str, Any]:
    """Langextract失敗時のフォールバック実行（外部インターフェース）"""
    context = {'text_length': len(text_content), 'document_info': document_info}
    strategy = fallback_manager.get_best_fallback_strategy(error_type, context)
    
    return fallback_manager.execute_fallback_strategy(strategy, text_content, document_info)


def record_langextract_usage(success: bool, processing_time: float = 0, 
                           error_type: Optional[str] = None, 
                           fallback_strategy: Optional[str] = None):
    """Langextract使用状況を記録（外部インターフェース）"""
    metrics_tracker.record_request(success, processing_time, error_type, fallback_strategy)


def get_langextract_metrics() -> Dict[str, Any]:
    """Langextractメトリクスを取得（外部インターフェース）"""
    return metrics_tracker.get_metrics_summary()