"""pywebview 最小复现：打开 about:blank，15 秒后自动关闭，输出完整调试日志。"""
import os
import sys
import threading
import time

os.environ.setdefault(
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "--disable-gpu --disable-gpu-compositing --no-sandbox --disable-renderer-backgrounding",
)

import webview

storage = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wv_test_data")
os.makedirs(storage, exist_ok=True)


def auto_close(win):
    for i in range(15):
        time.sleep(1)
        print(f"[{i+1}s] window alive", flush=True)
    print("closing window...", flush=True)
    win.destroy()


win = webview.create_window("wv-test", "about:blank", width=640, height=480)
t = threading.Thread(target=auto_close, args=(win,), daemon=True)
t.start()
print("webview.start() ...", flush=True)
webview.start(debug=True, storage_path=storage)
print("webview.start() returned normally", flush=True)
