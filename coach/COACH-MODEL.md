# COACH-MODEL.md — living model of the user's Claude Code usage

Maintained by the weekly tutor loop. All mutations proposed via report card, human-approved.
Seeded from the 2026-07-21 audit (458 main sessions, 886 subagent/workflow transcripts, ~1 GB).

## Known habits

| id | habit | status | evidence (at discovery) |
|----|-------|--------|------------------------|
| H1 | God sessions — giant context as project memory | active | 132 sessions >150k peak ctx; worst 1.29B cache-read tokens; top 12 sessions ≈49% of lifetime spend |
| H2 | Micro-prompt babysitting ("commit and push", "continue") | active | 51+12 occurrences; 810/2628 prompts <50 chars |
| H3 | Per-stop security-review fleet on frontier models | mitigated 2026-07-21 | 202/458 sessions; gated via ENABLE_STOP_REVIEW=0 + Sonnet model |
| H4 | ~53k-token startup toll (plugins/skills/hooks) | active | median baseline ctx of trivial 1-turn sessions = 53k |
| H5 | Tool frictions: cd-prefixed Bash, cat/grep-in-Bash, re-reads, fat pastes | active | 4382 cd-Bash; ~700 unix-in-Bash; 871 re-reads; 178 pastes >8k chars |

## Current sensors

- Fast loop: rules.json (babysit-prompt, god-session-150k/300k, fat-paste) via UserPromptSubmit hook — 0 tokens
- Sensor A (presence): weekly distribution snapshot + delta vs trailing 4 weeks
- Sensor B (absence): owned-vs-used inventory (skills, plugins, models, native features); monthly changelog check
- Sensor C (out-of-model): weekly stratified 3-session raw-trace read (random / most-expensive / most-recent)
- Meta: unasked-question step + 30-day zero-fire rule retirement proposals

## Open hypotheses

- (none yet — first weekly run will populate)

## Decision log

- 2026-07-21: system seeded. H3 gated (ENABLE_STOP_REVIEW=0, SECURITY_REVIEW_MODEL=claude-sonnet-4-6). Standing commit-and-push rules added to 3 active project CLAUDE.md files. Thresholds: nudge 150k, escalate 300k — recalibrate after week 1.
- 2026-07-21: weekly run (72 sessions, 0 proposals pending, errors: none)
- 2026-07-21: weekly run (72 sessions, 2 proposals pending, errors: none)
- 2026-07-21: W30 proposals resolved via chat. Approved: orphan-taskcreate rule (fast loop), deferral_total metric (Sensor A). Rejected: budget-disclosed-late rule, re-read-density metric. Deferred: 8-skill prune shortlist until 4 weeks of usage data (open hypothesis: cerebras-brain trio is used in other weeks).
- 2026-07-21: security-review finding (indirect prompt injection via Sensor C traces) hardened: UNTRUSTED preamble added to both LLM prompts; approval gate remains the primary control.
- 2026-07-22: P2 (statusline ambient cue) and P8 (quarterly blind-spot pass) implemented; SPEC-V2.md written (18-waste sensor expansion + Sensor F quality guard) — spec only, not yet implemented.
- 2026-07-22: unified into **Live Claude Coach** (repo renamed from living-claude-tutor). Phase 1 shipped: feature catalog (`coach_sync.py`, fetch→distill→diff, host-allowlisted), `capability_gap` + `tool_sequence` hook rule kinds with doc-URL citations, deterministic cross-session repetition pass, on-demand review skill (`coach-review`, natural-language triggered). First live catalog sync: 12 Claude Code features distilled from docs + changelog. Efficiency and capability findings now share one engine/report/approval gate. Phase 2 pending (full-Claude feature spotlight, catalog audit inside the quarterly blind-spot pass, auto-retirement of detectors for deprecated features).
