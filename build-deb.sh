#!/usr/bin/env bash
set -euo pipefail

PROJECT="ryzenadj-control"
VERSION="${1:-0.1.1}"
ARCH="${2:-amd64}"
PKGROOT="${PROJECT}_${VERSION}_${ARCH}"
DEBFILE="${PKGROOT}.deb"

rm -rf "${PKGROOT}" "${DEBFILE}"

mkdir -p "${PKGROOT}/DEBIAN"
mkdir -p "${PKGROOT}/usr/lib/${PROJECT}"
mkdir -p "${PKGROOT}/usr/bin"
mkdir -p "${PKGROOT}/usr/share/applications"
mkdir -p "${PKGROOT}/usr/share/icons/hicolor/scalable/apps"

cp -r main.py ui core resources "${PKGROOT}/usr/lib/${PROJECT}/"
find "${PKGROOT}/usr/lib/${PROJECT}" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "${PKGROOT}/usr/lib/${PROJECT}" -type f -name "*.pyc" -delete

cat > "${PKGROOT}/usr/bin/${PROJECT}" << 'EOF'
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/lib/ryzenadj-control/main.py "$@"
EOF
chmod 755 "${PKGROOT}/usr/bin/${PROJECT}"

cat > "${PKGROOT}/DEBIAN/control" << EOF
Package: ${PROJECT}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: h4us0x <95170448+h4us0x@users.noreply.github.com>
Depends: python3, python3-pyqt6, ryzenadj, policykit-1
Description: PyQt6 GUI for ryzenadj
 GUI for managing Ryzen CPU settings via ryzenadj.
EOF

install -m 644 resources/icons/logo-taskbar.svg \
  "${PKGROOT}/usr/share/icons/hicolor/scalable/apps/${PROJECT}.svg"

cat > "${PKGROOT}/usr/share/applications/${PROJECT}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=RyzenAdj Control
Comment=GUI for managing Ryzen CPU settings via ryzenadj
Exec=${PROJECT}
Icon=${PROJECT}
Terminal=false
Categories=System;Settings;
StartupNotify=true
EOF
chmod 644 "${PKGROOT}/usr/share/applications/${PROJECT}.desktop"

dpkg-deb --build --root-owner-group "${PKGROOT}"
echo "Built ${DEBFILE}"
