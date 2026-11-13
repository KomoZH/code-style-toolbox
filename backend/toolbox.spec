# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（--onedir 绿色免安装，架构 §1.2）。

产出 dist/CodeStyleToolbox/CodeStyleToolbox.exe；
前端静态资源内嵌 app/static，示例与预设由 package.bat 拷贝到 exe 同级。
"""

from pathlib import Path

block_cipher = None

ROOT = Path(".").resolve()          # backend/
PROJECT_ROOT = ROOT.parent          # 项目根

datas = [
    (str(ROOT / "app" / "static"), "app/static"),
    (str(PROJECT_ROOT / "data" / "presets"), "data/presets"),
    (str(PROJECT_ROOT / "examples"), "examples"),
]

a = Analysis(
    ["app/main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # pywebview 独立桌面窗口（WebView2 渲染，依赖 pythonnet/clr_loader）
        "webview",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "clr_loader",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CodeStyleToolbox",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台窗口便于查看端口与日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CodeStyleToolbox",
)
