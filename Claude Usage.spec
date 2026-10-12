# -*- mode: python ; coding: utf-8 -*-
# Build with ./build_dmg.sh, which runs: pyinstaller --noconfirm "Claude Usage.spec"


a = Analysis(
    ['usage_bar.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Claude Usage',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,   # the arch of the Mac building it (Intel or Apple Silicon)
    codesign_identity=None,
    entitlements_file=None,
    icon=['build_assets/ClaudeUsage.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Claude Usage',
)
app = BUNDLE(
    coll,
    name='Claude Usage.app',
    icon='build_assets/ClaudeUsage.icns',
    bundle_identifier='local.claude-usage-bar',
    version='1.0.2',
    info_plist={
        'LSUIElement': True,
        'NSHumanReadableCopyright': '© 2026 Afif Tabish',
        'CFBundleGetInfoString': 'Claude Usage 1.0.2 by Afif Tabish',
    },
)
