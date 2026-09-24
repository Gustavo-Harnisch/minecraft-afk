#!/usr/bin/env python3
"""Build Linux release archives and SHA-256 checksums from a Git commit."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent.parent


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, env={**os.environ, "TZ": "UTC"}
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="Committed revision to package (default: HEAD)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    arguments = parser.parse_args()

    if git("status", "--porcelain"):
        parser.error("Commit or set aside pending changes before building a release.")

    commit = git("rev-parse", "--verify", "--end-of-options", f"{arguments.ref}^{{commit}}")
    package_info = git("show", f"{commit}:minecraft_afk/__init__.py")
    match = re.search(r'^__version__ = "(\d+\.\d+\.\d+)"$', package_info, re.MULTILINE)
    if match is None:
        parser.error("The selected revision must declare a numeric major.minor.patch version.")
    version = match.group(1)
    output = arguments.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    prefix = f"minecraft-afk-{version}/"
    checksums = []

    for archive_format in ("tar.gz", "zip"):
        archive = output / f"minecraft-afk-{version}-linux.{archive_format}"
        git("archive", f"--format={archive_format}", f"--prefix={prefix}",
            f"--output={archive}", commit)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksums.append(f"{digest}  {archive.name}\n")
        print(archive)

    manifest = output / "SHA256SUMS"
    manifest.write_text("".join(checksums), encoding="utf-8")
    print(manifest)
    print(f"Packaged version {version} from commit {commit}")


if __name__ == "__main__":
    main()
