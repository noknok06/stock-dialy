"""詳細画面の入力動線をスピードダイヤルに統一：記録/取引/株式分割/仮説の追加。

追加はスピードダイヤルに集約、編集・削除は各所インラインのまま（本テストは追加導線を検証）。
"""
import pytest
from django.urls import reverse


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
