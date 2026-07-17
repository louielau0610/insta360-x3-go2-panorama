#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$ROOT/.venv-jetson}"
SDK_DIR="${UNITREE_SDK_DIR:-$ROOT/.vendor/unitree_sdk2_python}"
SDK_COMMIT="e4cd91f051aaa77a70600e3d2bf7f50889db1980"
export CYCLONEDDS_HOME="${CYCLONEDDS_HOME:-$HOME/unitree_ros2/cyclonedds_ws/install/cyclonedds}"

[[ -f "$CYCLONEDDS_HOME/lib/libddsc.so" ]] || {
  echo "CycloneDDS installation not found: $CYCLONEDDS_HOME" >&2
  exit 2
}

python3 -c 'import sys; assert sys.version_info >= (3, 8), sys.version'
if [[ ! -x "$VENV/bin/python" ]]; then
  if ! python3 -m venv --system-site-packages "$VENV"; then
    rm -rf "$VENV"
    python3 -m pip install --user "virtualenv<21"
    python3 -m virtualenv --system-site-packages "$VENV"
  fi
fi
"$VENV/bin/python" -m pip install --upgrade "pip<26" "setuptools<76" wheel
"$VENV/bin/python" -m pip install --index-url https://pypi.org/simple -r "$ROOT/requirements-jetson.txt"
"$VENV/bin/python" -m pip install --index-url https://pypi.org/simple --no-deps --ignore-requires-python "py360convert==1.0.4"
SITE_PACKAGES="$("$VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')"
for module in "$SITE_PACKAGES"/py360convert/*.py; do
  if ! head -1 "$module" | grep -q 'from __future__ import annotations'; then
    sed -i '1i from __future__ import annotations' "$module"
  fi
done
"$VENV/bin/python" -m pip install --no-deps -e "$ROOT"

mkdir -p "$(dirname "$SDK_DIR")"
if [[ ! -d "$SDK_DIR/.git" ]]; then
  git clone https://github.com/unitreerobotics/unitree_sdk2_python.git "$SDK_DIR"
fi
if ! git -C "$SDK_DIR" cat-file -e "$SDK_COMMIT^{commit}"; then
  git -C "$SDK_DIR" fetch origin "$SDK_COMMIT"
fi
git -C "$SDK_DIR" checkout "$SDK_COMMIT"
"$VENV/bin/python" -m pip install --no-deps -e "$SDK_DIR"

echo "Installed. Activate with: source '$VENV/bin/activate'"
