"""Firestore best-effort cloud sync for Control Center configuration.

Design goals (per Chairman):
  * Never lose data: local user_control_config.json is the ground truth. Every
    write goes to the file first, then attempts to mirror to Firestore.
  * Always in sync: a merge strategy reads the newest document from Firestore
    (by updated_at) when network + rules permit, and uses the file otherwise.
  * Realtime: the WebSocket broadcaster (server.py) fans out a
    config_updated event to every connected dashboard after each save.

Auth strategy (priority order):
  1. FIREBASE_SERVICE_ACCOUNT_JSON (base64 service-account key) — best.
  2. OAuth user token from firebase-tools configstore (requires `firebase login`)
     — works with rules `request.auth != null`.
  3. FIREBASE_API_KEY + FIREBASE_PROJECT_ID with anonymous Identity Toolkit signIn
     — requires Anonymous sign-in provider + permissive Firestore rules.

Nothing here blocks startup or a save: every cloud call is best-effort.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from typing import Any

import requests

# BUG FIX: trước đây mọi lỗi cloud đều bị nuốt im lặng (except Exception: return
# False/None) nên operator không bao giờ biết Firestore sync đang chết. Giờ log
# warning ở tầng public để chẩn đoán.
logger = logging.getLogger("firebase_sync")

# ── Public helpers (all auth styles) ────────────────────────────────────────────

def is_configured() -> bool:
    return bool(service_account_ready() or oauth_user_ready() or web_api_key_ready())


def service_account_ready() -> bool:
    try:
        cred = _service_account_credentials()
        return cred is not None
    except Exception:
        return False


def oauth_user_ready() -> bool:
    """Check if firebase-tools OAuth user token is available."""
    return _oauth_user_access_token() is not None


_pull_cache: dict[str, Any] = {"ts": 0.0, "data": None}
_PULL_TTL_SECONDS = 15.0
_PUSH_LOCK = threading.Lock()


def pull_config() -> dict[str, Any] | None:
    """Fetch the doc from Firestore; None if unreachable/disabled. Cached."""
    now = time.time()
    if now - _pull_cache["ts"] < _PULL_TTL_SECONDS:
        return _pull_cache["data"]
    if not is_configured():
        return None
    try:
        if service_account_ready():
            result = _pull_with_admin()
        elif oauth_user_ready():
            result = _pull_with_oauth_user()
        else:
            result = _pull_with_rest_anonymous()
    except Exception as exc:
        logger.warning("pull_config failed: %s", exc)
        result = None
    _pull_cache["ts"] = time.time()
    _pull_cache["data"] = result
    return result


def push_config(data: dict[str, Any]) -> bool:
    """Best-effort push of the control config to Firestore 'control_center/config' doc."""
    if not is_configured():
        return False
    with _PUSH_LOCK:
        try:
            _pull_cache["ts"] = 0.0  # invalidate so next pull re-reads cloud
            if service_account_ready():
                return _push_with_admin(data)
            elif oauth_user_ready():
                return _push_with_oauth_user(data)
            return _push_with_rest_anonymous(data)
        except Exception as exc:
            logger.warning("push_config failed: %s", exc)
            return False


# ── Service Account (firebase_admin) ───────────────────────────────────────────

def _service_account_credentials():
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        return None
    import json as _json
    try:
        return _json.loads(base64.b64decode(raw.encode()).decode("utf-8"))
    except Exception:
        return None


def _push_with_admin(data: dict[str, Any]) -> bool:
    from firebase_admin import credentials, firestore, initialize_app
    cred = credentials.Certificate(_service_account_credentials())
    app = initialize_app(cred, name="ate-control-config", options={"projectId": _project_id()})
    db = firestore.client(app)
    db.collection("control_center").document("config").set(data, merge=True)
    return True


def _pull_with_admin() -> dict[str, Any] | None:
    from firebase_admin import credentials, firestore, initialize_app
    cred = credentials.Certificate(_service_account_credentials())
    app = initialize_app(cred, name="ate-control-config-pull")
    db = firestore.client(app)
    doc = db.collection("control_center").document("config").get()
    return dict(doc.to_dict() or {})


# ── OAuth User Token (firebase-tools configstore) ──────────────────────────────

def _read_firebase_configstore() -> dict[str, Any]:
    """Read ~/.config/configstore/firebase-tools.json and return parsed JSON."""
    import pathlib
    path = pathlib.Path.home() / ".config" / "configstore" / "firebase-tools.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("firebase-tools configstore not readable: %s", exc)
        return {}


def _oauth_user_access_token() -> str | None:
    """Return current access_token from firebase-tools configstore, or None."""
    cfg = _read_firebase_configstore()
    return cfg.get("tokens", {}).get("access_token")


def _firestore_base() -> str:
    return f"https://firestore.googleapis.com/v1/projects/{_project_id()}/databases/(default)/documents"


def _project_id() -> str:
    return os.getenv("FIREBASE_PROJECT_ID", "").strip()


def _push_with_oauth_user(data: dict[str, Any]) -> bool:
    token = _oauth_user_access_token()
    if not token:
        return False
    url = f"{_firestore_base()}/control/config"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"fields": _data_to_fields(data)}
    resp = requests.patch(url, json=payload, headers=headers, timeout=30)
    if resp.status_code in (200, 201, 204):
        return True
    url2 = f"{_firestore_base()}/control?documentId=config"
    resp2 = requests.post(url2, json={"fields": _data_to_fields(data)}, headers=headers, timeout=30)
    return resp2.status_code in (200, 201, 204)


def _pull_with_oauth_user() -> dict[str, Any] | None:
    token = _oauth_user_access_token()
    if not token:
        return None
    url = f"{_firestore_base()}/control/config"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        return None
    return _fields_to_data(resp.json().get("fields")) or {}


# ── Anonymous REST (web API key) ──────────────────────────────────────────────

def _beta_api_key() -> str:
    return os.getenv("FIREBASE_API_KEY", os.getenv("NEXT_PUBLIC_FIREBASE_API_KEY", "")).strip()


def web_api_key_ready() -> bool:
    return bool(_project_id() and _beta_api_key())


def _id_token_via_anonymous() -> str | None:
    """Identity Toolkit anonymous sign-in; yields an ID token for rules."""
    import requests
    url = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
    try:
        resp = requests.post(url, params={"key": _beta_api_key()},
                             json={"returnSecureToken": True},
                             timeout=6)
        if resp.status_code != 200:
            resp2 = requests.post(url, json={"apikey": _beta_api_key(), "returnSecureToken": True}, timeout=6)
            if resp2.status_code != 200:
                return None
            data = resp2.json()
        else:
            data = resp.json()
        return data.get("idToken")
    except Exception as exc:
        logger.warning("anonymous sign-in failed: %s", exc)
        return None


def _push_with_rest_anonymous(data: dict[str, Any]) -> bool:
    import requests
    token = _id_token_via_anonymous()
    if not token:
        return False
    url = f"{_firestore_base()}/control/config"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"fields": _data_to_fields(data)}
    resp = requests.patch(url, json=payload, headers=headers, timeout=30)
    if resp.status_code in (200, 201, 204):
        return True
    url2 = f"{_firestore_base()}/control?documentId=config"
    resp2 = requests.post(url2, json={"fields": _data_to_fields(data)}, headers=headers, timeout=30)
    return resp2.status_code in (200, 201, 204)


def _pull_with_rest_anonymous() -> dict[str, Any] | None:
    import requests
    token = _id_token_via_anonymous()
    if not token:
        return None
    url = f"{_firestore_base()}/control/config"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        return None
    return _fields_to_data(resp.json().get("fields")) or {}


# Field value helpers ------------------------------------------------------------

def _field_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, dict):
        return {"mapValue": {"fields": _data_to_fields(value)}}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_field_value(v) for v in value]}}
    if isinstance(value, str):
        return {"stringValue": value}
    if value is None:
        return {"nullValue": None}
    return {"stringValue": str(value)}


def _data_to_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {k: _field_value(v) for k, v in data.items()}


def _fields_to_data(fields: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, dtype in (fields or {}).items():
        if "stringValue" in dtype:
            out[key] = dtype["stringValue"]
        elif "integerValue" in dtype:
            out[key] = int(dtype["integerValue"])
        elif "doubleValue" in dtype:
            out[key] = float(dtype["doubleValue"])
        elif "booleanValue" in dtype:
            out[key] = dtype["booleanValue"]
        elif "nullValue" in dtype:
            out[key] = None
        elif "arrayValue" in dtype:
            out[key] = [_fields_to_data({"x": it})["x"] for it in dtype.get("arrayValue", {}).get("values", [])]
        elif "mapValue" in dtype:
            out[key] = _fields_to_data(dtype.get("mapValue", {}).get("fields", {}))
    return out