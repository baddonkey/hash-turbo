"""Screenshot reminder hook: nudge when a QML file was changed.

Cross-platform — invoked from .github/hooks/screenshot-reminder.json.
"""

from __future__ import annotations

import json
import os
import re


def main() -> None:
    tool_result = os.environ.get("COPILOT_TOOL_RESULT", "")
    match = re.search(r"src/hash_turbo/gui/qml/[^ \"]+\.qml", tool_result)
    if match:
        print(json.dumps({
            "systemMessage": (
                "QML file changed \u2014 consider regenerating documentation "
                "screenshots with @screenshot-docs."
            ),
        }))


if __name__ == "__main__":
    main()
