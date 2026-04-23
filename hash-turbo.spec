# -*- mode: python ; coding: utf-8 -*-
import re
from pathlib import Path

# Read version from the single source of truth
_version_match = re.search(
    r'^__version__\s*=\s*["\']([^"\']+)["\']',
    Path('src/hash_turbo/__init__.py').read_text(encoding='utf-8'),
    re.MULTILINE,
)
VERSION = _version_match.group(1) if _version_match else '0.0.0'
_major, _minor, _patch = (VERSION.split('.') + ['0', '0', '0'])[:3]
VERSION_TUPLE = (int(_major), int(_minor), int(_patch), 0)

# Generate version_info.py for Windows exe metadata
Path('version_info.py').write_text(
    f'''\
# Auto-generated from hash-turbo.spec — do not edit manually.
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers={VERSION_TUPLE},
        prodvers={VERSION_TUPLE},
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "hash-turbo"),
                        StringStruct("FileDescription", "hash-turbo — Cross-platform file hash management tool"),
                        StringStruct("FileVersion", "{VERSION}"),
                        StringStruct("InternalName", "hash-turbo"),
                        StringStruct("LegalCopyright", "Copyright (c) 2025-2026 hash-turbo contributors"),
                        StringStruct("OriginalFilename", "hash-turbo.exe"),
                        StringStruct("ProductName", "hash-turbo"),
                        StringStruct("ProductVersion", "{VERSION}"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
''',
    encoding='utf-8',
)


a = Analysis(
    ['src\\hash_turbo\\cli\\app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src\\hash_turbo\\assets\\icon.png', 'hash_turbo\\assets'),
        ('src\\hash_turbo\\assets\\icon.ico', 'hash_turbo\\assets'),
        ('src\\hash_turbo\\i18n\\locales', 'hash_turbo\\i18n\\locales'),
        ('src\\hash_turbo\\gui\\qml', 'hash_turbo\\gui\\qml'),
        ('docs\\user-manual.pdf', 'hash_turbo\\assets'),
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# CLI executable — console=True so stdin/stdout/stderr work in terminals
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
    version='version_info.py',
)

# GUI executable — onedir so Qt libs live in the install directory (no per-launch extraction)
exe_gui = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
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
    icon=['assets\\icon.ico'],
    version='version_info.py',
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
