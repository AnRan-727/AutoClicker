# 图像识别点击器（AutoClicker）for macOS

## 一、生成安装包（只需做一次）

安装包里包含 Python 解释器、OpenCV、PyAutoGUI 等全部依赖，**用户安装后直接用，不需要装 Python**。

打包必须在 Mac 上完成（PyInstaller 不能跨平台编译），两种方式任选：

### 方式 A：在自己的 Mac 上一键打包
1. 打包机需要有 Python 3.10+ 且 **Tk ≥ 8.6.10**，推荐 [python.org 官方安装包](https://www.python.org/downloads/macos/)（自带新版 Tk）。
   Mac 自带的 `/usr/bin/python3` 和未配置 tcl-tk 的 pyenv Python 会链接系统 Tk 8.5，打包后界面是空白的；脚本会自动检测并跳过它们。
2. 解压本文件夹，打开「终端」，执行：
   ```bash
   cd 解压后的/mac_autoclicker
   bash build_mac.command
   ```
3. 约 2~5 分钟后得到 `dist/AutoClicker-1.2.0-arm64.dmg`（Intel Mac 上是 `x86_64`）。

> 打出来的包只适配打包机的芯片：在 Apple 芯片 Mac 上打的给 M 系列用，在 Intel Mac 上打的给 Intel 用。

### 方式 B：GitHub 云端自动打包（两种芯片都要时推荐）
把文件夹推到 GitHub 仓库 → Actions → 「Build macOS DMG」→ Run workflow，
完成后在运行页下载 Apple 芯片和 Intel 两个 DMG。

## 二、安装

双击 DMG → 把 **AutoClicker** 拖进「应用程序」→ 从启动台打开。

- 如果提示「无法验证开发者」：在「应用程序」里**右键 → 打开 → 打开**（只需一次）；
  或执行 `xattr -cr /Applications/AutoClicker.app`。

## 三、首次启动：权限检测

软件启动时会自动检测：

| 权限 | 用途 | 是否必需 |
|---|---|---|
| 屏幕录制 | 截图识别 | 必需 |
| 辅助功能 | 鼠标点击 | 必需 |
| 输入监控 | 全局停止快捷键（其它软件在前台时也能按） | 必需 |

- **都已授权** → 直接进入主界面。
- **缺少权限** → 弹出授权窗口，点「去授权」会自动打开对应的系统设置页面，打开 AutoClicker 的开关即可。
  授权状态每 1.5 秒自动刷新，必需权限到位后自动进入主界面。
- **屏幕录制**是 macOS 的特殊权限，授权后要点「重启软件」才生效。

> **只需授权一次**：打包脚本第一次运行时会在「登录」钥匙串创建本机签名证书 `AutoClicker Self-Signed`，
> 以后每次打包都用同一个证书签名，重装/更新软件后授权依然有效。
> 创建证书时系统会弹窗要求输入登录密码（信任证书、允许 codesign 使用密钥，选「始终允许」），只有第一次需要。
> 从旧版（临时签名）升级的第一次，在授权页点「去授权」即可，软件会自动清除旧的失效记录。

## 四、使用

1. 「新增按钮」→「屏幕框选截图」框选目标按钮（或「上传图片」）。
2. 调整「相似度阈值」：0.80~0.90 常用；识别不到就调低，误点就调高。
3. 「测试识别」：鼠标会移到识别位置并显示相似度。
4. 设置点击动作、偏移、等待时间、未找到处理、循环次数，点「开始运行」。

**停止方式**：停止快捷键（默认 ⌃⇧S，在「运行设置」里点一下快捷键按钮，直接按下新组合键即可修改；Esc 取消，⌫ 清除）/ 停止按钮 / 鼠标甩到屏幕左上角。

**两种模式**：顺序执行（固定流程）；监视模式（出现哪个点哪个，适合随机弹窗）。

## 五、数据位置

安装版的配置和模板图片保存在：
`~/Library/Application Support/AutoClicker/`（`config.json` 和 `templates/`），卸载或升级 App 不会丢失。

## 六、从源码直接运行（开发用）

```bash
pip install -r requirements.txt
python3 autoclicker.py
```
此时权限需授予给「终端」而不是 AutoClicker。

## 注意

- PyAutoGUI 在 macOS 上只截取**主显示器**。
- 模板尽量用本软件的「屏幕框选截图」截取，Retina 缩放会自动处理。
- 停止快捷键使用 macOS 底层键盘事件监听（CGEventTap），全局生效；不再使用 pynput（在 macOS 14+ 会闪退）。
