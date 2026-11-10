# -*- coding: utf-8 -*-
"""
macOS 隐私权限检测与引导（纯 ctypes，无需额外依赖）
- 屏幕录制   CGPreflightScreenCaptureAccess / CGRequestScreenCaptureAccess
- 辅助功能   AXIsProcessTrusted / AXIsProcessTrustedWithOptions(prompt)
- 输入监控   IOHIDCheckAccess / IOHIDRequestAccess
"""
import ctypes
import os
import shlex
import subprocess
import sys

IS_MAC = sys.platform == "darwin"
from version import BUNDLE_ID
_reset_done = set()


def _reset_stale(service):
    """清除本软件在 TCC 中的旧授权记录（旧签名留下的失效条目），每项每次启动只做一次。
    只在「未授权时点去授权」才调用，所以不会影响已生效的授权。"""
    if not getattr(sys, "frozen", False) or service in _reset_done:
        return
    _reset_done.add(service)
    try:
        subprocess.run(["/usr/bin/tccutil", "reset", service, BUNDLE_ID],
                       capture_output=True, timeout=5)
    except Exception:
        pass


def _load(name):
    try:
        return ctypes.cdll.LoadLibrary(f"/System/Library/Frameworks/{name}.framework/{name}")
    except OSError:
        return None


_CG = _load("CoreGraphics") if IS_MAC else None
_AS = _load("ApplicationServices") if IS_MAC else None
_CF = _load("CoreFoundation") if IS_MAC else None
_IOK = _load("IOKit") if IS_MAC else None

_IOHID_LISTEN_EVENT = 1      # kIOHIDRequestTypeListenEvent
_IOHID_GRANTED = 0           # kIOHIDAccessTypeGranted


def _fn(lib, name, restype=ctypes.c_bool, argtypes=()):
    if lib is None or not hasattr(lib, name):
        return None
    f = getattr(lib, name)
    f.restype = restype
    f.argtypes = list(argtypes)
    return f


# ---------- 检测
def screen_recording_granted():
    f = _fn(_CG, "CGPreflightScreenCaptureAccess")
    return True if f is None else bool(f())


def accessibility_granted():
    f = _fn(_AS, "AXIsProcessTrusted")
    return True if f is None else bool(f())


def input_monitoring_granted():
    f = _fn(_IOK, "IOHIDCheckAccess", ctypes.c_uint32, [ctypes.c_uint32])
    return True if f is None else f(_IOHID_LISTEN_EVENT) == _IOHID_GRANTED


# ---------- 请求（会让系统把本程序加入对应列表并弹出系统提示）
def open_settings(anchor):
    subprocess.Popen(["open", f"x-apple.systempreferences:com.apple.preference.security?{anchor}"])


def request_screen_recording():
    _reset_stale("ScreenCapture")
    f = _fn(_CG, "CGRequestScreenCaptureAccess")
    if f:
        f()
    open_settings("Privacy_ScreenCapture")


def request_accessibility():
    _reset_stale("Accessibility")
    try:
        key = ctypes.c_void_p.in_dll(_AS, "kAXTrustedCheckOptionPrompt")
        true = ctypes.c_void_p.in_dll(_CF, "kCFBooleanTrue")
        kcb = ctypes.c_void_p.in_dll(_CF, "kCFTypeDictionaryKeyCallBacks")
        vcb = ctypes.c_void_p.in_dll(_CF, "kCFTypeDictionaryValueCallBacks")
        create = _fn(_CF, "CFDictionaryCreate", ctypes.c_void_p,
                     [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                      ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p])
        keys = (ctypes.c_void_p * 1)(key.value)
        vals = (ctypes.c_void_p * 1)(true.value)
        d = create(None, keys, vals, 1, ctypes.addressof(kcb), ctypes.addressof(vcb))
        _fn(_AS, "AXIsProcessTrustedWithOptions", ctypes.c_bool, [ctypes.c_void_p])(d)
        _fn(_CF, "CFRelease", None, [ctypes.c_void_p])(d)
    except Exception:
        pass
    open_settings("Privacy_Accessibility")


def request_input_monitoring():
    _reset_stale("ListenEvent")
    f = _fn(_IOK, "IOHIDRequestAccess", ctypes.c_bool, [ctypes.c_uint32])
    if f:
        f(_IOHID_LISTEN_EVENT)
    open_settings("Privacy_ListenEvent")


def relaunch():
    """重启本程序（屏幕录制授权后必须重启才生效）"""
    if getattr(sys, "frozen", False):
        bundle = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", ".."))
        subprocess.Popen(["/bin/sh", "-c", f"sleep 1; open {shlex.quote(bundle)}"])
    else:
        subprocess.Popen([sys.executable] + sys.argv)
    os._exit(0)


PERMISSIONS = [
    # key, 名称, 用途, 是否必需, 检测函数, 请求函数
    ("screen", "屏幕录制", "截图识别按钮", True, screen_recording_granted, request_screen_recording),
    ("ax", "辅助功能", "控制鼠标点击", True, accessibility_granted, request_accessibility),
    ("input", "输入监控", "全局停止快捷键（在其它软件里也能按）", True, input_monitoring_granted, request_input_monitoring),
]


def required_granted():
    return all(chk() for _, _, _, req, chk, _ in PERMISSIONS if req)


# ---------- 授权引导（直接画在主窗口里，不用隐藏主窗口 + 子窗口，避免 macOS 上空白）
_DEFAULT_COLORS = dict(
    bg=("#F2F3F7", "#16171B"), card=("#FFFFFF", "#212329"), border=("#E3E5EB", "#30333A"),
    field=("#F5F6F9", "#2A2D34"), hover=("#ECEEF3", "#30333B"), text=("#1B1D23", "#ECEDF1"),
    muted=("#7B818D", "#8D93A0"), accent="#3D6AF2", accent_h="#2F57D4", ok="#1F9D63", err="#E5484D",
    ok_bg=("#E5F6EE", "#1C3A2C"), err_bg=("#FDECEC", "#3F2326"),
)


def show_permission_gate(root, on_ready, colors=None):
    """必需权限都有 → 立即调用 on_ready()；否则在 root 中显示授权界面，授权完成或用户选择继续后再调用。"""
    if not IS_MAC or required_granted():
        on_ready()
        return

    import customtkinter as ctk
    C = dict(_DEFAULT_COLORS, **(colors or {}))

    def F(size, weight="normal"):
        return ctk.CTkFont(family="PingFang SC", size=size, weight=weight)

    state = {"done": False}
    root.title("需要授权")
    w, h = 600, 540
    root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")
    wrap = ctk.CTkFrame(root, fg_color="transparent")
    wrap.pack(fill="both", expand=True, padx=32, pady=28)

    def proceed():
        if state["done"]:
            return
        state["done"] = True
        wrap.destroy()
        on_ready()

    ctk.CTkLabel(wrap, text="◎", width=52, height=52, corner_radius=14, fg_color=C["accent"],
                 text_color="white", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(wrap, text="开始之前，需要三项系统权限", font=F(21, "bold"),
                 text_color=C["text"]).pack(anchor="w", pady=(14, 4))
    ctk.CTkLabel(wrap, justify="left", wraplength=530, font=F(13), text_color=C["muted"], text=(
        "点击「去授权」会自动清除旧的失效记录并打开系统设置，打开 AutoClicker 的开关即可。"
        "屏幕录制授权后需要重启软件才能生效。只需授权一次，以后更新软件不用重新授权。")).pack(anchor="w", pady=(0, 18))

    rows = {}
    for key, name, desc, req, chk, ask in PERMISSIONS:
        card = ctk.CTkFrame(wrap, fg_color=C["card"], corner_radius=14, border_width=1, border_color=C["border"])
        card.pack(fill="x", pady=5)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=name, font=F(14, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="sw", padx=16, pady=(12, 0))
        ctk.CTkLabel(card, text=desc, font=F(12), text_color=C["muted"]).grid(
            row=1, column=0, sticky="nw", padx=16, pady=(0, 12))
        pill = ctk.CTkLabel(card, text="", height=24, corner_radius=12, font=F(12, "bold"))
        pill.grid(row=0, column=1, rowspan=2, padx=8, ipadx=10)
        btn = ctk.CTkButton(card, text="去授权", width=84, height=32, corner_radius=9, font=F(13, "bold"),
                            fg_color=C["accent"], hover_color=C["accent_h"], command=ask)
        btn.grid(row=0, column=2, rowspan=2, padx=(4, 14))
        rows[key] = (pill, btn, chk)

    bar = ctk.CTkFrame(wrap, fg_color="transparent")
    bar.pack(fill="x", side="bottom")
    ghost = dict(height=36, corner_radius=10, font=F(13), fg_color=C["field"], hover_color=C["hover"],
                 text_color=C["text"])
    ctk.CTkButton(bar, text="退出", width=70, command=root.destroy, **ghost).pack(side="left")
    ctk.CTkButton(bar, text="重启软件", width=100, height=36, corner_radius=10, font=F(13, "bold"),
                  fg_color=C["accent"], hover_color=C["accent_h"], command=relaunch).pack(side="right")
    ctk.CTkButton(bar, text="暂不授权，继续打开", width=150, command=proceed, **ghost).pack(side="right", padx=8)

    def refresh():
        if state["done"]:
            return
        for pill, btn, chk in rows.values():
            ok = chk()
            pill.configure(text="已授权" if ok else "未授权",
                           fg_color=C["ok_bg"] if ok else C["err_bg"],
                           text_color=C["ok"] if ok else C["err"])
            btn.configure(state="disabled" if ok else "normal", text="已完成" if ok else "去授权")
        if required_granted():
            proceed()
            return
        root.after(1500, refresh)

    refresh()
    root.lift()
    root.focus_force()


def startup_notes():
    """进入主界面后在日志里显示的提示（macOS 无）"""
    return []
