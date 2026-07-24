# Living Claude Tutor — Specification v2: The 18-Waste Sensor Expansion

Status: **spec only — nothing implemented yet.** · 2026-07-22
Extends SPEC.html (v0.1). Design decisions locked during brainstorming 2026-07-22:
scope = **everything** (all 18 waste classes), wiring = **doctrine-pure** (no new
fast-loop rules on day one; sensors discover → evidence → pending proposal → human
approves → rule).

---

## 1. What changes, in one paragraph

v0.1 built a tutor that watches for five known-bad habits and reviews the week with
three sensors. v2 gives it **eyes for 18 waste classes** across four new/extended
sensor classes — and, critically, a **conscience**: Sensor F, a quality-guard layer
that pairs every cost metric with a quality counter-metric, so the tutor can prove
its own advice isn't making responses worse. The objective function changes from
*minimize tokens* to **maximize quality per token**.

```
Sensor A   (presence, EXTENDED)    — 12 new weekly counters from main transcripts
Sensor A'  (NEW: subagent scope)   — same pass over nested subagent/workflow transcripts
Sensor B   (absence, unchanged)    — owned-vs-used inventory
Sensor C   (out-of-model, unchanged) — stratified raw-trace discovery
Sensor D   (NEW: cross-session)    — wastes invisible inside any single transcript
Sensor E   (NEW: config drift)     — the config layer: startup toll, stale CLAUDE.md
Sensor F   (NEW: quality guard)    — counter-metrics + the obeyed-vs-ignored evaluator
```

Everything is stdlib Python streaming JSONL. Zero new LLM cost except a longer
weekly analyst prompt (~2–3k extra tokens/week).

---

## 2. The core principle: no cost metric without a counter-metric

The v0.1 tutor is a single-objective optimizer. Left alone, it would coach the user
into *cheap-but-worse*: clearing context that was earning its keep, cheap models on
hard tasks, batched prompts that get misread. v2's rule:

> **Every sensor that pushes cost down must name the Sensor F metric that would
> detect the quality damage its advice could cause. A proposal ships with both
> columns filled in, or it doesn't ship.**

---

## 3. Sensor F — the quality guard (described first, because everything else references it)

### Motivation (simple terms)
If the tutor tells you to spend fewer tokens, how do you know the answers didn't get
worse? You can't feel a 10% quality drop week to week. So the tutor measures quality
the same way it measures cost: from the transcripts, deterministically, for free.

### The five quality proxies

| metric | plain-language meaning | how it's computed (stdlib, per session) |
|---|---|---|
| `correction_rate` | how often you had to tell Claude it got it wrong | user turns matching a correction regex: `no[,.]? that('s| is) (wrong|not)`, `not what i (meant|asked)`, `still (failing|broken|wrong)`, `you broke`, `undo that`, `revert` — count ÷ user turns |
| `rework_thrash` | Claude editing the same file over and over = flailing | Edit/Write to a path within ≤4 assistant turns of a prior successful Edit/Write to the same path; count runs |
| `error_density` | how often tool calls blow up | tool_results flagged `is_error` ÷ total tool calls |
| `resume_friction` | after a /clear, did the next session have to re-learn everything? | joins Sensor D: files re-Read + questions re-asked in the first N turns of the successor session on the same project |
| `tokens_per_artifact` | the one true efficiency number | out_tokens ÷ durable artifacts (see §4.10 for the artifact definition) |

### The evaluator: obeyed-vs-ignored cohorts
`state.json` already logs every nudge fire (rule, session, timestamp). Weekly, the
tutor joins fires against transcripts and splits sessions into:

- **obeyed** — the nudged behavior happened (per-rule detector: god-session → context
  dropped/cleared within 3 turns of the fire; babysit → no further babysit prompts
  that session; fat-paste → no further >8k prompts; etc.)
- **ignored** — nudge fired, behavior continued.

Then it compares the two cohorts on the five quality proxies. Verdicts:

- **validated** — obeyed cohort no worse on quality, cheaper on tokens → rule keeps running; evidence noted in TUTOR-MODEL.md.
- **harmful** — obeyed cohort measurably worse (e.g. correction_rate up) → tutor auto-drafts a **retirement proposal** with the numbers. This extends v0.1's 30-day zero-fire retirement into **harm-based retirement**.
- **inconclusive** — small n; keep watching.

### Optional rigor: per-rule holdout
A rule may carry `"holdout_pct": 15` in rules.json. The fast-loop hook then rolls a
deterministic hash(session_id + rule_id); below the threshold it **suppresses the
nudge but logs a shadow fire**. This gives a genuine control group (nudge-eligible
but un-nudged) instead of self-selected cohorts. Zero tokens; slightly more
bookkeeping. OFF by default — enable per rule, by human approval, doctrine-pure.

### Counter-counter-metric (who guards the guard?)
`correction_rate` and friends are proxies and can be gamed or noisy. Sensor C's
weekly raw-trace read is the human-grade check: one of its three stratified picks is
re-weighted to prefer sessions where a nudge was obeyed, so a real LLM periodically
eyeballs whether "obeyed" sessions actually look healthy.

---

## 4. Sensor A extensions — 12 new weekly counters (main transcripts)

Each entry: **Motivation / Implementation / Quality counter.**

### 4.1 Model-mismatch (two-sided)
- **Motivation:** paying Opus prices for Haiku-shaped work is pure waste — but the
  reverse (Haiku flailing at Opus-shaped work, causing retries and corrections) is
  waste *plus* damage. v2 detects both directions.
- **Implementation:** per session: model mix (already counted) + complexity proxies
  (user turns, distinct tools, Edit/Write count, out_tokens).
  `frontier_trivial` = frontier model AND ≤2 turns AND 0 edits AND <2k out.
  `cheap_struggle` = cheap model AND (correction_rate ≥2 turns OR error_density > 0.2).
  Weekly counters for both + token totals attached.
- **Quality counter:** `correction_rate` in sessions that moved down-model after a
  (future, approved) nudge. A down-model rule is validated only if corrections don't rise.

### 4.2 Failed-command loops
- **Motivation:** the same failing command retried 3+ times burns turns and context;
  the fix is diagnosis, not repetition.
- **Implementation:** consecutive Bash/PowerShell tool_results with `is_error` where
  the command shares its first token. Runs ≥3 → `failed_cmd_loops` (count + longest run).
- **Quality counter:** `error_density` trend. A "stop retrying, diagnose" nudge is
  validated if error runs shorten without correction_rate rising.

### 4.3 Interrupted-generation waste
- **Motivation:** hitting Esc mid-answer throws away paid output tokens. Chronic
  interrupts usually mean prompts were underspecified to begin with.
- **Implementation:** interrupts already counted; add `interrupted_out_tokens` — the
  output_tokens of the assistant message immediately preceding each interrupt marker.
- **Quality counter:** interrupts are ambiguous — sometimes they're good steering.
  Only flag as waste when the interrupt is followed by a *rephrase of the same
  request* (normalized-prefix similarity to the pre-interrupt prompt). Never a live
  nudge without that qualifier.

### 4.4 Permission-prompt churn
- **Motivation:** every denied tool call is a wasted round-trip; repeated denials of
  the same command family is allowlist debt, not a behavior problem.
- **Implementation:** count tool_results carrying permission-denial markers; bucket
  by tool + command first-token. Metric `permission_denials` + top-10 denied prefixes.
  Output feeds a suggestion to run the fewer-permission-prompts skill.
- **Quality counter:** quality-neutral (config fix). Safety gate instead: the
  suggested allowlist additions must never include destructive command patterns —
  the report card marks them read-only-only.

### 4.5 Compaction thrash
- **Motivation:** compacting and then ballooning right back past 150k means you paid
  for the compaction *and* the god session. The habit survived the cure.
- **Implementation:** detect compaction events (compact-summary markers in the
  transcript), then check whether peak context after the event re-exceeds 150k.
  Metric `compact_thrash_sessions`.
- **Quality counter:** `resume_friction`. If post-compact work shows high
  re-derivation, the answer is *better handoffs*, not *more compaction* — the
  analyst is instructed to read these two together.

### 4.6 Verbose tool results
- **Motivation:** a 40k-character build log dumped into context pays rent on every
  subsequent turn of the session. Filtering at the source (head_limit, tail, grep)
  is nearly free.
- **Implementation:** tool_result content-length distribution; `fat_tool_results` =
  results >20k chars, with per-tool top offenders and an estimated token-rent figure
  (chars/4 × remaining turns).
- **Quality counter:** `correction_rate` — over-aggressive filtering can hide the
  one error line that mattered. A "trim your outputs" nudge is validated only if
  missed-error corrections don't rise in the obeyed cohort.

### 4.7 Speculative read fan-out
- **Motivation:** reading 20 files "for context" and using 3 is paying for 17
  tenants who never show up.
- **Implementation:** proxy: sessions with ≥15 Reads and ≤2 Edits. Refinement:
  fraction of Read basenames that never appear again in later assistant text or tool
  inputs. Metric `speculative_reads`.
- **Quality counter:** the dangerous inverse is under-reading → wrong edits. Any
  future "read less" nudge is validated only if `error_density` and
  `correction_rate` hold flat in the obeyed cohort. This is the sensor most likely
  to be **rejected** by its own quality gate — that's working as intended.

### 4.8 Plan-mode abandonment
- **Motivation:** a plan written and never executed is pure spend — either planning
  happened too early or the plan was too heavy.
- **Implementation:** ExitPlanMode approval observed, then session ends within ≤3
  further assistant turns with zero Edit/Write. Metric `abandoned_plans`.
- **Quality counter:** cross-session check first (Sensor D): the plan may execute in
  a *later* session. Only counted abandoned if no successor session on that project
  touches the planned files within the week.

### 4.9 Over-verification
- **Motivation:** re-reading a file right after editing it (the Edit tool already
  errors on failure), re-running tests when nothing changed — reflexive
  double-checking that costs real tokens.
- **Implementation:** Read of path P within ≤2 assistant turns of a successful
  Edit/Write to P → `verify_rereads`. Repeated identical test commands with no
  intervening file mutation → `redundant_test_runs`.
- **Quality counter:** `error_density` downstream. If suppressing verification lets
  broken code ship (corrections spike), the retirement pipeline kills the nudge.
  Verification of *non-trivial logic* is explicitly out of scope — this sensor only
  counts the mechanical double-checks.

### 4.10 Outcome waste (no-artifact sessions)
- **Motivation:** the saddest token is the one that produced nothing durable.
- **Implementation:** durable artifact = observed git commit (successful `git commit`
  Bash call) OR Write/Edit outside scratchpad/temp paths OR artifact/report publish
  OR memory write. `no_artifact_sessions` = sessions with >10k out_tokens and zero
  artifacts; plus the headline ratio `tokens_per_artifact` (Sensor F's fifth metric).
- **Quality counter:** built-in caveat — Q&A and research sessions legitimately
  produce no files (the *answer* was the artifact). Mitigation: sessions whose first
  prompt is question-shaped (regex: starts with wh-word/how/why/can/does, ends "?")
  are excluded. **Advisory metric only — never becomes a live nudge.**

### 4.11 Idle automation
- **Motivation:** a cron or loop wakeup that does nothing still pays the ~53k
  startup toll. Silent recurring waste is the worst kind because nobody is watching.
- **Implementation:** identify automation sessions (autonomous-loop sentinels, cron
  command markers in first prompt); flag those with zero mutations, zero messages
  sent, short duration. Metric `idle_automation_runs` × toll estimate = weekly cost
  of doing nothing.
- **Quality counter:** an automation that fires uselessly 6 days a week may earn its
  keep on the 7th. The report shows per-automation value over a trailing month
  (artifacts produced per wakeup) before any disable proposal.

### 4.12 Tool-schema dribble (MCP bloat, dynamic half)
- **Motivation:** loading deferred tool schemas one at a time wastes a full
  round-trip each; the system prompt explicitly says batch them.
- **Implementation:** ≥3 single-select ToolSearch calls in one session →
  `toolsearch_dribble`. (The *static* half — how many MCP servers/tools are mounted
  at all — is Sensor E's inventory.)
- **Quality counter:** quality-neutral.

---

## 5. Sensor A' — subagent & workflow transcripts (scope extension)

- **Motivation:** 886 subagent/workflow transcripts (≈2/3 of all transcript files)
  are currently invisible to the weekly loop. Fan-outs can duplicate work, return
  nothing, or quietly dominate spend — nobody is auditing the fleet.
- **Implementation:** extend the snapshot glob from `projects/*/*.jsonl` to the
  nested directories (audit2.py already proved the recursive glob). Per parent
  session: `agents_spawned`, `agent_null_returns` (empty/error final output),
  `agent_dupes` (near-duplicate normalized prompt prefixes — same work requested
  twice), `subagent_token_share` (subagent out_tokens ÷ session total).
- **Quality counter:** fan-out often *raises* quality (verification swarms,
  adversarial review). The guard: join with parent-session `correction_rate`.
  Verify-style swarms that correlate with low corrections are marked
  **quality-positive** in the report and are exempt from waste-flagging. Only
  null-returns and duplicates are unambiguous waste.

---

## 6. Sensor D — cross-session waste (new sensor class)

Wastes that no single transcript can show; computed by joining sessions per project
over the trailing window.

### 6.1 Re-derivation
- **Motivation:** every fresh session that re-explores the same codebase pays
  tuition for a class already taken. (The 871 within-session re-reads have a
  cross-session twin nobody measures.)
- **Implementation:** per project: files Read in ≥3 distinct sessions this week
  (`re_derived_files`); first-prompt similarity clusters; sessions that started
  cold (no HANDOFF.md/memory read in first turns) after a predecessor ended >150k.
  Composite `rederivation_score`.
- **Quality counter:** this metric is itself the quality half of the god-session
  rule (`resume_friction`). Its "fix" — handoff files — is validated when successor
  sessions reach their first Edit in fewer turns.

### 6.2 Paste-again
- **Motivation:** the same 10k-character blob pasted into three sessions pays rent
  three times; a file path costs ~20 tokens.
- **Implementation:** sha1 of normalized first 4k chars of every >8k prompt; same
  hash in ≥2 sessions → `repeat_pastes` (count + estimated duplicate tokens).
- **Quality counter:** quality-neutral (file reference strictly dominates).

### 6.3 Duplicate concurrent sessions
- **Motivation:** two live sessions on the same project in the same hour → double
  startup toll, overlapping exploration, race-condition edits.
- **Implementation:** overlapping timestamp ranges per project dir where both
  sessions mutate files → `concurrent_overlap_sessions`.
- **Quality counter:** legitimate patterns exist (worktrees, delegated subagents).
  Sessions carrying worktree/isolation markers are excluded before flagging.

---

## 7. Sensor E — config drift (new sensor class)

The config layer is upstream of every session; nobody currently watches it change.

### 7.1 Startup-toll tracking (H4, finally instrumented)
- **Motivation:** the ~53k-token toll is paid by *every* session before the first
  word of work. It grows silently as skills/plugins accrete. A 10k toll increase ×
  50 sessions/week = half a million tokens of pure overhead.
- **Implementation:** weekly toll estimate = median first-assistant-turn context
  (input + cache_creation) across trivial 1-turn sessions. Stored as a trend line.
  Correlated against §7.2's config snapshot deltas: when the toll jumps, the report
  names which plugin/skill arrived that week.
- **Quality counter:** joins Sensor B before proposing prunes — a skill that looks
  unused this week may be load-bearing in other weeks (the deferred cerebras-trio
  precedent, decision log 2026-07-21). Prune proposals require 4 weeks of zero use.

### 7.2 Config snapshot & stale-CLAUDE.md
- **Motivation:** standing instructions rot. A stale CLAUDE.md directive silently
  causes wrong behavior — and therefore rework — in every session that loads it.
- **Implementation:** weekly snapshot of hashes/sizes/mtimes: `~/.claude/CLAUDE.md`,
  per-project CLAUDE.mds seen in transcripts, `settings.json`, enabledPlugins list.
  Deltas go in the report ("what changed in your config this week"). Staleness
  surfaced to the analyst as age + size only (aggregates, not content — the
  UNTRUSTED discipline extends to config files).
- **Quality counter:** the tutor **never edits config**; it only proposes a human
  review with evidence ("this file is 14 weeks unchanged while babysit prompts rose
  3× — its standing rules may no longer match how you work").

---

## 8. Pipeline & report-card changes

1. **Snapshot schema v2** — all new counters live beside the v1 keys; old snapshots
   remain readable (missing keys default 0), so deltas-vs-baseline keep working
   through the transition.
2. **Deltas** — new keys join the trailing-4-week baseline comparison automatically.
3. **Analyst prompt** — gains sections: subagent fleet, cross-session, config drift,
   and the quality panel; plus one standing instruction: *"Reject any proposal whose
   paired quality counter-metric worsened in the obeyed cohort."*
4. **Report card** — every proposal now renders **two columns: projected token
   saving | quality-cohort evidence.** New sections: fleet audit (A'), cross-session
   (D), config drift (E), quality panel (F) with the five proxies vs baseline.
5. **Auto-drafted proposals** — any new metric crossing its evidence threshold in
   week 1+ drafts its fast-loop rule into pending-proposals.json with fire-count
   evidence attached. Human approval remains the only path into rules.json.
   Harm-based retirements flow through the same pending file.
6. **rules.json schema** — one optional new field: `holdout_pct` (see §3). No
   change to existing rules.

## 9. Cost model

| component | tokens |
|---|---|
| All sensors A/A'/D/E/F | 0 (stdlib streaming) |
| Fast-loop hook | 0 (unchanged; holdout adds a hash call) |
| Analyst (Haiku) | +2–3k prompt tokens/week |
| Sensor C (Sonnet) | unchanged (re-weighted sampling only) |

## 10. Rollout

- **Week 0:** implement sensors; run `tutor_weekly.py --no-llm` to validate schema
  v2 on real transcripts; commit. No behavior change for the user.
- **Week 1:** first full run. Report card shows all 18 metrics + auto-drafted rule
  proposals with evidence. Human approves the worthy ones into rules.json.
- **Week 2+:** cohort evaluator starts producing validated/harmful verdicts as
  obeyed/ignored data accumulates. Holdouts enabled per rule if desired.
- **Recalibration:** thresholds in this spec (20k chars, 15 Reads, 0.2 error
  density, etc.) are opening bids — the deltas-vs-baseline mechanism recalibrates
  them after 2 weeks of data, via proposals like everything else.

---
*Spec written 2026-07-22 with Claude Code. Implements nothing; approves nothing.
The tutor's rule applies to its own spec: propose, don't impose.*
