"""SPEC-V2-TRIMMED self-check: synthetic transcripts exercise each §1 detector and the
§0 self-contamination guard. Stdlib assert only. Run: python test_detectors.py"""
import json, os, tempfile
import coach_weekly as cw


def _write_session(d, name, lines):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        for ln in lines:
            f.write(json.dumps(ln) + "\n")
    return p


def asst(usage=None, tools=()):
    content = [{"type": "tool_use", "id": t["id"], "name": t["name"],
                "input": t.get("input", {})} for t in tools]
    return {"type": "assistant",
            "message": {"model": "claude-opus-4-8", "usage": usage or {}, "content": content}}


def user(txt=None, results=()):
    if results:
        c = [{"type": "tool_result", "tool_use_id": r["id"],
              "is_error": r.get("is_error", False), "content": r.get("content", "ok")}
             for r in results]
    else:
        c = txt
    return {"type": "user", "message": {"content": c}}


def build(tmp):
    # --- live session: 3 consecutive failed `npm` bash loops, one verbose result,
    #     3 single-select ToolSearch, a big paste ---
    big = "PASTE " * 3000  # >8k chars
    _write_session(tmp, "live__work.jsonl", [
        user("do the thing"),
        asst(usage={"input_tokens": 5000, "cache_creation_input_tokens": 1000},
             tools=[{"id": "b1", "name": "Bash", "input": {"command": "npm test"}},
                    {"id": "s1", "name": "ToolSearch", "input": {"query": "select:Read"}},
                    {"id": "s2", "name": "ToolSearch", "input": {"query": "select:Edit"}},
                    {"id": "s3", "name": "ToolSearch", "input": {"query": "select:Grep"}},
                    {"id": "v1", "name": "Read", "input": {}}]),
        user(results=[{"id": "b1", "is_error": True, "content": "fail"},
                      {"id": "v1", "content": "X" * 25000}]),
        asst(tools=[{"id": "b2", "name": "Bash", "input": {"command": "npm test"}}]),
        user(results=[{"id": "b2", "is_error": True, "content": "fail"}]),
        asst(tools=[{"id": "b3", "name": "Bash", "input": {"command": "npm test"}}]),
        user(results=[{"id": "b3", "is_error": True, "content": "fail"}]),  # streak hits 3
        user(big),
    ])
    # --- second live session with the SAME big paste (triggers repeat_pastes) and a
    #     trivial one-turn startup toll ---
    _write_session(tmp, "live__other.jsonl", [
        user(big),
        asst(usage={"input_tokens": 40000, "cache_creation_input_tokens": 13000}),
    ])
    # --- coach-dev session: MUST be excluded by §0. Same failure vocabulary. ---
    _write_session(tmp, "living-claude-tutor__dev.jsonl", [
        user("revert that, you broke it"),
        asst(tools=[{"id": "c1", "name": "Bash", "input": {"command": "npm test"}}]),
        user(results=[{"id": "c1", "is_error": True, "content": "Traceback"}]),
        asst(tools=[{"id": "c2", "name": "Bash", "input": {"command": "npm test"}}]),
        user(results=[{"id": "c2", "is_error": True, "content": "Traceback"}]),
        asst(tools=[{"id": "c3", "name": "Bash", "input": {"command": "npm test"}}]),
        user(results=[{"id": "c3", "is_error": True, "content": "Traceback"}]),
    ])


def main():
    with tempfile.TemporaryDirectory() as root:
        proj = os.path.join(root, "projects", "C--Users-x")
        os.makedirs(proj)
        build(proj)
        cw.PROJECTS = os.path.join(root, "projects")  # redirect scan
        snap = cw.build_snapshot(days=36500)

    # §0 guard: the coach-dev session is excluded, its 1 loop does NOT count
    assert snap["coach_sessions_excluded"] == 1, snap["coach_sessions_excluded"]
    # §1.2 exactly one failed-command loop from live sessions
    assert snap["failed_cmd_loops"] == 1, snap["failed_cmd_loops"]
    # §1.6 error density counts only live bash results (3 fails / 3 results)
    assert snap["error_density"] == 1.0, snap["error_density"]
    # §1.3 one verbose (>20k) result
    assert snap["verbose_results_count"] == 1, snap["verbose_results_count"]
    assert snap["verbose_by_tool"] and snap["verbose_by_tool"][0][0] == "Read"
    # §1.4 the big paste appears in 2 live sessions
    assert snap["repeat_pastes"] == 1, snap["repeat_pastes"]
    # §1.5 one session with >=3 single-select ToolSearch
    assert snap["toolsearch_dribble_sessions"] == 1, snap["toolsearch_dribble_sessions"]
    # §1.1 startup toll = median first-turn (input+cache_creation) of one-turn live sessions
    #     only live__other qualifies (one turn) -> 40000+13000
    assert snap["startup_toll_median"] == 53000, snap["startup_toll_median"]

    # guard identifies coach paths, not live ones
    assert cw.is_coach_file("/x/projects/living-claude-tutor/a.jsonl")
    assert cw.is_coach_file("/x/C--Users-simon-Downloads-live-claude-tutor-audit/a.jsonl")
    assert not cw.is_coach_file("/x/projects/C--Users-x/live__work.jsonl")
    print("all detector checks passed")


if __name__ == "__main__":
    main()
