#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/remnawave-updater"
BIN="/usr/local/bin/remnawave-updater"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_SETUP=1

if [[ "${1:-}" == "--no-setup" ]]; then
  RUN_SETUP=0
fi

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo ./install.sh"
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer currently supports Debian/Ubuntu (apt)."
  exit 1
fi

echo "[1/4] Installing system dependencies..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3 python3-rich python3-paramiko openssh-client ca-certificates >/dev/null

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found. Remnawave requires Docker; install it first: https://docs.rw/install/requirements/"
  exit 1
fi

echo "[2/4] Installing application files..."
mkdir -p "$APP_DIR"
if [[ "$SOURCE_DIR" != "$APP_DIR" ]]; then
  rm -rf "$APP_DIR/remnawave_updater" "$APP_DIR/tests"
  cp -a "$SOURCE_DIR/remnawave_updater" "$APP_DIR/"
  cp -a "$SOURCE_DIR/tests" "$APP_DIR/" 2>/dev/null || true
  for file in pyproject.toml requirements.txt README.md README_EN.md LICENSE CHANGELOG.md SECURITY.md; do
    [[ -f "$SOURCE_DIR/$file" ]] && cp "$SOURCE_DIR/$file" "$APP_DIR/"
  done
fi

echo "[3/4] Creating command..."
cat > "$BIN" <<WRAPPER
#!/usr/bin/env bash
export PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec /usr/bin/python3 -m remnawave_updater.cli "\$@"
WRAPPER
chmod 755 "$BIN"

echo "[4/4] Done."
echo
if [[ $RUN_SETUP -eq 1 ]]; then
  exec "$BIN" setup
else
  echo "Run setup: sudo remnawave-updater setup"
fi
