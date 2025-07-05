# earnings_analysis/services/sentiment_analyzer.py （数値処理改善版）
import re
import csv
import os
import threading
import time
import logging
from typing import Dict, List, Tuple, Any
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from .xbrl_extractor import EDINETXBRLService

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """辞書ベース感情分析エンジン"""
    
    def __init__(self):
        self.sentiment_dict = {}
        self.load_sentiment_dictionary()
        
    def load_sentiment_dictionary(self):
        """感情極性辞書の読み込み（エラーハンドリング強化版）"""
        try:
            dict_path = getattr(settings, 'SENTIMENT_DICT_PATH', 
                            os.path.join(settings.BASE_DIR, 'data', 'sentiment_dict.csv'))
            
            if not os.path.exists(dict_path):
                logger.warning(f"感情辞書が見つかりません: {dict_path}")
                self._load_default_dictionary()
                return
            
            logger.info(f"感情辞書読み込み開始: {dict_path}")
            
            with open(dict_path, 'r', encoding='utf-8') as f:
                # まず1行目をチェック
                first_line = f.readline().strip()
                if not first_line.startswith('word,score'):
                    logger.error(f"CSVヘッダーが正しくありません: {first_line}")
                    self._load_default_dictionary()
                    return
                
                # ファイルの先頭に戻る
                f.seek(0)
                
                reader = csv.DictReader(f)
                loaded_count = 0
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # データの検証
                        if 'word' not in row or 'score' not in row:
                            logger.warning(f"感情辞書の{row_num}行目: 必要なカラムがありません - {row}")
                            continue
                        
                        word = row['word'].strip()
                        
                        # 空行やコメント行をスキップ
                        if not word or word.startswith('#'):
                            continue
                        
                        # スコアの変換
                        score_str = row['score'].strip()
                        
                        # 全角マイナス記号を半角に変換
                        score_str = score_str.replace('−', '-')
                        score_str = score_str.replace('－', '-')
                        
                        score = float(score_str)
                        
                        # スコア範囲の検証
                        if not (-1.0 <= score <= 1.0):
                            logger.warning(f"感情辞書の{row_num}行目: スコアが範囲外 ({score}): {word}")
                            continue
                        
                        self.sentiment_dict[word] = score
                        loaded_count += 1
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"感情辞書の{row_num}行目でエラー: {row} - {e}")
                        continue
                        
            logger.info(f"感情辞書読み込み完了: {loaded_count}語")
            
            if loaded_count == 0:
                logger.warning("感情辞書から有効な語彙が読み込めませんでした。デフォルト辞書を使用します。")
                self._load_default_dictionary()
            
        except Exception as e:
            logger.error(f"感情辞書読み込みエラー: {e}")
            self._load_default_dictionary()


    def _load_default_dictionary(self):
        """デフォルト感情辞書（数値パターン含む）"""
        default_dict = {
            # 強いポジティブ語（財務）
            '増収': 0.8, '増益': 0.8, '黒字転換': 0.9, '過去最高': 0.9, '最高益': 0.9,
            '大幅増益': 0.9, '増配': 0.7, '復配': 0.8, '業績好調': 0.8,
            
            # ポジティブ語（成長・改善）
            '成長': 0.8, '増加': 0.6, '改善': 0.7, '好調': 0.8, '順調': 0.7,
            '拡大': 0.6, '向上': 0.7, '安定': 0.5, '堅調': 0.6, '良好': 0.7,
            '回復': 0.6, '達成': 0.7, '成功': 0.8, '効果': 0.5, '利益': 0.6,
            '売上': 0.4, '収益': 0.5, '黒字': 0.7, '好転': 0.7, '伸長': 0.6,
            
            # 数値と組み合わさるポジティブ語
            '上昇': 0.6, '増': 0.5, '高': 0.4, '超過': 0.5, '上回': 0.6,
            '上振れ': 0.6, '改善': 0.7, '向上': 0.7,
            
            # ポジティブ語（ビジネス）
            '競争力': 0.6, '優位性': 0.7, '強み': 0.6, '機会': 0.5, '展開': 0.5,
            '革新': 0.7, 'イノベーション': 0.7, '技術力': 0.6, '品質': 0.5,
            '効率': 0.5, '生産性': 0.6, '収益性': 0.6, '将来性': 0.7,
            
            # 強いネガティブ語（財務）
            '減収': -0.7, '減益': -0.8, '赤字': -0.8, '損失': -0.7, '赤字転落': -0.9,
            '大幅減益': -0.9, '減配': -0.6, '無配': -0.8, '業績悪化': -0.8,
            
            # 数値と組み合わさるネガティブ語
            '下落': -0.6, '減': -0.5, '低': -0.4, '割れ': -0.5, '下回': -0.6,
            '下振れ': -0.6, '悪化': -0.8, '低下': -0.6,
            
            # ネガティブ語（リスク・問題）
            'リスク': -0.6, '課題': -0.4, '懸念': -0.6, '困難': -0.7, '問題': -0.6,
            '減少': -0.6, '不調': -0.7, '停滞': -0.5, '不安': -0.6, '影響': -0.3, 
            '圧迫': -0.6, '縮小': -0.5, '厳しい': -0.7, '困窮': -0.8, '不振': -0.7, 
            '苦戦': -0.7,
            
            # パーセンテージ関連の語彙
            '％以上': 0.3, '％超': 0.3, '％台': 0.0, '％程度': 0.0, '％前後': 0.0,
            '％未満': -0.2, '％割れ': -0.4, '％下落': -0.6, '％上昇': 0.6,
            '倍以上': 0.6, '倍超': 0.6, '倍未満': -0.2, '倍増': 0.8, '半減': -0.7,
            
            # 時間・期間関連
            '年間': 0.0, 'ヶ月': 0.0, '四半期': 0.0, '期': 0.0,
            '年ぶり': 0.3, '年連続': 0.4, '継続': 0.2,
            
            # 中立語
            '維持': 0.1, '推移': 0.0, '状況': 0.0, '環境': 0.0,
            '計画': 0.1, '予定': 0.1, '見込み': 0.1, '予想': 0.0,
        }
        self.sentiment_dict = default_dict
        logger.info(f"デフォルト感情辞書を使用: {len(self.sentiment_dict)}語")
    
    def _preprocess_text(self, text: str) -> str:
        """テキスト前処理（数値保持改善版）"""
        # HTMLタグ除去
        text = re.sub(r'<[^>]+>', '', text)
        
        # 特殊文字の正規化
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[\r\n\t]+', ' ', text)
        
        # 重要な数値パターンを保護（一時的にプレースホルダーに置換）
        protected_patterns = []
        
        # 1. パーセンテージ（％、%、パーセント）
        percentage_pattern = r'(\d+(?:\.\d+)?)\s*(?:％|%|パーセント)'
        for i, match in enumerate(re.finditer(percentage_pattern, text)):
            placeholder = f"__PERCENTAGE_{i}__"
            protected_patterns.append((placeholder, match.group()))
            text = text.replace(match.group(), placeholder)
        
        # 2. 倍率表現
        ratio_pattern = r'(\d+(?:\.\d+)?)\s*(?:倍|x)'
        for i, match in enumerate(re.finditer(ratio_pattern, text)):
            placeholder = f"__RATIO_{i}__"
            protected_patterns.append((placeholder, match.group()))
            text = text.replace(match.group(), placeholder)
        
        # 3. 年数・期間
        period_pattern = r'(\d+)\s*(?:年|ヶ月|か月|四半期|期|日)'
        for i, match in enumerate(re.finditer(period_pattern, text)):
            placeholder = f"__PERIOD_{i}__"
            protected_patterns.append((placeholder, match.group()))
            text = text.replace(match.group(), placeholder)
        
        # 4. 重要な指標（売上高、利益率など）
        metrics_pattern = r'(\d+(?:\.\d+)?)\s*(?:億円|百万円|千円|円|ドル|ユーロ)(?=\s|$|、|。)'
        for i, match in enumerate(re.finditer(metrics_pattern, text)):
            # 金額は数値部分のみ保持（単位は除去）
            number_part = re.match(r'(\d+(?:\.\d+)?)', match.group()).group(1)
            if float(number_part) >= 100:  # 100以上の場合のみ
                placeholder = f"__AMOUNT_{i}__"
                protected_patterns.append((placeholder, f"{number_part}億円" if "億" in match.group() else f"{number_part}百万円"))
                text = text.replace(match.group(), placeholder)
        
        # 5. 順位・ランキング
        ranking_pattern = r'(?:第|)(\d+)(?:位|番目|等)'
        for i, match in enumerate(re.finditer(ranking_pattern, text)):
            placeholder = f"__RANKING_{i}__"
            protected_patterns.append((placeholder, match.group()))
            text = text.replace(match.group(), placeholder)
        
        # 残りの大きな数値（金額表記等）をNUMBERに置換
        # コンマ区切りの大きな数値
        text = re.sub(r'\d{1,3}(?:,\d{3})+', 'NUMBER', text)
        
        # 長い数値（6桁以上）
        text = re.sub(r'\b\d{6,}\b', 'NUMBER', text)
        
        # 小数点を含む大きな数値（ただし保護されたもの以外）
        text = re.sub(r'\b\d{3,}\.\d+\b', 'NUMBER', text)
        
        # 保護したパターンを復元
        for placeholder, original in protected_patterns:
            text = text.replace(placeholder, original)
        
        # 不要な文字除去
        text = re.sub(r'[【】「」（）\(\)\[\]〔〕]', '', text)
        
        # 日付表記の簡略化（年月日の組み合わせのみ）
        text = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', 'DATE', text)
        
        return text.strip()
    
    def _simple_tokenize(self, text: str) -> List[str]:
        """簡易形態素解析（数値パターン対応）"""
        words = []
        
        # 数値パターンの語彙を追加で識別
        numeric_patterns = [
            r'\d+(?:\.\d+)?％(?:以上|超|台|程度|前後|未満|割れ|下落|上昇)',
            r'\d+(?:\.\d+)?倍(?:以上|超|未満|増)',
            r'\d+年(?:ぶり|連続|間|前)',
            r'\d+ヶ月(?:ぶり|連続|間|前)',
            r'\d+四半期(?:ぶり|連続)',
            r'第\d+(?:位|四半期|期)',
        ]
        
        # 数値パターンを先に抽出
        for pattern in numeric_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                numeric_phrase = match.group()
                words.append(numeric_phrase)
        
        # 辞書の語彙でマッチング（長い語を優先）
        sorted_words = sorted(self.sentiment_dict.keys(), key=len, reverse=True)
        
        # 処理済み位置を記録
        processed_positions = set()
        
        for word in sorted_words:
            if word in text:
                positions = []
                start = 0
                while True:
                    pos = text.find(word, start)
                    if pos == -1:
                        break
                    
                    # 既に処理済みの位置と重複していないかチェック
                    if not any(pos <= p < pos + len(word) for p in processed_positions):
                        positions.append(pos)
                        for i in range(pos, pos + len(word)):
                            processed_positions.add(i)
                    
                    start = pos + 1
                
                words.extend([word] * len(positions))
        
        # 英数字の抽出
        english_words = re.findall(r'[a-zA-Z]+', text)
        words.extend([w.lower() for w in english_words if len(w) > 2])
        
        return words
    
    def analyze_text(self, text: str, session_id: str = None) -> Dict[str, Any]:
        """単一テキストの感情分析実行（数値考慮版）"""
        try:
            # テキスト前処理
            cleaned_text = self._preprocess_text(text)
            
            # 形態素解析
            words = self._simple_tokenize(cleaned_text)
            
            # 数値パターンのスコア調整
            numeric_sentiment_boost = self._analyze_numeric_patterns(cleaned_text)
            
            # 感情スコア計算
            sentiment_scores = []
            keyword_scores = {'positive': [], 'negative': []}
            word_counts = {}
            
            for word in words:
                if word in self.sentiment_dict:
                    score = self.sentiment_dict[word]
                    sentiment_scores.append(score)
                    
                    # 単語の出現回数をカウント
                    word_counts[word] = word_counts.get(word, 0) + 1
                    
                    if score > 0.3:
                        keyword_scores['positive'].append({
                            'word': word, 
                            'score': score, 
                            'count': word_counts[word]
                        })
                    elif score < -0.3:
                        keyword_scores['negative'].append({
                            'word': word, 
                            'score': score, 
                            'count': word_counts[word]
                        })
            
            # 数値パターンによるスコア調整を追加
            sentiment_scores.extend(numeric_sentiment_boost)
            
            # 全体スコア計算
            if sentiment_scores:
                overall_score = sum(sentiment_scores) / len(sentiment_scores)
                # 重み付けスコア（強い感情語により重みを付ける）
                weighted_score = sum(score * abs(score) for score in sentiment_scores) / len(sentiment_scores)
                overall_score = (overall_score + weighted_score) / 2
                overall_score = max(-1.0, min(1.0, overall_score))
            else:
                overall_score = 0.0
            
            # 感情ラベル決定
            if overall_score > 0.2:
                sentiment_label = 'positive'
            elif overall_score < -0.2:
                sentiment_label = 'negative'
            else:
                sentiment_label = 'neutral'
            
            # 文章レベルの分析
            sentences = self._split_sentences(cleaned_text)
            sentence_analysis = []
            
            for sentence in sentences[:10]:
                sent_words = self._simple_tokenize(sentence)
                sent_numeric_boost = self._analyze_numeric_patterns(sentence)
                sent_scores = [self.sentiment_dict.get(w, 0) for w in sent_words if w in self.sentiment_dict]
                sent_scores.extend(sent_numeric_boost)
                sent_score = sum(sent_scores) / len(sent_scores) if sent_scores else 0
                
                if abs(sent_score) > 0.3:
                    sentence_analysis.append({
                        'text': sentence[:150],
                        'score': round(sent_score, 2),
                        'keywords': [w for w in sent_words if w in self.sentiment_dict],
                        'has_numbers': bool(re.search(r'\d+(?:\.\d+)?[％%倍年ヶ月]', sentence))
                    })
            
            # 統計情報
            total_sentences = len(sentences)
            positive_sentences = len([s for s in sentences if self._sentence_score(s) > 0.2])
            negative_sentences = len([s for s in sentences if self._sentence_score(s) < -0.2])
            neutral_sentences = total_sentences - positive_sentences - negative_sentences
            
            # キーワードの重複除去とスコア計算
            unique_positive = {}
            for kw in keyword_scores['positive']:
                word = kw['word']
                if word not in unique_positive:
                    unique_positive[word] = kw
                else:
                    unique_positive[word]['count'] += kw['count']
            
            unique_negative = {}
            for kw in keyword_scores['negative']:
                word = kw['word']
                if word not in unique_negative:
                    unique_negative[word] = kw
                else:
                    unique_negative[word]['count'] += kw['count']
            
            return {
                'overall_score': round(overall_score, 3),
                'sentiment_label': sentiment_label,
                'statistics': {
                    'total_sentences': total_sentences,
                    'positive_sentences': positive_sentences,
                    'negative_sentences': negative_sentences,
                    'neutral_sentences': neutral_sentences,
                    'total_words': len(words),
                    'sentiment_words': len([s for s in sentiment_scores if s != 0]),
                    'numeric_patterns_found': len(numeric_sentiment_boost),
                },
                'top_keywords': {
                    'positive': sorted(unique_positive.values(), 
                                     key=lambda x: x['score'] * x['count'], reverse=True)[:5],
                    'negative': sorted(unique_negative.values(), 
                                     key=lambda x: x['score'] * x['count'])[:5],
                },
                'sample_sentences': {
                    'positive': [s for s in sentence_analysis if s['score'] > 0.2][:3],
                    'negative': [s for s in sentence_analysis if s['score'] < -0.2][:3],
                },
                'analysis_metadata': {
                    'analyzed_at': timezone.now().isoformat(),
                    'dictionary_size': len(self.sentiment_dict),
                    'session_id': session_id,
                    'numeric_patterns_applied': len(numeric_sentiment_boost) > 0,
                }
            }
            
        except Exception as e:
            logger.error(f"感情分析エラー: {e}")
            raise Exception(f"感情分析処理中にエラーが発生しました: {str(e)}")
    
    def _analyze_numeric_patterns(self, text: str) -> List[float]:
        """数値パターンに基づく感情スコア調整"""
        scores = []
        
        # パーセンテージパターンの分析
        percentage_patterns = [
            (r'(\d+(?:\.\d+)?)％以上(?:上昇|増加|改善|向上)', 0.6),  # X%以上上昇
            (r'(\d+(?:\.\d+)?)％超(?:上昇|増加|改善|向上)', 0.7),   # X%超上昇
            (r'(\d+(?:\.\d+)?)％(?:下落|減少|悪化|低下)', -0.6),   # X%下落
            (r'(\d+(?:\.\d+)?)％割れ', -0.5),                    # X%割れ
            (r'(\d+(?:\.\d+)?)％台', 0.0),                       # X%台（中立）
        ]
        
        for pattern, base_score in percentage_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    value = float(match.group(1))
                    # 数値の大きさに応じてスコアを調整
                    if value >= 50:
                        adjusted_score = base_score * 1.5  # 50%以上は影響大
                    elif value >= 20:
                        adjusted_score = base_score * 1.2  # 20%以上は影響中
                    elif value >= 10:
                        adjusted_score = base_score        # 10%以上は基準
                    else:
                        adjusted_score = base_score * 0.7  # 10%未満は影響小
                    
                    scores.append(adjusted_score)
                except ValueError:
                    continue
        
        # 倍率パターンの分析
        ratio_patterns = [
            (r'(\d+(?:\.\d+)?)倍(?:以上|超)', 0.7),           # X倍以上
            (r'(\d+(?:\.\d+)?)倍増', 0.8),                   # X倍増
            (r'半減', -0.7),                                  # 半減
            (r'(\d+(?:\.\d+)?)倍未満', -0.3),               # X倍未満
        ]
        
        for pattern, base_score in ratio_patterns:
            if pattern == r'半減':
                if pattern in text:
                    scores.append(base_score)
            else:
                matches = re.finditer(pattern, text)
                for match in matches:
                    try:
                        value = float(match.group(1))
                        if value >= 3:
                            adjusted_score = base_score * 1.3  # 3倍以上は特に良い
                        elif value >= 2:
                            adjusted_score = base_score        # 2倍は基準
                        else:
                            adjusted_score = base_score * 0.8  # 2倍未満は控えめ
                        
                        scores.append(adjusted_score)
                    except ValueError:
                        continue
        
        # 期間パターンの分析
        period_patterns = [
            (r'(\d+)年ぶり', 0.5),    # X年ぶり（久しぶりはポジティブ）
            (r'(\d+)年連続', 0.4),    # X年連続（継続はポジティブ）
            (r'過去(\d+)年', 0.2),    # 過去X年（やや中立）
        ]
        
        for pattern, base_score in period_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    value = float(match.group(1))
                    if value >= 10:
                        adjusted_score = base_score * 1.2  # 10年以上は意味深い
                    elif value >= 5:
                        adjusted_score = base_score        # 5年以上は基準
                    else:
                        adjusted_score = base_score * 0.8  # 5年未満は控えめ
                    
                    scores.append(adjusted_score)
                except ValueError:
                    continue
        
        return scores
    
    def _split_sentences(self, text: str) -> List[str]:
        """文分割（数値を含む文を考慮）"""
        # 日本語の文末記号で分割
        sentences = re.split(r'[。！？\n]', text)
        
        # フィルタリング
        filtered_sentences = []
        for s in sentences:
            s = s.strip()
            # 短すぎる文や数値のみの文を除外
            if len(s) > 15 and not re.match(r'^\s*[\d,\.\s]+\s*$', s):
                filtered_sentences.append(s)
        
        return filtered_sentences
    
    def _sentence_score(self, sentence: str) -> float:
        """文単位の感情スコア（数値パターン考慮）"""
        words = self._simple_tokenize(sentence)
        numeric_boost = self._analyze_numeric_patterns(sentence)
        
        scores = [self.sentiment_dict.get(w, 0) for w in words if w in self.sentiment_dict]
        scores.extend(numeric_boost)
        
        if scores:
            return sum(scores) / max(len(scores), 1)
        return 0

    # analyze_text_sectionsメソッドも同様に更新...
    def analyze_text_sections(self, text_sections: Dict[str, str], session_id: str = None) -> Dict[str, Any]:
        """複数のテキストセクションの感情分析（数値パターン対応）"""
        try:
            all_results = {}
            overall_scores = []
            section_analysis = {}
            
            # セクション別分析
            for section_name, text in text_sections.items():
                if len(text.strip()) < 50:
                    continue
                    
                section_result = self.analyze_text(text, session_id)
                section_analysis[section_name] = section_result
                overall_scores.append(section_result['overall_score'])
            
            # 全体統計の計算
            if overall_scores:
                overall_score = sum(overall_scores) / len(overall_scores)
                overall_score = max(-1.0, min(1.0, overall_score))
            else:
                overall_score = 0.0
            
            # 感情ラベル決定
            if overall_score > 0.2:
                sentiment_label = 'positive'
            elif overall_score < -0.2:
                sentiment_label = 'negative'
            else:
                sentiment_label = 'neutral'
            
            # 統合統計の計算
            total_sentences = sum(r['statistics']['total_sentences'] for r in section_analysis.values())
            total_positive = sum(r['statistics']['positive_sentences'] for r in section_analysis.values())
            total_negative = sum(r['statistics']['negative_sentences'] for r in section_analysis.values())
            total_neutral = total_sentences - total_positive - total_negative
            total_numeric_patterns = sum(r['statistics'].get('numeric_patterns_found', 0) for r in section_analysis.values())
            
            # キーワードの統合
            all_positive_keywords = []
            all_negative_keywords = []
            
            for result in section_analysis.values():
                all_positive_keywords.extend(result['top_keywords']['positive'])
                all_negative_keywords.extend(result['top_keywords']['negative'])
            
            # 重複除去とソート
            unique_positive = {}
            for kw in all_positive_keywords:
                word = kw['word']
                if word not in unique_positive or kw['score'] > unique_positive[word]['score']:
                    unique_positive[word] = kw
            
            unique_negative = {}
            for kw in all_negative_keywords:
                word = kw['word']
                if word not in unique_negative or kw['score'] < unique_negative[word]['score']:
                    unique_negative[word] = kw
            
            top_positive = sorted(unique_positive.values(), key=lambda x: x['score'], reverse=True)[:10]
            top_negative = sorted(unique_negative.values(), key=lambda x: x['score'])[:10]
            
            # サンプル文章の統合
            all_positive_sentences = []
            all_negative_sentences = []
            
            for result in section_analysis.values():
                all_positive_sentences.extend(result['sample_sentences']['positive'])
                all_negative_sentences.extend(result['sample_sentences']['negative'])
            
            # スコア順でソート
            all_positive_sentences.sort(key=lambda x: x['score'], reverse=True)
            all_negative_sentences.sort(key=lambda x: x['score'])
            
            return {
                'overall_score': round(overall_score, 3),
                'sentiment_label': sentiment_label,
                'statistics': {
                    'total_sentences': total_sentences,
                    'positive_sentences': total_positive,
                    'negative_sentences': total_negative,
                    'neutral_sentences': total_neutral,
                    'analyzed_sections': len(section_analysis),
                    'total_words': sum(r['statistics']['total_words'] for r in section_analysis.values()),
                    'sentiment_words': sum(r['statistics']['sentiment_words'] for r in section_analysis.values()),
                    'numeric_patterns_found': total_numeric_patterns,
                },
                'top_keywords': {
                    'positive': top_positive,
                    'negative': top_negative,
                },
                'sample_sentences': {
                    'positive': all_positive_sentences[:5],
                    'negative': all_negative_sentences[:5],
                },
                'section_analysis': section_analysis,
                'analysis_metadata': {
                    'analyzed_at': timezone.now().isoformat(),
                    'dictionary_size': len(self.sentiment_dict),
                    'session_id': session_id,
                    'sections_analyzed': list(text_sections.keys()),
                    'numeric_patterns_applied': total_numeric_patterns > 0,
                }
            }
            
        except Exception as e:
            logger.error(f"セクション分析エラー: {e}")
            raise Exception(f"感情分析処理中にエラーが発生しました: {str(e)}")


class SentimentAnalysisService:
    """感情分析サービス（セッション管理）"""
    
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
        self.xbrl_service = EDINETXBRLService()
    
    def start_analysis(self, document_id: str, force: bool = False, user_ip: str = None) -> Dict[str, Any]:
        """感情分析開始"""
        from ..models import DocumentMetadata, SentimentAnalysisSession
        
        try:
            # 書類存在確認
            document = DocumentMetadata.objects.get(doc_id=document_id, legal_status='1')
            
            # 既存セッション確認（1時間以内）
            if not force:
                recent_session = SentimentAnalysisSession.objects.filter(
                    document=document,
                    processing_status='COMPLETED',
                    created_at__gte=timezone.now() - timedelta(hours=1)
                ).first()
                
                if recent_session:
                    return {
                        'status': 'already_analyzed',
                        'session_id': str(recent_session.session_id),
                        'result': recent_session.analysis_result,
                        'message': '1時間以内に分析済みです'
                    }
            
            # 新規セッション作成
            session = SentimentAnalysisSession.objects.create(
                document=document,
                processing_status='PENDING'
            )
            
            # バックグラウンドで分析開始
            threading.Thread(
                target=self._execute_analysis,
                args=(session.id, user_ip),
                daemon=True
            ).start()
            
            return {
                'status': 'started',
                'session_id': str(session.session_id),
                'message': '感情分析を開始しました'
            }
            
        except DocumentMetadata.DoesNotExist:
            raise Exception('指定された書類が見つかりません')
        except Exception as e:
            logger.error(f"分析開始エラー: {e}")
            raise Exception(f"分析開始に失敗しました: {str(e)}")
    
    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """進行状況取得"""
        from ..models import SentimentAnalysisSession
        
        try:
            session = SentimentAnalysisSession.objects.get(session_id=session_id)
            
            if session.is_expired:
                return {
                    'status': 'expired',
                    'message': 'セッションが期限切れです'
                }
            
            progress = session.progress_percentage
            
            # 詳細進行状況
            if session.processing_status == 'PROCESSING':
                # analysis_resultから詳細進行状況を取得
                result = session.analysis_result or {}
                progress = result.get('progress', 50)
                message = result.get('current_step', '感情スコア計算中...')
            elif session.processing_status == 'COMPLETED':
                progress = 100
                message = '分析完了'
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
            
        except SentimentAnalysisSession.DoesNotExist:
            return {
                'status': 'not_found',
                'message': 'セッションが見つかりません'
            }
    
    def get_result(self, session_id: str) -> Dict[str, Any]:
        """分析結果取得"""
        from ..models import SentimentAnalysisSession
        
        try:
            session = SentimentAnalysisSession.objects.get(session_id=session_id)
            
            if session.is_expired:
                return {
                    'status': 'expired',
                    'message': 'セッションが期限切れです'
                }
            
            if session.processing_status == 'COMPLETED':
                return {
                    'status': 'completed',
                    'result': session.analysis_result
                }
            elif session.processing_status == 'FAILED':
                return {
                    'status': 'failed',
                    'error': session.error_message
                }
            else:
                return {
                    'status': 'processing',
                    'message': '分析中です'
                }
                
        except SentimentAnalysisSession.DoesNotExist:
            return {
                'status': 'not_found',
                'message': 'セッションが見つかりません'
            }
    
    def _execute_analysis(self, session_id: int, user_ip: str = None):
        """分析実行（バックグラウンド処理）"""
        from ..models import SentimentAnalysisSession, SentimentAnalysisHistory
        
        start_time = time.time()
        
        try:
            session = SentimentAnalysisSession.objects.get(id=session_id)
            session.processing_status = 'PROCESSING'
            session.analysis_result = {'progress': 5, 'current_step': '書類情報確認中...'}
            session.save()
            
            # XBRLテキスト取得
            session.analysis_result = {'progress': 15, 'current_step': 'XBRLファイル取得中...'}
            session.save()
            
            xbrl_text_sections = self.xbrl_service.get_xbrl_text_from_document(session.document)
            
            if not xbrl_text_sections:
                # XBRLが取得できない場合は基本情報を使用
                session.analysis_result = {'progress': 25, 'current_step': '基本情報を使用して分析中...'}
                session.save()
                
                document_text = self._extract_basic_document_text(session.document)
                result = self.analyzer.analyze_text(document_text, str(session.session_id))
            else:
                # XBRLテキストを分析
                session.analysis_result = {'progress': 40, 'current_step': 'XBRLテキスト前処理中...'}
                session.save()
                
                session.analysis_result = {'progress': 60, 'current_step': 'セクション別感情分析実行中...'}
                session.save()
                
                result = self.analyzer.analyze_text_sections(xbrl_text_sections, str(session.session_id))
            
            session.analysis_result = {'progress': 90, 'current_step': '結果保存中...'}
            session.save()
            
            # セッション更新
            session.overall_score = result['overall_score']
            session.sentiment_label = result['sentiment_label']
            session.analysis_result = result
            session.processing_status = 'COMPLETED'
            session.save()
            
            # 履歴保存
            analysis_duration = time.time() - start_time
            SentimentAnalysisHistory.objects.create(
                document=session.document,
                overall_score=result['overall_score'],
                sentiment_label=result['sentiment_label'],
                user_ip=user_ip,
                analysis_duration=analysis_duration
            )
            
            logger.info(f"感情分析完了: {session.session_id} ({analysis_duration:.2f}秒)")
            
        except Exception as e:
            logger.error(f"感情分析エラー: {session_id} - {e}")
            
            try:
                session = SentimentAnalysisSession.objects.get(id=session_id)
                session.processing_status = 'FAILED'
                session.error_message = str(e)
                session.save()
            except:
                pass
    
    def _extract_basic_document_text(self, document) -> str:
        """基本的な書類情報からテキスト抽出"""
        text = f"""
        {document.company_name}
        {document.doc_description}
        
        提出日: {document.submit_date_time}
        期間: {document.period_start} から {document.period_end}
        
        この書類は{document.company_name}により提出された{document.doc_description}です。
        """
        
        # 基本的なサンプルテキスト（実際のXBRLが取得できない場合）
        sample_text = """
        当社の業績は前年同期と比較して増収増益となりました。売上高は順調に増加しており、
        主力事業の好調な推移により収益性が向上しています。新規事業の展開も順調で、
        市場における競争力の強化が図られています。
        一方で、原材料費の上昇やエネルギーコストの増加により、一部セグメントでは
        収益圧迫要因も存在します。為替変動リスクや地政学的リスクなど、
        事業環境には不確実性も残っています。
        今後も継続的な業務改善と効率化を推進し、安定した成長を目指してまいります。
        """
        
        return text + sample_text
    
    def cleanup_expired_sessions(self) -> int:
        """期限切れセッションのクリーンアップ"""
        from ..models import SentimentAnalysisSession
        
        try:
            expired_count = SentimentAnalysisSession.objects.filter(
                expires_at__lt=timezone.now()
            ).delete()[0]
            
            logger.info(f"期限切れセッション削除: {expired_count}件")
            return expired_count
            
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")
            return 0