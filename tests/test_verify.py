import json
from hashlib import sha256
from pathlib import Path

from systmonline_fhir.verify import verify_manifest


def test_verifies_capture_set_and_detects_tampering(tmp_path: Path):
    page = tmp_path / "page.html"
    page.write_text("<html>synthetic</html>", encoding="utf-8")
    digest = sha256(page.read_bytes()).hexdigest()
    manifest = tmp_path / "capture-set-manifest.json"
    manifest.write_text(
        json.dumps({"views": {"patient_record": [{"filename": page.name, "sha256": digest}]}}),
        encoding="utf-8",
    )

    valid = verify_manifest(manifest)
    assert valid.valid
    assert valid.verified_pages == 1

    page.write_text("<html>changed</html>", encoding="utf-8")
    invalid = verify_manifest(manifest)
    assert not invalid.valid
    assert invalid.errors == ("page 1: checksum mismatch",)
