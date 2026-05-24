import datetime
import pytest
from django.urls import reverse
from stockdiary.models import DiaryNote


@pytest.mark.django_db
def test_detail_renders_topic_ui(authenticated_client, diary_with_notes):
    diary = diary_with_notes
    # give one note a topic
    note = diary.notes.first()
    note.topic = 'ナフサの影響'
    note.save()

    url = reverse('stockdiary:detail', kwargs={'pk': diary.pk})
    resp = authenticated_client.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'ナフサの影響' in html            # topic chip rendered
    assert 'switchNotesView' in html          # view toggle wired
    assert 'openEditNoteSheet' in html        # edit button wired
    assert 'notes-view-topic' in html         # theme view container present
    assert 'name="topic"' in html             # bottom-sheet topic input


@pytest.mark.django_db
def test_add_note_with_topic(authenticated_client, sample_diary):
    url = reverse('stockdiary:add_note', kwargs={'pk': sample_diary.pk})
    resp = authenticated_client.post(url, {
        'date': datetime.date.today().isoformat(),
        'note_type': 'analysis',
        'importance': 'medium',
        'topic': '半導体サイクル',
        'content': '受注が底打ちした可能性。',
    })
    assert resp.status_code in (302, 200)
    note = DiaryNote.objects.filter(diary=sample_diary, topic='半導体サイクル').first()
    assert note is not None
    assert note.content == '受注が底打ちした可能性。'


@pytest.mark.django_db
def test_edit_note_updates_topic_and_content(authenticated_client, diary_with_notes):
    diary = diary_with_notes
    note = diary.notes.first()
    url = reverse('stockdiary:edit_note', kwargs={'diary_pk': diary.pk, 'pk': note.pk})
    resp = authenticated_client.post(url, {
        'date': note.date.isoformat(),
        'note_type': note.note_type,
        'importance': note.importance,
        'topic': '更新後テーマ',
        'content': '内容を編集しました。',
    })
    assert resp.status_code in (302, 200)
    note.refresh_from_db()
    assert note.topic == '更新後テーマ'
    assert note.content == '内容を編集しました。'


@pytest.mark.django_db
def test_edit_note_rejects_other_users_note(authenticated_client, another_user, sample_diary):
    from stockdiary.models import StockDiary
    other_diary = StockDiary.objects.create(user=another_user, stock_symbol='9999', stock_name='他人')
    other_note = DiaryNote.objects.create(diary=other_diary, date=datetime.date.today(), content='secret')
    url = reverse('stockdiary:edit_note', kwargs={'diary_pk': other_diary.pk, 'pk': other_note.pk})
    resp = authenticated_client.post(url, {
        'date': other_note.date.isoformat(),
        'note_type': 'analysis',
        'importance': 'medium',
        'topic': 'hack',
        'content': 'hacked',
    })
    assert resp.status_code == 404
    other_note.refresh_from_db()
    assert other_note.content == 'secret'
