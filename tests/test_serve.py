import copy
import http.client
import json
import sys
import threading
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import sysmodel  # noqa: E402
from test_check import E, VALID, page_data  # noqa: E402


def changed_steps(edit):
    m = copy.deepcopy(VALID)
    edit(m)
    return {n for n in range(1, 7) if sysmodel.fingerprint(m, n) != sysmodel.fingerprint(VALID, n)}


def test_fingerprint_covers_only_what_the_step_shows():
    assert changed_steps(lambda m: E(m, "tests", "T1").update(name="x")) == {6}
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


@pytest.fixture
def served(tmp_path):
    model = tmp_path / "app.yaml"
    model.write_text(yaml.safe_dump(VALID))
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
