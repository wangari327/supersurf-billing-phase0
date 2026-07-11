from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "staticfiles",
    "__pycache__",
}
SKIP_SUFFIXES = {
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".sqlite3",
}
ALLOWED_VALUES = {
    "",
    "dev-only-change-me",
    "dev-only-insecure-supersurf-key",
    "production-check-only-secret-key-with-length",
}
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\\b([A-Z0-9_]*(SECRET|TOKEN|PASSWORD|PRIVATE_KEY|CONSUMER_KEY|CONSUMER_SECRET)[A-Z0-9_]*)\\s*[:=]\\s*['\\\"]?([^'\\\"\\s#]+)"
)


def should_scan(path: Path) -> bool:
    relative_parts = set(path.relative_to(ROOT).parts)
    if relative_parts & SKIP_DIRS:
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    return path.is_file()


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = SECRET_ASSIGNMENT.search(line)
            if not match:
                continue
            value = match.group(3).strip()
            if value in ALLOWED_VALUES or value.startswith("$") or value.startswith("${"):
                continue
            if value.lower() in {"true", "false", "none", "null"}:
                continue
            findings.append(f"{path.relative_to(ROOT)}:{line_number}: possible secret assignment")

    if findings:
        print("\\n".join(findings))
        return 1
    print("No obvious committed secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

