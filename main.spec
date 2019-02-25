# -*- mode: python -*-

# noinspection PyUnresolvedReferences
a = Analysis(['main.py'],
             pathex=['/Users/melvyn/MenuPlaythrough'],
             datas=[('imgs/icon.png', '.')],
             hiddenimports=['numpy.core._dtype_ctypes'])

# noinspection PyUnresolvedReferences
pyz = PYZ(a.pure, a.zipped_data)

# noinspection PyUnresolvedReferences
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='MenuPlaythough',
          bootloader_ignore_signals=False,
          upx=True,
          console=False)

# noinspection PyUnresolvedReferences
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               upx=True,
               name='MenuPlaythrough')

# noinspection PyUnresolvedReferences
app = BUNDLE(coll,
             name='MenuPlaythrough.app',
             icon='imgs/Icon.icns',
             info_plist={'LSUIElement': True})
