# -*- mode: python -*-

block_cipher = None


a = Analysis(['../dvr_scan/__main__.py'],
             pathex=['.'],
             binaries=None,
             datas=[('../*.md', '.'), ('../dvr_scan/LICENSE*', '.'), ('../docs/', 'docs/')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
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
