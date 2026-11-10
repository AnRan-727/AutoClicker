# -*- coding: utf-8 -*-
"""
平台适配层：界面和识别逻辑是同一套代码，系统相关的部分在这里按平台切换。

    permissions  系统权限检测与授权引导（mac：屏幕录制/辅助功能/输入监控；Windows：无需授权）
    hotkey       全局停止快捷键 + 快捷键录制（mac：CGEventTap；Windows：RegisterHotKey）
    UI_FONT / MONO_FONT   界面字体
    data_dir() / log_dir()   配置与日志目录
    pretty_hotkey()      快捷键显示（mac：⌃⇧S；Windows：Ctrl+Shift+S）
    setup_process()      进程级初始化（Windows 任务栏图标等）
"""
import os
import sys

from version import APP_NAME

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
FROZEN = getattr(sys, "frozen", False)

if IS_MAC:
    from . import mac_permissions as permissions
    try:
        from . import mac_hotkey as hotkey
    except Exception:
        hotkey = None
    UI_FONT, MONO_FONT = "PingFang SC", "Menlo"
    PLATFORM_NAME = "macOS"
elif IS_WIN:
    from . import win_permissions as permissions
    from . import win_hotkey as hotkey
    UI_FONT, MONO_FONT = "Microsoft YaHei UI", "Consolas"
    PLATFORM_NAME = "Windows"
else:                                   # 其它系统：可运行，但没有全局快捷键
    from . import win_permissions as permissions
    hotkey = None
    UI_FONT, MONO_FONT = "Noto Sans CJK SC", "DejaVu Sans Mono"
    PLATFORM_NAME = sys.platform

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir():
    """配置与模板目录：打包后放用户目录（程序目录可能只读），源码运行时放 src/ 旁边"""
    if not FROZEN:
        d = SRC_DIR
    elif IS_MAC:
        d = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    elif IS_WIN:
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    else:
        d = os.path.expanduser(f"~/.{APP_NAME.lower()}")
    os.makedirs(d, exist_ok=True)
    return d


def log_dir():
    if IS_MAC:
        d = os.path.expanduser(f"~/Library/Logs/{APP_NAME}")
    elif IS_WIN:
        d = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME, "logs")
    else:
        d = os.path.join(data_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def resource_path(name):
    """打包后随程序分发的资源（如 Windows 图标）"""
    base = getattr(sys, "_MEIPASS", SRC_DIR)
    return os.path.join(base, name)


def pretty_hotkey(spec):
    if not spec or not spec.strip():
        return ""
    return hotkey.pretty(spec) if hotkey else spec


def setup_process(root):
    """创建主窗口后调用"""
    if IS_WIN:
        try:
            import ctypes
            # 任务栏显示本程序图标，而不是 Python 图标
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dimgg.AutoClicker")
        except Exception:
            pass
        ico = resource_path("AppIcon.ico")
        if os.path.exists(ico):
            try:
                root.iconbitmap(ico)     # 需在 CustomTkinter 设置默认图标之前调用
            except Exception:
                pass
