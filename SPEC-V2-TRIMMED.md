# SPEC-V2 — Trimmed (draft, for review)

Status: **draft — not yet approved, nothing implemented.** Derived from an adversarial
critic review of `SPEC-V2.md`. This file is a separate proposal; **`SPEC-V2.md` is
left untouched** as the original record of the full 7-sensor design.

Critic's one-line verdict: the core principle — pair every cost metric with a quality
counter-metric — is worth keeping. The apparatus built around it (cohort verdicts,
holdout groups, 7 sensor classes, 18 metrics) is over-engineered for a solo tool.
About four small deterministic detectors, plus the startup-toll instrument, survive
scrutiny. This draft keeps only those, plus one new precondition the original spec
never addressed.

---

## 0. Precondition on shipping anything: the self-contamination guard

**This is the critic's most important finding and it blocks everything else below.**

The coach detects waste (corrections, errors, rework) by regex over your own session
transcripts. But the coach's *own development* — writing SPEC-V2.md, editing
`rules.json`, discussing detector regexes in chat, this very file — produces
transcripts that contain the exact strings those regexes look for: `you broke`,
`revert`, `no that's wrong`, `Traceback`, etc. Nobody designed a fix for this in the
original spec.

**Consequence if unfixed:** the sessions where you work *on* the coach — arguably the
sessions you care most about getting an honest read on — would score as the noisiest,
most error-prone, most corrected sessions in the whole dataset. Not because you were
doing badly, but because the coach would be reading its own vocabulary back to itself.
The "maximize quality per token" story the spec promises would run on numbers
corrupted by construction, in exactly the sessions most likely to be inspected.

**Required fix before any quality-guard metric ships:**
- Exclude this project's own directory (`living-claude-tutor` / `claude-coach-live`,
  however it's identified in the transcript path) from all Sensor F quality-proxy
  computations.
- If that's too coarse (you may want visibility into coach-dev sessions for other
  reasons), the fallback is to exclude only the five quality-proxy regex matches
  *when the matched text appears inside a code block, file path, or quoted string* —
  but the simpler directory-level exclusion should be tried first; add the narrower
  fix only if it proves necessary.

Nothing in §2 below should be turned on until this is in code, not just asserted in
a spec.

---

## 1. What ships

Each item: what it does, why it survived, one-line implementation note.

### 1.1 Startup-toll tracking (was §7.1)
- **What:** weekly median first-assistant-turn context (input + cache_creation) across
  trivial one-turn sessions, tracked as a trend line.
- **Why it survived:** instruments a habit you already know is active (H4, ~53k-token
  toll) with one clean deterministic number. No quality gate needed — there's no
  "the toll going down could be bad" failure mode.
- **Note:** correlate against Sensor B's inventory so the report can name which
  skill/plugin arrived the week the toll jumped, same as the original spec.

### 1.2 Failed-command loops (was §4.2)
- **What:** consecutive Bash/PowerShell tool_results with `is_error=true` sharing a
  first command token, 3+ in a row.
- **Why it survived:** `is_error` is a real, reliable transcript field — no fragile
  regex, no undefined "marker" to reverse-engineer.

### 1.3 Verbose tool results (was §4.6)
- **What:** tool_result content-length distribution; flag results >20k chars with
  per-tool top offenders.
- **Why it survived:** pure content-length math. Deterministic, cheap, no ambiguity.

### 1.4 Paste-again (was §6.2)
- **What:** sha1 of the normalized first 4k chars of every >8k-char prompt; same hash
  reappearing in ≥2 sessions this week → `repeat_pastes`.
- **Why it survived:** exact-match hashing, not a fuzzy heuristic. Quality-neutral
  (a file reference always dominates a repeated paste, no tradeoff to weigh).

### 1.5 Tool-schema dribble (was §4.12)
- **What:** ≥3 single-select ToolSearch calls in one session → `toolsearch_dribble`.
- **Why it survived:** simple count of a real tool-call pattern; the system prompt
  already tells the model to batch these, so this just measures compliance.

### 1.6 Quality guard, as a discipline (was Sensor F)
- **What:** each new proposal in the weekly report displays **one paired quality
  number** next to its cost saving (e.g. failed-command-loop proposals show
  `error_density` trend; verbose-tool-result proposals show whether missed-error
  corrections rose). You read both numbers and decide.
- **Why it survived in this reduced form, but not as originally specced:** the
  *principle* (never propose a cost cut blind to quality) is sound and cheap to keep.
  What's cut is the **automated verdict engine** (validated/harmful/inconclusive) and
  **holdout groups** — see §2.1 for why.

---

## 2. What's cut, and why

### 2.1 The cohort verdict engine + holdout groups (was Sensor F's evaluator)
- **Cut because:** it's rigor theater at the sample sizes this project actually has.
  Your own historical counts are **all-time**, not weekly — 51+12 babysit occurrences,
  132 god-sessions, across the whole audit period. Split per-rule, per-week, into
  obeyed-vs-ignored cohorts, a "verdict" would run on something like N=3 vs N=4. A
  "harmful" verdict at that N is close to a coin flip — and the spec has it
  **auto-drafting a retirement proposal** off that noise, i.e. potentially killing a
  rule that's actually working because of sampling luck.
- **Compounding problem:** the fire log the evaluator would join against is a
  2000-entry ring buffer (`coach_hook.py`), which at current usage volume rolls over
  faster than the trailing window the evaluator needs — so even the "did this session
  get nudged" join isn't reliably answerable from the data.
- **Holdouts make it worse, not better:** withholding ~15% of nudges you already
  approved, to build a control group that won't reach significance for months, is a
  bad trade at solo scale.

### 2.2 Permission-prompt churn (was §4.4)
- **Cut because:** dead on arrival for you specifically. Your real permission-mode
  distribution is 6325 `bypassPermissions` vs. 226 `default` — you run almost
  everything in a mode with no permission prompts to deny. This detector would report
  ~zero, forever.

### 2.3 Speculative read fan-out (was §4.7)
- **Cut because:** the original spec text itself predicts this detector is "the
  sensor most likely to be rejected by its own quality gate." Building something
  designed to self-reject isn't worth the implementation cost.

### 2.4 Interrupted-generation waste + compaction thrash (were §4.3, §4.5)
- **Cut/deferred because:** both rely on transcript "markers" the original spec never
  concretely defined. A real check against an actual transcript found that naive
  string matches (e.g. grepping `compact`) hit unrelated content (skill-listing
  attachments, `tool_use_id` fragments), not real compaction events. These need actual
  reverse-engineering of the transcript schema before they're buildable — not
  scoped out, just not free the way the rest of this list is.

### 2.5 Concurrent-session detection (was §6.3)
- **Cut because:** a rare event that requires excluding legitimate confounders
  (worktrees, delegated subagents) to avoid false flags — high implementation cost
  for low expected yield.

### 2.6 Subagent fleet audit, full version (was Sensor A')
- **Reduced, not fully cut:** the original proposed four joined counters requiring
  cross-transcript joins over 1000+ nested files. Replaced with one number —
  `subagent_token_share` (subagent out_tokens ÷ session total) — which carries most
  of the signal. Expand only if that number turns out to be large enough to warrant
  more detail.

### 2.7 Config-drift snapshot (was §7.2), deferred not cut
- **Deferred because:** the original spec asserts an "UNTRUSTED discipline" (hash/size/
  mtime only, never file body) in prose, but nothing in the current code enforces
  that for project-level CLAUDE.md files specifically — which are attacker-
  controllable in a way `~/.claude`'s own config isn't. Ship only after that
  assertion is a real code-level guarantee, not a spec sentence.

### 2.8 Cross-session re-derivation (was §6.1)
- **Folded in, not built separately:** this substantially overlaps the existing
  god-session / `resume_friction` story already tracked. Not worth a separate sensor
  class on top of what's already measured.

---

## 3. Cost model

Same shape as the original spec, minus the expensive parts:
- Sensors 1.1–1.5: 0 LLM tokens, stdlib streaming, all read fields that already exist
  cheaply per-session (no new cross-file joins except the single reduced fleet
  counter in §2.6).
- No new "free" claim for anything that actually requires streaming 1000+ nested
  subagent transcripts — that cost is deferred along with the full fleet audit.

## 4. Rollout

1. Implement the self-contamination guard (§0) first — nothing else ships before this.
2. Implement 1.1–1.5 + the quality-guard discipline (1.6). Run `--no-llm` to validate
   against real transcripts before wiring into the weekly report.
3. First full weekly run with the new counters. Human approves what's worth keeping,
   same approval gate as always.
4. Revisit anything in §2 only if real usage data makes a specific cut item look
   worth reconsidering — not on a schedule, on evidence.

---
*Draft derived from adversarial review of SPEC-V2.md, 2026-07-23. Proposes, does not
implement. SPEC-V2.md is unmodified and remains the full original design record.*
