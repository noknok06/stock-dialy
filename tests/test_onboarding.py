import pytest

from diary_templates.defaults import (
    BASIC_TEMPLATE_TITLE,
    SAMPLE_TEMPLATE_TITLE,
)
from diary_templates.models import DiaryTemplate
from stockdiary.utils import build_theme_recall
from tags.models import MasterTag, Tag


@pytest.mark.django_db
def test_signal_seeds_only_basic_for_new_user(django_user_model):
    u = django_user_model.objects.create_user(
        username='newbie', email='n@example.com', password='x'
    )
    titles = set(DiaryTemplate.objects.filter(user=u).values_list('title', flat=True))
    assert titles == {BASIC_TEMPLATE_TITLE}


@pytest.mark.django_db
def test_list_templates_basic_first(client, django_user_model):
    u = django_user_model.objects.create_user(
        username='u2', email='u2@example.com', password='x'
    )
    # signal already created basic; add sample + an unrelated one
    DiaryTemplate.objects.get_or_create(user=u, title=SAMPLE_TEMPLATE_TITLE, defaults={'body': 'x'})
    DiaryTemplate.objects.create(user=u, title='AAA', body='x')
    client.force_login(u)
    resp = client.get('/diary-templates/api/list/')
    data = resp.json()
    assert data['success']
    titles = [t['title'] for t in data['templates']]
    assert titles[0] == BASIC_TEMPLATE_TITLE  # 基本が先頭
    assert titles[1:] == ['AAA', SAMPLE_TEMPLATE_TITLE]  # 残りはタイトル順


@pytest.mark.django_db
def test_add_sample_action(client, django_user_model):
    u = django_user_model.objects.create_user(
        username='u3', email='u3@example.com', password='x'
    )
    client.force_login(u)
    assert not DiaryTemplate.objects.filter(user=u, title=SAMPLE_TEMPLATE_TITLE).exists()
    resp = client.post('/diary-templates/add-sample/')
    assert resp.status_code == 302
    assert DiaryTemplate.objects.filter(user=u, title=SAMPLE_TEMPLATE_TITLE).exists()


@pytest.mark.django_db
def test_empty_recall_theme_branch(sample_diary):
    t = Tag.objects.create(user=sample_diary.user, name='半導体', axis='theme')
    sample_diary.tags.add(t)
    out = build_theme_recall([], sample_diary, sample_diary.user)
    assert out['is_empty']
    assert out['focal_theme_tags'] == ['半導体']
    assert out['focal_label_tags'] == []


@pytest.mark.django_db
def test_empty_recall_label_branch(sample_diary):
    t = Tag.objects.create(user=sample_diary.user, name='自動車', axis='custom')
    sample_diary.tags.add(t)
    out = build_theme_recall([], sample_diary, sample_diary.user)
    assert out['is_empty']
    assert out['focal_theme_tags'] == []
    assert out['focal_label_tags'] == [{'id': t.id, 'name': '自動車'}]


@pytest.mark.django_db
def test_theme_recall_partial_renders_all_empty_branches():
    from django.template.loader import render_to_string

    base = {'primary': [], 'more': [], 'total': 0, 'is_empty': True, 'sector_only': False}

    # theme branch
    html = render_to_string('stockdiary/partials/_theme_recall.html', {
        'theme_recall': {**base, 'focal_theme_tags': ['半導体'], 'focal_label_tags': [], 'suggested_themes': []},
    })
    assert '記録中' in html and '@半導体' in html

    # label branch (deep link to tags:update with dict id)
    html = render_to_string('stockdiary/partials/_theme_recall.html', {
        'theme_recall': {**base, 'focal_theme_tags': [], 'focal_label_tags': [{'id': 42, 'name': '自動車'}], 'suggested_themes': []},
    })
    assert '/tags/42/update/' in html and 'テーマに変える' in html

    # no-tags branch with suggestions
    html = render_to_string('stockdiary/partials/_theme_recall.html', {
        'theme_recall': {**base, 'focal_theme_tags': [], 'focal_label_tags': [], 'suggested_themes': ['防衛', 'AI']},
    })
    assert '@テーマ' in html and '@防衛' in html


@pytest.mark.django_db
def test_empty_recall_suggested_themes(sample_diary):
    MasterTag.objects.create(name='防衛', axis='theme', is_active=True, sort_order=1)
    MasterTag.objects.create(name='AI', axis='theme', is_active=True, sort_order=2)
    MasterTag.objects.create(name='高配当', axis='capital_policy', is_active=True, sort_order=3)
    out = build_theme_recall([], sample_diary, sample_diary.user)
    assert out['is_empty']
    assert out['focal_theme_tags'] == []
    assert out['focal_label_tags'] == []
    assert out['suggested_themes'] == ['防衛', 'AI']  # theme軸のみ・sort_order順
