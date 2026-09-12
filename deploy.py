#!/usr/bin/env python3
"""部署脚本：从CDN下载最新index.html并提交到main分支"""
import urllib.request, os, subprocess, sys

URL = "https://aka.doubaocdn.com/s/IYsw8lU65q"
OUT = "index.html"

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.stderr:
        print(r.stderr.strip(), file=sys.stderr)
    return r

def main():
    print(f"正在从 {URL} 下载 index.html...")
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        content = resp.read().decode("utf-8")
    print(f"下载完成，大小: {len(content)} 字符")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"已写入 {OUT}")

    # 验证倒序
    if "15:55" in content and "15:40" in content:
        i1 = content.index("15:55")
        i2 = content.index("15:40")
        if i1 < i2:
            print("验证通过：探索轨迹为倒序排列（15:55在15:40之前）")
        else:
            print("警告：顺序可能不正确")

    # git提交
    run("git config user.name 'github-actions[bot]'")
    run("git config user.email 'github-actions[bot]@users.noreply.github.com'")
    run(f"git add {OUT}")
    r = run("git commit -m '更新探索轨迹为倒序排列 + 最新数据快照(2026-09-12 15:55)'")
    if "nothing to commit" not in (r.stdout + r.stderr):
        run("git push origin main")
        print("已提交并推送到 main 分支")
    else:
        print("无变化，无需提交")

if __name__ == "__main__":
    main()
