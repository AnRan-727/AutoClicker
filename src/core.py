# -*- coding: utf-8 -*-
"""识别与执行引擎（与界面、系统无关）：截图、模板匹配、点击、循环调度"""
import os
import sys
import threading
import time
import traceback

import cv2
import numpy as np
import pyautogui

from version import APP_NAME, APP_VERSION
import platforms

# 配置和模板目录：mac ~/Library/Application Support/AutoClicker，Windows %APPDATA%\\AutoClicker
APP_DIR = platforms.data_dir()
TPL_DIR = os.path.join(APP_DIR, "templates")
CFG_PATH = os.path.join(APP_DIR, "config.json")
os.makedirs(TPL_DIR, exist_ok=True)

pyautogui.FAILSAFE = True   # 鼠标移到屏幕左上角 → 抛出 FailSafeException 紧急停止
pyautogui.PAUSE = 0.03

ACTIONS = {"left": "单击", "double": "双击", "right": "右键", "move": "仅移动"}
FAILS = {"skip": "跳过继续", "restart": "重新开始本轮", "stop": "停止运行"}
MODES = {"sequence": "顺序执行", "monitor": "监视模式"}

STEP_DEFAULT = dict(
    name="按钮", image="", confidence=0.85, action="left",
    offset_x=0, offset_y=0, after_delay=0.5, timeout=5.0,
    on_fail="skip", all_matches=False, grayscale=False, enabled=True,
)
GLOBAL_DEFAULT = dict(
    mode="sequence", loops=0, round_interval=1.0, start_delay=3.0,
    scan_interval=0.3, move_duration=0.1, multiscale=False,
    region=None, stop_hotkey="<ctrl>+<shift>+s",
)


def resolve(path):
    return path if os.path.isabs(path) else os.path.join(APP_DIR, path)


def imread(path):
    """支持中文路径的读取"""
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def label_to_key(mapping, label):
    for k, v in mapping.items():
        if v == label:
            return k
    return next(iter(mapping))


# ---------------------------------------------------------------- 识别核心
class Screen:
    """一次屏幕截图。保存物理像素图像及其与逻辑坐标（pyautogui 坐标）的比例。"""

    def __init__(self, region=None):
        shot = pyautogui.screenshot().convert("RGB")
        logical_w, _ = pyautogui.size()
        self.scale = shot.width / logical_w          # Retina 屏通常为 2.0
        bgr = cv2.cvtColor(np.asarray(shot), cv2.COLOR_RGB2BGR)
        self.ox = self.oy = 0
        if region:
            x, y, w, h = [int(round(v * self.scale)) for v in region]
            bgr = bgr[y:y + h, x:x + w]
            self.ox, self.oy = x, y
        self.bgr = bgr
        self._gray = None

    @property
    def gray(self):
        if self._gray is None:
            self._gray = cv2.cvtColor(self.bgr, cv2.COLOR_BGR2GRAY)
        return self._gray


class Matcher:
    SCALES = [1.0, 0.9, 1.1, 0.8, 1.25, 0.75, 1.5, 0.5, 2.0]

    def __init__(self):
        self._cache = {}

    def template(self, path, gray):
        full = resolve(path)
        key = (full, gray, os.path.getmtime(full))
        tpl = self._cache.get(key)
        if tpl is None:
            tpl = imread(full)
            if tpl is None:
                raise ValueError(f"无法读取图片: {path}")
            if gray:
                tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            self._cache[key] = tpl
        return tpl

    def find(self, screen, step, multiscale=False):
        """返回 ([(逻辑x, 逻辑y, 相似度), ...], 最高相似度)"""
        tpl = self.template(step["image"], step["grayscale"])
        scr = screen.gray if step["grayscale"] else screen.bgr
        conf = step["confidence"]
        best = None
        for s in (self.SCALES if multiscale else [1.0]):
            t = tpl if s == 1.0 else cv2.resize(
                tpl, None, fx=s, fy=s,
                interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
            th, tw = t.shape[:2]
            if th < 4 or tw < 4 or th > scr.shape[0] or tw > scr.shape[1]:
                continue
            res = cv2.matchTemplate(scr, t, cv2.TM_CCOEFF_NORMED)
            _, mx, _, _ = cv2.minMaxLoc(res)
            if not np.isfinite(mx):
                continue
            if best is None or mx > best[0]:
                best = (mx, res, tw, th)
            if mx >= 0.98:
                break
        if best is None:
            return [], 0.0
        mx, res, tw, th = best
        if mx < conf:
            return [], mx

        hits = []
        if not step["all_matches"]:
            _, v, _, loc = cv2.minMaxLoc(res)
            hits.append((loc, v))
        else:
            res = res.copy()
            for _ in range(100):
                _, v, _, loc = cv2.minMaxLoc(res)
                if v < conf:
                    break
                hits.append((loc, v))
                x, y = loc   # 非极大值抑制：抹掉该点附近区域
                res[max(0, y - th // 2):y + th // 2 + 1,
                    max(0, x - tw // 2):x + tw // 2 + 1] = -1
            hits.sort(key=lambda h: (h[0][1], h[0][0]))  # 从上到下、从左到右

        pts = [((screen.ox + x + tw / 2) / screen.scale,
                (screen.oy + y + th / 2) / screen.scale, v)
               for (x, y), v in hits]
        return pts, mx


# ---------------------------------------------------------------- 执行引擎
class Runner:
    """后台执行。emit(kind, msg, level) 把日志/状态送回界面线程；level: info/ok/warn/err"""

    def __init__(self, emit):
        self.emit = emit
        self.matcher = Matcher()
        self.stop_evt = threading.Event()
        self.thread = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def log(self, msg, level="info"):
        self.emit("log", msg, level)

    def start(self, steps, g):
        self.stop_evt.clear()
        self.thread = threading.Thread(target=self._run, args=(steps, g), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_evt.set()

    def _sleep(self, sec):
        """可被停止打断的等待；返回 True 表示已收到停止信号"""
        return self.stop_evt.wait(max(0.0, sec))

    def _run(self, steps, g):
        try:
            self.log(f"{g['start_delay']:g} 秒后开始，请切换到目标软件窗口…")
            self.emit("status", "准备中", "warn")
            if self._sleep(g["start_delay"]):
                return
            n = 0
            while not self.stop_evt.is_set() and (g["loops"] <= 0 or n < g["loops"]):
                n += 1
                total = "∞" if g["loops"] <= 0 else g["loops"]
                self.emit("status", f"运行中 · 第 {n}/{total} 轮", "ok")
                if g["mode"] == "monitor":
                    self._round_monitor(steps, g)
                else:
                    self.log(f"—— 第 {n} 轮 ——")
                    if self._round_sequence(steps, g) == "stop":
                        break
                if self._sleep(g["round_interval"]):
                    break
            self.log("运行结束")
        except pyautogui.FailSafeException:
            self.log("鼠标移到屏幕角落，触发 FailSafe 紧急停止", "err")
        except Exception as e:
            self.log(f"运行出错：{e}\n{traceback.format_exc()}", "err")
        finally:
            self.emit("done", "", "info")

    def _click(self, st, x, y, g, score):
        x, y = x + st["offset_x"], y + st["offset_y"]
        a = st["action"]
        self.log(f"[{st['name']}] 相似度 {score:.3f} → {ACTIONS[a]} ({x:.0f}, {y:.0f})", "ok")
        pyautogui.moveTo(x, y, duration=g["move_duration"])
        if a == "left":
            pyautogui.click(x, y)
        elif a == "double":
            pyautogui.doubleClick(x, y)
        elif a == "right":
            pyautogui.rightClick(x, y)

    def _wait_find(self, st, g):
        """在 timeout 内反复截图查找；返回点列表，[] 未找到，None 已停止"""
        deadline = time.time() + max(0.0, st["timeout"])
        while True:
            if self.stop_evt.is_set():
                return None
            pts, best = self.matcher.find(Screen(g["region"]), st, g["multiscale"])
            if pts:
                return pts
            if time.time() >= deadline:
                self.log(f"[{st['name']}] 未找到（最高相似度 {best:.3f}）", "warn")
                return []
            if self._sleep(g["scan_interval"]):
                return None

    def _round_sequence(self, steps, g):
        for st in steps:
            pts = self._wait_find(st, g)
            if pts is None:
                return "stop"
            if not pts:
                f = st["on_fail"]
                self.log(f"[{st['name']}] → {FAILS[f]}", "warn")
                if f == "stop":
                    self.stop_evt.set()
                    return "stop"
                if f == "restart":
                    return "restart"
                continue
            for x, y, v in (pts if st["all_matches"] else pts[:1]):
                if self.stop_evt.is_set():
                    return "stop"
                self._click(st, x, y, g, v)
                if self._sleep(st["after_delay"]):
                    return "stop"
        return "ok"

    def _round_monitor(self, steps, g):
        """监视模式：一次截图检查所有按钮，出现哪个点哪个"""
        scr = Screen(g["region"])
        for st in steps:
            if self.stop_evt.is_set():
                return
            pts, _ = self.matcher.find(scr, st, g["multiscale"])
            if not pts:
                continue
            for x, y, v in (pts if st["all_matches"] else pts[:1]):
                self._click(st, x, y, g, v)
                if self._sleep(st["after_delay"]):
                    return
            scr = Screen(g["region"])   # 点击后界面可能变化，重新截图
