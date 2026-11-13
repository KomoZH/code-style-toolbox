"""路径常量、数据目录初始化与端口策略（架构 §8 目录约定）。

源码模式：数据目录 = <项目根>/data；打包模式：数据目录 = exe 同级/data。
任何模块不得自行拼路径，统一从本模块取。
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 根目录判定
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    # PyInstaller 打包模式：exe 同级目录
    ROOT_DIR: Path = Path(sys.executable).resolve().parent
    # 前端静态资源随包内嵌（toolbox.spec datas → app/static）
    STATIC_DIR: Path = Path(getattr(sys, "_MEIPASS", ROOT_DIR)) / "app" / "static"
    _BUNDLED_PRESETS: Path = Path(getattr(sys, "_MEIPASS", ROOT_DIR)) / "data" / "presets"
    _BUNDLED_EXAMPLES: Path = Path(getattr(sys, "_MEIPASS", ROOT_DIR)) / "examples"
else:
    # 源码模式：本文件位于 backend/app/config.py → 项目根为上三级
    ROOT_DIR = Path(__file__).resolve().parents[2]
    STATIC_DIR = Path(__file__).resolve().parent / "static"
    _BUNDLED_PRESETS = ROOT_DIR / "data" / "presets"
    _BUNDLED_EXAMPLES = ROOT_DIR / "examples"

DATA_DIR: Path = ROOT_DIR / "data"
PROFILES_DIR: Path = DATA_DIR / "profiles"
PRESETS_DIR: Path = DATA_DIR / "presets"
HISTORY_DIR: Path = DATA_DIR / "history"
EXAMPLES_DIR: Path = _BUNDLED_EXAMPLES

# 端口策略（架构 §5-7）：默认 18765，占用时递增探测
DEFAULT_PORT: int = 18765
MAX_PORT_PROBE: int = 20

# 历史快照容量（架构 §5-6）
HISTORY_KEEP: int = 50

# 提取置信度阈值（架构 §3.1 字段约定）
LOW_CONFIDENCE: float = 0.6
LOW_SAMPLES: int = 30
LOW_TOTAL_LINES: int = 200


def ensure_data_dirs() -> None:
    """首次运行时创建数据目录；打包模式下将内置预设复制到 exe 同级 data/。"""
    for d in (DATA_DIR, PROFILES_DIR, PRESETS_DIR, HISTORY_DIR):
        d.mkdir(parents=True, exist_ok=True)
    # 打包模式下 presets 为只读内嵌资源，首次运行拷贝出来便于统一读取
    if getattr(sys, "frozen", False) and _BUNDLED_PRESETS.exists():
        import shutil

        for src in _BUNDLED_PRESETS.glob("*.yaml"):
            dst = PRESETS_DIR / src.name
            if not dst.exists():
                shutil.copy2(src, dst)


def find_free_port(start: int = DEFAULT_PORT, max_probe: int = MAX_PORT_PROBE) -> int:
    """从 start 起递增探测可用端口。"""
    for offset in range(max_probe):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"端口 {start}~{start + max_probe - 1} 均被占用，无法启动服务")
