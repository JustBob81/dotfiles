#!/usr/bin/env python3
"""Verify a dpkg-sig v4 signature using its documented member-hash format.

The format is documented in the dpkg-sig manual:
https://manpages.debian.org/unstable/dpkg-sig/dpkg-sig.1.en.html
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run(argv: list[str]) -> bytes:
    result = subprocess.run(argv, check=True, stdout=subprocess.PIPE)
    return result.stdout


def fail(message: str) -> None:
    raise ValueError(message)


def verify(deb: Path, gnupg_home: Path, expected_fingerprint: str) -> str:
    members = run(["ar", "t", str(deb)]).decode("utf-8").splitlines()
    signature_members = [name for name in members if re.fullmatch(r"_gpg[a-z]+[A-Z0-9]?", name)]
    if "_gpgbuilder" not in signature_members:
        fail("DEB does not contain the required _gpgbuilder signature")

    signature = run(["ar", "p", str(deb), "_gpgbuilder"])
    if b"BEGIN PGP SIGNED MESSAGE" not in signature:
        fail("_gpgbuilder is not a dpkg-sig v4 cleartext signature")

    with tempfile.TemporaryDirectory(prefix="verify-dpkg-sig-") as temp_dir:
        cleartext = Path(temp_dir) / "manifest"
        result = subprocess.run(
            ["gpg", "--openpgp", "--batch", "--no-tty", "--status-fd", "1",
             "--homedir", str(gnupg_home), "--output", str(cleartext), "--decrypt"],
            input=signature,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        status = result.stdout.decode("utf-8", errors="replace")
        valid = [
            line.split()[2:]
            for line in status.splitlines()
            if line.startswith("[GNUPG:] VALIDSIG ")
        ]
        if result.returncode != 0 or not valid or not cleartext.is_file():
            fail("GnuPG did not validate the Zoom DEB signature")

        fingerprints = set()
        for fields in valid:
            if fields:
                fingerprints.add(fields[0].upper())
                if len(fields) >= 10:
                    fingerprints.add(fields[9].upper())
        if expected_fingerprint.upper() not in fingerprints:
            fail("DEB signature is valid but was not made by the reviewed Zoom key")
        manifest = cleartext.read_text(encoding="utf-8")

    fields: dict[str, str] = {}
    files: list[tuple[str, str, int, str]] = []
    in_files = False
    for line in manifest.splitlines():
        if in_files:
            if not line[:1].isspace():
                break
            parts = line.split()
            if len(parts) != 4:
                fail("Malformed file entry in signed dpkg-sig manifest")
            md5, sha1, size, name = parts
            files.append((md5.lower(), sha1.lower(), int(size), name))
        elif line.startswith("Files:"):
            in_files = True
        elif ":" in line:
            key, value = line.split(":", 1)
            fields[key.lower()] = value.strip()

    if fields.get("version") != "4" or fields.get("role") != "builder":
        fail("Signed manifest is not a supported dpkg-sig v4 builder signature")
    if not files:
        fail("Signed dpkg-sig manifest contains no package member hashes")

    actual_members = set(members)
    signed_members: set[str] = set()
    for expected_md5, expected_sha1, expected_size, name in files:
        if name not in actual_members or name.startswith("_gpg"):
            fail(f"Signed package member is missing or invalid: {name}")
        content = run(["ar", "p", str(deb), name])
        if (
            len(content) != expected_size
            or hashlib.sha1(content).hexdigest() != expected_sha1
            or hashlib.md5(content).hexdigest() != expected_md5
        ):
            fail(f"Package member does not match signed digests: {name}")
        signed_members.add(name)

    if "debian-binary" not in signed_members:
        fail("Signed manifest does not cover debian-binary")
    if not any(name.startswith("control.tar") for name in signed_members):
        fail("Signed manifest does not cover the control archive")
    if not any(name.startswith("data.tar") for name in signed_members):
        fail("Signed manifest does not cover the package payload")

    return f"GOODSIG _gpgbuilder {expected_fingerprint.upper()}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deb", type=Path)
    parser.add_argument("gnupg_home", type=Path)
    parser.add_argument("fingerprint")
    args = parser.parse_args()
    try:
        print(verify(args.deb, args.gnupg_home, args.fingerprint))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Signature verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
