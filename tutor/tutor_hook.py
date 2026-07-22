"""Living Claude Tutor - fast loop (P1).
UserPromptSubmit hook: zero tokens idle, one-line nudge when a rule fires.
Rules are data (rules.json); this file should rarely change.
Fail-safe: any error exits 0 silently - never break prompting.
"""
import json, os, re, sys, time

TUTOR = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(TUTOR, "rules.json")
STATE = os.path.join(TUTOR, "state.json")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def context_estimate(transcript_path):
    """Context size proxy: last assistant usage block in the transcript tail."""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            f.seek(max(0, size - 262144))
            tail = f.read().decode("utf-8", errors="replace")
        for line in reversed(tail.splitlines()):
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            u = (d.get("message") or {}).get("usage") or {}
            ctx = ((u.get("input_tokens") or 0)
                   + (u.get("cache_read_input_tokens") or 0)
                   + (u.get("cache_creation_input_tokens") or 0))
            if ctx:
                return ctx
    except Exception:
        pass
    return 0


def orphaned_taskcreate(transcript_path):
    """True if the last TaskCreate has no TaskUpdate after it and the session
    has moved on (8+ assistant messages since) - a dead task list."""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            f.seek(max(0, size - 1048576))
            tail = f.read().decode("utf-8", errors="replace")
        last_create = max((m.end() for m in
                           re.finditer(r'"name"\s*:\s*"TaskCreate"', tail)), default=-1)
        if last_create < 0:
            return False
        after = tail[last_create:]
        if re.search(r'"name"\s*:\s*"TaskUpdate"', after):
            return False
        return len(re.findall(r'"type"\s*:\s*"assistant"', after)) >= 8
    except Exception:
        return False


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = json.load(sys.stdin)
    prompt = data.get("prompt") or ""
    transcript = data.get("transcript_path") or ""
    session = data.get("session_id") or "?"

    rules = load(RULES, {}).get("rules", [])
    state = load(STATE, {"fires": [], "counters": {}})
    now = time.time()
    week = time.strftime("%G-W%V")
    ctx = None  # computed lazily, once
    nudges = []

    for r in rules:
        if r.get("status") != "active":
            continue
        rid = r["id"]
        # cooldown: don't re-fire the same rule within cooldown_min (per session)
        last = next((f for f in reversed(state["fires"])
                     if f["rule"] == rid and f["session"] == session), None)
        if last and now - last["t"] < 60 * r.get("cooldown_min", 10):
            continue

        kind = r.get("kind")
        hit = False
        if kind == "regex":
            hit = re.search(r["pattern"], prompt.strip(), re.IGNORECASE) is not None
        elif kind == "prompt_length":
            hit = len(prompt) > r["threshold"]
        elif kind == "context_threshold":
            if ctx is None:
                ctx = context_estimate(transcript)
            hit = ctx > r["threshold"]
        elif kind == "orphan_taskcreate":
            hit = orphaned_taskcreate(transcript)
            # escalation rules suppress their milder sibling via 'suppresses'
        if not hit:
            continue

        wk = state["counters"].setdefault(week, {})
        wk[rid] = wk.get(rid, 0) + 1
        state["fires"].append({"rule": rid, "session": session, "t": now})
        msg = r["message"].replace("{count}", str(wk[rid]))
        if ctx is not None:
            msg = msg.replace("{ctx_k}", str(round(ctx / 1000)))
        nudges.append((r.get("priority", 5), rid, msg))

    if nudges:
        # highest priority only; suppress milder context rule if escalation fired
        nudges.sort(key=lambda x: x[0])
        fired_ids = {n[1] for n in nudges}
        for r in rules:
            for sup in r.get("suppresses", []):
                if r["id"] in fired_ids:
                    fired_ids.discard(sup)
        chosen = [n for n in nudges if n[1] in fired_ids][:1]
        if chosen:
            print("<tutor-nudge>%s Surface this note verbatim to the user at the "
                  "top of your reply, then answer their prompt.</tutor-nudge>"
                  % chosen[0][2])

    state["fires"] = state["fires"][-2000:]
    try:
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
