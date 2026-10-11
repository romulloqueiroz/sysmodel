import copy
import http.client
import json
import os
import sys
import threading
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import sysmodel  # noqa: E402
from test_check import E, VALID, drop, page_data  # noqa: E402
from test_levels import stale, tree  # noqa: E402


def changed_steps(edit):
    m = copy.deepcopy(VALID)
    edit(m)
    return {n for n in range(1, 7) if sysmodel.fingerprint(m, n) != sysmodel.fingerprint(VALID, n)}


def test_fingerprint_covers_only_what_the_step_shows():
    assert changed_steps(lambda m: E(m, "tests", "T1").update(name="x")) == {6}
    assert changed_steps(lambda m: E(m, "tests", "T2").update(description="x")) == {6}
    assert changed_steps(lambda m: E(m, "items", "I1").update(description="x")) == {1, 2, 5}
    assert changed_steps(lambda m: E(m, "items", "I5").update(description="x")) == {2, 5}
    assert changed_steps(lambda m: E(m, "requirements", "Q1").update(text="x")) == {1, 6}
    assert changed_steps(lambda m: E(m, "functions", "F11").update(runs_in="C12")) == {4}   # matching isn't step 2's call
    assert changed_steps(lambda m: E(m, "functions", "F11").update(name="x")) == {2, 4}
    assert changed_steps(lambda m: E(m, "components", "C2").update(choice="SQLite")) == {3, 4, 5}
    assert changed_steps(lambda m: E(m, "interfaces", "IF1").update(carries=["I1"])) == {5}
    assert changed_steps(lambda m: E(m, "items", "I1").update(name="x")) == {1, 2, 5}          # crosses the boundary
    assert changed_steps(lambda m: E(m, "items", "I5").update(name="x")) == {2, 5}             # internal
    assert changed_steps(lambda m: E(m, "requirements", "Q2")["specifies"].append("F1")) == {2}
    assert changed_steps(lambda m: E(m, "requirements", "Q3")["specifies"].append("C1")) == {4}
    assert changed_steps(lambda m: m["requirements"].append(
        {"id": "Q9", "text": "x", "derived_from": ["Q3"], "specifies": ["C2"]})) == {4, 6}       # derived while matching
    assert changed_steps(lambda m: m["requirements"].append(
        {"id": "Q9", "text": "x", "derived_from": ["Q1"], "specifies": ["I5", "F11"]})) == {4, 6}  # not step 2's links


def test_review_state_goes_stale_when_the_step_changes():
    fp = sysmodel.fingerprint(VALID, 3)
    decisions = {3: {"decision": "approved", "fingerprint": fp}}
    assert sysmodel.review_state(VALID, decisions, 6)[3]["current"]
    m = copy.deepcopy(VALID)
    E(m, "components", "C2").update(name="Store")
    st = sysmodel.review_state(m, decisions, 6)
    assert not st[3]["current"] and st[3]["last"]["decision"] == "approved" and st[1]["last"] is None
    m = copy.deepcopy(VALID)
    E(m, "components", "C2").update(choice="SQLite")
    assert not sysmodel.review_state(m, decisions, 6)[3]["current"]


def test_cli_render_shows_saved_reviews(tmp_path):
    src = tmp_path / "app.yaml"
    src.write_text(yaml.safe_dump(VALID))
    sysmodel.review_path(src).write_text(yaml.safe_dump({2: {"decision": "sent back", "note": "split F1",
                                                             "fingerprint": sysmodel.fingerprint(VALID, 2)}}))
    assert sysmodel.main(["render", str(src)]) == 0
    d = page_data((tmp_path / "app.html").read_text())
    assert d["review"]["2"]["last"]["note"] == "split F1" and d["review"]["2"]["current"] and d["live"] is None


def start(model):
    """Serve model on a free port; returns (server, call) where call(method, path, body, headers) gives (status, content type, data)."""
    srv = sysmodel.make_server(model, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def call(method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", port)
        h = {"Content-Type": "application/json"} if body is not None else {}
        c.request(method, path, json.dumps(body) if isinstance(body, dict) else body, {**h, **(headers or {})})
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, r.getheader("Content-Type"), data

    return srv, call


@pytest.fixture
def served(tmp_path):
    model = tmp_path / "app.yaml"
    model.write_text(yaml.safe_dump(VALID))
    srv, call = start(model)
    yield model, call
    srv.shutdown()
    srv.server_close()


def post(call, step, decision, model, note="", **extra):
    m = yaml.safe_load(model.read_text())
    body = {"step": step, "decision": decision, "note": note, "checked": [],
            "fingerprint": sysmodel.fingerprint(m, step) if step in sysmodel.STEPS else "", **extra}
    status, _, data = call("POST", "/api/review", body)
    return status, json.loads(data)


def test_serve_page_uses_offline_copies_and_knows_it_is_live(served):
    model, call = served
    status, ctype, data = call("GET", "/")
    html = data.decode()
    assert status == 200 and ctype.startswith("text/html")
    assert "https://" not in "".join(l for l in html.splitlines() if "<script src" in l or "<link" in l)
    d = page_data(html)
    assert d["live"]["version"] and d["review"]["1"]["last"] is None
    for name in sysmodel.VENDOR.values():
        status, _, body = call("GET", "/vendor/" + name)
        assert status == 200 and body
    assert b"url(fonts/" in call("GET", "/vendor/fonts.css")[2]
    assert call("GET", "/vendor/../sysmodel.py")[0] == 404


def test_serve_saves_decisions_next_to_the_model(served):
    model, call = served
    v0 = json.loads(call("GET", "/api/version")[2])["version"]
    assert post(call, 1, "approved", model)[0] == 200
    status, out = post(call, 2, "approved", model, checked=["R12", "R99"])
    assert status == 200 and out["review"]["2"]["current"] and out["version"] != v0
    saved = sysmodel.load_reviews(sysmodel.review_path(model))
    assert saved[2]["decision"] == "approved" and saved[2]["checked"] == ["R12"] and saved[2]["by"]
    status, out = post(call, 3, "sent back", model, note="Split the web service")
    assert status == 200 and sysmodel.load_reviews(sysmodel.review_path(model))[3]["note"] == "Split the web service"
    # the model changes under step 2: the approval goes stale, and the page sees a new version
    m = yaml.safe_load(model.read_text())
    E(m, "functions", "F12").update(name="Send visitor on")
    model.write_text(yaml.safe_dump(m))
    assert json.loads(call("GET", "/api/version")[2])["version"] != out["version"]
    assert not page_data(call("GET", "/")[2].decode())["review"]["2"]["current"]


def test_serve_refuses_bad_decisions(served):
    model, call = served
    assert post(call, 1, "sent back", model)[0] == 400                       # sending back needs a note
    status, out = post(call, 1, "approved", model, fingerprint="old")
    assert status == 409 and out["reload"]                                   # model changed since the page loaded
    m = yaml.safe_load(model.read_text())
    E(m, "functions", "F2").pop("runs_in")
    model.write_text(yaml.safe_dump(m))
    status, out = post(call, 4, "approved", model)
    assert status == 409 and "must-fix" in out["error"]                      # step 4 has an R14 error now
    assert post(call, 7, "approved", model)[0] == 400
    assert not sysmodel.review_path(model).exists()


def test_serve_only_talks_to_its_own_pages(served):
    model, call = served
    body = json.dumps({"step": 1, "decision": "approved"})
    assert call("POST", "/api/review", body, {"Content-Type": "text/plain"})[0] == 415
    assert call("POST", "/api/review", body, {"Content-Type": "application/json", "Origin": "https://evil.example"})[0] == 403
    assert call("GET", "/", headers={"Host": "evil.example:80"})[0] == 403


def test_serve_explains_an_unreadable_model(served):
    model, call = served
    model.write_text("system: [unclosed")
    status, _, data = call("GET", "/")
    assert status == 200 and b"Can't read app.yaml" in data and b"api/version" in data


def test_progress_says_whose_turn_each_step_is():
    m = copy.deepcopy(VALID)
    m.pop("tests")
    fp = lambda n: sysmodel.fingerprint(m, n)
    decisions = {1: {"decision": "approved", "by": "ana", "at": "2026-10-10T09:00", "fingerprint": fp(1)},
                 2: {"decision": "approved", "by": "ana", "at": "2026-10-10T09:00", "fingerprint": "old"},
                 3: {"decision": "sent back", "by": "ana", "at": "2026-10-10T09:00", "fingerprint": fp(3), "note": "Split C1"}}
    E(m, "functions", "F2").pop("runs_in")
    rows = {r["step"]: r for r in sysmodel.progress(m, decisions)}
    assert rows[1]["turn"] == "done"
    assert rows[2]["turn"] == "person" and "changed since approved" in rows[2]["why"]
    assert rows[3]["turn"] == "ai" and rows[3]["why"].endswith("Split C1")
    assert rows[4]["turn"] == "ai" and rows[4]["why"] == "1 must fix"              # F2 runs nowhere (R14)
    assert rows[5]["turn"] == "person" and rows[5]["why"] == "ready for review"
    assert rows[6]["turn"] == "ai" and rows[6]["why"] == "not started"
    E(m, "external", "E1")["sends"].append("I2")   # an edit outside step 2's pieces breaks a step 2 rule (R10)
    rows = {r["step"]: r for r in sysmodel.progress(m, {2: {**decisions[2], "fingerprint": fp(2)}})}
    assert rows[2]["turn"] == "ai" and rows[2]["why"] == "1 must fix"


def test_cli_status_names_the_next_step(tmp_path, capsys):
    src = tmp_path / "app.yaml"
    src.write_text(yaml.safe_dump(VALID))
    sysmodel.review_path(src).write_text(yaml.safe_dump({1: {"decision": "approved", "by": "ana", "at": "2026-10-10T09:00",
                                                             "fingerprint": sysmodel.fingerprint(VALID, 1)}}))
    assert sysmodel.main(["status", str(src)]) == 0
    out = capsys.readouterr().out
    assert "1 Problem     DONE    approved by ana, 2026-10-10 09:00" in out
    assert "Next: step 2 Functions, waiting for a person to review it" in out


def test_skill_table_matches_the_fingerprints():
    import re
    rows = re.findall(r"^\| (.+?) \| ([\d, ]+) \|$", (HERE.parent / "SKILL.md").read_text(), re.M)
    assert [(label, tuple(int(d) for d in steps.split(","))) for label, steps in rows] == sysmodel.OWNERS


def test_skill_links_resolve():
    import re
    for link in re.findall(r"\]\(([^)]+\.md)\)", (HERE.parent / "SKILL.md").read_text()):
        assert (HERE.parent / link).is_file(), link


def test_wait_returns_when_a_person_decides(tmp_path, capsys, monkeypatch):
    model = tmp_path / "app.yaml"
    model.write_text(yaml.safe_dump(VALID))
    path = sysmodel.review_path(model)
    path.write_text(yaml.safe_dump({1: {"decision": "approved", "by": "ana", "at": "2026-10-10T09:00"}}))
    sent = {"decision": "sent back", "by": "ana", "at": "2026-10-10T09:05", "note": "Split Q7"}
    real_sleep = sysmodel.time.sleep
    def decide_then_sleep(_):                                      # the person clicks while wait polls
        path.write_text(yaml.safe_dump({1: {"decision": "approved", "by": "ana", "at": "2026-10-10T09:00"}, 2: sent}))
        real_sleep(0)
    monkeypatch.setattr(sysmodel.time, "sleep", decide_then_sleep)
    assert sysmodel.main(["wait", str(model)]) == 0
    assert capsys.readouterr().out == ("Step 2 Functions: sent back by ana, 2026-10-10 09:05\nNote: Split Q7\n\n"
                                       "Run `status` and go on with the loop.\n")


def test_page_data_carries_decisions_md_next_to_the_model(tmp_path):
    src = tmp_path / "app.yaml"
    src.write_text(yaml.safe_dump(VALID))
    assert sysmodel.main(["render", str(src)]) == 0
    assert page_data((tmp_path / "app.html").read_text())["notes"] is None
    (tmp_path / "decisions.md").write_text("## Step 1 Problem\n- **cost** `x`\n")
    assert sysmodel.main(["render", str(src)]) == 0
    assert page_data((tmp_path / "app.html").read_text())["notes"] == "## Step 1 Problem\n- **cost** `x`\n"


def test_serve_notes_show_and_version_follows_decisions_md(served):
    model, call = served
    assert page_data(call("GET", "/")[2].decode())["notes"] is None
    v0 = json.loads(call("GET", "/api/version")[2])["version"]
    (model.parent / "decisions.md").write_text("## Step 1 Problem\nhello\n")
    assert json.loads(call("GET", "/api/version")[2])["version"] != v0
    assert page_data(call("GET", "/")[2].decode())["notes"].startswith("## Step 1")


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(sysmodel.tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    model = tmp_path / "app.yaml"
    model.write_text(yaml.safe_dump(VALID))
    return model


def test_state_file_is_per_model_in_the_temp_dir_and_tolerates_junk(tmp_state, tmp_path):
    f = sysmodel.state_path(tmp_state)
    assert f.parent == tmp_path / "tmp" and f.name.startswith("sysmodel-") and f != sysmodel.state_path(tmp_path / "other.yaml")
    assert sysmodel.read_state(tmp_state) == {}
    f.write_text("{not json")
    assert sysmodel.read_state(tmp_state) == {}
    sysmodel.write_state(tmp_state, serve={"pid": 1, "url": "u"}, handoff={"1": "x"})
    sysmodel.write_state(tmp_state, serve=None)
    assert sysmodel.read_state(tmp_state) == {"handoff": {"1": "x"}}


def test_handoff_keeps_a_step_with_the_ai_until_it_is_handed_over(tmp_state):
    m = copy.deepcopy(VALID)
    turns = lambda: {r["step"]: (r["turn"], r["why"]) for r in sysmodel.progress(m, {}, tmp_state)}
    assert turns()[1] == ("person", "ready for review")                      # no hand-off record: as before
    sysmodel.write_state(tmp_state, handoff={"1": sysmodel.fingerprint(m, 1)})
    assert turns()[1] == ("person", "ready for review") and turns()[2] == ("ai", "the AI is still working on it")
    E(m, "requirements", "Q1").update(text="x")
    assert turns()[1] == ("ai", "the AI is still working on it")


def test_progress_never_calls_an_unstarted_step_done():
    m = copy.deepcopy(VALID)
    m.pop("tests")
    d = {6: {"decision": "approved", "fingerprint": sysmodel.fingerprint(m, 6)}}
    assert sysmodel.progress(m, d)[5]["why"] == "not started"


def test_wait_records_handoff_and_stops_when_serve_is_gone(tmp_state, capsys):
    assert sysmodel.main(["wait", str(tmp_state)]) == 2
    assert "The review app stopped. Start `serve` again, then `wait`." in capsys.readouterr().err
    h = sysmodel.read_state(tmp_state)["handoff"]
    assert h and h["1"] == sysmodel.fingerprint(VALID, 1)
    sysmodel.write_state(tmp_state, serve={"pid": 2 ** 22 + 12345, "url": "u"})   # dead pid
    assert sysmodel.main(["wait", str(tmp_state)]) == 2


def test_status_names_the_review_app(tmp_state, capsys):
    sysmodel.main(["status", str(tmp_state)])
    assert "Review app: not running; start serve" in capsys.readouterr().out
    sysmodel.write_state(tmp_state, serve={"pid": os.getpid(), "url": "http://127.0.0.1:8765/"})
    sysmodel.main(["status", str(tmp_state)])
    assert "Review app: http://127.0.0.1:8765/" in capsys.readouterr().out


def test_serve_refuses_approvals_out_of_order_or_early(served, tmp_state):
    model, call = served
    status, out = post(call, 3, "approved", model)
    assert status == 409 and "Step 1" in out["error"]
    m = yaml.safe_load(model.read_text())
    m.pop("tests")
    model.write_text(yaml.safe_dump(m))
    assert post(call, 1, "approved", model)[0] == 200 and post(call, 2, "approved", model)[0] == 200
    for n in (3, 4, 5):
        assert post(call, n, "approved", model)[0] == 200
    status, out = post(call, 6, "approved", model)
    assert status == 409 and "isn't started" in out["error"]
    assert post(call, 6, "sent back", model, note="no tests")[0] == 200       # send back stays allowed


def test_serve_refuses_approval_while_the_ai_is_working(served):
    model, call = served
    sysmodel.write_state(model, handoff={})
    try:
        status, out = post(call, 1, "approved", model)
        assert status == 409 and "still working" in out["error"]
        assert post(call, 1, "sent back", model, note="x")[0] == 200
    finally:
        sysmodel.state_path(model).unlink()


def test_decision_saves_elements_and_page_says_what_changed(served):
    model, call = served
    assert post(call, 1, "approved", model)[0] == 200
    saved = sysmodel.load_reviews(sysmodel.review_path(model))[1]["elements"]
    assert "Q1" in saved and "SH1" in saved
    none = {"added": [], "changed": [], "removed": []}
    assert page_data(call("GET", "/")[2].decode())["review"]["1"]["changed"] == none
    m = yaml.safe_load(model.read_text())
    E(m, "requirements", "Q1").update(text="changed")
    m["requirements"] = [r for r in m["requirements"] if r["id"] != "Q2"]
    m["requirements"].append({"id": "Q8", "text": "new"})
    model.write_text(yaml.safe_dump(m))
    ch = sysmodel.review_state(m, sysmodel.load_reviews(sysmodel.review_path(model)), 6)[1]["changed"]
    assert ch == {"added": ["Q8"], "changed": ["Q1"], "removed": ["Q2"]}
    assert sysmodel.review_state(m, {1: {"fingerprint": "old"}}, 6)[1]["changed"] == none   # old review file: no elements


def test_page_data_carries_progress(tmp_path):
    src = tmp_path / "app.yaml"
    src.write_text(yaml.safe_dump(VALID))
    assert sysmodel.main(["render", str(src)]) == 0
    rows = page_data((tmp_path / "app.html").read_text())["progress"]
    assert [r["step"] for r in rows] == [1, 2, 3, 4, 5, 6] and {"name", "turn", "why", "errors", "warnings"} <= rows[0].keys()


@pytest.fixture
def served_tree(tmp_path):
    """The two-level fixture tree, the top level approved, served from its root: (top, child, call)."""
    top, kid = tree(tmp_path)
    srv, call = start(top)
    yield top, kid, call
    srv.shutdown()
    srv.server_close()


def test_serve_shows_each_level_of_the_tree(served_tree):
    top, kid, call = served_tree
    root = page_data(call("GET", "/")[2].decode())
    assert root["model"]["system"]["id"] != "C1" and root["levels"]["here"] == "" and len(root["levels"]["crumbs"]) == 1
    assert root["levels"]["children"] == [dict(id="C1", name=root["levels"]["children"][0]["name"], level="C1", step=1, step_name="Problem",
                                               turn="person", why="ready for review")]
    assert page_data(call("GET", "/?level=")[2].decode())["model"] == root["model"]
    d = page_data(call("GET", "/?level=C1")[2].decode())
    assert d["model"]["system"]["id"] == "C1" and d["levels"]["here"] == "C1" and d["levels"]["children"] == []
    assert [c["level"] for c in d["levels"]["crumbs"]] == ["", "C1"] and d["review"]["1"]["last"] is None and d["live"]["version"]
    m = yaml.safe_load(kid.read_text())
    drop(m, "items", "I4")
    kid.write_text(yaml.safe_dump(m, sort_keys=False))
    assert any(f["rule"] == "L01" for f in page_data(call("GET", "/?level=C1")[2].decode())["findings"])   # the page checks against the level above


def test_serve_knows_only_the_levels_of_the_tree(served_tree):
    top, kid, call = served_tree
    for level in ("C2", "C1/C1", "..", "%2e%2e/C1"):
        assert call("GET", f"/?level={level}")[0] == 404 and call("GET", f"/api/version?level={level}")[0] == 404
        assert call("POST", f"/api/review?level={level}", {"step": 1, "decision": "sent back", "note": "x"})[0] == 404
    assert call("POST", "/api/review", {"level": ["C1"], "step": 1, "decision": "sent back", "note": "x"})[0] == 404
    assert not sysmodel.review_path(kid).exists()


def test_serve_saves_a_decision_in_the_level_it_names(served_tree):
    top, kid, call = served_tree
    root_reviews = sysmodel.review_path(top).read_text()
    fp = sysmodel.fingerprint(yaml.safe_load(kid.read_text()), 1)
    status, _, out = call("POST", "/api/review?level=C1", {"level": "C1", "step": 1, "decision": "approved", "fingerprint": fp})
    out = json.loads(out)
    assert status == 200 and out["progress"][0]["turn"] == "done" and out["levels"]["here"] == "C1"
    assert sysmodel.load_reviews(sysmodel.review_path(kid))[1]["decision"] == "approved"
    assert sysmodel.review_path(top).read_text() == root_reviews
    # the query alone picks the level too; the body wins when both name one
    fp2 = sysmodel.fingerprint(yaml.safe_load(kid.read_text()), 2)
    status, _, out = call("POST", "/api/review?level=C1", {"step": 2, "decision": "sent back", "note": "split it", "fingerprint": fp2})
    assert status == 200 and sysmodel.load_reviews(sysmodel.review_path(kid))[2]["note"] == "split it"
    fp0 = sysmodel.fingerprint(yaml.safe_load(top.read_text()), 1)
    status, _, out = call("POST", "/api/review?level=C1", {"level": "", "step": 1, "decision": "sent back", "note": "root", "fingerprint": fp0})
    assert status == 200 and sysmodel.load_reviews(sysmodel.review_path(top))[1]["note"] == "root"


def test_serve_refuses_a_level_while_the_level_above_is_stale(served_tree):
    top, kid, call = served_tree
    stale(top)
    fp = sysmodel.fingerprint(yaml.safe_load(kid.read_text()), 1)
    status, _, out = call("POST", "/api/review?level=C1", {"step": 1, "decision": "approved", "fingerprint": fp})
    assert status == 409 and "level above isn't approved" in json.loads(out)["error"] and not sysmodel.review_path(kid).exists()
    d = page_data(call("GET", "/")[2].decode())["levels"]["children"][0]
    assert (d["turn"], d["why"]) == ("ai", "the level above is not approved")


def test_serve_version_follows_every_level(served_tree):
    top, kid, call = served_tree
    version = lambda: json.loads(call("GET", "/api/version?level=C1")[2])["version"]
    seen = [version()]
    for f in (kid, sysmodel.review_path(kid), kid.with_name("decisions.md")):
        f.write_text(f.read_text() + "\n" if f.exists() else "## Step 1 Problem\nhi\n")
        seen.append(version())
    assert len(set(seen)) == len(seen)
    assert json.loads(call("GET", "/api/version")[2])["version"] == seen[-1]       # one version for the tree, whatever the level


def test_serve_of_a_level_opens_on_that_level(served_tree):
    top, kid, call = served_tree
    srv, kid_call = start(kid)
    try:
        assert page_data(kid_call("GET", "/")[2].decode())["levels"]["here"] == "C1"
        assert page_data(kid_call("GET", "/?level=")[2].decode())["levels"]["here"] == ""
    finally:
        srv.shutdown()
        srv.server_close()
