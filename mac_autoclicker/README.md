# macOS 打包

源码在 `../src`，与 Windows 版共用同一套界面和识别逻辑；这里只放 macOS 的打包配置。

## 一键打包

1. 安装 [Python 3.12 官方安装包](https://www.python.org/downloads/macos/)（需要 Tk ≥ 8.6.10；Mac 自带的 `/usr/bin/python3` 和未配置 tcl-tk 的 pyenv Python 使用旧版 Tk 8.5，打包后界面会空白，脚本会自动跳过它们）
2. 在终端执行：
   ```bash
   cd mac_autoclicker
   bash build_mac.command
   ```
3. 产物：`dist/AutoClicker-<版本>-arm64.dmg`（Intel Mac 上是 `x86_64`）

> 打出来的包只适配打包机的芯片。两种芯片都要时，用 GitHub Actions 自动打包（推送版本标签即可）。

## 固定签名：重装后无需重新授权

首次打包会在「登录」钥匙串创建本机签名证书 `AutoClicker Self-Signed`，之后每次打包都用同一个证书签名，
重装 / 更新软件后系统权限依然有效。创建证书时系统会弹窗要求输入登录密码：

- 信任证书 → 允许
- 「codesign 想要使用钥匙串中的密钥」→ 选「始终允许」

## 安装与权限

双击 DMG，把 **AutoClicker** 拖进「应用程序」。首次启动会检测并引导授权：

| 权限 | 用途 |
|---|---|
| 屏幕录制 | 截图识别（授权后需重启软件生效） |
| 辅助功能 | 鼠标点击 |
| 输入监控 | 全局停止快捷键 |

首次打开如提示「无法验证开发者」：系统设置 → 隐私与安全性 → 「仍要打开」，或执行 `xattr -cr /Applications/AutoClicker.app`。

## 数据位置

- 配置与模板：`~/Library/Application Support/AutoClicker/`
- 日志：`~/Library/Logs/AutoClicker/app.log`

## 注意

- 只截取**主显示器**，目标软件请放在主屏上
- 系统要求 macOS 14 及以上
