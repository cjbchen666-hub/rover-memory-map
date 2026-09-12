#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rover 记忆地图网页生成器
- 输入：rover/state.json, rover/memory.md, rover/trail.md, rover/web/reports/*.md
- 输出：rover/web/index.html（自包含，数据固化；ECharts 走 CDN）
- 用法：每次漫游汇报后运行一次：python3 build_site.py
"""
import json, re, os, html as H

ROVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(WEB_DIR, "reports")
OUT = os.path.join(WEB_DIR, "index.html")

# ---------- 领域配色 ----------
DOMAINS = {
    "能力实证": {"ids": {1, 2, 3, 9, 16, 18, 19, 24, 29, 30, 31}, "color": "#58a6ff", "desc": "AI 能力边界、自主科研、元认知"},
    "安全治理": {"ids": {5, 7, 8, 12, 15, 17, 23}, "color": "#f78166", "desc": "pacing、分级管控、攻防评估"},
    "社会结构": {"ids": {4, 6, 10, 11, 13, 14, 34, 35}, "color": "#7ee787", "desc": "雇佣与中层、居民去杠杆、银行转型"},
    "极限工程": {"ids": {20, 21, 22}, "color": "#d2a8ff", "desc": "悬索桥极限、CFRP、制度时滞"},
    "天文考古": {"ids": {25, 26, 27, 28, 32}, "color": "#ffd58a", "desc": "Chandra、毅力号、火星样本、FAST、城市考古"},
    "生物基因": {"ids": {33}, "color": "#ffa657", "desc": "CRISPR 基因编辑、体内编辑、儿童伦理"},
    "认知科学": {"ids": {36, 37, 38}, "color": "#bc8cff", "desc": "BabyLM、fMRI 神经对齐、视觉错觉机制"},
}
ID2DOMAIN = {i: d for d, meta in DOMAINS.items() for i in meta["ids"]}

# ---------- 汇报发现的领域分类关键词 ----------
CATEGORY_KEYWORDS = {
    "能力实证": ["模型", "训练", "优化", "nanogpt", "agent", "科研", "复现", "靶场", "能力", "参数", "loss", "gpt", "claude", "fable", "opus", "kimi", "deepseek", "glm", "grok", "自主", "改进", "算法", "算力", "token"],
    "安全治理": ["pacing", "分级", "安全", "护栏", "astra", "daybreak", "aisi", "网络安全", "preparedness", "critical", "漏洞", "exploit", "攻击", "网安", "防御", "风险", "监管", "发布", "密钥", "bedrock"],
    "社会结构": ["银行", "劳动力", "就业", "组织", "中层", "雇佣", "数字员工", "工时", "裁员", "岗位", "管理", "企业", "公司", "创业", "受益", "分配", "经济", "金融", "行业"],
    "极限工程": ["桥", "悬索", "cfrp", "材料", "工程", "墨西拿", "主缆", "斜拉", "跨度", "钢缆", "基建", "建筑", "结构"],
    "天文考古": ["火星", "天文", "chandra", "fast", "射电暴", "x 射线", "x射线", "星系", "太空", "样本", "漫游车", "frb", "超新星", "宇宙", "望远镜", "观测", "nasa", "天问", "毅力", "天体", "黑洞", "中子星"],
}

def classify_finding(title, body):
    """根据标题和正文关键词判断发现所属领域，返回最匹配的领域名。"""
    text = (title + " " + body).lower()
    scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in kws if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "能力实证"

def parse_report_findings(raw):
    """解析汇报 md 中的每条发现，返回 [{idx, title, body, category, source, so_what}]。"""
    findings = []
    # 匹配 **[N. 标题]** 开头的发现块
    pattern = re.compile(r"\*\*\[\s*(\d+)\.\s*(.+?)\s*\]\*\*(.*?)(?=\n\*\*\[\s*\d+\.|\n### |\Z)", re.S)
    for m in pattern.finditer(raw):
        idx = int(m.group(1))
        title = m.group(2).strip()
        body = m.group(3).strip()
        category = classify_finding(title, body)
        # 提取来源 URL
        src_m = re.search(r"来源[：:]\s*(https?://\S+)", body)
        source = src_m.group(1) if src_m else ""
        # 提取"所以呢"
        so_m = re.search(r"所以呢[：:]\s*(.+?)(?=\n- |\Z)", body, re.S)
        so_what = re.sub(r"\s+", " ", so_m.group(1)).strip()[:120] if so_m else ""
        findings.append({
            "idx": idx, "title": title, "body": body,
            "category": category, "source": source, "so_what": so_what
        })
    return findings

# ---------- 解析 state.json ----------
def load_state():
    p = os.path.join(ROVER_DIR, "state.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)

# ---------- 解析 memory.md ----------
def parse_memory():
    p = os.path.join(ROVER_DIR, "memory.md")
    text = open(p, encoding="utf-8").read()
    # 点区
    points = {}
    for m in re.finditer(r"\[点 (\d+)\]\s*((?:.|\n)*?)(?=\n\[点 |\n## )", text):
        pid = int(m.group(1))
        body = re.sub(r"\s+", " ", m.group(2)).strip()
        points[pid] = body
    # 连线区
    links = []
    lone = []
    for line in text.splitlines():
        m = re.match(r"\[点 (\d+)\]\s*←\s*(\S+)\s*→\s*\[([^\]]+)\]\s*：?(.*)", line.strip())
        if m:
            src = int(m.group(1))
            typ = m.group(2)
            dst_raw = m.group(3)
            note = re.sub(r"\s+", " ", m.group(4)).strip()[:110]
            m2 = re.match(r"点 (\d+)", dst_raw)
            if m2:
                dst = int(m2.group(1))
                links.append({"src": src, "dst": dst, "type": typ, "note": note})
            else:
                links.append({"src": src, "dst_text": dst_raw, "type": typ, "note": note})
        m = re.match(r"\[点 (\d+)\]\s*（[^）]*孤点[^）]*）(.*)", line.strip())
        if m:
            lone.append({"id": int(m.group(1)), "note": re.sub(r"\s+", " ", m.group(2)).strip()[:110]})
    # 地图形状观察
    shapes = []
    parts = text.split("## 地图形状观察")
    for part in parts[1:]:
        s = re.sub(r"\s+", " ", part).strip()
        if s:
            shapes.append(s)
    return points, links, lone, shapes

# ---------- 解析 trail.md ----------
def parse_trail():
    p = os.path.join(ROVER_DIR, "trail.md")
    text = open(p, encoding="utf-8").read()
    entries = []
    blocks = re.split(r"\n## ", text)
    for blk in blocks[1:]:
        header, _, rest = blk.partition("\n")
        hm = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|\s*(.*?)\s*\|\s*(.*)", header)
        if not hm:
            continue
        t, start, angle = hm.group(1), hm.group(2).strip(), hm.group(3).strip()
        def grab(key):
            m = re.search(r"- " + key + r"：(.*?)(?=\n- |\n## |\Z)", rest, re.S)
            if not m:
                return ""
            return re.sub(r"\s+", " ", m.group(1)).strip()
        entries.append({
            "time": t, "start": start, "angle": angle,
            "saw": grab("我看了什么"),
            "found": grab("我发现了什么"),
            "jump": grab("我跳到了哪里"),
            "judge": grab("我的判断"),
        })
    entries.reverse()  # 倒序：最新时间在前
    return entries

# ---------- 解析汇报归档 ----------
def md_to_html(md):
    lines = md.splitlines()
    out, in_list = [], False
    first = True
    for ln in lines:
        s = ln.rstrip()
        if first and s.startswith("# "):
            first = False
            continue
        first = False
        if not s:
            if in_list:
                out.append("</ul>"); in_list = False
            continue
        if s.startswith("### "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h4>{H.escape(s[4:])}</h4>")
        elif s.startswith("## "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h3>{H.escape(s[3:])}</h3>")
        elif s.startswith("# "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h2>{H.escape(s[2:])}</h2>")
        elif s.startswith("- "):
            if not in_list: out.append("<ul>"); in_list = True
            item = s[2:]
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", item)
            item = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', item)
            out.append(f"<li>{item}</li>")
        else:
            if in_list: out.append("</ul>"); in_list = False
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            out.append(f"<p>{item}</p>")
    if in_list: out.append("</ul>")
    return "\n".join(out)

def load_reports():
    reports = []
    if os.path.isdir(REPORTS_DIR):
        for fn in sorted(os.listdir(REPORTS_DIR)):
            if fn.endswith(".md"):
                raw = open(os.path.join(REPORTS_DIR, fn), encoding="utf-8").read()
                title = raw.splitlines()[0].lstrip("# ").strip() if raw.splitlines() else fn
                # 从文件名提取时间 2026-09-12-0950
                tm = re.match(r"(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})", fn)
                time_str = f"{tm.group(1)} {tm.group(2)}:{tm.group(3)}" if tm else fn
                findings = parse_report_findings(raw)
                # 领域分布统计
                cat_counts = {}
                for f in findings:
                    cat_counts[f["category"]] = cat_counts.get(f["category"], 0) + 1
                reports.append({
                    "file": fn, "title": title, "time": time_str,
                    "html": md_to_html(raw), "findings": findings,
                    "cat_counts": cat_counts
                })
    reports.sort(key=lambda r: r["file"], reverse=True)
    return reports

# ---------- 生成 ECharts 数据 ----------
def build_graph(points, links, lone):
    degrees = {}
    for l in links:
        if "dst" in l:
            degrees[l["src"]] = degrees.get(l["src"], 0) + 1
            degrees[l["dst"]] = degrees.get(l["dst"], 0) + 1
    nodes = []
    for pid, body in sorted(points.items()):
        d = ID2DOMAIN.get(pid, "能力实证")
        label = f"点{pid}"
        brief = body[:64] + ("…" if len(body) > 64 else "")
        nodes.append({
            "id": pid, "name": label, "value": degrees.get(pid, 0) + 1,
            "category": d,
            "symbolSize": 18 + min(degrees.get(pid, 0) * 3, 26),
            "brief": H.escape(brief),
        })
    edges = []
    ext_count = 0
    for l in links:
        if "dst" in l and l["dst"] in points:
            edges.append({"source": l["src"], "target": l["dst"],
                          "type": l["type"], "note": H.escape(l["note"])})
        elif "dst_text" in l:
            ext_count += 1
            ext_id = f"ext-{ext_count}"
            name = l["dst_text"].split("（")[0][:12]
            nodes.append({
                "id": ext_id, "name": name, "value": 1,
                "category": "外部", "symbolSize": 14,
                "brief": H.escape(l["dst_text"][:60]),
            })
            edges.append({"source": l["src"], "target": ext_id,
                          "type": l["type"], "note": H.escape(l["note"])})
    return nodes, edges, lone

# ---------- 组装 HTML ----------
def render(state, points, links, lone, shapes, entries, reports, nodes, edges):
    state_html = f"""
    <div class="stat-grid">
      <div class="stat-card">
        <span class="stat-label">当前位置</span>
        <span class="stat-value">{H.escape(state.get('current_position',''))}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">这一程目标</span>
        <span class="stat-value">{H.escape(state.get('current_goal',''))}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">能量</span>
        <span class="stat-value energy">{H.escape(str(state.get('energy','')))}/20</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">模式</span>
        <span class="stat-value">{'深夜低频' if state.get('night_mode') else '白天活跃'}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">上次汇报</span>
        <span class="stat-value">{H.escape(str(state.get('last_report_time','')))}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">最后更新</span>
        <span class="stat-value">{H.escape(str(state.get('last_update','')))}</span>
      </div>
    </div>
    <div class="leads">
      <h3>待追线索 · pending_leads</h3>
      <ol>
    """
    for lead in state.get("pending_leads", []):
        state_html += f"<li>{H.escape(lead)}</li>\n"
    state_html += "</ol></div>"

    legend_html = "".join(
        f'<span class="lg"><i style="background:{meta["color"]}"></i>{H.escape(d)}<em>{H.escape(meta["desc"])}</em></span>'
        for d, meta in DOMAINS.items())
    legend_html += (
        '<span class="lg edge"><i class="edge-dot sup"></i>补充</span>'
        '<span class="lg edge"><i class="edge-dot con"></i>矛盾</span>'
        '<span class="lg edge"><i class="edge-dot lone"></i>孤点</span>')

    # 节点/边 JS 数据
    js_nodes = json.dumps(nodes, ensure_ascii=False)
    js_edges = json.dumps(edges, ensure_ascii=False)
    js_lone = json.dumps(lone, ensure_ascii=False)
    js_domains = json.dumps({k: {"color": v["color"]} for k, v in DOMAINS.items()}, ensure_ascii=False)

    # 时间线（最新72步，可折叠卡片）
    tl = []
    total = len(entries)
    for idx, e in enumerate(entries[:72]):
        step_num = total - idx
        found = e["found"]
        found_brief = found[:120] + ("…" if len(found) > 120 else "")
        full_parts = []
        if e["saw"]:
            full_parts.append(f'<div class="tl-full-item"><span class="tl-full-label">我看了什么</span><div class="tl-full-text">{H.escape(e["saw"])}</div></div>')
        if e["found"]:
            full_parts.append(f'<div class="tl-full-item"><span class="tl-full-label">我发现了什么</span><div class="tl-full-text">{H.escape(e["found"])}</div></div>')
        if e["jump"]:
            full_parts.append(f'<div class="tl-full-item"><span class="tl-full-label">我跳到了哪里</span><div class="tl-full-text">{H.escape(e["jump"])}</div></div>')
        if e["judge"]:
            full_parts.append(f'<div class="tl-full-item"><span class="tl-full-label">我的判断</span><div class="tl-full-text">{H.escape(e["judge"])}</div></div>')
        full_html = "\n".join(full_parts)
        start_short = e["start"][:42] + ("…" if len(e["start"]) > 42 else "")
        angle_short = e["angle"][:22] + ("…" if len(e["angle"]) > 22 else "")
        tl.append(f"""
        <div class="tl-card" data-step="{step_num}">
          <div class="tl-card-head" onclick="toggleTrail(this)">
            <div class="tl-card-left">
              <span class="tl-step-num">#{step_num}</span>
              <span class="tl-card-time">{H.escape(e['time'])}</span>
            </div>
            <div class="tl-card-right">
              <span class="tl-card-start">{H.escape(start_short)}</span>
              <span class="tl-card-angle">{H.escape(angle_short)}</span>
              <span class="tl-card-toggle">▾</span>
            </div>
          </div>
          <div class="tl-card-brief">{H.escape(found_brief)}</div>
          <div class="tl-card-full" style="display:none">{full_html}</div>
        </div>""")
    tl_html = "\n".join(tl)

    # 汇报归档：时间线视图 + 类别视图
    if reports:
        # --- 时间线视图 ---
        tl_items = []
        for r in reports:
            cat_tags = "".join(
                f'<span class="rpt-cat" style="background:{DOMAINS[c]["color"]}22;color:{DOMAINS[c]["color"]};border-color:{DOMAINS[c]["color"]}55">{H.escape(c)}×{n}</span>'
                for c, n in sorted(r["cat_counts"].items(), key=lambda x: -x[1])
                if c in DOMAINS
            )
            findings_brief = "；".join(f'{f["idx"]}.{f["title"][:30]}' for f in r["findings"][:3])
            if len(r["findings"]) > 3:
                findings_brief += f" 等 {len(r['findings'])} 条"
            tl_items.append(f"""
            <div class="rpt-tl-row">
              <div class="rpt-tl-time">{H.escape(r['time'])}</div>
              <div class="rpt-tl-axis"><i></i></div>
              <div class="rpt-tl-body">
                <div class="rpt-tl-title" onclick="toggleReport(this)">{H.escape(r['title'])}</div>
                <div class="rpt-tl-meta">{len(r['findings'])} 条发现 · {cat_tags}</div>
                <div class="rpt-tl-brief">{H.escape(findings_brief)}</div>
                <div class="rpt-tl-full" style="display:none">{r['html']}</div>
              </div>
            </div>""")
        rep_timeline_html = "\n".join(tl_items)

        # --- 类别视图 ---
        # 按领域聚合所有发现
        cat_findings = {c: [] for c in DOMAINS}
        for r in reports:
            for f in r["findings"]:
                cat = f["category"] if f["category"] in cat_findings else "能力实证"
                cat_findings[cat].append({
                    "report_time": r["time"], "report_title": r["title"],
                    "idx": f["idx"], "title": f["title"],
                    "so_what": f["so_what"], "source": f["source"]
                })
        cat_sections = []
        for cat, items in cat_findings.items():
            if not items:
                continue
            color = DOMAINS[cat]["color"]
            items_html = ""
            for it in items:
                src_link = f'<a href="{it["source"]}" target="_blank" rel="noopener">来源</a>' if it["source"] else ""
                items_html += f"""
                <div class="cat-item">
                  <div class="cat-item-title">{it['idx']}. {H.escape(it['title'])}</div>
                  <div class="cat-item-meta">{H.escape(it['report_time'])} · {src_link}</div>
                  <div class="cat-item-sowhat">{H.escape(it['so_what'])}</div>
                </div>"""
            cat_sections.append(f"""
            <div class="cat-section">
              <h4 class="cat-header" style="border-left-color:{color}"><span style="color:{color}">{H.escape(cat)}</span> · {len(items)} 条<em>{H.escape(DOMAINS[cat]['desc'])}</em></h4>
              {items_html}
            </div>""")
        rep_category_html = "\n".join(cat_sections)
        rep_html = f"""
        <div class="rpt-tabs">
          <button class="rpt-tab active" onclick="switchRptTab('timeline', this)">📅 时间线</button>
          <button class="rpt-tab" onclick="switchRptTab('category', this)">🏷️ 按类别</button>
        </div>
        <div id="rpt-timeline" class="rpt-view active">{rep_timeline_html}</div>
        <div id="rpt-category" class="rpt-view">{rep_category_html}</div>
        """
    else:
        rep_html = '<p class="muted">暂无汇报归档。</p>'

    # 形状观察
    shapes_html = "".join(f"<li>{H.escape(s)}</li>" for s in shapes[-5:])

    # 数据时间
    data_time = state.get("last_update", "")

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rover 记忆地图 · 漫游日志</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root {{
  --bg:#0a0e14; --panel:#11161f; --panel2:#151c28; --line:#232c3a;
  --text:#e6edf3; --muted:#8b949e; --accent:#58a6ff;
  /* [优化 1] 四级来源标签颜色 */
  --l1:#7ee787; --l2:#58a6ff; --l3:#ffd58a; --l4:#ff7b72;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background:var(--bg); color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;
  line-height:1.65;
}}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 20px 80px; }}
header.hero {{
  padding:48px 0 28px; border-bottom:1px solid var(--line);
  display:flex; align-items:flex-end; justify-content:space-between; gap:20px; flex-wrap:wrap;
}}
.hero h1 {{ font-size:30px; font-weight:800; letter-spacing:.5px; }}
.hero h1 span {{ color:var(--accent); }}
.hero .sub {{ color:var(--muted); font-size:14px; margin-top:6px; max-width:640px; }}
.badge {{ display:inline-flex; align-items:center; gap:8px; background:var(--panel); border:1px solid var(--line);
  border-radius:999px; padding:8px 16px; font-size:13px; color:var(--muted); }}
.badge i {{ width:8px; height:8px; border-radius:50%; background:var(--accent); display:inline-block; }}
section {{ margin-top:44px; }}
h2.sec {{ font-size:20px; font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:10px; }}
h2.sec .dot {{ width:10px; height:10px; border-radius:2px; background:var(--accent); display:inline-block; }}
h2.sec small {{ color:var(--muted); font-weight:400; font-size:13px; }}
.stat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; margin-top:18px; }}
.stat-card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }}
.stat-label {{ display:block; font-size:12px; color:var(--muted); margin-bottom:6px; letter-spacing:1px; }}
.stat-value {{ font-size:14px; }}
.stat-value.energy {{ color:var(--accent); font-weight:700; }}
.leads {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 20px; margin-top:14px; }}
.leads h3 {{ font-size:14px; color:var(--muted); letter-spacing:1px; margin-bottom:10px; }}
.leads ol {{ padding-left:20px; }}
.leads li {{ font-size:13.5px; margin-bottom:6px; color:var(--text); }}
#map {{ width:100%; height:640px; background:var(--panel); border:1px solid var(--line); border-radius:14px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px; margin-top:14px; font-size:12.5px; color:var(--muted); }}
.legend .lg {{ display:inline-flex; align-items:center; gap:7px; }}
.legend .lg i {{ width:10px; height:10px; border-radius:3px; display:inline-block; }}
.legend .lg em {{ font-style:normal; color:#6e7681; margin-left:2px; }}
.legend .lg.edge i {{ width:16px; height:3px; border-radius:2px; }}
.edge-dot.sup {{ background:#7ee787; }}
.edge-dot.con {{ background:#ff7b72; }}
.edge-dot.lone {{ background:#8b949e; border:1px dashed #8b949e; height:6px !important; }}
.tl {{ margin-top:20px; }}
.tl-row {{ display:grid; grid-template-columns:56px 24px 1fr; gap:0; }}
.tl-time {{ padding:14px 0; text-align:right; font-variant-numeric:tabular-nums; color:var(--muted); font-size:13px; }}
.tl-axis {{ position:relative; }}
.tl-axis::before {{ content:""; position:absolute; left:50%; top:0; bottom:0; width:2px; background:var(--line); transform:translateX(-50%); }}
.tl-axis i {{ position:absolute; left:50%; top:22px; width:10px; height:10px; border-radius:50%;
  background:var(--accent); transform:translateX(-50%); box-shadow:0 0 0 4px rgba(88,166,255,.15); }}
.tl-body {{ padding:10px 0 18px 14px; }}
.tl-start {{ font-size:13.5px; font-weight:600; }}
.tl-angle {{ display:inline-block; margin-top:4px; font-size:12px; color:var(--muted);
  background:var(--panel2); border:1px solid var(--line); border-radius:6px; padding:2px 8px; }}
.tl-body p {{ margin-top:8px; font-size:13.5px; color:#c9d1d9; }}
/* 轨迹卡片（72步可折叠） */
.tl-toolbar {{ display:flex; align-items:center; gap:8px; margin:14px 0 12px; flex-wrap:wrap; }}
.tl-btn {{ background:var(--panel); border:1px solid var(--line); color:var(--muted);
  padding:6px 14px; border-radius:6px; font-size:12px; cursor:pointer; transition:all .2s; }}
.tl-btn:hover {{ border-color:var(--accent); color:var(--text); }}
.tl-count {{ font-size:11.5px; color:var(--muted); margin-left:auto; }}
.tl-card {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
  margin-bottom:8px; overflow:hidden; transition:border-color .2s, box-shadow .2s; }}
.tl-card:hover {{ border-color:#2d3a4f; box-shadow:0 2px 12px rgba(0,0,0,.2); }}
.tl-card-head {{ display:flex; justify-content:space-between; align-items:center;
  padding:10px 14px; cursor:pointer; user-select:none; gap:12px; }}
.tl-card-left {{ display:flex; align-items:center; gap:10px; flex-shrink:0; }}
.tl-step-num {{ font-size:11px; font-weight:700; color:var(--accent);
  background:rgba(88,166,255,.1); border-radius:4px; padding:2px 7px; letter-spacing:.5px; }}
.tl-card-time {{ font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tl-card-right {{ display:flex; align-items:center; gap:10px; min-width:0; flex:1; justify-content:flex-end; }}
.tl-card-start {{ font-size:13px; font-weight:600; color:var(--text); max-width:340px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.tl-card-angle {{ font-size:11px; color:var(--muted); background:var(--panel2);
  border:1px solid var(--line); border-radius:4px; padding:2px 7px; white-space:nowrap; flex-shrink:0; }}
.tl-card-toggle {{ font-size:11px; color:var(--muted); transition:transform .2s; flex-shrink:0; }}
.tl-card.open .tl-card-toggle {{ transform:rotate(180deg); }}
.tl-card-brief {{ padding:0 14px 10px; font-size:12.5px; color:#8b949e; line-height:1.65; }}
.tl-card.open .tl-card-brief {{ display:none; }}
.tl-card-full {{ padding:14px 16px; background:var(--panel2); border-top:1px solid var(--line); }}
.tl-full-item {{ margin-bottom:12px; }}
.tl-full-item:last-child {{ margin-bottom:0; }}
.tl-full-label {{ display:inline-block; font-size:11px; font-weight:700; color:var(--accent);
  margin-bottom:5px; letter-spacing:.8px; text-transform:uppercase; }}
.tl-full-text {{ font-size:12.5px; color:#c9d1d9; line-height:1.75; }}
/* [优化 1] 来源等级标签 */
.src-badge {{ display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; padding:2px 8px; border-radius:4px; letter-spacing:.5px; flex-shrink:0; }}
.src-badge::before {{ content:""; width:6px; height:6px; border-radius:50%; display:inline-block; }}
.src-badge.l1 {{ background:rgba(126,231,135,.12); color:var(--l1); border:1px solid rgba(126,231,135,.3); }}
.src-badge.l1::before {{ background:var(--l1); }}
.src-badge.l2 {{ background:rgba(88,166,255,.12); color:var(--l2); border:1px solid rgba(88,166,255,.3); }}
.src-badge.l2::before {{ background:var(--l2); }}
.src-badge.l3 {{ background:rgba(255,213,138,.12); color:var(--l3); border:1px solid rgba(255,213,138,.3); }}
.src-badge.l3::before {{ background:var(--l3); }}
.src-badge.l4 {{ background:rgba(255,123,114,.12); color:var(--l4); border:1px solid rgba(255,123,114,.3); }}
.src-badge.l4::before {{ background:var(--l4); }}
/* [优化 4] 时效标签 */
.time-badge {{ display:inline-block; font-size:10px; padding:1px 6px; border-radius:3px; margin-left:6px; flex-shrink:0; }}
.time-badge.new {{ background:rgba(126,231,135,.15); color:var(--l1); }}
.time-badge.recent {{ background:rgba(88,166,255,.15); color:var(--l2); }}
.time-badge.old {{ background:rgba(139,148,158,.15); color:var(--muted); }}
/* [优化 2] 单一来源警告 */
.single-src-warn {{ color:var(--l4); font-size:11px; margin-left:6px; font-weight:600; }}
/* [优化 5] 关于本页折叠区 */
.about-section {{ margin-top:44px; }}
.about-toggle {{ cursor:pointer; user-select:none; display:flex; align-items:center; gap:10px; padding:12px 0; }}
.about-toggle .arrow {{ transition:transform .2s; display:inline-block; font-size:14px; color:var(--muted); }}
.about-section.open .about-toggle .arrow {{ transform:rotate(90deg); }}
.about-content {{ display:none; margin-top:8px; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:20px 24px; }}
.about-section.open .about-content {{ display:block; }}
.about-content h4 {{ font-size:14px; color:var(--accent); margin:16px 0 8px; font-weight:700; }}
.about-content h4:first-child {{ margin-top:0; }}
.about-content p, .about-content li {{ font-size:13px; color:#c9d1d9; line-height:1.75; }}
.about-content ul {{ padding-left:20px; margin:8px 0; }}
.about-content .src-legend {{ display:flex; flex-wrap:wrap; gap:10px; margin:10px 0; }}
.about-content .src-legend span {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; }}
@media (max-width:640px) {{
  .tl-card-head {{ flex-direction:column; align-items:flex-start; gap:6px; }}
  .tl-card-right {{ width:100%; justify-content:space-between; }}
  .tl-card-start {{ max-width:200px; }}
  .tl-count {{ margin-left:0; width:100%; }}
}}
.report {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:24px 26px; margin-top:16px; }}
.report h3 {{ font-size:17px; margin-bottom:12px; color:var(--accent); }}
.report h2 {{ font-size:15px; margin:14px 0 6px; }}
.report h4 {{ font-size:14px; margin:12px 0 4px; color:#e6edf3; }}
.report p {{ font-size:13.8px; margin:6px 0; color:#c9d1d9; }}
.report ul {{ margin:6px 0 6px 4px; padding-left:20px; }}
.report li {{ font-size:13.8px; margin-bottom:8px; color:#c9d1d9; }}
.report a {{ color:var(--accent); text-decoration:none; word-break:break-all; }}
.report a:hover {{ text-decoration:underline; }}
.report strong {{ color:#e6edf3; }}
/* 汇报归档：tab 切换 */
.rpt-tabs {{ display:flex; gap:8px; margin:18px 0 14px; }}
.rpt-tab {{ background:var(--panel); border:1px solid var(--line); color:var(--muted);
  padding:8px 18px; border-radius:8px; font-size:13.5px; cursor:pointer; transition:all .2s; }}
.rpt-tab:hover {{ border-color:var(--accent); color:var(--text); }}
.rpt-tab.active {{ background:var(--accent); border-color:var(--accent); color:#0a0e14; font-weight:600; }}
.rpt-view {{ display:none; }}
.rpt-view.active {{ display:block; }}
/* 时间线视图 */
.rpt-tl-row {{ display:grid; grid-template-columns:120px 24px 1fr; gap:0; }}
.rpt-tl-time {{ padding:16px 8px 16px 0; text-align:right; font-variant-numeric:tabular-nums;
  color:var(--muted); font-size:12.5px; line-height:1.5; }}
.rpt-tl-axis {{ position:relative; }}
.rpt-tl-axis::before {{ content:""; position:absolute; left:50%; top:0; bottom:0; width:2px;
  background:var(--line); transform:translateX(-50%); }}
.rpt-tl-axis i {{ position:absolute; left:50%; top:22px; width:12px; height:12px; border-radius:50%;
  background:var(--accent); transform:translateX(-50%); box-shadow:0 0 0 4px rgba(88,166,255,.18); }}
.rpt-tl-body {{ padding:12px 0 20px 14px; }}
.rpt-tl-title {{ font-size:15px; font-weight:700; cursor:pointer; color:var(--text); }}
.rpt-tl-title:hover {{ color:var(--accent); }}
.rpt-tl-meta {{ margin-top:6px; font-size:12px; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
.rpt-cat {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px;
  border:1px solid; font-weight:500; }}
.rpt-tl-brief {{ margin-top:8px; font-size:13px; color:#8b949e; line-height:1.6; }}
.rpt-tl-full {{ margin-top:14px; background:var(--panel2); border:1px solid var(--line);
  border-radius:10px; padding:18px 20px; }}
.rpt-tl-full h2 {{ font-size:15px; margin:12px 0 6px; color:var(--accent); }}
.rpt-tl-full h3 {{ font-size:14px; margin:10px 0 4px; }}
.rpt-tl-full h4 {{ font-size:13.5px; margin:8px 0 4px; }}
.rpt-tl-full p {{ font-size:13px; margin:5px 0; color:#c9d1d9; }}
.rpt-tl-full ul {{ margin:5px 0; padding-left:18px; }}
.rpt-tl-full li {{ font-size:13px; margin-bottom:5px; color:#c9d1d9; }}
.rpt-tl-full a {{ color:var(--accent); word-break:break-all; }}
.rpt-tl-full strong {{ color:#e6edf3; }}
/* 类别视图 */
.cat-section {{ margin-bottom:22px; }}
.cat-header {{ font-size:15px; font-weight:700; padding:8px 14px; background:var(--panel);
  border:1px solid var(--line); border-left:3px solid; border-radius:8px; margin-bottom:10px;
  display:flex; align-items:center; gap:10px; }}
.cat-header em {{ font-style:normal; font-weight:400; font-size:12px; color:var(--muted); margin-left:auto; }}
.cat-item {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:12px 16px; margin-bottom:8px; }}
.cat-item-title {{ font-size:13.5px; font-weight:600; color:var(--text); }}
.cat-item-meta {{ margin-top:4px; font-size:11.5px; color:var(--muted); }}
.cat-item-meta a {{ color:var(--accent); text-decoration:none; }}
.cat-item-sowhat {{ margin-top:6px; font-size:12.5px; color:#8b949e; line-height:1.55; }}
@media (max-width:640px) {{
  .rpt-tl-row {{ grid-template-columns:80px 18px 1fr; }}
  .rpt-tl-time {{ font-size:11px; }}
}}
.shapes {{ display:flex; flex-direction:column; gap:10px; margin-top:14px; }}
.shapes li {{ list-style:none; background:var(--panel); border:1px solid var(--line);
  border-radius:10px; padding:12px 16px; font-size:13.5px; color:#c9d1d9; }}
.muted {{ color:var(--muted); }}
footer {{ margin-top:56px; padding-top:20px; border-top:1px solid var(--line); color:var(--muted); font-size:12.5px; }}
@media (max-width:640px) {{
  #map {{ height:520px; }}
  .tl-row {{ grid-template-columns:44px 18px 1fr; }}
  .hero h1 {{ font-size:24px; }}
  .report {{ padding:16px; }}
}}
</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <div>
    <h1>Rover <span>记忆地图</span></h1>
    <div class="sub">自主网络漫游 Agent · 探索轨迹与兴趣地图 · 数据快照 {H.escape(data_time)}</div>
  </div>
  <div class="badge"><i></i>持续漫游中 · 每 10 分钟一步</div>
</header>

{state_html}

<section>
  <h2 class="sec"><span class="dot"></span>记忆地图 <small>点 {len(nodes)} 个 · 连线 {len(edges)} 条 · 悬停看详情，拖拽可移动</small></h2>
  <div id="map"></div>
  <div class="legend">{legend_html}</div>
</section>

<section>
  <h2 class="sec"><span class="dot"></span>探索轨迹 <small>最新 {min(len(entries),72)} 步 · 点击卡片展开详情</small></h2>
  <div class="tl-toolbar">
    <button class="tl-btn" onclick="expandAllTrail()">全部展开</button>
    <button class="tl-btn" onclick="collapseAllTrail()">全部收起</button>
    <span class="tl-count">共 {len(entries)} 步，显示最新 {min(len(entries),72)} 步</span>
  </div>
  <div class="tl">{tl_html}</div>
</section>

<section>
  <h2 class="sec"><span class="dot"></span>地图形状观察</h2>
  <ul class="shapes">{shapes_html}</ul>
</section>

<section>
  <h2 class="sec"><span class="dot"></span>汇报归档 <small>{len(reports)} 篇</small></h2>
  {rep_html}
</section>

<!-- [优化 5] 关于本页折叠区 -->
<section class="about-section" id="about-section">
  <div class="about-toggle" onclick="toggleAbout()">
    <span class="arrow">▶</span>
    <h2 class="sec" style="margin:0"><span class="dot"></span>关于本页 <small>来源分级与可信度规则</small></h2>
  </div>
  <div class="about-content">
    <h4>一、来源分级规则（L1–L4）</h4>
    <div class="src-legend">
      <span><span class="src-badge l1">L1 一手</span> 政府公告、论文原文、公司官方博文/财报、官方仓库 README</span>
      <span><span class="src-badge l2">L2 权威转述</span> 新华社、央视、NEJM、Nature 等有编辑审核的转述</span>
      <span><span class="src-badge l3">L3 二手聚合</span> 聚合页、个人博客、社区转述</span>
      <span><span class="src-badge l4">L4 存疑</span> 链接失效、仅标题、AI 生成内容</span>
    </div>
    <h4>二、可信度判定标准</h4>
    <ul>
      <li>只有 L1 才能标"高"可信度；L2 标"中高"；L3 及以下不得标"高"。</li>
      <li>高影响数字若只有单一来源，必须标 ⚠️ 单一来源，待核实。</li>
      <li>原始链接失效时，显式标注"原始链接失效，当前为 L2 转述"，不使用"官方称"等暗示一手的措辞。</li>
      <li>每条结论强制显示原始链接（L1）和转述链接（L2/L3），两者独立判定等级。</li>
    </ul>
    <h4>三、时效标签</h4>
    <ul>
      <li><span class="time-badge new">新</span> 7 天内发布的内容</li>
      <li><span class="time-badge recent">近期</span> 30 天内发布的内容</li>
      <li><span class="time-badge old">旧闻</span> 更早的内容，须显示原始发布时间，避免与最新快照混淆</li>
    </ul>
    <h4>四、数据更新与免责声明</h4>
    <p>本页由 Rover 自动生成，每次汇报后运行 build_site.py 重建。数据快照时间：{H.escape(data_time)}。数据来源：memory.md（长期记忆点与连线）、trail.md（漫游轨迹）、state.json（运行状态）、reports/（汇报归档）。</p>
    <p>来源等级由 URL 域名自动判定，可能存在误判（如个人博客托管在 github.io 会被误判为 L1）。关键结论请以原始链接为准。本页仅作漫游记录与兴趣地图展示，不构成任何投资、医疗或法律建议。</p>
  </div>
</section>

<footer>由 Rover 自动生成 · 每次汇报后运行 build_site.py 重建本页 · 数据来自 memory.md / trail.md / state.json</footer>
</div>

<script>
var POINTS = {js_nodes};
var EDGES = {js_edges};
var LONE = {js_lone};
var DOMAINS = {js_domains};
var CATS = Object.keys(DOMAINS);

var chart = echarts.init(document.getElementById('map'));
var option = {{
  tooltip: {{
    backgroundColor: '#11161f', borderColor: '#232c3a', textStyle: {{ color: '#e6edf3', fontSize: 13 }},
    formatter: function(p) {{
      if (p.dataType === 'edge') {{
        var t = p.data.type === '矛盾' ? '矛盾' : (p.data.type === '延续' ? '延续' : '补充');
        return '<b>点' + p.data.source + ' → 点' + p.data.target + '</b>（' + t + '）<br>' + (p.data.note || '');
      }}
      var b = p.data.brief || '';
      return '<b>' + p.data.name + '</b> · ' + (p.data.category || '') + '<br><span style="color:#8b949e">' + b + '</span>';
    }}
  }},
  legend: [{{ data: CATS, textStyle: {{ color: '#8b949e' }}, top: 10, type: 'scroll' }}],
  series: [{{
    type: 'graph', layout: 'force',
    roam: true, draggable: true,
    label: {{ show: true, position: 'bottom', color: '#c9d1d9', fontSize: 11, formatter: function(p) {{ return p.name.length > 6 ? p.name.slice(0,6) + '…' : p.name; }} }},
    edgeSymbol: ['none', 'arrow'], edgeSymbolSize: [0, 7],
    force: {{ repulsion: 320, edgeLength: [70, 160], gravity: 0.08 }},
    lineStyle: {{ width: 1.4, curveness: 0.12, opacity: 0.85 }},
    emphasis: {{ focus: 'adjacency', lineStyle: {{ width: 3 }} }},
    categories: CATS.map(function(c) {{ return {{ name: c, itemStyle: {{ color: DOMAINS[c].color }} }}; }}),
    data: POINTS.map(function(n) {{
      return {{
        id: n.id, name: n.name, value: n.value, category: n.category,
        symbolSize: n.symbolSize, brief: n.brief,
        itemStyle: {{ color: (DOMAINS[n.category] ? DOMAINS[n.category].color : '#6e7681') }}
      }};
    }}),
    links: EDGES.map(function(e) {{
      var col = e.type === '矛盾' ? '#ff7b72' : (e.type === '延续' ? '#7ee787' : '#8b949e');
      return {{
        source: e.source, target: e.target,
        lineStyle: {{ color: col, type: e.type === '矛盾' ? 'dashed' : 'solid' }},
        type: e.type, note: e.note
      }};
    }})
  }}]
}};
chart.setOption(option);
window.addEventListener('resize', function() {{ chart.resize(); }});

// 汇报归档 tab 切换
function switchRptTab(view, btn) {{
  document.querySelectorAll('.rpt-tab').forEach(function(b) {{ b.classList.remove('active'); }});
  document.querySelectorAll('.rpt-view').forEach(function(v) {{ v.classList.remove('active'); }});
  btn.classList.add('active');
  document.getElementById('rpt-' + view).classList.add('active');
}}
// 展开/收起汇报全文
function toggleReport(el) {{
  var full = el.parentElement.querySelector('.rpt-tl-full');
  if (full.style.display === 'none') {{
    full.style.display = 'block';
    el.style.color = 'var(--accent)';
  }} else {{
    full.style.display = 'none';
    el.style.color = '';
  }}
}}
// 轨迹卡片展开/收起
function toggleTrail(el) {{
  var card = el.closest('.tl-card');
  var full = card.querySelector('.tl-card-full');
  if (full.style.display === 'none') {{
    full.style.display = 'block';
    card.classList.add('open');
  }} else {{
    full.style.display = 'none';
    card.classList.remove('open');
  }}
}}
function expandAllTrail() {{
  document.querySelectorAll('.tl-card').forEach(function(c) {{
    c.querySelector('.tl-card-full').style.display = 'block';
    c.classList.add('open');
  }});
}}
function collapseAllTrail() {{
  document.querySelectorAll('.tl-card').forEach(function(c) {{
    c.querySelector('.tl-card-full').style.display = 'none';
    c.classList.remove('open');
  }});
}}
// [优化 1] 来源等级判定：根据URL域名判断L1-L4
function classifySource(url) {{
  if (!url) return 'l3';
  var u = url.toLowerCase();
  // L1 一手官方：政府、论文原文、公司官方、官方仓库
  var l1 = ['.gov', 'nejm.org', 'nature.com', 'science.org', 'pnas.org', 'arxiv.org',
    'github.com/babylm-org', 'github.com/facebookresearch', 'github.com/facebook',
    'github.com/openai', 'github.com/deepmind', 'ir.intelliatx.com', 'intelligence.gov',
    'nasa.gov', 'esa.int', 'cnsa.gov.cn', 'hnswwkgyjy.cn', 'kaogu.cn',
    'chinese-babylm.github.io', 'openai.com', 'anthropic.com', 'deepmind.google',
    'ai.meta.com', 'about.fb.com', 'blog.google', 'research.google',
    'sec.gov', 'fda.gov', 'who.int', 'cdc.gov', 'worldbank.org', 'imf.org',
    'stats.gov.cn', 'pboc.gov.cn', 'csrc.gov.cn', 'cbirc.gov.cn'];
  // L2 权威媒体转述：有编辑审核的媒体
  var l2 = ['xinhuanet.com', 'news.cn', 'cctv.com', 'people.com.cn', 'reuters.com',
    'apnews.com', 'bbc.com', 'nytimes.com', 'washingtonpost.com', 'economist.com',
    'ft.com', 'wsj.com', 'bloomberg.com', 'theguardian.com', 'scientificamerican.com',
    'quantamagazine.org', 'technologyreview.com', 'ieee.org', 'acm.org',
    'caixin.com', 'yicai.com', '21jingji.com', '36kr.com', 'jiemian.com',
    'thepaper.cn', 'zhihu.com', 'mp.weixin.qq.com'];
  // L4 存疑/未核实：链接失效、仅标题、AI生成
  var l4 = ['web.archive.org', 'webcache.googleusercontent.com'];
  for (var i = 0; i < l4.length; i++) if (u.indexOf(l4[i]) >= 0) return 'l4';
  for (var i = 0; i < l1.length; i++) if (u.indexOf(l1[i]) >= 0) return 'l1';
  for (var i = 0; i < l2.length; i++) if (u.indexOf(l2[i]) >= 0) return 'l2';
  return 'l3'; // 默认L3二手聚合/自媒体
}}
// [优化 4] 时效标签判定
function classifyTime(timeStr) {{
  if (!timeStr) return '';
  var now = new Date();
  var t = new Date(timeStr.replace(/-/g, '/'));
  if (isNaN(t.getTime())) return '';
  var diffDays = (now - t) / (1000 * 60 * 60 * 24);
  if (diffDays <= 7) return '<span class="time-badge new">新</span>';
  if (diffDays <= 30) return '<span class="time-badge recent">近期</span>';
  return '<span class="time-badge old">旧闻 ' + timeStr.slice(0,10) + '</span>';
}}
// [优化 1+4] 给轨迹卡片添加来源标签和时效标签
function annotateTrailCards() {{
  document.querySelectorAll('.tl-card').forEach(function(card) {{
    var head = card.querySelector('.tl-card-right');
    if (!head || head.querySelector('.src-badge')) return;
    // 从卡片全文中提取URL
    var full = card.querySelector('.tl-card-full');
    var url = '';
    if (full) {{
      var m = full.innerHTML.match(/https?:\/\/[^\s<>"']+/);
      if (m) url = m[0];
    }}
    var level = classifySource(url);
    var label = level === 'l1' ? 'L1 一手' : level === 'l2' ? 'L2 权威转述' : level === 'l3' ? 'L3 二手聚合' : 'L4 存疑';
    var badge = '<span class="src-badge ' + level + '">' + label + '</span>';
    // 时效标签
    var timeEl = card.querySelector('.tl-card-time');
    var timeBadge = '';
    if (timeEl) timeBadge = classifyTime(timeEl.textContent);
    head.insertAdjacentHTML('afterbegin', badge + timeBadge);
  }});
}}
// [优化 1] 给汇报条目添加来源标签
function annotateReports() {{
  document.querySelectorAll('.rpt-tl-body, .cat-item').forEach(function(el) {{
    if (el.querySelector('.src-badge')) return;
    var links = el.querySelectorAll('a[href]');
    var url = '';
    for (var i = 0; i < links.length; i++) {{
      if (links[i].href && links[i].href.indexOf('http') >= 0) {{ url = links[i].href; break; }}
    }}
    if (!url) return;
    var level = classifySource(url);
    var label = level === 'l1' ? 'L1 一手' : level === 'l2' ? 'L2 权威转述' : level === 'l3' ? 'L3 二手聚合' : 'L4 存疑';
    var badge = '<span class="src-badge ' + level + '" style="margin-right:6px">' + label + '</span>';
    var meta = el.querySelector('.rpt-tl-meta, .cat-item-meta');
    if (meta) meta.insertAdjacentHTML('afterbegin', badge);
  }});
}}
// [优化 5] 关于本页折叠区切换
function toggleAbout() {{
  document.getElementById('about-section').classList.toggle('open');
}}
// 页面加载后自动标注
document.addEventListener('DOMContentLoaded', function() {{
  annotateTrailCards();
  annotateReports();
}});
</script>
</body>
</html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return OUT

def main():
    state = load_state()
    points, links, lone, shapes = parse_memory()
    entries = parse_trail()
    reports = load_reports()
    nodes, edges, lone2 = build_graph(points, links, lone)
    out = render(state, points, links, lone2, shapes, entries, reports, nodes, edges)
    print(f"OK -> {out}")
    print(f"points={len(points)} links={len(links)} lone={len(lone)} entries={len(entries)} reports={len(reports)}")

if __name__ == "__main__":
    main()
