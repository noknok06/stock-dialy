"""security.middleware.IPFilterMiddleware の不審リクエスト判定のテスト。

なぜこのテストがあるか:
  分析API（/api/analysis/）への POST 本文に markdown を含めると 403
  "Suspicious Request Detected" で弾かれるバグがあった。
  原因は `_is_suspicious_request` の SQLi 検知パターン
  `(\\%27)|(\\')|(\\-\\-)|(\\%23)|(#)` が、markdown の見出し `#`・
  表区切り `--`・アポストロフィ `'` を不正入力と誤検知していたこと
  （走査対象は POST の JSON ボディ）。
  分析APIは Bearer 認証必須・本文は ORM 保存（SQLi不成立）・
  テンプレートで自動エスケープ描画（XSS不成立）のため、
  本文走査の対象外にした。その挙動を固定する回帰テスト。
"""
import json

import pytest
from django.test import RequestFactory

from security.middleware import IPFilterMiddleware


@pytest.fixture
def middleware():
    return IPFilterMiddleware(get_response=lambda request: None)


def _json_post(path, payload):
    return RequestFactory().post(
        path, data=json.dumps(payload), content_type='application/json'
    )


# markdown の見出し(#)・表区切り(--)・アポストロフィ(') を含む本文
MARKDOWN_BODY = {
    "content": "## 決算分析\n|指標|値|\n|---|---|\n- it's a test -- dash",
    "topic": "決算分析",
}


def test_analysis_api_post_with_markdown_is_not_suspicious(middleware):
    """分析APIへの markdown 入り POST は不審判定されない（バグ回帰）。"""
    request = _json_post('/api/analysis/diary/7203/notes/', MARKDOWN_BODY)
    assert middleware._is_suspicious_request(request) is False


def test_non_analysis_api_post_with_markdown_chars_still_blocked(middleware):
    """除外はあくまで /api/analysis/ 限定。他の /api/ では従来通り検知が効く。"""
    request = _json_post('/api/notifications/logs/', MARKDOWN_BODY)
    assert middleware._is_suspicious_request(request) is True


def test_analysis_api_get_query_injection_is_not_scanned(middleware):
    """除外はパス単位。/api/analysis/ では GET クエリも走査しない。"""
    request = RequestFactory().get("/api/analysis/holdings/", {"q": "' OR 1=1 --"})
    assert middleware._is_suspicious_request(request) is False


def test_sql_injection_on_protected_path_is_detected(middleware):
    """除外パス以外では SQLi 風入力を従来通りブロックする（防御の健在性）。"""
    request = RequestFactory().get("/api/notifications/logs/", {"id": "1' OR '1'='1"})
    assert middleware._is_suspicious_request(request) is True
