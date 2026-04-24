"""Pre-commit hook: run mypy + pytest on staged .py files.

Cross-platform — invoked from .github/hooks/pre-commit-check.json.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=d"],
        capture_output=True,
        text=True,
    )
    staged = [f for f in result.stdout.splitlines() if f.endswith(".py")]
    if not staged:
        return

    print("Running mypy...")
    subprocess.run([sys.executable, "-m", "mypy", "--strict", *staged], check=False)

    print("Running pytest...")
    subprocess.run([sys.executable, "-m", "pytest", "-x", "--tb=short", "-q"], check=False)


if __name__ == "__main__":
    main()
