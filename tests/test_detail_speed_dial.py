"""詳細画面の入力動線をスピードダイヤルに統一：記録/取引/株式分割/仮説の追加。

追加はスピードダイヤルに集約、編集・削除は各所インラインのまま（本テストは追加導線を検証）。
"""
import pytest
from django.urls import reverse

from stockdiary.models import Thesis


@pytest.mark.django_db
def test_speed_dial_contains_all_add_actions(authenticated_client, sample_diary):
    resp = authenticated_client.get(reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk}))
    assert resp.status_code == 200
    html = resp.content.decode()
    # 4つの追加アクションがスピードダイヤルに含まれる（data-action-id で判定）
    assert 'data-action-id="add-note"' in html
    assert 'data-action-id="add-transaction"' in html
    assert 'data-action-id="add-split"' in html
    assert 'data-action-id="add-thesis"' in html
    # 分割はボトムシート、仮説は HTMX フォーム起動
    assert "openBottomSheet('addSplitSheet')" in html
    assert 'openThesisForm();' in html
    assert 'window.openThesisForm' in html
    # 仮説の追加先は記録タブの『仮説』ビュー。openThesisForm が notes-tab を開き、
    # thesis ビューへ切り替えてからフォームを起動する（移設後の遷移先回帰防止）。
    assert "document.getElementById('notes-tab')" in html
    assert "switchNotesView('thesis')" in html


@pytest.mark.django_db
def test_persistent_inline_add_rows_removed(authenticated_client, sample_diary_with_transaction):
    """追加導線はスピードダイヤルに一本化：各タブ上部の常設「追加」ボタン行(.tab-action-row)を撤去。

    編集・削除は取引カードのインラインに残す（showEditForm / deleteTransaction）。
    """
    resp = authenticated_client.get(
        reverse('stockdiary:detail', kwargs={'pk': sample_diary_with_transaction.pk})
    )
    assert resp.status_code == 200
    html = resp.content.decode()
    # 常設のインライン追加ボタン行は撤去済み（CSSコメントは class= を含まないため誤検知しない）
    assert 'class="tab-action-row"' not in html
    # 編集・削除のインライン導線は維持
    assert 'showEditForm(' in html
    assert 'deleteTransaction(' in html


@pytest.mark.django_db
def test_thesis_add_button_only_in_empty_state(authenticated_client, sample_diary):
    """仮説追加も一本化：仮説ゼロ時のみ常設CTA(.karte-add-thesis)を出し、
    既に仮説がある場合は撤去して FAB(openThesisForm)へ集約する。"""
    detail_url = reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})

    # 仮説ゼロ：空状態CTAボタンが出る（class= で判定。CSS セレクタ文字列は誤検知しない）
    html = authenticated_client.get(detail_url).content.decode()
    assert 'class="karte-add-thesis"' in html
    assert '当時の仮説を記録する' in html
    # FAB からの起動に必要な作成URLが karte-block に付与されている
    assert 'data-thesis-create-url=' in html

    # 仮説を1件追加すると、常設の追加ボタンは消える（FABに一本化）
    Thesis.objects.create(diary=sample_diary, claim='主張', basis='根拠')
    html2 = authenticated_client.get(detail_url).content.decode()
    assert 'class="karte-add-thesis"' not in html2
    assert '当時の仮説を記録する' not in html2
    # ただし FAB の add-thesis 導線と作成URLは維持
    assert 'data-action-id="add-thesis"' in html2
    assert 'data-thesis-create-url=' in html2
    # テンプレートコメントが本文へ漏れていないこと（複数行 {# #} 事故の回帰防止）
    assert 'openThesisForm() が data-thesis-create-url' not in html2


@pytest.mark.django_db
def test_overview_tag_dedup_and_thesis_relocated_to_notes_tab(authenticated_client, sample_diary, user):
    """① 概要タブのタグ重複を解消する。
    ④ 検証ループ(仮説)は概要タブから「記録」タブの『仮説』ビューへ移設し、
       テーマ別/活動と同じトグル並びに統一する（UX の自然さ向上）。

    旧仕様では検証ループを概要タブの投資理由直後に固めていたが、記録系の導線（テーマ別・活動）
    と並べた方が自然なため記録タブへ移した。概要側の目次・本文に仮説ブロックが残っていると
    「隠れたタブ内要素へジャンプする死にリンク」になるため、その回帰も防ぐ。
    """
    from tags.models import Tag
    sample_diary.tags.add(Tag.objects.create(user=user, name='長期投資'))

    html = authenticated_client.get(
        reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
    ).content.decode()

    # ① タグ表示は「テーマ×感応」に一本化。素のサイドバー用チップ(sidebar-tags)は重複出力しない
    assert 'id="section-theme-sensitivity"' in html
    assert 'class="sidebar-tags"' not in html
    # サイドバー目次からテーマ×感応へジャンプできる（重複の代わりの導線）
    assert 'data-target="section-theme-sensitivity"' in html

    # ④ 検証ループ(karte-block)は記録タブの『仮説』ビュー(#notes-view-thesis)内へ移設
    assert html.index('id="notes-content"') < html.index('id="karte-block"')
    assert html.index('id="notes-view-thesis"') < html.index('id="karte-block"')
    # トグルは テーマ別 → 仮説 → 活動 の並び（仮説は中央）
    assert html.index('data-view="topic"') < html.index('data-view="thesis"') < html.index('data-view="activity"')
    # 概要タブ目次に「仮説と検証」への死にリンクが残っていない
    assert 'data-target="karte-block"' not in html


@pytest.mark.django_db
def test_timeline_tab_removed_from_top_level(authenticated_client, sample_diary):
    """② タブ数削減: 旧「時系列(活動履歴)」トップレベルタブを撤去（6→5タブ）。"""
    html = authenticated_client.get(
        reverse('stockdiary:detail', kwargs={'pk': sample_diary.pk})
    ).content.decode()
    assert 'data-bs-target="#events-content"' not in html
    # 既存の主要タブは維持
    for target in ('#basic-content', '#notes-content', '#transactions-content', '#related-content'):
        assert f'data-bs-target="{target}"' in html
    # テンプレートコメントが本文へ漏れていないこと（複数行 {# #} 事故の回帰防止）
    assert 'event_timeline でも出す' not in html
    assert 'フィルタの参照元として DOM に常設' not in html
