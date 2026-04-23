---
description: "Use when editing documentation files — reminds to update screenshots when describing GUI features"
applyTo: "docs/**"
---
# Documentation Guidelines

When adding or modifying documentation that describes GUI features or views:

- Check whether `docs/screenshots/` contains up-to-date screenshots for the described view
- If a QML view has changed since the last screenshot, regenerate it using `@screenshot-docs` or `/update-docs-images`
- Reference screenshots in docs using relative paths: `![Hash View](screenshots/hash-view.png)`
- Available screenshots: `hash-view.png`, `verify-view.png`, `sanitize-view.png`, `settings-view.png`
