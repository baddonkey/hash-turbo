# -*- mode: python ; coding: utf-8 -*-
# macOS-specific PyInstaller spec — produces a .app bundle and standalone CLI binary.
# Run via: scripts/build_macos.sh
import re
from pathlib import Path

_version_match = re.search(
    r'^__version__\s*=\s*["\']([^"\']+)["\']',
    Path('src/hash_turbo/__init__.py').read_text(encoding='utf-8'),
    re.MULTILINE,
)
VERSION = _version_match.group(1) if _version_match else '0.0.0'

# Optional: include user-manual PDF if it has been generated
_pdf = Path('docs/user-manual.pdf')
_extra_datas = [(_pdf.as_posix(), 'hash_turbo/assets')] if _pdf.exists() else []

a = Analysis(
    ['src/hash_turbo/cli/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/hash_turbo/assets/icon.png', 'hash_turbo/assets'),
        ('src/hash_turbo/i18n/locales', 'hash_turbo/i18n/locales'),
        ('src/hash_turbo/gui/qml', 'hash_turbo/gui/qml'),
        ('THIRD-PARTY-LICENSES.md', 'hash_turbo/assets'),
        *_extra_datas,
    ],
    hiddenimports=[
        'hash_turbo.gui',
        'hash_turbo.gui.app',
        'hash_turbo.gui.hash_view_model',
        'hash_turbo.gui.verify_view_model',
        'hash_turbo.gui.sanitize_view_model',
        'hash_turbo.gui.settings_model',
        'hash_turbo.gui.hash_worker',
        'hash_turbo.gui.verify_worker',
        'hash_turbo.gui.sanitize_worker',
        'hash_turbo.gui.gettext_translator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# ── Single unified binary — console=True so CLI stdout/stderr always work;
# GUI hides the console window via AppKit before Qt opens its first frame.
# onedir mode: Qt libs stay on disk inside the .app bundle, fast startup.
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,   # defer binaries/datas to COLLECT (onedir mode)
    name='hash-turbo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='hash-turbo',
)

# ── .app bundle ────────────────────────────────────────────────────────────────
app = BUNDLE(
    coll,
    name='hash-turbo.app',
    icon='assets/icon.icns',
    bundle_identifier='com.hash-turbo.app',
    info_plist={
        'CFBundleName': 'hash-turbo',
        'CFBundleDisplayName': 'hash-turbo',
        'CFBundleExecutable': 'hash-turbo',
        'CFBundleVersion': VERSION,
        'CFBundleShortVersionString': VERSION,
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': '????',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15',
        'NSPrincipalClass': 'NSApplication',
        'NSRequiresAquaSystemAppearance': False,  # supports Dark Mode
    },
)
