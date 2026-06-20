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
