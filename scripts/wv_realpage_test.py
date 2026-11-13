"""白屏诊断：用 pywebview 打开真实应用页面，分别测试带/不带 GPU 禁用参数。
用法: python wv_realpage_test.py [nogpu]
"""
import os
import sys
import threading
import time

if "nogpu" in sys.argv:
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-gpu --disable-gpu-compositing"
    print("mode: disable-gpu")
else:
    print("mode: default (no extra args)")

import webview


def auto_close(win):
    time.sleep(20)
    win.destroy()


win = webview.create_window("wv-realpage-test", "http://127.0.0.1:18765/", width=1000, height=700)
threading.Thread(target=auto_close, args=(win,), daemon=True).start()
webview.start(debug=True)
print("exited normally")
