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
"""Update the Advanced Installer .aip project for a release.

Usage:
    python scripts/update_installer.py                    # version bump only
    python scripts/update_installer.py --sync-files       # bump + re-sync APPDIR
    python scripts/update_installer.py --sync-only        # re-sync APPDIR only (CI)
    python scripts/update_installer.py --sync-only --dev  # CI dev build (renames MSI)
    python scripts/update_installer.py --version 2.0.1    # explicit version override
    python scripts/update_installer.py --aip tmp/DVR-Scan.aip  # edit a copy of the .aip

The MSI ProductVersion is the display version (e.g. "2.0", "2.0.1") with no
padding to three components; see common.py for the conventions.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DIST_TREE,
    INSTALLER_AIP,
    display_version,
    msi_name,
    read_version,
)


def find_advinst() -> Path:
    if env := os.environ.get("ADVINST"):
        path = Path(env)
        if not path.exists():
            sys.exit(f"ADVINST={env} does not exist.")
        return path
    candidates = sorted(
        Path(r"C:\Program Files (x86)\Caphyon").glob(
            "Advanced Installer*/bin/x86/AdvancedInstaller.com"
        )
    )
    if not candidates:
        sys.exit(
            r"AdvancedInstaller.com not found under C:\Program Files (x86)\Caphyon. "
            "Set the ADVINST environment variable to its full path."
        )
    return candidates[-1]


def run(advinst: Path, aip: Path, *edit_args: str, check: bool = True) -> int:
    cmd = [str(advinst), "/edit", str(aip), *edit_args]
    print(">", " ".join(cmd))
    return subprocess.run(cmd, check=check).returncode


def resync_appdir(advinst: Path, aip: Path) -> None:
    if not DIST_TREE.exists():
        sys.exit(f"{DIST_TREE} not found. Run `pyinstaller dist/dvr-scan.spec` first.")
    # /ResetSync errors out if APPDIR isn't already a synced folder
    # (true on the first run); /NewSync will fail if it IS synced. So
    # try the reset but tolerate failure, then sync.
    run(advinst, aip, "/ResetSync", "APPDIR", check=False)
    run(advinst, aip, "/NewSync", "APPDIR", str(DIST_TREE))


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--sync-files",
        action="store_true",
        help="Bump version/GUIDs AND re-sync APPDIR from dist/dvr-scan/.",
    )
    mode.add_argument(
        "--sync-only",
        action="store_true",
        help="Re-sync APPDIR only; leave version/GUID fields untouched (CI use).",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help=(
            "Rename the MSI to dvr-scan-{ver}-dev-win64.msi so dev-build artifacts "
            "are distinguishable from release artifacts. Only valid with --sync-only."
        ),
    )
    parser.add_argument(
        "--version",
        dest="version_override",
        help="Version override (default: derived from dvr_scan.__version__).",
    )
    parser.add_argument(
        "--aip",
        type=Path,
        default=INSTALLER_AIP,
        help="Path to the .aip project to edit (default: dist/installer/DVR-Scan.aip).",
    )
    args = parser.parse_args()

    if args.dev and not args.sync_only:
        sys.exit("--dev is only valid in combination with --sync-only.")

    aip = args.aip.resolve()
    if not aip.is_file():
        sys.exit(f"{aip} not found.")

    advinst = find_advinst()
    print(f"Using {advinst}")

    raw_version = args.version_override or read_version()
    version = display_version(raw_version)

    if args.sync_only:
        print(f"Re-syncing APPDIR in {aip.name}")
        resync_appdir(advinst, aip)
        if args.dev:
            dev_name = f"dvr-scan-{version}-dev-win64.msi"
            print(f"Renaming MSI package to {dev_name} (dev build)")
            run(advinst, aip, "/SetPackageName", dev_name, "-buildname", "DefaultBuild")
        return

    if version != raw_version:
        print(f"Normalized {raw_version!r} -> {version!r} for Advanced Installer")
    print(f"Bumping {aip.name} to {version}")

    run(advinst, aip, "/SetVersion", version)
    run(advinst, aip, "/SetProductCode", "-langid", "1033")
    run(advinst, aip, "/SetPackageName", msi_name(version), "-buildname", "DefaultBuild")

    if args.sync_files:
        resync_appdir(advinst, aip)


if __name__ == "__main__":
    main()
