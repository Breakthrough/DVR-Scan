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
"""Validate finalized Windows release artifacts.

Runs against the staging directory produced by `scripts/finalize_windows_dist.py`
(default `dist/signed/`) and verifies the artifacts that go up to a GitHub
release. Catches regressions that only manifest in the post-build artifact, not
in unit tests:

    1. Filename presence (lowercase dvr-scan-X.Y-win64.*), no stray artifacts
    2. SHA256 of `.zip` and `.msi` matches `SHA256SUMS` and `manifest.json`,
       and per-file hashes inside the portable .zip match the manifest
    3. Authenticode signatures on the `.msi` and on `dvr-scan.exe` and
       `dvr-scan-app.exe` inside the portable `.zip`
    4. MSI / portable-zip parity: every file in the portable .zip exists in
       the MSI (matched by SHA256, name-agnostic to tolerate MSI mangling)
    5. Frozen `.exe` smoke tests (Windows only), run with ffmpeg scrubbed from
       PATH so the bundled ffmpeg.exe must be found next to dvr-scan.exe:
       - `dvr-scan.exe --version` reports the expected version, no required
         package is "Not Installed", and PyAV / tkinter / ffmpeg are available
       - `dvr-scan-app.exe --version` succeeds
       - A short scan-only run and a short ENCODE run on a test video succeed
         (skipped if the test video resource is absent)
       - The error path produces a clean error, not a Python traceback

Re-run standalone after fixing any failure:
    python scripts/validate_release.py [--staging-dir DIR] [--allow-unsigned]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    APP_EXE,
    CLI_EXE,
    EXE_NAMES,
    REPO_DIR,
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

# Mirrors the package list printed by `dvr-scan --version` (dvr_scan/platform.py).
# Keep in sync: any package added there should be classified here as REQUIRED (must
# report a version in the frozen .exe) or OPTIONAL (may legitimately be absent).
REQUIRED_PACKAGES = (
    "av",
    "cv2",
    "dvr_scan",
    "numpy",
    "platformdirs",
    "PIL",
    "scenedetect",
    "tqdm",
)
# moviepy is not bundled. screeninfo IS bundled but has no __version__ attribute,
# so `--version` always prints "Not Installed" for it; it cannot be asserted on.
OPTIONAL_PACKAGES = ("moviepy", "screeninfo")
# Entries that must appear in the Features section. "ffmpeg" only appears when the
# ffmpeg binary was found, which (with PATH scrubbed) proves the bundled copy works.
REQUIRED_FEATURES = ("PyAV", "tkinter", "ffmpeg")

NOT_INSTALLED = "Not Installed"
TEST_VIDEO = REPO_DIR / "tests" / "resources" / "simple_movement.mp4"
SMOKE_ARGS = ("-et", "5s", "-df", "3")
SMOKE_TIMEOUT = 300


def fail(message: str) -> None:
    """Print FAIL marker and bubble out as a SystemExit so finalize stops."""
    sys.exit(f"VALIDATION FAILED: {message}")


def section(name: str) -> None:
    print()
    print(f"[{name}]")


def parse_version_output(text: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """Parse `dvr-scan --version` output.

    Returns (header version, packages, features). The header version is the token
    after "DVR-Scan" on the first non-empty line. The Packages and Features sections
    each start at their title line, skip the following `---` separator, and end at
    the next blank line. Each entry is "<name><padding><value>"; the value may
    contain spaces (e.g. "Not Installed"). Missing sections yield empty dicts.
    """
    lines = [line.rstrip() for line in text.splitlines()]
    header = ""
    for line in lines:
        if line.strip():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "DVR-Scan":
                header = parts[1]
            break

    def parse_section(title: str) -> dict[str, str]:
        entries: dict[str, str] = {}
        try:
            start = next(i for i, line in enumerate(lines) if line.strip() == title)
        except StopIteration:
            return entries
        for line in lines[start + 1 :]:
            stripped = line.strip()
            if stripped.startswith("---"):
                continue
            if not stripped:
                break
            parts = stripped.split(None, 1)
            if len(parts) != 2:
                continue
            entries[parts[0]] = parts[1].strip()
        return entries

    return header, parse_section("Packages"), parse_section("Features")


def check_filenames(staging: Path) -> tuple[Path, Path, Path]:
    """Step 1: required artifacts present, no stray inconsistent names."""
    section("Filenames")
    portable_zip = staging / zip_name(VERSION)
    msi = staging / msi_name(VERSION)
    manifest = staging / manifest_name(VERSION)
    sums = staging / "SHA256SUMS"

    for required in (portable_zip, msi, manifest, sums):
        if not required.is_file():
            fail(f"missing required artifact: {required.name}")
        print(f"  found {required.name}")

    stray_suffixed = list(staging.glob("dvr-scan-*-portable.zip"))
    if stray_suffixed:
        fail("found stale '-portable' artifacts: " + ", ".join(p.name for p in stray_suffixed))
    for zip_path in staging.glob("dvr-scan-*.zip"):
        # Allow the canonical name, the SignPath input bundle, and any .unsigned.zip backup.
        if zip_path.name in (portable_zip.name, SIGNED_BUNDLE) or zip_path.name.endswith(
            ".unsigned.zip"
        ):
            continue
        fail(
            f"unexpected .zip artifact: {zip_path.name} "
            f"(only {portable_zip.name} expected besides the signed bundle)"
        )
    for msi_path in staging.glob("*.msi"):
        # Exact (case-sensitive) name match: a leftover DVR-Scan-*.msi is a stray.
        if msi_path.name == msi.name:
            continue
        fail(f"unexpected stray MSI: {msi_path.name} (only {msi.name} expected)")

    return portable_zip, msi, manifest


def check_hashes(staging: Path, portable_zip: Path, msi: Path, manifest_path: Path) -> dict:
    """Step 2: SHA256 of .zip / .msi matches SHA256SUMS and manifest.json,
    and per-file hashes inside the portable .zip match the manifest."""
    section("Hashes")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("version") != VERSION:
        fail(f"manifest version {manifest.get('version')!r} != expected {VERSION!r}")

    portable_actual = sha256_file(portable_zip)
    msi_actual = sha256_file(msi)
    print(f"  {portable_zip.name}: {portable_actual}")
    print(f"  {msi.name}: {msi_actual}")

    if manifest["bundles"]["portable_zip"]["sha256"] != portable_actual:
        fail(f"manifest portable_zip sha256 mismatch ({portable_zip.name})")
    if manifest["bundles"]["msi"]["sha256"] != msi_actual:
        fail(f"manifest msi sha256 mismatch ({msi.name})")

    sums_text = (staging / "SHA256SUMS").read_text(encoding="utf-8")
    expected_lines = {
        f"{msi_actual}  {msi.name}",
        f"{portable_actual}  {portable_zip.name}",
    }
    actual_lines = {line.strip() for line in sums_text.splitlines() if line.strip()}
    if expected_lines != actual_lines:
        fail(
            "SHA256SUMS does not match recomputed digests.\n"
            f"  expected: {sorted(expected_lines)}\n"
            f"  actual:   {sorted(actual_lines)}"
        )
    print("  SHA256SUMS matches")

    print(f"  re-hashing {portable_zip.name} contents...")
    actual_contents = hash_zip_contents(portable_zip)
    expected_contents = manifest["bundles"]["portable_zip"]["contents"]
    actual_by_path = {entry["path"]: entry for entry in actual_contents}
    expected_by_path = {entry["path"]: entry for entry in expected_contents}
    if actual_by_path.keys() != expected_by_path.keys():
        only_actual = sorted(actual_by_path.keys() - expected_by_path.keys())
        only_manifest = sorted(expected_by_path.keys() - actual_by_path.keys())
        fail(
            "manifest contents file list does not match portable .zip:\n"
            f"  only in zip:      {only_actual}\n"
            f"  only in manifest: {only_manifest}"
        )
    for path, expected in expected_by_path.items():
        actual = actual_by_path[path]
        if actual["sha256"] != expected["sha256"] or actual["size"] != expected["size"]:
            fail(f"manifest content mismatch for {path}: {expected} vs {actual}")
    print(f"  manifest matches all {len(actual_by_path)} entries inside portable .zip")
    return manifest


def check_signatures(portable_zip: Path, msi: Path, allow_unsigned: bool = False) -> None:
    """Step 3: Authenticode on .msi and on both .exes inside the portable .zip."""
    section("Signatures")
    print(f"  verifying {msi.name}")
    verify_authenticode(msi, allow_unsigned=allow_unsigned)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(portable_zip) as zf:
            for exe_name in EXE_NAMES:
                try:
                    zf.extract(exe_name, tmp_path)
                except KeyError:
                    fail(f"{exe_name} not found at root of {portable_zip.name}")
        for exe_name in EXE_NAMES:
            print(f"  verifying {exe_name} inside {portable_zip.name}")
            verify_authenticode(tmp_path / exe_name, allow_unsigned=allow_unsigned)


def _hashes_in_dir(root: Path) -> set[str]:
    return {sha256_file(p) for p in root.rglob("*") if p.is_file()}


def check_msi_zip_parity(portable_zip: Path, msi: Path, sevenz: Path) -> None:
    """Step 4: every file in the portable .zip should exist (by content)
    inside the MSI. We compare SHA256 sets to be name-agnostic - 7-Zip's MSI
    extraction can mangle filenames, so name-by-name diffs are unreliable, but
    content hashes are exact."""
    section("MSI / portable-zip parity")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        msi_dir = tmp_path / "msi"
        zip_dir = tmp_path / "zip"
        msi_dir.mkdir()
        zip_dir.mkdir()

        # Extract MSI (which may produce inner .cab archives that themselves need
        # extracting to recover the actual installed file tree).
        print(f"  extracting {msi.name} with 7-Zip...")
        subprocess.run(
            [str(sevenz), "x", str(msi), f"-o{msi_dir}", "-y"],
            check=True,
            capture_output=True,
        )
        cabs = list(msi_dir.rglob("*.cab"))
        for cab in cabs:
            print(f"    expanding inner archive: {cab.name}")
            subprocess.run(
                [str(sevenz), "x", str(cab), f"-o{cab.parent}", "-y"],
                check=True,
                capture_output=True,
            )
            cab.unlink()

        print(f"  extracting {portable_zip.name}...")
        with zipfile.ZipFile(portable_zip) as zf:
            zf.extractall(zip_dir)

        msi_hashes = _hashes_in_dir(msi_dir)
        zip_hashes = _hashes_in_dir(zip_dir)
        missing_from_msi = zip_hashes - msi_hashes
        if missing_from_msi:
            # Re-walk the portable zip to attach names to the missing hashes.
            zip_by_hash = {}
            for p in zip_dir.rglob("*"):
                if p.is_file():
                    zip_by_hash.setdefault(sha256_file(p), p.relative_to(zip_dir).as_posix())
            named = sorted(zip_by_hash.get(h, h) for h in missing_from_msi)
            fail(
                f"{len(missing_from_msi)} file(s) present in portable .zip but not in MSI:\n"
                + "\n".join(f"    {n}" for n in named[:25])
                + (f"\n    ... ({len(named) - 25} more)" if len(named) > 25 else "")
            )
        print(
            f"  all {len(zip_hashes)} files in portable .zip are present in MSI "
            f"({len(msi_hashes)} files in MSI total)"
        )


def _env_without_ffmpeg() -> dict[str, str]:
    """Copy of os.environ with every PATH entry that could supply ffmpeg removed.

    The frozen build ships ffmpeg.exe next to dvr-scan.exe; it must be found via
    the Windows application-directory lookup, not via PATH."""
    env = dict(os.environ)
    path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
    kept = []
    for entry in env.get(path_key, "").split(os.pathsep):
        if not entry:
            continue
        if "ffmpeg" in entry.lower() or Path(entry, "ffmpeg.exe").is_file():
            print(f"  scrubbed from PATH: {entry}")
            continue
        kept.append(entry)
    env[path_key] = os.pathsep.join(kept)
    return env


def _run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=cwd,
            env=env,
            timeout=SMOKE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        fail(f"timed out after {SMOKE_TIMEOUT}s: {' '.join(cmd)}")
        raise  # unreachable; keeps type checkers happy


def _output(result: subprocess.CompletedProcess) -> str:
    return f"  stdout: {result.stdout.strip()[:2000]}\n  stderr: {result.stderr.strip()[:2000]}"


BUNDLED_CONFIG = "dvr-scan.cfg"
STARTUP_MODE_LINE = re.compile(r"^\s*startup-mode\s*=\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)


def check_bundled_config(portable_zip: Path) -> None:
    """Step 5: the bundled config template (installed to the user config folder by the MSI
    and shipped at the root of the portable .zip) must contain an active
    `startup-mode = wizard` line so fresh installs start in the Scan Wizard. The code
    default is `advanced`, so a template without the line would silently change what
    new users see."""
    section("Bundled config template")
    with zipfile.ZipFile(portable_zip) as zf:
        names = set(zf.namelist())
        if BUNDLED_CONFIG not in names:
            fail(f"{BUNDLED_CONFIG} not found at root of {portable_zip.name}")
        text = zf.read(BUNDLED_CONFIG).decode("utf-8-sig")
    modes = [m.group(1).lower() for m in STARTUP_MODE_LINE.finditer(text)]
    if modes != ["wizard"]:
        fail(
            f"{BUNDLED_CONFIG} must have exactly one active `startup-mode = wizard` line, "
            f"found: {modes or 'none'}"
        )
    print(f"  {BUNDLED_CONFIG}: startup-mode = wizard")


def check_frozen_exe(portable_zip: Path) -> None:
    """Step 6: extract portable .zip, run both .exes, verify version, package and
    feature detection, smoke scans, and clean error path."""
    section("Frozen .exe smoke tests")
    if sys.platform != "win32":
        print("  (skipping .exe smoke tests on non-Windows)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        app_dir = tmp_path / "app"
        work_dir = tmp_path / "work"
        app_dir.mkdir()
        work_dir.mkdir()
        with zipfile.ZipFile(portable_zip) as zf:
            zf.extractall(app_dir)
        exe = app_dir / CLI_EXE
        app_exe = app_dir / APP_EXE
        for path in (exe, app_exe):
            if not path.is_file():
                fail(f"{path.name} not found at root of {portable_zip.name}")
        env = _env_without_ffmpeg()
        # An explicit -c skips the lookup of the machine's own user config file
        # (%LOCALAPPDATA%\DVR-Scan\dvr-scan.cfg), which could otherwise change the
        # output mode or other defaults the smoke runs rely on.
        empty_cfg = work_dir / "empty.cfg"
        empty_cfg.write_text("# empty config: isolates release validation from user settings\n")
        cfg_args = ("-c", str(empty_cfg))

        # 5a. `dvr-scan.exe --version`: version, packages, features. The version
        # action prints via argparse's parser.exit(), i.e. to stderr, so parse both.
        result = _run([str(exe), "--version"], work_dir, env)
        if result.returncode != 0:
            fail(f"`{CLI_EXE} --version` exited {result.returncode}\n{_output(result)}")
        header, packages, features = parse_version_output(result.stdout + result.stderr)
        if not header or display_version(header) != VERSION:
            fail(f"`{CLI_EXE} --version` header reports {header!r}, expected {VERSION!r}")
        print(f"  header: DVR-Scan {header}")
        reported = packages.get("dvr_scan", "")
        if not reported or display_version(reported) != VERSION:
            fail(f"`{CLI_EXE} --version` reports dvr_scan=={reported!r}, expected {VERSION!r}")
        missing = [
            name for name in REQUIRED_PACKAGES if packages.get(name, NOT_INSTALLED) == NOT_INSTALLED
        ]
        if missing:
            fail(
                "frozen .exe reports required packages as missing / 'Not Installed':\n    "
                + ", ".join(missing)
            )
        for name in REQUIRED_PACKAGES:
            print(f"  {name}=={packages[name]}")
        for name in OPTIONAL_PACKAGES:
            print(f"  {name}=={packages.get(name, NOT_INSTALLED)} (optional)")
        missing_features = [name for name in REQUIRED_FEATURES if name not in features]
        if missing_features:
            hint = (
                " (ffmpeg missing: the bundled ffmpeg.exe was not found next to "
                f"{CLI_EXE} with ffmpeg scrubbed from PATH)"
                if "ffmpeg" in missing_features
                else ""
            )
            fail(f"`{CLI_EXE} --version` is missing features: {missing_features}{hint}")
        for name in REQUIRED_FEATURES:
            print(f"  feature {name}: {features[name]}")

        # 5b. `dvr-scan-app.exe --version`.
        result = _run([str(app_exe), "--version"], work_dir, env)
        if result.returncode != 0:
            fail(f"`{APP_EXE} --version` exited {result.returncode}\n{_output(result)}")
        app_output = result.stdout + result.stderr
        if VERSION not in app_output:
            fail(f"`{APP_EXE} --version` output does not contain {VERSION!r}\n{_output(result)}")
        print(f"  {APP_EXE} --version OK")

        # 5c/5d. Functional smoke runs on the test video, if available.
        if TEST_VIDEO.is_file():
            print(f"  running scan-only on {TEST_VIDEO.name}...")
            result = _run(
                [str(exe), *cfg_args, "-i", str(TEST_VIDEO), "-so", *SMOKE_ARGS], work_dir, env
            )
            if result.returncode != 0:
                fail(f"scan-only smoke run exited {result.returncode}\n{_output(result)}")
            print("  scan-only OK")

            out_dir = work_dir / "smoke_output"
            out_dir.mkdir()
            print(f"  running default (ENCODE) output mode on {TEST_VIDEO.name}...")
            result = _run(
                [str(exe), *cfg_args, "-i", str(TEST_VIDEO), *SMOKE_ARGS, "-d", str(out_dir)],
                work_dir,
                env,
            )
            if result.returncode != 0:
                fail(f"encode smoke run exited {result.returncode}\n{_output(result)}")
            clips = sorted(out_dir.glob("*.mp4"))
            if not clips:
                fail(
                    "encode smoke run produced no .mp4 files (bundled ffmpeg not used?)\n"
                    f"  output dir contents: {[p.name for p in out_dir.iterdir()]}\n"
                    + _output(result)
                )
            print(f"  encode OK ({len(clips)} clip(s))")
        else:
            print(
                f"  (skipping smoke scans; {TEST_VIDEO.relative_to(REPO_DIR)} not present locally)"
            )

        # 5e. Clean error path: a missing input must give a logged error and a
        # nonzero exit, not a Python traceback.
        nonexistent = work_dir / "definitely-not-a-video.mp4"
        result = _run([str(exe), *cfg_args, "-i", str(nonexistent), "-so"], work_dir, env)
        if result.returncode == 0:
            fail(f"error path: {CLI_EXE} exited 0 on a missing input file")
        if "Traceback" in result.stderr or "Traceback" in result.stdout:
            fail(
                f"error path: {CLI_EXE} surfaced a Python traceback to the user:\n"
                + _output(result)
            )
        print(f"  error path: clean exit {result.returncode} (no traceback)")


def run_all_checks(staging: Path, allow_unsigned: bool = False) -> None:
    """Entrypoint shared with `finalize_windows_dist.py`. Raises SystemExit on failure."""
    if not staging.is_dir():
        fail(f"staging directory not found: {staging}")
    print(f"Validating release artifacts in: {staging}")
    print(f"Expected version: {VERSION}")
    if allow_unsigned:
        print("WARNING: --allow-unsigned is set; unsigned binaries will NOT fail validation.")

    portable_zip, msi, manifest_path = check_filenames(staging)
    check_hashes(staging, portable_zip, msi, manifest_path)
    check_signatures(portable_zip, msi, allow_unsigned=allow_unsigned)
    sevenz = find_7zip()
    check_msi_zip_parity(portable_zip, msi, sevenz)
    check_bundled_config(portable_zip)
    check_frozen_exe(portable_zip)

    print()
    if allow_unsigned:
        print("All validation checks passed (WITH --allow-unsigned; NOT releasable).")
    else:
        print("All validation checks passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=SIGNED_DIR,
        help="Directory containing finalized artifacts (default: dist/signed/).",
    )
    parser.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="Downgrade Authenticode failures to warnings (local dry runs ONLY).",
    )
    args = parser.parse_args()
    run_all_checks(args.staging_dir.resolve(), allow_unsigned=args.allow_unsigned)


if __name__ == "__main__":
    main()
