#!/usr/bin/env bash
# Build Endless Sky 0.11.2 with the combat-log patch, for playing with monitoring.
# A separate copy in ~/es-observe (or $ES_OBSERVE); your installed game is not touched.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BASE=${ES_OBSERVE:-$HOME/es-observe}
SRC=$BASE/src
BUILD=$BASE/build

if command -v dnf >/dev/null; then
  echo "Build dependencies (Fedora), if not installed yet:"
  echo "  sudo dnf install gcc-c++ cmake ninja-build SDL2-devel libpng-devel libjpeg-turbo-devel libavif-devel \\"
  echo "    mesa-libGL-devel glew-devel minizip-devel openal-soft-devel libmad-devel flac-devel libuuid-devel pkgconf git"
fi

mkdir -p "$BASE"
if [ ! -d "$SRC/.git" ]; then
  git clone --branch v0.11.2 --depth 1 https://github.com/endless-sky/endless-sky "$SRC"
fi
cd "$SRC"
git checkout -- . && git clean -fdq source
git apply "$HERE/combat-log.patch"
cmake -S "$SRC" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DES_USE_VCPKG=OFF -DES_USE_SYSTEM_LIBRARIES=ON \
  -DBUILD_TESTING=OFF
ninja -C "$BUILD"
echo
echo "Built: $BUILD/endless-sky. Play with: $HERE/play.sh"
