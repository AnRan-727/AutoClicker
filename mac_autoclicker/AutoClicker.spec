# -*- mode: python ; coding: utf-8 -*-
# macOS 打包配置：源码在 ../src（与 Windows 共用），把 Python 解释器 + 全部依赖打进 AutoClicker.app
import os
import re
from PyInstaller.utils.hooks import collect_data_files

SRC = os.path.abspath(os.path.join(SPECPATH, "..", "src"))
_ver = open(os.path.join(SRC, "version.py"), encoding="utf-8").read()
APP_VERSION = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', _ver).group(1)
BUNDLE_ID = re.search(r'BUNDLE_ID\s*=\s*"([^"]+)"', _ver).group(1)
ICON = os.path.join(SPECPATH, "assets", "AppIcon.icns")
ICON = ICON if os.path.exists(ICON) else None

a = Analysis(
    [os.path.join(SRC, "autoclicker.py")],
    pathex=[SRC],
    binaries=[],
    datas=collect_data_files("customtkinter"),   # 主题 json / 字体
    hiddenimports=[
        "version", "core", "platforms", "platforms.mac_permissions", "platforms.mac_hotkey",
        "customtkinter", "darkdetect",
        "pyscreeze", "pymsgbox", "pytweening", "mouseinfo",
        "PIL._tkinter_finder",
        "Quartz", "AppKit", "Foundation", "CoreFoundation",
    ],
    excludes=["platforms.win_hotkey", "matplotlib", "scipy", "pandas", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AutoClicker",
    console=False,
    argv_emulation=False,
    target_arch=None,          # 跟随打包机器架构（Apple 芯片=arm64，Intel=x86_64）
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AutoClicker")

app = BUNDLE(
    coll,
    name="AutoClicker.app",
    icon=ICON,
    bundle_identifier=BUNDLE_ID,
    version=APP_VERSION,
    info_plist={
        "CFBundleName": "AutoClicker",
        "CFBundleDisplayName": "图像识别点击器",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSAppleEventsUsageDescription": "用于自动化控制前台软件。",
    },
)
