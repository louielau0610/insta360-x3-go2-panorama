#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor"
BUILD="$ROOT/.vendor/x5_sdk"
ARCH="$(uname -m)"
if [[ -n "${X5_SDK_ARCHIVE:-}" ]]; then
  ARCHIVE="$X5_SDK_ARCHIVE"
elif [[ "$ARCH" == "x86_64" ]]; then
  ARCHIVE="$VENDOR/CameraSDK-2.1.1-Linux.tar.gz"
elif [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
  if [[ -f "$HOME/CameraSDK-2.1.1-jetson.tar.gz" ]]; then
    ARCHIVE="$HOME/CameraSDK-2.1.1-jetson.tar.gz"
  else
    ARCHIVE="$VENDOR/CameraSDK-2.1.1-gcc-arm-11.2-2022.02-x86_64-aarch64-none-linux-gnu.tar.gz"
  fi
else
  echo "Unsupported architecture: $ARCH" >&2
  exit 2
fi
[[ -f "$ARCHIVE" ]] || { echo "Camera SDK archive missing: $ARCHIVE" >&2; exit 3; }
rm -rf "$BUILD"
mkdir -p "$BUILD" "$ROOT/bin" "$ROOT/lib"
tar -xf "$ARCHIVE" -C "$BUILD"
SDK_ROOT="$(find "$BUILD" -type f -name libCameraSDK.so -printf '%h\n' | head -1 | xargs dirname)"
g++ -std=c++17 -O2 -pthread "$ROOT/native/x5_stream_recorder.cc" \
  -I"$SDK_ROOT/include" -L"$SDK_ROOT/lib" -lCameraSDK \
  -Wl,-rpath,'$ORIGIN/../lib' -o "$ROOT/bin/x5-stream-recorder"
cp "$SDK_ROOT/lib/libCameraSDK.so" "$ROOT/lib/"
echo "Built $ROOT/bin/x5-stream-recorder"
