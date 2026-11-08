#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2026 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#
"""Finalize signed Windows release artifacts.

Takes the signed bundle returned by SignPath, extracts the file tree from the
signed MSI via `msiexec /a`, repacks it as the portable .zip with 7-Zip, and
emits SHA256 manifests over the final release artifacts.

Run after the SignPath signing job completes and `dvr-scan-signed.zip` has
been downloaded.

Expected input (in --staging-dir, default `dist/signed/`):
    dvr-scan-signed.zip                  - SignPath bundle (signed .exes + .msi)

Outputs (written to the same directory):
    dvr-scan-X.Y-win64.zip               - portable .zip rebuilt from the signed MSI
    dvr-scan-X.Y-win64.msi               - signed MSI extracted from the bundle
    dvr-scan-X.Y-win64.manifest.json     - structured per-file SHA256 manifest
    SHA256SUMS                           - flat sha256sum -c compatible output

Usage:
    python scripts/finalize_windows_dist.py [--staging-dir DIR] [--allow-unsigned]
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_release  # noqa: E402
from common import (  # noqa: E402
    CLI_EXE,
    EXE_NAMES,
    SIGNED_BUNDLE,
    SIGNED_DIR,
    display_version,
    find_7zip,
    hash_zip_contents,
    manifest_name,
    msi_name,
    read_version,
    sha256_file,
    verify_authenticode,
    zip_name,
)

VERSION = display_version(read_version())


def extract_signed_bundle(signed_zip: Path, dest: Path, allow_unsigned: bool) -> Path:
    """Extract the SignPath bundle, verify every signed binary, return the MSI path."""
    print(f"Extracting {signed_zip.name}...")
    with zipfile.ZipFile(signed_zip) as zf:
        zf.extractall(dest)
    for exe_name in EXE_NAMES:
        exe = next((p for p in dest.rglob(exe_name)), None)
        if exe is None:
            sys.exit(f"{exe_name} not found inside {signed_zip}")
        print(f"  signed exe: {exe.name} ({exe.stat().st_size:,} bytes)")
        verify_authenticode(exe, allow_unsigned=allow_unsigned)
    # appveyor.yml produces DVR-Scan-*.msi; match case-insensitively.
    msis = [p for p in dest.rglob("*") if p.is_file() and p.suffix.lower() == ".msi"]
    if not msis:
        sys.exit(f"No .msi found inside {signed_zip}")
    if len(msis) > 1:
        sys.exit(f"Multiple .msi files found inside {signed_zip}: {[p.name for p in msis]}")
    msi = msis[0]
    print(f"  signed msi: {msi.name} ({msi.stat().st_size:,} bytes)")
    verify_authenticode(msi, allow_unsigned=allow_unsigned)
    return msi


def extract_msi_tree(msi_path: Path, dest: Path) -> Path:
    """Run `msiexec /a` to extract the .msi's installed file tree without
    actually installing. Returns the directory containing dvr-scan.exe
    (the app root), which sits under TARGETDIR at the .aip's APPDIR depth."""
    if sys.platform != "win32":
        sys.exit("msiexec /a is Windows-only")
    print(f"Extracting {msi_path.name} via msiexec /a...")
    # /a = administrative install: file extraction only, no registry, no admin rights.
    # /qn = silent. TARGETDIR must be absolute.
    result = subprocess.run(
        ["msiexec", "/a", str(msi_path), "/qn", f"TARGETDIR={dest}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(
            f"msiexec /a failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    exe = next((p for p in dest.rglob(CLI_EXE)), None)
    if exe is None:
        sys.exit(f"{CLI_EXE} not found anywhere under {dest} after msiexec /a")
    tree = exe.parent
    # `msiexec /a` writes an "administrative" copy of the .msi (and sometimes a
    # `Cabs/` folder) into TARGETDIR alongside the extracted app files. When
    # APPDIR == TARGETDIR (no nested install folder), these land inside the app
    # tree and would pollute the portable .zip. Strip them.
    for stray in tree.glob("*.msi"):
        print(f"  stripping admin-install artifact: {stray.name}")
        stray.unlink()
    cabs_dir = tree / "Cabs"
    if cabs_dir.is_dir():
        print("  stripping admin-install artifact: Cabs/")
        shutil.rmtree(cabs_dir)
    print(f"  app tree: {tree.relative_to(dest)}/ ({sum(1 for _ in tree.rglob('*')):,} entries)")
    return tree


def build_portable_zip(tree: Path, zip_path: Path, sevenz: Path) -> None:
    """Pack `tree`'s top-level contents into a Deflate .zip."""
    if zip_path.exists():
        zip_path.unlink()
    print(f"Building {zip_path.name} (zip / Deflate / mx=9 / mt=on)...")
    # -mm=Deflate (not LZMA): Windows Explorer's built-in "Extract All" only
    # supports Deflate-compressed zips; LZMA needs 7-Zip/WinRAR. Portable .zip
    # ships to end users on clean Windows, so compat trumps ratio here.
    # -mfb=258 -mpass=15: max-out Deflate tuning (slow, but once per release).
    # -mmt=on: 7z parallelizes Deflate across files (not within a file), so
    # the docs/ tree gets a real speedup; the big binaries (dvr-scan.exe,
    # dvr-scan-app.exe, ffmpeg.exe) still each compress on a single thread.
    # Pass top-level entries (not '*') so we don't depend on shell globbing.
    entries = sorted(p.name for p in tree.iterdir())
    subprocess.run(
        [
            str(sevenz),
            "a",
            "-tzip",
            "-mm=Deflate",
            "-mx=9",
            "-mfb=258",
            "-mpass=15",
            "-mmt=on",
            str(zip_path),
            *entries,
        ],
        cwd=tree,
        check=True,
        capture_output=True,
    )
    print(f"  {zip_path.stat().st_size / (1024 * 1024):.1f} MB")


def write_manifests(staging: Path, portable_zip: Path, msi: Path) -> None:
    print(f"Hashing {portable_zip.name}...")
    portable_digest = sha256_file(portable_zip)
    print(f"Hashing {msi.name}...")
    msi_digest = sha256_file(msi)

    manifest = {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bundles": {
            "msi": {
                "path": msi.name,
                "size": msi.stat().st_size,
                "sha256": msi_digest,
            },
            "portable_zip": {
                "path": portable_zip.name,
                "size": portable_zip.stat().st_size,
                "sha256": portable_digest,
                "contents": hash_zip_contents(portable_zip),
            },
        },
    }

    manifest_path = staging / manifest_name(VERSION)
    sums_path = staging / "SHA256SUMS"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    sums_path.write_text(
        f"{msi_digest}  {msi.name}\n{portable_digest}  {portable_zip.name}\n",
        encoding="utf-8",
    )
    print(f"Wrote {manifest_path.name}")
    print(f"Wrote {sums_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=SIGNED_DIR,
        help=f"Directory holding {SIGNED_BUNDLE} (default: dist/signed/).",
    )
    parser.add_argument(
        "--allow-unsigned",
        action="store_true",
        help=(
            "Downgrade Authenticode failures to warnings. For local dry runs against "
            "an unsigned build ONLY; never use for a real release."
        ),
    )
    args = parser.parse_args()

    if args.allow_unsigned:
        print("=" * 72)
        print("WARNING: --allow-unsigned is set. Authenticode failures are NOT fatal.")
        print("WARNING: The resulting artifacts must NOT be published as a release.")
        print("=" * 72)

    staging = args.staging_dir.resolve()
    if not staging.is_dir():
        sys.exit(f"{staging} not found")

    signed_bundle = staging / SIGNED_BUNDLE
    if not signed_bundle.is_file():
        sys.exit(f"{signed_bundle} not found")

    sevenz = find_7zip()
    print(f"Using 7-Zip: {sevenz}")
    print(f"Staging dir: {staging}")
    print(f"Version:     {VERSION}")

    portable_zip = staging / zip_name(VERSION)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # The signed .exes are verified for the wrong-bundle check but otherwise
        # unused (the .msi already ships its own signed copies of both).
        signed_msi = extract_signed_bundle(
            signed_bundle, tmp_path / "bundle", allow_unsigned=args.allow_unsigned
        )
        # Copy under the canonical lowercase name (appveyor.yml emits DVR-Scan-*.msi).
        msi_dest = staging / msi_name(VERSION)
        # Unlink first: on a case-insensitive filesystem, copying over a leftover
        # DVR-Scan-*.msi from an earlier run would keep the old (uppercase) name.
        msi_dest.unlink(missing_ok=True)
        shutil.copy2(signed_msi, msi_dest)
        print(f"Copied signed MSI {signed_msi.name} -> {msi_dest.name}")
        msi_tree = extract_msi_tree(msi_dest, tmp_path / "msi-extract")
        build_portable_zip(msi_tree, portable_zip, sevenz)
        write_manifests(staging, portable_zip, msi_dest)

    print()
    print("Validating finalized artifacts...")
    validate_release.run_all_checks(staging, allow_unsigned=args.allow_unsigned)

    if args.allow_unsigned:
        print()
        print("WARNING: --allow-unsigned was set; these artifacts are NOT releasable.")


if __name__ == "__main__":
    main()
