#!/usr/bin/env python3
"""Verify release assets and reconstruct the original ZIP archives (stdlib only)."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

CHUNK_SIZE = 8 * 1024 * 1024


def checked_record(record):
    """Reject paths and malformed integrity metadata before opening any files."""
    name = record.get("name")
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or any(c in name for c in "/\\:\x00")
        or Path(name).name != name
    ):
        raise ValueError(f"Unsafe filename in manifest: {name!r}")
    if type(record.get("size")) is not int or record["size"] < 0:
        raise ValueError(f"Invalid size for {name}")
    if not isinstance(record.get("sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", record["sha256"]
    ):
        raise ValueError(f"Invalid SHA256 for {name}")
    return record


def load_manifest(path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema_version")
    archives = manifest.get("archives")
    if not isinstance(archives, list) or not archives:
        raise ValueError("Manifest must contain a nonempty archives list")
    archive_names = set()
    part_names = set()
    for archive in archives:
        checked_record(archive)
        if archive["name"] in archive_names:
            raise ValueError(f"Duplicate archive: {archive['name']}")
        archive_names.add(archive["name"])
        parts = archive.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ValueError(f"Missing parts for {archive['name']}")
        for part in parts:
            checked_record(part)
            if part["name"] in part_names:
                raise ValueError(f"Duplicate part: {part['name']}")
            part_names.add(part["name"])
        if sum(part["size"] for part in parts) != archive["size"]:
            raise ValueError(f"Part sizes do not sum to {archive['name']} size")
    for archive in archives:
        for part in archive["parts"]:
            if part["name"] in archive_names:
                if not (
                    len(archive["parts"]) == 1
                    and all(part[k] == archive[k] for k in ("name", "size", "sha256"))
                ):
                    raise ValueError(f"Part conflicts with an archive: {part['name']}")
    return archives


def stream_verified(directory, record, output=None, combined_hash=None):
    path = directory / record["name"]
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing regular file (symlinks are not accepted): {path}")
    if path.stat().st_size != record["size"]:
        raise ValueError(f"Size mismatch: {path.name}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while block := source.read(CHUNK_SIZE):
            size += len(block)
            digest.update(block)
            if output is not None:
                output.write(block)
            if combined_hash is not None:
                combined_hash.update(block)
    if size != record["size"] or digest.hexdigest() != record["sha256"]:
        raise ValueError(f"SHA256 or size mismatch: {path.name}")
    return size


def restore(directory, archives):
    for archive in archives:
        destination = directory / archive["name"]
        if destination.exists() or destination.is_symlink():
            try:
                stream_verified(directory, archive)
            except ValueError as exc:
                raise ValueError(f"Refusing to overwrite existing {destination}: {exc}") from exc
            print(f"Verified existing archive: {archive['name']}")
            continue
        parts = archive["parts"]
        if len(parts) == 1 and parts[0]["name"] == archive["name"]:
            raise ValueError(f"Missing downloaded archive: {destination}")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=directory, prefix=f".{archive['name']}.", suffix=".tmp", delete=False
            ) as output:
                temporary = Path(output.name)
                combined_hash = hashlib.sha256()
                size = 0
                for part in parts:
                    print(f"Verifying and joining: {part['name']}", flush=True)
                    size += stream_verified(directory, part, output, combined_hash)
            if size != archive["size"] or combined_hash.hexdigest() != archive["sha256"]:
                raise ValueError(f"Reconstructed archive checksum mismatch: {archive['name']}")
            # Publishing by hard link is atomic and refuses to overwrite a file that
            # appeared while we were working. The temporary is on the same filesystem.
            os.link(temporary, destination)
            print(f"Restored and verified: {archive['name']}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print("All original ZIPs verified. Extract all three into the same directory.")
    print("Downloaded parts were retained; remove them after extraction if desired.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path.cwd(), help="Directory containing downloaded assets")
    parser.add_argument("--manifest", type=Path, help="Manifest path (default: DIRECTORY/release-manifest.json)")
    args = parser.parse_args()
    directory = args.directory.resolve()
    try:
        archives = load_manifest(args.manifest or directory / "release-manifest.json")
        restore(directory, archives)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
