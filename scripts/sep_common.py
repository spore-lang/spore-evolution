from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "seps-index.json"
INDEX_VERSION = 1
INDEX_FIELDS = (
    "sep",
    "title",
    "status",
    "type",
    "authors",
    "created",
    "requires",
    "discussion",
    "pr",
    "superseded_by",
)


@dataclass(frozen=True)
class SepDocument:
    path: Path
    relative_path: Path
    raw_front_matter: str
    metadata: dict[str, object]
    body: str


def extract_front_matter(text: str, path: Path) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML front matter")

    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError(f"{path}: unterminated YAML front matter")

    return parts[0][4:], parts[1]


def parse_scalar(raw_value: str) -> object:
    if raw_value == "null":
        return None

    if raw_value == "[]":
        return []

    if raw_value.startswith("[") and raw_value.endswith("]"):
        inner = raw_value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]

    if re.fullmatch(r"-?\d+", raw_value):
        return int(raw_value)

    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {'"', "'"}:
        return raw_value[1:-1]

    return raw_value


def parse_front_matter(raw_front_matter: str, path: Path) -> dict[str, object]:
    metadata: dict[str, object] = {}
    lines = raw_front_matter.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if line.startswith("  - "):
            raise ValueError(f"{path}: unexpected list item without a key")

        key, separator, rest = line.partition(":")
        if not separator:
            raise ValueError(f"{path}: invalid front matter line `{line}`")

        key = key.strip()
        value = rest.lstrip()

        if not key:
            raise ValueError(f"{path}: empty front matter key")

        if value:
            metadata[key] = parse_scalar(value)
            index += 1
            continue

        items: list[object] = []
        index += 1
        while index < len(lines) and lines[index].startswith("  - "):
            items.append(parse_scalar(lines[index][4:].strip()))
            index += 1
        metadata[key] = items

    return metadata


def headings(body: str) -> set[str]:
    found: set[str] = set()
    for line in body.splitlines():
        if line.startswith("## "):
            found.add(line[3:].strip())
    return found


def discover_markdown_files() -> list[Path]:
    return sorted(
        path
        for directory in (ROOT / "drafts", ROOT / "seps")
        for path in directory.rglob("*.md")
        if path.name != "README.md"
    )


def load_documents() -> tuple[list[SepDocument], list[str]]:
    documents: list[SepDocument] = []
    errors: list[str] = []

    for path in discover_markdown_files():
        text = path.read_text(encoding="utf-8")
        try:
            raw_front_matter, body = extract_front_matter(text, path)
            metadata = parse_front_matter(raw_front_matter, path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        documents.append(
            SepDocument(
                path=path,
                relative_path=path.relative_to(ROOT),
                raw_front_matter=raw_front_matter,
                metadata=metadata,
                body=body,
            )
        )

    return documents, errors


def document_sort_key(document: SepDocument) -> tuple[int, int, str]:
    sep = document.metadata.get("sep")
    if isinstance(sep, int):
        return (0, sep, document.relative_path.as_posix())
    return (1, 0, document.relative_path.as_posix())


def build_sep_index(documents: list[SepDocument]) -> dict[str, object]:
    entries: list[dict[str, object]] = []

    for document in sorted(documents, key=document_sort_key):
        entry: dict[str, object] = {"path": document.relative_path.as_posix()}
        for field in INDEX_FIELDS:
            entry[field] = document.metadata.get(field)
        entries.append(entry)

    return {
        "version": INDEX_VERSION,
        "documents": entries,
    }
