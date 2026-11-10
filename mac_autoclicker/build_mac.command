#!/bin/bash
# macOS 一键打包：源码在 ../src（与 Windows 共用），生成 dist/AutoClicker.app 和 dist/AutoClicker-<版本>-<架构>.dmg
# 用法：在终端执行  bash build_mac.command
set -euo pipefail
# 固定 UTF-8，避免中文紧贴变量时被当成变量名的一部分
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
cd "$(dirname "$0")"

# 版本号从共享源码 ../src/version.py 读取
VERSION="$(sed -n 's/^APP_VERSION *= *"\(.*\)"/\1/p' ../src/version.py)"
ARCH="$(uname -m)"
APP="dist/AutoClicker.app"
DMG="dist/AutoClicker-${VERSION}-${ARCH}.dmg"

pause() { [ -z "${CI:-}" ] && read -r -p "按回车键关闭…" _ || true; }
trap 'echo; echo "❌ 打包失败，请把上面的报错发给我"; pause' ERR

# ---------- 固定代码签名证书（只在第一次打包时创建，保存在「登录」钥匙串）
IDENTITY="AutoClicker Self-Signed"
KEYCHAIN="${HOME}/Library/Keychains/login.keychain-db"
# 不用管道 + grep -q：在 pipefail 下 grep 提前退出会让判断出错
has_identity() { [[ "$(security find-identity -v -p codesigning 2>/dev/null)" == *"${IDENTITY}"* ]]; }
ensure_identity() {
  has_identity && return 0
  echo
  echo "   首次打包：创建本机签名证书「${IDENTITY}」，以后重装软件无需重新授权。"
  echo "   接下来系统可能弹窗："
  echo "     · 要求输入登录密码以「信任」该证书 → 输入密码并允许"
  echo "     · 「codesign 想要使用钥匙串中的密钥」→ 输入登录密码并点「始终允许」"
  local tmp; tmp="$(mktemp -d)"
  if security find-certificate -c "${IDENTITY}" "${KEYCHAIN}" >/dev/null 2>&1; then
    # 证书已导入但未被信任（上次中途取消）→ 只补做信任
    security find-certificate -c "${IDENTITY}" -p "${KEYCHAIN}" > "${tmp}/cert.pem"
  else
    cat > "${tmp}/cfg" <<CFG
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = ${IDENTITY}
[ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
CFG
    /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -config "${tmp}/cfg" \
      -keyout "${tmp}/key.pem" -out "${tmp}/cert.pem" >/dev/null 2>&1 || { rm -rf "${tmp}"; return 1; }
    /usr/bin/openssl pkcs12 -export -inkey "${tmp}/key.pem" -in "${tmp}/cert.pem" -name "${IDENTITY}" \
      -out "${tmp}/id.p12" -passout pass:autoclicker >/dev/null 2>&1 || { rm -rf "${tmp}"; return 1; }
    security import "${tmp}/id.p12" -k "${KEYCHAIN}" -P autoclicker -T /usr/bin/codesign >/dev/null \
      || { rm -rf "${tmp}"; return 1; }
  fi
  security add-trusted-cert -r trustRoot -p codeSign -k "${KEYCHAIN}" "${tmp}/cert.pem" || { rm -rf "${tmp}"; return 1; }
  rm -rf "${tmp}"
  has_identity
}

echo "==> 1/6 查找合适的 Python（需要 3.9+ 且 Tk ≥ 8.6.10，否则界面会空白）"
# 返回 0 表示该 Python 可用
check_py() {
  "$1" - <<'PYEOF' 2>/dev/null
import sys, tkinter
pl = tkinter.Tcl().eval("info patchlevel")
ok = sys.version_info >= (3, 9) and tuple(int(x) for x in pl.split(".")[:3]) >= (8, 6, 10)
print(f"   {sys.executable}  Python {sys.version.split()[0]}  Tk {pl}  {'✓' if ok else '✗ 版本过旧'}")
sys.exit(0 if ok else 1)
PYEOF
}
PY=""
for cand in "${PYTHON:-}" \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
    /Users/anran/Documents/Documents/PythonProjects/Private/AutoClicker/.venv/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 \
    /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  [ -z "${cand}" ] && continue
  command -v "${cand}" >/dev/null 2>&1 || continue
  if check_py "${cand}"; then PY="${cand}"; break; fi
done
if [ -z "${PY}" ]; then
  echo
  echo "没有找到合适的 Python。Mac 自带的 /usr/bin/python3 使用旧版 Tk 8.5，打包后界面会是空白。"
  echo "请安装官方 Python 3.12（自带新版 Tk）：https://www.python.org/downloads/macos/"
  echo "安装后重新运行本脚本即可。"
  pause; exit 1
fi
echo "   使用：${PY}"

echo "==> 2/6 创建独立构建环境"
rm -rf .venv-build
"${PY}" -m venv .venv-build
source .venv-build/bin/activate
python -m pip install -q -U pip

echo "==> 3/6 安装依赖（会被全部打进安装包）"
pip install -q -r ../requirements.txt "pyinstaller>=6.6"

echo "==> 4/6 生成图标"
python ../src/make_icon.py assets

echo "==> 5/6 打包 .app"
rm -rf build dist
pyinstaller --noconfirm --clean AutoClicker.spec
# 用固定的本机证书签名：macOS 按签名识别 App，签名不变 → 重装/更新后授权仍然有效
xattr -cr "${APP}" || true
if [ -z "${CI:-}" ] && ensure_identity; then
  SIGN="${IDENTITY}"
  echo "   使用固定签名：${IDENTITY}"
else
  SIGN="-"
  echo "   ⚠ 无法创建固定签名证书，改用临时签名（重装后需要重新授权）"
fi
codesign --force --deep --sign "${SIGN}" "${APP}"
xattr -cr "${APP}" || true

echo "==> 6/6 制作 DMG 安装包"
STAGE="dist/dmg"
mkdir -p "${STAGE}"
cp -R "${APP}" "${STAGE}/"
ln -s /Applications "${STAGE}/Applications"
hdiutil create -volname "AutoClicker" -srcfolder "${STAGE}" -ov -format UDZO "${DMG}" >/dev/null
rm -rf "${STAGE}"

echo
echo "✅ 完成！"
echo "   安装包：$(pwd)/${DMG}"
echo "   双击 DMG，把 AutoClicker 拖进「应用程序」即可使用。"
[ -z "${CI:-}" ] && open dist || true
pause
