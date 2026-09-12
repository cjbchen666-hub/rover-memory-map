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
    "生物基因": {"ids": {33, 40}, "color": "#ffa657", "desc": "CRISPR 基因编辑、体内编辑、儿童伦理"},
    "认知科学": {"ids": {36, 37, 38}, "color": "#bc8cff", "desc": "BabyLM、fMRI 神经对齐、视觉错觉机制"},
    "社会心理": {"ids": {39}, "color": "#f0883e", "desc": "评论区毒化、差异化动机、群体行为"},
}
ID2DOMAIN = {i: d for d, meta in DOMAINS.items() for i in meta["ids"]}

# ---------- 汇报发现的领域分类关键词 ----------
CATEGORY_KEYWORDS = {
    "能力实证": ["模型", "训练", "优化", "nanogpt", "agent", "科研", "复现", "靶场", "能力", "参数", "loss", "gpt", "claude", "fable", "opus", "kimi", "deepseek", "glm", "grok", "自主", "改进", "算法", "算力", "token"],
    "安全治理": ["pacing", "分级", "安全", "护栏", "astra", "daybreak", "aisi", "网络安全", "preparedness", "critical", "漏洞", "exploit", "攻击", "网安", "防御", "风险", "监管", "发布", "密钥", "bedrock"],
    "社会结构": ["银行", "劳动力", "就业", "组织", "中层", "雇佣", "数字员工", "工时", "裁员", "岗位", "管理", "企业", "公司", "创业", "受益", "分配", "经济", "金融", "行业"],
    "极限工程": ["桥", "悬索", "cfrp", "材料", "工程", "墨西拿", "主缆", "斜拉", "跨度", "钢缆", "基建", "建筑", "结构"],
    "天文考古": ["火星", "天文", "chandra", "fast", "射电暴", "x 射线", "x射线", "星系", "太空", "样本", "漫游车", "frb", "超新星", "宇宙", "望远镜", "观测", "nasa", "天问", "毅力", "天体", "黑洞", "中子星"],
    "生物基因": ["crispr", "基因", "编辑", "治疗", "临床", "dna", "rna", "蛋白", "细胞", "疗法", "输注", "治愈", "遗传", "罕见病"],
    "认知科学": ["认知", "大脑", "神经", "fMRI", "fmri", "脑", "心理", "语言", "学习", "模型", "对齐", "错觉", "视觉"],
    "社会心理": ["评论", "群体", "社会", "心理", "动机", "行为", "愤怒", "毒化", "消极", "积极", "差异化"],
}

def classify_finding(title, body):
    text = (title + " " + body).lower()
    scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in kws if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "能力实证"

def parse_report_findings(raw):
    findings = []
    pattern = re.compile(r"\*\*\[\s*(\d+)\.\s*(.+?)\s*\]\*\*(.*?)(?=\n\*\*\[\s*\d+\.|\n### |\Z)", re.S)
    for m in pattern.finditer(raw):
        idx = int(m.group(1))
        title = m.group(2).strip()
        body = m.group(3).strip()
        category = classify_finding(title, body)
        src_m = re.search(r"来源[：:]\s*(https?://\S+)", body)
        source = src_m.group(1) if src_m else ""
        so_m = re.search(r"所以呢[：:]\s*(.+?)(?=\n- |\Z)", body, re.S)
        so_what = re.sub(r"\s+", " ", so_m.group(1)).strip()[:120] if so_m else ""
        findings.append({"idx": idx, "title": title, "body": body, "category": category, "source": source, "so_what": so_what})
    return findings

def load_state():
    p = os.path.join(ROVER_DIR, "state.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def parse_memory():
    p = os.path.join(ROVER_DIR, "memory.md")
    text = open(p, encoding="utf-8").read()
    points = {}
    for m in re.finditer(r"\[点 (\d+)\]\s*((?:.|\n)*?)(?=\n\[点 |\n## )", text):
        pid = int(m.group(1))
        body = re.sub(r"\s+", " ", m.group(2)).strip()
        points[pid] = body
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
    shapes = []
    parts = text.split("## 地图形状观察")
    for part in parts[1:]:
        s = re.sub(r"\s+", " ", part).strip()
        if s:
            shapes.append(s)
    return points, links, lone, shapes

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
        entries.append({"time": t, "start": start, "angle": angle, "saw": grab("我看了什么"), "found": grab("我发现了什么"), "jump": grab("我跳到了哪里"), "judge": grab("我的判断")})
    return entries

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
                tm = re.match(r"(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})", fn)
                time_str = f"{tm.group(1)} {tm.group(2)}:{tm.group(3)}" if tm else fn
                findings = parse_report_findings(raw)
                cat_counts = {}
                for f in findings:
                    cat_counts[f["category"]] = cat_counts.get(f["category"], 0) + 1
                reports.append({"file": fn, "title": title, "time": time_str, "html": md_to_html(raw), "findings": findings, "cat_counts": cat_counts})
    reports.sort(key=lambda r: r["file"], reverse=True)
    return reports

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
        nodes.append({"id": pid, "name": label, "value": degrees.get(pid, 0) + 1, "category": d, "symbolSize": 18 + min(degrees.get(pid, 0) * 3, 26), "brief": H.escape(brief)})
    edges = []
    ext_count = 0
    for l in links:
        if "dst" in l and l["dst"] in points:
            edges.append({"source": l["src"], "target": l["dst"], "type": l["type"], "note": H.escape(l["note"])})
        elif "dst_text" in l:
            ext_count += 1
            ext_id = f"ext-{ext_count}"
            name = l["dst_text"].split("（")[0][:12]
            nodes.append({"id": ext_id, "name": name, "value": 1, "category": "外部", "symbolSize": 14, "brief": H.escape(l["dst_text"][:60])})
            edges.append({"source": l["src"], "target": ext_id, "type": l["type"], "note": H.escape(l["note"])})
    return nodes, edges, lone

def render(state, points, links, lone, shapes, entries, reports, nodes, edges):
    state_html = '<div class="stat-grid">'
    for label, key in [("当前位置", "current_position"), ("这一程目标", "current_goal"), ("能量", "energy"), ("模式", "night_mode"), ("上次汇报", "last_report_time"), ("最后更新", "last_update")]:
        val = state.get(key, "")
        if key == "energy": val = f"{val}/20"
        elif key == "night_mode": val = "深夜低频" if val else "白天活跃"
        state_html += f'<div class="stat-card"><span class="stat-label">{label}</span><span class="stat-value">{H.escape(str(val))}</span></div>'
    state_html += '</div><div class="leads"><h3>待追线索 · pending_leads</h3><ol>'
    for lead in state.get("pending_leads", []):
        state_html += f"<li>{H.escape(lead)}</li>\n"
    state_html += "</ol></div>"

    legend_html = "".join(f'<span class="lg"><i style="background:{meta["color"]}"></i>{H.escape(d)}<em>{H.escape(meta["desc"])}</em></span>' for d, meta in DOMAINS.items())
    legend_html += '<span class="lg edge"><i class="edge-dot sup"></i>补充</span><span class="lg edge"><i class="edge-dot con"></i>矛盾</span><span class="lg edge"><i class="edge-dot lone"></i>孤点</span>'

    js_nodes = json.dumps(nodes, ensure_ascii=False)
    js_edges = json.dumps(edges, ensure_ascii=False)
    js_lone = json.dumps(lone, ensure_ascii=False)
    js_domains = json.dumps({k: {"color": v["color"]} for k, v in DOMAINS.items()}, ensure_ascii=False)

    tl = []
    total = len(entries)
    for idx, e in enumerate(entries[:72]):
        step_num = total - idx
        found = e["found"]
        found_brief = found[:120] + ("…" if len(found) > 120 else "")
        full_parts = []
        for label, key in [("我看了什么", "saw"), ("我发现了什么", "found"), ("我跳到了哪里", "jump"), ("我的判断", "judge")]:
            if e[key]:
                full_parts.append(f'<div class="tl-full-item"><span class="tl-full-label">{label}</span><div class="tl-full-text">{H.escape(e[key])}</div></div>')
        full_html = "\n".join(full_parts)
        start_short = e["start"][:42] + ("…" if len(e["start"]) > 42 else "")
        angle_short = e["angle"][:22] + ("…" if len(e["angle"]) > 22 else "")
        tl.append(f'''<div class="tl-card" data-step="{step_num}"><div class="tl-card-head" onclick="toggleTrail(this)"><div class="tl-card-left"><span class="tl-step-num">#{step_num}</span><span class="tl-card-time">{H.escape(e['time'])}</span></div><div class="tl-card-right"><span class="tl-card-start">{H.escape(start_short)}</span><span class="tl-card-angle">{H.escape(angle_short)}</span><span class="tl-card-toggle">▾</span></div></div><div class="tl-card-brief">{H.escape(found_brief)}</div><div class="tl-card-full" style="display:none">{full_html}</div></div>''')
    tl_html = "\n".join(tl)

    if reports:
        tl_items = []
        for r in reports:
            cat_tags = "".join(f'<span class="rpt-cat" style="background:{DOMAINS[c]["color"]}22;color:{DOMAINS[c]["color"]};border-color:{DOMAINS[c]["color"]}55">{H.escape(c)}×{n}</span>' for c, n in sorted(r["cat_counts"].items(), key=lambda x: -x[1]) if c in DOMAINS)
            findings_brief = "；".join(f'{f["idx"]}.{f["title"][:30]}' for f in r["findings"][:3])
            if len(r["findings"]) > 3: findings_brief += f" 等 {len(r['findings'])} 条"
            tl_items.append(f'''<div class="rpt-tl-row"><div class="rpt-tl-time">{H.escape(r['time'])}</div><div class="rpt-tl-axis"><i></i></div><div class="rpt-tl-body"><div class="rpt-tl-title" onclick="toggleReport(this)">{H.escape(r['title'])}</div><div class="rpt-tl-meta">{len(r['findings'])} 条发现 · {cat_tags}</div><div class="rpt-tl-brief">{H.escape(findings_brief)}</div><div class="rpt-tl-full" style="display:none">{r['html']}</div></div></div>''')
        rep_timeline_html = "\n".join(tl_items)
        cat_findings = {c: [] for c in DOMAINS}
        for r in reports:
            for f in r["findings"]:
                cat = f["category"] if f["category"] in cat_findings else "能力实证"
                cat_findings[cat].append({"report_time": r["time"], "report_title": r["title"], "idx": f["idx"], "title": f["title"], "so_what": f["so_what"], "source": f["source"]})
        cat_sections = []
        for cat, items in cat_findings.items():
            if not items: continue
            color = DOMAINS[cat]["color"]
            items_html = ""
            for it in items:
                src_link = f'<a href="{it["source"]}" target="_blank" rel="noopener">来源</a>' if it["source"] else ""
                items_html += f'''<div class="cat-item"><div class="cat-item-title">{it['idx']}. {H.escape(it['title'])}</div><div class="cat-item-meta">{H.escape(it['report_time'])} · {src_link}</div><div class="cat-item-sowhat">{H.escape(it['so_what'])}</div></div>'''
            cat_sections.append(f'''<div class="cat-section"><h4 class="cat-header" style="border-left-color:{color}"><span style="color:{color}">{H.escape(cat)}</span> · {len(items)} 条<em>{H.escape(DOMAINS[cat]['desc'])}</em></h4>{items_html}</div>''')
        rep_category_html = "\n".join(cat_sections)
        rep_html = f'''<div class="rpt-tabs"><button class="rpt-tab active" onclick="switchRptTab('timeline', this)">📅 时间线</button><button class="rpt-tab" onclick="switchRptTab('category', this)">🏷️ 按类别</button></div><div id="rpt-timeline" class="rpt-view active">{rep_timeline_html}</div><div id="rpt-category" class="rpt-view">{rep_category_html}</div>'''
    else:
        rep_html = '<p class="muted">暂无汇报归档。</p>'

    shapes_html = "".join(f"<li>{H.escape(s)}</li>" for s in shapes[-5:])
    data_time = state.get("last_update", "")

    html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rover 记忆地图 · 漫游日志</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root {{ --bg:#0a0e14; --panel:#11161f; --panel2:#151c28; --line:#232c3a; --text:#e6edf3; --muted:#8b949e; --accent:#58a6ff; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif; line-height:1.65; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 20px 80px; }}
header.hero {{ padding:48px 0 28px; border-bottom:1px solid var(--line); display:flex; align-items:flex-end; justify-content:space-between; gap:20px; flex-wrap:wrap; }}
.hero h1 {{ font-size:30px; font-weight:800; letter-spacing:.5px; }}
.hero h1 span {{ color:var(--accent); }}
.hero .sub {{ color:var(--muted); font-size:14px; margin-top:6px; max-width:640px; }}
.badge {{ display:inline-flex; align-items:center; gap:8px; background:var(--panel); border:1px solid var(--line); border-radius:999px; padding:8px 16px; font-size:13px; color:var(--muted); }}
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
.tl-toolbar {{ display:flex; align-items:center; gap:8px; margin:14px 0 12px; flex-wrap:wrap; }}
.tl-btn {{ background:var(--panel); border:1px solid var(--line); color:var(--muted); padding:6px 14px; border-radius:6px; font-size:12px; cursor:pointer; transition:all .2s; }}
.tl-btn:hover {{ border-color:var(--accent); color:var(--text); }}
.tl-count {{ font-size:11.5px; color:var(--muted); margin-left:auto; }}
.tl-card {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; margin-bottom:8px; overflow:hidden; transition:border-color .2s, box-shadow .2s; }}
.tl-card:hover {{ border-color:#2d3a4f; box-shadow:0 2px 12px rgba(0,0,0,.2); }}
.tl-card-head {{ display:flex; justify-content:space-between; align-items:center; padding:10px 14px; cursor:pointer; user-select:none; gap:12px; }}
.tl-card-left {{ display:flex; align-items:center; gap:10px; flex-shrink:0; }}
.tl-step-num {{ font-size:11px; font-weight:700; color:var(--accent); background:rgba(88,166,255,.1); border-radius:4px; padding:2px 7px; letter-spacing:.5px; }}
.tl-card-time {{ font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tl-card-right {{ display:flex; align-items:center; gap:10px; min-width:0; flex:1; justify-content:flex-end; }}
.tl-card-start {{ font-size:13px; font-weight:600; color:var(--text); max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.tl-card-angle {{ font-size:11px; color:var(--muted); background:var(--panel2); border:1px solid var(--line); border-radius:4px; padding:2px 7px; white-space:nowrap; flex-shrink:0; }}
.tl-card-toggle {{ font-size:11px; color:var(--muted); transition:transform .2s; flex-shrink:0; }}
.tl-card.open .tl-card-toggle {{ transform:rotate(180deg); }}
.tl-card-brief {{ padding:0 14px 10px; font-size:12.5px; color:#8b949e; line-height:1.65; }}
.tl-card.open .tl-card-brief {{ display:none; }}
.tl-card-full {{ padding:14px 16px; background:var(--panel2); border-top:1px solid var(--line); }}
.tl-full-item {{ margin-bottom:12px; }}
.tl-full-item:last-child {{ margin-bottom:0; }}
.tl-full-label {{ display:inline-block; font-size:11px; font-weight:700; color:var(--accent); margin-bottom:5px; letter-spacing:.8px; text-transform:uppercase; }}
.tl-full-text {{ font-size:12.5px; color:#c9d1d9; line-height:1.75; }}
@media (max-width:640px) {{ .tl-card-head {{ flex-direction:column; align-items:flex-start; gap:6px; }} .tl-card-right {{ width:100%; justify-content:space-between; }} .tl-card-start {{ max-width:200px; }} .tl-count {{ margin-left:0; width:100%; }} }}
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
.rpt-tabs {{ display:flex; gap:8px; margin:18px 0 14px; }}
.rpt-tab {{ background:var(--panel); border:1px solid var(--line); color:var(--muted); padding:8px 18px; border-radius:8px; font-size:13.5px; cursor:pointer; transition:all .2s; }}
.rpt-tab:hover {{ border-color:var(--accent); color:var(--text); }}
.rpt-tab.active {{ background:var(--accent); border-color:var(--accent); color:#0a0e14; font-weight:600; }}
.rpt-view {{ display:none; }}
.rpt-view.active {{ display:block; }}
.rpt-tl-row {{ display:grid; grid-template-columns:120px 24px 1fr; gap:0; }}
.rpt-tl-time {{ padding:16px 8px 16px 0; text-align:right; font-variant-numeric:tabular-nums; color:var(--muted); font-size:12.5px; line-height:1.5; }}
.rpt-tl-axis {{ position:relative; }}
.rpt-tl-axis::before {{ content:""; position:absolute; left:50%; top:0; bottom:0; width:2px; background:var(--line); transform:translateX(-50%); }}
.rpt-tl-axis i {{ position:absolute; left:50%; top:22px; width:12px; height:12px; border-radius:50%; background:var(--accent); transform:translateX(-50%); box-shadow:0 0 0 4px rgba(88,166,255,.18); }}
.rpt-tl-body {{ padding:12px 0 20px 14px; }}
.rpt-tl-title {{ font-size:15px; font-weight:700; cursor:pointer; color:var(--text); }}
.rpt-tl-title:hover {{ color:var(--accent); }}
.rpt-tl-meta {{ margin-top:6px; font-size:12px; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
.rpt-cat {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; border:1px solid; font-weight:500; }}
.rpt-tl-brief {{ margin-top:8px; font-size:13px; color:#8b949e; line-height:1.6; }}
.rpt-tl-full {{ margin-top:14px; background:var(--panel2); border:1px solid var(--line); border-radius:10px; padding:18px 20px; }}
.rpt-tl-full h2 {{ font-size:15px; margin:12px 0 6px; color:var(--accent); }}
.rpt-tl-full h3 {{ font-size:14px; margin:10px 0 4px; }}
.rpt-tl-full h4 {{ font-size:13.5px; margin:8px 0 4px; }}
.rpt-tl-full p {{ font-size:13px; margin:5px 0; color:#c9d1d9; }}
.rpt-tl-full ul {{ margin:5px 0; padding-left:18px; }}
.rpt-tl-full li {{ font-size:13px; margin-bottom:5px; color:#c9d1d9; }}
.rpt-tl-full a {{ color:var(--accent); word-break:break-all; }}
.rpt-tl-full strong {{ color:#e6edf3; }}
.cat-section {{ margin-bottom:22px; }}
.cat-header {{ font-size:15px; font-weight:700; padding:8px 14px; background:var(--panel); border:1px solid var(--line); border-left:3px solid; border-radius:8px; margin-bottom:10px; display:flex; align-items:center; gap:10px; }}
.cat-header em {{ font-style:normal; font-weight:400; font-size:12px; color:var(--muted); margin-left:auto; }}
.cat-item {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin-bottom:8px; }}
.cat-item-title {{ font-size:13.5px; font-weight:600; color:var(--text); }}
.cat-item-meta {{ margin-top:4px; font-size:11.5px; color:var(--muted); }}
.cat-item-meta a {{ color:var(--accent); text-decoration:none; }}
.cat-item-sowhat {{ margin-top:6px; font-size:12.5px; color:#8b949e; line-height:1.55; }}
@media (max-width:640px) {{ .rpt-tl-row {{ grid-template-columns:80px 18px 1fr; }} .rpt-tl-time {{ font-size:11px; }} }}
.shapes {{ display:flex; flex-direction:column; gap:10px; margin-top:14px; }}
.shapes li {{ list-style:none; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 16px; font-size:13.5px; color:#c9d1d9; }}
.muted {{ color:var(--muted); }}
footer {{ margin-top:56px; padding-top:20px; border-top:1px solid var(--line); color:var(--muted); font-size:12.5px; }}
@media (max-width:640px) {{ #map {{ height:520px; }} .hero h1 {{ font-size:24px; }} .report {{ padding:16px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header class="hero"><div><h1>Rover <span>记忆地图</span></h1><div class="sub">自主网络漫游 Agent · 探索轨迹与兴趣地图 · 数据快照 {H.escape(data_time)}</div></div><div class="badge"><i></i>持续漫游中 · 每 10 分钟一步</div></header>
{state_html}
<section><h2 class="sec"><span class="dot"></span>记忆地图 <small>点 {len(nodes)} 个 · 连线 {len(edges)} 条 · 悬停看详情，拖拽可移动</small></h2><div id="map"></div><div class="legend">{legend_html}</div></section>
<section><h2 class="sec"><span class="dot"></span>探索轨迹 <small>最新 {min(len(entries),72)} 步 · 点击卡片展开详情</small></h2><div class="tl-toolbar"><button class="tl-btn" onclick="expandAllTrail()">全部展开</button><button class="tl-btn" onclick="collapseAllTrail()">全部收起</button><span class="tl-count">共 {len(entries)} 步，显示最新 {min(len(entries),72)} 步</span></div><div class="tl">{tl_html}</div></section>
<section><h2 class="sec"><span class="dot"></span>地图形状观察</h2><ul class="shapes">{shapes_html}</ul></section>
<section><h2 class="sec"><span class="dot"></span>汇报归档 <small>{len(reports)} 篇</small></h2>{rep_html}</section>
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
  tooltip: {{ backgroundColor: '#11161f', borderColor: '#232c3a', textStyle: {{ color: '#e6edf3', fontSize: 13 }}, formatter: function(p) {{ if (p.dataType === 'edge') {{ var t = p.data.type === '矛盾' ? '矛盾' : (p.data.type === '延续' ? '延续' : '补充'); return '<b>点' + p.data.source + ' → 点' + p.data.target + '</b>（' + t + '）<br>' + (p.data.note || ''); }} var b = p.data.brief || ''; return '<b>' + p.data.name + '</b> · ' + (p.data.category || '') + '<br><span style="color:#8b949e">' + b + '</span>'; }} }},
  legend: [{{ data: CATS, textStyle: {{ color: '#8b949e' }}, top: 10, type: 'scroll' }}],
  series: [{{ type: 'graph', layout: 'force', roam: true, draggable: true, label: {{ show: true, position: 'bottom', color: '#c9d1d9', fontSize: 11, formatter: function(p) {{ return p.name.length > 6 ? p.name.slice(0,6) + '…' : p.name; }} }}, edgeSymbol: ['none', 'arrow'], edgeSymbolSize: [0, 7], force: {{ repulsion: 320, edgeLength: [70, 160], gravity: 0.08 }}, lineStyle: {{ width: 1.4, curveness: 0.12, opacity: 0.85 }}, emphasis: {{ focus: 'adjacency', lineStyle: {{ width: 3 }} }}, categories: CATS.map(function(c) {{ return {{ name: c, itemStyle: {{ color: DOMAINS[c].color }} }}; }}), data: POINTS.map(function(n) {{ return {{ id: n.id, name: n.name, value: n.value, category: n.category, symbolSize: n.symbolSize, brief: n.brief, itemStyle: {{ color: (DOMAINS[n.category] ? DOMAINS[n.category].color : '#6e7681') }} }}; }}), links: EDGES.map(function(e) {{ var col = e.type === '矛盾' ? '#ff7b72' : (e.type === '延续' ? '#7ee787' : '#8b949e'); return {{ source: e.source, target: e.target, lineStyle: {{ color: col, type: e.type === '矛盾' ? 'dashed' : 'solid' }}, type: e.type, note: e.note }}; }}) }}]
}};
chart.setOption(option);
window.addEventListener('resize', function() {{ chart.resize(); }});
function switchRptTab(view, btn) {{ document.querySelectorAll('.rpt-tab').forEach(function(b) {{ b.classList.remove('active'); }}); document.querySelectorAll('.rpt-view').forEach(function(v) {{ v.classList.remove('active'); }}); btn.classList.add('active'); document.getElementById('rpt-' + view).classList.add('active'); }}
function toggleReport(el) {{ var full = el.parentElement.querySelector('.rpt-tl-full'); if (full.style.display === 'none') {{ full.style.display = 'block'; el.style.color = 'var(--accent)'; }} else {{ full.style.display = 'none'; el.style.color = ''; }} }}
function toggleTrail(el) {{ var card = el.closest('.tl-card'); var full = card.querySelector('.tl-card-full'); if (full.style.display === 'none') {{ full.style.display = 'block'; card.classList.add('open'); }} else {{ full.style.display = 'none'; card.classList.remove('open'); }} }}
function expandAllTrail() {{ document.querySelectorAll('.tl-card').forEach(function(c) {{ c.querySelector('.tl-card-full').style.display = 'block'; c.classList.add('open'); }}); }}
function collapseAllTrail() {{ document.querySelectorAll('.tl-card').forEach(function(c) {{ c.querySelector('.tl-card-full').style.display = 'none'; c.classList.remove('open'); }}); }}
</script>
</body>
</html>'''
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
