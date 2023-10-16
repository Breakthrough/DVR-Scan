# -*- mode: python -*-

block_cipher = None

a = Analysis(['../dvr_scan/__main__.py'],
             pathex=['.'],
             binaries=None,
             datas=[
                ('../dvr-scan.cfg', 'dvr-scan'),
                ('../*.md', 'dvr-scan'),
                ('../dist/dvr-scan.ico', 'dvr-scan'),
                ('../dvr_scan/LICENSE*', 'dvr-scan'),
                ('../docs/*.md', 'dvr-scan/docs/')
            ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=["av"],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='dvr-scan',
          debug=False,
          strip=False,
          upx=True,
          console=True,
          version='.version_info',
          icon='dvr-scan.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='dvr-scan')
