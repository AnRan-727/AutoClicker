# Windows 打包

源码在 `../src`，与 macOS 版共用同一套界面和识别逻辑；这里只放 Windows 的打包配置。

## 一键打包

1. 安装 [Python 3.12](https://www.python.org/downloads/windows/)（安装时勾选 **tcl/tk** 和 **py launcher**）
2. （可选）安装 [Inno Setup 6](https://jrsoftware.org/isdl.php) 用来生成安装包：`winget install JRSoftware.InnoSetup`
3. 双击 **`build_win.bat`**

产物在 `dist\`：

| 文件 | 说明 |
|---|---|
| `AutoClicker-<版本>-Setup.exe` | 安装包（需要 Inno Setup） |
| `AutoClicker-<版本>-win64-portable.zip` | 免安装版，解压后运行 `AutoClicker.exe` |

不想在本地打包：推送版本标签后 GitHub Actions 会自动打出 Windows 版并上传到 Release。

## 与 macOS 版的区别

| | macOS | Windows |
|---|---|---|
| 系统权限 | 屏幕录制 / 辅助功能 / 输入监控 | 不需要 |
| 全局停止快捷键 | CGEventTap，默认 ⌃⇧S | RegisterHotKey，默认 Ctrl+Shift+S |
| 配置目录 | `~/Library/Application Support/AutoClicker` | `%APPDATA%\AutoClicker` |
| 日志目录 | `~/Library/Logs/AutoClicker` | `%LOCALAPPDATA%\AutoClicker\logs` |

## 注意

- 如果要点击的程序是**以管理员身份运行**的，本软件也要右键「以管理员身份运行」，否则 Windows 会拦截点击
- 首次运行可能出现 SmartScreen「Windows 已保护你的电脑」：点「更多信息」→「仍要运行」（软件未购买代码签名证书）
- 截图只截取**主显示器**，目标程序请放在主屏上
- 快捷键被其它程序占用时会在日志中提示，换一个组合即可
