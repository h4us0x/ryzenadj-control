#!/usr/bin/env bash
set -euo pipefail

PROJECT="ryzenadj-gui"
VERSION="${1:-0.1.0}"
OUT_DIR="dist"
PKG_DIR="${PROJECT}-${VERSION}"

rm -rf "${OUT_DIR}" "${PKG_DIR}"
mkdir -p "${OUT_DIR}" "${PKG_DIR}"

cp -r main.py ui core resources pics requirements.txt README.md LICENSE "${PKG_DIR}"

tar -czf "${OUT_DIR}/${PKG_DIR}.tar.gz" "${PKG_DIR}"
rm -rf "${PKG_DIR}"

echo "Built ${OUT_DIR}/${PKG_DIR}.tar.gz"
