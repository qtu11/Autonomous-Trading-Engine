"""Tests for economic-calendar news protection (the state the EA polls every 30s).

Covers:
- protection endpoint must compute REAL levels from EA-pushed calendar events
  (lockdown within ±15 min, approaching within 1h, watch within 5h)
- alias /api/economic-calendar/protection == /api/v1/economic-calendar/protection
- auth is required (401 without Bearer)
"""
from datetime import datetime, timedelta, timezone

import server  # noqa: E402  (conftest.py đã thêm dashboard/ vào sys.path)

from starlette.testclient import TestClient  # noqa: E402

client = TestClient(server.app)
HDR = {"Authorization": "Bearer test-bridge-token"}


def _event(dt: datetime, impact: str = "HIGH", title: str = "Nonfarm Payrolls") -> dict:
    """Payload đúng format EA gửi: date/time dấu chấm kiểu MQL5, impact MED/HIGH."""
    return {
        "event_id": str(int(dt.timestamp())),
        "day": dt.strftime("%Y.%m.%d"),
        "date": dt.strftime("%Y.%m.%d"),
        "time": dt.strftime("%H:%M"),
        "currency": "USD",
        "title": title,
        "impact": impact,
        "actual": "", "forecast": "", "previous": "",
        "status": "UPCOMING",
    }


def _push(events):
    server._market_cache.pop("economic_calendar", None)
    r = client.post("/api/v1/bridge/calendar", json={"executor_id": "ate-ea-local", "events": events}, headers=HDR)
    assert r.status_code == 200


def _fetch(path="/api/v1/economic-calendar/protection"):
    return client.get(path, headers=HDR)


def test_protection_lockdown_within_window():
    """Event HIGH đang trong cửa sổ ±15 phút -> lockdown (chặn entry)."""
    _push([_event(datetime.now(timezone.utc) + timedelta(minutes=5))])
    r = _fetch()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "OK"
    assert body["level"] == "lockdown"
    assert body["protection_level"] == "lockdown"
    assert body["live_remaining_seconds"] > 0
    assert body["next_event"]["title"] == "Nonfarm Payrolls"


def test_protection_watch_within_5h():
    """Event HIGH trong 1-5h -> watch (entries vẫn được phép, nhưng EA biết tin tới)."""
    _push([_event(datetime.now(timezone.utc) + timedelta(hours=2))])
    body = _fetch().json()
    assert body["level"] == "watch"


def test_protection_none_with_fresh_calendar_but_no_high_med_events():
    """Calendar tươi (EA vừa đẩy) nhưng chỉ có event LOW -> none (không chặn)."""
    _push([_event(datetime.now(timezone.utc) + timedelta(minutes=5), impact="LOW", title="Low Impact")])
    body = _fetch().json()
    assert body["level"] == "none"
    assert body["data_available"] is True


def test_protection_unknown_without_calendar_data():
    """FAIL-CLOSED: chưa có dữ liệu lịch (cache trống) -> "unknown" chứ KHÔNG phải
    "none" — EA phải CHẶN entry khi không có thông tin tin tức nào."""
    server._market_cache.pop("economic_calendar", None)
    body = _fetch().json()
    assert body["level"] == "unknown"
    assert body["data_available"] is False


def test_protection_med_impact_also_blocks():
    """EA gửi impact 'MED' (MQL5 CALENDAR_IMPORTANCE_MODERATE) — phải được tính là
    mức chặn như HIGH trong cửa sổ lockdown."""
    _push([_event(datetime.now(timezone.utc) + timedelta(minutes=3), impact="MED", title="CPI MoM")])
    body = _fetch().json()
    assert body["level"] == "lockdown"
    assert body["next_event"]["title"] == "CPI MoM"


def test_protection_v1_alias():
    """Cả 2 đường alias phải trả kết quả như nhau (EA dùng /api/v1/...)."""
    _push([_event(datetime.now(timezone.utc) + timedelta(hours=2))])
    v1 = _fetch("/api/v1/economic-calendar/protection").json()
    plain = _fetch("/api/economic-calendar/protection").json()
    assert v1["level"] == plain["level"] == "watch"


def test_protection_requires_bearer():
    """Không có Bearer -> 401 (fail-closed: EA không biết trạng thái -> chặn entry)."""
    _push([])
    r = client.get("/api/v1/economic-calendar/protection")
    assert r.status_code == 401


def test_parse_event_datetime_mql5_format():
    """BUG FIX: EA gửi date '2026.08.12' (dấu chấm MQL5) — phải parse được."""
    ev = {"date": "2026.08.12", "time": "10:30"}
    dt = server._parse_event_datetime(ev)
    assert dt is not None
    assert dt.isoformat().startswith("2026-08-12T10:30:00")
