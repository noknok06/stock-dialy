"""バックリンク（この銘柄に触れている他の記録）のテスト"""
import pytest
from datetime import date, timedelta

from stockdiary.models import StockDiary, DiaryNote
from stockdiary.utils import find_backlinks

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def mentioning_diary(user):
    """トヨタ(7203)に本文で言及している別銘柄の日記"""
    return StockDiary.objects.create(
        user=user,
        stock_symbol='6902',
        stock_name='デンソー',
        reason='主要顧客のトヨタ(7203)の生産計画に連動する。',
    )


class TestFindBacklinks:

    def test_reason_mention_found(self, sample_diary, mentioning_diary):
        backlinks = find_backlinks(sample_diary, sample_diary.user)
        assert len(backlinks) == 1
        item = backlinks[0]
        assert item['diary'].id == mentioning_diary.id
        assert item['source'] == 'reason'
        assert '(7203)' in item['snippet']

    def test_fullwidth_bracket_mention_found(self, sample_diary, user):
        d = StockDiary.objects.create(
            user=user, stock_symbol='6301', stock_name='コマツ',
            reason='トヨタ（7203）と比較して割安。',
        )
        backlinks = find_backlinks(sample_diary, user)
        assert any(b['diary'].id == d.id for b in backlinks)

    def test_note_mention_found(self, sample_diary, user):
        other = StockDiary.objects.create(
            user=user, stock_symbol='7267', stock_name='ホンダ', reason='EV戦略',
        )
        note_date = date.today() - timedelta(days=3)
        DiaryNote.objects.create(
            diary=other, date=note_date,
            content='トヨタ(7203)の決算を受けて自動車セクター全体が上昇。',
        )
        backlinks = find_backlinks(sample_diary, user)
        note_items = [b for b in backlinks if b['source'] == 'note']
        assert len(note_items) == 1
        assert note_items[0]['diary'].id == other.id
        assert note_items[0]['date'] == note_date

    def test_bare_code_without_brackets_not_matched(self, sample_diary, user):
        """括弧なしの数字はメンションとして扱わない"""
        StockDiary.objects.create(
            user=user, stock_symbol='8306', stock_name='三菱UFJ',
            reason='時価総額7203億円のテスト',
        )
        assert find_backlinks(sample_diary, user) == []

    def test_same_symbol_diary_excluded(self, sample_diary, user):
        """同一銘柄の重複日記は自己言及なので対象外"""
        StockDiary.objects.create(
            user=user, stock_symbol='7203', stock_name='トヨタ自動車(2冊目)',
            reason='トヨタ(7203)の積み増し検討。',
        )
        assert find_backlinks(sample_diary, user) == []

    def test_other_user_not_included(self, sample_diary, another_user):
        StockDiary.objects.create(
            user=another_user, stock_symbol='6902', stock_name='デンソー',
            reason='トヨタ(7203)に連動。',
        )
        assert find_backlinks(sample_diary, sample_diary.user) == []

    def test_asymmetric_linked_from_included(self, sample_diary, user):
        """linked_from の片方向リンク（古いデータ）は手動リンクとして出る"""
        other = StockDiary.objects.create(
            user=user, stock_symbol='9101', stock_name='日本郵船', reason='海運',
        )
        other.linked_diaries.add(sample_diary)  # 片方向のみ
        backlinks = find_backlinks(sample_diary, user)
        assert len(backlinks) == 1
        assert backlinks[0]['source'] == 'link'
        assert backlinks[0]['diary'].id == other.id

    def test_symmetric_link_not_listed(self, sample_diary, user):
        """双方向リンク済みは関連日記リストと重複するため出さない"""
        other = StockDiary.objects.create(
            user=user, stock_symbol='9101', stock_name='日本郵船', reason='海運',
        )
        other.linked_diaries.add(sample_diary)
        sample_diary.linked_diaries.add(other)
        assert find_backlinks(sample_diary, user) == []

    def test_no_symbol_diary_only_links(self, user):
        """銘柄コードなしのメモ日記はテキスト言及検索の対象外"""
        memo = StockDiary.objects.create(user=user, stock_symbol='', stock_name='投資メモ')
        assert find_backlinks(memo, user) == []

    def test_detail_page_defers_backlinks_to_htmx(self, authenticated_client, sample_diary, mentioning_diary):
        """detail 初期表示ではバックリンクを計算せず、関連タブ表示時に HTMX で
        遅延ロードする。重い find_backlinks を毎回走らせないための回帰。
        初期HTMLには遅延ロードの配線（エンドポイントURLとコンテナ）だけが入る。"""
        from django.urls import reverse
        response = authenticated_client.get(
            reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
        )
        assert response.status_code == 200
        html = response.content.decode()
        # 遅延ロードの配線が入っている
        assert reverse('stockdiary:backlinks_panel', kwargs={'diary_id': sample_diary.pk}) in html
        assert 'id="backlinks-panel-body"' in html
        # バックリンク本体（見出し）は初期HTMLには含めない（遅延ロードの partial にのみ存在）。
        # ※ 銘柄名そのものは別所（日記メンションのオートコンプリート等）にも出るため
        #   バックリンク固有の見出し文言で判定する。
        assert 'この銘柄に触れている記録' not in html

    def test_backlinks_panel_endpoint_renders(self, authenticated_client, sample_diary, mentioning_diary):
        """遅延ロード先のエンドポイントはバックリンクを描画する（HTMXリクエスト）。"""
        from django.urls import reverse
        response = authenticated_client.get(
            reverse('stockdiary:backlinks_panel', kwargs={'diary_id': sample_diary.pk}),
            HTTP_HX_REQUEST='true',
        )
        assert response.status_code == 200
        html = response.content.decode()
        assert 'この銘柄に触れている記録' in html
        assert 'デンソー' in html

    def test_backlinks_panel_other_user_forbidden(self, client, sample_diary, another_user):
        """他人の日記のバックリンクパネルは取得できない。"""
        from django.urls import reverse
        client.force_login(another_user)
        response = client.get(
            reverse('stockdiary:backlinks_panel', kwargs={'diary_id': sample_diary.pk}),
            HTTP_HX_REQUEST='true',
        )
        assert response.status_code == 404
