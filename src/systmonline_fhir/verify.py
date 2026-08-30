from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class VerificationResult:
    manifest: str
    declared_pages: int
    verified_pages: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors and self.declared_pages == self.verified_pages


def _page_declarations(manifest: dict) -> list[dict]:
    if isinstance(manifest.get("pages"), list):
        return list(manifest["pages"])
    views = manifest.get("views", {})
    if isinstance(views, dict):
        return [page for pages in views.values() if isinstance(pages, list) for page in pages]
    return []


def verify_manifest(path: Path) -> VerificationResult:
    root = path.parent.resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    pages = _page_declarations(manifest)
    errors: list[str] = []
    verified = 0
    for index, declaration in enumerate(pages, start=1):
        filename = declaration.get("filename")
        expected = declaration.get("sha256")
        if not isinstance(filename, str) or not isinstance(expected, str):
            errors.append(f"page {index}: missing filename or sha256")
            continue
        candidate = (root / filename).resolve()
        if candidate.parent != root:
            errors.append(f"page {index}: filename escapes the capture directory")
            continue
        if not candidate.is_file():
            errors.append(f"page {index}: file is missing")
            continue
        actual = sha256(candidate.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"page {index}: checksum mismatch")
            continue
        verified += 1
    return VerificationResult(path.name, len(pages), verified, tuple(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a private capture manifest and its pages")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    result = verify_manifest(args.manifest)
    print(json.dumps({**asdict(result), "valid": result.valid}, indent=2))
    raise SystemExit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
