# -*- coding: utf-8 -*-
"""
Windows（及其它系统）的权限模块。
Windows 截图和模拟点击不需要系统授权，所以授权页直接跳过；接口与 mac_permissions 保持一致。
唯一的限制：目标程序以「管理员身份」运行时，普通权限的程序无法点击它（Windows UIPI 机制）。
"""
import sys

IS_WIN = sys.platform.startswith("win")


def is_admin():
    if not IS_WIN:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def screen_recording_granted():
    return True


def accessibility_granted():
    return True


def input_monitoring_granted():
    return True


def required_granted():
    return True


def show_permission_gate(root, on_ready, colors=None):
    """无需授权，直接进入主界面"""
    on_ready()


def relaunch_as_admin():
    """以管理员身份重新启动本程序（需要用户在 UAC 弹窗中确认）"""
    if not IS_WIN:
        return False
    import ctypes
    import os
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe, params = sys.executable, " ".join(f'"{a}"' for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    if rc > 32:
        os._exit(0)
    return False


def startup_notes():
    """进入主界面后在日志里显示的提示"""
    if IS_WIN and not is_admin():
        return [("如果要点击的程序是以管理员身份运行的，本软件也需要右键「以管理员身份运行」才能点到它", "info")]
    return []
