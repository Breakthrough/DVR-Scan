#
#      DVR-Scan: Video Motion Event Detection & Extraction Tool
#   --------------------------------------------------------------
#       [  Site: https://www.dvr-scan.com/                 ]
#       [  Repo: https://github.com/Breakthrough/DVR-Scan  ]
#
# Copyright (C) 2016 Brandon Castellano <http://www.bcastell.com>.
# DVR-Scan is licensed under the BSD 2-Clause License; see the included
# LICENSE file, or visit one of the above pages for details.
#

"""Infrastructure script to run before generating a release."""

import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def write_version_info_for_windows_exe():
    print("Creating .version_info.")
    sys.path.append(str(Path(".").absolute()))
    import dvr_scan

    VERSION = dvr_scan.__version__

    with open("dist/.version_info", "wb") as f:
        elements = [int(elem) if elem.isnumeric() else 999 for elem in VERSION.split(".")]
        assert 2 <= len(elements) <= 3
        major = elements[0]
        minor = elements[1]
        patch = elements[2] if len(elements) == 3 else 0

        f.write(
            f"""# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
# filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
# Set not needed items to zero 0.
filevers=(0, {major}, {minor}, {patch}),
prodvers=(0, {major}, {minor}, {patch}),
# Contains a bitmask that specifies the valid bits 'flags'r
mask=0x3f,
# Contains a bitmask that specifies the Boolean attributes of the file.
flags=0x0,
# The operating system for which this file was designed.
# 0x4 - NT and there is no need to change it.
OS=0x4,
# The general type of file.
# 0x1 - the file is an application.
fileType=0x1,
# The function of the file.
# 0x0 - the function is not defined for this fileType
subtype=0x0,
# Creation date and time stamp.
date=(0, 0)
),
  kids=[
StringFileInfo(
  [
  StringTable(
    u'040904B0',
    [StringStruct(u'CompanyName', u'github.com/Breakthrough'),
    StringStruct(u'FileDescription', u'www.dvr-scan.com'),
    StringStruct(u'FileVersion', u'{VERSION}'),
    StringStruct(u'InternalName', u'DVR-Scan'),
    StringStruct(u'LegalCopyright', u'Copyright © 2025 Brandon Castellano'),
    StringStruct(u'OriginalFilename', u'dvr-scan.exe'),
    StringStruct(u'ProductName', u'DVR-Scan'),
    StringStruct(u'ProductVersion', u'{VERSION}')])
  ]),
VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
""".encode()
        )


def build_docs(use_local_images=True):
    print("Building docs.")

    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(Path("docs/"), tmp.joinpath("docs"), dirs_exist_ok=True)
        shutil.copytree(Path("website/"), tmp.joinpath("website"), dirs_exist_ok=True)

        index_path = tmp.joinpath("docs", "index.md")
        new_index = tmp.joinpath("docs", "index_docs.md")
        new_index.replace(index_path)
        tmp.joinpath("docs", "download.md").unlink()

        mkdocs_path = tmp.joinpath("mkdocs.yml")
        curr_mkdocs_path = tmp.joinpath("docs", "mkdocs.yml")
        curr_mkdocs_path.replace(mkdocs_path)

        docs_build_path = Path("dvr_scan").joinpath("docs")

        subprocess.run(
            [
                "mkdocs",
                "build",
                "--config-file",
                mkdocs_path.absolute(),
                "--site-dir",
                docs_build_path.absolute(),
            ],
            check=True,
        )
        print("Postprocessing docs.")

        delete_and_replace = [
            "assets/bounding-box.gif",
            "assets/dvr-scan-logo.png",
            "assets/dvr-scan.ico",
            "assets/dvr-scan.png",
            "assets/region-editor-mask.jpg",
            "assets/region-editor-multiple.jpg",
            "assets/region-editor-region.jpg",
            "assets/region-editor-start.jpg",
        ]

        # Fix some issues with the output from mkdocs for local use without a web server.
        # TODO: Should disable search feature on local docs since it doesn't work.
        replacements = {'href="."': 'href="index.html"'}
        if not use_local_images:
            replacements.update(
                {path: f"https://www.dvr-scan.com/{path}" for path in delete_and_replace}
            )

        for file in [Path(path) for path in docs_build_path.glob("**/*.html")]:
            contents = file.read_text()
            for old, new in replacements.items():
                contents = contents.replace(old, new)
            # HACK: Fix non-normalized paths.
            contents = contents.replace("../", "")
            file.unlink(missing_ok=False)
            file.write_text(contents)

        if not use_local_images:
            # Delete files now that they are not referenced.
            for path in delete_and_replace:
                docs_build_path.joinpath(path).unlink(missing_ok=False)

        for to_remove in (
            "requirements.txt",
            "sitemap.xml",
            "sitemap.xml.gz",
            "assets/images",
            "assets/javascripts/lunr",
            "assets/javascripts/workers",
            "assets/javascripts/bundle.220ee61c.min.js.map",
            "assets/stylesheets/main.eebd395e.min.css.map",
            "assets/stylesheets/palette.ecc896b0.min.css.map",
        ):
            to_remove = docs_build_path.joinpath(to_remove)
            shutil.rmtree(
                to_remove, ignore_errors=False
            ) if to_remove.is_dir() else to_remove.unlink()

        def remove_mapping():
            path = docs_build_path.joinpath("assets/javascripts/bundle.220ee61c.min.js")
            contents = path.read_text()
            TO_REMOVE = "//# sourceMappingURL=bundle.220ee61c.min.js.map\n"
            assert TO_REMOVE in contents
            contents = contents.replace(TO_REMOVE, "")
            path.unlink()
            path.write_text(contents)

        remove_mapping()


if __name__ == "__main__":
    if not (len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "--use-local-images")):
        print("Usage: pre_release.py [--use-local-images]")
        raise SystemExit(1)

    write_version_info_for_windows_exe()
    build_docs(use_local_images=bool(len(sys.argv) == 2 and sys.argv[1] == "--use-local-images"))
