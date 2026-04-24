#!/usr/bin/env bash
# build_macos.sh — Build a self-contained macOS distribution for hash-turbo.
#
# Produces:
#   dist/hash-turbo.app          — unified app bundle (CLI + GUI)
#   dist/hash-turbo-<version>.dmg — distributable disk image
#
# Usage:
#   bash scripts/build_macos.sh
#   bash scripts/build_macos.sh --sign "Developer ID Application: Your Name (TEAMID)"
#
# Requirements:
#   pip install pyinstaller
#   Xcode Command Line Tools (for iconutil / hdiutil)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── Parse arguments ────────────────────────────────────────────────────────────
SIGN_IDENTITY=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sign) SIGN_IDENTITY="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Read version ───────────────────────────────────────────────────────────────
VERSION=$(python3 -c "
import re, pathlib
m = re.search(r'__version__\s*=\s*[\"\\']([^\"\\']+)[\"\\']',
              pathlib.Path('src/hash_turbo/__init__.py').read_text())
print(m.group(1) if m else '0.0.0')
")
echo "Building hash-turbo $VERSION for macOS …"

# ── Generate .icns from bundled PNGs ──────────────────────────────────────────
ICONSET_DIR="$(mktemp -d)/hash-turbo.iconset"
mkdir -p "$ICONSET_DIR"

# iconutil expects specific filenames; map our assets to them
cp assets/icon_16.png  "$ICONSET_DIR/icon_16x16.png"
cp assets/icon_32.png  "$ICONSET_DIR/icon_16x16@2x.png"
cp assets/icon_32.png  "$ICONSET_DIR/icon_32x32.png"
cp assets/icon_64.png  "$ICONSET_DIR/icon_32x32@2x.png"
cp assets/icon_128.png "$ICONSET_DIR/icon_128x128.png"
cp assets/icon_256.png "$ICONSET_DIR/icon_128x128@2x.png"
cp assets/icon_256.png "$ICONSET_DIR/icon_256x256.png"
cp assets/icon_512.png "$ICONSET_DIR/icon_256x256@2x.png"
cp assets/icon_512.png "$ICONSET_DIR/icon_512x512.png"

iconutil --convert icns --output assets/icon.icns "$ICONSET_DIR"
echo "  icon.icns generated."

# ── Build with PyInstaller ─────────────────────────────────────────────────────
pyinstaller \
    --noconfirm \
    --clean \
    hash-turbo-macos.spec

echo "  PyInstaller build complete."

# ── Ad-hoc or Developer-ID code signing ───────────────────────────────────────
sign_item() {
    local path="$1"
    if [[ -n "$SIGN_IDENTITY" ]]; then
        codesign --force --deep --options runtime \
            --sign "$SIGN_IDENTITY" "$path"
    else
        # Ad-hoc signature — runs locally, not notarized
        codesign --force --deep --sign - "$path"
    fi
}

sign_item "dist/hash-turbo.app"
echo "  Code signing done."

# ── Create DMG ────────────────────────────────────────────────────────────────
DMG_NAME="hash-turbo-${VERSION}-macos.dmg"
DMG_STAGING="$(mktemp -d)/dmg-staging"
mkdir -p "$DMG_STAGING"

cp -R "dist/hash-turbo.app" "$DMG_STAGING/"

# Symlink to /Applications for drag-and-drop install
ln -s /Applications "$DMG_STAGING/Applications"

# Write a minimal README inside the DMG
cat > "$DMG_STAGING/README.txt" <<'EOF'
hash-turbo — Cross-platform file hash management tool

• Drag hash-turbo.app into Applications to install.
• For CLI access, double-click "Install CLI Tool.command" in this DMG.
  This creates a /usr/local/bin/hash-turbo symlink so you can run
  hash-turbo from any terminal.

Full documentation: https://github.com/baddonkey/hash-turbo
EOF

# Double-clickable .command script to install the CLI symlink
cat > "$DMG_STAGING/Install CLI Tool.command" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APP="/Applications/hash-turbo.app"
BINARY="$APP/Contents/MacOS/hash-turbo"
LINK="/usr/local/bin/hash-turbo"

if [[ ! -d "$APP" ]]; then
    echo "ERROR: hash-turbo.app not found in /Applications."
    echo "       Drag hash-turbo.app into Applications first, then re-run this script."
    exit 1
fi

sudo mkdir -p /usr/local/bin
sudo ln -sf "$BINARY" "$LINK"
echo "✓ Installed: $LINK -> $BINARY"
echo "  You can now run 'hash-turbo' from any terminal."
EOF
chmod +x "$DMG_STAGING/Install CLI Tool.command"

# Build a compressed read-only DMG
hdiutil create \
    -volname "hash-turbo $VERSION" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    -fs HFS+ \
    "dist/$DMG_NAME"

echo ""
echo "Done! Artifacts:"
echo "  dist/hash-turbo.app"
echo "  dist/$DMG_NAME"
