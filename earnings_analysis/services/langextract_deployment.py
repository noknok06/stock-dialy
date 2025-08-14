# earnings_analysis/services/langextract_deployment.py
"""
LangExtract感情分析の段階的導入とモニタリングシステム
"""

import logging
import time
import random
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

@dataclass
class AnalysisPerformanceMetrics:
    """分析パフォーマンス指標"""
    session_id: str
    method: str  # 'traditional', 'langextract', 'hybrid'
    processing_time: float
    accuracy_score: Optional[float]
    confidence_level: float
    error_occurred: bool
    error_message: str
    text_length: int
    sections_count: int
    api_calls_count: int
    timestamp: datetime

class LangExtractDeploymentManager:
    """LangExtract段階的導入管理"""
    
    def __init__(self):
        self.rollout_percentage = getattr(settings, 'LANGEXTRACT_ROLLOUT_PERCENTAGE', 0)
        self.company_whitelist = getattr(settings, 'LANGEXTRACT_COMPANY_WHITELIST', [])
        self.doc_type_whitelist = getattr(settings, 'LANGEXTRACT_DOC_TYPE_WHITELIST', [])
        self.performance_cache_timeout = 3600  # 1時間
        
    def should_use_langextract(self, document) -> Tuple[bool, str]:
        """LangExtractを使用すべきかを判定"""
        
        # 1. 機能フラグチェック
        if not getattr(settings, 'USE_LANGEXTRACT_SENTIMENT', False):
            return False, "feature_disabled"
        
        # 2. 会社ホワイトリストチェック
        if self.company_whitelist:
            company_key = self._get_company_key(document)
            if company_key not in self.company_whitelist:
                return False, "company_not_whitelisted"
        
        # 3. 書類種別ホワイトリストチェック
        if self.doc_type_whitelist:
            if document.doc_type_code not in self.doc_type_whitelist:
                return False, "doc_type_not_whitelisted"
        
        # 4. ロールアウト率チェック
        if self.rollout_percentage < 100:
            # 文書IDベースの一貫性のあるランダム判定
            hash_seed = hash(document.doc_id) % 100
            if hash_seed >= self.rollout_percentage:
                return False, "rollout_percentage"
        
        # 5. システム負荷チェック
        if self._is_system_overloaded():
            return False, "system_overloaded"
        
        # 6. 過去のパフォーマンスチェック
        recent_performance = self._get_recent_performance()
        if recent_performance and recent_performance['error_rate'] > 0.5:
            return False, "high_error_rate"
        
        return True, "approved"
    
    def _get_company_key(self, document) -> str:
        """企業識別キー生成"""
        return f"{document.edinet_code}_{document.securities_code}"
    
    def _is_system_overloaded(self) -> bool:
        """システム負荷チェック"""
        # 現在の並行処理数をチェック
        concurrent_analyses = cache.get('langextract_concurrent_count', 0)
        max_concurrent = getattr(settings, 'LANGEXTRACT_MAX_CONCURRENT', 5)
        
        return concurrent_analyses >= max_concurrent
    
    def _get_recent_performance(self) -> Optional[Dict[str, float]]:
        """最近のパフォーマンス指標取得"""
        cache_key = 'langextract_performance_1h'
        return cache.get(cache_key)
    
    def track_analysis_start(self, session_id: str):
        """分析開始の追跡"""
        # 並行処理数を増加
        cache_key = 'langextract_concurrent_count'
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, timeout=300)  # 5分でタイムアウト
        
        # 開始時刻を記録
        start_time_key = f'langextract_start_{session_id}'
        cache.set(start_time_key, time.time(), timeout=300)
    
    def track_analysis_complete(self, session_id: str, success: bool, 
                              error_message: str = None):
        """分析完了の追跡"""
        # 並行処理数を減少
        cache_key = 'langextract_concurrent_count'
        current_count = cache.get(cache_key, 1)
        cache.set(cache_key, max(0, current_count - 1), timeout=300)
        
        # パフォーマンス指標を記録
        start_time_key = f'langextract_start_{session_id}'
        start_time = cache.get(start_time_key)
        
        if start_time:
            processing_time = time.time() - start_time
            self._record_performance_metric(session_id, processing_time, success, error_message)
            cache.delete(start_time_key)

    def _record_performance_metric(self, session_id: str, processing_time: float, 
                                 success: bool, error_message: str = None):
        """パフォーマンス指標記録"""
        try:
            # 最近の指標を取得・更新
            cache_key = 'langextract_performance_1h'
            current_metrics = cache.get(cache_key, {
                'total_count': 0,
                'success_count': 0,
                'error_count': 0,
                'avg_processing_time': 0.0,
                'max_processing_time': 0.0,
            })
            
            current_metrics['total_count'] += 1
            if success:
                current_metrics['success_count'] += 1
            else:
                current_metrics['error_count'] += 1
            
            # 処理時間の更新
            total_time = (current_metrics['avg_processing_time'] * 
                         (current_metrics['total_count'] - 1) + processing_time)
            current_metrics['avg_processing_time'] = total_time / current_metrics['total_count']
            current_metrics['max_processing_time'] = max(
                current_metrics['max_processing_time'], 
                processing_time
            )
            
            # エラー率の計算
            current_metrics['error_rate'] = (
                current_metrics['error_count'] / current_metrics['total_count']
            )
            
            cache.set(cache_key, current_metrics, timeout=self.performance_cache_timeout)
            
            # 詳細ログ記録
            logger.info(f"LangExtract performance: session={session_id}, "
                       f"time={processing_time:.2f}s, success={success}, "
                       f"error='{error_message or 'None'}'")
            
        except Exception as e:
            logger.error(f"Failed to record performance metric: {e}")


class LangExtractMonitoringService:
    """LangExtract分析のモニタリングサービス"""
    
    def __init__(self):
        self.deployment_manager = LangExtractDeploymentManager()
    
    def get_performance_dashboard_data(self) -> Dict[str, Any]:
        """パフォーマンスダッシュボード用データ取得"""
        try:
            # 基本指標
            current_metrics = cache.get('langextract_performance_1h', {})
            
            # 並行処理状況
            concurrent_count = cache.get('langextract_concurrent_count', 0)
            max_concurrent = getattr(settings, 'LANGEXTRACT_MAX_CONCURRENT', 5)
            
            # ロールアウト状況
            rollout_status = {
                'percentage': self.deployment_manager.rollout_percentage,
                'company_whitelist_size': len(self.deployment_manager.company_whitelist),
                'doc_type_whitelist_size': len(self.deployment_manager.doc_type_whitelist),
            }
            
            # 分析手法の比較データ（模擬データ）
            method_comparison = self._get_method_comparison_data()
            
            return {
                'current_metrics': current_metrics,
                'concurrent_processing': {
                    'current': concurrent_count,
                    'max': max_concurrent,
                    'utilization_rate': (concurrent_count / max_concurrent) * 100
                },
                'rollout_status': rollout_status,
                'method_comparison': method_comparison,
                'system_status': self._get_system_status(),
                'recommendations': self._generate_recommendations(current_metrics)
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {'error': str(e)}
    
    def _get_method_comparison_data(self) -> Dict[str, Any]:
        """分析手法比較データ"""
        # 実際の実装では、データベースから過去のパフォーマンスデータを取得
        return {
            'traditional': {
                'avg_processing_time': 15.3,
                'accuracy_score': 0.72,
                'error_rate': 0.02
            },
            'langextract': {
                'avg_processing_time': 45.7,
                'accuracy_score': 0.89,
                'error_rate': 0.08
            },
            'hybrid': {
                'avg_processing_time': 52.1,
                'accuracy_score': 0.93,
                'error_rate': 0.05
            }
        }
    
    def _get_system_status(self) -> Dict[str, str]:
        """システムステータス取得"""
        current_metrics = cache.get('langextract_performance_1h', {})
        error_rate = current_metrics.get('error_rate', 0)
        avg_time = current_metrics.get('avg_processing_time', 0)
        
        if error_rate > 0.3:
            return {'status': 'critical', 'message': 'エラー率が高すぎます'}
        elif error_rate > 0.1:
            return {'status': 'warning', 'message': 'エラー率が上昇しています'}
        elif avg_time > 120:  # 2分超
            return {'status': 'warning', 'message': '処理時間が長くなっています'}
        else:
            return {'status': 'healthy', 'message': 'システムは正常に動作しています'}
    
    def _generate_recommendations(self, metrics: Dict) -> List[str]:
        """改善提案生成"""
        recommendations = []
        
        error_rate = metrics.get('error_rate', 0)
        avg_time = metrics.get('avg_processing_time', 0)
        total_count = metrics.get('total_count', 0)
        
        if error_rate > 0.2:
            recommendations.append(
                f"エラー率が{error_rate:.1%}と高いため、ロールアウト率を下げることを検討してください"
            )
        
        if avg_time > 90:
            recommendations.append(
                f"平均処理時間が{avg_time:.1f}秒と長いため、タイムアウト設定の見直しを検討してください"
            )
        
        if total_count < 10:
            recommendations.append(
                "サンプル数が少ないため、より多くのデータを収集してからパフォーマンスを評価してください"
            )
        
        if not recommendations:
            recommendations.append("現在のパフォーマンスは良好です。ロールアウト拡大を検討できます")
        
        return recommendations


class LangExtractABTestManager:
    """LangExtract A/Bテスト管理"""
    
    def __init__(self):
        self.test_groups = {
            'control': 0.3,      # 従来手法のみ
            'langextract': 0.3,  # LangExtractのみ
            'hybrid': 0.4,       # ハイブリッド
        }
    
    def assign_test_group(self, document) -> str:
        """テストグループ割り当て"""
        # 文書IDベースの一貫性のあるグループ分け
        hash_value = hash(document.doc_id) % 100
        
        cumulative = 0
        for group, percentage in self.test_groups.items():
            cumulative += percentage * 100
            if hash_value < cumulative:
                return group
        
        return 'control'  # フォールバック
    
    def record_ab_test_result(self, session_id: str, group: str, 
                            result: Dict[str, Any]):
        """A/Bテスト結果記録"""
        cache_key = f'ab_test_results_{group}'
        current_results = cache.get(cache_key, [])
        
        test_result = {
            'session_id': session_id,
            'group': group,
            'overall_score': result.get('overall_score', 0),
            'processing_time': result.get('processing_time', 0),
            'confidence': result.get('confidence_level', 0),
            'timestamp': timezone.now().isoformat()
        }
        
        current_results.append(test_result)
        
        # 最新100件のみ保持
        if len(current_results) > 100:
            current_results = current_results[-100:]
        
        cache.set(cache_key, current_results, timeout=86400)  # 24時間

