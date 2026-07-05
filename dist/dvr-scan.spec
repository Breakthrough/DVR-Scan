# -*- mode: python -*-

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, get_package_paths

block_cipher = None

# Collect PyAV explicitly so it is always included, rather than relying on the
# module graph and contrib hooks (#255). The Windows PyAV wheel keeps its FFmpeg
# DLLs in an av.libs directory next to the package (delvewheel layout), which
# collect_all does not see; collect them as data files to preserve that layout
# (same approach as the pyinstaller-hooks-contrib hook, with which PyInstaller
# de-duplicates these entries).
av_datas, av_binaries, av_hiddenimports = collect_all('av')
_av_libs_dir = os.path.join(get_package_paths('av')[0], 'av.libs')
if not os.path.isdir(_av_libs_dir):
    raise SystemExit('av.libs not found: PyAV FFmpeg DLLs would be missing from the build')
av_datas += [(os.path.join(_av_libs_dir, f), 'av.libs') for f in os.listdir(_av_libs_dir)]

cli = Analysis(['../dvr_scan/__main__.py'],
             pathex=['.'],
             binaries=av_binaries,
             datas=[
                ('../dvr_scan/dvr-scan.ico', 'dvr_scan'),
                ('../dvr_scan/dvr-scan-logo.png', 'dvr_scan'),
                ('../dvr_scan/LICENSE*', 'dvr_scan'),
            ] + av_datas,
             hiddenimports=av_hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

cli_pyz = PYZ(cli.pure, cli.zipped_data,
             cipher=block_cipher)

cli_exe = EXE(cli_pyz,
          cli.scripts,
          exclude_binaries=True,
          name='dvr-scan',
          debug=False,
          strip=False,
          upx=True,
          console=True,
          version='.version_info',
          icon='../dvr_scan/dvr-scan.ico')

app = Analysis(['../dvr_scan/app/__main__.py'],
             pathex=['.'],
             binaries=av_binaries,
             datas=[
                ('../dvr_scan/dvr-scan.ico', 'dvr_scan'),
                ('../dvr_scan/dvr-scan-logo.png', 'dvr_scan'),
                ('../dvr_scan/dvr-scan.png', 'dvr_scan'),
                ('../dvr_scan/LICENSE*', 'dvr_scan'),
            ] + collect_data_files('tkinterdnd2') + av_datas,
             hiddenimports=['tkinterdnd2'] + av_hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

app_pyz = PYZ(app.pure, app.zipped_data,
             cipher=block_cipher)

app_exe = EXE(app_pyz,
          app.scripts,
          exclude_binaries=True,
          name='dvr-scan-app',
          debug=False,
          strip=False,
          upx=True,
          console=True,
          hide_console="hide-late",
          version='.version_info',
          icon='../dvr_scan/dvr-scan.ico')

coll = COLLECT(
               cli_exe,
               cli.binaries,
               cli.zipfiles,
               cli.datas,
               app_exe,
               app.binaries,
               app.zipfiles,
               app.datas,
               strip=False,
               upx=True,
               name='dvr-scan')
