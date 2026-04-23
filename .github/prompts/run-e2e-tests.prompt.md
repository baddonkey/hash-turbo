---
description: "Run GUI end-to-end tests with visible windows, optionally including stress tests"
argument-hint: "Options: 'stress' to include stress tests, 'hash/verify/sanitize/qml' to pick suites"
---
Run the GUI end-to-end tests in **visible mode** so each window renders on screen.

## Default Task

Run all (normal, stress) GUI E2E including QML test files with `--visual`:

```
pytest tests/gui/test_qml_e2e.py tests/gui/test_verify_view.py tests/gui/test_hash_view.py tests/gui/test_sanitize_view.py --visual -v
```

## Stress Tests

When the user says **stress** (or no arguments are given), also include `--stress`:

```
pytest tests/gui/test_qml_e2e.py tests/gui/test_verify_view.py tests/gui/test_hash_view.py tests/gui/test_sanitize_view.py --visual --stress -v
```

## Customization

The user may narrow the scope:
- **hash** → `tests/gui/test_hash_view.py`
- **verify** → `tests/gui/test_verify_view.py`
- **sanitize** → `tests/gui/test_sanitize_view.py`
- **qml** → `tests/gui/test_qml_e2e.py`

Combine freely, e.g. "hash verify stress".

## After Running

Report the pass / fail / skip counts and highlight any failures.
