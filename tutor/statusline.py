"""Living Claude Tutor - P2 ambient statusline (SPEC.html piece P2).
statusLine command: reads Claude Code's statusline JSON on stdin, prints one line:
    ctx ~142k YELLOW · Opus 4.8 · $2.31 · nudges wk: 3
Zero tokens ever - runs client-side. Reuses P1's context estimate and thresholds
(rules.json is the single source of truth). Fail-safe: never break the statusline.
"""
import json, os, sys, time

TUTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TUTOR)
from tutor_hook import context_estimate, load  # noqa: E402


def grade(ctx):
    """Traffic-light from active context_threshold rules; defaults 150k/300k."""
    ts = sorted(r["threshold"] for r in load(os.path.join(TUTOR, "rules.json"), {})
                .get("rules", [])
                if r.get("kind") == "context_threshold" and r.get("status") == "active")
    ts = ts or [150000, 300000]
    if ctx > ts[-1]:
        return "\U0001f534"  # red: god-session territory
    if ctx > ts[0]:
        return "\U0001f7e1"  # yellow: nudge threshold crossed
    return "\U0001f7e2"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    brief = "--brief" in sys.argv  # for embedding in an existing statusline script
    data = json.load(sys.stdin)
    ctx = context_estimate(data.get("transcript_path") or "")
    week = time.strftime("%G-W%V")
    fires = sum(load(os.path.join(TUTOR, "state.json"), {})
                .get("counters", {}).get(week, {}).values())
    if brief:
        print("%s nudges:%d" % (grade(ctx), fires))
        return
    model = ((data.get("model") or {}).get("display_name") or "").strip()
    cost = (data.get("cost") or {}).get("total_cost_usd")

    parts = ["ctx ~%dk %s" % (round(ctx / 1000), grade(ctx))]
    if model:
        parts.append(model)
    if isinstance(cost, (int, float)) and cost > 0:
        parts.append("$%.2f" % cost)
    parts.append("nudges wk: %d" % fires)
    print(" · ".join(parts))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("tutor: -")  # fail-safe placeholder; never crash the statusline
    sys.exit(0)
