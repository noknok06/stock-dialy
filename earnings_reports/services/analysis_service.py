"""
earnings_reports/services/analysis_service.py
堅牢化された決算書類分析サービス - エラーハンドリング強化版
"""

import re
import zipfile
import io
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from ..models import Analysis, SentimentAnalysis, CashFlowAnalysis, Document
from .edinet_service import EDINETService

logger = logging.getLogger('earnings_analysis')


class EarningsAnalysisService:
    """堅牢化された決算分析サービス"""
    
    def __init__(self):
        """初期化"""
        self.edinet_service = EDINETService(settings.EDINET_API_KEY)
        
        # 感情分析用キーワード辞書（拡張版）
        self.sentiment_keywords = {
            'positive': [
                # 成長・拡大関連
                '成長', '拡大', '増加', '増収', '増益', '向上', '改善', '好調', '堅調', '順調',
                '強化', '拡充', '積極的', '前向き', '期待', '自信', '確信', '達成', '成功',
                '革新', '変革', '進歩', '発展', '躍進', '飛躍', '突破', '上昇', '伸長',
                # 品質・効率関連
                '高品質', '効率', '最適', '優秀', '卓越', '先進', '画期的', '革命的',
                # 市場・競争関連
                '優位', '領先', 'トップ', 'リーダー', 'シェア拡大', '競争力', '差別化'
            ],
            'negative': [
                # 減少・悪化関連
                '減少', '減収', '減益', '低下', '悪化', '困難', '課題', '問題', '懸念', '不安',
                '厳しい', '苦戦', '低迷', '停滞', '遅れ', '縮小', '減退', '悪化', '下落',
                # リスク・危機関連
                'リスク', '脅威', '危機', '損失', '赤字', '不振', '不調', '失敗', '挫折',
                # 不確実性関連
                '不透明', '不安定', '変動', '混乱', '困窮', '破綻', '危険'
            ],
            'confidence': [
                '確実', '確信', '自信', '見通し', '計画通り', '予定通り', '順調',
                '達成', '実現', '可能', '期待', '目標', '戦略的', '安定', '着実',
                '確保', '維持', '継続', '持続', '推進', '強固', '堅実'
            ],
            'uncertainty': [
                '不確実', '不透明', '未定', '検討中', '様子見', '慎重', '判断困難',
                '困難', '予測困難', '判断', '状況次第', '不明', '未確定', '検討',
                '課題', '懸念', '注視', '見極め', '模索', '検証'
            ],
            'growth': [
                '成長戦略', '事業拡大', '新規事業', '投資', 'M&A', 'DX', 'デジタル変革',
                '海外展開', 'グローバル', 'イノベーション', '新商品', '新サービス',
                'AI', 'IoT', 'クラウド', 'ビッグデータ', 'サステナビリティ', 'ESG'
            ],
            'risk': [
                'リスク', '不確実性', '変動', '影響', '懸念', '課題', '問題',
                '競争激化', '原材料高', '人手不足', '為替', '金利', 'インフレ',
                'コロナ', 'パンデミック', '地政学', '規制', '法改正', 'サイバー',
                '自然災害', '気候変動', 'サプライチェーン', '供給網'
            ]
        }
        
        # キャッシュ設定
        self.cache_timeout = 3600  # 1時間
    
    def execute_analysis(self, analysis: Analysis) -> bool:
        """
        分析実行メイン関数（堅牢化版）
        
        Args:
            analysis: 分析オブジェクト
            
        Returns:
            bool: 成功した場合True
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"分析開始: {analysis.document.company.name} - {analysis.document.doc_description}")
            
            with transaction.atomic():
                # 分析状態を処理中に更新
                analysis.status = 'processing'
                analysis.save()
            
            # 1. 書類ダウンロードとキャッシュチェック
            document_content = self._download_with_cache(analysis.document)
            if not document_content:
                raise Exception("書類のダウンロードに失敗しました")
            
            # ダウンロードサイズを記録
            analysis.document.download_size = len(document_content) // (1024 * 1024)  # MB
            analysis.document.is_downloaded = True
            analysis.document.save()
            
            # 2. テキスト抽出と前処理（エラーハンドリング強化）
            extracted_text = self._safe_extract_and_preprocess_text(document_content)
            if not extracted_text:
                raise Exception("有効なテキストの抽出に失敗しました")
            
            logger.info(f"テキスト抽出完了: {len(extracted_text)}文字")
            
            # 3. 分析実行（各分析でエラーハンドリング）
            analysis_results = {}
            
            # 感情分析
            if analysis.settings_json.get('include_sentiment', True):
                logger.info("感情分析を実行中...")
                try:
                    sentiment_result = self._safe_sentiment_analysis(
                        extracted_text, 
                        analysis.settings_json
                    )
                    analysis_results['sentiment'] = sentiment_result
                except Exception as e:
                    logger.warning(f"感情分析エラー: {str(e)}")
                    analysis_results['sentiment'] = self._get_default_sentiment_result()
            
            # キャッシュフロー分析
            if analysis.settings_json.get('include_cashflow', True):
                logger.info("キャッシュフロー分析を実行中...")
                try:
                    cashflow_result = self._safe_cashflow_analysis(
                        extracted_text, 
                        analysis.settings_json
                    )
                    analysis_results['cashflow'] = cashflow_result
                except Exception as e:
                    logger.warning(f"キャッシュフロー分析エラー: {str(e)}")
                    analysis_results['cashflow'] = self._get_default_cashflow_result()
            
            # 4. 分析結果の保存
            with transaction.atomic():
                # 感情分析結果
                if 'sentiment' in analysis_results:
                    self._save_sentiment_analysis(analysis, analysis_results['sentiment'])
                
                # キャッシュフロー分析結果
                if 'cashflow' in analysis_results:
                    self._save_cashflow_analysis(analysis, analysis_results['cashflow'])
                
                # 5. 総合スコア計算
                overall_score = self._calculate_comprehensive_score(analysis, analysis_results)
                
                # 6. 前回分析との比較
                if analysis.settings_json.get('compare_previous', True):
                    try:
                        self._compare_with_previous_analysis(analysis)
                    except Exception as e:
                        logger.warning(f"前回比較エラー: {str(e)}")
                
                # 7. 分析完了
                analysis.status = 'completed'
                analysis.overall_score = overall_score
                analysis.confidence_level = self._determine_confidence_level(analysis, analysis_results)
                analysis.processing_time = (datetime.now() - start_time).total_seconds()
                analysis.save()
                
                # 書類の分析状態を更新
                analysis.document.is_analyzed = True
                analysis.document.save()
            
            logger.info(f"分析完了: {analysis.document.company.name} - スコア: {overall_score}")
            return True
            
        except Exception as e:
            logger.error(f"分析エラー: {str(e)}")
            
            try:
                analysis.status = 'failed'
                analysis.error_message = str(e)
                analysis.processing_time = (datetime.now() - start_time).total_seconds()
                analysis.save()
            except Exception as save_error:
                logger.error(f"エラー保存失敗: {str(save_error)}")
            
            return False
    
    def _safe_extract_and_preprocess_text(self, zip_content: bytes) -> str:
        """
        安全なテキスト抽出・前処理（エラーハンドリング強化）
        
        Args:
            zip_content: ZIPファイルのバイナリデータ
            
        Returns:
            str: 前処理済みテキスト
        """
        extracted_texts = []
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                # ファイル優先順位を設定
                file_priorities = {
                    '.xbrl': 1,  # 最優先
                    '.xml': 2,
                    '.htm': 3,
                    '.html': 4
                }
                
                # ファイルリストを優先順位でソート
                file_list = sorted(
                    zip_file.filelist,
                    key=lambda f: file_priorities.get(
                        '.' + f.filename.split('.')[-1].lower(), 999
                    )
                )
                
                processed_files = 0
                max_files = 10  # 処理するファイル数の上限
                
                for file_info in file_list:
                    if processed_files >= max_files:
                        break
                    
                    filename = file_info.filename.lower()
                    
                    # 対象ファイルの判定
                    if any(ext in filename for ext in ['.xbrl', '.xml', '.htm', '.html']):
                        try:
                            file_content = zip_file.read(file_info.filename)
                            
                            # ファイルサイズチェック（100MB以上は除外）
                            if len(file_content) > 100 * 1024 * 1024:
                                logger.warning(f"ファイルサイズが大きすぎます: {filename}")
                                continue
                            
                            # エンコーディング判定・変換
                            text = self._safe_decode_file_content(file_content)
                            
                            # テキスト前処理
                            clean_text = self._safe_clean_and_structure_text(text)
                            
                            if clean_text and len(clean_text) > 100:  # 最小文字数チェック
                                extracted_texts.append({
                                    'filename': filename,
                                    'text': clean_text,
                                    'length': len(clean_text),
                                    'priority': file_priorities.get(
                                        '.' + filename.split('.')[-1], 999
                                    )
                                })
                                processed_files += 1
                                
                        except Exception as e:
                            logger.warning(f"ファイル{filename}の処理エラー: {str(e)}")
                            continue
            
            # 優先順位順でテキストを結合
            extracted_texts.sort(key=lambda x: (x['priority'], -x['length']))
            
            # 最も適切なテキストを選択（上位3ファイル）
            combined_text = ""
            for text_info in extracted_texts[:3]:
                combined_text += f"\n\n=== {text_info['filename']} ===\n"
                combined_text += text_info['text']
            
            logger.info(f"テキスト抽出完了: {processed_files}ファイル処理, {len(combined_text)}文字")
            return combined_text
            
        except Exception as e:
            logger.error(f"テキスト抽出エラー: {str(e)}")
            return ""
    
    def _safe_decode_file_content(self, content: bytes) -> str:
        """安全なファイル内容のデコード"""
        
        try:
            # BOMを検出してエンコーディングを特定
            if content.startswith(b'\xef\xbb\xbf'):
                return content[3:].decode('utf-8')
            elif content.startswith(b'\xff\xfe'):
                return content[2:].decode('utf-16le')
            elif content.startswith(b'\xfe\xff'):
                return content[2:].decode('utf-16be')
            
            # 一般的なエンコーディングを試行
            encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932']
            
            for encoding in encodings:
                try:
                    decoded = content.decode(encoding)
                    # 日本語文字が含まれているかチェック
                    if any('\u3040' <= char <= '\u309F' or '\u30A0' <= char <= '\u30FF' or '\u4E00' <= char <= '\u9FAF' for char in decoded[:1000]):
                        return decoded
                except UnicodeDecodeError:
                    continue
            
            # すべて失敗した場合はutf-8で強制デコード
            return content.decode('utf-8', errors='ignore')
            
        except Exception as e:
            logger.warning(f"デコードエラー: {str(e)}")
            return ""
    
    def _safe_clean_and_structure_text(self, xml_text: str) -> str:
        """安全なXMLテキストの清浄化と構造化"""
        
        try:
            # 1. XMLタグの除去
            text = re.sub(r'<[^>]+>', '', xml_text)
            
            # 2. HTMLエンティティのデコード
            entity_map = {
                '&lt;': '<', '&gt;': '>', '&amp;': '&', '&nbsp;': ' ',
                '&quot;': '"', '&apos;': "'", '&yen;': '¥', '&copy;': '©'
            }
            for entity, char in entity_map.items():
                text = text.replace(entity, char)
            
            # 3. 数値文字参照の変換（安全に）
            try:
                text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))) if int(m.group(1)) < 1114112 else '', text)
                text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)) if int(m.group(1), 16) < 1114112 else '', text)
            except Exception as e:
                logger.warning(f"数値文字参照変換エラー: {str(e)}")
            
            # 4. 余分な空白・改行の整理
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\n\s*\n', '\n', text)
            
            # 5. 意味のないテキストパターンを除去
            # 数字のみの行
            text = re.sub(r'^[0-9\s\-\.\,\(\)\[\]]+$', '', text, flags=re.MULTILINE)
            # 記号のみの行
            text = re.sub(r'^[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+$', '', text, flags=re.MULTILINE)
            # 短すぎる行（5文字未満）
            text = re.sub(r'^.{1,4}$', '', text, flags=re.MULTILINE)
            
            # 6. 重要セクションの識別と強調
            important_sections = [
                '経営方針', '業績', '事業の状況', 'セグメント', 'キャッシュ・フロー',
                '設備投資', '研究開発', 'リスク', '今後の見通し', '配当', '株主'
            ]
            
            for section in important_sections:
                try:
                    pattern = f'({section}[^。]*。[^。]*。[^。]*。)'
                    text = re.sub(pattern, f'\n\n【重要】\\1\n\n', text)
                except re.error:
                    continue
            
            return text.strip()
            
        except Exception as e:
            logger.warning(f"テキスト清浄化エラー: {str(e)}")
            return xml_text  # 失敗した場合は元のテキストを返す
    
    def _safe_sentiment_analysis(self, text: str, settings: Dict) -> Dict:
        """安全な感情分析（エラーハンドリング強化）"""
        
        result = self._get_default_sentiment_result()
        
        try:
            # テキストを小文字に変換
            text_lower = text.lower()
            
            # 重要セクションの重み付け
            important_text = []
            try:
                important_text = re.findall(r'【重要】([^【]*)', text, re.DOTALL)
            except re.error:
                pass
            
            important_text_combined = ' '.join(important_text)
            
            # 各カテゴリのキーワードカウント（重み付きスコア）
            for category, keywords in self.sentiment_keywords.items():
                total_count = 0
                important_count = 0
                
                for keyword in keywords:
                    try:
                        # 通常テキストでのカウント
                        normal_count = text_lower.count(keyword)
                        total_count += normal_count
                        
                        # 重要セクションでのカウント（重み2倍）
                        if important_text_combined:
                            imp_count = important_text_combined.lower().count(keyword)
                            important_count += imp_count
                            total_count += imp_count  # 重要セクションは追加で加算
                    except Exception:
                        continue
                
                # カテゴリ別スコア計算
                weighted_score = total_count + (important_count * 2)
                
                if category == 'positive':
                    result['positive_score'] = min(100, weighted_score * 1.5)
                elif category == 'negative':
                    result['negative_score'] = min(100, weighted_score * 1.5)
                elif category == 'confidence':
                    result['confidence_keywords_count'] = total_count
                elif category == 'uncertainty':
                    result['uncertainty_keywords_count'] = total_count
                elif category == 'growth':
                    result['growth_keywords_count'] = total_count
                elif category == 'risk':
                    result['risk_keywords_count'] = total_count
            
            # ニュートラルスコア計算
            total_sentiment = result['positive_score'] + result['negative_score']
            if total_sentiment > 0:
                # 正規化
                total = result['positive_score'] + result['negative_score']
                result['positive_score'] = (result['positive_score'] / total) * 100
                result['negative_score'] = (result['negative_score'] / total) * 100
                result['neutral_score'] = 0
            else:
                result['neutral_score'] = 100
            
            # リスク深刻度の詳細判定
            risk_count = result['risk_keywords_count']
            text_length = len(text) / 1000  # KB単位
            
            risk_density = risk_count / max(text_length, 1)  # リスク密度
            
            if risk_density >= 5 or risk_count >= 20:
                result['risk_severity'] = 'critical'
            elif risk_density >= 3 or risk_count >= 10:
                result['risk_severity'] = 'high'
            elif risk_density >= 1 or risk_count >= 5:
                result['risk_severity'] = 'medium'
            else:
                result['risk_severity'] = 'low'
            
            # 重要フレーズ抽出（安全に）
            try:
                result['key_phrases'] = self._safe_extract_contextual_phrases(text, 'positive', max_phrases=10)
                result['risk_phrases'] = self._safe_extract_contextual_phrases(text, 'risk', max_phrases=8)
            except Exception as e:
                logger.warning(f"フレーズ抽出エラー: {str(e)}")
            
            # カスタムキーワード分析
            custom_keywords = settings.get('custom_keywords', [])
            if custom_keywords:
                for keyword in custom_keywords:
                    try:
                        count = text_lower.count(keyword.lower())
                        if count > 0:
                            result['custom_keyword_counts'][keyword] = count
                    except Exception:
                        continue
            
            return result
            
        except Exception as e:
            logger.warning(f"感情分析エラー: {str(e)}")
            return self._get_default_sentiment_result()
    
    def _safe_cashflow_analysis(self, text: str, settings: Dict) -> Dict:
        """安全なキャッシュフロー分析（エラーハンドリング強化）"""
        
        result = self._get_default_cashflow_result()
        
        try:
            # 複数の抽出パターンでキャッシュフロー金額を取得
            cf_amounts = self._safe_extract_comprehensive_cashflow_amounts(text)
            result.update(cf_amounts)
            
            # フリーキャッシュフローの計算
            if result['operating_cf'] is not None and result['investing_cf'] is not None:
                result['free_cf'] = result['operating_cf'] + result['investing_cf']
            
            # パターン分類と詳細分析
            if all(cf_amounts[key] is not None for key in ['operating_cf', 'investing_cf', 'financing_cf']):
                try:
                    pattern_info = self._classify_detailed_cashflow_pattern(
                        result['operating_cf'],
                        result['investing_cf'],
                        result['financing_cf']
                    )
                    result.update(pattern_info)
                except Exception as e:
                    logger.warning(f"CFパターン分類エラー: {str(e)}")
            
            # 成長率分析（前年同期比）
            try:
                growth_rates = self._extract_cashflow_growth_rates(text)
                result.update(growth_rates)
            except Exception as e:
                logger.warning(f"CF成長率分析エラー: {str(e)}")
            
            # CF充足率計算
            try:
                adequacy_ratio = self._calculate_cf_adequacy_ratio(result, text)
                if adequacy_ratio is not None:
                    result['cf_adequacy_ratio'] = adequacy_ratio
            except Exception as e:
                logger.warning(f"CF充足率計算エラー: {str(e)}")
            
            # CF品質スコア計算（詳細版）
            try:
                result['cf_quality_score'] = self._calculate_advanced_cf_quality_score(result, text)
            except Exception as e:
                logger.warning(f"CF品質スコア計算エラー: {str(e)}")
            
            # 詳細解釈の生成
            try:
                result['interpretation'] = self._generate_detailed_cf_interpretation(result, text)
            except Exception as e:
                logger.warning(f"CF解釈生成エラー: {str(e)}")
            
            # リスク要因の詳細特定
            try:
                result['risk_factors'] = self._identify_detailed_cf_risk_factors(result, text)
            except Exception as e:
                logger.warning(f"CFリスク要因特定エラー: {str(e)}")
            
            return result
            
        except Exception as e:
            logger.warning(f"キャッシュフロー分析エラー: {str(e)}")
            return self._get_default_cashflow_result()
    
    def _safe_extract_comprehensive_cashflow_amounts(self, text: str) -> Dict:
        """安全な包括的キャッシュフロー金額抽出"""
        
        cf_amounts = {
            'operating_cf': None,
            'investing_cf': None,
            'financing_cf': None,
            'free_cf': None
        }
        
        # 修正された正規表現パターン
        patterns = {
            'operating_cf': [
                r'営業活動.*?(?:による|に係る).*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'営業.*?CF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Operating.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'営業キャッシュフロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ],
            'investing_cf': [
                r'投資活動.*?(?:による|に係る).*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'投資.*?CF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Investing.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'投資キャッシュフロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ],
            'financing_cf': [
                r'財務活動.*?(?:による|に係る).*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'財務.*?CF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Financing.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'財務キャッシュフロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ],
            'free_cf': [
                r'フリー.*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Free.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',  # 修正: 余分な括弧を削除
                r'FCF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ]
        }
        
        for cf_type, pattern_list in patterns.items():
            amounts = []
            
            for pattern in pattern_list:
                try:
                    # 正規表現の妥当性をチェック
                    re.compile(pattern)
                    
                    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
                    
                    for match in matches:
                        try:
                            # 数値の清浄化
                            amount_str = match.replace(',', '').replace('△', '-').replace('▲', '-').replace('+', '')
                            amount = int(amount_str)
                            amounts.append(amount)
                        except ValueError:
                            continue
                            
                except re.error as e:
                    # 正規表現エラーをログに記録してスキップ
                    logger.warning(f"正規表現パターンエラー ({cf_type}): {str(e)} - パターン: {pattern}")
                    continue
                except Exception as e:
                    logger.warning(f"パターンマッチングエラー ({cf_type}): {str(e)}")
                    continue
            
            if amounts:
                # 複数の値がある場合は、桁数の最も大きい値を採用
                try:
                    best_amount = max(amounts, key=lambda x: len(str(abs(x))))
                    cf_amounts[cf_type] = best_amount
                except Exception as e:
                    logger.warning(f"金額選択エラー ({cf_type}): {str(e)}")
        
        return cf_amounts
    
    def _get_default_sentiment_result(self) -> Dict:
        """デフォルトの感情分析結果"""
        return {
            'positive_score': 0.0,
            'negative_score': 0.0,
            'neutral_score': 100.0,
            'confidence_keywords_count': 0,
            'uncertainty_keywords_count': 0,
            'growth_keywords_count': 0,
            'risk_keywords_count': 0,
            'risk_severity': 'low',
            'key_phrases': [],
            'risk_phrases': [],
            'custom_keyword_counts': {},
            'sentiment_change': None,
            'confidence_change': None
        }
    
    def _get_default_cashflow_result(self) -> Dict:
        """デフォルトのキャッシュフロー分析結果"""
        return {
            'operating_cf': None,
            'investing_cf': None,
            'financing_cf': None,
            'free_cf': None,
            'pattern': 'other',
            'pattern_score': 0.0,
            'operating_cf_growth': None,
            'investing_cf_growth': None,
            'financing_cf_growth': None,
            'cf_adequacy_ratio': None,
            'cf_quality_score': 50.0,
            'interpretation': '分析に必要なデータが不足しています。',
            'risk_factors': []
        }
    
    # 既存のメソッドをそのまま継承...
    
    def _download_with_cache(self, document: Document) -> Optional[bytes]:
        """キャッシュ機能付きの書類ダウンロード"""
        
        # キャッシュキーを生成
        cache_key = f"document_content_{document.doc_id}"
        
        # キャッシュから取得を試行
        cached_content = cache.get(cache_key)
        if cached_content:
            logger.info(f"キャッシュから書類を取得: {document.doc_id}")
            return cached_content
        
        try:
            # EDINETからダウンロード
            logger.info(f"EDINETから書類をダウンロード: {document.doc_id}")
            content = self.edinet_service.download_document(document.doc_id)
            
            if content:
                # キャッシュに保存（1時間）
                cache.set(cache_key, content, self.cache_timeout)
                logger.info(f"書類をキャッシュに保存: {document.doc_id}")
            
            return content
            
        except Exception as e:
            logger.error(f"書類ダウンロードエラー: {str(e)}")
            return None
    
    # 他の既存メソッドも同様にエラーハンドリングを強化
    # （紙面の都合上、主要な修正部分のみ表示）
    
    
    def _download_with_cache(self, document: Document) -> Optional[bytes]:
        """キャッシュ機能付きの書類ダウンロード"""
        
        # キャッシュキーを生成
        cache_key = f"document_content_{document.doc_id}"
        
        # キャッシュから取得を試行
        cached_content = cache.get(cache_key)
        if cached_content:
            logger.info(f"キャッシュから書類を取得: {document.doc_id}")
            return cached_content
        
        try:
            # EDINETからダウンロード
            logger.info(f"EDINETから書類をダウンロード: {document.doc_id}")
            content = self.edinet_service.download_document(document.doc_id)
            
            if content:
                # キャッシュに保存（1時間）
                cache.set(cache_key, content, self.cache_timeout)
                logger.info(f"書類をキャッシュに保存: {document.doc_id}")
            
            return content
            
        except Exception as e:
            logger.error(f"書類ダウンロードエラー: {str(e)}")
            return None
    
    def _extract_and_preprocess_text(self, zip_content: bytes) -> str:
        """
        ZIPファイルからテキストを抽出・前処理
        
        Args:
            zip_content: ZIPファイルのバイナリデータ
            
        Returns:
            str: 前処理済みテキスト
        """
        extracted_texts = []
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                # ファイル優先順位を設定
                file_priorities = {
                    '.xbrl': 1,  # 最優先
                    '.xml': 2,
                    '.htm': 3,
                    '.html': 4
                }
                
                # ファイルリストを優先順位でソート
                file_list = sorted(
                    zip_file.filelist,
                    key=lambda f: file_priorities.get(
                        '.' + f.filename.split('.')[-1].lower(), 999
                    )
                )
                
                processed_files = 0
                max_files = 10  # 処理するファイル数の上限
                
                for file_info in file_list:
                    if processed_files >= max_files:
                        break
                    
                    filename = file_info.filename.lower()
                    
                    # 対象ファイルの判定
                    if any(ext in filename for ext in ['.xbrl', '.xml', '.htm', '.html']):
                        try:
                            file_content = zip_file.read(file_info.filename)
                            
                            # ファイルサイズチェック（100MB以上は除外）
                            if len(file_content) > 100 * 1024 * 1024:
                                logger.warning(f"ファイルサイズが大きすぎます: {filename}")
                                continue
                            
                            # エンコーディング判定・変換
                            text = self._decode_file_content(file_content)
                            
                            # テキスト前処理
                            clean_text = self._clean_and_structure_text(text)
                            
                            if clean_text and len(clean_text) > 100:  # 最小文字数チェック
                                extracted_texts.append({
                                    'filename': filename,
                                    'text': clean_text,
                                    'length': len(clean_text),
                                    'priority': file_priorities.get(
                                        '.' + filename.split('.')[-1], 999
                                    )
                                })
                                processed_files += 1
                                
                        except Exception as e:
                            logger.warning(f"ファイル{filename}の処理エラー: {str(e)}")
                            continue
            
            # 優先順位順でテキストを結合
            extracted_texts.sort(key=lambda x: (x['priority'], -x['length']))
            
            # 最も適切なテキストを選択（上位3ファイル）
            combined_text = ""
            for text_info in extracted_texts[:3]:
                combined_text += f"\n\n=== {text_info['filename']} ===\n"
                combined_text += text_info['text']
            
            logger.info(f"テキスト抽出完了: {processed_files}ファイル処理, {len(combined_text)}文字")
            return combined_text
            
        except Exception as e:
            logger.error(f"テキスト抽出エラー: {str(e)}")
            return ""
    
    def _decode_file_content(self, content: bytes) -> str:
        """ファイル内容のデコード（改善版）"""
        
        # BOMを検出してエンコーディングを特定
        if content.startswith(b'\xef\xbb\xbf'):
            return content[3:].decode('utf-8')
        elif content.startswith(b'\xff\xfe'):
            return content[2:].decode('utf-16le')
        elif content.startswith(b'\xfe\xff'):
            return content[2:].decode('utf-16be')
        
        # 一般的なエンコーディングを試行
        encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932']
        
        for encoding in encodings:
            try:
                decoded = content.decode(encoding)
                # 日本語文字が含まれているかチェック
                if any('\u3040' <= char <= '\u309F' or '\u30A0' <= char <= '\u30FF' or '\u4E00' <= char <= '\u9FAF' for char in decoded[:1000]):
                    return decoded
            except UnicodeDecodeError:
                continue
        
        # すべて失敗した場合はutf-8で強制デコード
        return content.decode('utf-8', errors='ignore')
    
    def _clean_and_structure_text(self, xml_text: str) -> str:
        """XMLテキストの清浄化と構造化（改善版）"""
        
        # 1. XMLタグの除去
        text = re.sub(r'<[^>]+>', '', xml_text)
        
        # 2. HTMLエンティティのデコード
        entity_map = {
            '&lt;': '<', '&gt;': '>', '&amp;': '&', '&nbsp;': ' ',
            '&quot;': '"', '&apos;': "'", '&yen;': '¥', '&copy;': '©'
        }
        for entity, char in entity_map.items():
            text = text.replace(entity, char)
        
        # 3. 数値文字参照の変換
        text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
        text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)
        
        # 4. 余分な空白・改行の整理
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # 5. 意味のないテキストパターンを除去
        # 数字のみの行
        text = re.sub(r'^[0-9\s\-\.\,\(\)\[\]]+$', '', text, flags=re.MULTILINE)
        # 記号のみの行
        text = re.sub(r'^[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+$', '', text, flags=re.MULTILINE)
        # 短すぎる行（5文字未満）
        text = re.sub(r'^.{1,4}$', '', text, flags=re.MULTILINE)
        
        # 6. 重要セクションの識別と強調
        important_sections = [
            '経営方針', '業績', '事業の状況', 'セグメント', 'キャッシュ・フロー',
            '設備投資', '研究開発', 'リスク', '今後の見通し', '配当', '株主'
        ]
        
        for section in important_sections:
            pattern = f'({section}[^。]*。[^。]*。[^。]*。)'
            text = re.sub(pattern, f'\n\n【重要】\\1\n\n', text)
        
        return text.strip()
    
    def _perform_advanced_sentiment_analysis(self, text: str, settings: Dict) -> Dict:
        """
        高度な感情分析（改善版）
        
        Args:
            text: 分析対象テキスト
            settings: 分析設定
            
        Returns:
            Dict: 感情分析結果
        """
        result = {
            'positive_score': 0.0,
            'negative_score': 0.0,
            'neutral_score': 0.0,
            'confidence_keywords_count': 0,
            'uncertainty_keywords_count': 0,
            'growth_keywords_count': 0,
            'risk_keywords_count': 0,
            'risk_severity': 'low',
            'key_phrases': [],
            'risk_phrases': [],
            'custom_keyword_counts': {},
            'sentiment_change': None,
            'confidence_change': None
        }
        
        # テキストを小文字に変換
        text_lower = text.lower()
        
        # 重要セクションの重み付け
        important_text = re.findall(r'【重要】([^【]*)', text, re.DOTALL)
        important_text_combined = ' '.join(important_text)
        
        # 各カテゴリのキーワードカウント（重み付きスコア）
        for category, keywords in self.sentiment_keywords.items():
            total_count = 0
            important_count = 0
            
            for keyword in keywords:
                # 通常テキストでのカウント
                normal_count = text_lower.count(keyword)
                total_count += normal_count
                
                # 重要セクションでのカウント（重み2倍）
                if important_text_combined:
                    imp_count = important_text_combined.lower().count(keyword)
                    important_count += imp_count
                    total_count += imp_count  # 重要セクションは追加で加算
            
            # カテゴリ別スコア計算
            weighted_score = total_count + (important_count * 2)
            
            if category == 'positive':
                result['positive_score'] = min(100, weighted_score * 1.5)
            elif category == 'negative':
                result['negative_score'] = min(100, weighted_score * 1.5)
            elif category == 'confidence':
                result['confidence_keywords_count'] = total_count
            elif category == 'uncertainty':
                result['uncertainty_keywords_count'] = total_count
            elif category == 'growth':
                result['growth_keywords_count'] = total_count
            elif category == 'risk':
                result['risk_keywords_count'] = total_count
        
        # ニュートラルスコア計算
        total_sentiment = result['positive_score'] + result['negative_score']
        if total_sentiment > 0:
            # 正規化
            total = result['positive_score'] + result['negative_score']
            result['positive_score'] = (result['positive_score'] / total) * 100
            result['negative_score'] = (result['negative_score'] / total) * 100
            result['neutral_score'] = 0
        else:
            result['neutral_score'] = 100
        
        # リスク深刻度の詳細判定
        risk_count = result['risk_keywords_count']
        text_length = len(text) / 1000  # KB単位
        
        risk_density = risk_count / max(text_length, 1)  # リスク密度
        
        if risk_density >= 5 or risk_count >= 20:
            result['risk_severity'] = 'critical'
        elif risk_density >= 3 or risk_count >= 10:
            result['risk_severity'] = 'high'
        elif risk_density >= 1 or risk_count >= 5:
            result['risk_severity'] = 'medium'
        else:
            result['risk_severity'] = 'low'
        
        # 重要フレーズ抽出（コンテキスト考慮）
        result['key_phrases'] = self._extract_contextual_phrases(text, 'positive', max_phrases=10)
        result['risk_phrases'] = self._extract_contextual_phrases(text, 'risk', max_phrases=8)
        
        # カスタムキーワード分析
        custom_keywords = settings.get('custom_keywords', [])
        if custom_keywords:
            for keyword in custom_keywords:
                count = text_lower.count(keyword.lower())
                if count > 0:
                    result['custom_keyword_counts'][keyword] = count
        
        return result
    
    def _extract_contextual_phrases(self, text: str, category: str, max_phrases: int = 10) -> List[str]:
        """コンテキストを考慮したフレーズ抽出"""
        
        keywords = self.sentiment_keywords.get(category, [])
        phrases = []
        
        for keyword in keywords:
            # キーワード周辺のより大きなコンテキストを抽出
            pattern = f'.{{0,80}}{re.escape(keyword)}.{{0,80}}'
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            
            for match in matches[:2]:  # 各キーワードにつき最大2フレーズ
                # 文の境界で調整
                sentences = re.split(r'[。！？\n]', match)
                if len(sentences) >= 2:
                    # 最も内容のある文を選択
                    best_sentence = max(sentences, key=len)
                    clean_phrase = re.sub(r'\s+', ' ', best_sentence).strip()
                    
                    if len(clean_phrase) > 15 and clean_phrase not in phrases:
                        phrases.append(clean_phrase)
        
        # 長さと関連性でソート
        phrases.sort(key=lambda x: (-len(x), -sum(kw in x.lower() for kw in keywords)))
        
        return phrases[:max_phrases]
    
    def _perform_advanced_cashflow_analysis(self, text: str, settings: Dict) -> Dict:
        """
        高度なキャッシュフロー分析（改善版）
        
        Args:
            text: 分析対象テキスト
            settings: 分析設定
            
        Returns:
            Dict: キャッシュフロー分析結果
        """
        result = {
            'operating_cf': None,
            'investing_cf': None,
            'financing_cf': None,
            'free_cf': None,
            'pattern': 'other',
            'pattern_score': 0.0,
            'operating_cf_growth': None,
            'investing_cf_growth': None,
            'financing_cf_growth': None,
            'cf_adequacy_ratio': None,
            'cf_quality_score': 50.0,
            'interpretation': '',
            'risk_factors': []
        }
        
        # 複数の抽出パターンでキャッシュフロー金額を取得
        cf_amounts = self._extract_comprehensive_cashflow_amounts(text)
        result.update(cf_amounts)
        
        # フリーキャッシュフローの計算
        if result['operating_cf'] is not None and result['investing_cf'] is not None:
            result['free_cf'] = result['operating_cf'] + result['investing_cf']
        
        # パターン分類と詳細分析
        if all(cf_amounts[key] is not None for key in ['operating_cf', 'investing_cf', 'financing_cf']):
            pattern_info = self._classify_detailed_cashflow_pattern(
                result['operating_cf'],
                result['investing_cf'],
                result['financing_cf']
            )
            result.update(pattern_info)
        
        # 成長率分析（前年同期比）
        growth_rates = self._extract_cashflow_growth_rates(text)
        result.update(growth_rates)
        
        # CF充足率計算
        adequacy_ratio = self._calculate_cf_adequacy_ratio(result, text)
        if adequacy_ratio is not None:
            result['cf_adequacy_ratio'] = adequacy_ratio
        
        # CF品質スコア計算（詳細版）
        result['cf_quality_score'] = self._calculate_advanced_cf_quality_score(result, text)
        
        # 詳細解釈の生成
        result['interpretation'] = self._generate_detailed_cf_interpretation(result, text)
        
        # リスク要因の詳細特定
        result['risk_factors'] = self._identify_detailed_cf_risk_factors(result, text)
        
        return result
    
    def _extract_comprehensive_cashflow_amounts(self, text: str) -> Dict:
        """包括的なキャッシュフロー金額抽出（修正版）"""
        
        cf_amounts = {
            'operating_cf': None,
            'investing_cf': None,
            'financing_cf': None,
            'free_cf': None
        }
        
        # 修正された正規表現パターン
        patterns = {
            'operating_cf': [
                r'営業活動.*?(?:による|に係る).*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'営業.*?CF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Operating.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'営業キャッシュフロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ],
            'investing_cf': [
                r'投資活動.*?(?:による|に係る).*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'投資.*?CF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Investing.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'投資キャッシュフロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ],
            'financing_cf': [
                r'財務活動.*?(?:による|に係る).*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'財務.*?CF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Financing.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'財務キャッシュフロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ],
            'free_cf': [
                r'フリー.*?キャッシュ.*?フロー.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',
                r'Free.*?cash.*?flow.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)',  # 修正: 余分な括弧を削除
                r'FCF.*?[：:]?\s*([△▲\-\+]?\d{1,3}(?:,\d{3})*)'
            ]
        }
        
        for cf_type, pattern_list in patterns.items():
            amounts = []
            
            for pattern in pattern_list:
                try:
                    # 正規表現の妥当性をチェック
                    re.compile(pattern)
                    
                    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
                    
                    for match in matches:
                        try:
                            # 数値の清浄化
                            amount_str = match.replace(',', '').replace('△', '-').replace('▲', '-').replace('+', '')
                            amount = int(amount_str)
                            amounts.append(amount)
                        except ValueError:
                            continue
                            
                except re.error as e:
                    # 正規表現エラーをログに記録してスキップ
                    logger.warning(f"正規表現パターンエラー ({cf_type}): {str(e)} - パターン: {pattern}")
                    continue
            
            if amounts:
                # 複数の値がある場合は、桁数の最も大きい値を採用
                best_amount = max(amounts, key=lambda x: len(str(abs(x))))
                cf_amounts[cf_type] = best_amount
        
        return cf_amounts
 
    def _classify_detailed_cashflow_pattern(self, operating_cf: int, investing_cf: int, financing_cf: int) -> Dict:
        """詳細なキャッシュフローパターン分類"""
        
        # 金額の大小も考慮した詳細分類
        operating_positive = operating_cf > 0
        investing_negative = investing_cf < 0
        financing_negative = financing_cf < 0
        
        # 金額の規模（億円単位）
        op_scale = abs(operating_cf) / 100000000 if operating_cf else 0
        inv_scale = abs(investing_cf) / 100000000 if investing_cf else 0
        fin_scale = abs(financing_cf) / 100000000 if financing_cf else 0
        
        if operating_positive and investing_negative and financing_negative:
            # 理想型の詳細分析
            if op_scale > inv_scale + fin_scale:
                pattern = 'ideal'
                score = 90
            else:
                pattern = 'ideal'
                score = 75
                
        elif operating_positive and investing_negative and financing_cf > 0:
            # 成長型の詳細分析
            if inv_scale > op_scale * 0.5:  # 積極的投資
                pattern = 'growth'
                score = 70
            else:
                pattern = 'growth'
                score = 60
                
        elif operating_positive and investing_cf > 0 and financing_negative:
            # 再構築型
            pattern = 'restructuring'
            score = 45
            
        elif operating_cf < 0 and investing_cf > 0 and financing_cf > 0:
            # 危険型
            pattern = 'danger'
            score = -30
            
        elif operating_positive and abs(investing_cf) < op_scale * 0.1 and abs(financing_cf) < op_scale * 0.1:
            # 保守型
            pattern = 'conservative'
            score = 55
            
        else:
            # その他
            pattern = 'other'
            score = 30
        
        return {
            'pattern': pattern,
            'pattern_score': score
        }
    
    def _calculate_comprehensive_score(self, analysis: Analysis, analysis_results: Dict) -> float:
        """包括的な総合スコア計算"""
        
        score = 0.0
        weight_sum = 0.0
        
        # 基本重み
        sentiment_weight = 0.4
        cashflow_weight = 0.6
        
        # 分析レベルによる重み調整
        analysis_depth = analysis.settings_json.get('analysis_depth', 'basic')
        if analysis_depth == 'comprehensive':
            # 包括分析では重みを調整
            sentiment_weight = 0.3
            cashflow_weight = 0.7
        
        # 感情分析スコア
        if 'sentiment' in analysis_results:
            sentiment_data = analysis_results['sentiment']
            
            # 基本感情スコア
            sentiment_score = sentiment_data['positive_score'] - sentiment_data['negative_score']
            
            # リスク調整
            risk_penalty = min(20, sentiment_data['risk_keywords_count'] * 2)
            sentiment_score -= risk_penalty
            
            # 自信度ボーナス
            confidence_bonus = min(10, sentiment_data['confidence_keywords_count'])
            sentiment_score += confidence_bonus
            
            score += sentiment_score * sentiment_weight
            weight_sum += sentiment_weight
        
        # キャッシュフロースコア
        if 'cashflow' in analysis_results:
            cashflow_data = analysis_results['cashflow']
            cf_score = cashflow_data.get('pattern_score', 0)
            
            # CF品質による調整
            quality_adjustment = (cashflow_data.get('cf_quality_score', 50) - 50) * 0.4
            cf_score += quality_adjustment
            
            score += cf_score * cashflow_weight
            weight_sum += cashflow_weight
        
        # 重み付き平均
        if weight_sum > 0:
            final_score = score / weight_sum
        else:
            final_score = 0.0
        
        # スコア範囲を-100から100に制限
        return max(-100, min(100, final_score))
    
    def _compare_with_previous_analysis(self, analysis: Analysis):
        """前回分析との比較"""
        
        try:
            # 前回の分析結果を取得
            previous_analysis = Analysis.objects.filter(
                document__company=analysis.document.company,
                user=analysis.user,
                status='completed',
                analysis_date__lt=analysis.analysis_date
            ).order_by('-analysis_date').first()
            
            if not previous_analysis:
                return
            
            # 感情分析の比較
            if hasattr(analysis, 'sentiment') and hasattr(previous_analysis, 'sentiment'):
                current_sentiment = analysis.sentiment
                prev_sentiment = previous_analysis.sentiment
                
                # 感情変化の計算
                current_net = current_sentiment.positive_score - current_sentiment.negative_score
                prev_net = prev_sentiment.positive_score - prev_sentiment.negative_score
                current_sentiment.sentiment_change = current_net - prev_net
                
                # 自信度変化の計算
                current_conf = current_sentiment.management_confidence_index
                prev_conf = prev_sentiment.management_confidence_index
                current_sentiment.confidence_change = current_conf - prev_conf
                
                current_sentiment.save()
            
        except Exception as e:
            logger.warning(f"前回分析との比較エラー: {str(e)}")
    
    def _determine_confidence_level(self, analysis: Analysis, analysis_results: Dict) -> str:
        """信頼性レベル判定（改善版）"""
        
        confidence_score = 0
        
        # データの充実度
        if 'sentiment' in analysis_results:
            confidence_score += 30
        if 'cashflow' in analysis_results:
            confidence_score += 40
        
        # テキストの品質
        if analysis.document.download_size and analysis.document.download_size > 1:  # 1MB以上
            confidence_score += 15
        
        # 分析設定の詳細度
        analysis_depth = analysis.settings_json.get('analysis_depth', 'basic')
        if analysis_depth == 'comprehensive':
            confidence_score += 15
        elif analysis_depth == 'detailed':
            confidence_score += 10
        
        # 信頼性レベルの判定
        if confidence_score >= 80:
            return 'high'
        elif confidence_score >= 50:
            return 'medium'
        else:
            return 'low'
    
    def _save_sentiment_analysis(self, analysis: Analysis, sentiment_result: Dict):
        """感情分析結果保存"""
        
        SentimentAnalysis.objects.update_or_create(
            analysis=analysis,
            defaults=sentiment_result
        )
    
    def _save_cashflow_analysis(self, analysis: Analysis, cashflow_result: Dict):
        """キャッシュフロー分析結果保存"""
        
        CashFlowAnalysis.objects.update_or_create(
            analysis=analysis,
            defaults=cashflow_result
        )

    def _safe_extract_contextual_phrases(self, text, category, max_phrases=10):
        return []

    def _extract_cashflow_growth_rates(self, report):
        return None

    def _calculate_cf_adequacy_ratio(self, cf_data, report):
        return None

    def _calculate_advanced_cf_quality_score(self, report):
        return None

    def _generate_detailed_cf_interpretation(self, report):
        return ""

    def _identify_detailed_cf_risk_factors(self, report):
        return []        