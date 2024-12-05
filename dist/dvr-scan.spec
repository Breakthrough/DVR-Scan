# -*- mode: python -*-

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
             excludes=["av"],
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

coll = COLLECT(cli_exe,
               cli.binaries,
               cli.zipfiles,
               cli.datas,
               strip=False,
               upx=True,
               name='dvr-scan')
