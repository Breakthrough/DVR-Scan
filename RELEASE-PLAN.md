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
- [ ] `appveyor.yml`: Advanced Installer `PATH` entry (`Advanced Installer 23.3`) must match the
      version `advinst.msi` currently installs
- [ ] Advanced Installer OSS license still valid

### Changelog and docs

- [ ] `docs/changelog.md` is up to date and accurate
- [ ] `docs/download.md` is up to date and accurate
- [ ] Verify all docs are up to date: `README.md`, `docs/*.md`, the `dvr-scan.cfg` config file
      template, `dvr-scan --help` output, `CONTRIBUTING.md`, etc.

### Installer project (Windows releases)

- [ ] `dist/installer/DVR-Scan.aip`: set `ProductVersion` to `X.Y`, `PackageFileName` to
      `DVR-Scan-X.Y-win64`, and generate a new `ProductCode` GUID.
      See 1d6a057 (`git show 1d6a057 -- dist/installer/DVR-Scan.aip`) for a historical example.
- [ ] If bundled files changed (new Python/PyAV/OpenCV DLLs), re-sync the `.aip` file list
      against a local `dist/dvr-scan/` build in the Advanced Installer GUI

### Local frozen build test

```bash
python dist/pre_release.py --use-local-images
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
- [ ] `dvr-scan-app.exe` launches, wizard opens, and can perform a scan

## 2. Release commit

- [ ] `dvr_scan/__init__.py`: `__version__ = "X.Y"` (no `-dev` suffix).
- [ ] `docs/changelog.md`: heading `(In Development)` -> `(YYYY-MM-DD)`.
- [ ] `README.md`: `### Latest Release: vX.Y (Month D, YYYY)`.
- [ ] `docs/download.md`: Python block and Windows blocks need updated version/date information
      and download links
- [ ] `docs/index.md` and `docs/index_docs.md`: `Latest Version: X.Y (Month D, YYYY)`
- [ ] `dist/installer/DVR-Scan.aip` and `appveyor.yml` if not already committed above
- [ ] Dates are the actual tag date, consistent across all five files
- [ ] `git status` shows nothing else (`dvr_scan/docs/` is clean)

```bash
git add README.md docs/changelog.md docs/download.md docs/index.md docs/index_docs.md \
        dvr_scan/__init__.py dist/installer/DVR-Scan.aip appveyor.yml
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

Pushing the tag triggers various runs automatically.

- [ ] `gh run list --branch vX.Y-release` shows all GitHub workflows passing
- [ ] AppVeyor build passes
- [ ] SignPath: approved signing request and assembled release artifacts:
  - `dvr-scan-X.Y-win64.msi`: the signed MSI (filename must be lowercase)
  - `dvr-scan-X.Y-win64.zip`: AppVeyor artifact `DVR-Scan-win64_portable` with the two
    `.exe` files inside replaced with the signed variants, and renamed correctly
- [ ] `Get-AuthenticodeSignature` is `Valid` on the MSI and on both EXE files inside the archive
- [ ] Install the MSI on a clean Windows machine: shortcut should launches the app,
      `dvr-scan --version` works from a command prompt, upgrade over the previous version works,
      and uninstall leaves no traces aside from user config data.
- [ ] Portable zip: extract, run `dvr-scan.exe --version` and one scan.

## 5. GitHub release

- [ ] Zenodo: the GitHub switch for `Breakthrough/DVR-Scan` is ON **before** publishing, so the
      publish event mints a new DOI (the tag itself does not).
- [ ] Download the Python artifacts from the tag's Python Distribution:
      `gh run download <run-id> -n dvr-scan-dist -D release/`
      (should be four files: `dvr_scan-X.Y` and `dvr_scan_headless-X.Y`, `.whl` + `.tar.gz`).
- [ ] Release notes: verbatim to the corresponding the `X.Y` changelog section, but with adjusted
      `####` headings promoted to `##` (`#### Release Notes` -> `## Release Notes`) since the
      existing headers are chosen for the website

```bash
gh release create vX.Y-release --draft --title "DVR-Scan vX.Y" --notes-file release-notes.md \
    release/dvr-scan-X.Y-win64.msi release/dvr-scan-X.Y-win64.zip \
    release/dvr_scan-X.Y-py3-none-any.whl release/dvr_scan-X.Y.tar.gz \
    release/dvr_scan_headless-X.Y-py3-none-any.whl release/dvr_scan_headless-X.Y.tar.gz
```

- [ ] Six assets, names exactly as linked from `docs/download.md`.
- [ ] Upload draft (`gh release edit vX.Y-release --draft=false --latest`).
- [ ] Zenodo record appears at https://zenodo.org/account/settings/github/

## 6. PyPI

`publish-pypi.yml` is manually triggered. For `pypi` it requires the tag's Python Distribution and
Windows Distribution runs to have succeeded via push event. It reuses the same `dvr-scan-dist`
artifact for the release commit test run.

```bash
gh workflow run publish-pypi.yml -f tag=vX.Y-release -f environment=testpypi
gh workflow run publish-pypi.yml -f tag=vX.Y-release -f environment=pypi
```

- [ ] Publish on TestPyPI: `gh workflow run publish-pypi.yml -f tag=vX.Y-release -f environment=testpypi`
- [ ] `pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple dvr-scan==X.Y` works
- [ ] https://test.pypi.org/project/dvr-scan/ and https://test.pypi.org/project/dvr-scan-headless/ show `X.Y`.
- [ ] Publish on PyPI: `gh workflow run publish-pypi.yml -f tag=vX.Y-release -f environment=pypi`
- [ ] https://pypi.org/project/dvr-scan/ and https://pypi.org/project/dvr-scan-headless/ show `X.Y`.
- [ ] Smoke test using `pip`:

```bash
python -m venv /tmp/dvr && . /tmp/dvr/bin/activate      # or .\Scripts\activate
pip install dvr-scan==X.Y
dvr-scan --version
dvr-scan -i tests/resources/simple_movement.mp4 -so -df 4 -et 100
pip install --force-reinstall dvr-scan-headless==X.Y && dvr-scan --version
```

## 7. Website

The site is usually automatically built by `update-site.yml` from `main`. To trigger a manual build
from the release tag itself instead:

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


# Missing Automation

TODOs for this plan which are outstanding (most of these already exist for PySceneDetect):

- `scripts/update_installer.py` equivalent: bump `.aip` `ProductVersion`/`PackageFileName`
  from `__version__` and re-sync the file list (`AdvancedInstaller.com /edit ... /NewSync`).
- `scripts/finalize_windows_dist.py` + `validate_release.py` equivalents
- Rebuild the portable zip from the signed MSI (`msiexec /a`), emit `SHA256SUMS`, verify
  Authenticode signatures and MSI/zip parity, smoke-test the frozen exe.
- `release-test.yml`: tag vs `__version__` check, changelog heading check,
  `twine check`, `pip-audit`.
- Add a release orchestrator (`release.yml`) and `test-installer.yml` (MSI install/upgrade on a
  Github Actions runner instead of a local VM).
- Trigger `update-site.yml` on `v*-release` tags instead of the `release` branch.

