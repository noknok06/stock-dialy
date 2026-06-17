"""デモデータ（create_realistic_test_data）の検証ループ投入テスト。

reset_demo → create_realistic_test_data は cron / django-q で毎日再投入される。
仮説・検証が投資家カルテ／知識ライブラリ／ホーム想起を埋めること、そして
検証予定日が「相対日」で持たれ、いつ再投入してもホームの
「答え合わせを待つ仮説」が安定して現れることを検証する。
"""
import pytest

from django.core.management import call_command
from django.utils import timezone

from stockdiary.models import Thesis, Verdict
from stockdiary.services.recall_service import RecallService
from stockdiary.services.karte_service import build_investor_karte

pytestmark = pytest.mark.django_db(transaction=True)


def test_demo_populates_thesis_and_verdict(user):
    call_command('create_realistic_test_data', '--username', user.username)
    assert Thesis.objects.filter(diary__user=user).count() == 7
    assert Verdict.objects.filter(thesis__diary__user=user).count() == 4


def test_demo_due_thesis_surfaces_on_home(user):
    call_command('create_realistic_test_data', '--username', user.username)
    recall = RecallService.build(user)
    # 未検証かつ検証予定日が到来済みの仮説（三菱重工）だけがホーム想起に出る
    names = [t.diary.stock_name for t in recall['due_theses']]
    assert names == ['三菱重工業']
    assert recall['has_content'] is True


def test_demo_due_date_is_relative_to_today(user):
    """検証予定日が固定日でなく相対日であること（毎日の再投入で陳腐化しない）。"""
    call_command('create_realistic_test_data', '--username', user.username)
    today = timezone.localdate()
    open_qs = Thesis.objects.filter(diary__user=user, status=Thesis.STATUS_OPEN)
    due = open_qs.filter(review_due_date__lte=today).count()
    future = open_qs.filter(review_due_date__gt=today).count()
    assert due == 1      # 三菱重工（due=-10）
    assert future == 2   # アドバンテスト(+30)・ソニー(+60)


def test_demo_karte_has_quadrant_distribution(user):
    call_command('create_realistic_test_data', '--username', user.username)
    karte = build_investor_karte(user)
    assert karte['has_content']
    counts = {q['key']: q['count'] for q in karte['quadrants']}
    # 規律ある勝ち（skill）と、偶然の勝ち（lucky=レーザーテック）の対比を示す
    assert counts['skill'] == 3
    assert counts['lucky'] == 1


def test_demo_lucky_matches_retrospective_narrative(user):
    """レーザーテックの検証が『仮説は外れたが利益（偶然の勝ち）』であること。

    既存の振り返りノート（運の要素が大きい）と矛盾しない。
    """
    call_command('create_realistic_test_data', '--username', user.username)
    v = Verdict.objects.get(thesis__diary__user=user,
                            thesis__diary__stock_symbol='6920')
    assert v.quadrant == 'lucky'


def test_demo_reset_is_idempotent_with_clear(user):
    call_command('create_realistic_test_data', '--username', user.username)
    call_command('create_realistic_test_data', '--username', user.username, '--clear')
    # 二重投入されない（--clear で日記ごと削除 → CASCADE で仮説/検証も消える）
    assert Thesis.objects.filter(diary__user=user).count() == 7
    assert Verdict.objects.filter(thesis__diary__user=user).count() == 4
