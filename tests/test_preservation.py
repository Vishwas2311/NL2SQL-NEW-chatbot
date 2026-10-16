"""Guard the fixed UI against accidental edits during backend-only development."""

import hashlib
import json
from pathlib import Path


def test_original_ui_reference_hashes():
    root = Path("NL2SQL_V4_2_EXISTING_UI_BACKEND_ONLY_FULL_DOCUMENTATION")
    manifest = next(root.glob("*/existing_ui_reference/ASSET_SHA256.json"))
    recorded = json.loads(manifest.read_text())
    for filename, evidence in recorded.items():
        payload = (manifest.parent / filename).read_bytes()
        assert len(payload) == evidence["bytes"]
        assert hashlib.sha256(payload).hexdigest() == evidence["sha256"]
