---
description: "Scaffold a new Python module with test file, following src/ layout and hexagonal conventions"
agent: "senior-python-engineer"
argument-hint: "Module name and purpose, e.g. 'user_repository — persists user aggregates'"
---
Scaffold a new module in the `src/` package and a matching test file in `tests/`.

## Inputs

- **Module name**: first word of the argument (snake_case)
- **Purpose**: remaining description after the name

## What to generate

1. `src/<package>/<module_name>.py` — module with:
   - Module-level docstring from purpose
   - Type-hinted classes or functions appropriate to the purpose
   - Domain vs infrastructure separation (if applicable)
   - `__all__` export list

2. `tests/test_<module_name>.py` — test file with:
   - At least 2 test functions using `test_<unit>_<scenario>_<expected>` naming
   - Arrange-Act-Assert structure
   - Pytest fixtures where appropriate

3. Update `src/<package>/__init__.py` if it exists — add public imports

## Constraints

- Python 3.11+, type hints everywhere
- Use dataclasses for value objects / DTOs
- Use Protocol for abstractions at boundaries
- Keep the module focused on a single concept
- Do NOT add unnecessary dependencies
