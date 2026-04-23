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

# ── CLI binary (console=True, runs in Terminal) ────────────────────────────────
exe_cli = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='hash-turbo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.icns',
)

# ── GUI binary (console=False, wrapped in .app bundle below) ──────────────────
# onedir mode: binaries/datas go into COLLECT so they live on disk inside the
# .app bundle and are never extracted at launch — eliminates the ~30 s startup.
exe_gui = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,   # defer binaries/datas to COLLECT (onedir mode)
    name='hash-turbo-gui',
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

coll_gui = COLLECT(
    exe_gui,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='hash-turbo-gui',
)

# ── .app bundle ────────────────────────────────────────────────────────────────
app = BUNDLE(
    coll_gui,
    name='hash-turbo.app',
    icon='assets/icon.icns',
    bundle_identifier='com.hash-turbo.app',
    info_plist={
        'CFBundleName': 'hash-turbo',
        'CFBundleDisplayName': 'hash-turbo',
        'CFBundleExecutable': 'hash-turbo-gui',
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
