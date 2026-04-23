# hash-turbo — File Hash Management Tool

> Last updated: 2026-04-21

## Problem Statement

Verifying file integrity is a routine task for developers, sysadmins, and security-conscious users. Existing tools (`sha256sum`, `md5sum`) are fragmented across platforms, lack a unified interface, and offer no GUI. Users need a single, cross-platform tool that can generate, store, and verify file hashes with support for many algorithms — accessible both from the command line and a desktop UI.

## Users

- **Developers** verifying build artifacts, downloads, or release assets
- **Sysadmins** auditing file integrity across systems
- **End users** who prefer a visual interface for hash operations

## Platforms

- macOS
- Linux
- Windows

## Interfaces

| Interface | Technology | Purpose |
|-----------|-----------|---------|
| CLI | Python `click` | Scriptable, pipeline-friendly hash operations |
| GUI | PySide6 + QML (Qt Quick / Material) | Visual file selection, hash generation, and verification |

Both interfaces share the same core library — no logic duplication.

## Dependency Management

pip with `pyproject.toml`. No additional build tooling.

## Distribution

Two standalone binaries via PyInstaller for macOS, Linux, and Windows. Published as GitHub releases.

| Binary | Console | Purpose |
|--------|---------|-------|
| `hash-turbo` | Yes | CLI usage — full terminal stdin/stdout/stderr support |
| `hash-turbo-gui` | No | GUI-only — launches without a console window |

---

## Core Features

### F1 — Hash Generation (single file)

Generate a hash for a single file using a specified algorithm.

```
$ hash-turbo hash path/to/file.zip
SHA-256: 3a7bd3e2...af91c
```

- Default algorithm: SHA-256
- `--algorithm` / `-a` flag to select a different algorithm
- Output: `<algorithm>: <hex digest>`

### F2 — Hash Generation (multiple files)

Generate hashes for multiple files or an entire directory tree.

```
$ hash-turbo hash file1.txt file2.txt
$ hash-turbo hash src/ --recursive
```

- Accept multiple file paths, glob patterns, or directories
- `--recursive` / `-r` flag for directory traversal
- `--glob` / `-g` pattern for filtering (e.g., `*.py`)
- `--exclude` pattern to skip files (e.g., `__pycache__`)
- Output: one line per file — `<hash>  <path>`

### F3 — Hash File Generation

Write hashes to a combined hash file (compatible with `sha256sum` / BSD format).

```
$ hash-turbo hash src/ -r -o checksums.sha256
```

- `--output` / `-o` to write results to a file
- `--format` option: `gnu` (default, `<hash>  <path>`), `bsd` (`SHA256 (file) = <hash>`), or `json`
- `--path-mode`: `relative` (default) or `absolute`
  - Relative paths are computed from the hash file's location or a `--base-dir`
- Hash file extension is configurable — defaults to `.<algorithm>` (e.g., `.sha256`), overridden by the output filename if given

### F4 — Hash Verification

Verify files against a previously generated hash file.

```
$ hash-turbo verify checksums.sha256
file1.txt: OK
file2.txt: FAILED
```

- Read hash files in both GNU and BSD formats (auto-detect)
- `--strict` flag: fail on missing files (default: warn and continue)
- Exit codes: `0` = all OK, `1` = mismatch or missing file
- `--quiet` / `-q`: only show failures
- `--flexible-whitespace` / `--no-flexible-whitespace`: accept tabs and multiple spaces in GNU format (default: enabled)
- `--binary-only` / `--no-binary-only`: always hash in binary mode, ignoring the text/binary indicator (default: enabled)
- Verify a single file against an expected hash inline:
  ```
  $ hash-turbo verify file.zip --expect 3a7bd3e2...af91c
  ```

### F5 — Hash File Sanitization

Transform an existing hash manifest file — convert between formats, normalize paths, and clean up entries.

```
$ hash-turbo sanitize checksums.sha256 --format bsd --hash-case lower
$ hash-turbo sanitize checksums.sha256 --strip-prefix C:/projects --separator posix
$ hash-turbo sanitize checksums.sha256 --deduplicate --sort path -o cleaned.sha256
```

- `--format`: Convert to `gnu` or `bsd` (auto-detects input format if omitted)
- `--separator`: Normalize path separators — `keep` (default), `posix` (`/`), or `windows` (`\`)
- `--strip-prefix <path>`: Remove a leading path prefix from all entries, making them relative
- `--hash-case`: Normalize hex digest casing — `keep` (default), `lower`, or `upper`
- `--sort`: Sort entries — `none` (default), `path`, `hash`, or `filesystem`
- `--deduplicate`: Remove duplicate entries by path (case-insensitive)
- `--line-ending`: Line ending style — `system` (default), `lf`, `crlf`, or `cr`
- `--normalize-whitespace` / `--no-normalize-whitespace`: accept and fix irregular whitespace in GNU format (default: enabled)
- `-o` / `--output`: Write result to a file (default: stdout)
- Available in both CLI and GUI (Sanitize tab)

### F6 — Supported Algorithms

Support all algorithms available in Python's `hashlib`, including:

| Algorithm | Flag value |
|-----------|-----------|
| MD5 | `md5` |
| SHA-1 | `sha1` |
| SHA-224 | `sha224` |
| SHA-256 | `sha256` (default) |
| SHA-384 | `sha384` |
| SHA-512 | `sha512` |
| SHA3-256 | `sha3-256` |
| SHA3-512 | `sha3-512` |
| BLAKE2b | `blake2b` |
| BLAKE2s | `blake2s` |

- `hash-turbo algorithms` command to list all available algorithms at runtime
- Support any algorithm string that `hashlib.new()` accepts (future-proof)

### F7 — GUI Application

A PySide6 + QML (Qt Quick with Material style) desktop application providing visual access to all core features.

**Hash Generation View:**
- Drag-and-drop or file picker for single/multiple files and folders
- Algorithm selector (dropdown)
- Format selector (GNU / BSD)
- Recursive checkbox (checked by default) — controls whether subdirectories are scanned
- Relative paths checkbox with configurable base directory
- Output file field for writing results to a hash file (auto-filled from folder selection)
- Progress bar with percentage and current file name
- Rolling results terminal (monospace, last 200 lines) showing hash output in selected format
- Activity log showing scan progress and status messages
- Concurrent scan + hash pipeline: files are hashed as they are discovered, not after a full scan completes

**Hash Verification View:**
- Load a hash file via file picker or drag-and-drop onto a drop zone
- Reload button to re-read a previously loaded file from disk
- Read-only input preview (monospace) showing loaded hash entries (first 200 lines for large files)
- Custom base directory override for resolving file paths
- Options: output folder, detect new files, flexible whitespace, binary mode only
- Visual pass/fail indicators per file (OK, FAIL, MISSING, NEW)
- Progress bar with percentage during verification
- Activity log with summary: passed, failed, missing, new
- Report generation — open the verification report file after completion

**Sanitize View:**
- Load a hash file via file picker or drag-and-drop onto a drop zone
- Reload button to re-read a previously loaded file from disk
- Read-only input preview (monospace) showing loaded hash entries (first 200 lines for large files)
- Options panel: output format, path separator, strip prefix, hash case, sort, deduplicate, normalize whitespace, line ending
- Output file field — auto-filled as `<stem>-sanitized.<ext>` from the loaded file
- Transform button applies all selected operations; result auto-saved to output file
- Result displayed in a ListView with alternating row colors on a terminal-style black background

**Settings:**
- Default algorithm
- Default path mode (relative/absolute)
- Default output format (GNU/BSD/JSON)
- Theme (system/light/dark)
- Language selector (EN, DE, FR, IT, Rumantsch) — translations via gettext `.po`/`.mo` files
- Exclude patterns: one pattern per line; supports fnmatch globs and `re:`-prefixed regex (e.g., `Thumbs.db`, `re:^\..+`). Persisted via QSettings across sessions. Defaults: `Thumbs.db`, `re:^\..+` (hidden files).

**Application Icon:**
- Custom icon displayed in window title bar and taskbar/dock
- macOS dock icon set via `pyobjc-framework-Cocoa` (AppKit) with graceful fallback

### F8 — Cross-Platform Behavior

- Path separators normalized per platform in output
- Hash file portability: paths stored with `/` in hash files, resolved to platform separator on verification
- GUI uses native file dialogs via PySide6 QML
- `pyobjc-framework-Cocoa` (macOS only) for native dock icon; imported with graceful fallback on other platforms

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Large file support** | Stream files in chunks (default 1 MiB) using zero-copy `readinto` + `memoryview`; never load entire file into memory |
| **Performance** | Hash files up to 10 GB without excessive memory usage |
| **Parallelism** | `--jobs` / `-j` flag for concurrent hashing of multiple files (default: CPU count) |
| **Encoding** | Hash files are UTF-8; handle non-ASCII filenames gracefully |
| **Exit codes** | `0` = success, `1` = verification failure, `2` = usage error |
| **Logging** | `--verbose` / `-v` for detailed output; `--quiet` / `-q` for minimal output |

---

## Architecture

```
src/hash_turbo/
├── core/               # Domain logic — no I/O dependencies
│   ├── hasher.py        # Hash computation (single file, streaming)
│   ├── hash_file.py     # Parse and write hash files (GNU/BSD)
│   ├── verifier.py      # Compare computed vs expected hashes
│   ├── sanitizer.py     # Hash file transformation (format, paths, dedup)
│   ├── models.py        # Domain types: HashResult, HashEntry, Algorithm
│   └── exclude_filter.py # Filename exclusion (fnmatch + regex patterns)
├── cli/                 # CLI adapter
│   ├── app.py           # Entry point, argument parsing
│   └── formatters.py    # Output formatting (table, plain, JSON)
├── gui/                 # PySide6 QML adapter
│   ├── app.py           # QGuiApplication + QQmlApplicationEngine setup
│   ├── gettext_translator.py # QTranslator bridge: QML qsTr() → gettext
│   ├── hash_view_model.py    # QML view model for hash generation
│   ├── hash_worker.py        # Background QThread: concurrent scan + hash pipeline
│   ├── verify_view_model.py  # QML view model for verification
│   ├── verify_worker.py      # Background QThread for verification
│   ├── sanitize_view_model.py # QML view model for sanitize/transform
│   ├── sanitize_worker.py    # Background QThread for sanitize/transform
│   ├── settings_model.py     # QML view model for settings (QSettings)
│   └── qml/                  # QML UI files (Material style)
│       ├── Main.qml           # Root window, tab layout
│       ├── HashView.qml       # Hash generation view
│       ├── VerifyView.qml     # Verification view
│       ├── SanitizeView.qml   # Sanitize/transform view
│       ├── SettingsView.qml   # Settings view
│       ├── FloatingBadge.qml  # Reusable GroupBox badge label
│       ├── Terminal.qml       # Reusable monospace log component
│       └── icons/             # SVG icons for buttons and actions
├── assets/              # Bundled resources
│   └── icon.png         # Application icon
└── infra/               # Infrastructure adapters
    ├── file_scanner.py   # Directory walking (os.walk), glob filtering, exclude support
    ├── executor.py       # Parallel file hashing (ThreadPoolExecutor)
    ├── hash_io.py        # Single-file hash I/O helper
    ├── logging.py        # Logging setup
    └── settings_store.py # QSettings persistence
```

**Boundaries:**
- `core/` has zero I/O — receives file content as streams or paths, returns domain objects
- `cli/` and `gui/` are thin adapters that wire `core/` + `infra/`
- `infra/` handles filesystem and concurrency concerns

---

## CLI Command Summary

```
hash-turbo hash <paths...>          Generate hashes
    -a, --algorithm <algo>         Algorithm (default: sha256)
    -r, --recursive                Recurse into directories
    -g, --glob <pattern>           Filter files by glob
    --exclude <pattern>            Exclude files matching pattern
    -o, --output <file>            Write hash file
    --format {gnu,bsd,json}        Output format (default: gnu)
    --path-mode {relative,absolute} Path style in output (default: relative)
    --base-dir <dir>               Base for relative paths (default: hash file dir)
    -j, --jobs <n>                 Parallel workers (default: CPU count)
    -v, --verbose                  Verbose output
    -q, --quiet                    Quiet output

hash-turbo verify <hashfile>        Verify files against hash file
    --expect <hash>                Verify single file against inline hash
    --strict                       Fail on missing files
    --flexible-whitespace          Accept irregular whitespace (default: on)
    --binary-only                  Always hash in binary mode (default: on)
    -a, --algorithm <algo>         Algorithm for --expect mode
    -q, --quiet                    Only show failures
    -v, --verbose                  Verbose output

hash-turbo sanitize <hashfile>       Sanitize / transform a hash file
    --format {gnu,bsd}             Output format (default: auto-detect)
    --separator {keep,posix,windows} Path separator style (default: keep)
    --strip-prefix <path>          Remove leading path prefix
    --hash-case {keep,lower,upper} Hex digest casing (default: keep)
    --sort {none,path,hash,filesystem} Sort entries (default: none)
    --deduplicate                  Remove duplicate entries by path
    --line-ending {system,lf,crlf,cr} Line ending style (default: system)
    --normalize-whitespace         Fix irregular whitespace (default: on)
    -o, --output <file>            Write result to file (default: stdout)

hash-turbo algorithms               List available hash algorithms

hash-turbo gui                      Launch the QML GUI
hash-turbo                          Launch the GUI (default when no subcommand given)

hash-turbo --version                Show version
hash-turbo --help                   Show help
```

---

## Decisions

| Decision | Choice |
|----------|--------|
| Package name | `hash-turbo` (import: `hash_turbo`) |
| CLI framework | `click` |
| Dependency management | pip with `pyproject.toml` |
| Distribution | PyInstaller — CLI as onefile binary, GUI as onedir `.app` bundle packaged in a DMG |
| GUI PyInstaller mode | **onedir** — Qt/PySide6 libraries live permanently inside `hash-turbo.app/Contents/Frameworks/`, avoiding per-launch extraction and giving near-instant startup |
| Hash file extension | Configurable, defaults to `.<algorithm>` |
| JSON output | Yes — `--format json` (CLI only) |

