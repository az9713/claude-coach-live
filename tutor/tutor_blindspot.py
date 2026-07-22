"""Living Claude Tutor - P8 quarterly blind-spot pass (SPEC.html piece P8).
The weekly loop normalizes its own blind spots: whatever it consistently overlooks
becomes invisible to it. Quarterly, audit the TUTOR ITSELF - not the user:
assemble an aggregates-only package (TUTOR-MODEL.md + rules.json + last 4 weekly
snapshots) -> one Sonnet call asking "what does this model of the user NOT see?"
-> findings to reports/, proposals to pending-proposals.json. Human-approved, as ever.

Usage: python tutor_blindspot.py [--no-llm]
--no-llm still writes the input package (reports/blindspot-input-<Q>.md) so you can
run the interactive blind-spot-pass skill on it by hand instead. Stdlib only.
"""
import glob, json, os, sys, time

TUTOR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TUTOR)
from tutor_weekly import (call_claude, parse_proposals, model_file, UNTRUSTED,  # noqa: E402
                          SNAPDIR, REPORTDIR, PENDING, MODELFILE, RULESFILE)

QUARTER = "%s-Q%d" % (time.strftime("%Y"), (time.localtime().tm_mon - 1) // 3 + 1)

PROMPT = UNTRUSTED + """You are the QUARTERLY BLIND-SPOT AUDITOR of a 'living tutor' that coaches a \
Claude Code user out of wasteful usage habits. Your subject is THE TUTOR ITSELF, not the user. \
The weekly loop normalizes its own blind spots - whatever its metrics consistently overlook has \
become invisible to it. Your job is to reset the frame. Be terse and concrete.

THE TUTOR'S CURRENT MODEL OF THE USER (TUTOR-MODEL.md):
%s

ITS ACTIVE RULE FILE (rules.json):
%s

ITS LAST %d WEEKLY SNAPSHOTS (every metric it knows how to compute):
%s

Work through, in order:
1. STACK MAP: sketch the full space of Claude Code cost/quality waste (context, prompting, tooling,
   orchestration, config, cross-session, model choice). Mark each region COVERED or BLIND given the
   metrics above.
2. MEASUREMENT ARTIFACTS: what does the tutor systematically miss BECAUSE of how it measures?
   (streaming counters, weekly aggregation, main-transcripts-only, threshold framing, survivorship.)
3. STALE BELIEFS: which entries in the model/rules look wrong, outdated, or never re-validated?
4. RAT-HOLES: where could the tutor waste effort on metrics that sound useful but change no behavior?
5. HIGH-YIELD UNASKED QUESTIONS: the 3 questions this audit should ask next quarter, each with a
   concretely computable sensor spec (from transcript JSONL, stdlib only).

Then ONE fenced ```json block:
{"blind_spots": [{"region": "...", "why_invisible": "...", "evidence": "..."}],
 "proposals": [{"id": "...", "kind": "regex|context_threshold|prompt_length|weekly_metric",
                "pattern_or_threshold": "...", "message": "...", "rationale": "..."}],
 "retire": ["rule-id"],
 "unasked": [{"question": "...", "sensor_spec": "..."}]}
(empty arrays if none)."""


def build_package():
    snaps = sorted(glob.glob(os.path.join(SNAPDIR, "*.json")))[-4:]
    snap_txt = "\n\n".join("=== %s ===\n%s" % (os.path.basename(f),
                           open(f, encoding="utf-8").read()) for f in snaps) or "(none yet)"
    try:
        rules_txt = open(RULESFILE, encoding="utf-8").read()
    except OSError:
        rules_txt = "(missing)"
    return model_file(), rules_txt, len(snaps), snap_txt


def main():
    no_llm = "--no-llm" in sys.argv
    model, rules_txt, n, snap_txt = build_package()

    inp = os.path.join(REPORTDIR, "blindspot-input-%s.md" % QUARTER)
    with open(inp, "w", encoding="utf-8") as f:
        f.write("# Blind-spot pass input - %s\n\n## TUTOR-MODEL.md\n%s\n"
                "\n## rules.json\n```json\n%s\n```\n\n## Last %d weekly snapshots\n%s\n"
                % (QUARTER, model, rules_txt, n, snap_txt))
    print("[1/3] input package: %s" % inp)

    if no_llm:
        print("[2/3] --no-llm: skipping audit call")
        print("[3/3] run it by hand instead: open a Claude session and invoke the "
              "blind-spot-pass skill on the package file above.")
        return

    print("[2/3] blind-spot audit call (sonnet)...")
    out, err = call_claude(PROMPT % (model, rules_txt, n, snap_txt), "sonnet", timeout=900)
    if err:
        print("error: %s" % err)
        with open(MODELFILE, "a", encoding="utf-8") as f:
            f.write("- %s: blind-spot pass %s FAILED (%s)\n"
                    % (time.strftime("%Y-%m-%d"), QUARTER, err[:120]))
        return

    rpt = os.path.join(REPORTDIR, "blindspot-%s.md" % QUARTER)
    with open(rpt, "w", encoding="utf-8") as f:
        f.write("# Blind-spot pass - %s\n\n%s\n" % (QUARTER, out))

    pend = []
    try:
        pend = json.load(open(PENDING, encoding="utf-8"))
    except Exception:
        pass
    payload = parse_proposals(out)
    if payload:
        pend.append({"week": QUARTER, "source": "blindspot", "payload": payload})
        with open(PENDING, "w", encoding="utf-8") as f:
            json.dump(pend, f, indent=1)

    with open(MODELFILE, "a", encoding="utf-8") as f:
        f.write("- %s: blind-spot pass %s (%s blind spots, %s proposals pending review)\n"
                % (time.strftime("%Y-%m-%d"), QUARTER,
                   len(payload.get("blind_spots", [])), len(payload.get("proposals", []))))
    print("[3/3] report: %s (proposals pending - nothing auto-applied)" % rpt)


if __name__ == "__main__":
    main()
