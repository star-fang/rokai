# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['main.py'],
             pathex=['C:\\Users\\clavi\\PycharmProjects\\rokAi\\rokAiPy'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

for d in a.datas:
    if 'pyconfig' in d[0]:
        a.datas.remove(d)
        break

a.datas += [('ruby_in_dialog.png','C:\\Users\\clavi\\rokRss\\ruby_in_dialog.png','DATA'),
            ('ruby_day.png','C:\\Users\\clavi\\rokRss\\ruby_day.png','DATA'),
            ('ruby_night.png','C:\\Users\\clavi\\rokRss\\ruby_night.png','DATA'),
            ('btn_to_field.png','C:\\Users\\clavi\\rokRss\\btn_to_field.png','DATA'),
            ('btn_to_home.png','C:\\Users\\clavi\\rokRss\\btn_to_home.png','DATA'),
            ('btn_robot.png','C:\\Users\\clavi\\rokRss\\btn_robot.png','DATA'),
            ('head_robot.png','C:\\Users\\clavi\\rokRss\\head_robot.png','DATA'),
            ('error.log','C:\\Users\\clavi\\rokRss\\error.log','DATA'),
            ('debug.log','C:\\Users\\clavi\\rokRss\\debug.log','DATA'),
            ('name.json','C:\\Users\\clavi\\rokRss\\name.json','DATA'),
            ('vertex1947.json','C:\\Users\\clavi\\rokRss\\vertex1947.json','DATA')]

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='rokAi',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
