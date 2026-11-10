; Inno Setup 安装脚本：把 dist\AutoClicker 打包成 AutoClicker-<版本>-Setup.exe
; 由 build_win.ps1 调用：ISCC.exe /DAppVersion=1.3.0 installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "AutoClicker"
#define AppDisplayName "图像识别点击器"
#define AppExe "AutoClicker.exe"

[Setup]
; AppId 固定不变：升级安装时会覆盖旧版本，而不是装出两份
AppId={{6F1C2B7A-3D4E-4B8F-9A1C-AC1C7E2D0B13}
AppName={#AppDisplayName}
AppVersion={#AppVersion}
AppVerName={#AppDisplayName} {#AppVersion}
AppPublisher=dimgg
AppPublisherURL=https://github.com/AnRan-727/AutoClicker
AppSupportURL=https://github.com/AnRan-727/AutoClicker/issues
AppUpdatesURL=https://github.com/AnRan-727/AutoClicker/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppDisplayName}
DisableProgramGroupPage=yes
; 默认装到当前用户，无需管理员；安装时可选择为所有用户安装
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename={#AppName}-{#AppVersion}-Setup
SetupIconFile=assets\AppIcon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppDisplayName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
#if FileExists(AddBackslash(CompilerPath) + "Languages\ChineseSimplified.isl")
Name: "chs"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppDisplayName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppDisplayName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppDisplayName}}"; Flags: nowait postinstall skipifsilent

; 卸载时保留用户配置和模板（%APPDATA%\AutoClicker），重装后可继续使用
