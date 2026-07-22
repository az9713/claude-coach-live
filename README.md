# Living Claude Tutor

A self-extending habit coach for Claude Code usage. Born from an audit of 458 sessions
that found 12 "god sessions" accounted for ~49% of 13.25B lifetime cache-read tokens.

![The tutor at work: escalation nudge firing in a live 518k-token session — and being obeyed](tutor_at_work.jpg)

*Above: the tutor's zero-token hook catching a god session at 518k context tokens in the wild,
and the session's Claude complying — handoff, commit, then /clear.*

**Core principle — the compilation ladder:** expensive intelligence (LLM analysis) runs
rarely on small aggregates; its discoveries are compiled downward into zero-token
deterministic sensors (hooks, scripts) that run always.

## Contents

- `SPEC.html` — full specification: 9 pieces, motivation, implementation, cost model.
- `audit/` — one-off transcript audit scripts (stream ~/.claude/projects JSONL, emit aggregates only).
- `tutor/` — the tutor source (snapshot; the live install is a git repo at `~/.claude/tutor/`):
  - `tutor_hook.py` + `rules.json` — UserPromptSubmit hook. Zero tokens idle; one-line nudge
    when a rule fires (babysitting prompts, >150k/300k context, fat pastes, orphaned task lists).
  - `tutor_weekly.py` — weekly engine: stats snapshot → deltas (Sensor A) → owned-vs-used
    inventory (Sensor B) → stratified raw-trace discovery (Sensor C, the "unknown unknowns"
    pass) → Haiku/Sonnet analysis → HTML report card → pending proposals (human-approved,
    never auto-applied) → TUTOR-MODEL.md decision log.
  - `TUTOR-MODEL.md` — the living model: known habits, sensors, hypotheses, decisions.
  - `statusline.py` — P2 ambient cue: statusLine command rendering `ctx ~142k 🟡 · nudges wk: 3`.
    Zero tokens; reuses the hook's context estimate; thresholds come from rules.json.
  - `tutor_blindspot.py` — P8 quarterly blind-spot pass: audits the TUTOR itself
    ("what does this model of the user not see?") via one Sonnet call over aggregates;
    findings land in pending-proposals.json like everything else. `--no-llm` just builds
    the input package for a manual interactive run.
  - `test_p2p8.py` — stdlib self-check for the two pieces above.
  - `run_weekly.cmd` / `run_quarterly.cmd` — Windows scheduled-task wrappers.

## Install (Windows)

1. Copy `tutor/` to `%USERPROFILE%\.claude\tutor\`.
2. Wire the fast-loop hook into `~/.claude/settings.json` (merge into any existing `hooks` block):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"%USERPROFILE%\\.claude\\tutor\\tutor_hook.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

3. Register the weekly discovery run:

```
schtasks /Create /SC WEEKLY /D SUN /ST 18:00 /TN ClaudeTutorWeekly /TR "%USERPROFILE%\.claude\tutor\run_weekly.cmd"
```

4. (P2) Wire the ambient statusline. Two options:

   **a. Standalone** — point `~/.claude/settings.json` at the tutor script (replaces any
   existing `statusLine` block):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python \"%USERPROFILE%\\.claude\\tutor\\statusline.py\""
  }
}
```

   **b. Embed (used on the reference install)** — if you already have a statusline script
   you like, append the tutor's `--brief` output to it instead of replacing it:

```bash
# Living Claude Tutor (P2): threshold grade + nudges this week; silent on any failure
tutor=$(echo "$input" | python "$HOME/.claude/tutor/statusline.py" --brief 2>/dev/null)
[ -n "$tutor" ] && parts+=("$tutor")
```

### Reading the statusline (P2)

Example (embed mode, appended to an existing statusline):

```
| Fable 5 | effort:high | fable_5_maxxing_5 | ctx 15% | 5h 1% | 7d 89% | ~89k nudges:11 |
```

Everything before the last segment is the pre-existing statusline (model, reasoning
effort, working dir, Claude Code's own context-window %, 5-hour and 7-day rate-limit
usage). The tutor contributes only the last segment, which has two parts:

| part | meaning | source |
|---|---|---|
| `~89k` / `~158k !` / `~310k !!` | **this session's** estimated context, in tokens, with an ASCII escalation marker: no marker below 150k; ` !` past 150k (the nudge threshold — plan a handoff at the next natural pause); ` !!` past 300k (god-session territory — run handoff-after-clear, then `/clear`) | last `usage` block in the session transcript (input + cache_read + cache_creation), same estimate the P1 hook uses; thresholds read live from `rules.json`, so an approved threshold change re-marks the meter automatically |
| `nudges:11` | **all sessions, this ISO week**: total P1 rule fires (babysit prompts, god-session warnings, fat pastes, orphaned task lists) | `state.json` weekly counters |

The marker is deliberately ASCII, not a colored dot — it reads identically in a
color terminal, a monochrome one, and a piped log. The raw `~Nk` number carries the
information a traffic-light colour only hinted at: you see *how far* into the session
you are, not just which band.

So `~89k nudges:11` reads: *"this session is fine (89k, well under threshold), but the
tutor has had to speak up 11 times across all sessions this week."* A high count with an
unmarked, low `~Nk` means the waste is happening in *other* sessions — the weekly report
card breaks down which rules fired. Note the tutor's `~Nk` and Claude Code's own `ctx %`
can disagree slightly: they use different accounting (the tutor counts raw transcript
usage; Claude Code reports usable-window percentage after reserved buffers). Trust
either — they converge where it matters.

Standalone mode renders the full form instead: `ctx ~201k ! · Opus 4.8 · $2.31 · nudges wk: 3`.

5. (P8) Register the quarterly blind-spot pass (1st of Jan/Apr/Jul/Oct, 18:30):

```
schtasks /Create /SC MONTHLY /MO 3 /D 1 /ST 18:30 /TN ClaudeTutorBlindspot /TR "%USERPROFILE%\.claude\tutor\run_quarterly.cmd"
```

Test both without spending tokens: `python test_p2p8.py`.

6. Requires Python 3.x (stdlib only) and the `claude` CLI on PATH for the weekly LLM sensors.
   Test without spending tokens: `python tutor_weekly.py --no-llm`.

Optional (recommended): tame Claude Code's own background security-review fleet by adding to
the `env` block of `~/.claude/settings.json` — this was 44% of all sessions in the original audit:

```json
"ENABLE_STOP_REVIEW": "0",
"SECURITY_REVIEW_MODEL": "claude-sonnet-4-6"
```

Runtime state (`state.json`, `snapshots/`, `reports/`, `pending-proposals.json`) is
machine-local and not part of this repo.

Built with Claude Code (Fable 5), 2026-07-21.
