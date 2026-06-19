"""note_type を「追える軸」にする（段階9a-E）テスト。

docs/diary_recording_redesign.md 段階9a-E:
- 継続記録に note_type 絞り込みチップを追加（決算分析・ニュース等を時系列で追える）
- 入力フォームで note_type を選択可能化（hidden 固定 analysis からの脱却）
"""
import datetime

import pytest
from django.urls import reverse

from stockdiary.models import DiaryNote


@pytest.mark.django_db
class TestNoteTypeFilterUI:
    def test_detail_renders_note_type_filter_chips(self, authenticated_client, diary_with_notes):
        url = reverse('stockdiary:detail', kwargs={'pk': diary_with_notes.pk})
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert 'noteTypeFilter' in html          # 種類フィルタのコンテナ
        assert 'filterNotesByType' in html        # フィルタ関数の結線
        assert '決算情報' in html                  # 種類チップのラベル

    def test_detail_renders_note_type_selection_pills(self, authenticated_client, diary_with_notes):
        url = reverse('stockdiary:detail', kwargs={'pk': diary_with_notes.pk})
        resp = authenticated_client.get(url)
        html = resp.content.decode()
        # 入力フォームの note_type 選択ピル（data-target で隠しinputに結線される）
        assert 'data-target="note_type"' in html
        assert 'data-value="earnings"' in html


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
