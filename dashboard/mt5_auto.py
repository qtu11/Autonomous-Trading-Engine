"""
MT5 terminal auto-deployment helpers.

Implements (best-effort, each step returns (ok, message)):
  1. locate_terminal64       - resolve terminal64.exe path
  2. connect_and_login       - launch terminal (if needed) + log into the given account
  3. copy_expert_to_data     - copy ATE_XAUUSD.ex5 into the Experts folder
  4. open_symbol_chart       - open a chart for the resolved symbol at the requested timeframe
  5. attach_expert_to_chart  - double-click the EA in the Navigator tree (UI automation)
  6. enable_algo_trading     - toggle the green "Algo Trading" button (UI automation)
  7. algo_state              - authoritative truth via mt5.terminal_info().trade_allowed

UI automation (steps 4-6) requires the optional `pywinauto` package. When it is
missing every UI step fails gracefully with a clear manual instruction instead of
silently pretending to succeed.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import winreg
from pathlib import Path

# BUG FIX: các lỗi registry/UI automation trước đây bị except im lặng -> không
# debug được khi MT5 auto-deploy fail. Log warning thay vì pass.
logger = logging.getLogger("mt5_auto")

try:
    import MetaTrader5 as mt5  # type: ignore
    MT5_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    mt5 = None
    MT5_AVAILABLE = False

try:
    import pywinauto  # type: ignore
    from pywinauto.application import Application
    PYWINAUTO_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    pywinauto = None
    Application = None
    PYWINAUTO_AVAILABLE = False

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

EXPERT_FILE = "ATE_XAUUSD.ex5"
EXPERT_DIR_NAME = "ATE_XAUUSD"

# MT5 chart period quick-keys (documented MetaTrader 5 shortcuts).
TIMEFRAME_KEYS: dict[str, str] = {
    "M1": "1",
    "M5": "5",
    "M15": "15",
    "M30": "30",
    "H1": "H",
    "H4": "4",
    "D1": "D",
    "W1": "W",
    "MN1": "MN",
}

PROGRAM_FILES_CANDIDATES = [
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
]

MAIN_WINDOW_TITLE_PATTERNS = [
    r"^.*MetaTrader.*$",
    r"^.*MT5.*$",
    r"^.*MetaTrader 5.*$",
]


# --------------------------------------------------------------------------- #
# Path / registry resolution
# --------------------------------------------------------------------------- #


def find_terminal64(explicit_path: str | None = None) -> tuple[bool, str | None, str]:
    """
    Locate terminal64.exe.

    explicit_path may be:
      - a direct path to terminal64.exe
      - a directory containing terminal64.exe (broker install dir)
      - empty/None -> registry lookup, then common Program Files scan
    """
    if explicit_path:
        p = Path(explicit_path)
        if p.is_file() and p.name.lower() == "terminal64.exe":
            return True, str(p), ""
        if p.is_dir():
            candidate = p / "terminal64.exe"
            if candidate.is_file():
                return True, str(candidate), ""
            return False, None, f"Không tìm thấy terminal64.exe trong thư mục: {explicit_path}"
        return False, None, f"Đường dẫn không hợp lệ (không phải file/thư mục): {explicit_path}"

    # 1) registry: HKCU\Software\MetaQuotes\Terminal\<hash>\TerminalPath
    try:
        base = r"Software\MetaQuotes\Terminal"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as k:
                        try:
                            tp, _ = winreg.QueryValueEx(k, "TerminalPath")
                        except FileNotFoundError:
                            continue
                    if tp and os.path.basename(str(tp)).lower() == "terminal64.exe" and os.path.isfile(tp):
                        return True, tp, ""
                except OSError as exc:
                    logger.debug("registry key read failed: %s", exc)
                    continue
    except OSError as exc:
        logger.warning("registry scan for terminal64 failed: %s", exc)

    # 2) Program Files scan (one level, name-based guess)
    for pf in PROGRAM_FILES_CANDIDATES:
        if not pf or not os.path.isdir(pf):
            continue
        for folder in os.listdir(pf):
            candidate = os.path.join(pf, folder, "terminal64.exe")
            if os.path.isfile(candidate):
                return True, candidate, ""
    return False, None, "Không tự tìm được terminal64.exe. Hãy nhập đường dẫn thủ công (VD: C:\\Program Files\\Exness MetaTrader 5\\terminal64.exe)."


def find_data_path() -> str | None:
    """Data folder from the currently running MT5 terminal (if any)."""
    if not MT5_AVAILABLE:
        return None
    try:
        if mt5.initialize(timeout=3000):
            info = mt5.terminal_info()
            if info is not None:
                return info.data_path
        return None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #


def connect_and_login(
    terminal64: str,
    login: str | None = None,
    password: str | None = None,
    server: str | None = None,
    timeout_ms: int = 90_000,
) -> tuple[bool, str, dict | None]:
    """Launch terminal64 (if needed) and log into the given account.

    Returns (ok, message, account_info_dict)."""
    if not MT5_AVAILABLE:
        return False, "MetaTrader5 (python module) chưa được cài. Chạy: pip install MetaTrader5", None

    kwargs: dict = {"path": terminal64, "timeout": timeout_ms}
    if login is not None and str(login).strip():
        kwargs["login"] = int(str(login).strip())
    if password:
        kwargs["password"] = password
    if server:
        kwargs["server"] = server

    try:
        ok = mt5.initialize(**kwargs)
    except Exception as exc:  # pragma: no cover
        return False, f"Lỗi khi gọi mt5.initialize: {exc}", None

    if not ok:
        err = mt5.last_error()
        return (
            False,
            f"Không thể kết nối/log vào terminal. MetaTrader5 last_error={err}. "
            "Kiểm tra: tài khoản/password/server đúng chưa, terminal đã đóng hẳn chưa (Ctrl+Shift+Esc kiểm tra tiến trình terminal64.exe).",
            None,
        )

    info = mt5.account_info()
    if info is None:
        return False, f"Kết nối terminal OK nhưng không lấy được thông tin tài khoản. last_error={mt5.last_error()}", None

    acc = {
        "login": info.login,
        "server": info.server,
        "company": info.company,
        "currency": info.currency,
        "balance": info.balance,
        "equity": info.equity,
        "leverage": info.leverage,
        "trade_allowed": bool(info.trade_allowed),
        "data_path": (mt5.terminal_info().data_path if mt5.terminal_info() else None),
    }
    return True, f"Đã kết nối tài khoản {info.login} @ {info.server}", acc


def copy_expert_to_data(data_path: str, source_expert: str | None = None) -> tuple[bool, str, str | None]:
    """
    Ensure ATE_XAUUSD.ex5 exists inside the MT5 data folder Experts folder.

    source_expert defaults to the .ex5 in the repo root. When the target already
    exists with a non-empty size the copy is skipped (keeps the newest compiled build
    intact unless the repo file is strictly newer).
    """
    if not data_path or not os.path.isdir(data_path):
        return False, f"Data folder không tồn tại: {data_path}", None

    experts_dir = os.path.join(data_path, "MQL5", "Experts")
    os.makedirs(experts_dir, exist_ok=True)
    target = os.path.join(experts_dir, EXPERT_FILE)

    if source_expert is None:
        repo_root = Path(__file__).resolve().parent.parent
        source_expert = str(repo_root / EXPERT_FILE)
        if not os.path.isfile(source_expert):
            return (
                False,
                f"Không tìm thấy file nguồn {EXPERT_FILE} tại {source_expert}. "
                "Hãy biên dịch ATE_XAUUSD.mq5 trong MetaEditor (F7) để sinh .ex5.",
                None,
            )

    if not os.path.isfile(source_expert):
        return False, f"File nguồn .ex5 không tồn tại: {source_expert}", None

    if os.path.isfile(target) and os.path.getsize(target) > 0:
        if os.path.getmtime(source_expert) > os.path.getmtime(target) + 2:
            shutil.copy2(source_expert, target)
            return True, f"Đã cập nhật {EXPERT_FILE} (file repo mới hơn).", target
        return True, f"File {EXPERT_FILE} đã có sẵn trong Experts (không cần copy).", target

    try:
        shutil.copy2(source_expert, target)
    except OSError as exc:
        return False, f"Copy {EXPERT_FILE} thất bại: {exc}", None
    return True, f"Đã copy {EXPERT_FILE} vào {target}", target


# --------------------------------------------------------------------------- #
# UI automation (optional)
# --------------------------------------------------------------------------- #


def _mt5_window(app: Application):
    """Find the main MT5 window by title pattern."""
    for pattern in MAIN_WINDOW_TITLE_PATTERNS:
        try:
            win = app.window(title_re=pattern)
            if win.exists(timeout=2):
                return win
        except Exception:
            continue
    return None


def open_symbol_chart(symbol: str, timeframe: str, terminal64: str) -> tuple[bool, str]:
    """Open a chart for `symbol` at `timeframe` on the MT5 terminal window."""
    if not PYWINAUTO_AVAILABLE:
        return (
            False,
            "Chưa cài pywinauto nên không thể tự mở chart. "
            "Chạy: pip install pywinauto  (hoặc tự mở chart thủ công: Nhấp đúp symbol trong Market Watch, chọn timeframe).",
        )
    try:
        app = Application(backend="uia").connect(path=terminal64)
    except Exception as exc:
        return False, f"Không tìm thấy cửa sổ MT5: {exc}"
    win = _mt5_window(app)
    if win is None:
        return False, "Không tìm thấy cửa sổ chính MetaTrader 5."

    key = TIMEFRAME_KEYS.get(timeframe.upper(), "H")
    try:
        win.set_focus()
        # Ctrl+U opens the Symbols search dialog; typing the symbol + Enter opens a new chart.
        win.send_keystrokes("^u")
        time.sleep(1.0)
        try:
            dlg = app.window(title_re="^.*Symbols.*$")
            if dlg.exists(timeout=2):
                dlg.set_focus()
                dlg.send_keystrokes(symbol, with_spaces=True)
                time.sleep(0.5)
                dlg.send_keystrokes("{ENTER}")
            else:
                win.send_keystrokes(symbol, with_spaces=True)
                win.send_keystrokes("{ENTER}")
        except Exception:
            win.send_keystrokes(symbol, with_spaces=True)
            win.send_keystrokes("{ENTER}")
        time.sleep(2.5)
        # Chart period quick-key (must be typed while the chart window is focused).
        win.send_keystrokes(key)
        time.sleep(1.0)
        return True, f"Đã mở chart {symbol} trên timeframe {timeframe} (nếu chưa có sẵn)."
    except Exception as exc:
        return False, f"Mở chart thất bại (UI): {exc}"


def attach_expert_to_chart(terminal64: str, expert_name: str = EXPERT_FILE) -> tuple[bool, str]:
    """Double-click the EA inside the Navigator tree -> attaches to active chart."""
    if not PYWINAUTO_AVAILABLE:
        return (
            False,
            "Chưa cài pywinauto nên không thể tự gắn EA. "
            "Thao tác thủ công: bấm Ctrl+N mở Navigator -> Expert Advisors -> nhấp đúp ATE_XAUUSD. "
            "Chạy: pip install pywinauto  để tự động hoá bước này.",
        )
    try:
        app = Application(backend="uia").connect(path=terminal64)
    except Exception as exc:
        return False, f"Không tìm thấy cửa sổ MT5: {exc}"
    win = _mt5_window(app)
    if win is None:
        return False, "Không tìm thấy cửa sổ chính MetaTrader 5."

    try:
        win.set_focus()
        # F5 or Ctrl+N opens the Navigator (Ctrl+N is the documented shortcut).
        win.send_keystrokes("^n")
        time.sleep(1.5)

        # Find any tree view containing our EA and double-click it.
        for tree in win.descendants(class_name="SysTreeView32", found_index=0, timeout=3):
            try:
                items = tree.get_items() if hasattr(tree, "get_items") else []
                for it in items:
                    txt = str(it.window_text()).lower()
                    if "expert" in txt or "advisor" in txt or "ea" in txt:
                        tree.expand(it)
                        for sub in tree.get_items():
                            if str(sub.window_text()).lower() == expert_name.lower():
                                sub.double_click_input()
                                return True, f"Đã gắn {expert_name} vào chart (double-click Navigator)."
            except Exception:
                continue

        # Fallback: send keystrokes on the tree after expanding the node.
        nav = win.child_window(class_name="SysTreeView32")
        if nav.exists(timeout=2):
            nav.set_focus()
            nav.type_keys("{DOWN}" * 3 + "{ENTER}")
            return True, "Đã thử gắn EA qua phím (hãy kiểm tra Navigator)."
    except Exception as exc:
        return False, f"Gắn EA thất bại (UI): {exc}"

    return False, "Không tìm thấy EA trong cây Navigator (có thể file .ex5 chưa được copy đúng chỗ)."


def enable_algo_trading(terminal64: str, expert_name: str = EXPERT_FILE) -> tuple[bool, str]:
    """
    Toggle the green 'Algo Trading' button via UI automation.

    Authoritative check afterwards via mt5.terminal_info().trade_allowed.
    """
    # Fast path: already enabled?
    if MT5_AVAILABLE and mt5.initialize(timeout=3000) and mt5.terminal_info() is not None:
        if mt5.terminal_info().trade_allowed:
            return True, "Algo Trading đã BẬT (trade_allowed=True)."

    if not PYWINAUTO_AVAILABLE:
        return (
            False,
            "Algo Trading chưa bật. Chưa cài pywinauto nên không tự bật được. "
            "Thao tác thủ công: bấm nút 'Algo Trading' (xanh lá) trên toolbar của MT5, "
            "hoặc chạy: pip install pywinauto",
        )

    try:
        app = Application(backend="uia").connect(path=terminal64)
    except Exception as exc:
        return False, f"Không tìm thấy cửa sổ MT5: {exc}"
    win = _mt5_window(app)
    if win is None:
        return False, "Không tìm thấy cửa sổ chính MetaTrader 5."

    candidates = ["Algo Trading", "AlgoTrading", "Algo", "Алго", "Автоторговля", "Giao dịch tự động", "Algotrading"]
    try:
        win.set_focus()
        for c in candidates:
            try:
                btn = win.descendants(title=c, control_type="Button")
                if btn:
                    btn[0].click_input()
                    time.sleep(1.5)
                    break
            except Exception as exc:
                logger.debug("algo button click failed (%s): %s", c, exc)
                continue
    except Exception as exc:
        logger.warning("UI automation for Algo Trading failed: %s", exc)

    # Verify truth via terminal_info.
    for _ in range(4):
        if MT5_AVAILABLE and mt5.initialize(timeout=3000) and mt5.terminal_info() is not None and mt5.terminal_info().trade_allowed:
            return True, "Algo Trading đã BẬT thành công (trade_allowed=True)."
        time.sleep(1.0)

    return (
        False,
        "Không tự bật được Algo Trading (UI automation không tìm thấy nút). "
        "Thao tác thủ công: bấm nút 'Algo Trading' (xanh lá) trên toolbar MT5.",
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def deploy_expert_to_chart(
    login: str,
    password: str,
    server: str,
    symbol: str,
    timeframe: str,
    terminal64_path: str | None = None,
    source_expert: str | None = None,
) -> dict:
    """
    Full deployment pipeline. Returns a report dict:

        {
          "ok": bool,
          "terminal64": ...,
          "account": {...} | None,
          "data_path": ...,
          "expert": {"ok": bool, "message": str, "path": ...},
          "chart": {"ok": bool, "message": str},
          "attach": {"ok": bool, "message": str},
          "algo": {"ok": bool, "message": str},
          "steps": [ { "name", "ok", "message" }, ... ],
          "symbol_info": {...},
        }
    """
    report: dict = {
        "ok": False,
        "terminal64": None,
        "account": None,
        "data_path": None,
        "expert": {"ok": False, "message": "", "path": None},
        "chart": {"ok": False, "message": ""},
        "attach": {"ok": False, "message": ""},
        "algo": {"ok": False, "message": ""},
        "steps": [],
    }

    def step(name: str, ok: bool, message: str) -> None:
        report["steps"].append({"name": name, "ok": bool(ok), "message": message})

    # 1) terminal64.exe
    ok, path, err = find_terminal64(terminal64_path)
    if not ok:
        step("locate_terminal64", False, err)
        return report
    report["terminal64"] = path
    step("locate_terminal64", True, f"terminal64.exe: {path}")

    # 2) launch + login
    ok, msg, acc = connect_and_login(path, login, password, server)
    step("connect_login", ok, msg)
    report["account"] = acc
    if not ok:
        return report
    report["data_path"] = acc.get("data_path")

    # 3) copy expert
    ok, msg, target = copy_expert_to_data(acc["data_path"] or "", source_expert)
    report["expert"] = {"ok": ok, "message": msg, "path": target}
    step("copy_expert", ok, msg)

    # 4) chart + timeframe
    ok, msg = open_symbol_chart(symbol, timeframe, path)
    report["chart"] = {"ok": ok, "message": msg}
    step("open_chart", ok, msg)

    # 5) attach EA
    ok, msg = attach_expert_to_chart(path)
    report["attach"] = {"ok": ok, "message": msg}
    step("attach_expert", ok, msg)

    # 6) algo trading
    ok, msg = enable_algo_trading(path)
    report["algo"] = {"ok": ok, "message": msg}
    step("enable_algo", ok, msg)

    all_critical = all(s["ok"] for s in report["steps"][:3])  # locate + login + copy
    report["ok"] = all_critical
    return report


def manual_checklist(report: dict) -> str:
    """Human-readable fallback instructions when UI steps could not run."""
    lines = []
    for s in report.get("steps", []):
        lines.append(f"[{'OK' if s['ok'] else '!!'}] {s['name']}: {s['message']}")
    return "\n".join(lines)
