"""分析API（stockdiary/api_analysis.py）の書き込み時タグ同期のテスト。

なぜこのテストがあるか:
  分析API の update_reason / add_note は reason・ノートを保存するだけで、
  本文中の `@タグ` を diary.tags（M2M）へ同期していなかった。そのため
  「日記は更新されるがタグが更新されない」状態になっていた。
  UI の保存フローと同じ正本ロジック（views._sync_hashtag_tags）を
  書き込み後に呼ぶよう修正した。その同期挙動を固定する回帰テスト。
"""
import json

import pytest
from django.test import RequestFactory
from django.contrib.auth import get_user_model

from stockdiary import api_analysis
from stockdiary.models import StockDiary

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api_user(db):
    return User.objects.create_user(
        username='analysis_api_user', password='pass', email='a@example.com'
    )


@pytest.fixture
def diary(api_user):
    return StockDiary.objects.create(
        user=api_user, stock_name='トヨタ自動車', stock_symbol='7203', reason=''
    )


@pytest.fixture
def auth_settings(settings, api_user):
    settings.ANALYSIS_API_KEY = 'testkey'
    settings.ANALYSIS_API_USER = api_user.username
    return settings


def _patch(path, payload):
    return RequestFactory().patch(
        path, data=json.dumps(payload), content_type='application/json',
        HTTP_AUTHORIZATION='Bearer testkey',
    )


def _post(path, payload):
    return RequestFactory().post(
        path, data=json.dumps(payload), content_type='application/json',
        HTTP_AUTHORIZATION='Bearer testkey',
    )


def test_update_reason_syncs_tags_from_body(auth_settings, diary):
    """reason 更新時、本文中の @タグが diary.tags に同期される（バグ回帰）。"""
    reason = "## 関連タグ\n`@世界トップ` `@円安↑` `@高配当`"
    request = _patch('/api/analysis/diary/7203/reason/', {'reason': reason})

    response = api_analysis.update_reason(request, '7203')
    assert response.status_code == 200

    body = json.loads(response.content)
    assert set(body['tags']) == {'世界トップ', '円安', '高配当'}

    diary.refresh_from_db()
    assert set(diary.tags.values_list('name', flat=True)) == {'世界トップ', '円安', '高配当'}
    # 矢印付き(@円安↑)は方向(up)も反映される
    assert diary.tag_directions.filter(tag__name='円安', direction='up').exists()


def test_add_note_syncs_tags_from_content(auth_settings, diary):
    """ノート追加時、本文中の @タグが diary.tags に同期される。"""
    request = _post(
        '/api/analysis/diary/7203/notes/',
        {'content': '決算分析。`@決算ミス` `@半導体`', 'topic': '決算分析'},
    )
    response = api_analysis.add_note(request, '7203')
    assert response.status_code == 201

    body = json.loads(response.content)
    assert {'決算ミス', '半導体'} <= set(body['tags'])
    diary.refresh_from_db()
    assert {'決算ミス', '半導体'} <= set(diary.tags.values_list('name', flat=True))


def test_update_reason_removes_stale_tags(auth_settings, diary):
    """reason から消えた @タグは diary.tags からも解除される。"""
    api_analysis.update_reason(
        _patch('/api/analysis/diary/7203/reason/', {'reason': '`@高配当` `@世界トップ`'}),
        '7203',
    )
    diary.refresh_from_db()
    assert set(diary.tags.values_list('name', flat=True)) == {'高配当', '世界トップ'}

    # 高配当を外した本文で更新 → 高配当が解除される
    api_analysis.update_reason(
        _patch('/api/analysis/diary/7203/reason/', {'reason': '`@世界トップ`'}),
        '7203',
    )
    diary.refresh_from_db()
    assert set(diary.tags.values_list('name', flat=True)) == {'世界トップ'}
