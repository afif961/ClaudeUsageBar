"""Claude Usage — macOS menu bar item showing your Claude plan usage %.

By Afif Tabish.

Shows the current 5-hour session usage next to the battery icon, with the
weekly limits and reset times in its menu. Same numbers as `/usage` in
Claude Code. Refreshes every minute.

It uses the login Claude Code already saved on this Mac (Keychain item
"Claude Code-credentials") and only sends it to api.anthropic.com. The token
is never written to disk or logged. If the login has expired, open Claude
Code once and it renews it.

Set CLAUDE_USAGE_MOCK=1 to run with sample numbers (no login used).
"""
import fcntl
import json
import math
import os
import plistlib
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import objc
from AppKit import (
    NSApplication, NSApplicationActivationPolicyAccessory, NSAttributedString, NSBezierPath,
    NSColor, NSFont, NSFontAttributeName, NSForegroundColorAttributeName, NSImage, NSImageLeft,
    NSMakeRect, NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength,
)
from Foundation import NSObject, NSTimer, NSUserDefaults
from PyObjCTools import AppHelper

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
SETTINGS_PAGE = "https://claude.ai/settings/usage"
REFRESH_SECONDS = 300          # the usage endpoint rate-limits per-minute polling
MAX_BACKOFF_SECONDS = 1800     # longest wait after repeated "too many requests"
APP_VERSION = "1.0.3"
AUTHOR = "Afif Tabish"
MOCK = os.environ.get("CLAUDE_USAGE_MOCK") == "1"
FROZEN = getattr(sys, "frozen", False)          # True in the shareable, self-contained app
LOG_FILE = Path.home() / "Library" / "Logs" / "ClaudeUsage.log"
AGENT_LABEL = "local.claude-usage-bar"
AGENT_FILE = Path.home() / "Library" / "LaunchAgents" / (AGENT_LABEL + ".plist")
LOCK_FILE = Path.home() / "Library" / "Application Support" / "Claude Usage" / "running.lock"

# (api field, menu label)
LIMITS = [
    ("five_hour", "Current session (5h)"),
    ("seven_day", "Weekly — all models"),
    ("seven_day_opus", "Weekly — Opus"),
    ("seven_day_sonnet", "Weekly — Sonnet"),
]


# ── Data ─────────────────────────────────────────────────────────────────────

def _ssl_context():
    """Verify against macOS's own CA bundle. A bundled (PyInstaller) Python's
    OpenSSL otherwise looks for certificates at the path of the machine that
    built it, which doesn't exist on other Macs, so every request fails."""
    system_bundle = "/etc/ssl/cert.pem"
    if os.path.exists(system_bundle):
        return ssl.create_default_context(cafile=system_bundle)
    return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()


class LoginError(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, retry_after=None):
        super().__init__()
        self.retry_after = retry_after   # seconds, when the server says


def _access_token():
    """Claude Code's OAuth access token from the Keychain (or its file fallback)."""
    raw = None
    try:
        raw = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        pass
    if not raw:
        f = Path.home() / ".claude" / ".credentials.json"
        raw = f.read_text() if f.exists() else ""
    try:
        token = json.loads(raw)["claudeAiOauth"]["accessToken"]
    except Exception:
        raise LoginError("No Claude login found — open Claude Code and log in")
    return token


def fetch_usage():
    if MOCK:
        now = datetime.now(timezone.utc).timestamp()
        iso = lambda h: datetime.fromtimestamp(now + h * 3600, timezone.utc).isoformat()
        return {"five_hour": {"utilization": 42.0, "resets_at": iso(2.3)},
                "seven_day": {"utilization": 18.0, "resets_at": iso(80)},
                "seven_day_opus": {"utilization": 7.0, "resets_at": iso(80)}}
    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": "Bearer " + _access_token(),
        "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json",
        "User-Agent": "claude-usage-bar/1.0.3",
    })
    try:
        with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise LoginError("Login expired — open Claude Code to renew it")
        if e.code == 429:
            try:
                retry_after = int(e.headers.get("Retry-After", ""))
            except ValueError:   # missing, or an HTTP date rather than seconds
                retry_after = None
            raise RateLimited(retry_after)
        raise


def _pct(block):
    try:
        return float(block.get("utilization"))
    except Exception:
        return None


def _reset_time(block):
    try:
        return datetime.fromisoformat(str(block["resets_at"]).replace("Z", "+00:00"))
    except Exception:
        return None


def _countdown(block):
    """'2h 15m' until reset, '' if unknown."""
    t = _reset_time(block)
    if not t:
        return ""
    secs = max(0, (t - datetime.now(timezone.utc)).total_seconds())
    d, h, m = int(secs // 86400), int(secs % 86400 // 3600), int(secs % 3600 // 60)
    if d:
        return f"{d}d {h}h"
    return f"{h}h {m}m" if h else f"{m}m"


def _reset_text(block):
    t = _reset_time(block)
    if not t:
        return ""
    when = t.astimezone().strftime("%a %-I:%M %p")
    return f"resets in {_countdown(block)}  ({when})"


# ── Icon ─────────────────────────────────────────────────────────────────────

def _burst_icon(size=16.0):
    """A small starburst drawn as a template image (follows light/dark menu bar)."""
    img = NSImage.alloc().initWithSize_((size, size))
    img.lockFocus()
    NSColor.blackColor().set()
    c, rays = size / 2, 10
    for i in range(rays):
        a = math.pi * 2 * i / rays + math.pi / 2
        inner, outer = 1.6, c - 0.6
        p = NSBezierPath.bezierPath()
        p.setLineWidth_(1.9)
        p.setLineCapStyle_(1)  # round
        p.moveToPoint_((c + inner * math.cos(a), c + inner * math.sin(a)))
        p.lineToPoint_((c + outer * math.cos(a), c + outer * math.sin(a)))
        p.stroke()
    img.unlockFocus()
    img.setTemplate_(True)
    return img


# ── Menu bar app ─────────────────────────────────────────────────────────────

class UsageBar(NSObject):

    def init(self):
        self = objc.super(UsageBar, self).init()
        self.defaults = NSUserDefaults.standardUserDefaults()
        self.data, self.error, self.updated = None, None, None
        self.backoff, self.timer, self.busy = 0, None, False
        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        btn = self.item.button()
        btn.setImage_(_burst_icon())
        btn.setImagePosition_(NSImageLeft)
        btn.setToolTip_("Claude usage")
        self._set_title("…")
        self.menu = NSMenu.alloc().init()
        self.menu.setAutoenablesItems_(False)
        self.item.setMenu_(self.menu)
        self._build_menu()
        self.refresh_(None)   # each check schedules the next one when it finishes
        # tick the reset countdown every 30 s without calling the API
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            30, self, "tick:", None, True)
        return self

    # title in the menu bar
    @objc.python_method
    def _set_title(self, text, pct=None):
        color = NSColor.controlTextColor()
        if pct is not None and pct >= 90:
            color = NSColor.systemRedColor()
        elif pct is not None and pct >= 75:
            color = NSColor.systemOrangeColor()
        attrs = {NSFontAttributeName: NSFont.monospacedDigitSystemFontOfSize_weight_(13, 0.0),
                 NSForegroundColorAttributeName: color}
        self.item.button().setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(" " + text, attrs))

    @objc.python_method
    def _show_weekly(self):
        return bool(self.defaults.boolForKey_("showWeekly"))

    @objc.python_method
    def _add(self, title, action=None, enabled=True, key=""):
        mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
        if action:
            mi.setTarget_(self)
        mi.setEnabled_(enabled)
        self.menu.addItem_(mi)
        return mi

    @objc.python_method
    def _build_menu(self):
        self.menu.removeAllItems()
        if self.error:
            self._add("⚠︎ " + self.error, enabled=False)
        if self.data:
            for key, label in LIMITS:
                block = self.data.get(key)
                pct = _pct(block) if isinstance(block, dict) else None
                if pct is None:
                    continue
                bar = "▰" * round(pct / 10) + "▱" * (10 - round(pct / 10))
                self._add(f"{label}:  {pct:.0f}%", enabled=False)
                sub = self._add(f"     {bar}   {_reset_text(block)}", enabled=False)
                sub.setIndentationLevel_(1)
        elif not self.error:
            self._add("Loading…", enabled=False)
        self.menu.addItem_(NSMenuItem.separatorItem())
        if self.updated:
            self._add("Updated " + self.updated.strftime("%-I:%M %p"), enabled=False)
        self._add("Refresh now", "refresh:", key="r")
        weekly = self._add("Show weekly % in menu bar", "toggleWeekly:")
        weekly.setState_(1 if self._show_weekly() else 0)
        login = self._add("Start at login", "toggleLogin:")
        login.setState_(1 if start_at_login_enabled() else 0)
        self._add("Open usage page…", "openSettings:")
        self.menu.addItem_(NSMenuItem.separatorItem())
        self._add("About Claude Usage…", "about:")
        self._add(f"Made by {AUTHOR}", enabled=False)
        self._add("Quit Claude Usage", "quit:", key="q")

    @objc.python_method
    def _render(self):
        if self.data:
            s = _pct(self.data.get("five_hour") or {})
            w = _pct(self.data.get("seven_day") or {})
            text = f"{s:.0f}%" if s is not None else "—"
            left = _countdown(self.data.get("five_hour") or {})
            if left:
                text += f" · {left}"
            if self._show_weekly() and w is not None:
                text += f"  |  wk {w:.0f}%"
            self._set_title(text, max(x for x in (s, w, 0) if x is not None))
        else:
            self._set_title("—")
        self._build_menu()

    # actions
    def refresh_(self, _):
        if self.busy:   # "Refresh now" while a check is already running
            return
        self.busy = True
        if self.timer:
            self.timer.invalidate()
            self.timer = None

        def work():
            detail, limited, retry_after = None, False, None
            try:
                data, err = fetch_usage(), None
            except LoginError as e:
                data, err = None, str(e)
            except RateLimited as e:
                data, err = None, "Checking too often — showing last values, will retry"
                limited, retry_after = True, e.retry_after
            except Exception as e:
                data, err = None, "Can't reach Claude — showing last known values"
                detail = f"{type(e).__name__}: {e}"
            AppHelper.callAfter(self._done, data, err, detail, limited, retry_after)
        threading.Thread(target=work, daemon=True).start()

    @objc.python_method
    def _done(self, data, err, detail=None, limited=False, retry_after=None):
        self.busy = False
        # back off on "too many requests" (5, 10, 20, then 30 min) so retries don't keep it limited
        if limited:
            self.backoff = min(MAX_BACKOFF_SECONDS, max(REFRESH_SECONDS, self.backoff * 2))
            delay = max(retry_after or 0, self.backoff)
            detail = f"next check in {delay // 60} min"
        else:
            self.backoff, delay = 0, REFRESH_SECONDS
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            delay, self, "refresh:", None, False)
        # log only when the state changes, so a lasting failure isn't written on every check
        if err != self.error or (data and self.updated is None):
            _log("Usage check failed: " + err + (f" ({detail})" if detail else "") if err
                 else "Usage loaded")
        if data:
            self.data, self.updated = data, datetime.now()
        self.error = err
        self._render()

    def tick_(self, _):
        self._render()

    def toggleWeekly_(self, _):
        self.defaults.setBool_forKey_(not self._show_weekly(), "showWeekly")
        self._render()

    def toggleLogin_(self, _):
        try:
            set_start_at_login(not start_at_login_enabled())
        except OSError as e:
            _log(f"Could not change start at login: {e}")
        self._build_menu()

    def openSettings_(self, _):
        webbrowser.open(SETTINGS_PAGE)

    def about_(self, _):
        app = NSApplication.sharedApplication()
        app.activateIgnoringOtherApps_(True)   # menu bar apps have no window to come forward with
        app.orderFrontStandardAboutPanelWithOptions_({
            "ApplicationName": "Claude Usage",
            "ApplicationVersion": APP_VERSION,
            "Version": "",
            "Copyright": f"© {datetime.now().year} {AUTHOR}",
            "Credits": NSAttributedString.alloc().initWithString_(f"Created by {AUTHOR}"),
        })

    def quit_(self, _):
        _log("Quit from menu")
        NSApplication.sharedApplication().terminate_(None)


def _log(msg):
    line = datetime.now().isoformat(timespec="seconds") + " " + msg
    if FROZEN:   # no terminal: write the log file directly
        try:
            with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass
    else:
        print(line, flush=True)


def _launcher_path():
    if FROZEN:
        return sys.executable
    return "/Applications/Claude Usage.app/Contents/MacOS/ClaudeUsage"


def start_at_login_enabled():
    return AGENT_FILE.exists()


def set_start_at_login(on):
    """Login item via a per-user LaunchAgent; restarts the app if it crashes, not after Quit."""
    if on:
        AGENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENT_FILE, "wb") as f:
            plistlib.dump({
                "Label": AGENT_LABEL,
                "ProgramArguments": [_launcher_path()],
                "RunAtLoad": True,
                "KeepAlive": {"SuccessfulExit": False},
                "ProcessType": "Interactive",
            }, f)
    elif AGENT_FILE.exists():
        AGENT_FILE.unlink()


_lock = None


def _already_running():
    global _lock
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    _lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


def main():
    import atexit, sys, traceback
    if _already_running():
        return   # another copy is already in the menu bar
    _log("Claude Usage started" + (" (sample data)" if MOCK else ""))
    atexit.register(lambda: _log("Claude Usage stopped"))
    sys.excepthook = lambda *e: _log("Error: " + "".join(traceback.format_exception(*e)))

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon
    bar = UsageBar.alloc().init()  # noqa: F841 — kept alive by the run loop
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
