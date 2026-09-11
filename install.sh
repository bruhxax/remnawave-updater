#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/remnawave-updater"
BIN="/usr/local/bin/remnawave-updater"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_SETUP=1

if [[ "${1:-}" == "--no-setup" ]]; then
  RUN_SETUP=0
elif [[ $# -gt 0 ]]; then
  echo "Usage: sudo ./install.sh [--no-setup]"
  exit 2
fi

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo ./install.sh"
  exit 1
fi

echo "[1/3] Checking requirements..."
missing=()
for cmd in python3 docker ssh ssh-keygen; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing+=("$cmd")
  else
    printf '  ✓ %s\n' "$cmd"
  fi
done

if ! python3 - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "  ✗ Python 3.10+ is required."
  exit 1
fi

if command -v docker >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
  missing+=("docker-compose-plugin")
else
  printf '  ✓ docker compose\n'
fi

if ((${#missing[@]})); then
  echo
  echo "Missing requirements: ${missing[*]}"
  echo "Remnawave Updater does not run apt update/install automatically."
  echo "Install the missing packages manually and run this installer again."
  echo
  echo "Ubuntu/Debian examples:"
  echo "  OpenSSH tools:  apt install openssh-client"
  echo "  Python 3:       apt install python3"
  echo "  Docker:         https://docs.rw/install/requirements/"
  exit 1
fi

PYTHON_BIN="$(command -v python3)"

echo "[2/3] Installing Remnawave Updater..."
mkdir -p "$APP_DIR"
if [[ "$SOURCE_DIR" != "$APP_DIR" ]]; then
  rm -rf "$APP_DIR/remnawave_updater" "$APP_DIR/tests"
  cp -a "$SOURCE_DIR/remnawave_updater" "$APP_DIR/"
  cp -a "$SOURCE_DIR/tests" "$APP_DIR/" 2>/dev/null || true
  for file in pyproject.toml requirements.txt README.md README_EN.md LICENSE CHANGELOG.md SECURITY.md CONTRIBUTING.md; do
    [[ -f "$SOURCE_DIR/$file" ]] && cp "$SOURCE_DIR/$file" "$APP_DIR/"
  done
fi

cat > "$BIN" <<WRAPPER
#!/usr/bin/env bash
export PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PYTHON_BIN" -m remnawave_updater.cli "\$@"
WRAPPER
chmod 755 "$BIN"

echo "[3/3] Done."
echo "  ✓ No apt update"
echo "  ✓ No pip install"
echo "  ✓ No third-party Python packages"
echo

if [[ $RUN_SETUP -eq 1 ]]; then
  exec "$BIN" setup
else
  echo "Run setup: sudo remnawave-updater setup"
fi
