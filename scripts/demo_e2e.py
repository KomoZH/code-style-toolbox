"""端到端演示：提取 → 规则落盘 → 转换 → 差异对照（仅标准库 urllib）。"""
import json
import urllib.request

BASE = "http://127.0.0.1:18765/api"


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    # 1. 取内置 Python 示例
    examples = get("/examples")["data"]
    py_example = next(e for e in examples if e["language"] == "python")
    samples = py_example["files"]
    print(f"[1] 示例: {py_example['language']} x {len(samples)} 个文件")

    # 2. 风格提取
    r = post("/extract", {
        "profile_name": "demo_extracted_style",
        "samples": [{"filename": f["filename"], "content": f["content"]} for f in samples],
    })
    assert r["code"] == 0, r
    profile = r["data"]
    pid = profile["id"]
    rules = profile["rules"]
    print(f"[2] 提取完成 profile_id={pid}")
    print(f"    naming.functions={rules['naming']['functions']}  "
          f"indent={rules['indent']['style']}x{rules['indent']['size']}")

    # 3. 用提取的规则转换同一份示例（验证提取→转换闭环）
    r = post("/convert", {
        "profile_id": pid,
        "items": [{"filename": samples[0]["filename"], "content": samples[0]["content"]}],
    })
    assert r["code"] == 0, r
    item = r["data"]["results"][0]
    diff_ops = item.get("diff", [])
    changed = [d for d in diff_ops if d.get("tag") != "equal"]
    print(f"[3] 转换 status={item['status']}, diff 块数={len(changed)}")
    if item["status"] == "converted":
        orig_lines = item["original"].count("\n")
        print(f"    原文 {orig_lines} 行，差异块 {len(changed)} 处（仅风格层面）")

    # 4. 语言识别抽查
    r = post("/detect", {"filename": "x.java", "code": "public class A { public static void main(String[] a){} }"})
    print(f"[4] 语言识别 java -> {r['data']['language']} (confidence={r['data']['confidence']})")

    # 5. 清理演示 profile
    with urllib.request.urlopen(
        urllib.request.Request(BASE + f"/profiles/{pid}", method="DELETE"), timeout=30
    ) as resp:
        json.loads(resp.read())
    print("[5] 演示 profile 已清理")


if __name__ == "__main__":
    main()
