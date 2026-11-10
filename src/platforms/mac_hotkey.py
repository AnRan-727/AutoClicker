# -*- coding: utf-8 -*-
"""
macOS 全局快捷键（替代 pynput）
pynput 在后台线程调用 TSMGetInputSourceProperty，新版 macOS 会直接杀进程闪退。
这里用 NSEvent 全局/本地监听，在主线程注册、按物理键码匹配，不调用输入法接口。
start()/stop() 必须在主线程（Tk 线程）调用。全局监听需要「输入监控」权限。
"""

# 物理键码（与键盘布局无关，按美式键位）
KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26,
    "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47, "`": 50,
    "enter": 36, "return": 36, "tab": 48, "space": 49, "backspace": 51, "delete": 51,
    "esc": 53, "escape": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "left": 123, "right": 124, "down": 125, "up": 126,
}
MODS = {
    "shift": 1 << 17,
    "ctrl": 1 << 18, "control": 1 << 18,
    "alt": 1 << 19, "option": 1 << 19, "opt": 1 << 19,
    "cmd": 1 << 20, "command": 1 << 20,
}
MOD_MASK = (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20)
KEY_DOWN_MASK = 1 << 10   # NSEventMaskKeyDown


def parse(spec):
    """'<ctrl>+<shift>+s' / '<cmd>+<alt>+x' / '<f8>' → (keycode, modifier_flags)"""
    keycode, mods = None, 0
    for part in spec.lower().replace(" ", "").split("+"):
        name = part.strip("<>")
        if not name:
            continue
        if name in MODS:
            mods |= MODS[name]
        elif name in KEYCODES and keycode is None:
            keycode = KEYCODES[name]
        else:
            raise ValueError(f"无法识别的按键：{part}")
    if keycode is None:
        raise ValueError("快捷键里缺少主键（例如 s、x、<f8>）")
    return keycode, mods


class GlobalHotkey:
    """全局快捷键：任何软件在前台都生效。
    主方案：CGEventTap（只监听、不拦截）跑在独立线程自己的 CFRunLoop 上，只读键码和修饰键，
            不调用输入法接口（pynput 闪退的原因），需要「输入监控」权限。
    兜底：创建失败（未授权）时退回 NSEvent 监听，只保证本软件在前台时可用。
    start()/stop() 在主线程调用；回调在监听线程触发，回调内只能做线程安全的事。"""

    def __init__(self, spec, callback):
        self.keycode, self.mods = parse(spec)
        self.callback = callback
        self.mode = None          # "global" / "local"
        self._tap = None
        self._loop = None
        self._thread = None
        self._cb_ref = None
        self._monitors = []
        self._handlers = []

    # ---------- CGEventTap
    def _start_tap(self):
        import threading
        import Quartz
        import CoreFoundation as CF

        def tap_cb(proxy, etype, event, refcon):
            try:
                if etype in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
                    if self._tap is not None:
                        Quartz.CGEventTapEnable(self._tap, True)   # 被系统暂停后重新启用
                elif etype == Quartz.kCGEventKeyDown:
                    code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                    rep = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventAutorepeat)
                    flags = int(Quartz.CGEventGetFlags(event)) & MOD_MASK
                    if code == self.keycode and flags == self.mods and not rep:
                        self.callback()
            except Exception:
                pass
            return event

        self._cb_ref = tap_cb
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown), tap_cb, None)
        if tap is None:
            return False           # 没有「输入监控」权限
        self._tap = tap
        source = CF.CFMachPortCreateRunLoopSource(None, tap, 0)
        ready = threading.Event()

        def run():
            self._loop = CF.CFRunLoopGetCurrent()
            CF.CFRunLoopAddSource(self._loop, source, CF.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            ready.set()
            CF.CFRunLoopRun()

        self._thread = threading.Thread(target=run, name="GlobalHotkeyTap", daemon=True)
        self._thread.start()
        ready.wait(2)
        return True

    def _stop_tap(self):
        if self._tap is None:
            return
        try:
            import Quartz
            import CoreFoundation as CF
            Quartz.CGEventTapEnable(self._tap, False)
            if self._loop is not None:
                CF.CFRunLoopStop(self._loop)
            CF.CFMachPortInvalidate(self._tap)
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._tap = self._loop = self._thread = self._cb_ref = None

    # ---------- NSEvent 兜底
    def _start_nsevent(self):
        from AppKit import NSEvent

        def match(ev):
            try:
                if ev.keyCode() == self.keycode and (int(ev.modifierFlags()) & MOD_MASK) == self.mods \
                        and not ev.isARepeat():
                    self.callback()
            except Exception:
                pass

        def local_handler(ev):
            match(ev)
            return ev

        self._handlers = [match, local_handler]
        g = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(KEY_DOWN_MASK, match)
        l = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(KEY_DOWN_MASK, local_handler)
        self._monitors = [m for m in (g, l) if m is not None]

    def _stop_nsevent(self):
        if not self._monitors:
            return
        from AppKit import NSEvent
        for m in self._monitors:
            try:
                NSEvent.removeMonitor_(m)
            except Exception:
                pass
        self._monitors = []
        self._handlers = []

    # ---------- 对外接口
    def start(self):
        try:
            ok = self._start_tap()
        except Exception:
            ok = False
        if ok:
            self.mode = "global"
        else:
            self._start_nsevent()
            self.mode = "local"
        return self.mode

    def stop(self):
        self._stop_tap()
        self._stop_nsevent()
        self.mode = None


# ---------------------------------------------------------------- 快捷键录制
_CODE_TO_NAME = {}
for _name, _code in KEYCODES.items():
    _CODE_TO_NAME.setdefault(_code, _name)
_MOD_ORDER = [("ctrl", 1 << 18), ("alt", 1 << 19), ("shift", 1 << 17), ("cmd", 1 << 20)]   # ⌃⌥⇧⌘
FUNCTION_KEYS = {KEYCODES[f"f{i}"] for i in range(1, 13)}
ESC, BACKSPACE = KEYCODES["esc"], KEYCODES["backspace"]


def to_spec(keycode, flags):
    """(键码, 修饰键) → '<ctrl>+<shift>+s'；不支持的键返回 None"""
    name = _CODE_TO_NAME.get(keycode)
    if name is None:
        return None
    parts = [f"<{m}>" for m, bit in _MOD_ORDER if flags & bit]
    parts.append(f"<{name}>" if len(name) > 1 else name)
    return "+".join(parts)


class KeyRecorder:
    """在本软件窗口内捕获下一次按键（吞掉该按键，不会输入到其它控件）。主线程调用。"""

    def __init__(self, on_key, widget=None):
        self.on_key = on_key       # on_key(keycode, modifier_flags)；widget 仅 Windows 使用
        self._monitor = None
        self._handler = None

    def start(self):
        from AppKit import NSEvent

        def handler(ev):
            try:
                self.on_key(int(ev.keyCode()), int(ev.modifierFlags()) & MOD_MASK)
            except Exception:
                pass
            return None            # 吞掉按键

        self._handler = handler
        self._monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(KEY_DOWN_MASK, handler)

    def stop(self):
        if self._monitor is not None:
            from AppKit import NSEvent
            try:
                NSEvent.removeMonitor_(self._monitor)
            except Exception:
                pass
        self._monitor = None
        self._handler = None


# ---------------------------------------------------------------- 界面文案 / 显示
MOD_HINT = "需要配合 ⌃ ⌥ ⇧ ⌘ 使用（F1~F12 可单独用）"
LOCAL_HINT = "请在 系统设置 → 隐私与安全性 → 输入监控 中打开 AutoClicker"

_MOD_SYMBOLS = {"ctrl": "⌃", "control": "⌃", "shift": "⇧", "alt": "⌥", "option": "⌥", "opt": "⌥",
                "cmd": "⌘", "command": "⌘"}
_KEY_SYMBOLS = {"esc": "Esc", "escape": "Esc", "enter": "↩", "return": "↩", "tab": "⇥", "space": "Space",
                "backspace": "⌫", "delete": "⌫", "left": "←", "right": "→", "up": "↑", "down": "↓"}


def pretty(spec):
    """'<ctrl>+<shift>+s' → '⌃⇧S'（按 macOS 习惯 ⌃⌥⇧⌘ 排序）"""
    order = {"⌃": 0, "⌥": 1, "⇧": 2, "⌘": 3}
    mods, keys = [], []
    for p in spec.split("+"):
        n = p.strip().strip("<>").lower()
        if n in _MOD_SYMBOLS:
            mods.append(_MOD_SYMBOLS[n])
        elif n:
            keys.append(_KEY_SYMBOLS.get(n, n.upper()))
    return "".join(sorted(set(mods), key=order.get)) + "".join(keys)
