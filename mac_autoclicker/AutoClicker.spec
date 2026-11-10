# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：把 Python 解释器 + 全部依赖打进 AutoClicker.app，安装即用
import os
from PyInstaller.utils.hooks import collect_data_files

APP_VERSION = "1.2.0"
ICON = "assets/AppIcon.icns" if os.path.exists("assets/AppIcon.icns") else None

a = Analysis(
    ["autoclicker.py"],
    pathex=["."],
    binaries=[],
    datas=collect_data_files("customtkinter"),   # 主题 json / 字体
    hiddenimports=[
        "core", "mac_permissions", "customtkinter", "darkdetect",
        "hotkey_mac",
        "pyscreeze", "pymsgbox", "pytweening", "mouseinfo",
        "PIL._tkinter_finder",
        "Quartz", "AppKit", "Foundation", "CoreFoundation",
    ],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "pytest"],
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
    bundle_identifier="com.dimgg.autoclicker",
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
