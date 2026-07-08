"""Validate document extraction against a manually checked answer key.

Manifest format:
{
  "documents": [
    {
      "name": "company-a",
      "path": "sample_data/real/company-a.pdf",
      "expected": "sample_data/real/company-a.expected.json"
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.extraction_service import ExtractionService


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            flattened.update(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
        return flattened
    if isinstance(value, list):
        flattened = {}
        for index, child in enumerate(value):
            flattened.update(_flatten(child, f"{prefix}[{index}]"))
        return flattened
    return {prefix: value}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_document(path: Path, expected_path: Path) -> tuple[int, int, list[str]]:
    actual = ExtractionService().extract_company_data(path.name, path.read_bytes())
    actual_flat = _flatten(actual.model_dump(mode="json"))
    expected_flat = _flatten(_load_json(expected_path))

    mismatches: list[str] = []
    for key, expected_value in expected_flat.items():
        actual_value = actual_flat.get(key)
        if actual_value != expected_value:
            mismatches.append(f"{key}: expected {expected_value!r}, got {actual_value!r}")
    return len(expected_flat) - len(mismatches), len(expected_flat), mismatches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    manifest = _load_json(args.manifest)
    total_passed = 0
    total_fields = 0
    failures: list[str] = []

    for document in manifest["documents"]:
        path = Path(document["path"])
        expected_path = Path(document["expected"])
        passed, fields, mismatches = validate_document(path, expected_path)
        total_passed += passed
        total_fields += fields
        print(f"{document['name']}: {passed}/{fields} fields matched")
        failures.extend(f"{document['name']} {mismatch}" for mismatch in mismatches)

    accuracy = (total_passed / total_fields * 100) if total_fields else 0
    print(f"\nExtraction field accuracy: {accuracy:.2f}% ({total_passed}/{total_fields})")
    if failures:
        print("\nMismatches:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
