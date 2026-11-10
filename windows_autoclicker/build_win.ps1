# Windows 一键打包：源码在 ..\src（与 macOS 共用）
# 产物：dist\AutoClicker-<版本>-Setup.exe（安装包）和 dist\AutoClicker-<版本>-win64-portable.zip（免安装版）
# 用法：双击 build_win.bat，或在 PowerShell 中执行  .\build_win.ps1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Set-Location -Path $PSScriptRoot

$IsCI = [bool]$env:CI
function Pause-End { if (-not $IsCI) { Read-Host "按回车键关闭" | Out-Null } }
function Fail($msg) { Write-Host ""; Write-Host "❌ $msg" -ForegroundColor Red; Pause-End; exit 1 }
function Run($exe, [string[]]$argList) {
    # 原生程序会往 stderr 写普通日志（pip / PyInstaller），不能当成错误
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $exe @argList
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { Fail "命令执行失败：$exe $($argList -join ' ')" }
}

$Version = (Select-String -Path ..\src\version.py -Pattern 'APP_VERSION\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
Write-Host "AutoClicker Windows 打包  v$Version" -ForegroundColor Cyan

# ---------- 1. 查找合适的 Python（3.9+，Tk ≥ 8.6.10）
Write-Host "==> 1/6 查找合适的 Python"
$check = @'
import sys, tkinter
pl = tkinter.Tcl().eval("info patchlevel")
ok = sys.version_info >= (3, 9) and tuple(int(x) for x in pl.split(".")[:3]) >= (8, 6, 10)
print(f"   {sys.executable}  Python {sys.version.split()[0]}  Tk {pl}  {'OK' if ok else '版本过旧'}")
sys.exit(0 if ok else 1)
'@
# 写到临时文件再执行：PowerShell 5.1 传带引号的多行参数会出错
$checkFile = Join-Path $env:TEMP "autoclicker_check_python.py"
[System.IO.File]::WriteAllText($checkFile, $check, (New-Object System.Text.UTF8Encoding $false))
$candidates = @()
if ($env:PYTHON) { $candidates += ,@($env:PYTHON) }
foreach ($v in "3.13", "3.12", "3.11", "3.10") { $candidates += ,@("py", "-$v") }
$candidates += ,@("python")
$Py = $null
foreach ($c in $candidates) {
    $exe = $c[0]; $pre = @($c | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try { & $exe @pre $checkFile 2>$null; $ok = ($LASTEXITCODE -eq 0) } catch { $ok = $false }
    $ErrorActionPreference = $old
    if ($ok) { $Py = $c; break }
}
if (-not $Py) { Fail "没有找到合适的 Python。请从 https://www.python.org/downloads/windows/ 安装 Python 3.12（勾选 tcl/tk 和 py launcher）后重试。" }
$PyExe = $Py[0]; $PyPre = @($Py | Select-Object -Skip 1)

# ---------- 2. 独立构建环境
Write-Host "==> 2/6 创建独立构建环境"
if (Test-Path .venv-build) { Remove-Item -Recurse -Force .venv-build }
Run $PyExe ($PyPre + @("-m", "venv", ".venv-build"))
$VPy = Join-Path $PSScriptRoot ".venv-build\Scripts\python.exe"
Run $VPy @("-m", "pip", "install", "-q", "-U", "pip")

# ---------- 3. 依赖（全部打进安装包）
Write-Host "==> 3/6 安装依赖（会被全部打进安装包）"
Run $VPy @("-m", "pip", "install", "-q", "-r", "..\requirements.txt", "pyinstaller>=6.6")

# ---------- 4. 图标
Write-Host "==> 4/6 生成图标"
Run $VPy @("..\src\make_icon.py", "assets")

# ---------- 5. PyInstaller
Write-Host "==> 5/6 打包程序"
foreach ($d in "build", "dist") { if (Test-Path $d) { Remove-Item -Recurse -Force $d } }
Run $VPy @("-m", "PyInstaller", "--noconfirm", "--clean", "AutoClicker.spec")
if (-not (Test-Path "dist\AutoClicker\AutoClicker.exe")) { Fail "没有生成 dist\AutoClicker\AutoClicker.exe" }

$Zip = "dist\AutoClicker-$Version-win64-portable.zip"
Compress-Archive -Path "dist\AutoClicker" -DestinationPath $Zip -Force
Write-Host "   免安装版：$Zip"

# ---------- 6. 安装包（Inno Setup）
Write-Host "==> 6/6 制作安装包"
function Find-Iscc {
    $paths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $paths) { if ($p -and (Test-Path $p)) { return $p } }
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}
$Iscc = Find-Iscc
if (-not $Iscc -and $IsCI) {
    choco install innosetup -y --no-progress | Out-Null
    $Iscc = Find-Iscc
}
if ($Iscc) {
    Run $Iscc @("/Q", "/DAppVersion=$Version", "installer.iss")
    Write-Host "   安装包：dist\AutoClicker-$Version-Setup.exe"
} else {
    Write-Host "   ⚠ 未安装 Inno Setup，跳过安装包（免安装版已生成）。" -ForegroundColor Yellow
    Write-Host "     需要安装包可执行：winget install JRSoftware.InnoSetup ，然后重新运行本脚本。"
}

Write-Host ""
Write-Host "✅ 完成！产物在 $PSScriptRoot\dist" -ForegroundColor Green
if (-not $IsCI) { Invoke-Item dist }
Pause-End
