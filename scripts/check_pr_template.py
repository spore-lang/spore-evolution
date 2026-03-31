#!/usr/bin/env -S uv run

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REQUIRED_CHECKBOXES = [
    "- [x] I linked the canonical discussion thread.",
    "- [x] I used the correct SEP template for this proposal type.",
    "- [x] I updated front matter metadata and required sections.",
]


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH is not set; skipping PR template validation.")
        return 0

    payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pull_request = payload.get("pull_request")
    if not pull_request:
        print("No pull_request payload found; skipping PR template validation.")
        return 0

    body = pull_request.get("body") or ""
    missing = [item for item in REQUIRED_CHECKBOXES if item not in body]

    if missing:
        print("Pull request body is missing required checked items:\n", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Pull request template checklist looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
