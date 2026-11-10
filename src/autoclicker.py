#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像识别自动点击器 —— 界面（CustomTkinter），macOS 与 Windows 共用同一套代码
识别/执行逻辑见 core.py；系统相关部分（权限、全局快捷键、字体、目录）见 platforms/
"""
import json
import os
import queue
import shutil
import sys
import time
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pyautogui
from PIL import Image, ImageTk

from core import (APP_NAME, APP_VERSION, TPL_DIR, CFG_PATH, ACTIONS, FAILS, MODES,
                  STEP_DEFAULT, GLOBAL_DEFAULT, resolve, imread, label_to_key, Screen, Runner)
import platforms as plat

perms = plat.permissions
hk_mod = plat.hotkey                    # 当前系统的快捷键实现；None = 不支持全局快捷键
if hk_mod is not None:
    GlobalHotkey, KeyRecorder = hk_mod.GlobalHotkey, hk_mod.KeyRecorder
    to_spec, FUNCTION_KEYS, ESC, BACKSPACE = hk_mod.to_spec, hk_mod.FUNCTION_KEYS, hk_mod.ESC, hk_mod.BACKSPACE
else:
    GlobalHotkey = KeyRecorder = None

ctk.set_appearance_mode("system")      # 跟随系统浅色 / 深色
ctk.set_default_color_theme("blue")

# ---------------------------------------------------------------- 设计规范
FONT = plat.UI_FONT
C = dict(
    bg=("#F2F3F7", "#16171B"),
    card=("#FFFFFF", "#212329"),
    border=("#E3E5EB", "#30333A"),
    field=("#F5F6F9", "#2A2D34"),
    hover=("#ECEEF3", "#30333B"),
    text=("#1B1D23", "#ECEDF1"),
    muted=("#7B818D", "#8D93A0"),
    sel=("#EBF0FF", "#26304A"),
    sel_hover=("#DCE5FF", "#2F3B5C"),
    seg_bg=("#ECEEF3", "#2A2D34"),
    seg_hover=("#E2E5EC", "#33363E"),
    seg_sel=("#FFFFFF", "#474C58"),
    accent="#3D6AF2",
    accent_h="#2F57D4",
    ok="#1F9D63",
    warn="#E08A00",
    err="#E5484D",
    ok_bg=("#E5F6EE", "#1C3A2C"),
    err_bg=("#FDECEC", "#3F2326"),
)
STATUS_COLORS = {"idle": "#9AA0AA", "info": "#9AA0AA", "warn": C["warn"], "ok": C["ok"], "err": C["err"]}
pretty_hotkey = plat.pretty_hotkey


# ---------------------------------------------------------------- 屏幕框选
class RegionSelector(tk.Toplevel):
    """全屏覆盖层，拖动鼠标框选区域。回调 (逻辑区域(x,y,w,h), 物理像素裁剪图)"""

    def __init__(self, master, callback, on_finish):
        super().__init__(master)
        self.callback, self.on_finish = callback, on_finish
        self.shot = pyautogui.screenshot().convert("RGB")
        self.lw, self.lh = pyautogui.size()
        self.scale = self.shot.width / self.lw
        disp = self.shot.resize((self.lw, self.lh), Image.BILINEAR)
        disp = Image.blend(disp, Image.new("RGB", disp.size, (0, 0, 0)), 0.25)
        self.tkimg = ImageTk.PhotoImage(disp)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{self.lw}x{self.lh}+0+0")
        self.canvas = tk.Canvas(self, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.update()
        # 窗口可能被菜单栏挤下去，按实际位置偏移图像，保证与真实屏幕对齐
        rx, ry = self.winfo_rootx(), self.winfo_rooty()
        self.canvas.create_image(-rx, -ry, anchor="nw", image=self.tkimg)
        self.canvas.create_text(
            self.lw // 2, 40, fill="yellow", font=(FONT, 20, "bold"),
            text="拖动鼠标框选区域    Esc / 右键 取消")
        self.start = None
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        for seq in ("<Escape>", "<Button-2>", "<Button-3>"):
            self.bind(seq, lambda e: self._close())
        self.focus_force()

    def _press(self, e):
        self.start = (e.x_root, e.y_root, e.x, e.y)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=2)

    def _drag(self, e):
        if self.rect:
            self.canvas.coords(self.rect, self.start[2], self.start[3], e.x, e.y)

    def _release(self, e):
        if not self.start:
            return
        x0, y0 = self.start[0], self.start[1]
        x, y = min(x0, e.x_root), min(y0, e.y_root)
        w, h = abs(e.x_root - x0), abs(e.y_root - y0)
        if w >= 3 and h >= 3:
            s = self.scale
            crop = self.shot.crop((int(x * s), int(y * s), int((x + w) * s), int((y + h) * s)))
            self._close()
            self.callback((int(x), int(y), int(w), int(h)), crop)
        else:
            self._close()

    def _close(self):
        self.destroy()
        self.on_finish()


# ---------------------------------------------------------------- 列表行
class StepRow(ctk.CTkFrame):
    def __init__(self, master, app, idx):
        super().__init__(master, corner_radius=12, fg_color="transparent",
                         border_width=2, border_color=C["card"])
        self.app, self.idx = app, idx
        self.grid_columnconfigure(2, weight=1)
        self.num = ctk.CTkLabel(self, width=22, font=app.f["small_b"], text_color=C["muted"])
        self.num.grid(row=0, column=0, rowspan=2, padx=(10, 2), pady=8)
        self.thumb = ctk.CTkLabel(self, text="", width=64, height=40, corner_radius=8,
                                  fg_color=C["field"], font=app.f["small"], text_color=C["muted"])
        self.thumb.grid(row=0, column=1, rowspan=2, padx=6, pady=8)
        self.name = ctk.CTkLabel(self, anchor="w", font=app.f["body_b"], text_color=C["text"])
        self.name.grid(row=0, column=2, sticky="sw", padx=(8, 4), pady=(8, 0))
        self.sub = ctk.CTkLabel(self, anchor="w", font=app.f["small"], text_color=C["muted"])
        self.sub.grid(row=1, column=2, sticky="nw", padx=(8, 4), pady=(0, 8))
        self.en = tk.BooleanVar()
        self.sw = ctk.CTkSwitch(self, text="", width=46, variable=self.en, progress_color=C["accent"],
                                command=lambda: app.set_enabled(self.idx, self.en.get()))
        self.sw.grid(row=0, column=3, rowspan=2, padx=(4, 6))
        for w in (self, self.num, self.thumb, self.name, self.sub):
            w.bind("<Button-1>", lambda e: app.select(self.idx))

    def update_view(self, s, selected):
        self.num.configure(text=str(self.idx + 1))
        self.name.configure(text=s["name"] or "未命名",
                            text_color=C["text"] if s["enabled"] else C["muted"])
        self.sub.configure(text=f"{ACTIONS[s['action']]} · {s['confidence']:.2f} · {s['timeout']:g}s")
        self.en.set(s["enabled"])
        img, _ = self.app.thumb(s["image"], (64, 40))
        self.thumb.configure(image=img, text="" if img else "无图")
        self.configure(fg_color=C["sel"] if selected else "transparent",
                       border_color=C["accent"] if selected else C["card"])


# ---------------------------------------------------------------- 主界面
class App:
    def __init__(self, root):
        self.root = root
        root.title(f"图像识别点击器 v{APP_VERSION}")
        w, h = 1220, 800
        x = max(0, (root.winfo_screenwidth() - w) // 2)
        y = max(30, (root.winfo_screenheight() - h) // 3)
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(1060, 660)
        root.configure(fg_color=C["bg"])

        def F(size, weight="normal"):
            return ctk.CTkFont(family=FONT, size=size, weight=weight)
        self.f = dict(title=F(20, "bold"), h2=F(15, "bold"), body=F(13), body_b=F(13, "bold"),
                      small=F(12), small_b=F(12, "bold"), value=F(24, "bold"),
                      mono=ctk.CTkFont(family=plat.MONO_FONT, size=12))

        self.steps = []
        self.cfg = dict(GLOBAL_DEFAULT)
        self.cur = None
        self._loading = False
        self.rows = []
        self._thumbs = {}
        self.hotkey = None
        self.q = queue.Queue()
        self.runner = Runner(lambda k, m, l: self.q.put((k, m, l)))

        self._build()
        self.load_config(CFG_PATH, silent=True)
        self._poll()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ================================================================ 组件工厂
    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=16,
                            border_width=1, border_color=C["border"])

    def _label(self, parent, text, muted=True, font="small"):
        return ctk.CTkLabel(parent, text=text, font=self.f[font],
                            text_color=C["muted"] if muted else C["text"])

    def _entry(self, parent, var, width=120):
        return ctk.CTkEntry(parent, textvariable=var, width=width, height=32, corner_radius=8,
                            border_width=1, fg_color=C["field"], border_color=C["border"],
                            text_color=C["text"], font=self.f["body"])

    def _field(self, parent, label, var, width=100):
        fr = ctk.CTkFrame(parent, fg_color="transparent")
        self._label(fr, label).pack(anchor="w")
        self._entry(fr, var, width).pack(fill="x", pady=(3, 0))
        return fr

    def _btn(self, parent, text, cmd, kind="ghost", width=80, height=32):
        style = dict(
            primary=dict(fg_color=C["accent"], hover_color=C["accent_h"], text_color="white"),
            ghost=dict(fg_color=C["field"], hover_color=C["hover"], text_color=C["text"]),
            soft=dict(fg_color=C["sel"], hover_color=C["sel_hover"], text_color=C["accent"]),
            danger=dict(fg_color=C["field"], hover_color=C["err_bg"], text_color=C["err"]),
        )[kind]
        return ctk.CTkButton(parent, text=text, command=cmd, width=width, height=height,
                             corner_radius=9, font=self.f["body_b" if kind == "primary" else "body"], **style)

    def _segmented(self, parent, values, var, command=None):
        return ctk.CTkSegmentedButton(
            parent, values=values, variable=var, height=32, corner_radius=9, font=self.f["body"],
            fg_color=C["seg_bg"], unselected_color=C["seg_bg"], unselected_hover_color=C["seg_hover"],
            selected_color=C["seg_sel"], selected_hover_color=C["seg_sel"], text_color=C["text"],
            command=command)

    def _switch(self, parent, text, var):
        return ctk.CTkSwitch(parent, text=text, variable=var, font=self.f["body"], text_color=C["text"],
                             progress_color=C["accent"], switch_width=38, switch_height=20)

    def thumb(self, path, box):
        """返回 (CTkImage | None, 原图尺寸)；按 2 倍像素生成，Retina 下清晰"""
        if not path:
            return None, None
        full = resolve(path)
        if not os.path.exists(full):
            return None, None
        key = (full, os.path.getmtime(full), box)
        if key not in self._thumbs:
            im = Image.open(full).convert("RGBA")
            size0 = im.size
            t = im.copy()
            t.thumbnail((box[0] * 2, box[1] * 2), Image.LANCZOS)
            disp = (max(1, t.width // 2), max(1, t.height // 2))
            self._thumbs[key] = (ctk.CTkImage(light_image=t, dark_image=t, size=disp), size0)
        return self._thumbs[key]

    # ================================================================ 布局
    def _build(self):
        r = self.root
        r.grid_columnconfigure(0, weight=1)
        r.grid_rowconfigure(1, weight=1)    # 上方：按钮列表 + 设置（可滚动，随窗口伸缩）
        r.grid_rowconfigure(2, weight=0)    # 下方：运行设置 + 日志，保持完整高度
        self._build_header().grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))

        body = ctk.CTkFrame(r, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=6)
        body.grid_columnconfigure(0, weight=2, minsize=360)
        body.grid_columnconfigure(1, weight=5)
        body.grid_rowconfigure(0, weight=1)
        self._build_list(body).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_editor(body).grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        bottom = ctk.CTkFrame(r, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="nsew", padx=20, pady=(6, 18))
        bottom.grid_columnconfigure(0, weight=5)
        bottom.grid_columnconfigure(1, weight=4)
        bottom.grid_rowconfigure(0, weight=1)
        self._build_settings(bottom).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_log(bottom).grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def _build_header(self):
        h = ctk.CTkFrame(self.root, fg_color="transparent")
        h.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(h, text="◎", width=44, height=44, corner_radius=12, fg_color=C["accent"],
                     text_color="white", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(h, text="图像识别点击器", font=self.f["title"], text_color=C["text"]).grid(
            row=0, column=1, sticky="sw")
        self._label(h, f"识别画面中的按钮 · 自动点击 · 循环执行      v{APP_VERSION}").grid(
            row=1, column=1, sticky="nw")

        right = ctk.CTkFrame(h, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, sticky="e")
        pill = ctk.CTkFrame(right, fg_color=C["card"], corner_radius=17, border_width=1, border_color=C["border"])
        pill.pack(side="left", padx=(0, 14))
        self.status_dot = ctk.CTkLabel(pill, text="●", font=ctk.CTkFont(size=13), text_color=STATUS_COLORS["idle"])
        self.status_dot.pack(side="left", padx=(14, 6), pady=4)
        self.status_txt = ctk.CTkLabel(pill, text="就绪", font=self.f["small_b"], text_color=C["text"])
        self.status_txt.pack(side="left", padx=(0, 16), pady=4)

        self.btn_stop = ctk.CTkButton(
            right, text="■  停止", width=110, height=40, corner_radius=10, command=self.stop,
            fg_color=C["card"], hover_color=C["err_bg"], border_width=1, border_color=C["border"],
            text_color=C["err"], text_color_disabled=C["muted"], font=self.f["body_b"], state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 10))
        self.btn_start = ctk.CTkButton(
            right, text="▶  开始运行", width=140, height=40, corner_radius=10, command=self.start,
            fg_color=C["accent"], hover_color=C["accent_h"], font=self.f["body_b"])
        self.btn_start.pack(side="left")
        return h

    def _build_list(self, parent):
        c = self._card(parent)
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        self._label(top, "按钮列表", muted=False, font="h2").pack(side="left")
        self.count_lbl = ctk.CTkLabel(top, text="0", width=26, height=20, corner_radius=10,
                                      fg_color=C["sel"], text_color=C["accent"], font=self.f["small_b"])
        self.count_lbl.pack(side="left", padx=8)
        self._btn(top, "删除", self.del_step, "danger", width=48, height=28).pack(side="right")
        self._btn(top, "复制", self.dup_step, width=48, height=28).pack(side="right", padx=4)
        self._btn(top, "↓", lambda: self.move_step(1), width=30, height=28).pack(side="right")
        self._btn(top, "↑", lambda: self.move_step(-1), width=30, height=28).pack(side="right", padx=4)

        self.list_frame = ctk.CTkScrollableFrame(c, fg_color="transparent", corner_radius=0,
                                                 scrollbar_button_color=C["border"],
                                                 scrollbar_button_hover_color=C["muted"])
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 6))
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.empty_list = self._label(self.list_frame, "还没有按钮\n点击下方「＋ 新增按钮」开始")
        self._btn(c, "＋  新增按钮", self.add_step, "soft", height=38).grid(
            row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        return c

    def _build_editor(self, parent):
        c = self._card(parent)
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(1, weight=1)
        self._label(c, "按钮设置", muted=False, font="h2").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 8))
        self.editor_empty = self._label(c, "选择左侧的按钮进行设置，或新增一个按钮")
        self.editor_empty.grid(row=1, column=0)
        # 外层容器负责显示/隐藏，内层可滚动：窗口较小时可以滚动查看全部设置
        self.editor = ctk.CTkFrame(c, fg_color="transparent")
        self.editor.grid(row=1, column=0, sticky="nsew", padx=(18, 6), pady=(0, 12))
        self.editor.grid_columnconfigure(0, weight=1)
        self.editor.grid_rowconfigure(0, weight=1)
        ed = ctk.CTkScrollableFrame(self.editor, fg_color="transparent", corner_radius=0,
                                    scrollbar_button_color=C["border"], scrollbar_button_hover_color=C["muted"])
        ed.grid(row=0, column=0, sticky="nsew")
        self._ed, self._ed_layout = ed, None

        self.v = dict(
            name=tk.StringVar(), confidence=tk.DoubleVar(value=0.85), action=tk.StringVar(),
            offset_x=tk.StringVar(), offset_y=tk.StringVar(), timeout=tk.StringVar(),
            after_delay=tk.StringVar(), on_fail=tk.StringVar(),
            all_matches=tk.BooleanVar(), grayscale=tk.BooleanVar(), enabled=tk.BooleanVar(),
        )

        # 左列：名称 + 图片
        L = self._ed_left = ctk.CTkFrame(ed, fg_color="transparent")
        self._label(L, "名称").pack(anchor="w")
        self._entry(L, self.v["name"], 300).pack(fill="x", pady=(3, 12))
        self._label(L, "识别图片").pack(anchor="w")
        self.preview = ctk.CTkLabel(L, text="未设置图片", width=300, height=150, corner_radius=12,
                                    fg_color=C["field"], text_color=C["muted"], font=self.f["small"])
        self.preview.pack(pady=(3, 4))
        self.preview_info = self._label(L, "")
        self.preview_info.pack(anchor="w", pady=(0, 8))
        bf = ctk.CTkFrame(L, fg_color="transparent")
        bf.pack(fill="x")
        bf.grid_columnconfigure((0, 1, 2), weight=1, uniform="b")
        self._btn(bf, "上传图片", self.upload_image).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._btn(bf, "框选截图", self.capture_template).grid(row=0, column=1, sticky="ew", padx=4)
        self._btn(bf, "测试识别", self.test_step, "primary").grid(row=0, column=2, sticky="ew", padx=(4, 0))

        # 右列：参数
        R = self._ed_right = ctk.CTkFrame(ed, fg_color="transparent")
        R.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="f")
        sim = ctk.CTkFrame(R, fg_color="transparent")
        sim.grid(row=0, column=0, columnspan=4, sticky="ew")
        self._label(sim, "相似度阈值").pack(side="left", anchor="s")
        self.fuzz_pill = ctk.CTkLabel(sim, text="", height=22, corner_radius=11, fg_color=C["sel"],
                                      text_color=C["accent"], font=self.f["small_b"])
        self.fuzz_pill.pack(side="right", padx=(8, 0), ipadx=8)
        self.conf_val = ctk.CTkLabel(sim, text="", font=self.f["value"], text_color=C["text"])
        self.conf_val.pack(side="right")
        ctk.CTkSlider(R, from_=0.5, to=1.0, number_of_steps=50, variable=self.v["confidence"],
                      height=18, button_color=C["accent"], button_hover_color=C["accent_h"],
                      progress_color=C["accent"]).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(2, 2))
        self._label(R, "越低越宽松易误点，越高越严格易漏识别，常用 0.80~0.90").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(0, 12))

        self._label(R, "点击动作").grid(row=3, column=0, columnspan=4, sticky="w")
        self._segmented(R, list(ACTIONS.values()), self.v["action"]).grid(
            row=4, column=0, columnspan=4, sticky="ew", pady=(3, 12))

        for col, (key, label) in enumerate([("offset_x", "偏移 X"), ("offset_y", "偏移 Y"),
                                            ("timeout", "等待出现 (秒)"), ("after_delay", "点击后等待 (秒)")]):
            self._field(R, label, self.v[key], 80).grid(row=5, column=col, sticky="ew",
                                                         padx=(0 if col == 0 else 5, 0 if col == 3 else 5))

        self._label(R, "未找到时").grid(row=6, column=0, columnspan=4, sticky="w", pady=(12, 0))
        self._segmented(R, list(FAILS.values()), self.v["on_fail"]).grid(
            row=7, column=0, columnspan=4, sticky="ew", pady=(3, 14))

        sw = ctk.CTkFrame(R, fg_color="transparent")
        sw.grid(row=8, column=0, columnspan=4, sticky="w")
        self._switch(sw, "启用", self.v["enabled"]).pack(side="left", padx=(0, 18))
        self._switch(sw, "点击所有匹配项", self.v["all_matches"]).pack(side="left", padx=(0, 18))
        self._switch(sw, "灰度匹配", self.v["grayscale"]).pack(side="left")

        for var in self.v.values():
            var.trace_add("write", lambda *a: self.on_edit())
        # 自适应：宽度够 → 左右两栏；窗口窄 → 上下排列（配合滚动查看全部）
        self.editor.bind("<Configure>", lambda e: self.root.after_idle(self._relayout_editor, e.width))
        self._relayout_editor(1000)
        self._show_editor(False)
        return c

    def _build_settings(self, parent):
        c = self._card(parent)
        c.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=18, pady=(14, 8))
        self._label(top, "运行设置", muted=False, font="h2").pack(side="left")
        self._btn(top, "保存", lambda: self.save_config(CFG_PATH), "soft", width=56, height=28).pack(side="right")
        self._btn(top, "导出", self.export_cfg, width=56, height=28).pack(side="right", padx=6)
        self._btn(top, "导入", self.import_cfg, width=56, height=28).pack(side="right")

        self.g = dict(
            mode=tk.StringVar(), loops=tk.StringVar(), round_interval=tk.StringVar(),
            start_delay=tk.StringVar(), scan_interval=tk.StringVar(), move_duration=tk.StringVar(),
            multiscale=tk.BooleanVar(), stop_hotkey=tk.StringVar(),
        )
        mode = ctk.CTkFrame(c, fg_color="transparent")
        mode.grid(row=1, column=0, columnspan=3, sticky="ew", padx=18)
        self._segmented(mode, list(MODES.values()), self.g["mode"]).pack(side="left")
        self.mode_hint = self._label(mode, "")
        self.mode_hint.pack(side="left", padx=12)

        fields = [("loops", "循环次数（0 = 无限）"), ("round_interval", "每轮间隔 (秒)"), ("start_delay", "启动延迟 (秒)"),
                  ("scan_interval", "扫描间隔 (秒)"), ("move_duration", "鼠标移动耗时 (秒)")]
        for i, (k, label) in enumerate(fields):
            r, col = divmod(i, 3)
            self._field(c, label, self.g[k]).grid(row=2 + r, column=col, sticky="ew",
                                                  padx=(18 if col == 0 else 6, 18 if col == 2 else 6), pady=(10, 0))

        # 停止快捷键：点击后直接按下组合键录制
        hkf = ctk.CTkFrame(c, fg_color="transparent")
        hkf.grid(row=3, column=2, sticky="ew", padx=(6, 18), pady=(10, 0))
        hkf.grid_columnconfigure(0, weight=1)
        self._label(hkf, "停止快捷键").grid(row=0, column=0, columnspan=2, sticky="w")
        self.hk_btn = ctk.CTkButton(
            hkf, text="", height=32, corner_radius=8, border_width=1, border_color=C["border"],
            fg_color=C["field"], hover_color=C["hover"], text_color=C["text"], font=self.f["body_b"],
            command=self._record_hotkey)
        self.hk_btn.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        self._btn(hkf, "✕", self._clear_hotkey, width=32, height=32).grid(row=1, column=1, padx=(6, 0), pady=(3, 0))
        self._recorder = None

        reg = ctk.CTkFrame(c, fg_color="transparent")
        reg.grid(row=4, column=0, columnspan=3, sticky="ew", padx=18, pady=(14, 16))
        self._label(reg, "识别区域").pack(side="left")
        self.region_lbl = ctk.CTkLabel(reg, text="整个屏幕", height=26, corner_radius=8, fg_color=C["field"],
                                       text_color=C["text"], font=self.f["small_b"])
        self.region_lbl.pack(side="left", padx=8, ipadx=8)
        self._btn(reg, "框选区域", self.pick_region, width=76, height=28).pack(side="left")
        self._btn(reg, "恢复全屏", self.clear_region, width=76, height=28).pack(side="left", padx=6)
        self._switch(reg, "多尺度匹配", self.g["multiscale"]).pack(side="right")

        self.g["mode"].trace_add("write", lambda *a: self._update_mode_hint())
        self.g["stop_hotkey"].trace_add("write", lambda *a: self._update_hotkey_label())
        return c

    def _build_log(self, parent):
        c = self._card(parent)
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        self._label(top, "运行日志", muted=False, font="h2").pack(side="left")
        self.hk_lbl = self._label(top, "")
        self.hk_lbl.pack(side="left", padx=10)
        self._btn(top, "清空", lambda: self.logbox.delete("1.0", "end"), width=56, height=28).pack(side="right")
        self.logbox = ctk.CTkTextbox(c, font=self.f["mono"], fg_color=C["field"], corner_radius=10,
                                     text_color=C["text"], wrap="word", border_width=0, height=120)
        self.logbox.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        for tag, color in [("time", "#9AA0AA"), ("ok", C["ok"]), ("warn", C["warn"]), ("err", C["err"])]:
            self.logbox.tag_config(tag, foreground=color)
        return c

    # ================================================================ 状态显示
    def set_status(self, text, level="idle"):
        self.status_txt.configure(text=text)
        self.status_dot.configure(text_color=STATUS_COLORS.get(level, STATUS_COLORS["idle"]))

    def _update_mode_hint(self):
        m = label_to_key(MODES, self.g["mode"].get())
        self.mode_hint.configure(text="按列表顺序依次等待并点击" if m == "sequence"
                                 else "每轮检查所有按钮，出现哪个点哪个（适合随机弹窗）")

    def _update_hotkey_label(self):
        p = pretty_hotkey(self.g["stop_hotkey"].get())
        self.hk_lbl.configure(text=f"按 {p} 停止" if p else "")
        if self._recorder is None:
            self.hk_btn.configure(text=p or "点击设置", border_color=C["border"],
                                  text_color=C["text"] if p else C["muted"])

    def _record_hotkey(self):
        if self._recorder is not None:          # 再点一次 = 取消
            self._finish_record(None)
            return
        if KeyRecorder is None:
            messagebox.showinfo("提示", "当前环境不支持快捷键录制")
            return
        self.hk_btn.configure(text="请按下组合键…（Esc 取消）", border_color=C["accent"], text_color=C["accent"])

        def on_key(code, mods):
            if code == ESC and not mods:
                spec = None
            elif code == BACKSPACE and not mods:
                spec = ""
            else:
                spec = to_spec(code, mods)
                if spec is None:
                    return                      # 不支持的键，继续等待
                if not mods and code not in FUNCTION_KEYS:
                    self.hk_btn.configure(text=hk_mod.MOD_HINT)
                    return
            self.root.after(0, lambda: self._finish_record(spec))

        self._recorder = KeyRecorder(on_key, self.root)
        try:
            self._recorder.start()
        except Exception as e:
            self._recorder = None
            self.log(f"快捷键录制失败：{e}", "err")
            self._update_hotkey_label()

    def _finish_record(self, spec):
        if self._recorder is None:
            return
        self._recorder.stop()
        self._recorder = None
        if spec is not None:
            self.g["stop_hotkey"].set(spec)
            self.log(f"停止快捷键已设置为：{pretty_hotkey(spec) or '无'}")
        self._update_hotkey_label()

    def _clear_hotkey(self):
        self._finish_record(None)
        self.g["stop_hotkey"].set("")

    def _relayout_editor(self, width):
        mode = "wide" if width >= 800 else "narrow"
        if mode == self._ed_layout:
            return
        self._ed_layout = mode
        ed, L, R = self._ed, self._ed_left, self._ed_right
        L.grid_forget()
        R.grid_forget()
        if mode == "wide":
            ed.grid_columnconfigure(0, weight=0)
            ed.grid_columnconfigure(1, weight=1)
            L.grid(row=0, column=0, sticky="nw", padx=(0, 22), pady=(0, 12))
            R.grid(row=0, column=1, sticky="new", padx=(0, 12), pady=(0, 12))
        else:
            ed.grid_columnconfigure(0, weight=1)
            ed.grid_columnconfigure(1, weight=0)
            L.grid(row=0, column=0, sticky="nw", padx=(0, 12), pady=(0, 18))
            R.grid(row=1, column=0, sticky="new", padx=(0, 12), pady=(0, 12))

    def _show_editor(self, on):
        if on:
            self.editor_empty.grid_remove()
            self.editor.grid()
        else:
            self.editor.grid_remove()
            self.editor_empty.grid()

    # ================================================================ 按钮列表
    def refresh_list(self):
        for r in self.rows:
            r.destroy()
        self.rows = []
        for i, s in enumerate(self.steps):
            row = StepRow(self.list_frame, self, i)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.update_view(s, i == self.cur)
            self.rows.append(row)
        if self.steps:
            self.empty_list.grid_forget()
        else:
            self.empty_list.grid(row=0, column=0, pady=60)
        self.count_lbl.configure(text=str(len(self.steps)))

    def select(self, i):
        if not (0 <= i < len(self.steps)):
            self.cur = None
            self._show_editor(False)
        else:
            self.cur = i
            self._show_editor(True)
            self._load_editor()
        for j, r in enumerate(self.rows):
            r.update_view(self.steps[j], j == self.cur)

    def add_step(self):
        self.steps.append(dict(STEP_DEFAULT, name=f"按钮{len(self.steps) + 1}"))
        self.refresh_list()
        self.select(len(self.steps) - 1)

    def dup_step(self):
        if self.cur is None:
            return
        s = dict(self.steps[self.cur], name=self.steps[self.cur]["name"] + " 副本")
        self.steps.insert(self.cur + 1, s)
        self.refresh_list()
        self.select(self.cur + 1)

    def del_step(self):
        if self.cur is None:
            return
        if not messagebox.askyesno("删除按钮", f"确定删除「{self.steps[self.cur]['name']}」吗？"):
            return
        del self.steps[self.cur]
        i = min(self.cur, len(self.steps) - 1)
        self.cur = None
        self.refresh_list()
        self.select(i)

    def move_step(self, d):
        i = self.cur
        if i is None or not (0 <= i + d < len(self.steps)):
            return
        self.steps[i], self.steps[i + d] = self.steps[i + d], self.steps[i]
        self.cur = i + d
        self.refresh_list()
        self.select(i + d)

    def set_enabled(self, i, val):
        self.steps[i]["enabled"] = bool(val)
        self.rows[i].update_view(self.steps[i], i == self.cur)
        if i == self.cur:
            self._loading = True
            self.v["enabled"].set(bool(val))
            self._loading = False

    # ================================================================ 编辑区
    def _load_editor(self):
        s = self.steps[self.cur]
        self._loading = True
        self.v["name"].set(s["name"])
        self.v["confidence"].set(s["confidence"])
        self.v["action"].set(ACTIONS[s["action"]])
        self.v["on_fail"].set(FAILS[s["on_fail"]])
        self.v["offset_x"].set(str(s["offset_x"]))
        self.v["offset_y"].set(str(s["offset_y"]))
        self.v["timeout"].set(f"{s['timeout']:g}")
        self.v["after_delay"].set(f"{s['after_delay']:g}")
        for k in ("all_matches", "grayscale", "enabled"):
            self.v[k].set(bool(s[k]))
        self._loading = False
        self._update_conf_label()
        self._show_preview(s["image"])

    def on_edit(self):
        if self._loading or self.cur is None:
            return
        s = self.steps[self.cur]
        for k, var in self.v.items():
            try:
                val = var.get()
            except tk.TclError:
                continue
            try:
                if k in ("offset_x", "offset_y"):
                    val = int(float(val))
                elif k in ("timeout", "after_delay"):
                    val = max(0.0, float(val))
            except ValueError:
                continue          # 输入框暂时为空或非法，保留旧值
            if k == "action":
                val = label_to_key(ACTIONS, val)
            elif k == "on_fail":
                val = label_to_key(FAILS, val)
            elif k == "confidence":
                val = round(float(val), 2)
            s[k] = val
        self.rows[self.cur].update_view(s, True)
        self._update_conf_label()

    def _update_conf_label(self):
        try:
            c = float(self.v["confidence"].get())
        except (tk.TclError, ValueError):
            return
        self.conf_val.configure(text=f"{c:.2f}")
        self.fuzz_pill.configure(text=f"模糊度 {round((1 - c) * 100)}%")

    def _show_preview(self, path):
        img, size = self.thumb(path, (300, 150))
        if img:
            self.preview.configure(image=img, text="")
            self.preview_info.configure(text=f"{os.path.basename(path)}  ·  {size[0]}×{size[1]} px")
        else:
            self.preview.configure(image=None, text="未设置图片" if not path else "图片文件不存在")
            self.preview_info.configure(text="上传图片，或在屏幕上框选截图" if not path else path)

    # ================================================================ 图片 / 区域
    def _set_image(self, rel):
        if self.cur is None:
            return
        self.steps[self.cur]["image"] = rel
        self._show_preview(rel)
        self.rows[self.cur].update_view(self.steps[self.cur], True)
        self.log(f"[{self.steps[self.cur]['name']}] 图片已设置：{rel}")

    def upload_image(self):
        if self.cur is None:
            return
        path = filedialog.askopenfilename(
            title="选择要识别的按钮图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.tiff"), ("所有文件", "*.*")])
        if not path:
            return
        if imread(path) is None:
            messagebox.showerror("错误", "无法读取该图片")
            return
        ext = os.path.splitext(path)[1].lower() or ".png"
        name = f"tpl_{uuid.uuid4().hex[:8]}{ext}"
        shutil.copy(path, os.path.join(TPL_DIR, name))
        self._set_image(f"templates/{name}")

    def _with_hidden_window(self, fn, delay=400):
        # 用透明代替 withdraw：macOS 上隐藏主窗口后弹出的子窗口可能不绘制
        self.root.attributes("-alpha", 0.0)
        self.root.after(delay, fn)

    def _restore(self):
        self.root.attributes("-alpha", 1.0)
        self.root.lift()

    def capture_template(self):
        if self.cur is None:
            return

        def done(_region, crop):
            name = f"cap_{uuid.uuid4().hex[:8]}.png"
            crop.save(os.path.join(TPL_DIR, name))
            self._set_image(f"templates/{name}")

        self._with_hidden_window(lambda: RegionSelector(self.root, done, self._restore))

    def pick_region(self):
        def done(region, _crop):
            self.cfg["region"] = list(region)
            self._update_region_label()
            self.log(f"识别区域：{region}")

        self._with_hidden_window(lambda: RegionSelector(self.root, done, self._restore))

    def clear_region(self):
        self.cfg["region"] = None
        self._update_region_label()

    def _update_region_label(self):
        r = self.cfg.get("region")
        self.region_lbl.configure(text="整个屏幕" if not r else f"{r[0]}, {r[1]}  ·  {r[2]}×{r[3]}")

    def test_step(self):
        if self.cur is None or not self.steps[self.cur]["image"]:
            messagebox.showinfo("提示", "请先为该按钮设置图片")
            return
        step = dict(self.steps[self.cur])
        g = self.read_global()
        if g is None:
            return

        def run():
            try:
                t0 = time.time()
                pts, best = self.runner.matcher.find(Screen(g["region"]), step, g["multiscale"])
                ms = (time.time() - t0) * 1000
                self._restore()
                if pts:
                    x, y, _ = pts[0]
                    self.log(f"[测试] {step['name']}：找到 {len(pts)} 处，最高相似度 {best:.3f}，"
                             f"位置 ({x:.0f}, {y:.0f})，耗时 {ms:.0f}ms，鼠标已移到该处", "ok")
                    pyautogui.moveTo(x + step["offset_x"], y + step["offset_y"], duration=0.2)
                else:
                    self.log(f"[测试] {step['name']}：未找到（最高相似度 {best:.3f} < 阈值 "
                             f"{step['confidence']:.2f}），可降低阈值或重新截图", "warn")
            except Exception as e:
                self._restore()
                self.log(f"[测试] 出错：{e}", "err")

        self._with_hidden_window(run, 300)

    # ================================================================ 配置
    def read_global(self):
        g = dict(self.cfg)
        try:
            g["mode"] = label_to_key(MODES, self.g["mode"].get())
            g["loops"] = int(float(self.g["loops"].get()))
            for k in ("round_interval", "start_delay", "scan_interval", "move_duration"):
                g[k] = max(0.0, float(self.g[k].get()))
            g["scan_interval"] = max(0.05, g["scan_interval"])
            g["multiscale"] = bool(self.g["multiscale"].get())
            g["stop_hotkey"] = self.g["stop_hotkey"].get().strip()
        except (ValueError, tk.TclError):
            messagebox.showerror("错误", "运行设置中有非法数值，请检查")
            return None
        return g

    def _apply_global(self):
        cfg = self.cfg
        self.g["mode"].set(MODES.get(cfg["mode"], MODES["sequence"]))
        for k in ("loops", "round_interval", "start_delay", "scan_interval", "move_duration"):
            self.g[k].set(f"{cfg[k]:g}")
        self.g["multiscale"].set(bool(cfg["multiscale"]))
        self.g["stop_hotkey"].set(cfg["stop_hotkey"])
        self._update_region_label()
        self._update_mode_hint()
        self._update_hotkey_label()

    def save_config(self, path, silent=False):
        g = self.read_global()
        if g is None:
            return
        self.cfg = g
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"global": g, "steps": self.steps}, f, ensure_ascii=False, indent=2)
        if not silent:
            self.log(f"配置已保存：{path}", "ok")

    def load_config(self, path, silent=False):
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.cfg = dict(GLOBAL_DEFAULT, **data.get("global", {}))
                self.steps = [dict(STEP_DEFAULT, **s) for s in data.get("steps", [])]
                if not silent:
                    self.log(f"已加载配置：{path}", "ok")
            except Exception as e:
                messagebox.showerror("错误", f"配置读取失败：{e}")
        self._apply_global()
        self.cur = None
        self.refresh_list()
        self.select(0 if self.steps else -1)

    def export_cfg(self):
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if p:
            self.save_config(p)

    def import_cfg(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p:
            self.load_config(p)

    # ================================================================ 运行控制
    def start(self):
        if self.runner.running:
            return
        steps = [dict(s) for s in self.steps if s["enabled"]]
        if not steps:
            messagebox.showinfo("提示", "没有启用的按钮")
            return
        for s in steps:
            if not s["image"] or not os.path.exists(resolve(s["image"])):
                messagebox.showerror("错误", f"按钮「{s['name']}」没有设置有效图片")
                return
        g = self.read_global()
        if g is None:
            return
        self.save_config(CFG_PATH, silent=True)
        self._start_hotkey(g["stop_hotkey"])
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.runner.start(steps, g)

    def stop(self):
        if self.runner.running:
            self.runner.stop()
            self.log("正在停止…")

    def _on_done(self):
        self._stop_hotkey()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.set_status("已停止", "idle")

    def _start_hotkey(self, hk):
        self._stop_hotkey()
        if not hk:
            return
        if GlobalHotkey is None:
            self.log("当前环境不支持全局快捷键（可用停止按钮或鼠标甩到左上角）", "warn")
            return
        try:
            self.hotkey = GlobalHotkey(hk, self._hotkey_pressed)
            mode = self.hotkey.start()
            if mode == "global":
                self.log(f"全局停止快捷键已启用：{pretty_hotkey(hk)}（任何软件在前台都可按）")
            else:
                self.log(f"停止快捷键 {pretty_hotkey(hk)} 仅在本软件在前台时有效：{hk_mod.LOCAL_HINT}", "warn")
        except Exception as e:
            self.hotkey = None
            self.log(f"停止快捷键启用失败：{e}（可用停止按钮或鼠标甩到左上角）", "err")

    def _stop_hotkey(self):
        if self.hotkey:
            try:
                self.hotkey.stop()
            except Exception:
                pass
            self.hotkey = None

    def _hotkey_pressed(self):
        self.log("检测到停止快捷键")
        self.runner.stop()

    # ================================================================ 日志
    def log(self, msg, level="info"):
        self.q.put(("log", msg, level))

    def _poll(self):
        try:
            while True:
                kind, msg, level = self.q.get_nowait()
                if kind == "log":
                    box = self.logbox
                    box.insert("end", time.strftime("%H:%M:%S") + "  ", "time")
                    box.insert("end", msg + "\n", level if level != "info" else None)
                    if int(box.index("end-1c").split(".")[0]) > 3000:
                        box.delete("1.0", "1000.0")
                    box.see("end")
                elif kind == "status":
                    self.set_status(msg, level)
                elif kind == "done":
                    self._on_done()
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def on_close(self):
        self.runner.stop()
        self._stop_hotkey()
        try:
            self.save_config(CFG_PATH, silent=True)
        except Exception:
            pass
        self.root.destroy()


def _setup_logging():
    """打包后没有控制台，把错误写到日志文件（mac: ~/Library/Logs/AutoClicker，Win: %LOCALAPPDATA%\\AutoClicker\\logs）"""
    import logging
    logging.basicConfig(filename=os.path.join(plat.log_dir(), "app.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    sys.excepthook = lambda t, v, tb: logging.error("未捕获异常", exc_info=(t, v, tb))
    return logging


def main():
    logging = _setup_logging()
    root = ctk.CTk()
    plat.setup_process(root)
    logging.info("启动 v%s %s Python %s Tk %s", APP_VERSION, plat.PLATFORM_NAME, sys.version.split()[0],
                 root.tk.call("info", "patchlevel"))
    root.report_callback_exception = lambda t, v, tb: logging.error("界面异常", exc_info=(t, v, tb))
    root.configure(fg_color=C["bg"])

    def ready():
        app = App(root)
        for msg, level in perms.startup_notes():
            app.log(msg, level)
        if not perms.required_granted():
            root.after(500, lambda: messagebox.showwarning(
                "权限不足", "尚未授予屏幕录制或辅助功能权限，识别/点击可能无效。"))

    # 启动时检测权限：都有 → 直接进入主界面；缺少 → 先在同一窗口显示授权界面
    perms.show_permission_gate(root, ready, C)
    root.mainloop()


if __name__ == "__main__":
    main()
