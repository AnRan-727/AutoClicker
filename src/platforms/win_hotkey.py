# -*- coding: utf-8 -*-
"""
Windows 全局快捷键与快捷键录制（纯 ctypes，无第三方依赖）

- GlobalHotkey：RegisterHotKey 在独立线程注册，线程内跑消息循环，收到 WM_HOTKEY 回调。
  任何程序在前台都生效；组合键被其它程序占用时注册失败并抛出异常。
- KeyRecorder：录制时绑定窗口的 <KeyPress>，用虚拟键码 + GetAsyncKeyState 读取修饰键。

快捷键配置格式与 macOS 相同：'<ctrl>+<shift>+s'、'<alt>+<f8>'；'<cmd>' 在 Windows 上对应 Win 键。
"""
import ctypes
import sys
import threading

IS_WIN = sys.platform.startswith("win")

# 修饰键标志（RegisterHotKey 的 fsModifiers）
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
MODS = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT, "option": MOD_ALT, "opt": MOD_ALT,
    "shift": MOD_SHIFT,
    "cmd": MOD_WIN, "command": MOD_WIN, "win": MOD_WIN, "super": MOD_WIN,
}
MOD_MASK = MOD_ALT | MOD_CONTROL | MOD_SHIFT | MOD_WIN

# 虚拟键码
KEYCODES = {chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)}
KEYCODES.update({str(d): 0x30 + d for d in range(10)})
KEYCODES.update({f"f{i}": 0x6F + i for i in range(1, 13)})        # F1=0x70
KEYCODES.update({
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "esc": 0x1B, "escape": 0x1B,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "insert": 0x2D,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0,
    "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
})
FUNCTION_KEYS = {KEYCODES[f"f{i}"] for i in range(1, 13)}
ESC, BACKSPACE = KEYCODES["esc"], KEYCODES["backspace"]
# 单独按下修饰键时忽略（Shift/Ctrl/Alt/Win 及左右区分版本）
MODIFIER_VKS = {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x14}

_CODE_TO_NAME = {}
for _name, _code in KEYCODES.items():
    _CODE_TO_NAME.setdefault(_code, _name)
_MOD_ORDER = [("ctrl", MOD_CONTROL), ("alt", MOD_ALT), ("shift", MOD_SHIFT), ("cmd", MOD_WIN)]

WM_HOTKEY, WM_QUIT = 0x0312, 0x0012


def parse(spec):
    """'<ctrl>+<shift>+s' → (虚拟键码, 修饰键标志)"""
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


def to_spec(keycode, mods):
    """(虚拟键码, 修饰键标志) → '<ctrl>+<shift>+s'；不支持的键返回 None"""
    name = _CODE_TO_NAME.get(keycode)
    if name is None:
        return None
    parts = [f"<{m}>" for m, bit in _MOD_ORDER if mods & bit]
    parts.append(f"<{name}>" if len(name) > 1 else name)
    return "+".join(parts)


_PRETTY_MODS = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "option": "Alt", "opt": "Alt",
                "shift": "Shift", "cmd": "Win", "command": "Win", "win": "Win", "super": "Win"}
_PRETTY_KEYS = {"esc": "Esc", "escape": "Esc", "enter": "Enter", "return": "Enter", "tab": "Tab",
                "space": "Space", "backspace": "Backspace", "delete": "Delete", "left": "←", "right": "→",
                "up": "↑", "down": "↓", "home": "Home", "end": "End", "pageup": "PgUp",
                "pagedown": "PgDn", "insert": "Insert"}


def pretty(spec):
    """'<ctrl>+<shift>+s' → 'Ctrl+Shift+S'"""
    order = {"Ctrl": 0, "Alt": 1, "Shift": 2, "Win": 3}
    mods, keys = set(), []
    for p in spec.split("+"):
        n = p.strip().strip("<>").lower()
        if n in _PRETTY_MODS:
            mods.add(_PRETTY_MODS[n])
        elif n:
            keys.append(_PRETTY_KEYS.get(n, n.upper()))
    return "+".join(sorted(mods, key=order.get) + keys)


MOD_HINT = "需要配合 Ctrl / Alt / Shift / Win 使用（F1~F12 可单独用）"
LOCAL_HINT = "快捷键可能被其它程序占用，请换一个组合"


def current_mods():
    """读取当前按住的修饰键"""
    if not IS_WIN:
        return 0
    gks = ctypes.windll.user32.GetAsyncKeyState
    down = lambda vk: bool(gks(vk) & 0x8000)
    mods = 0
    if down(0x11):
        mods |= MOD_CONTROL
    if down(0x12):
        mods |= MOD_ALT
    if down(0x10):
        mods |= MOD_SHIFT
    if down(0x5B) or down(0x5C):
        mods |= MOD_WIN
    return mods


# ---------------------------------------------------------------- 全局快捷键
class GlobalHotkey:
    """start()/stop() 在主线程调用；回调在快捷键线程触发，回调内只能做线程安全的事。"""

    _HOTKEY_ID = 0xA11C

    def __init__(self, spec, callback):
        self.keycode, self.mods = parse(spec)
        self.spec = spec
        self.callback = callback
        self.mode = None
        self._thread = None
        self._tid = None
        self._ok = False

    def start(self):
        if not IS_WIN:
            raise RuntimeError("仅支持 Windows")
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = wintypes.BOOL
        ready = threading.Event()

        def run():
            # 热键绑定在注册它的线程上，消息循环必须在同一线程
            self._tid = kernel32.GetCurrentThreadId()
            self._ok = bool(user32.RegisterHotKey(None, self._HOTKEY_ID,
                                                  self.mods | MOD_NOREPEAT, self.keycode))
            ready.set()
            if not self._ok:
                return
            msg = wintypes.MSG()
            try:
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == WM_HOTKEY and msg.wParam == self._HOTKEY_ID:
                        try:
                            self.callback()
                        except Exception:
                            pass
            finally:
                user32.UnregisterHotKey(None, self._HOTKEY_ID)

        self._thread = threading.Thread(target=run, name="GlobalHotkey", daemon=True)
        self._thread.start()
        ready.wait(2)
        if not self._ok:
            self._thread = None
            raise RuntimeError(f"{pretty(self.spec)} 已被其它程序占用，请换一个组合")
        self.mode = "global"
        return self.mode

    def stop(self):
        if self._thread is not None and self._thread.is_alive() and self._tid:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            self._thread.join(timeout=1)
        self._thread = None
        self._tid = None
        self.mode = None


# ---------------------------------------------------------------- 快捷键录制
class KeyRecorder:
    """录制时捕获本窗口的下一次按键（吞掉该按键，不会输入到输入框）。主线程调用。"""

    def __init__(self, on_key, widget=None):
        self.on_key = on_key        # on_key(虚拟键码, 修饰键标志)
        self.widget = widget
        self._root = None
        self._bind_id = None

    def start(self):
        if self.widget is None:
            raise RuntimeError("缺少窗口")
        self._root = self.widget.winfo_toplevel()
        self._root.focus_set()      # 移走输入框焦点，避免按键被输入进去
        self._bind_id = self._root.bind("<KeyPress>", self._on_key, add="+")

    def _on_key(self, event):
        vk = event.keycode
        if vk in MODIFIER_VKS:
            return "break"          # 只按了修饰键，继续等主键
        try:
            self.on_key(vk, current_mods())
        except Exception:
            pass
        return "break"

    def stop(self):
        if self._root is not None and self._bind_id is not None:
            try:
                self._root.unbind("<KeyPress>", self._bind_id)
            except Exception:
                pass
        self._root = None
        self._bind_id = None
