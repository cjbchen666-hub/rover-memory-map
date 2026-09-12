#!/usr/bin/env python3
"""
Rover 记忆地图 · 独立复核区注入脚本
=====================================
用途：在 Rover Agent 生成 index.html 之后、部署到 GitHub Pages 之前，
      自动注入"独立复核展示区"（CSS + HTML + JS），并确保 audit-log.json 在同目录。

特性：
  - 幂等：重复运行会先移除旧注入再重新注入，不会重复
  - 不修改原始信念数据：只在指定位置插入新代码，不动 #beliefs-data 和渲染逻辑
  - 容错：插入点找不到时给出明确警告，不崩溃
  - 备份：注入前自动备份原文件为 index.html.bak

用法：
  python3 inject-audit.py [index.html路径] [audit-log.json路径] [输出路径]

集成到 GitHub Actions：
  - name: Inject audit section
    run: python3 inject-audit.py rover/web/index.html audit-log.json rover/web/index.html
"""

import sys
import os
import shutil
import re
from datetime import datetime

# 起止标记（用于幂等检测和移除）
CSS_START = "/* === AUDIT-CSS-START === */"
CSS_END = "/* === AUDIT-CSS-END === */"
HTML_OVERVIEW_START = "<!-- AUDIT-OVERVIEW-START -->"
HTML_OVERVIEW_END = "<!-- AUDIT-OVERVIEW-END -->"
HTML_LOG_START = "<!-- AUDIT-LOG-START -->"
HTML_LOG_END = "<!-- AUDIT-LOG-END -->"
JS_START = "/* === AUDIT-JS-START === */"
JS_END = "/* === AUDIT-JS-END === */"

ALL_MARKERS = [CSS_START, CSS_END, HTML_OVERVIEW_START, HTML_OVERVIEW_END,
               HTML_LOG_START, HTML_LOG_END, JS_START, JS_END]

AUDIT_MARKER = "inject-audit.py"


def has_audit_marker(html):
    return any(m in html for m in ALL_MARKERS)


def strip_between(text, start_marker, end_marker):
    while start_marker in text and end_marker in text:
        start_idx = text.find(start_marker)
        end_idx = text.find(end_marker, start_idx)
        if end_idx == -1:
            break
        remove_end = end_idx + len(end_marker)
        if remove_end < len(text) and text[remove_end] == '\n':
            remove_end += 1
        text = text[:start_idx] + text[remove_end:]
    return text


def strip_existing_audit(html):
    html = strip_between(html, CSS_START, CSS_END)
    html = strip_between(html, HTML_OVERVIEW_START, HTML_OVERVIEW_END)
    html = strip_between(html, HTML_LOG_START, HTML_LOG_END)
    html = strip_between(html, JS_START, JS_END)
    return html


def build_css():
    return CSS_START + """
:root {
  --audit-pass: #7ee787; --audit-downgrade: #ffd58a; --audit-supplement: #8b949e;
  --audit-unknown: #58a6ff; --audit-pending: #ff7b72; --audit-bg: #0d1117;
  --audit-panel: #161b22; --audit-border: #30363d;
}
.audit-overview { background:var(--audit-panel); border:1px solid var(--audit-border); border-radius:14px; padding:20px 24px; margin-top:24px; }
.audit-overview-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; flex-wrap:wrap; gap:10px; }
.audit-overview-title { font-size:16px; font-weight:700; display:flex; align-items:center; gap:8px; }
.audit-overview-title .shield { display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px; background:rgba(88,166,255,.15); border-radius:5px; font-size:13px; }
.audit-overview-meta { font-size:12px; color:var(--muted); }
.audit-stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
.audit-stat { background:var(--audit-bg); border:1px solid var(--audit-border); border-radius:10px; padding:12px 14px; text-align:center; }
.audit-stat-num { font-size:24px; font-weight:800; line-height:1.2; }
.audit-stat-label { font-size:11px; color:var(--muted); margin-top:4px; letter-spacing:.5px; }
.audit-stat.pass .audit-stat-num { color:var(--audit-pass); }
.audit-stat.downgrade .audit-stat-num { color:var(--audit-downgrade); }
.audit-stat.supplement .audit-stat-num { color:var(--audit-supplement); }
.audit-stat.unknown .audit-stat-num { color:var(--audit-unknown); }
.audit-stat.pending .audit-stat-num { color:var(--audit-pending); }
.audit-stat.todo .audit-stat-num { color:var(--audit-pending); }
.belief-audit-bar { margin-top:10px; padding:10px 14px; background:var(--audit-bg); border:1px solid var(--audit-border); border-radius:8px; font-size:12.5px; }
.belief-audit-bar-row1 { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.audit-verdict-badge { display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; padding:3px 10px; border-radius:4px; letter-spacing:.5px; flex-shrink:0; }
.audit-verdict-badge::before { content:""; width:6px; height:6px; border-radius:50%; display:inline-block; }
.audit-verdict-badge.pass { background:rgba(126,231,135,.12); color:var(--audit-pass); border:1px solid rgba(126,231,135,.3); }
.audit-verdict-badge.pass::before { background:var(--audit-pass); }
.audit-verdict-badge.downgrade { background:rgba(255,213,138,.12); color:var(--audit-downgrade); border:1px solid rgba(255,213,138,.3); }
.audit-verdict-badge.downgrade::before { background:var(--audit-downgrade); }
.audit-verdict-badge.supplement { background:rgba(139,148,158,.12); color:var(--audit-supplement); border:1px solid rgba(139,148,158,.3); }
.audit-verdict-badge.supplement::before { background:var(--audit-supplement); }
.audit-verdict-badge.unknown { background:rgba(88,166,255,.12); color:var(--audit-unknown); border:1px solid rgba(88,166,255,.3); }
.audit-verdict-badge.unknown::before { background:var(--audit-unknown); }
.audit-verdict-badge.pending { background:rgba(255,123,114,.12); color:var(--audit-pending); border:1px solid rgba(255,123,114,.3); }
.audit-verdict-badge.pending::before { background:var(--audit-pending); }
.audit-conf-compare { display:inline-flex; align-items:center; gap:6px; font-variant-numeric:tabular-nums; }
.audit-conf-original { color:var(--muted); text-decoration:line-through; text-decoration-color:rgba(139,148,158,.5); }
.audit-conf-arrow { color:var(--muted); font-size:11px; }
.audit-conf-recommended { font-weight:700; }
.audit-conf-recommended.down { color:var(--audit-downgrade); }
.audit-conf-recommended.up { color:var(--audit-pass); }
.audit-conf-recommended.same { color:var(--muted); }
.audit-meta-counts { display:inline-flex; align-items:center; gap:12px; margin-left:auto; color:var(--muted); font-size:11.5px; }
.audit-meta-counts .cnt { display:inline-flex; align-items:center; gap:3px; }
.audit-meta-counts .cnt.warn { color:var(--audit-downgrade); }
.audit-meta-counts .cnt.todo { color:var(--audit-pending); }
.audit-expand-btn { background:none; border:1px solid var(--audit-border); color:var(--muted); font-size:11px; padding:2px 8px; border-radius:4px; cursor:pointer; transition:all .2s; flex-shrink:0; }
.audit-expand-btn:hover { border-color:var(--accent); color:var(--text); }
.belief-audit-detail { display:none; margin-top:10px; padding-top:10px; border-top:1px solid var(--audit-border); }
.belief-audit-bar.open .belief-audit-detail { display:block; }
.audit-summary { font-size:12.5px; color:#c9d1d9; line-height:1.7; margin-bottom:10px; }
.audit-findings-title, .audit-actions-title { font-size:11px; font-weight:700; color:var(--accent); letter-spacing:.8px; text-transform:uppercase; margin:10px 0 6px; }
.audit-finding { font-size:12px; color:#c9d1d9; line-height:1.65; padding:6px 10px; background:var(--audit-panel); border-radius:6px; margin-bottom:5px; border-left:3px solid var(--audit-border); }
.audit-finding.high { border-left-color:var(--audit-pending); }
.audit-finding.medium { border-left-color:var(--audit-downgrade); }
.audit-finding.low { border-left-color:var(--audit-supplement); }
.audit-finding .finding-sev { display:inline-block; font-size:10px; font-weight:700; padding:1px 6px; border-radius:3px; margin-right:6px; vertical-align:middle; }
.audit-finding.high .finding-sev { background:rgba(255,123,114,.15); color:var(--audit-pending); }
.audit-finding.medium .finding-sev { background:rgba(255,213,138,.15); color:var(--audit-downgrade); }
.audit-finding.low .finding-sev { background:rgba(139,148,158,.15); color:var(--audit-supplement); }
.audit-finding .finding-loc { display:block; font-size:10.5px; color:var(--muted); margin-top:3px; }
.audit-action { display:flex; align-items:flex-start; gap:8px; font-size:12px; color:#c9d1d9; line-height:1.6; padding:5px 0; }
.audit-action input[type="checkbox"] { margin-top:3px; flex-shrink:0; accent-color:var(--audit-pass); cursor:default; }
.audit-action.done .action-text { text-decoration:line-through; color:var(--muted); }
.audit-action .action-id { font-size:10px; color:var(--muted); font-weight:600; margin-right:4px; }
.belief-item.audit-not-passed::before { content:"⚠ 复核未通过"; display:inline-block; font-size:10px; font-weight:700; color:var(--audit-pending); background:rgba(255,123,114,.1); border:1px solid rgba(255,123,114,.3); padding:2px 8px; border-radius:4px; margin-bottom:6px; letter-spacing:.5px; }
.audit-log-section { margin-top:44px; }
.audit-log-toggle { cursor:pointer; user-select:none; display:flex; align-items:center; gap:10px; padding:12px 0; }
.audit-log-toggle .arrow { transition:transform .2s; display:inline-block; font-size:14px; color:var(--muted); }
.audit-log-section.open .audit-log-toggle .arrow { transform:rotate(90deg); }
.audit-log-content { display:none; margin-top:8px; }
.audit-log-section.open .audit-log-content { display:block; }
.audit-log-item { background:var(--audit-panel); border:1px solid var(--audit-border); border-radius:10px; padding:14px 18px; margin-bottom:8px; position:relative; padding-left:28px; }
.audit-log-item::before { content:""; position:absolute; left:12px; top:18px; width:8px; height:8px; border-radius:50%; background:var(--accent); }
.audit-log-item.initial::before { background:var(--audit-unknown); }
.audit-log-item.downgrade::before { background:var(--audit-downgrade); }
.audit-log-item.supplement::before { background:var(--audit-supplement); }
.audit-log-item.blocking::before { background:var(--audit-pending); }
.audit-log-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
.audit-log-date { font-size:11.5px; color:var(--muted); font-variant-numeric:tabular-nums; }
.audit-log-action { font-size:12.5px; font-weight:600; color:var(--text); }
.audit-log-belief { font-size:11px; font-weight:700; color:var(--accent); background:rgba(88,166,255,.1); padding:1px 7px; border-radius:3px; }
.audit-log-detail { font-size:12.5px; color:#c9d1d9; line-height:1.7; }
.audit-helper-section { margin-top:44px; }
.audit-helper-box { background:var(--audit-panel); border:1px solid var(--audit-border); border-radius:12px; padding:20px 24px; }
.audit-helper-box h3 { font-size:15px; font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:8px; }
.audit-helper-box p { font-size:13px; color:#c9d1d9; line-height:1.75; margin-bottom:10px; }
.audit-helper-box ul { padding-left:20px; margin-bottom:10px; }
.audit-helper-box li { font-size:12.5px; color:#c9d1d9; line-height:1.75; margin-bottom:4px; }
.audit-helper-box .key-point { background:var(--audit-bg); border-left:3px solid var(--accent); padding:10px 14px; border-radius:0 6px 6px 0; font-size:12.5px; color:#c9d1d9; line-height:1.7; margin-top:12px; }
.audit-legend { display:flex; flex-wrap:wrap; gap:14px; margin-top:14px; padding-top:14px; border-top:1px solid var(--audit-border); }
.audit-legend-item { display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--muted); }
.audit-legend-item i { width:10px; height:10px; border-radius:3px; display:inline-block; }
@media (max-width:640px) {
  .audit-stats { grid-template-columns:repeat(3,1fr); }
  .audit-stat-num { font-size:20px; }
  .audit-meta-counts { margin-left:0; width:100%; }
  .belief-audit-bar-row1 { gap:8px; }
}
""" + CSS_END + "\n"


def build_html_overview():
    return HTML_OVERVIEW_START + """
<section id="audit-overview-section">
  <div class="audit-overview">
    <div class="audit-overview-head">
      <div class="audit-overview-title"><span class="shield">🛡</span>独立复核总览</div>
      <div class="audit-overview-meta">复核日期 <span id="auditDate">—</span> · 复核框架 v1.0 · 数据来源 audit-log.json</div>
    </div>
    <div class="audit-stats" id="auditStats">
      <div class="audit-stat"><div class="audit-stat-num">…</div><div class="audit-stat-label">加载中</div></div>
    </div>
  </div>
</section>
""" + HTML_OVERVIEW_END + "\n"


def build_html_log_and_helper():
    return HTML_LOG_START + """
<section id="audit-log-section" class="audit-log-section">
  <h2 class="sec"><span class="dot" style="background:var(--audit-unknown)"></span>复核日志 <small id="auditLogCount">—</small></h2>
  <div class="audit-log-toggle" onclick="toggleAuditLog()" role="button" tabindex="0" aria-expanded="false">
    <span class="arrow">▸</span><span style="font-size:13px;color:var(--muted)">按时间倒序 · 点击展开</span>
  </div>
  <div class="audit-log-content" id="auditLogContent"></div>
</section>
<section id="audit-helper-section" class="audit-helper-section">
  <h2 class="sec"><span class="dot" style="background:var(--audit-supplement)"></span>关于独立复核</h2>
  <div class="audit-helper-box">
    <h3>🛡 复核助手说明</h3>
    <p>本区域由独立复核助手生成，用于对 Rover 记忆地图中的每条信念进行证据质量和逻辑一致性检查。复核结论仅供参考，不替代原始信念数据。</p>
    <p><strong>复核标准（9 项检查）：</strong></p>
    <ul>
      <li>来源等级：一手来源、二手汇总、观点评论，是否标注准确</li>
      <li>原文可追溯：是否有链接、时间、原文片段</li>
      <li>反方来源：是否搜索过批评、反驳、复现失败、争议、局限等关键词</li>
      <li>证据与结论匹配：原文是否真的支持结论</li>
      <li>置信度合理性：变化是否有理由，是否与证据强度匹配</li>
      <li>来源独立性：多个来源是否同源或互相引用</li>
      <li>时效性：证据是否过时</li>
      <li>内容偏差：总结是否与原文有明显出入</li>
      <li>信念张力：对立信念之间是否解释清楚</li>
    </ul>
    <div class="key-point"><strong>核心原则：</strong>不修改原始信念数据。复核数据单独存放于 <code>audit-log.json</code>，页面加载后按信念编号（B1-B6）合并显示。如果复核未通过，该信念不显示"已确认"状态。证据不足时标记"待补充"，不直接下强结论。</div>
    <div class="audit-legend">
      <div class="audit-legend-item"><i style="background:var(--audit-pass)"></i>通过</div>
      <div class="audit-legend-item"><i style="background:var(--audit-downgrade)"></i>建议降级</div>
      <div class="audit-legend-item"><i style="background:var(--audit-supplement)"></i>建议补充</div>
      <div class="audit-legend-item"><i style="background:var(--audit-unknown)"></i>暂无法判断</div>
      <div class="audit-legend-item"><i style="background:var(--audit-pending)"></i>待处理（阻塞）</div>
    </div>
  </div>
</section>
""" + HTML_LOG_END + "\n"


def build_js():
    return JS_START + """
  var AUDIT_DATA=null,AUDIT_BY_ID={};
  var VERDICT_CLASS={'通过':'pass','建议降级':'downgrade','建议补充':'supplement','暂无法判断':'unknown','待处理':'pending'};
  function loadAuditData(){fetch('audit-log.json').then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(function(data){AUDIT_DATA=data;if(data.audits){data.audits.forEach(function(a){AUDIT_BY_ID[a.belief_id]=a;});}renderAuditOverview(data);renderAuditBars(data);renderAuditLog(data);}).catch(function(err){console.warn('[Audit] 无法加载 audit-log.json:',err.message);var o=document.getElementById('auditStats');if(o){o.innerHTML='<div class="audit-stat pending" style="grid-column:1/-1"><div class="audit-stat-num" style="font-size:14px">复核数据加载失败</div><div class="audit-stat-label">请确认 audit-log.json 与页面在同一目录</div></div>';}});}
  function renderAuditOverview(data){var a=data.audits||[];var t=a.length;var p=a.filter(function(x){return x.verdict==='通过';}).length;var d=a.filter(function(x){return x.verdict==='建议降级';}).length;var s=a.filter(function(x){return x.verdict==='建议补充';}).length;var u=a.filter(function(x){return x.verdict==='暂无法判断';}).length;var pd=a.filter(function(x){return x.verdict==='待处理'||x.blocking;}).length;var ta=0,da=0;a.forEach(function(x){(x.required_actions||[]).forEach(function(act){ta++;if(act.done)da++;});});var oa=ta-da;if(data.meta&&data.meta.audit_date){var el=document.getElementById('auditDate');if(el)el.textContent=data.meta.audit_date;}var h='';h+='<div class="audit-stat"><div class="audit-stat-num">'+t+'</div><div class="audit-stat-label">已复核</div></div>';h+='<div class="audit-stat pass"><div class="audit-stat-num">'+p+'</div><div class="audit-stat-label">通过</div></div>';h+='<div class="audit-stat downgrade"><div class="audit-stat-num">'+d+'</div><div class="audit-stat-label">建议降级</div></div>';h+='<div class="audit-stat supplement"><div class="audit-stat-num">'+s+'</div><div class="audit-stat-label">建议补充</div></div>';h+='<div class="audit-stat unknown"><div class="audit-stat-num">'+u+'</div><div class="audit-stat-label">暂无法判断</div></div>';h+='<div class="audit-stat todo"><div class="audit-stat-num">'+oa+'</div><div class="audit-stat-label">未完成待办</div></div>';var c=document.getElementById('auditStats');if(c)c.innerHTML=h;}
  function renderAuditBars(data){var items=document.querySelectorAll('#beliefs-section .belief-item');items.forEach(function(item){var bid=item.getAttribute('data-belief-id');var audit=AUDIT_BY_ID[bid];if(!audit){item.insertAdjacentHTML('beforeend',buildPendingAuditBar(bid));return;}if(audit.verdict!=='通过'){item.classList.add('audit-not-passed');}item.insertAdjacentHTML('beforeend',buildAuditBar(audit));});document.querySelectorAll('.audit-expand-btn').forEach(function(btn){btn.addEventListener('click',function(e){e.stopPropagation();var bar=this.closest('.belief-audit-bar');if(bar){bar.classList.toggle('open');this.textContent=bar.classList.contains('open')?'收起详情':'展开详情';}});});}
  function buildAuditBar(audit){var vc=VERDICT_CLASS[audit.verdict]||'pending';var oc=audit.rover_confidence,rc=audit.auditor_recommended_confidence;var cd='same';if(rc<oc)cd='down';else if(rc>oc)cd='up';var fc=(audit.findings||[]).length;var acts=audit.required_actions||[];var oa=acts.filter(function(a){return !a.done;}).length;var h='<div class="belief-audit-bar" data-audit-id="'+audit.belief_id+'">';h+='<div class="belief-audit-bar-row1">';h+='<span class="audit-verdict-badge '+vc+'">'+audit.verdict+'</span>';h+='<span class="audit-conf-compare"><span class="audit-conf-original">'+oc.toFixed(2)+'</span><span class="audit-conf-arrow">→</span><span class="audit-conf-recommended '+cd+'">'+rc.toFixed(2)+'</span></span>';h+='<span class="audit-meta-counts"><span class="cnt warn">⚠ '+fc+' 问题</span><span class="cnt todo">☐ '+oa+' 待办</span></span>';h+='<button class="audit-expand-btn">展开详情</button>';h+='</div>';h+='<div class="belief-audit-detail">';if(audit.summary){h+='<div class="audit-summary">'+escHtml(audit.summary)+'</div>';}if(fc>0){h+='<div class="audit-findings-title">主要问题（'+fc+'）</div>';audit.findings.forEach(function(f){var sc=f.severity||'low';h+='<div class="audit-finding '+sc+'"><span class="finding-sev">'+(sc==='high'?'高':sc==='medium'?'中':'低')+'</span>'+escHtml(f.text);if(f.location){h+='<span class="finding-loc">来源位置：'+escHtml(f.location)+'</span>';}h+='</div>';});}if(acts.length>0){h+='<div class="audit-actions-title">待办事项（'+oa+' 未完成 / '+acts.length+' 总计）</div>';acts.forEach(function(act){var dn=act.done?'checked':'';var dc=act.done?'done':'';h+='<div class="audit-action '+dc+'"><input type="checkbox" '+dn+' disabled readonly><span class="action-text"><span class="action-id">'+escHtml(act.id)+'</span>'+escHtml(act.text)+'</span></div>';});}h+='</div></div>';return h;}
  function buildPendingAuditBar(bid){return '<div class="belief-audit-bar" data-audit-id="'+bid+'"><div class="belief-audit-bar-row1"><span class="audit-verdict-badge pending">待处理</span><span class="audit-conf-compare"><span class="audit-conf-original">—</span><span class="audit-conf-arrow">→</span><span class="audit-conf-recommended same">—</span></span><span class="audit-meta-counts"><span class="cnt warn">⚠ 0 问题</span><span class="cnt todo">☐ 0 待办</span></span><span style="font-size:11px;color:var(--muted);margin-left:auto">尚未复核</span></div></div>';}
  function renderAuditLog(data){var logs=data.audit_log||[];var c=document.getElementById('auditLogContent');var ce=document.getElementById('auditLogCount');if(ce)ce.textContent=logs.length+' 条记录';if(!c)return;if(logs.length===0){c.innerHTML='<p style="color:var(--muted);font-size:13px;padding:10px 0">暂无复核日志。</p>';return;}var sorted=logs.slice().sort(function(a,b){return ((b.date||'')+' '+(b.time||'')).localeCompare((a.date||'')+' '+(a.time||''));});var h='';sorted.forEach(function(log){var lc='';if(log.action&&log.action.indexOf('降级')>-1)lc='downgrade';else if(log.action&&log.action.indexOf('补充')>-1)lc='supplement';else if(log.action&&log.action.indexOf('阻塞')>-1)lc='blocking';else if(log.action&&log.action.indexOf('初始')>-1)lc='initial';h+='<div class="audit-log-item '+lc+'"><div class="audit-log-head"><span class="audit-log-date">'+escHtml(log.date||'')+' '+escHtml(log.time||'')+'</span><span class="audit-log-action">'+escHtml(log.action||'')+'</span>';if(log.belief_id&&log.belief_id!=='ALL'){h+='<span class="audit-log-belief">'+escHtml(log.belief_id)+'</span>';}h+='</div>';if(log.detail){h+='<div class="audit-log-detail">'+escHtml(log.detail)+'</div>';}h+='</div>';});c.innerHTML=h;}
  function toggleAuditLog(){var s=document.getElementById('audit-log-section');if(s){s.classList.toggle('open');var t=s.querySelector('.audit-log-toggle');if(t){var ex=s.classList.contains('open');t.setAttribute('aria-expanded',ex);var l=t.querySelector('span:last-child');if(l)l.textContent=ex?'按时间倒序 · 点击收起':'按时间倒序 · 点击展开';}}}
  function escHtml(str){if(str==null)return '';var d=document.createElement('div');d.textContent=String(str);return d.innerHTML;}
  loadAuditData();
""" + JS_END + "\n"


def inject_css(html):
    if "</style>" not in html:
        print("  [警告] 未找到 </style>，跳过 CSS 注入")
        return html
    return html.replace("</style>", build_css() + "</style>", 1)


def inject_html_overview(html):
    if "</header>" in html:
        return html.replace("</header>", "</header>\n" + build_html_overview(), 1)
    print("  [警告] 未找到 </header>，跳过总览区块注入")
    return html


def inject_html_log_and_helper(html):
    anchor = '<section id="tensions-section">'
    if anchor in html:
        return html.replace(anchor, build_html_log_and_helper() + anchor, 1)
    print("  [警告] 未找到 tensions-section 锚点，跳过日志/说明区注入")
    return html


def inject_js(html):
    if "initBeliefPanel();" in html:
        return html.replace("initBeliefPanel();", "initBeliefPanel();\n" + build_js(), 1)
    print("  [警告] 未找到 initBeliefPanel()，跳过 JS 注入")
    return html


def main():
    html_path = sys.argv[1] if len(sys.argv) > 1 else "./index.html"
    audit_json_path = sys.argv[2] if len(sys.argv) > 2 else "./audit-log.json"
    output_path = sys.argv[3] if len(sys.argv) > 3 else html_path

    print(f"[inject-audit] 开始注入独立复核展示区")
    print(f"  输入 HTML: {html_path}")
    print(f"  复核数据: {audit_json_path}")
    print(f"  输出路径: {output_path}")

    if not os.path.exists(html_path):
        print(f"[错误] 未找到 {html_path}")
        sys.exit(1)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    original_size = len(html)

    if has_audit_marker(html):
        print("  [信息] 检测到已有注入内容，正在移除旧版本...")
        html = strip_existing_audit(html)

    backup_path = html_path + ".bak"
    shutil.copy2(html_path, backup_path)

    print("  [步骤] 注入 CSS...")
    html = inject_css(html)
    print("  [步骤] 注入顶部总览 HTML...")
    html = inject_html_overview(html)
    print("  [步骤] 注入复核日志 + 助手说明 HTML...")
    html = inject_html_log_and_helper(html)
    print("  [步骤] 注入 JS...")
    html = inject_js(html)

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    if os.path.exists(audit_json_path):
        dest = os.path.join(output_dir, "audit-log.json")
        if os.path.abspath(audit_json_path) != os.path.abspath(dest):
            shutil.copy2(audit_json_path, dest)

    final_size = len(html)
    print(f"\n[完成] 注入成功 ({final_size:,} 字节, +{final_size - original_size:,})")


if __name__ == "__main__":
    main()
