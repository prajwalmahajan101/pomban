import tempfile
from pathlib import Path

import pytest

from pomban.core.db import DB
from pomban.core.session_service import SessionService


@pytest.fixture
def svc():
    p = Path(tempfile.mktemp(suffix=".db"))
    db = DB(p)
    yield SessionService(db)
    db.close()
    p.unlink(missing_ok=True)


def test_lunch_not_taken_initially(svc):
    assert svc.lunch_taken_today() is False


def test_lunch_taken_after_long_pause_start(svc):
    svc.start("long_pause", 2700, [])
    assert svc.lunch_taken_today() is True


def test_lunch_query_is_cached(svc):
    # Prime the cache (False), then write a long_pause row directly bypassing the
    # service so the cache is stale — a cached read must still return False.
    assert svc.lunch_taken_today() is False
    svc.db.start_session("long_pause", 2700, [])  # not via svc.start → no invalidate
    assert svc.lunch_taken_today() is False  # served from cache
    svc._lunch_cache = None  # force re-query
    assert svc.lunch_taken_today() is True


def test_service_start_invalidates_cache(svc):
    assert svc.lunch_taken_today() is False  # cache primed False
    svc.start("long_pause", 2700, [])  # via service → invalidates
    assert svc.lunch_taken_today() is True
