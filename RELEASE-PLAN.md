# DVR-Scan Release Checklist

Copy this into the release PR and check off each item. Replace `X.Y` throughout with the version.

## 1. Pre-release

### Dependency Roll

Where applicable (mark as complete if nothing to update):

- [ ] `dist/requirements_windows.txt`
- [ ] `pyproject.toml`
- [ ] `uv lock --upgrade`.
- [ ] update ffmpeg pin (`ffmpeg_version`, GyanD/codexffmpeg release name) across all builders
- [ ] Python version
- [ ] Advanced Installer OSS license still valid (`appveyor.yml` resolves the installed
      Advanced Installer version dynamically, so no path to update)

### Changelog and docs

- [ ] `docs/changelog.md` is up to date and accurate
- [ ] `docs/download.md` is up to date and accurate
- [ ] Verify all docs are up to date: `README.md`, `docs/*.md`, the `dvr-scan.cfg` config file
      template, `dvr-scan --help` output, `CONTRIBUTING.md`, etc.

### Installer project (Windows releases)

- [ ] `python scripts/update_installer.py` bumps `dist/installer/DVR-Scan.aip` from
      `__version__`: `ProductVersion` -> `X.Y`, new `ProductCode` GUID, `PackageFileName` ->
      `dvr-scan-X.Y-win64`. Needs Advanced Installer installed locally (set `ADVINST` to the full
      path of `AdvancedInstaller.com` if it is not under `C:\Program Files (x86)\Caphyon`).
- [ ] If bundled files changed (new Python/PyAV/OpenCV DLLs), run
      `python scripts/update_installer.py --sync-files` after the local frozen build below to
      re-sync `APPDIR` against `dist/dvr-scan/`. CI re-syncs on every build (`--sync-only`), so
      this only keeps the committed `.aip` representative. Structural changes (dialogs, features,
      prerequisites, shortcuts, install directory layout) still need the Advanced Installer GUI.

### Local frozen build test

```bash
python dist/pre_release.py --release --use-local-images   # --release asserts the .aip ProductVersion matches __version__
pyinstaller dist/dvr-scan.spec
python dist/post_release.py
cp ffmpeg.exe dist/dvr-scan/          # the pinned GyanD full_build, not whatever is on PATH
git checkout -- dvr_scan/docs         # pre_release.py overwrites the docs, so we must restore it
```

- [ ] `dist/dvr-scan/_internal/av.libs/` exists with the PyAV FFmpeg DLLs.
- [ ] From a directory/environment with **no ffmpeg on PATH** (e.g. a temp dir, `where ffmpeg`
      is empty), the following must succeed and produce an mp4 with audio:
      `dvr-scan.exe --version`, `dvr-scan-app.exe --version`,
      `dvr-scan.exe -i <repo>/tests/resources/simple_movement.mp4 -et 5s -df 3`
      (`scripts/validate_release.py` repeats these checks against the final artifacts)
- [ ] `dvr-scan-app.exe` launches, wizard opens, and can perform a scan

## 2. Release commit

- [ ] `dvr_scan/__init__.py`: `__version__ = "X.Y"` (no `-dev` suffix).
- [ ] `docs/changelog.md`: heading `(In Development)` -> `(YYYY-MM-DD)`; the heading must be
      `### X.Y (YYYY-MM-DD)` (checked by `release-test.yml`).
- [ ] `README.md`: `### Latest Release: vX.Y (Month D, YYYY)`.
- [ ] `docs/download.md`: Python block and Windows blocks need updated version/date information
      and download links
- [ ] `docs/index.md` and `docs/index_docs.md`: `Latest Version: X.Y (Month D, YYYY)`
- [ ] `dist/installer/DVR-Scan.aip` if not already committed above
- [ ] Dates are the actual tag date, consistent across all five files
- [ ] `git status` shows nothing else (`dvr_scan/docs/` is clean)

```bash
git add README.md docs/changelog.md docs/download.md docs/index.md docs/index_docs.md \
        dvr_scan/__init__.py dist/installer/DVR-Scan.aip
git commit -m "[release] Release vX.Y"
```

## 3. Tag and branch

```bash
git tag vX.Y-release
git push origin main vX.Y-release
# either create a new release branch, or fast-forward the existing one
git branch -f releases/X.Y vX.Y-release
git push origin releases/X.Y
```

- [ ] Tag is on `main`; `releases/X.Y` points at the release commit.

## 4. CI artifacts and code signing

Pushing the tag triggers `Python Distribution`, `Windows Distribution`, `Release Tests`
(tag vs `__version__`, changelog heading, `twine check`, `pip-audit`), `Update Website`, and the
AppVeyor build (which re-syncs the `.aip` file list via `scripts/update_installer.py --sync-only`
before building the MSI and hands the result to SignPath).

- [ ] `gh run list --branch vX.Y-release` shows all GitHub workflows passing
- [ ] AppVeyor build passes
- [ ] SignPath: approve the signing request and download `dvr-scan-signed.zip` (signed
      `dvr-scan.exe`, `dvr-scan-app.exe` and MSI) into `dist/signed/`. No other inputs are
      needed: the portable zip is rebuilt from the signed MSI.
- [ ] `python scripts/finalize_windows_dist.py`: verifies the Authenticode signatures, copies the
      MSI as `dvr-scan-X.Y-win64.msi`, extracts its file tree with `msiexec /a` and repacks it as
      `dvr-scan-X.Y-win64.zip` with 7-Zip, writes `dvr-scan-X.Y-win64.manifest.json` +
      `SHA256SUMS`, then runs `scripts/validate_release.py` (filenames, hashes, signatures on the
      MSI and both EXEs inside the zip, MSI/zip parity, frozen-exe smoke tests with ffmpeg removed
      from `PATH`). Re-run the checks alone with `python scripts/validate_release.py`.
- [ ] Portable zip: extract, run `dvr-scan.exe --version` and one scan (also covered by validate).

Installing the MSI on a clean machine (shortcut, `dvr-scan --version` from a prompt, upgrade over
the previous version, clean uninstall) is automated by `test-installer.yml`, run in section 6.

## 5. GitHub release (draft)

- [ ] Zenodo: the GitHub switch for `Breakthrough/DVR-Scan` is ON **before** publishing, so the
      publish event mints a new DOI (the tag itself does not).
- [ ] Download the Python artifacts from the tag's Python Distribution:
      `gh run download <run-id> -n dvr-scan-dist -D release/`
      (should be four files: `dvr_scan-X.Y` and `dvr_scan_headless-X.Y`, `.whl` + `.tar.gz`).
- [ ] Copy the finalized Windows artifacts from `dist/signed/` into `release/`.
- [ ] Release notes: verbatim to the corresponding the `X.Y` changelog section, but with adjusted
      `####` headings promoted to `##` (`#### Release Notes` -> `## Release Notes`) since the
      existing headers are chosen for the website

```bash
gh release create vX.Y-release --draft --title "DVR-Scan vX.Y" --notes-file release-notes.md \
    release/dvr-scan-X.Y-win64.msi release/dvr-scan-X.Y-win64.zip \
    release/dvr-scan-X.Y-win64.manifest.json release/SHA256SUMS \
    release/dvr_scan-X.Y-py3-none-any.whl release/dvr_scan-X.Y.tar.gz \
    release/dvr_scan_headless-X.Y-py3-none-any.whl release/dvr_scan_headless-X.Y.tar.gz
```

- [ ] Eight assets, Windows names exactly as linked from `docs/download.md`. Leave the release
      as a **draft**; the orchestrator publishes it.

## 6. Publish (release orchestrator)

`release.yml` verifies the draft release's artifacts and then publishes stage by stage:
`test-installer.yml` (fresh install + upgrade from the previous release on a clean
`windows-latest` runner) -> TestPyPI publish + pip smoke install -> GitHub release
(draft -> public, marked latest) -> PyPI publish + pip smoke install.

```bash
gh workflow run release.yml -f tag=vX.Y-release -f verify-only=true   # optional: stop before anything goes public
gh workflow run release.yml -f tag=vX.Y-release
gh run watch
```

`publish-pypi.yml` can still be dispatched by hand (`-f tag=vX.Y-release -f environment=testpypi|pypi`);
for `pypi` it requires the tag's `Python Distribution`, `Windows Distribution` and
`Release Tests` runs to have succeeded.

- [ ] Orchestrator run is green
- [ ] https://pypi.org/project/dvr-scan/ and https://pypi.org/project/dvr-scan-headless/ show `X.Y`.
- [ ] Release is public and marked latest; Zenodo record appears at
      https://zenodo.org/account/settings/github/
- [ ] Smoke test using `pip`:

```bash
python -m venv /tmp/dvr && . /tmp/dvr/bin/activate      # or .\Scripts\activate
pip install dvr-scan==X.Y
dvr-scan --version
dvr-scan -i tests/resources/simple_movement.mp4 -so -df 4 -et 100
pip install --force-reinstall dvr-scan-headless==X.Y && dvr-scan --version
```

## 7. Website

`update-site.yml` runs automatically when the `vX.Y-release` tag is pushed (and on
`workflow_dispatch`). Because that happens before section 6, the download links on the site
resolve only once the release is public; re-dispatch if the site needs rebuilding later:

```bash
gh workflow run update-site.yml --ref vX.Y-release
```

- [ ] https://www.dvr-scan.com/ shows `Latest Version: X.Y`, `/download/` links resolve correctly,
      `/changelog/` shows the new section at the top

## 8. Post-release

- [ ] `dvr_scan/__init__.py`: `__version__ = "X.(Y+1)-dev0"`, add `### X.(Y+1) (In Development)`
      at the top of `docs/changelog.md`. Commit `[dist] Prepare for vX.(Y+1) development`
- [ ] Close the roadmap issue and milestone:
      `gh issue close <n> -c "Released in vX.Y"`; close milestone `vX.Y` on GitHub.
- [ ] Close/comment issues fixed in this release that are still open.
- [ ] `CITATION.cff`: add `version: X.Y`, `date-released: YYYY-MM-DD`, and (first time
      only) the concept `doi:`; add the DOI badge to `README.md` (snippet in `NEXT.md`).
- [ ] Announce: Discord, GitHub Discussions, any issues that asked for the feature.


# Automation Reference

| Script/Workflow | Description |
| --- | --- |
| `scripts/common.py` | version normalization, artifact names, hashing, Authenticode check |
| `scripts/update_installer.py` | `.aip` version/GUID/package-name bump; `--sync-files` / `--sync-only [--dev]` re-sync `APPDIR` |
| `scripts/finalize_windows_dist.py` | signed bundle -> MSI + portable zip + manifest + `SHA256SUMS`, then validate |
| `scripts/validate_release.py` | standalone artifact validation (`--allow-unsigned` for local dry runs) |
| `dist/pre_release.py --release` | asserts the `.aip` `ProductVersion` matches `__version__` |
| `release-test.yml` | tag vs `__version__`, changelog heading, build + `twine check`, `pip-audit` |
| `test-installer.yml` | MSI fresh install / upgrade / uninstall on a clean runner |
| `release.yml` | orchestrates installer test -> TestPyPI -> GitHub release -> PyPI |
| `update-site.yml` | rebuilds www.dvr-scan.com on `v*-release` tags |
| `appveyor.yml` | frozen build, `.aip` re-sync, MSI build, SignPath hand-off |
