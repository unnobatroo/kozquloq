"""Build the static audit-report site for kozquloq.vercel.app.

Usage:
    uv run python scripts/build_site.py --db data/kozquloq.duckdb \
        --dataroot v1.0-mini --out site_out

Reads the audit DB for summary/slice/token stats, renders up to --max-images
flagged-frame overlays from the dataset, and writes a single self-contained
index.html (Tabler 1.6 dashboard template via CDN + vanilla JS, no build step)
plus img/*.jpg into --out. Deploy with `vercel deploy --prod` inside the dir.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


def render_images(dataroot: str, version: str, img_dir: Path, max_images: int) -> list[str]:
    """Save overlays for the first flagged frames; return jpeg filenames."""
    from kozquloq.auditors import DEFAULT_AUDITORS, audit_frame
    from kozquloq.ingestion import load_frames
    from kozquloq.visualization.overlay import save_annotated_frame

    names: list[str] = []
    for _scene, frames in load_frames(dataroot, version):
        auditors = [cls() for cls in DEFAULT_AUDITORS]
        for bundle in frames:
            _, boxes = audit_frame(bundle, auditors)
            if any(r.flagged for r in boxes):
                names.append(save_annotated_frame(bundle, boxes, str(img_dir)).name)
                if len(names) >= max_images:
                    return names
    return names


PAGE = """<!DOCTYPE html>
<html lang="en" data-bs-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kozquloq - AV annotation lint report</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='14' fill='none' stroke='%2335c4b5' stroke-width='2' stroke-dasharray='4 3'/%3E%3Cpath d='M5 16 C9 10 23 10 27 16 C23 22 9 22 5 16 Z' fill='none' stroke='%231a2634' stroke-width='2'/%3E%3Ccircle cx='16' cy='16' r='4' fill='%2335c4b5'/%3E%3C/svg%3E">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@1.6.1/dist/css/tabler.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.49.0/dist/tabler-icons.min.css">
<style>
/* Kozquloq palette: deep ink base, lidar-teal accent, flag traffic colors */
:root{--tblr-primary:#1f9d8f;--tblr-body-bg:#f5f7fa;--koz-teal:#1f9d8f;
--koz-teal-dim:#177a70;--koz-ink:#1a2634;--koz-card:#ffffff}
.btn-primary{background:var(--koz-teal);border-color:var(--koz-teal);color:#fff;font-weight:600}
.btn-primary:hover{background:var(--koz-teal-dim);border-color:var(--koz-teal-dim);color:#fff}
.koz-navbar{background:#fff;border-bottom:1px solid #e2e8f0}
body{font-family:"Inter",-apple-system,"Segoe UI",Roboto,sans-serif}
.kpi{font-size:1.9rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.1}
.gauge-svg{transform:rotate(-90deg)}
.brand-mark{display:inline-flex;align-items:center;gap:8px}
.brand-mark svg{height:26px;width:26px}
.brand-sub{color:var(--koz-teal);font-size:11px;letter-spacing:2px;text-transform:uppercase}
.gallery-img{cursor:zoom-in;transition:transform .18s,box-shadow .18s;object-fit:cover}
.gallery-img:hover{transform:scale(1.015);box-shadow:0 6px 24px rgba(53,196,181,.25)}
.lb{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;justify-content:center;z-index:1050;cursor:zoom-out}
.lb.open{display:flex}.lb img{max-width:94vw;max-height:92vh;border-radius:6px}
.table-sorted{color:var(--koz-teal)}
th[data-col]{cursor:pointer;white-space:nowrap}
th[data-col]:hover{color:var(--koz-teal)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.78rem}
.step{border-left:3px solid var(--koz-teal)}
.failbar{min-width:70px}
.hidden{display:none!important}
.nav-tabs .nav-link.active{border-color:var(--koz-teal) var(--koz-teal) transparent}
</style></head><body class="antialiased">
<div class="page">
<header class="navbar navbar-expand-md koz-navbar">
 <div class="container-xl">
  <a class="navbar-brand brand-mark" href="#"><svg viewBox="0 0 32 32" fill="none">
   <circle cx="16" cy="16" r="14" stroke="#1f9d8f" stroke-width="1.6" stroke-dasharray="4 3"/>
   <path d="M5 16 C9 10 23 10 27 16 C23 22 9 22 5 16 Z" stroke="#1a2634" stroke-width="1.8"/>
   <circle cx="16" cy="16" r="4" fill="#1f9d8f"/></svg>
   <span>Kozquloq <span class="text-secondary fw-normal">/ lint report</span></span></a>
  <div class="navbar-nav flex-row ms-auto">
   <a class="btn btn-outline-secondary btn-sm me-2" href="https://github.com/unnobatroo/kozquloq" target="_blank"><i class="ti ti-brand-github me-1"></i>GitHub</a>
   <button class="btn btn-primary btn-sm" onclick="downloadMask('json')"><i class="ti ti-download me-1"></i>Download mask</button>
  </div>
 </div>
</header>

<main class="page-wrapper"><div class="container-xl py-4">

<div class="page-header d-print-none mb-4">
 <div class="row g-2 align-items-center">
  <div class="col">
   <div class="page-pretitle"><span class="brand-sub">köz quloq - eye and ear</span></div>
   <h2 class="page-title mb-1">nuScenes v1.0-mini</h2>
   <div class="text-secondary">__FLAGGED__ of __ANNS_FMT__ labels failed the sensor
    check - __FAILPCT__% of the dataset. This page is a static snapshot of one
    <code>kozquloq scan</code>.</div>
  </div>
  <div class="col-auto ms-auto">
   <span class="badge __GRADEBG__ fs-2 px-3 py-2">Grade __GRADE__</span>
  </div>
 </div>
</div>

<ul class="nav nav-tabs nav-fill mb-4" id="tabs">
 <li class="nav-item"><a class="nav-link active" data-pane="overview" href="#"><i class="ti ti-dashboard me-1"></i>Overview</a></li>
 <li class="nav-item"><a class="nav-link" data-pane="frames" href="#"><i class="ti ti-photo-scan me-1"></i>Flagged frames</a></li>
 <li class="nav-item"><a class="nav-link" data-pane="tokens" href="#"><i class="ti ti-filter me-1"></i>Invalid-token mask
   <span class="badge bg-red-lt ms-1">__TOKCOUNT__</span></a></li>
 <li class="nav-item"><a class="nav-link" data-pane="how" href="#"><i class="ti ti-info-circle me-1"></i>How it works</a></li>
</ul>

<!-- OVERVIEW -->
<div class="pane" id="pane-overview">
 <div class="row g-3 mb-1">
  <div class="col-sm-6 col-lg-4"><div class="card"><div class="card-body d-flex align-items-center">
   <svg class="gauge-svg" width="96" height="96" viewBox="0 0 96 96">
    <circle cx="48" cy="48" r="40" fill="none" stroke="#e5eaf0" stroke-width="9"/>
    <circle id="arc" cx="48" cy="48" r="40" fill="none" stroke="__GC__" stroke-width="9"
     stroke-linecap="round" stroke-dasharray="251" stroke-dashoffset="251"/></svg>
   <div class="ms-3"><div class="subheader">Health grade</div>
    <div class="kpi" style="color:__GC__">__GRADE__</div>
    <div class="text-secondary small">__FAILPCT__% flagged</div></div>
  </div></div></div>
  <div class="col-6 col-lg-4 col-xl-2"><div class="card"><div class="card-body">
   <div class="subheader">Frames</div><div class="kpi">__FRAMES_FMT__</div>
   <div class="text-secondary small">__BADFRAMES__ with flags</div></div></div></div>
  <div class="col-6 col-lg-4 col-xl-2"><div class="card"><div class="card-body">
   <div class="subheader">Annotations</div><div class="kpi">__ANNS_FMT__</div>
   <div class="text-secondary small">across __SCENES__ scenes</div></div></div></div>
  <div class="col-6 col-lg-4 col-xl-2"><div class="card"><div class="card-body">
   <div class="subheader text-red">Ghost labels</div><div class="kpi text-red">__GHOSTS_FMT__</div>
   <div class="text-secondary small">zero LiDAR returns</div></div></div></div>
  <div class="col-6 col-lg-4 col-xl-2"><div class="card"><div class="card-body">
   <div class="subheader text-orange">Kinematic</div><div class="kpi text-orange">__KIN__</div>
   <div class="text-secondary small">non-physical motion</div></div></div></div>
  <div class="col-6 col-lg-4 col-xl-2"><div class="card"><div class="card-body">
   <div class="subheader text-azure">Scale unstable</div><div class="kpi text-azure">__SCALE__</div>
   <div class="text-secondary small">volume &gt;15% drift</div></div></div></div>
 </div>

 <div class="card mt-3">
  <div class="card-header d-flex align-items-center">
   <h3 class="card-title">Failure rate by slice</h3>
   <div class="ms-auto text-secondary small">click headers to sort</div>
  </div>
  <div class="table-responsive"><table class="table table-vcenter card-table table-hover" id="sliceTab">
   <thead><tr><th data-col="0">Weather</th><th data-col="1">Time</th><th data-col="2">Category</th>
   <th data-col="3" class="text-end">N</th><th data-col="4" class="text-end">Ghosts</th>
   <th data-col="5" class="text-end">Kinematic</th><th data-col="6" class="text-end">Avg pts</th>
   <th data-col="7">Fail rate</th></tr></thead>
   <tbody>__SLICE_ROWS__</tbody></table></div>
 </div>
</div>

<!-- FRAMES -->
<div class="pane hidden" id="pane-frames">
 <div class="d-flex align-items-center mb-3">
  <h3 class="mb-0">Annotated overlays</h3>
  <span class="text-secondary ms-2 small">what the camera saw vs what the labels claim - click to zoom</span>
 </div>
 <div class="row g-3">__GALLERY__</div>
</div>

<!-- TOKENS -->
<div class="pane hidden" id="pane-tokens">
 <div class="card">
  <div class="card-header">
   <div class="row w-100 g-2 align-items-center">
    <div class="col"><h3 class="card-title mb-0">Invalid-token mask</h3>
     <div class="text-secondary small mt-1">The tokens your training pipeline should drop. Severity ≥0.5.</div></div>
    <div class="col-auto"><div class="btn-group">
     <button class="btn btn-outline-primary btn-sm" onclick="downloadMask('json')"><i class="ti ti-file-type-js me-1"></i>JSON</button>
     <button class="btn btn-outline-primary btn-sm" onclick="downloadMask('csv')"><i class="ti ti-file-type-csv me-1"></i>CSV</button>
     <button class="btn btn-outline-primary btn-sm" onclick="copyTokens()"><i class="ti ti-copy me-1"></i>Copy tokens</button>
    </div></div>
   </div>
  </div>
  <div class="card-body border-bottom py-3">
   <div class="d-flex flex-wrap gap-2 align-items-center">
    <input type="search" id="tokSearch" class="form-control w-auto" placeholder="Search token or category...">
    <div class="btn-group" id="reasonBtns">
     <button class="btn btn-sm active" data-f="">All</button>
     <button class="btn btn-sm" data-f="ghost"><i class="ti ti-ghost-2 me-1"></i>Ghost</button>
     <button class="btn btn-sm" data-f="kinematic"><i class="ti ti-run me-1"></i>Kinematic</button>
     <button class="btn btn-sm" data-f="scale"><i class="ti ti-resize me-1"></i>Scale</button>
    </div>
    <select id="catSel" class="form-select w-auto"><option value="">All categories</option></select>
    <span class="text-secondary small ms-auto" id="tokCount"></span>
   </div>
  </div>
  <div class="table-responsive"><table class="table table-vcenter card-table table-hover">
   <thead><tr><th>Token</th><th>Category</th><th class="text-end">Severity</th><th>Reason</th></tr></thead>
   <tbody id="tokBody"></tbody></table></div>
  <div class="card-footer d-flex align-items-center">
   <p class="m-0 text-secondary" id="tokPageInfo"></p>
   <ul class="pagination ms-auto m-0">
    <li class="page-item"><button class="page-link" id="pgPrev">‹ Prev</button></li>
    <li class="page-item"><button class="page-link" id="pgNext">Next ›</button></li>
   </ul>
  </div>
 </div>
</div>

<!-- HOW -->
<div class="pane hidden" id="pane-how">
 <div class="row g-3 mb-4">
  <div class="col-md-6 col-xl-3"><div class="card step h-100"><div class="card-body">
   <div class="subheader text-primary">01 - READ</div><b>Point it at the dataset</b>
   <p class="text-secondary small mt-2">It walks every keyframe and pulls the camera image, the LiDAR cloud, the labels, and the calibration needed to line them up in space and time.</p></div></div></div>
  <div class="col-md-6 col-xl-3"><div class="card step h-100"><div class="card-body">
   <div class="subheader text-primary">02 - COUNT</div><b>What did LiDAR actually see?</b>
   <p class="text-secondary small mt-2">For every box it counts the points inside. Road surface is ignored (z &lt; -2.0 m). A car or pedestrian under 35 m with zero points is a ghost.</p></div></div></div>
  <div class="col-md-6 col-xl-3"><div class="card step h-100"><div class="card-body">
   <div class="subheader text-primary">03 - TRACK</div><b>Does the motion obey physics?</b>
   <p class="text-secondary small mt-2">Each object ID is followed across frames. Pedestrians accelerating past 8 m/s², vehicles past 12, or rigid objects that change size by 15% get flagged.</p></div></div></div>
  <div class="col-md-6 col-xl-3"><div class="card step h-100"><div class="card-body">
   <div class="subheader text-primary">04 - EXPORT</div><b>Hand over the mask</b>
   <p class="text-secondary small mt-2">The bad tokens go to a Parquet/JSON file your training pipeline can drop directly; flagged frames get annotated images like the ones here.</p></div></div></div>
 </div>
 <div class="row g-3">
  <div class="col-md-3"><div class="card"><div class="card-body border-top border-top-3 border-red">
   <b>Ghost label</b><p class="text-secondary small mt-2 mb-0">Someone drew a box where the LiDAR recorded nothing. Training on it teaches hallucination. <code>severity 0.55 - masked</code></p></div></div></div>
  <div class="col-md-3"><div class="card"><div class="card-body border-top border-top-3 border-orange">
   <b>Kinematic outlier</b><p class="text-secondary small mt-2 mb-0">The "object" moved faster than physics allows - an ID hop or a jittered center. <code>severity 0.25</code></p></div></div></div>
  <div class="col-md-3"><div class="card"><div class="card-body border-top border-top-3 border-azure">
   <b>Scale unstable</b><p class="text-secondary small mt-2 mb-0">A rigid object changed volume by more than 15% between frames. <code>severity 0.20</code></p></div></div></div>
  <div class="col-md-3"><div class="card"><div class="card-body border-top border-top-3 border-green">
   <b>Verified</b><p class="text-secondary small mt-2 mb-0">LiDAR returns inside the box, plausible motion, stable size. <code>severity 0.00 - keep</code></p></div></div></div>
 </div>
 <div class="card mt-4"><div class="card-body">
  <h3 class="card-title">Reproduce</h3>
<pre class="p-3 rounded mb-0 mono" style="background:#10181f;color:#c9d4e0">pip install kozquloq
kozquloq scan --dataroot &lt;nuScenes-root&gt; --db audit.duckdb --viz-dir viz_out
kozquloq export --db audit.duckdb --output mask.parquet --min-severity 0.5
kozquloq viz &lt;sample_token&gt; --dataroot &lt;nuScenes-root&gt;</pre></div></div>
</div>

<footer class="footer footer-transparent mt-5"><div class="text-secondary small">
<span class="brand-sub">Kozquloq</span> - eslint for AV datasets. A zero-point
box is a signal, not a verdict: occluded objects can legitimately be empty, so
the mask is a review list rather than ground truth.
GPL-3.0 - generated static snapshot, not live data.
<a href="https://github.com/unnobatroo/kozquloq">github.com/unnobatroo/kozquloq</a></div></footer>
</div></main></div>
<div class="lb" id="lb"><img id="lbImg" alt="overlay"></div>
<script type="application/json" id="tokData">__TOKJSON__</script>
<script>
const TOK=JSON.parse(document.getElementById('tokData').textContent);
// tab nav
document.querySelectorAll('#tabs .nav-link').forEach(a=>a.addEventListener('click',e=>{
 e.preventDefault();
 document.querySelectorAll('#tabs .nav-link').forEach(x=>x.classList.remove('active'));
 document.querySelectorAll('.pane').forEach(p=>p.classList.add('hidden'));
 a.classList.add('active');document.getElementById('pane-'+a.dataset.pane).classList.remove('hidden')}));
// token table: search + reason filter + category select + pagination
const body=document.getElementById('tokBody'),PG=25;
let q='',f='',cat='',page=0;
const catSel=document.getElementById('catSel');
[...new Set(TOK.map(r=>r.category))].sort().forEach(c=>{const o=document.createElement('option');o.value=o.textContent=c;catSel.append(o)});
function filtered(){return TOK.filter(r=>(!f||r.reason.startsWith(f))&&(!cat||r.category===cat)&&(!q||(r.annotation_token+r.category).toLowerCase().includes(q)))}
function draw(){
 const rows=filtered(),pages=Math.max(1,Math.ceil(rows.length/PG));
 page=Math.min(page,pages-1);
 body.innerHTML=rows.slice(page*PG,page*PG+PG).map(r=>`<tr><td class="mono">${r.annotation_token.slice(0,12)}…</td><td>${r.category}</td><td class="text-end">${r.severity.toFixed(2)}</td><td>${r.reason}</td></tr>`).join('');
 document.getElementById('tokCount').textContent=`${rows.length} of ${TOK.length}`;
 document.getElementById('tokPageInfo').textContent=`Page ${page+1} of ${pages}`;
 document.getElementById('pgPrev').disabled=page===0;
 document.getElementById('pgNext').disabled=page>=pages-1;
}
draw();
document.getElementById('tokSearch').addEventListener('input',e=>{q=e.target.value.toLowerCase();page=0;draw()});
catSel.addEventListener('change',e=>{cat=e.target.value;page=0;draw()});
document.querySelectorAll('#reasonBtns .btn').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('#reasonBtns .btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');f=b.dataset.f;page=0;draw()}));
document.getElementById('pgPrev').onclick=()=>{page--;draw()};
document.getElementById('pgNext').onclick=()=>{page++;draw()};
// downloads
function downloadMask(fmt){
 const a=document.createElement('a');
 if(fmt==='csv'){const csv='annotation_token,category,severity,reason\\n'+filtered().map(r=>[r.annotation_token,r.category,r.severity,`"${r.reason}"`].join(',')).join('\\n');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='kozquloq_mask.csv'}
 else{a.href=URL.createObjectURL(new Blob([JSON.stringify(filtered(),null,2)],{type:'application/json'}));a.download='kozquloq_mask.json'}
 a.click();URL.revokeObjectURL(a.href)}
function copyTokens(){navigator.clipboard.writeText(filtered().map(r=>r.annotation_token).join('\\n'))}
// sortable slice table
document.querySelectorAll('#sliceTab th').forEach(th=>th.addEventListener('click',()=>{
 const i=+th.dataset.col,tb=document.querySelector('#sliceTab tbody'),rows=[...tb.rows],num=i>2&&i<7;
 rows.sort((a,b)=>{const x=a.cells[i].dataset.v??a.cells[i].textContent,y=b.cells[i].dataset.v??b.cells[i].textContent;
  return num?parseFloat(x)-parseFloat(y):x.localeCompare(y)});
 if(th.dataset.d==='d'){rows.reverse();th.dataset.d='a'}else th.dataset.d='d';
 tb.append(...rows);
 document.querySelectorAll('#sliceTab th').forEach(x=>x.classList.remove('table-sorted'));
 th.classList.add('table-sorted')}));
// gauge arc
const arc=document.getElementById('arc');
setTimeout(()=>{arc.style.transition='stroke-dashoffset 1.1s cubic-bezier(.22,1,.36,1)';
 arc.style.strokeDashoffset=251*(1-Math.min(__FAILPCTRAW__,100)/100)},300);
// lightbox
const lb=document.getElementById('lb'),li=document.getElementById('lbImg');
document.querySelectorAll('.gallery-img').forEach(im=>im.addEventListener('click',()=>{li.src=im.src;lb.classList.add('open')}));
lb.addEventListener('click',()=>lb.classList.remove('open'));
document.addEventListener('keydown',e=>{if(e.key==='Escape')lb.classList.remove('open')});
</script></body></html>"""


def build(db: str, img_names: list[str]) -> str:
    from kozquloq.storage.duckdb_store import Store

    store = Store(db)
    s = store.get_summary()
    slices = store.get_slice_metrics()
    invalid = store.get_invalid_tokens()
    esc = lambda v: html.escape(str(v))  # noqa: E731

    flags = {
        r["sample_token"]: r
        for r in store.query(
            """
            SELECT sample_token, bool_or(is_ghost) AS g,
                   bool_or(is_kinematic_outlier) AS k,
                   bool_or(is_scale_unstable) AS sc
            FROM audits GROUP BY sample_token
            """
        )
    }
    bad_frames = sum(1 for r in flags.values() if r["g"] or r["k"] or r["sc"])
    n_scenes = store.query("SELECT COUNT(DISTINCT scene_name) AS n FROM samples")[0]["n"]
    max_fail = max((r["failure_rate_pct"] for r in slices), default=1) or 1

    slice_rows = "".join(
        f"<tr><td>{esc(r['weather'])}</td><td>{esc(r['time_of_day'])}</td>"
        f"<td>{esc(r['category'])}</td><td class='text-end'>{r['total_annotations']:,}</td>"
        f"<td class='text-end'>{r['ghost_labels_count']}</td>"
        f"<td class='text-end'>{r['kinematic_outliers_count']}</td>"
        f"<td class='text-end'>{r['avg_lidar_points']}</td>"
        f"<td data-v='{r['failure_rate_pct']}'><div class='d-flex align-items-center gap-2'>"
        f"<div class='progress failbar flex-fill' style='height:6px'>"
        f"<div class='progress-bar bg-red' style='width:{r['failure_rate_pct'] / max_fail * 100:.0f}%'></div></div>"
        f"<span class='text-secondary'>{r['failure_rate_pct']}%</span></div></td></tr>"
        for r in slices
    )

    badge = {"ghost": "bg-red-lt", "kinematic": "bg-orange-lt", "scale": "bg-azure-lt"}

    def card(name: str) -> str:
        tok = name.removesuffix(".jpg")
        r = flags.get(tok) or {}
        kinds = [("ghost", r.get("g")), ("kinematic", r.get("k")), ("scale", r.get("sc"))]
        tags = " ".join(f"<span class='badge {badge[k]} me-1'>{k}</span>" for k, on in kinds if on)
        return (
            "<div class='col-sm-6 col-lg-4 col-xl-3'><div class='card'>"
            f"<img class='card-img-top gallery-img' src='img/{esc(name)}' loading='lazy' alt='overlay'/>"
            f"<div class='card-body py-2 px-3 d-flex align-items-center justify-content-between'>"
            f"<span class='mono text-secondary'>{esc(name[:8])}</span><span>{tags}</span>"
            "</div></div></div>"
        )

    gallery = "".join(card(n) for n in img_names)
    grade_color = {
        "A": ("bg-green-lt", "#2da44e"),
        "B": ("bg-lime-lt", "#4c9a11"),
        "C": ("bg-yellow-lt", "#9a6700"),
        "D": ("bg-orange-lt", "#bc4c00"),
        "F": ("bg-red-lt", "#cf222e"),
    }[s["grade"]]

    page = PAGE
    for k, v in {
        "__GC__": grade_color[1],
        "__GRADEBG__": grade_color[0],
        "__GRADE__": s["grade"],
        "__FLAGGED__": f"{s['flagged']:,}",
        "__ANNS_FMT__": f"{s['annotations']:,}",
        "__FAILPCT__": s["failure_pct"],
        "__FAILPCTRAW__": s["failure_pct"],
        "__FRAMES_FMT__": f"{s['frames']:,}",
        "__SCENES__": n_scenes,
        "__GHOSTS_FMT__": f"{s['ghosts']:,}",
        "__KIN__": s["kinematic_outliers"],
        "__SCALE__": s["scale_unstable"],
        "__BADFRAMES__": bad_frames,
        "__SLICE_ROWS__": slice_rows,
        "__GALLERY__": gallery,
        "__TOKCOUNT__": f"{len(invalid):,}",
        "__TOKJSON__": json.dumps(invalid),
    }.items():
        page = page.replace(k, str(v))
    return page


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="data/kozquloq.duckdb")
    p.add_argument("--dataroot", default=None, help="dataset root for overlays")
    p.add_argument("--version", default="v1.0-mini")
    p.add_argument("--out", default="site_out")
    p.add_argument("--max-images", type=int, default=8)
    args = p.parse_args()

    out = Path(args.out)
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    names = (
        render_images(args.dataroot, args.version, img_dir, args.max_images)
        if args.dataroot
        else sorted(x.name for x in img_dir.glob("*.jpg"))
    )
    (out / "index.html").write_text(build(args.db, names))
    print(f"site written to {out} ({len(names)} images)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
