# -*- mode: python -*-

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

cli = Analysis(['../dvr_scan/__main__.py'],
             pathex=['.'],
             binaries=None,
             datas=[
                ('../dvr_scan/dvr-scan.ico', 'dvr_scan'),
                ('../dvr_scan/dvr-scan-logo.png', 'dvr_scan'),
                ('../dvr_scan/LICENSE*', 'dvr_scan'),
            ],
             hiddenimports=[],
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
             binaries=None,
             datas=[
                ('../dvr_scan/dvr-scan.ico', 'dvr_scan'),
                ('../dvr_scan/dvr-scan-logo.png', 'dvr_scan'),
                ('../dvr_scan/dvr-scan.png', 'dvr_scan'),
                ('../dvr_scan/LICENSE*', 'dvr_scan'),
            ] + collect_data_files('tkinterdnd2'),
             hiddenimports=['tkinterdnd2'],
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
