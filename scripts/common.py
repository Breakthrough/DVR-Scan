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
"""Shared helpers for the Windows release scripts (update_installer.py,
finalize_windows_dist.py, validate_release.py).

Naming conventions enforced here (see RELEASE-PLAN.md):

- The MSI ProductVersion is `dvr_scan.__version__` with any Python-style suffix
  stripped ("2.0" -> "2.0", "2.1-dev0" -> "2.1"). It is NOT padded to three
  components; DVR-Scan 1.8 and 1.8.2 shipped as "1.8" / "1.8.2" and the
  Apps & Features key is "DVR-Scan <ProductVersion>".
- Release artifacts are lowercase: dvr-scan-X.Y-win64.msi / .zip, matching the
  links in docs/download.md.
"""

import ast
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_DIR / "dvr_scan" / "__init__.py"
INSTALLER_AIP = REPO_DIR / "dist" / "installer" / "DVR-Scan.aip"
DIST_TREE = REPO_DIR / "dist" / "dvr-scan"
SIGNED_DIR = REPO_DIR / "dist" / "signed"

SIGNED_BUNDLE = "dvr-scan-signed.zip"
CLI_EXE = "dvr-scan.exe"
APP_EXE = "dvr-scan-app.exe"
EXE_NAMES = (CLI_EXE, APP_EXE)

CHUNK = 1 << 20  # 1 MiB


def read_version() -> str:
    """Return `dvr_scan.__version__` by parsing dvr_scan/__init__.py.

    Importing dvr_scan pulls in cv2 and the rest of the runtime, which the
    release scripts should not depend on (they may run in a bare environment).
    """
    tree = ast.parse(VERSION_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "__version__" for target in node.targets
        ):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    sys.exit(f"Could not find __version__ in {VERSION_FILE}")


def display_version(raw: str) -> str:
    """Strip Python-style suffixes while keeping the component count.

    "2.0" -> "2.0", "2.0.1" -> "2.0.1", "2.1-dev0" -> "2.1", "2.1.dev0" -> "2.1".
    Used for the MSI ProductVersion and for every artifact filename so the
    installer, portable zip, PyPI package and git tag all line up.
    """
    parts = []
    for part in raw.split("."):
        digits = re.split(r"[^\d]", part, maxsplit=1)[0]
        if not digits:
            break
        parts.append(digits)
        if digits != part:
            # A suffix ends the numeric version ("2.1-dev0" -> stop after "2.1").
            break
    if not parts:
        sys.exit(f"Cannot derive a numeric version from {raw!r}")
    return ".".join(parts[:4])


def msi_name(version: str) -> str:
    return f"dvr-scan-{version}-win64.msi"


def zip_name(version: str) -> str:
    return f"dvr-scan-{version}-win64.zip"


def manifest_name(version: str) -> str:
    return f"dvr-scan-{version}-win64.manifest.json"


def find_7zip() -> Path:
    for candidate in (
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
    ):
        if candidate.exists():
            return candidate
    on_path = shutil.which("7z") or shutil.which("7z.exe")
    if on_path:
        return Path(on_path)
    sys.exit("7-Zip not found. Install from https://www.7-zip.org/.")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def hash_zip_contents(zip_path: Path) -> list[dict]:
    entries = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            h = hashlib.sha256()
            with zf.open(info) as f:
                for block in iter(lambda: f.read(CHUNK), b""):
                    h.update(block)
            entries.append(
                {
                    "path": info.filename,
                    "size": info.file_size,
                    "sha256": h.hexdigest(),
                }
            )
    return entries


def verify_authenticode(path: Path, allow_unsigned: bool = False) -> None:
    """Bail unless `path` carries a Valid Authenticode signature.

    Catches the wrong-artifact case: e.g. someone drops the AppVeyor
    pre-signing bundle into dist/signed/ instead of the SignPath output.
    PowerShell's Get-AuthenticodeSignature works on both .exe and .msi.

    With `allow_unsigned` (local dry runs against an unsigned build only) a
    non-Valid status is reported as a warning instead of a failure.
    """
    if sys.platform != "win32":
        print(f"  (skipping Authenticode check for {path.name} on non-Windows)")
        return
    ps_cmd = (
        f"$sig = Get-AuthenticodeSignature -FilePath '{path}'; "
        "Write-Output $sig.Status; "
        "if ($sig.SignerCertificate) { Write-Output $sig.SignerCertificate.Subject }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines:
        sys.exit(
            f"Authenticode check for {path.name} failed to run.\n  stderr: {result.stderr.strip()}"
        )
    status = lines[0]
    subject = lines[1] if len(lines) > 1 else "<no certificate>"
    print(f"  Authenticode: {status} ({subject})")
    if status != "Valid":
        if allow_unsigned:
            print(f"  WARNING: {path.name} is not signed (status={status!r}); --allow-unsigned set")
            return
        sys.exit(
            f"Authenticode check FAILED for {path.name}: status={status!r}. "
            f"Verify {SIGNED_BUNDLE} is the SignPath output, not an unsigned AppVeyor artifact."
        )
