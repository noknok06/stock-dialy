"""note_type の保存に関するテスト。

入力での note_type 強制選択UI（フィルタチップ／選択ピル）はユーザー判断で撤回
（topic 単一入力に統一）。note_type 自体は add_note フォーム・EDINET 連携・
振り返りフローで設定され得るため、保存経路のみ検証する。
"""
import datetime

import pytest
from django.urls import reverse

from stockdiary.models import DiaryNote


@pytest.mark.django_db
class TestNoteTypePersisted:
    def test_add_note_persists_selected_note_type(self, authenticated_client, sample_diary):
        url = reverse('stockdiary:add_note', kwargs={'pk': sample_diary.pk})
        resp = authenticated_client.post(url, {
            'date': datetime.date.today().isoformat(),
            'note_type': 'earnings',
            'importance': 'medium',
            'topic': '',
            'content': '今期は増収増益。ガイダンスも上方修正。',
        })
        assert resp.status_code in (302, 200)
        note = DiaryNote.objects.filter(diary=sample_diary, note_type='earnings').first()
        assert note is not None
        assert note.content.startswith('今期は増収増益')
