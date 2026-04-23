---
description: "Regenerate all GUI documentation, and screenshots or specific views"
agent: "screenshot-docs"
argument-hint: "Which views to capture (e.g. 'all', 'hash', 'verify dark theme')"
---
Capture documentation screenshots of the hash-turbo GUI.

## Default Task

Regenerate **all four views** (Hash, Verify, Sanitize, Settings) as PNG images in `docs/screenshots/`.
AFter capturing, update `README.md` and `user-manual.md` screenshot references if any new files were added. Create out of the user-manuial.md a PDF.

## Customization

The user may specify:
- **Specific views**: Only capture the named view(s)
- **Theme**: Capture in `dark`, `light`, or both themes
- **State**: Populate sample data (e.g. hash results, verification mismatches)

If no arguments are given, capture all views in the default (system) theme with empty/default state.