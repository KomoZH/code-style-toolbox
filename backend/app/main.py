"""FastAPI 入口：挂载路由、静态托管（SPA fallback）、端口选择、桌面窗口/浏览器启动。

源码模式：  python -m app.main   （backend/ 目录下）
打包模式：  PyInstaller 生成的 exe 直接调用 main()

启动形态：优先 pywebview 独立桌面窗口（Windows 内置 WebView2 渲染，
不依赖 JVM/Electron/浏览器）；pywebview 不可用时回退系统默认浏览器。
"""

from __future__ import annotations

import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import routes_convert, routes_extract, routes_profiles
from app.api.schemas import CODE_INTERNAL, err, ok
from app.config import DATA_DIR, STATIC_DIR, ensure_data_dirs, find_free_port


class SPAStaticFiles(StaticFiles):
    """SPA 静态托管：未知路径回退 index.html（前端路由 history 模式）。"""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        from starlette.exceptions import HTTPException as StarletteHTTPException

        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                index = Path(self.directory) / "index.html"  # type: ignore[arg-type]
                if index.exists():
                    return FileResponse(index)
            raise


def create_app() -> FastAPI:
    """应用工厂。"""
    ensure_data_dirs()
    app = FastAPI(title="Code Style Toolbox", version=__version__)

    app.include_router(routes_extract.router, prefix="/api")
    app.include_router(routes_profiles.router, prefix="/api")
    app.include_router(routes_convert.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok", "version": __version__})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):  # type: ignore[no-untyped-def]
        return JSONResponse(err(CODE_INTERNAL, f"未预期服务端错误：{exc}"), status_code=200)

    # 前端静态资源托管（前端构建产物 → backend/app/static）
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        app.mount("/", SPAStaticFiles(directory=str(STATIC_DIR), html=True), name="spa")

    return app


app = create_app()


def _run_server(port: int) -> None:
    """在后台线程中运行 uvicorn（桌面窗口模式下使用）。"""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def _wait_until_ready(port: int, timeout: float = 10.0) -> bool:
    """轮询 /api/health 直至服务就绪。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=1
            ) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            time.sleep(0.2)
    return False


def _open_browser_when_ready(port: int, delay: float = 1.2) -> None:
    """等待服务就绪后打开系统默认浏览器（pywebview 不可用时的回退形态）。"""

    def _open() -> None:
        time.sleep(delay)
        webbrowser.open(f"http://127.0.0.1:{port}/")

    threading.Thread(target=_open, daemon=True).start()


def _start_desktop_window(port: int) -> bool:
    """尝试以独立桌面窗口启动（pywebview + Windows 内置 WebView2）。

    返回 True 表示已进入桌面窗口事件循环（阻塞至窗口关闭）；
    返回 False 表示 pywebview 不可用，调用方应回退浏览器模式。

    稳定性措施（针对 WebView2 渲染进程崩溃 / CrashSender 报错）：
    - 关闭 GPU 渲染（--disable-gpu），规避显卡驱动导致的渲染进程崩溃；
    - 用户数据目录固定到项目 data/webview_data，避免默认目录 ACL/损坏问题；
    - 设置环境变量 CST_FORCE_BROWSER=1 可强制回退浏览器模式。
    """
    import os

    if os.environ.get("CST_FORCE_BROWSER") == "1":
        return False
    try:
        import webview  # pywebview，导入名 webview
    except ImportError:
        return False

    url = f"http://127.0.0.1:{port}/"
    threading.Thread(target=_run_server, args=(port,), daemon=True).start()
    if not _wait_until_ready(port):
        return False

    # WebView2 稳定性：禁用 GPU 渲染（渲染进程崩溃的最常见诱因）
    os.environ.setdefault(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--disable-gpu --disable-gpu-compositing",
    )
    storage = DATA_DIR / "webview_data"
    storage.mkdir(parents=True, exist_ok=True)

    print(f"Code Style Toolbox 已启动（独立窗口模式）: {url}  (关闭窗口即退出)")
    webview.create_window(
        "Code Style Toolbox — 代码风格迁移工具",
        url,
        width=1280,
        height=840,
        min_size=(960, 640),
    )
    # 阻塞；窗口关闭后返回，后台服务线程随进程退出
    webview.start(storage_path=str(storage))
    return True


def main() -> None:
    port = find_free_port()
    if _start_desktop_window(port):
        return
    _open_browser_when_ready(port)
    print(f"Code Style Toolbox 已启动（浏览器模式）: http://127.0.0.1:{port}/  (Ctrl+C 退出)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
