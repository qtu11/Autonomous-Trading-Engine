"""Unit tests for Control Center execution endpoints (mode / kill-switch /
demo-arm). BUG FIX: các route này từng bị thiếu ở backend -> frontend proxy 404.
Test xác nhận endpoint hoạt động + fail-closed (401 không token, 400 body sai)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from server import _config, app  # noqa: E402

_AUTH = {"Authorization": "Bearer test-token"}


def _snapshot():
    return {
        "execution_mode": _config.get("execution_mode"),
        "kill_switch": _config.get("kill_switch"),
        "demo_armed": _config.get("demo_armed"),
    }


def _restore(snap):
    _config["execution_mode"] = snap["execution_mode"]
    _config["kill_switch"] = snap["kill_switch"]
    _config["demo_armed"] = snap["demo_armed"]


def test_mode_requires_auth():
    with TestClient(app) as client:
        r = client.post("/api/control-center/mode", json={"mode": "DEMO"})
        assert r.status_code == 401


def test_mode_accepts_valid_values():
    snap = _snapshot()
    try:
        with TestClient(app) as client:
            for mode in ("DEMO", "LIVE", "DISABLED"):
                r = client.post("/api/control-center/mode", json={"mode": mode}, headers=_AUTH)
                assert r.status_code == 200, r.text
                assert r.json()["mode"] == mode
                assert _config["execution_mode"] == mode
            # lowercase + spaces được chuẩn hoá
            r = client.post("/api/control-center/mode", json={"mode": " demo "}, headers=_AUTH)
            assert r.json()["mode"] == "DEMO"
    finally:
        _restore(snap)


def test_mode_rejects_unknown_value():
    snap = _snapshot()
    try:
        with TestClient(app) as client:
            r = client.post("/api/control-center/mode", json={"mode": "BOGUS"}, headers=_AUTH)
            assert r.status_code == 400
    finally:
        _restore(snap)


def test_kill_switch_boolean_coercion():
    """String \"false\" phải hiểu là False (không được bool('false') == True)."""
    snap = _snapshot()
    try:
        with TestClient(app) as client:
            r = client.post("/api/control-center/kill-switch", json={"active": "false"}, headers=_AUTH)
            assert r.status_code == 200
            assert r.json()["kill_switch_active"] is False
            assert _config["kill_switch"] is False

            r = client.post("/api/control-center/kill-switch", json={"active": "true"}, headers=_AUTH)
            assert r.json()["kill_switch_active"] is True
    finally:
        _restore(snap)


def test_demo_arm_default_true():
    snap = _snapshot()
    try:
        with TestClient(app) as client:
            r = client.post("/api/control-center/demo-arm", json={}, headers=_AUTH)
            assert r.status_code == 200
            assert r.json()["demo_armed"] is True
    finally:
        _restore(snap)


def test_non_object_body_rejected():
    snap = _snapshot()
    try:
        with TestClient(app) as client:
            r = client.post("/api/control-center/mode", json=[1, 2, 3], headers=_AUTH)
            assert r.status_code == 400
            r = client.post("/api/control-center/kill-switch", json="active", headers=_AUTH)
            assert r.status_code == 400
    finally:
        _restore(snap)


def test_status_reflects_changes():
    snap = _snapshot()
    try:
        with TestClient(app) as client:
            client.post("/api/control-center/mode", json={"mode": "LIVE"}, headers=_AUTH)
            client.post("/api/control-center/kill-switch", json={"active": True}, headers=_AUTH)
            # BUG FIX (SECURITY): /api/control-center/status giờ yêu cầu bridge token
            # (lộ balance/equity/login MT5) — không còn public như trước.
            r = client.get("/api/control-center/status")
            assert r.status_code == 401
            r = client.get("/api/control-center/status", headers=_AUTH)
            assert r.status_code == 200
            body = r.json()
            assert body["execution"]["mode"] == "LIVE"
            assert body["safeguards"]["kill_switch_active"] is True
    finally:
        _restore(snap)
