import json, os, glob, re, sys
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
files = glob.glob(os.path.join(ROOT, "*", "*.jsonl"))

tool_counts = Counter()
bash_first_tokens = Counter()
bash_antipattern = Counter()          # cat/find/grep/echo/head/tail via Bash
model_counts = Counter()
user_msg_len_buckets = Counter()
short_user_msgs = Counter()           # exact text of tiny prompts
interrupt_count = 0
api_error_count = 0
sessions = []                          # per-session dicts
slash_cmds = Counter()
read_repeats_total = 0                # same file Read 2+ times in one session
sequential_read_sessions = 0
compact_events = 0
sidechain_files = 0
paste_msgs = 0                        # user msgs >8k chars
total_out_tokens = 0
total_in_tokens = 0
total_cache_read = 0
total_cache_create = 0
per_project = defaultdict(lambda: [0,0])   # sessions, output tokens

for f in files:
    proj = os.path.basename(os.path.dirname(f))
    s = {"proj": proj, "user_turns": 0, "asst": 0, "tools": 0, "out_tok": 0,
         "first": None, "start": None, "end": None, "task_calls": 0,
         "interrupts": 0, "models": set()}
    reads_this = Counter()
    sidechain = False
    try:
        fh = open(f, encoding="utf-8", errors="replace")
    except OSError:
        continue
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            t = d.get("type")
            if d.get("isSidechain"):
                sidechain = True
            ts = d.get("timestamp")
            if ts:
                if s["start"] is None: s["start"] = ts
                s["end"] = ts
            if t == "summary" or d.get("isCompactSummary"):
                compact_events += 1
            if t == "user":
                m = d.get("message", {})
                c = m.get("content")
                if isinstance(c, str):
                    txt = c
                elif isinstance(c, list):
                    txt = " ".join(x.get("text","") for x in c if isinstance(x,dict) and x.get("type")=="text")
                else:
                    txt = ""
                if "[Request interrupted by user" in txt:
                    interrupt_count += 1; s["interrupts"] += 1
                    continue
                if d.get("isMeta") or txt.startswith("<") or not txt.strip():
                    continue
                if isinstance(c, list) and any(isinstance(x,dict) and x.get("type")=="tool_result" for x in c):
                    continue
                s["user_turns"] += 1
                if s["first"] is None:
                    s["first"] = txt[:120]
                L = len(txt)
                if L > 8000: paste_msgs += 1
                b = "<50" if L<50 else "<200" if L<200 else "<1k" if L<1000 else "<8k" if L<8000 else "8k+"
                user_msg_len_buckets[b] += 1
                st = txt.strip()
                if L < 40:
                    short_user_msgs[st.lower()] += 1
                if st.startswith("/"):
                    slash_cmds[st.split()[0].lower()] += 1
            elif t == "assistant":
                m = d.get("message", {})
                s["asst"] += 1
                mo = m.get("model")
                if mo: model_counts[mo] += 1; s["models"].add(mo)
                u = m.get("usage") or {}
                ot = u.get("output_tokens",0)
                s["out_tok"] += ot
                total_out_tokens += ot
                total_in_tokens += u.get("input_tokens",0)
                total_cache_read += u.get("cache_read_input_tokens",0) or 0
                total_cache_create += u.get("cache_creation_input_tokens",0) or 0
                for blk in (m.get("content") or []):
                    if isinstance(blk,dict) and blk.get("type")=="tool_use":
                        name = blk.get("name","?")
                        tool_counts[name] += 1
                        s["tools"] += 1
                        if name in ("Task","Agent"): s["task_calls"] += 1
                        inp = blk.get("input") or {}
                        if name == "Read":
                            fp = inp.get("file_path")
                            if fp: reads_this[fp] += 1
                        if name == "Bash":
                            cmd = (inp.get("command") or "").strip()
                            tok = cmd.split()[0] if cmd.split() else ""
                            tok = os.path.basename(tok)
                            bash_first_tokens[tok] += 1
                            m1 = re.match(r"^(cat|find|grep|echo|head|tail|ls|sed|awk)\b", cmd)
                            if m1: bash_antipattern[m1.group(1)] += 1
            elif t == "system" and "error" in str(d.get("content","")).lower():
                api_error_count += 1
    rr = sum(v-1 for v in reads_this.values() if v > 1)
    read_repeats_total += rr
    if sidechain: sidechain_files += 1
    else:
        sessions.append(s)
        per_project[proj][0] += 1
        per_project[proj][1] += s["out_tok"]

# session-level aggregates (main sessions only)
n = len(sessions)
one_turn = sum(1 for s in sessions if s["user_turns"] <= 1)
turns = sorted(s["user_turns"] for s in sessions)
outs = sorted(s["out_tok"] for s in sessions)
def pct(lst,p):
    return lst[min(len(lst)-1, int(p*len(lst)))] if lst else 0
task_users = sum(1 for s in sessions if s["task_calls"]>0)
interrupt_sessions = sum(1 for s in sessions if s["interrupts"]>0)
multi_model = sum(1 for s in sessions if len(s["models"])>1)

# first-prompt themes
first_words = Counter()
for s in sessions:
    if s["first"]:
        w = s["first"].strip().split()
        if w: first_words[w[0].lower()[:20]] += 1

print(json.dumps({
  "files_total": len(files), "main_sessions": n, "sidechain_files": sidechain_files,
  "one_turn_sessions": one_turn,
  "user_turns_median": pct(turns,.5), "user_turns_p90": pct(turns,.9), "user_turns_max": turns[-1] if turns else 0,
  "out_tok_median": pct(outs,.5), "out_tok_p90": pct(outs,.9), "out_tok_total": total_out_tokens,
  "in_tok_total": total_in_tokens, "cache_read_total": total_cache_read, "cache_create_total": total_cache_create,
  "tool_counts_top25": tool_counts.most_common(25),
  "bash_top20": bash_first_tokens.most_common(20),
  "bash_antipattern": dict(bash_antipattern),
  "models": dict(model_counts),
  "user_msg_len_buckets": dict(user_msg_len_buckets),
  "short_msgs_top25": [x for x in short_user_msgs.most_common(60) if x[1]>=8][:25],
  "slash_top20": slash_cmds.most_common(20),
  "interrupts_total": interrupt_count, "interrupt_sessions": interrupt_sessions,
  "read_repeats_total": read_repeats_total,
  "paste_msgs_8k": paste_msgs,
  "compact_events": compact_events,
  "sessions_using_subagents": task_users,
  "multi_model_sessions": multi_model,
  "projects_top15_by_outtok": sorted([(k,v[0],v[1]) for k,v in per_project.items()], key=lambda x:-x[2])[:15],
  "first_words_top20": first_words.most_common(20),
}, indent=1, default=str))
