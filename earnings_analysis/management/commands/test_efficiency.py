# test_efficiency.py - 効率化テスト用スクリプト
"""
決算分析効率化のテスト・比較スクリプト

使用方法:
python test_efficiency.py --companies 7203,9983,6758 --test-type full
"""

import os
import sys
import django
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict
import argparse

# Django設定の初期化
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from earnings_analysis.services import EDINETAPIService
from earnings_analysis.analysis_service import OnDemandAnalysisService
from django.utils import timezone


class EfficiencyTester:
    """効率化テスト実行クラス"""
    
    def __init__(self):
        self.edinet_service = EDINETAPIService()
        self.analysis_service = OnDemandAnalysisService()
        self.results = []
    
    def run_comprehensive_test(self, company_codes: List[str]) -> Dict:
        """総合効率化テストを実行"""
        print("🧪 決算分析効率化 総合テストを開始します...")
        print(f"📊 テスト対象企業: {', '.join(company_codes)}")
        print("=" * 60)
        
        overall_results = {
            'test_start_time': datetime.now().isoformat(),
            'companies_tested': len(company_codes),
            'test_results': [],
            'summary': {}
        }
        
        for i, company_code in enumerate(company_codes, 1):
            print(f"\n[{i}/{len(company_codes)}] 企業コード: {company_code}")
            print("-" * 40)
            
            company_result = self._test_single_company(company_code)
            overall_results['test_results'].append(company_result)
            
            # 進捗表示
            progress = (i / len(company_codes)) * 100
            print(f"📈 進捗: {progress:.1f}% 完了")
        
        # サマリーの計算
        overall_results['summary'] = self._calculate_summary(overall_results['test_results'])
        
        # 結果の保存
        self._save_results(overall_results)
        
        # 結果表示
        self._display_results(overall_results)
        
        return overall_results
    
    def _test_single_company(self, company_code: str) -> Dict:
        """単一企業の効率化テスト"""
        result = {
            'company_code': company_code,
            'test_timestamp': datetime.now().isoformat(),
            'tests': {}
        }
        
        try:
            # 1. 企業情報検索テスト
            print("🔍 企業情報検索テスト...")
            info_test = self._test_company_info_search(company_code)
            result['tests']['company_info_search'] = info_test
            
            # 2. 効率的書類検索テスト
            print("📄 効率的書類検索テスト...")
            doc_test = self._test_document_search(company_code)
            result['tests']['document_search'] = doc_test
            
            # 3. 書類選択最適化テスト
            print("🎯 書類選択最適化テスト...")
            selection_test = self._test_document_selection(company_code)
            result['tests']['document_selection'] = selection_test
            
            # 4. 全体分析性能テスト
            print("⚡ 全体分析性能テスト...")
            analysis_test = self._test_full_analysis(company_code)
            result['tests']['full_analysis'] = analysis_test
            
            # 5. キャッシュ効率テスト
            print("💾 キャッシュ効率テスト...")
            cache_test = self._test_cache_efficiency(company_code)
            result['tests']['cache_efficiency'] = cache_test
            
            result['overall_success'] = True
            
        except Exception as e:
            print(f"❌ テスト中にエラー: {str(e)}")
            result['overall_success'] = False
            result['error'] = str(e)
        
        return result
    
    def _test_company_info_search(self, company_code: str) -> Dict:
        """企業情報検索の効率化テスト"""
        start_time = time.time()
        
        try:
            company_info = self.edinet_service.get_company_info_by_code(company_code)
            search_time = time.time() - start_time
            
            if company_info:
                result = {
                    'success': True,
                    'search_time': round(search_time, 2),
                    'company_name': company_info.get('company_name', '不明'),
                    'source': company_info.get('source', '不明'),
                    'documents_found': company_info.get('found_documents_count', 0),
                    'efficiency_rating': self._rate_efficiency(search_time, 'company_search')
                }
                print(f"  ✅ 成功: {result['company_name']} ({search_time:.2f}秒)")
            else:
                result = {
                    'success': False,
                    'search_time': round(search_time, 2),
                    'error': '企業情報が見つかりませんでした',
                    'efficiency_rating': 'N/A'
                }
                print(f"  ❌ 失敗: 企業情報が見つかりません ({search_time:.2f}秒)")
            
            return result
            
        except Exception as e:
            search_time = time.time() - start_time
            print(f"  ❌ エラー: {str(e)} ({search_time:.2f}秒)")
            return {
                'success': False,
                'search_time': round(search_time, 2),
                'error': str(e),
                'efficiency_rating': 'N/A'
            }
    
    def _test_document_search(self, company_code: str) -> Dict:
        """効率的書類検索のテスト"""
        start_time = time.time()
        
        try:
            documents = self.edinet_service.get_company_documents_efficiently(company_code)
            search_time = time.time() - start_time
            
            # 書類の分析
            doc_types = {}
            latest_date = None
            
            for doc in documents:
                doc_type = doc.get('doc_type_code', 'unknown')
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                
                doc_date = doc.get('submission_date', '')
                if doc_date and (not latest_date or doc_date > latest_date):
                    latest_date = doc_date
            
            result = {
                'success': True,
                'search_time': round(search_time, 2),
                'documents_found': len(documents),
                'document_types': doc_types,
                'latest_document_date': latest_date,
                'efficiency_rating': self._rate_efficiency(search_time, 'document_search')
            }
            
            print(f"  ✅ 成功: {len(documents)}件の書類を発見 ({search_time:.2f}秒)")
            print(f"     書類種別: {doc_types}")
            
            return result
            
        except Exception as e:
            search_time = time.time() - start_time
            print(f"  ❌ エラー: {str(e)} ({search_time:.2f}秒)")
            return {
                'success': False,
                'search_time': round(search_time, 2),
                'error': str(e),
                'efficiency_rating': 'N/A'
            }
    
    def _test_document_selection(self, company_code: str) -> Dict:
        """書類選択最適化のテスト"""
        start_time = time.time()
        
        try:
            # 効率的検索で書類を取得
            documents = self.edinet_service.find_latest_documents_for_analysis(company_code)
            selection_time = time.time() - start_time
            
            if not documents:
                return {
                    'success': False,
                    'selection_time': round(selection_time, 2),
                    'error': '分析用書類が見つかりませんでした',
                    'efficiency_rating': 'N/A'
                }
            
            # 最適書類の選択をテスト
            selected_docs = self.edinet_service._select_best_documents_for_analysis(documents)
            
            result = {
                'success': True,
                'selection_time': round(selection_time, 2),
                'total_documents': len(documents),
                'selected_documents': len(selected_docs),
                'selection_efficiency': round(len(selected_docs) / len(documents) * 100, 1),
                'selected_types': [doc.get('doc_type_code', 'unknown') for doc in selected_docs],
                'efficiency_rating': self._rate_efficiency(selection_time, 'document_selection')
            }
            
            print(f"  ✅ 成功: {len(documents)}件中{len(selected_docs)}件を選択 ({selection_time:.2f}秒)")
            print(f"     選択効率: {result['selection_efficiency']}%")
            
            return result
            
        except Exception as e:
            selection_time = time.time() - start_time
            print(f"  ❌ エラー: {str(e)} ({selection_time:.2f}秒)")
            return {
                'success': False,
                'selection_time': round(selection_time, 2),
                'error': str(e),
                'efficiency_rating': 'N/A'
            }
    
    def _test_full_analysis(self, company_code: str) -> Dict:
        """全体分析性能のテスト"""
        start_time = time.time()
        
        try:
            # 分析実行（キャッシュは使用しない）
            result = self.analysis_service.get_or_analyze_company(
                company_code, 
                force_refresh=True
            )
            analysis_time = time.time() - start_time
            
            analysis_result = {
                'success': result.get('success', False),
                'analysis_time': round(analysis_time, 2),
                'has_cashflow': result.get('cashflow_analysis') is not None,
                'has_sentiment': result.get('sentiment_analysis') is not None,
                'efficiency_rating': self._rate_efficiency(analysis_time, 'full_analysis')
            }
            
            if result.get('success'):
                print(f"  ✅ 成功: 分析完了 ({analysis_time:.2f}秒)")
                print(f"     CF分析: {'✓' if analysis_result['has_cashflow'] else '✗'}")
                print(f"     感情分析: {'✓' if analysis_result['has_sentiment'] else '✗'}")
            else:
                analysis_result['error'] = result.get('error', '不明なエラー')
                print(f"  ❌ 失敗: {analysis_result['error']} ({analysis_time:.2f}秒)")
            
            return analysis_result
            
        except Exception as e:
            analysis_time = time.time() - start_time
            print(f"  ❌ エラー: {str(e)} ({analysis_time:.2f}秒)")
            return {
                'success': False,
                'analysis_time': round(analysis_time, 2),
                'error': str(e),
                'efficiency_rating': 'N/A'
            }
    
    def _test_cache_efficiency(self, company_code: str) -> Dict:
        """キャッシュ効率のテスト"""
        try:
            # 1回目: 新規分析（キャッシュなし）
            start_time = time.time()
            result1 = self.analysis_service.get_or_analyze_company(company_code, force_refresh=True)
            first_time = time.time() - start_time
            
            # 2回目: キャッシュありの分析
            start_time = time.time()
            result2 = self.analysis_service.get_or_analyze_company(company_code, force_refresh=False)
            second_time = time.time() - start_time
            
            if result1.get('success') and result2.get('success'):
                speed_improvement = ((first_time - second_time) / first_time) * 100
                
                cache_result = {
                    'success': True,
                    'first_analysis_time': round(first_time, 2),
                    'cached_analysis_time': round(second_time, 2),
                    'speed_improvement': round(speed_improvement, 1),
                    'cache_hit': result2.get('from_cache', False),
                    'efficiency_rating': self._rate_cache_efficiency(speed_improvement)
                }
                
                print(f"  ✅ 成功: キャッシュで{speed_improvement:.1f}%高速化")
                print(f"     初回: {first_time:.2f}秒 → 2回目: {second_time:.2f}秒")
                
            else:
                cache_result = {
                    'success': False,
                    'error': '分析が失敗したためキャッシュテストできません',
                    'efficiency_rating': 'N/A'
                }
                print(f"  ❌ 失敗: 分析エラーのためキャッシュテスト不可")
            
            return cache_result
            
        except Exception as e:
            print(f"  ❌ エラー: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'efficiency_rating': 'N/A'
            }
    
    def _rate_efficiency(self, time_taken: float, test_type: str) -> str:
        """効率性を評価"""
        thresholds = {
            'company_search': {'excellent': 3, 'good': 8, 'fair': 15},
            'document_search': {'excellent': 5, 'good': 15, 'fair': 30},
            'document_selection': {'excellent': 1, 'good': 3, 'fair': 8},
            'full_analysis': {'excellent': 30, 'good': 60, 'fair': 120},
        }
        
        if test_type not in thresholds:
            return 'unknown'
        
        threshold = thresholds[test_type]
        
        if time_taken <= threshold['excellent']:
            return 'excellent'
        elif time_taken <= threshold['good']:
            return 'good'
        elif time_taken <= threshold['fair']:
            return 'fair'
        else:
            return 'poor'
    
    def _rate_cache_efficiency(self, improvement: float) -> str:
        """キャッシュ効率を評価"""
        if improvement >= 80:
            return 'excellent'
        elif improvement >= 60:
            return 'good'
        elif improvement >= 30:
            return 'fair'
        else:
            return 'poor'
    
    def _calculate_summary(self, test_results: List[Dict]) -> Dict:
        """テスト結果のサマリーを計算"""
        total_companies = len(test_results)
        successful_companies = sum(1 for r in test_results if r.get('overall_success', False))
        
        # 平均時間の計算
        avg_times = {}
        efficiency_ratings = {}
        
        test_types = ['company_info_search', 'document_search', 'document_selection', 'full_analysis', 'cache_efficiency']
        
        for test_type in test_types:
            times = []
            ratings = []
            
            for result in test_results:
                if test_type in result.get('tests', {}):
                    test_data = result['tests'][test_type]
                    if test_data.get('success'):
                        if test_type == 'cache_efficiency':
                            if 'first_analysis_time' in test_data:
                                times.append(test_data['first_analysis_time'])
                        else:
                            time_key = f"{test_type.replace('_', '_')}_time".replace('company_info_search_time', 'search_time')
                            if 'search_time' in test_data:
                                times.append(test_data['search_time'])
                            elif 'selection_time' in test_data:
                                times.append(test_data['selection_time'])
                            elif 'analysis_time' in test_data:
                                times.append(test_data['analysis_time'])
                        
                        ratings.append(test_data.get('efficiency_rating', 'unknown'))
            
            avg_times[test_type] = round(sum(times) / len(times), 2) if times else 0
            
            # 効率性評価の分布
            rating_counts = {}
            for rating in ratings:
                rating_counts[rating] = rating_counts.get(rating, 0) + 1
            efficiency_ratings[test_type] = rating_counts
        
        return {
            'total_companies': total_companies,
            'successful_companies': successful_companies,
            'success_rate': round((successful_companies / total_companies) * 100, 1) if total_companies > 0 else 0,
            'average_times': avg_times,
            'efficiency_ratings': efficiency_ratings,
            'overall_efficiency': self._calculate_overall_efficiency(efficiency_ratings)
        }
    
    def _calculate_overall_efficiency(self, efficiency_ratings: Dict) -> str:
        """全体的な効率性を計算"""
        excellent_count = 0
        good_count = 0
        total_count = 0
        
        for test_type, ratings in efficiency_ratings.items():
            excellent_count += ratings.get('excellent', 0)
            good_count += ratings.get('good', 0)
            for count in ratings.values():
                total_count += count
        
        if total_count == 0:
            return 'unknown'
        
        excellent_rate = excellent_count / total_count
        good_rate = (excellent_count + good_count) / total_count
        
        if excellent_rate >= 0.7:
            return 'excellent'
        elif good_rate >= 0.8:
            return 'good'
        elif good_rate >= 0.5:
            return 'fair'
        else:
            return 'poor'
    
    def _save_results(self, results: Dict):
        """テスト結果を保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'efficiency_test_results_{timestamp}.json'
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 テスト結果を保存しました: {filename}")
        except Exception as e:
            print(f"\n❌ 結果保存エラー: {str(e)}")
    
    def _display_results(self, results: Dict):
        """テスト結果を表示"""
        print("\n" + "=" * 60)
        print("🏁 効率化テスト結果サマリー")
        print("=" * 60)
        
        summary = results['summary']
        
        print(f"📊 テスト対象企業数: {summary['total_companies']}")
        print(f"✅ 成功企業数: {summary['successful_companies']}")
        print(f"📈 成功率: {summary['success_rate']}%")
        
        print(f"\n⏱️ 平均処理時間:")
        for test_type, avg_time in summary['average_times'].items():
            print(f"  {test_type}: {avg_time}秒")
        
        print(f"\n🎯 全体効率性評価: {summary['overall_efficiency'].upper()}")
        
        # 効率性評価の詳細
        print(f"\n📋 効率性評価分布:")
        for test_type, ratings in summary['efficiency_ratings'].items():
            print(f"  {test_type}:")
            for rating, count in ratings.items():
                print(f"    {rating}: {count}社")
        
        # 推奨事項
        print(f"\n💡 推奨事項:")
        overall_eff = summary['overall_efficiency']
        if overall_eff == 'excellent':
            print("  🎉 優秀な効率性です。現在の設定を維持してください。")
        elif overall_eff == 'good':
            print("  ✅ 良好な効率性です。一部の最適化を検討してください。")
        elif overall_eff == 'fair':
            print("  ⚠️ 改善の余地があります。設定の見直しを推奨します。")
        else:
            print("  🔧 大幅な改善が必要です。システム構成を見直してください。")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='決算分析効率化テストスクリプト')
    parser.add_argument('--companies', type=str, required=True,
                       help='テスト対象企業コード（カンマ区切り）例: 7203,9983,6758')
    parser.add_argument('--test-type', type=str, choices=['quick', 'full'], default='full',
                       help='テストタイプ (quick: 基本テスト, full: 総合テスト)')
    parser.add_argument('--output', type=str, help='結果出力ファイル名')
    
    args = parser.parse_args()
    
    # 企業コードをリストに変換
    company_codes = [code.strip() for code in args.companies.split(',')]
    
    # テスト実行
    tester = EfficiencyTester()
    
    if args.test_type == 'quick':
        print("🚀 クイックテストモード")
        # 簡易テストの実装（省略）
    else:
        results = tester.run_comprehensive_test(company_codes)
    
    print("\n🎯 テスト完了！")


if __name__ == '__main__':
    main()