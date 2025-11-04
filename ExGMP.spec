# -*- mode: python ; coding: utf-8 -*-

# 移除了 get_hook_dirs 的导入
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# 自动搜寻PyTorch和相关库的数据文件和动态库
# 这会帮助找到如CUDA, cuDNN等二进制文件
datas = collect_data_files('torch')
datas += collect_data_files('torchvision')
datas += collect_data_files('pyqtgraph')
datas += collect_data_files('mne')
datas += [
    ('icons', 'icons'),
    ('models', 'models')
]

binaries = collect_dynamic_libs('torch')
binaries += collect_dynamic_libs('torchvision')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'torch',
        'torchvision',
        'mne',
        'scipy.special._cdflib',
        'scipy.linalg.cython_blas',
        'scipy.linalg.cython_lapack',
        'scipy.integrate',
        'scipy.interpolate',
        'scipy.signal',
        'scipy.cluster',
        'pyqtgraph.colors',
        'pyqtgraph.parametertree',
        'PyQt6.sip',
        'PyQt6.QtNetwork',
        'PyQt6.QtSvg',
    ],
    hookspath=[], # <-- 主要修改点：直接设置为空列表[]，PyInstaller会自动寻找
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorflow'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ExGMP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # <-- 如果再次打包后运行出错，请设为True以查看错误信息
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/logo.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ExGMP',
)