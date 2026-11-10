# -*- mode: python ; coding: utf-8 -*-
# Windows 打包配置：源码在 ../src（与 macOS 共用），生成 dist/AutoClicker/AutoClicker.exe（文件夹形式，启动更快）
import os
import re
from PyInstaller.utils.hooks import collect_data_files

SRC = os.path.abspath(os.path.join(SPECPATH, "..", "src"))
_ver = open(os.path.join(SRC, "version.py"), encoding="utf-8").read()
APP_VERSION = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', _ver).group(1)
ICON = os.path.join(SPECPATH, "assets", "AppIcon.ico")
HAS_ICON = os.path.exists(ICON)

# exe 文件属性里的版本信息
_v = tuple(int(x) for x in (APP_VERSION.split(".") + ["0", "0", "0"])[:4])
VERSION_FILE = os.path.join(SPECPATH, "build", "version_info.txt")
os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
with open(VERSION_FILE, "w", encoding="utf-8") as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={_v}, prodvers={_v}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080404B0', [
      StringStruct('CompanyName', 'dimgg'),
      StringStruct('FileDescription', '图像识别点击器'),
      StringStruct('FileVersion', '{APP_VERSION}'),
      StringStruct('InternalName', 'AutoClicker'),
      StringStruct('OriginalFilename', 'AutoClicker.exe'),
      StringStruct('ProductName', 'AutoClicker 图像识别点击器'),
      StringStruct('ProductVersion', '{APP_VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
""")

datas = collect_data_files("customtkinter")    # 主题 json / 字体
if HAS_ICON:
    datas.append((ICON, "."))                    # 窗口左上角 / 任务栏图标

a = Analysis(
    [os.path.join(SRC, "autoclicker.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "version", "core", "platforms", "platforms.win_permissions", "platforms.win_hotkey",
        "customtkinter", "darkdetect",
        "pyscreeze", "pymsgbox", "pytweening", "mouseinfo",
        "PIL._tkinter_finder",
    ],
    excludes=["platforms.mac_permissions", "platforms.mac_hotkey", "Quartz", "AppKit", "Foundation",
              "CoreFoundation", "objc", "matplotlib", "scipy", "pandas", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AutoClicker",
    console=False,
    icon=ICON if HAS_ICON else None,
    version=VERSION_FILE,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AutoClicker")
