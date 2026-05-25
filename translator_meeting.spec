# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'sounddevice',
        'numpy',
        'websocket',
        'websocket._abnf',
        'websocket._core',
        'websocket._exceptions',
        'websocket._handshake',
        'websocket._http',
        'websocket._logging',
        'websocket._socket',
        'websocket._ssl_compat',
        'websocket._utils',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'urllib.request',
        'urllib.parse',
        'json',
        'threading',
        'config',
        'audio_capture',
        'soniox_client',
        'translator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MeetingTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if sys.platform == 'win32' and os.path.exists('icon.ico') else ('icon.icns' if sys.platform == 'darwin' and os.path.exists('icon.icns') else None),
    version=None,
)

# macOS: wrap EXE in an .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='MeetingTranslator.app',
        icon='icon.icns',  # Place icon.icns in project root
        bundle_identifier='com.meetingtranslator.app',
        info_plist={
            'NSMicrophoneUsageDescription': 'Meeting Translator needs microphone access for speech recognition.',
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
        },
    )
