"""Self-check for P2 (statusline) and P8 (blind-spot pass, --no-llm path).
Run: python test_p2p8.py  -> prints OK or throws. Stdlib only, no framework."""
import json, os, subprocess, sys, tempfile

TUTOR = os.path.dirname(os.path.abspath(__file__))


def run(script, stdin_text=None, args=()):
    p = subprocess.run([sys.executable, os.path.join(TUTOR, script), *args],
                       input=stdin_text, capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    return p.returncode, p.stdout


# --- P2: statusline renders ctx + grade + nudge counter from a fake transcript ---
usage_line = json.dumps({"type": "assistant", "message": {"usage": {
    "input_tokens": 1000, "cache_read_input_tokens": 200000,
    "cache_creation_input_tokens": 0, "output_tokens": 5}}})
with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                 encoding="utf-8") as f:
    f.write(usage_line + "\n")
    fake_transcript = f.name
try:
    code, out = run("statusline.py", json.dumps({
        "transcript_path": fake_transcript,
        "model": {"display_name": "TestModel"},
        "cost": {"total_cost_usd": 1.5}}))
    assert code == 0, "statusline must always exit 0"
    assert "ctx ~201k !" in out and "!!" not in out, \
        "201k should mark single ! (>150k, <300k): %r" % out
    assert "TestModel" in out and "$1.50" in out and "nudges wk:" in out, out

    # --brief mode for embedding in an existing statusline script
    code, out = run("statusline.py", json.dumps({"transcript_path": fake_transcript}),
                    args=("--brief",))
    assert code == 0 and "~201k !" in out and "nudges:" in out, out

    # garbage stdin must not crash it (fail-safe contract)
    code, out = run("statusline.py", "not json at all")
    assert code == 0 and out.strip(), "fail-safe broken: %r" % out
finally:
    os.unlink(fake_transcript)

# --- P8: --no-llm builds the input package and spends zero tokens ---
code, out = run("tutor_blindspot.py", args=("--no-llm",))
assert code == 0, out
assert "input package:" in out and "skipping audit call" in out, out
pkg = out.split("input package:", 1)[1].splitlines()[0].strip()
assert os.path.isfile(pkg), "package file missing: %s" % pkg
txt = open(pkg, encoding="utf-8").read()
assert "TUTOR-MODEL.md" in txt and "rules.json" in txt, "package incomplete"

print("OK - P2 statusline + P8 blind-spot (--no-llm) self-checks passed")
