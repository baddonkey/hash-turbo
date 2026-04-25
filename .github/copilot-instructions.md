# Copilot Instructions — hash-turbo

## Project Overview

Cross-platform file hash management tool with CLI and PySide6 QML GUI. Generates, stores, verifies, and sanitizes file hashes with support for many algorithms. See [docs/SPEC.md](docs/SPEC.md) for the full specification.

## Tech Stack

- Python 3.11+
- PySide6 + QML (Qt Quick / Material style GUI)
- Type hints everywhere, mypy-strict compatible
- Dependency management: pip with `pyproject.toml`
- Testing: pytest
- Distribution: standalone binary via PyInstaller

## Project Structure

```
src/hash_turbo/
├── core/           # Domain logic — zero I/O, pure functions and types
│   ├── hasher.py    # Hash computation (streaming)
│   ├── hash_file.py # Parse/write hash files (GNU/BSD format)
│   ├── verifier.py  # Compare computed vs expected hashes
│   ├── sanitizer.py # Hash file transformation (format, paths, dedup)
│   └── models.py    # Domain types: HashResult, HashEntry, Algorithm
├── cli/            # CLI adapter (click)
├── gui/            # PySide6 QML adapter
│   ├── qml/         # QML UI files (Material style)
│   └── *_model.py   # Python view models exposed to QML
├── i18n/           # Internationalization (gettext, .po/.mo)
└── infra/          # Infrastructure (file scanning, parallelism)
tests/              # Mirrors src/ structure
```

## Build & Run

```bash
pip install -e .              # Install in dev mode
hash-turbo hash <files...>    # CLI — generate hashes
hash-turbo verify <hashfile>  # CLI — verify hashes
hash-turbo gui                # Launch GUI
```

## Testing
Activate the venv and run pytest from the project root:

```bash
pytest              # Run all tests
pytest -x           # Stop on first failure
pytest --tb=short   # Shorter tracebacks
```

## Conventions

- Follow the standards defined in the `senior-python-engineer` agent for design, testing, and code style.
- Use `src/` layout with a top-level package.
- Separate domain logic from infrastructure (ports & adapters / hexagonal style).
- Keep modules small and focused — one concept per module.
- Name tests descriptively: `test_<unit>_<scenario>_<expected>`.

## Release & Publishing Rules

- **Never upload, publish, or push release assets autonomously.** Building the MSI/DMG is fine when asked, but uploading to GitHub releases or any remote requires explicit user instruction.
- After a build completes, stop and let the user decide what to do with the artifact.

## Agent Reference

| Agent | Purpose |
|-------|---------|
| [senior-python-engineer](.github/agents/senior-python-engineer.md) | Default coding agent — senior IC style, opinionated on design, testing, and Python standards |
| [code-reviewer](.github/agents/code-reviewer.agent.md) | Read-only code review — SOLID, tests, types, coupling |
| [screenshot-docs](.github/agents/screenshot-docs.agent.md) | Writes and runs PySide6 scripts to capture GUI screenshots to `docs/screenshots/` |
| [video-tutorial](.github/agents/video-tutorial.agent.md) | Re-records per-language demo MP4s (hash-verify, sanitize, settings) with synced narration |

## Customizations

| Type | Name | Purpose |
|------|------|---------|
| Prompt | `/scaffold-module` | Generate a new module + test file following project conventions |
| Prompt | `/update-docs-images` | Regenerate GUI documentation screenshots via `@screenshot-docs` |
| Prompt | `/regenerate-demo-videos` | Re-record all 15 per-language tutorial MP4s via `@video-tutorial` |
| Instruction | `testing-conventions` | Auto-applied to `tests/**` — naming, AAA structure, fixture patterns |
| Instruction | `docs-screenshots` | Auto-applied to `docs/**` — reminds to update screenshots when documenting GUI |
| Hook | `pre-commit-check` | Runs mypy --strict + pytest after tool use on staged `.py` files |
| Hook | `screenshot-reminder` | Nudges to regenerate screenshots when QML files are edited |
