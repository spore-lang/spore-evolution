#!/usr/bin/env -S uv run

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from sep_common import ROOT, SepDocument, headings, load_documents

SCHEMA_PATH = ROOT / "schemas" / "sep-frontmatter.schema.json"

REQUIRED_SECTIONS = {
    "Standards Track": [
        "Summary",
        "Motivation",
        "Guide-level explanation",
        "Reference-level explanation",
        "Human experience impact",
        "Agent experience impact",
        "Structured representation / protocol impact",
        "Diagnostics impact",
        "Drawbacks",
        "Alternatives considered",
        "Prior art",
        "Backward compatibility and migration",
        "Unresolved questions",
    ],
    "Process": [
        "Summary",
        "Motivation",
        "Goals",
        "Non-goals",
        "Proposal",
        "Lifecycle and transition rules",
        "Roles and responsibilities",
        "Drawbacks",
        "Alternatives considered",
        "Migration or rollout impact",
        "Unresolved questions",
    ],
    "Informational": [
        "Summary",
        "Motivation",
        "Discussion",
        "Prior art or references",
        "Implications for Spore",
        "Unresolved questions or future directions",
    ],
}

ALLOWED_STATUSES = {"Draft", "Accepted", "Rejected", "Withdrawn", "Superseded"}
ALLOWED_TRANSITIONS = {
    "Draft": {"Draft", "Accepted", "Rejected", "Withdrawn"},
    "Accepted": {"Accepted", "Superseded"},
    "Rejected": {"Rejected"},
    "Withdrawn": {"Withdrawn"},
    "Superseded": {"Superseded"},
}


def validate_front_matter_schema(documents: list[SepDocument], errors: list[str]) -> None:
    if not documents:
        return

    if shutil.which("uvx") is None:
        errors.append("`uvx` is required to run check-jsonschema")
        return

    with TemporaryDirectory(prefix="sep-frontmatter-") as temp_dir:
        for document in documents:
            temp_path = Path(temp_dir) / document.relative_path.with_suffix(".yaml")
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(document.raw_front_matter, encoding="utf-8")

            result = subprocess.run(
                [
                    "uvx",
                    "--from",
                    "check-jsonschema",
                    "check-jsonschema",
                    "--schemafile",
                    str(SCHEMA_PATH),
                    str(temp_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                continue

            message = (result.stdout + result.stderr).strip()
            errors.append(
                f"{document.relative_path}: front matter schema validation failed"
                + (f"\n{message}" if message else "")
            )


def validate_filename_and_title(path: Path, meta: dict[str, object], errors: list[str]) -> None:
    if path.parent.name == "drafts":
        if meta["sep"] is not None:
            errors.append(f"{path}: drafts must use `sep: null`")
        if meta["status"] != "Draft":
            errors.append(f"{path}: drafts must use `status: Draft`")
        if not path.name.endswith(".md"):
            errors.append(f"{path}: draft file must be Markdown")
        return

    if path.parent.name != "seps":
        return

    if not re.fullmatch(r"SEP-\d{4}-.+\.md", path.name):
        errors.append(f"{path}: numbered SEPs must match `SEP-XXXX-short-name.md`")
        return

    if not isinstance(meta["sep"], int):
        errors.append(f"{path}: numbered SEPs must use an integer `sep`")
        return

    expected_prefix = f"SEP-{meta['sep']:04d}:"
    if not str(meta["title"]).startswith(expected_prefix):
        errors.append(f"{path}: title must start with `{expected_prefix}`")

    expected_filename_prefix = f"SEP-{meta['sep']:04d}-"
    if not path.name.startswith(expected_filename_prefix):
        errors.append(f"{path}: filename prefix must match SEP number")


def validate_sections(path: Path, meta: dict[str, object], body: str, errors: list[str]) -> None:
    required = REQUIRED_SECTIONS.get(str(meta["type"]), [])
    found = headings(body)
    missing = [section for section in required if section not in found]
    if missing:
        errors.append(f"{path}: missing required sections: {', '.join(missing)}")


def validate_cross_field_rules(path: Path, meta: dict[str, object], errors: list[str]) -> None:
    status = str(meta["status"])
    if status not in ALLOWED_STATUSES:
        errors.append(f"{path}: invalid status `{status}`")

    if status == "Superseded" and meta["superseded_by"] is None:
        errors.append(f"{path}: `Superseded` documents must set `superseded_by`")

    if status != "Superseded" and meta["superseded_by"] is not None:
        errors.append(f"{path}: only `Superseded` documents may set `superseded_by`")

    if path.name != "SEP-0000-process.md" and meta["discussion"] is None:
        errors.append(f"{path}: `discussion` must not be null outside SEP-0000")


def extract_status_from_git(ref: str, relative_path: Path) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{relative_path.as_posix()}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    try:
        from sep_common import extract_front_matter, parse_front_matter

        raw_front_matter, _ = extract_front_matter(result.stdout, relative_path)
        meta = parse_front_matter(raw_front_matter, relative_path)
    except ValueError:
        return None

    status = meta.get("status")
    return status if isinstance(status, str) else None


def resolve_base_ref() -> str | None:
    github_base_ref = os.environ.get("GITHUB_BASE_REF")
    if github_base_ref:
        return f"origin/{github_base_ref}"

    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return "HEAD^"

    return None


def validate_status_transition(path: Path, meta: dict, base_ref: str | None, errors: list[str]) -> None:
    if base_ref is None:
        return

    previous_status = extract_status_from_git(base_ref, path.relative_to(ROOT))
    if previous_status is None:
        return

    current_status = meta["status"]
    allowed = ALLOWED_TRANSITIONS.get(previous_status, set())
    if current_status not in allowed:
        errors.append(
            f"{path}: invalid status transition `{previous_status}` -> `{current_status}`"
        )


def main() -> int:
    documents, errors = load_documents()
    seen_numbers: dict[int, Path] = {}
    base_ref = resolve_base_ref()

    validate_front_matter_schema(documents, errors)

    for document in documents:
        validate_filename_and_title(document.path, document.metadata, errors)
        validate_sections(document.path, document.metadata, document.body, errors)
        validate_cross_field_rules(document.path, document.metadata, errors)
        validate_status_transition(document.path, document.metadata, base_ref, errors)

        sep_number = document.metadata.get("sep")
        if isinstance(sep_number, int):
            other = seen_numbers.get(sep_number)
            if other is not None:
                errors.append(
                    f"{document.path}: duplicate SEP number {sep_number:04d} (already used by {other})"
                )
            else:
                seen_numbers[sep_number] = document.path

    if errors:
        print("SEP validation failed:\n", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(documents)} SEP documents successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
