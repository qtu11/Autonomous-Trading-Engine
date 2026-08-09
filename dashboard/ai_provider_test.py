"""AI provider connectivity test with actionable error classification.

Used by the Control Center "Test" button before saving a provider config.
Returns a structured result so the UI can explain the exact failure:
  - invalid key (401/403)
  - wrong model (404)
  - quota / insufficient credits (429 / 402)
  - bad URL / network (connection/dns/timeout)
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# provider key_type -> (default base url, does it speak Anthropic /messages shape)
PROVIDER_PRESETS: dict[str, dict] = {
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "anthropic": False,
        "hint": "Gemini (Google AI Studio / Vertex)",
    },
    "claude": {
        "url": "https://api.anthropic.com/v1/messages",
        "anthropic": True,
        "hint": "Anthropic Claude",
    },
    "deepseek": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "anthropic": False,
        "hint": "DeepSeek",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "anthropic": False,
        "hint": "OpenAI",
    },
    "zplay": {
        "url": "https://router.flatkey.ai/v1/chat/completions",
        "anthropic": False,
        "hint": "ZPlay / FlatKey router",
    },
    "grok": {
        "url": "https://api.x.ai/v1/chat/completions",
        "anthropic": False,
        "hint": "xAI Grok",
    },
    "qwen": {
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "anthropic": False,
        "hint": "Alibaba Qwen",
    },
    "opencode": {
        "url": "https://opencode.ai/zen/v1/chat/completions",
        "anthropic": False,
        "hint": "OpenCode Zen (free, no key required)",
    },
}


def classify_http_error(exc: urllib.error.HTTPError) -> tuple[str, str]:
    """Map an HTTP error to (code, human_readable_reason)."""
    status = exc.code
    body = ""
    try:
        body = exc.read().decode("utf-8", errors="replace")[:400]
    except Exception:
        pass
    detail = ""
    try:
        data = json.loads(body) if body else {}
        err = data.get("error", {})
        if isinstance(err, dict):
            detail = err.get("message") or err.get("code") or err.get("type") or ""
        elif isinstance(err, str):
            detail = err
        elif "message" in data:
            detail = str(data["message"])
        if isinstance(detail, str) and detail:
            detail = detail[:240]
    except Exception:
        detail = body[:240]

    hints = {
        400: ("BAD_REQUEST", "Yêu cầu sai (400). Thường do model/id không đúng chuẩn của nhà cung cấp."),
        401: ("INVALID_KEY", "API key SAI hoặc bị thu hồi (401 Unauthorized). Kiểm tra lại key trong mục API Keys."),
        403: ("KEY_FORBIDDEN", "API key bị TỪ CHỐI (403 Forbidden) - key không có quyền dùng model này hoặc bị chặn."),
        404: ("WRONG_MODEL", "Model không tồn tại hoặc sai tên (404 Not Found). Kiểm tra chính xác model ID của nhà cung cấp."),
        429: ("RATE_LIMITED", "Vượt giới hạn rate/quota (429) hết hạn mức miễn phí, thử lại sau hoặc nạp credit."),
        402: ("INSUFFICIENT_CREDITS", "Tài khoản không đủ tiền/quota cho model này (402 Payment Required)."),
        500: ("PROVIDER_ERROR", "Lỗi phía nhà cung cấp (500). Thử lại sau."),
        503: ("PROVIDER_UNAVAILABLE", "Nhà cung cấp đang bận/quá tải (503). Thử lại sau."),
    }
    code, base_msg = hints.get(status, (f"HTTP_{status}", f"Lỗi HTTP {status}."))
    if detail:
        base_msg = f"{base_msg} Chi tiết: {detail}"
    return code, base_msg


def check_provider_connection(
    key_type: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
    timeout: float = 20.0,
) -> dict:
    start = time.time()
    preset = PROVIDER_PRESETS.get(key_type) or PROVIDER_PRESETS["openai"]

    url = (base_url or "").strip() or str(preset.get("url") or "")
    is_anthropic = bool(preset.get("anthropic")) or "anthropic.com" in url

    url = url.rstrip("/")
    if is_anthropic:
        if not url.endswith("/messages"):
            url += "/messages"
    else:
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"

    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if api_key:
        if is_anthropic:
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    if is_anthropic:
        payload = json.dumps({
            "model": model,
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "reply with: ok"}],
        })
    else:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "reply with: ok"}],
            "max_tokens": 16,
        })

    req = urllib.request.Request(url, data=payload.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = int((time.time() - start) * 1000)
            body = resp.read().decode("utf-8", errors="replace")[:800]
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            usage = data.get("usage", {}) or {}
            return {
                "ok": True,
                "message": f"Kết nối thành công ({latency_ms}ms) - model '{model}' phản hồi OK.",
                "latency_ms": latency_ms,
                "status_code": resp.status,
                "error_code": None,
                "model_used": model,
                "usage": usage,
            }
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.time() - start) * 1000)
        code, reason = classify_http_error(exc)
        return {
            "ok": False,
            "message": reason,
            "latency_ms": latency_ms,
            "status_code": exc.code,
            "error_code": code,
            "model_used": model,
        }
    except urllib.error.URLError as exc:
        reason = str(exc.reason)
        if "Name or service not known" in reason or "getaddrinfo" in reason.lower():
            code, hint = "DNS_ERROR", "URL/domain không phân giải được - kiểm tra lại base_url (gõ sai host?)."
        elif "timed out" in reason.lower() or "timeout" in reason.lower():
            code, hint = "TIMEOUT", f"Timeout sau {int(timeout)}s. Server chậm hoặc không tới được, thử base_url khác."
        elif "Connection refused" in reason.lower():
            code, hint = "CONNECTION_REFUSED", "Kết nối bị từ chối - cổng/URL không đúng, hoặc firewall chặn."
        elif "certificate" in reason.lower():
            code, hint = "TLS_ERROR", "Lỗi SSL/TLS - URL không hợp lệ (thiếu https:// hoặc certificate lỗi)."
        else:
            code, hint = "NETWORK_ERROR", f"Lỗi mạng: {reason}"
        return {
            "ok": False,
            "message": hint,
            "latency_ms": int((time.time() - start) * 1000),
            "status_code": None,
            "error_code": code,
            "model_used": model,
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Lỗi không xác định: {exc}",
            "latency_ms": int((time.time() - start) * 1000),
            "status_code": None,
            "error_code": "UNKNOWN_ERROR",
            "model_used": model,
        }