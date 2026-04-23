# Third-Party Licenses

This file lists all third-party software used in hash-turbo, along with their
licenses and upstream URLs.

---

## Python Runtime Dependencies

These packages are required at runtime by the application.

| Package | Used for | License | URL |
|---------|----------|---------|-----|
| [click](https://pypi.org/project/click/) | CLI framework — argument parsing, command groups, help text, `--help` output for all subcommands | BSD-3-Clause | https://palletsprojects.com/p/click/ |

---

## Python GUI Dependencies

These packages are required when running the graphical interface
(`hash-turbo gui`).

| Package | Used for | License | URL |
|---------|----------|---------|-----|
| [PySide6](https://pypi.org/project/PySide6/) | Qt bindings — QML engine, Qt Quick / Material UI, threading (`QThread`), file dialogs, and the application event loop | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | https://pyside.org |
| [pyobjc-framework-Cocoa](https://pypi.org/project/pyobjc-framework-Cocoa/) *(macOS only)* | macOS Cocoa bridge — used to apply the native appearance and dark-mode integration on macOS | MIT | https://github.com/ronaldoussoren/pyobjc |

---

## Build System

These packages are used to build and package hash-turbo from source.

| Package | Used for | License | URL |
|---------|----------|---------|-----|
| [setuptools](https://pypi.org/project/setuptools/) | Python package build backend — compiles the `hash-turbo` wheel and installs the `hash-turbo` entry-point script | MIT | https://github.com/pypa/setuptools |
| [setuptools-scm](https://pypi.org/project/setuptools-scm/) | Derives the package version automatically from the Git tag so `__version__` is always in sync with the release tag | MIT | https://github.com/pypa/setuptools_scm |
| [PyInstaller](https://pypi.org/project/pyinstaller/) | Freezes the CLI and GUI into self-contained binaries (`hash-turbo`, `hash-turbo.app`) that run without a Python installation | GPL-2.0-or-later with Bootloader Exception | https://pyinstaller.org |
| [WiX Toolset v4](https://www.nuget.org/packages/wix) *(Windows installer)* | Compiles the `hash-turbo.wxs` descriptor into a distributable MSI installer for Windows | Microsoft Reciprocal License (MS-RL) | https://wixtoolset.org |

> **PyInstaller Bootloader Exception:** The PyInstaller bootloader (the stub
> that loads your frozen application) is licensed under the Apache 2.0 License.
> Only the build tool itself is GPL-2.0-or-later; the generated executables are
> not affected by the GPL.

---

## Development & Test Dependencies

These packages are used during development and CI, not shipped in releases.

| Package | Used for | License | URL |
|---------|----------|---------|-----|
| [pytest](https://pypi.org/project/pytest/) | Test runner — executes all unit and integration tests under `tests/` | MIT | https://docs.pytest.org |
| [pytest-qt](https://pypi.org/project/pytest-qt/) | Qt/PySide6 test helpers — provides the `qtbot` fixture used in GUI tests to drive the QML interface | MIT | https://github.com/pytest-dev/pytest-qt |
| [mypy](https://pypi.org/project/mypy/) | Static type checker — enforces `--strict` type correctness across the entire `src/` tree | MIT | https://www.mypy-lang.org |

---

## Internationalization (i18n) Tools

These packages are used to extract, update, and compile translation catalogs.

| Package | Used for | License | URL |
|---------|----------|---------|-----|
| [Babel](https://pypi.org/project/Babel/) | `pybabel` CLI — extracts translatable strings from Python source, updates `.po` files, and compiles them to binary `.mo` catalogs loaded at runtime | BSD-3-Clause | https://babel.pocoo.org |

---

## Optional Script Dependencies

These packages are only needed when running the documentation / tutorial
scripts in `scripts/`. They are **not** required to build or run hash-turbo
itself.

| Package | Used for | License | URL |
|---------|----------|---------|-----|
| [edge-tts](https://pypi.org/project/edge-tts/) | `record_*.py` — generates neural TTS narration audio clips (MP3) that are mixed with the screen-capture video to produce the tutorial MP4s | MIT | https://github.com/rany2/edge-tts |
| [Markdown](https://pypi.org/project/Markdown/) | `generate_pdf.py` — converts `docs/user-manual.md` to HTML as an intermediate step before headless-Chrome PDF rendering | BSD-3-Clause | https://python-markdown.github.io |
| [websocket-client](https://pypi.org/project/websocket-client/) | `generate_pdf.py` — communicates with Chrome over the DevTools Protocol (CDP) to trigger PDF export | Apache-2.0 | https://github.com/websocket-client/websocket-client |

---

## System / External Tools

These tools must be available on `PATH` when running the build or documentation
scripts. They are **not** Python packages.

| Tool | Used for | License | URL |
|------|----------|---------|-----|
| [ffmpeg](https://ffmpeg.org) | `record_*.py` — encodes screen-capture frames and narration audio into the final MP4 tutorial videos | LGPL-2.1-or-later / GPL-2.0-or-later | https://ffmpeg.org |
| `iconutil` *(macOS)* | `build_macos.sh` — converts the PNG icon assets into an `.icns` file embedded in the `.app` bundle | Proprietary (Xcode Command Line Tools) | https://developer.apple.com/xcode |
| `hdiutil` *(macOS)* | `build_macos.sh` — packages the built `.app` bundle into a distributable `.dmg` disk image | Proprietary (macOS built-in) | https://developer.apple.com/macos |
| [Google Chrome](https://www.google.com/chrome/) | `generate_pdf.py` — renders the HTML user manual to a PDF via the headless Chrome DevTools Protocol | Proprietary / Freeware | https://www.google.com/chrome |
