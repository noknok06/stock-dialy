"""DisclosureSync（開示インジケーター更新・イベント生成・通知ファンアウト）のテスト"""
import pytest
from datetime import date, datetime, timedelta, timezone as dt_timezone

from stockdiary.models import StockDiary, NotificationLog
from earnings_analysis.models import DocumentMetadata, DisclosureEvent
from earnings_analysis.services.disclosure_sync import (
    update_diary_disclosure_status,
    fan_out_disclosure_notifications,
)

pytestmark = pytest.mark.django_db(transaction=True)


def make_document(securities_code='72030', doc_id='S100TEST', file_date=None,
                  doc_type_code='120', **overrides):
    """DocumentMetadata のテストデータ生成"""
    file_date = file_date or date.today()
    defaults = dict(
        doc_id=doc_id,
        edinet_code='E02144',
        securities_code=securities_code,
        company_name='テスト株式会社',
        ordinance_code='010',
        form_code='030000',
        doc_type_code=doc_type_code,
        submit_date_time=datetime.combine(
            file_date, datetime.min.time(), tzinfo=dt_timezone.utc
        ),
        file_date=file_date,
        doc_description='テスト書類',
        legal_status='1',
        withdrawal_status='0',
    )
    defaults.update(overrides)
    return DocumentMetadata.objects.create(**defaults)


class TestDiaryDisclosureUpdate:
    """Stage 1a: StockDiary の開示フィールド更新"""

    def test_latest_disclosure_updated(self, sample_diary):
        make_document(securities_code='72030', file_date=date.today())
        updated = update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert updated == 1
        assert sample_diary.latest_disclosure_date == date.today()
        assert sample_diary.latest_disclosure_doc_type_name == '有価証券報告書'

    def test_no_change_no_update(self, sample_diary):
        make_document(securities_code='72030', file_date=date.today())
        update_diary_disclosure_status()
        # 2回目は変更なし → 更新0件
        assert update_diary_disclosure_status() == 0

    def test_multiple_diaries_same_symbol_all_updated(self, sample_diary, another_user):
        """同一銘柄を複数ユーザーが記録していても全日記が更新される"""
        other = StockDiary.objects.create(
            user=another_user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        make_document(securities_code='72030', file_date=date.today())
        assert update_diary_disclosure_status() == 2
        other.refresh_from_db()
        assert other.latest_disclosure_date == date.today()

    def test_latest_doc_wins(self, sample_diary):
        """複数書類がある場合は file_date が最新のものを採用"""
        make_document(doc_id='S100OLD1', file_date=date.today() - timedelta(days=3),
                      doc_type_code='120')
        make_document(doc_id='S100NEW1', file_date=date.today(), doc_type_code='160')
        update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_doc_type_name == '半期報告書'

    def test_unimportant_doc_type_does_not_update(self, sample_diary):
        """有報・半報以外（訂正類・臨報等）は表示フィールドを更新しない"""
        make_document(doc_id='S100AMD1', doc_type_code='130')  # 訂正有価証券報告書
        make_document(doc_id='S100EXT1', doc_type_code='180')  # 臨時報告書
        update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_date is None

    def test_stale_unimportant_value_reset(self, sample_diary):
        """過去に非重要種別が乗っていた場合、重要開示がなければ None に戻る"""
        sample_diary.latest_disclosure_date = date.today() - timedelta(days=2)
        sample_diary.latest_disclosure_doc_type_name = '臨時報告書'
        sample_diary.save(update_fields=[
            'latest_disclosure_date', 'latest_disclosure_doc_type_name'
        ])
        make_document(doc_type_code='180', file_date=date.today())
        update_diary_disclosure_status()
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_date is None
        assert sample_diary.latest_disclosure_doc_type_name == ''

    def test_non_japanese_symbol_ignored(self, user):
        diary = StockDiary.objects.create(user=user, stock_symbol='AAPL', stock_name='Apple')
        make_document(securities_code='AAPL0')
        update_diary_disclosure_status()
        diary.refresh_from_db()
        assert diary.latest_disclosure_date is None


class TestDisclosureEvents:
    """Stage 1b: 新規開示のイベント化"""

    def test_event_created_for_notify_type(self, sample_diary):
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        event = DisclosureEvent.objects.get()
        assert event.securities_code == '72030'
        assert event.doc_type_name == '有価証券報告書'

    def test_no_event_for_non_notify_type(self, sample_diary):
        """訂正書類など通知対象外の種別はイベント化しない"""
        make_document(doc_type_code='130', file_date=date.today())  # 訂正有価証券報告書
        update_diary_disclosure_status()
        assert DisclosureEvent.objects.count() == 0

    def test_no_event_for_old_disclosure(self, sample_diary):
        """EVENT_MAX_AGE_DAYS より古い開示はイベント化しない（初回実行の過去分流入防止）"""
        make_document(doc_type_code='120', file_date=date.today() - timedelta(days=30))
        update_diary_disclosure_status()
        assert DisclosureEvent.objects.count() == 0
        # 日記の表示フィールドは更新される（イベント化と表示は独立）
        sample_diary.refresh_from_db()
        assert sample_diary.latest_disclosure_date is not None

    def test_rerun_does_not_duplicate_event(self, sample_diary):
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        update_diary_disclosure_status()
        assert DisclosureEvent.objects.count() == 1


class TestNotificationFanOut:
    """Stage 2: アプリ内通知のファンアウト"""

    def test_notification_created_per_user(self, sample_diary, another_user):
        StockDiary.objects.create(
            user=another_user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()

        assert NotificationLog.objects.count() == 2
        log = NotificationLog.objects.get(user=sample_diary.user)
        assert 'トヨタ自動車' in log.title
        assert '有価証券報告書' in log.message
        assert log.url == f'/stockdiary/{sample_diary.id}/'
        assert log.is_read is False

    def test_one_notification_per_user_with_duplicate_diaries(self, sample_diary):
        """同一銘柄の日記が複数あってもユーザーへの通知は1通"""
        StockDiary.objects.create(
            user=sample_diary.user, stock_symbol='7203', stock_name='トヨタ自動車(2冊目)'
        )
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        assert NotificationLog.objects.filter(user=sample_diary.user).count() == 1

    def test_excluded_diary_not_notified(self, sample_diary):
        sample_diary.is_excluded = True
        sample_diary.save(update_fields=['is_excluded'])
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        assert NotificationLog.objects.count() == 0

    def test_rerun_does_not_duplicate_notification(self, sample_diary):
        make_document(doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        # イベント再ファンアウトでも一意制約 + ignore_conflicts で重複しない
        events = list(DisclosureEvent.objects.all())
        fan_out_disclosure_notifications(events)
        assert NotificationLog.objects.count() == 1

    def test_unrelated_user_not_notified(self, sample_diary, another_user):
        StockDiary.objects.create(
            user=another_user, stock_symbol='9984', stock_name='ソフトバンクグループ'
        )
        make_document(securities_code='72030', doc_type_code='120', file_date=date.today())
        update_diary_disclosure_status()
        assert NotificationLog.objects.filter(user=another_user).count() == 0


class TestAutoXBRLAnalysis:
    """新規開示イベントの XBRL 財務分析自動実行"""

    def _make_event(self, doc):
        from earnings_analysis.models import DisclosureEvent
        return DisclosureEvent.objects.create(
            securities_code=doc.securities_code,
            doc_id=doc.doc_id,
            file_date=doc.file_date,
            doc_type_code=doc.doc_type_code,
            doc_type_name='有価証券報告書',
        )

    def test_task_runs_analysis_for_xbrl_document(self, monkeypatch):
        from earnings_analysis import tasks

        doc = make_document(doc_type_code='120', xbrl_flag=True)
        event = self._make_event(doc)

        analyzed = []
        sentiment_run = []
        monkeypatch.setattr(
            'earnings_analysis.services.xbrl_analysis_service.XBRLAnalysisService.analyze_document',
            lambda self, d: analyzed.append(d.doc_id) or {'ok': True},
        )
        monkeypatch.setattr(
            'earnings_analysis.services.sentiment_analyzer.SentimentAnalysisService.run_lexicon_analysis',
            lambda self, d: sentiment_run.append(d.doc_id) or True,
        )
        tasks.auto_analyze_disclosure_task(event.id)
        assert analyzed == [doc.doc_id]
        assert sentiment_run == [doc.doc_id]

    def test_task_skips_without_xbrl(self, monkeypatch):
        from earnings_analysis import tasks

        doc = make_document(doc_type_code='120', xbrl_flag=False)
        event = self._make_event(doc)

        def _fail(self, d):
            raise AssertionError('XBRLなし書類で分析が呼ばれた')
        monkeypatch.setattr(
            'earnings_analysis.services.xbrl_analysis_service.XBRLAnalysisService.analyze_document',
            _fail,
        )
        tasks.auto_analyze_disclosure_task(event.id)

    def test_task_skips_when_already_analyzed(self, monkeypatch):
        from earnings_analysis import tasks
        from earnings_analysis.models import CompanyFinancialData

        doc = make_document(doc_type_code='120', xbrl_flag=True)
        event = self._make_event(doc)
        CompanyFinancialData.objects.create(document=doc, period_type='FY')

        def _fail(self, d):
            raise AssertionError('分析済み書類で再分析が呼ばれた')
        monkeypatch.setattr(
            'earnings_analysis.services.xbrl_analysis_service.XBRLAnalysisService.analyze_document',
            _fail,
        )
        monkeypatch.setattr(
            'earnings_analysis.services.sentiment_analyzer.SentimentAnalysisService.run_lexicon_analysis',
            lambda self, d: True,
        )
        tasks.auto_analyze_disclosure_task(event.id)

    def test_sync_queues_task_for_new_events(self, sample_diary, monkeypatch):
        """update_diary_disclosure_status が新規イベントをキューに投入する"""
        import django_q.tasks

        queued = []
        monkeypatch.setattr(
            django_q.tasks, 'async_task',
            lambda func, *args, **kwargs: queued.append((func, args)),
        )
        make_document(doc_type_code='120', file_date=date.today(), xbrl_flag=True)
        update_diary_disclosure_status()

        assert len(queued) == 1
        func, args = queued[0]
        assert func == 'earnings_analysis.tasks.auto_analyze_disclosure_task'


class TestXBRLAnalyzableGuard:
    """財務諸表を含まない種別（臨報・内部統制等）はXBRL財務分析の対象外"""

    def test_service_rejects_non_financial_doc_type(self, monkeypatch):
        from earnings_analysis.services.xbrl_analysis_service import XBRLAnalysisService

        def _fail(self, d):
            raise AssertionError('非対応種別でXBRL取得が呼ばれた')
        monkeypatch.setattr(
            'earnings_analysis.services.xbrl_extractor.EDINETXBRLService.get_comprehensive_analysis_from_document',
            _fail,
        )
        doc = make_document(doc_type_code='180', xbrl_flag=True)  # 臨時報告書
        result = XBRLAnalysisService().analyze_document(doc)
        assert result['ok'] is False
        assert '対応していません' in result['error']

    def test_view_rejects_non_financial_doc_type(self, authenticated_client, sample_diary):
        from django.urls import reverse

        doc = make_document(doc_type_code='235', xbrl_flag=True)  # 内部統制報告書
        url = reverse('stockdiary:edinet_xbrl_analyze', args=[sample_diary.id])
        res = authenticated_client.post(url, {'doc_id': doc.doc_id})
        assert res.status_code == 400
        assert '対応していません' in res.json()['error']

    def test_panel_hides_analyze_button_for_non_financial_doc(self, authenticated_client, sample_diary):
        from django.urls import reverse

        make_document(doc_id='S100EXTR', doc_type_code='180', xbrl_flag=True)
        make_document(doc_id='S100YUHO', doc_type_code='120', xbrl_flag=True)
        url = reverse('stockdiary:edinet_panel', args=[sample_diary.id])
        html = authenticated_client.get(url).content.decode()

        # 有報には分析ボタンが出る、臨報には出ない
        assert "edinetXBRLAnalyze('%s', 'S100YUHO'" % sample_diary.id in html
        assert "edinetXBRLAnalyze('%s', 'S100EXTR'" % sample_diary.id not in html


class TestPanelFactsOnlyPayload:
    """開示タブのモーダル用JSONは判定を含まず、事実と変化のみを出す"""

    def test_report_and_sentiment_json_exclude_judgments(self, authenticated_client, sample_diary):
        from django.urls import reverse
        from earnings_analysis.models import CompanyFinancialData, SentimentAnalysisHistory

        prev_doc = make_document(
            doc_id='S100PREV', doc_type_code='120',
            file_date=date.today() - timedelta(days=365),
        )
        doc = make_document(
            doc_id='S100CURR', doc_type_code='120',
            file_date=date.today(), xbrl_flag=True,
        )
        CompanyFinancialData.objects.create(
            document=doc, period_type='FY',
            net_sales=10_000_000_000, equity_ratio=50.0,
            operating_cf=500_000_000, investing_cf=-300_000_000, financing_cf=-100_000_000,
        )
        SentimentAnalysisHistory.objects.create(
            document=prev_doc, overall_score=0.10, sentiment_label='neutral',
        )
        # AI判定を含む分析結果を保存しても、パネルのJSONには露出しないこと
        SentimentAnalysisHistory.objects.create(
            document=doc, overall_score=0.35, sentiment_label='positive',
            analysis_result={'ai_expert_analysis': {
                'overall_score': 88, 'investment_points': [{'title': '注目'}],
            }},
        )

        url = reverse('stockdiary:edinet_panel', args=[sample_diary.id])
        html = authenticated_client.get(url).content.decode()

        # 判定要素（リスクラベル・強み/懸念・AIスコア・AIポイント）は出さない
        for judgment_key in ('risk_label', 'strengths', 'concerns',
                             'ai_overall_score', 'ai_insights', 'interpretation'):
            assert judgment_key not in html, judgment_key
        # 変化（経営トーンの前回比）は出す
        assert 'tone_trend' in html
        assert '経営トーン 改善' in html


class TestLexiconSentimentAnalysis:
    """語彙ベースのみの感情分析（run_lexicon_analysis・AI不使用）"""

    SECTIONS = {
        '経営方針': '当期は増収増益を達成し、業績は好調に推移しています。今後も持続的成長を目指します。',
    }

    def _service(self, monkeypatch, sections):
        from earnings_analysis.services.sentiment_analyzer import SentimentAnalysisService
        service = SentimentAnalysisService()
        monkeypatch.setattr(
            service.xbrl_service, 'get_xbrl_text_from_document', lambda doc: sections
        )
        return service

    def _forbid_ai(self, monkeypatch):
        def _fail(*args, **kwargs):
            raise AssertionError('use_ai=False なのに AI 経路が呼ばれた')
        monkeypatch.setattr(
            'earnings_analysis.services.ai_expert_analyzer.AIExpertAnalyzer.analyze_document_comprehensive',
            _fail,
        )
        monkeypatch.setattr(
            'earnings_analysis.services.gemini_insights.GeminiInsightsGenerator.generate_investment_insights',
            _fail,
        )

    def test_saves_history_without_calling_ai(self, monkeypatch):
        from earnings_analysis.models import SentimentAnalysisHistory

        self._forbid_ai(monkeypatch)
        doc = make_document(doc_type_code='120', xbrl_flag=True)
        service = self._service(monkeypatch, self.SECTIONS)

        assert service.run_lexicon_analysis(doc) is True
        history = SentimentAnalysisHistory.objects.get(document=doc)
        assert history.overall_score is not None
        assert history.sentiment_label in ('positive', 'negative', 'neutral')

    def test_skips_when_history_exists(self, monkeypatch):
        from earnings_analysis.models import SentimentAnalysisHistory

        doc = make_document(doc_type_code='120', xbrl_flag=True)
        SentimentAnalysisHistory.objects.create(
            document=doc, overall_score=0.1, sentiment_label='neutral'
        )
        service = self._service(monkeypatch, self.SECTIONS)
        assert service.run_lexicon_analysis(doc) is False
        assert SentimentAnalysisHistory.objects.filter(document=doc).count() == 1

    def test_skips_without_xbrl_text(self, monkeypatch):
        from earnings_analysis.models import SentimentAnalysisHistory

        doc = make_document(doc_type_code='120', xbrl_flag=True)
        service = self._service(monkeypatch, None)
        assert service.run_lexicon_analysis(doc) is False
        assert SentimentAnalysisHistory.objects.filter(document=doc).count() == 0


class TestEarningsReviewPrefill:
    """決算レビューのノート下書き（edinet_note_prefill）"""

    def _prefill(self, client, diary, doc):
        from django.urls import reverse
        url = reverse('stockdiary:edinet_note_prefill', args=[diary.id])
        return client.get(url, {'doc_id': doc.doc_id})

    def test_basic_structure(self, authenticated_client, sample_diary):
        """財務・感情データなしでもレビュー骨子（仮説の点検）が返る"""
        sample_diary.reason = 'EV シフトで部品需要が伸びると考えた'
        sample_diary.save(update_fields=['reason'])
        doc = make_document(doc_type_code='120', file_date=date.today())

        res = self._prefill(authenticated_client, sample_diary, doc)
        assert res.status_code == 200
        data = res.json()
        assert data['note_type'] == 'earnings'
        assert '## 決算レビュー: テスト株式会社' in data['content']
        assert '### 投資仮説の点検' in data['content']
        assert '> EV シフトで部品需要が伸びると考えた' in data['content']
        assert '維持 / 修正 / 撤回' in data['content']

    def test_financial_summary_with_previous_period(self, authenticated_client, sample_diary):
        """XBRL財務データがあれば確定財務サマリー（前回比つき）が差し込まれる"""
        from earnings_analysis.models import CompanyFinancialData

        prev_doc = make_document(
            doc_id='S100PREV', doc_type_code='160',
            file_date=date.today() - timedelta(days=180),
        )
        doc = make_document(doc_id='S100CURR', doc_type_code='120', file_date=date.today())
        CompanyFinancialData.objects.create(
            document=prev_doc, period_type='HalfYear',
            net_sales=10_000_000_000, operating_margin=8.0,
        )
        CompanyFinancialData.objects.create(
            document=doc, period_type='FY',
            net_sales=12_000_000_000, operating_margin=10.5, equity_ratio=55.2,
            operating_cf=500_000_000, investing_cf=-300_000_000, financing_cf=-100_000_000,
        )

        res = self._prefill(authenticated_client, sample_diary, doc)
        content = res.json()['content']
        assert '### 確定財務サマリー' in content
        assert '- 売上高: 120.0億円（前回 100.0億円）' in content
        assert '- 営業利益率: 10.5%（前回 8.0%）' in content
        assert '- 自己資本比率: 55.2%' in content
        assert '- CF: 営業+ / 投資− / 財務−' in content

    def test_management_tone_with_trend(self, authenticated_client, sample_diary):
        """感情分析結果があれば経営トーンと前回比トレンドが差し込まれる"""
        from earnings_analysis.models import SentimentAnalysisHistory

        prev_doc = make_document(
            doc_id='S100PREV', doc_type_code='120',
            file_date=date.today() - timedelta(days=365),
        )
        doc = make_document(doc_id='S100CURR', doc_type_code='120', file_date=date.today())
        SentimentAnalysisHistory.objects.create(
            document=prev_doc, overall_score=0.10, sentiment_label='neutral',
        )
        SentimentAnalysisHistory.objects.create(
            document=doc, overall_score=0.35, sentiment_label='positive',
        )

        res = self._prefill(authenticated_client, sample_diary, doc)
        content = res.json()['content']
        assert '### 経営トーン' in content
        assert 'ポジティブ' in content
        assert '前回 0.10 から改善' in content

    def test_other_users_diary_forbidden(self, authenticated_client, another_user):
        other_diary = StockDiary.objects.create(
            user=another_user, stock_symbol='7203', stock_name='トヨタ自動車'
        )
        doc = make_document(doc_type_code='120', file_date=date.today())
        res = self._prefill(authenticated_client, other_diary, doc)
        assert res.status_code == 404
