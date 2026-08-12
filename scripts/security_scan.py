#!/usr/bin/env python3
"""Fail on common secret material or private file types before publication."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".next",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "data",
    "node_modules",
}
BLOCKED_SUFFIXES = {".key", ".p12", ".pem"}
BLOCKED_FILENAMES = {".env", ".env.local", "id_rsa", "id_ed25519"}

# Pattern fragments are joined so this scanner does not match its own source.
CONTENT_PATTERNS = {
    "private key": re.compile("BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "OpenAI-style secret": re.compile(r"\bsk-" + r"[A-Za-z0-9_-]{20,}\b"),
    "GitHub-style token": re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA" + r"[A-Z0-9]{16}\b"),
}


def iter_publication_files():
    # Scan exactly what Git could publish: tracked files plus untracked files
    # that are not ignored. Local `.env` files stay private, while newly
    # authored source files are still checked before they are staged.
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for relative_bytes in result.stdout.split(b"\0"):
        if not relative_bytes:
            continue
        relative = Path(relative_bytes.decode("utf-8"))
        path = ROOT / relative
        if not path.is_file() or any(
            part in EXCLUDED_PARTS for part in relative.parts
        ):
            continue
        yield path


def main() -> int:
    findings: list[str] = []
    checked = 0
    for path in iter_publication_files():
        checked += 1
        relative = path.relative_to(ROOT)
        if path.name in BLOCKED_FILENAMES or path.suffix in BLOCKED_SUFFIXES:
            findings.append(f"{relative}: blocked private file type")
            continue
        try:
            content = path.read_text("utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in CONTENT_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{relative}: possible {label}")

    if findings:
        print("Publication security scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(f"Publication security scan passed ({checked} files checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
