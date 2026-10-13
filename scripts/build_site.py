"""Build the interactive static audit-report site for kozquloq.vercel.app.

Usage:
    uv run python scripts/build_site.py --db data/kozquloq.duckdb \
        --dataroot v1.0-mini --out site_out

Reads the audit DB for summary/slice/token stats, renders up to --max-images
flagged-frame overlays from the dataset, and writes a single self-contained
index.html (inline CSS/JS, no external assets) plus img/*.jpg into --out.
Deploy with `vercel deploy --prod` inside the output dir.
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
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kozquloq - AV annotation lint report</title>
<style>
:root{--bg:#0b0f14;--card:#131a23;--card2:#1a2430;--border:#263241;--fg:#e8eef6;--dim:#8b9bb0;
--red:#f85149;--amber:#f0a732;--blue:#4d9fff;--green:#3fb950;--acc:#58a6ff;}
*{margin:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
nav{position:sticky;top:0;z-index:50;background:rgba(11,15,20,.85);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
nav .wrap{display:flex;align-items:center;gap:20px;padding:12px 20px}
nav b{font-size:16px;letter-spacing:.3px}nav .sp{flex:1}
nav a{color:var(--dim);text-decoration:none;font-size:13px}nav a:hover{color:var(--fg)}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
.hero{padding:56px 0 8px;display:flex;gap:40px;align-items:center;flex-wrap:wrap}
.hero h1{font-size:34px;letter-spacing:-.5px}
.hero .sub{color:var(--dim);max-width:560px;margin-top:8px}
.hero .sub b{color:var(--fg)}
.gauge{position:relative;width:150px;height:150px;flex-shrink:0}
.gauge svg{transform:rotate(-90deg)}
.gauge .gl{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.gauge .gl b{font-size:40px;line-height:1}
.gauge .gl span{color:var(--dim);font-size:11px;text-transform:uppercase}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:24px 0}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;transition:.2s}
.card:hover{border-color:var(--acc);transform:translateY(-2px)}
.card .v{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
.card .k{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.6px;margin-top:2px}
h2{margin:44px 0 6px;font-size:20px;letter-spacing:-.2px}
.lede{color:var(--dim);font-size:14px;margin-bottom:14px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin:12px 0 8px;font-size:13px}
th,td{padding:9px 14px;text-align:left;border-bottom:1px solid var(--border)}
th{background:var(--card2);color:var(--dim);text-transform:uppercase;font-size:11px;letter-spacing:.5px;cursor:pointer;user-select:none;white-space:nowrap}
th:hover{color:var(--fg)}th .ar{color:var(--acc);font-size:9px}
tbody tr{transition:background .15s}tbody tr:hover{background:var(--card2)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.bar{height:6px;background:var(--card2);border-radius:3px;overflow:hidden;min-width:70px}
.bar i{display:block;height:100%;border-radius:3px}
.gal{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.gal figure{cursor:zoom-in;margin:0}
.gal img{width:100%;border-radius:10px;border:1px solid var(--border);display:block;transition:.2s}
.gal img:hover{border-color:var(--acc)}
.gal figcaption{color:var(--dim);padding:6px 2px 0;display:flex;justify-content:space-between;align-items:center}
.tagpill{font-size:10px;padding:2px 8px;border-radius:99px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.tg-ghost{background:rgba(248,81,73,.15);color:var(--red);border:1px solid rgba(248,81,73,.4)}
.tg-kin{background:rgba(240,167,50,.15);color:var(--amber);border:1px solid rgba(240,167,50,.4)}
.tg-scale{background:rgba(77,159,255,.15);color:var(--blue);border:1px solid rgba(77,159,255,.4)}
.lb{position:fixed;inset:0;background:rgba(0,0,0,.9);display:none;align-items:center;justify-content:center;z-index:100;cursor:zoom-out}
.lb.open{display:flex}.lb img{max-width:94vw;max-height:92vh;border-radius:8px}
.pipe{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:16px 0}
.step{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;position:relative}
.step .n{color:var(--acc);font-size:12px;font-weight:700;letter-spacing:1px}
.step b{display:block;margin:6px 0 4px;font-size:14px}
.step p{color:var(--dim);font-size:12.5px}
.step::after{content:"→";position:absolute;right:-13px;top:45%;color:var(--acc);font-size:16px;z-index:1}
.step:last-child::after{display:none}
.checks{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.chk{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;border-top:3px solid var(--green)}
.chk.red{border-top-color:var(--red)}.chk.amber{border-top-color:var(--amber)}.chk.blue{border-top-color:var(--blue)}
.chk b{font-size:14px}.chk p{color:var(--dim);font-size:12.5px;margin-top:6px}
.chk code{color:var(--acc);font-size:11px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.chip{background:var(--card);border:1px solid var(--border);color:var(--dim);border-radius:99px;padding:5px 14px;font-size:12px;cursor:pointer;transition:.15s}
.chip.on,.chip:hover{border-color:var(--acc);color:var(--fg)}
.chip.on{background:var(--card2)}
input[type=search]{background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--fg);padding:8px 14px;font-size:13px;width:240px;outline:none}
input[type=search]:focus{border-color:var(--acc)}
.cmd{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 20px;font-family:ui-monospace,Menlo,monospace;font-size:13px;overflow-x:auto;white-space:pre;line-height:1.8}
.cmd .cm{color:var(--dim)}
a{color:var(--acc)}
.foot{color:var(--dim);font-size:12px;margin:44px 0 40px;border-top:1px solid var(--border);padding-top:20px}
.reveal{opacity:0;transform:translateY(14px);transition:opacity .5s,transform .5s}
.reveal.vis{opacity:1;transform:none}
.tcount{color:var(--dim);font-size:12px;margin:6px 0}
@media(max-width:640px){.hero{padding:36px 0 4px}.step::after{display:none}}
</style></head><body>
<nav><div class="wrap"><b>Kozquloq</b><div class="sp"></div>
<a href="#how">How it works</a><a href="#slices">Slices</a><a href="#frames">Frames</a><a href="#tokens">Mask</a>
<a href="https://github.com/unnobatroo/kozquloq">GitHub ↗</a></div></nav>
<div class="wrap">
<div class="hero">
<div class="gauge"><svg width="150" height="150" viewBox="0 0 150 150">
<circle cx="75" cy="75" r="64" fill="none" stroke="#263241" stroke-width="11"/>
<circle id="arc" cx="75" cy="75" r="64" fill="none" stroke="__GC__" stroke-width="11"
 stroke-linecap="round" stroke-dasharray="402" stroke-dashoffset="402"/>
</svg><div class="gl"><b style="color:__GC__">__GRADE__</b><span>health grade</span></div></div>
<div><h1>AV annotation lint report</h1>
<p class="sub"><b>nuScenes v1.0-mini</b> audited for ghost labels (boxes with zero LiDAR
returns), non-physical kinematics, and volume instability. __FLAGGED__ of
__ANNS__ annotations failed - __FAILPCT__%. Static snapshot generated by
<code>kozquloq scan</code>.</p></div>
</div>
<div class="grid reveal">
<div class="card"><div class="v" data-n="__FRAMES__">0</div><div class="k">Frames</div></div>
<div class="card"><div class="v" data-n="__ANNS__">0</div><div class="k">Annotations</div></div>
<div class="card"><div class="v" style="color:var(--red)" data-n="__GHOSTS__">0</div><div class="k">Ghost labels</div></div>
<div class="card"><div class="v" style="color:var(--amber)" data-n="__KIN__">0</div><div class="k">Kinematic</div></div>
<div class="card"><div class="v" style="color:var(--blue)" data-n="__SCALE__">0</div><div class="k">Scale unstable</div></div>
<div class="card"><div class="v" data-n="__BADFRAMES__">0</div><div class="k">Frames w/ flags</div></div>
</div>

<h2 id="how" class="reveal">How it works</h2>
<div class="pipe reveal">
<div class="step"><div class="n">01 INGEST</div><b>nuScenes sensor logs</b><p>Keyframes, LiDAR sweeps, camera images, calibration and ego poses - fused via timestamp-aware SE(3) transforms.</p></div>
<div class="step"><div class="n">02 GEOMETRY</div><b>Occupancy check</b><p>Ground plane removed (z &lt; -2.0 m), then every box is tested with devkit <code>points_in_box</code>. Rigid/movable class + &lt;35 m + 0 points = ghost.</p></div>
<div class="step"><div class="n">03 KINEMATICS</div><b>Trajectory audit</b><p>Per-instance velocity and acceleration from frame deltas; volume stability per rigid object. Ped &gt;8 m/s², vehicle &gt;12 m/s², ΔV &gt;15%.</p></div>
<div class="step"><div class="n">04 EXPORT</div><b>Mask + overlays</b><p>Invalid annotation tokens land in a Parquet/JSON mask for training; flagged frames get annotated JPEG overlays.</p></div>
</div>
<div class="checks reveal">
<div class="chk red"><b>Ghost label</b><p>Annotator drew a box where LiDAR recorded nothing. Model learns hallucinated objects.<br><code>severity 0.55 - masked out</code></p></div>
<div class="chk amber"><b>Kinematic outlier</b><p>Acceleration beyond physics: tracking-ID hops or jittered centers.<br><code>severity 0.25 - downweighted</code></p></div>
<div class="chk blue"><b>Scale unstable</b><p>Rigid object volume changes &gt;15% between frames.<br><code>severity 0.20 - downweighted</code></p></div>
<div class="chk"><b>Verified</b><p>LiDAR returns inside the box, plausible motion, stable size.<br><code>severity 0.00 - keep</code></p></div>
</div>

<h2 id="slices" class="reveal">Failure rate by slice</h2>
<p class="lede reveal">Click a column header to sort. Higher failure rate = that slice carries more annotation noise.</p>
<table id="sliceTab" class="reveal"><thead><tr>
<th>Weather</th><th>Time</th><th>Category</th><th>N</th><th>Ghosts</th><th>Kinematic</th><th>Avg pts</th><th>Fail %</th>
</tr></thead><tbody>__SLICE_ROWS__</tbody></table>

<h2 id="frames" class="reveal">Flagged frames</h2>
<p class="lede reveal">Annotated overlays - click to zoom. Red = ghost, green = verified.</p>
<div class="gal reveal">__GALLERY__</div>

<h2 id="tokens" class="reveal">Invalid-token mask</h2>
<p class="lede reveal">The export payload - <span id="tokN">__TOKCOUNT__</span> tokens to exclude from training. Search or filter by reason.</p>
<div class="filters reveal">
<input type="search" id="tokSearch" placeholder="Search token or category...">
<button class="chip on" data-f="">all</button>
<button class="chip" data-f="ghost">ghost</button>
<button class="chip" data-f="kinematic">kinematic</button>
<button class="chip" data-f="scale">scale</button>
</div>
<table class="reveal"><thead><tr><th>Token</th><th>Category</th><th>Severity</th><th>Reason</th></tr></thead>
<tbody id="tokBody"></tbody></table>
<p class="tcount" id="tokCount"></p>

<h2 class="reveal">Reproduce</h2>
<div class="cmd reveal"><span class="cm"># install and audit</span>
pip install kozquloq
kozquloq scan --dataroot &lt;nuScenes-root&gt; --db audit.duckdb --viz-dir viz_out
<span class="cm"># export the training mask</span>
kozquloq export --db audit.duckdb --output mask.parquet --min-severity 0.5</div>
<p class="foot">Severity ≥0.5 tokens are masked out of training; lower severities are
downweighted in <code>QualityAuditDataset</code>. Overlay colors: green verified,
red ghost, amber kinematic, blue scale. GPL-3.0 - generated snapshot, not live.</p>
</div>
<div class="lb" id="lb"><img id="lbImg" alt="overlay"></div>
<script type="application/json" id="tokData">__TOKJSON__</script>
<script>
const TOK=JSON.parse(document.getElementById('tokData').textContent);
const body=document.getElementById('tokBody'),cnt=document.getElementById('tokCount');
let q='',f='';
function draw(){
 const rows=TOK.filter(r=>(!f||r.reason.startsWith(f))&&(!q||(r.annotation_token+r.category).toLowerCase().includes(q)));
 body.innerHTML=rows.map(r=>`<tr><td class="mono">${r.annotation_token.slice(0,12)}…</td><td>${r.category}</td><td>${r.severity.toFixed(2)}</td><td>${r.reason}</td></tr>`).join('');
 cnt.textContent=`${rows.length} of ${TOK.length} tokens`;
}
draw();
document.getElementById('tokSearch').addEventListener('input',e=>{q=e.target.value.toLowerCase();draw()});
document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{
 document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));c.classList.add('on');f=c.dataset.f;draw()}));
// sortable slice table
document.querySelectorAll('#sliceTab th').forEach((th,i)=>th.addEventListener('click',()=>{
 const tb=document.querySelector('#sliceTab tbody'),rows=[...tb.rows],num=i>2;
 rows.sort((a,b)=>{const x=a.cells[i].textContent,y=b.cells[i].textContent;
  return num?parseFloat(x)-parseFloat(y):x.localeCompare(y)});
 if(th.dataset.d==='d'){rows.reverse();th.dataset.d='a'}else th.dataset.d='d';
 tb.append(...rows);
 document.querySelectorAll('#sliceTab .ar').forEach(e=>e.remove());
 th.insertAdjacentHTML('beforeend',' <span class="ar">'+(th.dataset.d==='d'?'▼':'▲')+'</span>')}));
// count-up + gauge arc
const io=new IntersectionObserver(es=>es.forEach(e=>{
 if(!e.isIntersecting)return;e.target.classList.add('vis');
 e.target.querySelectorAll('[data-n]').forEach(el=>{
  const t=+el.dataset.n,t0=performance.now();
  const tick=n=>{const p=Math.min(1,(n-t0)/900);el.textContent=Math.round(t*(1-Math.pow(1-p,3))).toLocaleString();if(p<1)requestAnimationFrame(tick)};
  requestAnimationFrame(tick)});
 io.unobserve(e.target)}),{threshold:.2});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
const arc=document.getElementById('arc'),P=__FAILPCTRAW__;
setTimeout(()=>{arc.style.transition='stroke-dashoffset 1.1s cubic-bezier(.22,1,.36,1)';
 arc.style.strokeDashoffset=402*(1-Math.min(P,100)/100)},300);
// lightbox
const lb=document.getElementById('lb'),li=document.getElementById('lbImg');
document.querySelectorAll('.gal img').forEach(im=>im.addEventListener('click',()=>{li.src=im.src;lb.classList.add('open')}));
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

    # flag tags per rendered image (filename stem = sample_token)
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

    slice_rows = "".join(
        f"<tr><td>{esc(r['weather'])}</td><td>{esc(r['time_of_day'])}</td>"
        f"<td>{esc(r['category'])}</td><td>{r['total_annotations']}</td>"
        f"<td>{r['ghost_labels_count']}</td><td>{r['kinematic_outliers_count']}</td>"
        f"<td>{r['avg_lidar_points']}</td><td>{r['failure_rate_pct']}%</td></tr>"
        for r in slices
    )

    def pill(name: str) -> str:
        tok = name.removesuffix(".jpg")
        r = flags.get(tok) or {}
        kinds = [("ghost", r.get("g")), ("kinematic", r.get("k")), ("scale", r.get("sc"))]
        tags = " ".join(
            f"<span class='tagpill tg-{k if k != 'kinematic' else 'kin'}'>{k}</span>"
            for k, on in kinds
            if on
        )
        return (
            f"<figure><img src='img/{esc(name)}' loading='lazy' alt='overlay'/>"
            f"<figcaption><span class='mono'>{esc(name[:8])}</span>{tags}</figcaption></figure>"
        )

    gallery = "".join(pill(n) for n in img_names)
    grade_color = {
        "A": "#3fb950",
        "B": "#84cc16",
        "C": "#eab308",
        "D": "#f97316",
        "F": "#f85149",
    }[s["grade"]]

    page = PAGE
    for k, v in {
        "__GC__": grade_color,
        "__GRADE__": s["grade"],
        "__FLAGGED__": f"{s['flagged']:,}",
        "__ANNS__": s["annotations"],
        "__FAILPCT__": s["failure_pct"],
        "__FAILPCTRAW__": s["failure_pct"],
        "__FRAMES__": s["frames"],
        "__GHOSTS__": s["ghosts"],
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
