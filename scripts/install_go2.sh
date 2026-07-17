#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$ROOT/.venv-go2}"
SDK_DIR="${UNITREE_SDK_DIR:-$ROOT/.vendor/unitree_sdk2_python}"
SDK_COMMIT="e4cd91f051aaa77a70600e3d2bf7f50889db1980"

sudo apt-get update
sudo apt-get install -y build-essential cmake git python3-dev python3-pip python3-venv ffmpeg iproute2 iputils-ping v4l-utils
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/python" -m pip install -r "$ROOT/requirements-go2.txt"
"$VENV/bin/python" -m pip install --no-deps -e "$ROOT"

mkdir -p "$(dirname "$SDK_DIR")"
if [[ ! -d "$SDK_DIR/.git" ]]; then
  git clone https://github.com/unitreerobotics/unitree_sdk2_python.git "$SDK_DIR"
fi
git -C "$SDK_DIR" fetch --all --tags
git -C "$SDK_DIR" checkout "$SDK_COMMIT"
if ! "$VENV/bin/python" -m pip install "cyclonedds==0.10.2"; then
  cat >&2 <<'EOF'
Unitree SDK installation failed, usually because CycloneDDS 0.10.2 is missing.
Follow the official fallback:
  git clone https://github.com/eclipse-cyclonedds/cyclonedds -b releases/0.10.x ~/cyclonedds
  cmake -S ~/cyclonedds -B ~/cyclonedds/build -DCMAKE_INSTALL_PREFIX=~/cyclonedds/install
  cmake --build ~/cyclonedds/build --target install -j"$(nproc)"
  export CYCLONEDDS_HOME=~/cyclonedds/install
Then rerun this script with CYCLONEDDS_HOME exported.
EOF
  exit 1
fi
"$VENV/bin/python" -m pip install --no-deps -e "$SDK_DIR"

echo "Installed. Activate with: source '$VENV/bin/activate'"
