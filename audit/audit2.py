import json, os, glob, re
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
top = glob.glob(os.path.join(ROOT, "*", "*.jsonl"))
allf = glob.glob(os.path.join(ROOT, "**", "*.jsonl"), recursive=True)
nested = [f for f in allf if f not in set(top)]
nested_dirs = Counter(os.path.basename(os.path.dirname(f)) for f in nested)

review_samples = []
sess_stats = []   # (file, last_ctx, cache_read_sum, out_tok, n_user, dur_min, first)
for f in top:
    last_ctx = 0; cr = 0; out = 0; nu = 0; first = None; t0=None; t1=None
    model_ctx_peak = 0
    with open(f, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try: d = json.loads(line)
            except: continue
            ts = d.get("timestamp")
            if ts:
                if t0 is None: t0 = ts
                t1 = ts
            t = d.get("type")
            if t == "user":
                m = d.get("message", {})
                c = m.get("content")
                txt = c if isinstance(c,str) else " ".join(x.get("text","") for x in c if isinstance(x,dict) and x.get("type")=="text") if isinstance(c,list) else ""
                if not txt.strip() or d.get("isMeta") or txt.startswith("<"): continue
                if isinstance(c,list) and any(isinstance(x,dict) and x.get("type")=="tool_result" for x in c): continue
                nu += 1
                if first is None:
                    first = txt[:200]
                    if txt.strip().lower().startswith("review") and len(review_samples)<12:
                        review_samples.append(txt[:200].replace("\n"," "))
            elif t == "assistant":
                u = (d.get("message") or {}).get("usage") or {}
                ctx = (u.get("input_tokens",0) or 0)+(u.get("cache_read_input_tokens",0) or 0)+(u.get("cache_creation_input_tokens",0) or 0)
                if ctx > model_ctx_peak: model_ctx_peak = ctx
                cr += u.get("cache_read_input_tokens",0) or 0
                out += u.get("output_tokens",0) or 0
    dur = 0
    try:
        from datetime import datetime
        p = lambda s: datetime.fromisoformat(s.replace("Z","+00:00"))
        if t0 and t1: dur = (p(t1)-p(t0)).total_seconds()/60
    except: pass
    sess_stats.append((os.path.basename(f)[:12], model_ctx_peak, cr, out, nu, round(dur), (first or "")[:80].replace("\n"," ")))

sess_stats.sort(key=lambda x:-x[2])
peak_ctxs = sorted(s[1] for s in sess_stats)
def pct(l,p): return l[min(len(l)-1,int(p*len(l)))] if l else 0
over150k = sum(1 for c in peak_ctxs if c>150000)
over100k = sum(1 for c in peak_ctxs if c>100000)
base_heavy = sum(1 for c in peak_ctxs if c>40000 and c<200001)  # rough

print("nested file dirs (top 10):", nested_dirs.most_common(10))
print("nested total:", len(nested))
print("review first-prompt samples:")
for r in review_samples: print("  -", r)
print("peak context: median", pct(peak_ctxs,.5), "p90", pct(peak_ctxs,.9), "max", peak_ctxs[-1])
print("sessions peak ctx >100k:", over100k, ">150k:", over150k, "of", len(peak_ctxs))
print("top 12 sessions by cache-read (id, peakctx, cache_read, out, userturns, mins, first):")
for s in sess_stats[:12]: print("  ", s)
# minimum context floor: peak ctx of one-turn trivial sessions
tiny = [s[1] for s in sess_stats if s[4]<=1 and s[3]<20000]
tiny.sort()
print("baseline ctx (1-turn small sessions): median", pct(tiny,.5), "min", tiny[0] if tiny else 0, "n:", len(tiny))
