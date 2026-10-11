import copy
import http.client
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import sysmodel  # noqa: E402
from test_check import E, SCRIPT, VALID, drop, rules  # noqa: E402
from test_spec import approved  # noqa: E402

LV = HERE / "fixtures" / "levels"
APP = yaml.safe_load((LV / "app.yaml").read_text())
SEED = (LV / "C1" / "app.yaml").read_text()          # what `level app.yaml C1` writes


def level():
    """The fixture's C1 level after its AI wrote the purpose."""
    m = yaml.safe_load(SEED)
    m["system"]["purpose"] = "Answer the public HTTP requests: create short links and redirect visitors."
    return m


def l01(m, up=APP):
    return [(f["element"], f["message"]) for f in sysmodel.check_model(m, 1, up) if f["rule"] == "L01"]


def tree(tmp_path, kid=None):
    """The fixture's two levels in tmp_path, the top one approved; returns (top, level) paths."""
    top = Path(approved(tmp_path, APP))
    (tmp_path / "C1").mkdir()
    (tmp_path / "C1" / "app.yaml").write_text(yaml.safe_dump(kid or level(), sort_keys=False))
    return top, tmp_path / "C1" / "app.yaml"


# ---- the contract ----

def test_level_writes_the_contract(tmp_path, capsys):
    top = approved(tmp_path, APP)
    Path(top).write_text((LV / "app.yaml").read_text())              # the same model, in the fixture's key order
    assert sysmodel.main(["level", top, "C1"]) == 0
    assert (tmp_path / "C1" / "app.yaml").read_text() == SEED
    assert (tmp_path / "C1" / "decisions.md").read_text() == (
        "## Step 3 Parts\n\nFixed by the level above: Serverless functions; change it by a change request.\n")
    assert "Built with Serverless functions: fixed by the level above" in capsys.readouterr().out
    assert sysmodel.read_state(tmp_path / "C1" / "app.yaml")["handoff"] == {}   # nothing to approve before `wait`
    assert sysmodel.parent_of(tmp_path / "C1" / "app.yaml") == Path(top).resolve()


def test_contract_inherits_the_boundary_and_the_parts_requirements():
    m = sysmodel.contract(APP, "C1", "../app.yaml")
    assert m["system"]["id"] == "C1" and m["system"]["purpose"].startswith("TBD")
    assert m["sources"] == [{"id": "UP", "title": "The level above: ../app.yaml"}]
    assert m["external"] == [{"id": "E1", "name": "Web visitor", "kind": "external", "sends": ["I1", "I3"], "receives": ["I2", "I4"]},
                             {"id": "C2", "name": "Database", "kind": "external", "sends": ["I6"], "receives": ["I5"]}]
    reqs = {r["id"]: r for r in m["requirements"]}
    assert list(reqs) == ["Q1", "Q2", "Q5", "Q6", "Q7", "Q8"]      # Q3 and Q4 are shared out as Q6 and Q7
    assert all(r["source"] == "UP" and "derived_from" not in r and "parent" not in r for r in reqs.values())
    assert reqs["Q6"]["specifies"] == ["C1"] and reqs["Q8"]["specifies"] == ["C1"] and reqs["Q2"]["specifies"] == ["I1", "F11"]
    assert m["objectives"] == [{"id": "C1.O0", "name": "Value of Web service"}, {"id": "O1", "name": "Low running cost", "parent": "C1.O0"}]
    assert [(f["id"], f.get("parent")) for f in m["functions"]] == [("F1", None), ("F11", "F1"), ("F12", "F1")]
    assert not any("runs_in" in f for f in m["functions"]) and "components" not in m
    assert [(i["id"], i["between"], i["carries"]) for i in m["interfaces"]] == [
        ("IF1", ["C1", "E1"], ["I1", "I2", "I3", "I4"]), ("IF2", ["C1", "C2"], ["I5", "I6"])]
    assert [s["id"] for s in m["scenarios"]] == ["SC1"]                # SC2 names nothing that crosses
    assert [(t["id"], t["verifies"], t.get("scenarios")) for t in m["tests"]][2:4] == [("T3", ["Q6"], None), ("T4", ["Q7"], None)]


def test_contract_inherits_unshared_system_wide_requirements_only():
    up = copy.deepcopy(APP)
    drop(up, "requirements", "Q6")
    up["requirements"] += [
        {"id": "Q9", "text": "The web service shall be checked by real users.", "category": "qualification",
         "subcategory": "validation-plan", "stage": "release", "source": "SRC1", "specifies": ["C1"]},
        {"id": "Q10", "text": "The system shall favour low cost over speed.", "category": "trade-off",
         "subcategory": "cost-performance", "stage": "release", "source": "SRC1", "specifies": ["S"]}]
    reqs = {r["id"]: r for r in sysmodel.contract(up, "C1")["requirements"]}
    assert list(reqs) == ["Q1", "Q2", "Q5", "Q7", "Q8"]                # Q3 is a budget: apportioned, not copied (p. 251)
    assert reqs["Q8"]["specifies"] == ["C1"]                           # a constraint is copied by equivalence (p. 252)


def test_contract_computes_the_kind_of_each_outside_system():
    up = copy.deepcopy(APP)
    E(up, "functions", "F11")["outputs"] = ["I2"]                     # the database now only sends
    up["items"].append({"id": "I7", "name": "Build"})
    up["external"].append({"id": "E2", "name": "Build pipeline", "kind": "enabling", "sends": ["I7"]})
    E(up, "functions", "F11")["inputs"] = ["I1", "I7"]
    up["interfaces"].append({"id": "IF3", "between": ["E2", "S"], "carries": ["I7"]})
    ext = {e["id"]: e for e in sysmodel.contract(up, "C1")["external"]}
    assert ext["C2"] == {"id": "C2", "name": "Database", "kind": "context", "sends": ["I6"]}
    assert ext["E2"]["kind"] == "enabling" and ext["E1"]["kind"] == "external"


def test_contract_rolls_far_parts_up_and_keeps_whole_jobs():
    up = copy.deepcopy(VALID)
    E(up, "components", "C12")["subsystem"] = True
    up["components"].append({"id": "C21", "name": "Table", "parent": "C2"})
    E(up, "functions", "F2")["runs_in"] = "C21"
    m = sysmodel.contract(up, "C12")
    assert [(e["id"], e["kind"], e.get("sends"), e.get("receives")) for e in m["external"]] == [
        ("E1", "external", ["I3"], ["I4"]), ("C2", "context", ["I6"], None)]            # C21 is seen as C2
    assert [(i["id"], i["between"], i["carries"]) for i in m["interfaces"]] == [
        ("IF1", ["C12", "E1"], ["I3", "I4"]), ("IF2", ["C12", "C2"], ["I6"])]           # an interface on C1 covers C12
    assert [f["id"] for f in m["functions"]] == ["F12"] and "parent" not in m["functions"][0]
    assert E(m, "requirements", "Q5")["specifies"] == ["F12", "I3", "I4"]           # F1 becomes its leaves here
    E(up, "functions", "F11")["runs_in"] = "C12"
    m = sysmodel.contract(up, "C12")
    assert [(f["id"], f.get("parent")) for f in m["functions"]] == [("F1", None), ("F11", "F1"), ("F12", "F1")]
    up["functions"].append({"id": "F3", "name": "Report", "parent": "F0", "inputs": ["I6"], "outputs": ["I4"], "runs_in": "C12"})
    m = sysmodel.contract(up, "C12")
    assert [(f["id"], f.get("parent")) for f in m["functions"]][:2] == [("C12.F0", None), ("F1", "C12.F0")]
    assert E(m, "functions", "F3")["parent"] == "C12.F0"


def test_a_fresh_level_has_only_its_purpose_to_write(tmp_path):
    top = approved(tmp_path, APP)
    assert sysmodel.main(["level", top, "C1"]) == 0
    r = subprocess.run([sys.executable, str(SCRIPT), "check", str(tmp_path / "C1" / "app.yaml"), "--step", "1"],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert [x.split()[0] for x in r.stdout.splitlines() if " error " in x] == ["R24"]
    assert "1 errors, 0 warnings" in r.stdout
    assert {f["rule"] for f in sysmodel.check_model(level(), 1, APP)} == {"C03"}   # once the purpose is written


def test_a_level_needs_no_validation_or_acceptance_plan():
    assert [f["message"] for f in sysmodel.check_model(level(), 1, APP) if f["rule"] == "C03"] == [
        "there is no observance requirement", "there is no verification-plan requirement"]
    assert len([f for f in sysmodel.check_model(level(), 1) if f["rule"] == "C03"]) == 4


# ---- L01: the level keeps what the level above set ----

def test_l01_names_each_change_to_the_boundary():
    m = level()
    m["items"].append({"id": "I9", "name": "Log line"})
    E(m, "external", "E1").update(sends=["I1", "I9"], receives=["I2", "I4", "I9"])
    assert l01(m) == [("E1", "sends I9, the level above does not"), ("E1", "does not send I3, the level above does"),
                      ("E1", "receives I9, the level above does not")]
    m = level()
    drop(m, "external", "C2")
    m["external"].append({"id": "E3", "name": "Mailer", "kind": "external", "receives": ["I2"]})
    assert l01(m) == [("C2", "is in the level above but missing here; add it back to `external`"),
                      ("E3", "the level above does not connect this part to it; the boundary is set there, so send a change request")]


def test_l01_names_each_change_to_an_item():
    m = level()
    E(m, "items", "I1").update(name="URL", description="Any URL.")
    drop(m, "items", "I4")
    assert l01(m) == [("I1", "`name` is 'URL' here but 'Long URL' in the level above"),
                      ("I1", "`description` is 'Any URL.' here but 'The URL to shorten: an absolute http or https URL, 1 to 2000 "
                             "characters. Example: https://example.com/spring-sale?utm=mail' in the level above"),
                      ("I4", "is in the level above but missing here; add it back to `items`")]


def test_l01_names_each_change_to_an_inherited_requirement():
    m = level()
    E(m, "requirements", "Q6").update(threshold="99% monthly availability", text="The web service shall be up.")
    E(m, "requirements", "Q7").pop("objective")
    E(m, "requirements", "Q2").update(category="system-wide", subcategory="quality", stage="build",
                                      specifies=["C1"], source="SRC9")   # specifies and source are this level's
    drop(m, "requirements", "Q8")
    assert l01(m) == [("Q2", "`category` is 'system-wide' here but 'io' in the level above"),
                      ("Q2", "`subcategory` is 'quality' here but 'input' in the level above"),
                      ("Q2", "`stage` is 'build' here but 'release' in the level above"),
                      ("Q6", "`text` is 'The web service shall be up.' here but 'The web service shall be available 99.95% of each month.' in the level above"),
                      ("Q6", "`threshold` is '99% monthly availability' here but '99.95% monthly availability' in the level above"),
                      ("Q7", "`objective` is not set here but 'O1' in the level above"),
                      ("Q8", "is in the level above but missing here; add it back to `requirements`")]


def test_l01_names_each_change_to_an_objective_or_interface():
    m = level()
    E(m, "objectives", "O1").update(name="Cheap", weight=0.4)                    # weights are this level's
    E(m, "objectives", "C1.O0")["name"] = "Good web service"                    # so is the new root
    E(m, "interfaces", "IF1").update(between=["C1", "C2"], carries=["I1", "I2", "I3"])
    drop(m, "interfaces", "IF2")
    assert l01(m) == [("O1", "`name` is 'Cheap' here but 'Low running cost' in the level above"),
                      ("IF1", "`between` should join E1 to C1 or one of its parts, as in the level above"),
                      ("IF1", "does not carry I4, the level above does"),
                      ("IF2", "is in the level above but missing here; add it back to `interfaces`")]
    m = level()
    m["components"] = [{"id": "C1.C1", "name": "Router", "parent": "C1"}]
    E(m, "interfaces", "IF1")["between"] = ["E1", "C1.C1"]                       # the near end may be inside C1
    assert l01(m) == []


def test_l01_shows_drift_in_the_level_above(tmp_path, capsys):
    up = copy.deepcopy(APP)
    E(up, "external", "E1")["sends"] = ["I1", "I3", "I7"]
    up["items"].append({"id": "I7", "name": "Promo code"})
    E(up, "functions", "F11")["inputs"] = ["I1", "I7"]
    E(up, "interfaces", "IF1")["carries"].append("I7")
    _, kid = tree(tmp_path)
    (tmp_path / "app.yaml").write_text(yaml.safe_dump(up))
    assert sysmodel.main(["check", str(kid), "--step", "1"]) == 1
    out = capsys.readouterr().out
    assert 'L01 error  E1 "Web visitor": does not send I7, the level above does (book p.321)' in out
    assert 'L01 error  IF1 "Public HTTP": does not carry I7, the level above does (book p.321)' in out
    assert 'L01 error  I7: is in the level above but missing here; add it back to `items` (book p.321)' in out
    rows = sysmodel.progress(yaml.safe_load(kid.read_text()), {}, kid)
    assert rows[0]["turn"] == "ai" and rows[0]["errors"] == 3


def test_l01_waits_for_a_readable_level_above():
    up = copy.deepcopy(APP)
    E(up, "functions", "F11")["runs_in"] = "C9"
    assert l01(level(), up) == [("C1", "the level above has must-fix problems in its structure, "
                                       "so this level can't be compared with it; run check on it")]


def test_l01_only_runs_in_a_level():
    m = level()
    drop(m, "items", "I4")
    assert "L01" not in rules(m) and "L01" in rules(m, APP)


# ---- L02, L03, L04 ----

def test_l02_l03_l04():
    assert not {"L02", "L03", "L04"} & rules(APP)
    m = copy.deepcopy(APP)
    E(m, "requirements", "Q6")["specifies"] = ["S"]                              # a requirement on the whole system is no share
    assert [(f["element"], f["message"]) for f in sysmodel.check_model(m) if f["rule"] == "L03"] == [
        ("C1", "has no share of Q3; derive a requirement from Q3 that reaches this part")]
    m = copy.deepcopy(VALID)
    E(m, "components", "C12")["subsystem"] = True
    m["requirements"] += [{"id": f"Q{n}", "text": "The web service shall do its share.", "category": "system-wide",
                           "subcategory": "quality", "stage": "release", "derived_from": [q], "specifies": ["C12"],
                           "threshold": "1 unit"} for n, q in ((8, "Q3"), (9, "Q4"))]
    found = {(f["rule"], f["element"]) for f in sysmodel.check_model(m) if f["rule"] in ("L02", "L03", "L04")}
    assert found == {("L04", "F1")}                                              # F0, the top job, spans every part
    E(m, "requirements", "Q8")["specifies"] = ["C1"]                             # a share of the parent part is not the part's share
    assert {(f["rule"], f["element"]) for f in sysmodel.check_model(m) if f["rule"] == "L03"} == {("L03", "C12")}
    E(m, "requirements", "Q8")["specifies"] = ["C12"]
    E(m, "components", "C1")["subsystem"] = True
    assert ("L02", "C1") in {(f["rule"], f["element"]) for f in sysmodel.check_model(m)}


def test_l03_and_the_contract_agree_on_a_share_made_by_synthesis():
    m = copy.deepcopy(APP)
    q6 = E(m, "requirements", "Q6")                                              # the quality budget flowed down as outputs (p. 252)
    q6.update(category="io", subcategory="output", specifies=["F11", "I2"])
    del q6["threshold"]
    assert not [f for f in sysmodel.check_model(m) if f["rule"] == "L03"]
    assert "Q3" not in {r["id"] for r in sysmodel.contract(m, "C1")["requirements"]}


def test_a_budget_on_a_part_above_is_apportioned_again():
    m = copy.deepcopy(APP)
    m["components"] = [{"id": "C0", "name": "Backend", "parent": "S"}, {"id": "C1", "name": "Web service", "parent": "C0", "subsystem": True},
                       {"id": "C3", "name": "Cache", "parent": "C0"}, {"id": "C2", "name": "Database", "parent": "S"}]
    E(m, "requirements", "Q7")["specifies"] = ["C0"]
    assert {(f["rule"], f["element"]) for f in sysmodel.check_model(m, 4) if f["rule"] == "L03"} == {("L03", "C1")}
    assert "Q7" not in {r["id"] for r in sysmodel.contract(m, "C1")["requirements"]}


def test_subsystem_is_a_boolean():
    m = copy.deepcopy(APP)
    E(m, "components", "C1")["subsystem"] = "yes"
    assert rules(m) == {"S01"}


# ---- finding the levels ----

def test_parent_of_follows_the_folders_only_for_a_subsystem_level(tmp_path):
    top, kid = tree(tmp_path)
    assert sysmodel.parent_of(kid) == top.resolve() and sysmodel.parent_of(top) is None
    assert sysmodel.root_of(kid) == top.resolve() and sysmodel.root_of(top) == top
    assert sysmodel.level_files(top) == {"": top, "C1": tmp_path / "C1" / "app.yaml"}
    for folder, sid in (("C9", "C9"), ("C2", "C2"), ("C1", "X")):                # not a part, not a subsystem, wrong id
        (tmp_path / folder).mkdir(exist_ok=True)
        stray = tmp_path / folder / "app.yaml"
        stray.write_text(yaml.safe_dump({**level(), "system": {**level()["system"], "id": sid}}))
        assert sysmodel.parent_of(stray) is None
    assert sysmodel.level_files(top) == {"": top}
    (tmp_path / "C1" / "notes.yaml").write_text(yaml.safe_dump(level()))       # another file name is another model
    assert sysmodel.parent_of(tmp_path / "C1" / "notes.yaml") is None


def test_level_files_go_down_every_level(tmp_path):
    top, kid = tree(tmp_path)
    m = level()
    m["components"] = [{"id": "C1.C1", "name": "Router", "parent": "C1", "subsystem": True}]
    kid.write_text(yaml.safe_dump(m))
    (tmp_path / "C1" / "C1.C1").mkdir()
    grandkid = tmp_path / "C1" / "C1.C1" / "app.yaml"
    grandkid.write_text(yaml.safe_dump({**m, "system": {**m["system"], "id": "C1.C1"}}))
    assert sysmodel.level_files(top) == {"": top, "C1": kid, "C1/C1.C1": grandkid}
    assert sysmodel.root_of(grandkid) == top.resolve()


# ---- `level` refuses ----

def test_level_refuses_until_the_design_is_approved(tmp_path):
    top = tmp_path / "app.yaml"
    top.write_text(yaml.safe_dump(APP))
    with pytest.raises(SystemExit) as e:
        sysmodel.main(["level", str(top), "C1"])
    assert e.value.code == (f"{top} isn't fully approved (step 1 Problem: ready for review); "
                            "a level starts from an approved design")
    assert not (tmp_path / "C1").exists()


def test_level_refuses_a_part_that_is_not_a_subsystem_or_has_a_level(tmp_path):
    top = approved(tmp_path, APP)
    for bad in ("C2", "X9"):
        with pytest.raises(SystemExit) as e:
            sysmodel.main(["level", top, bad])
        assert e.value.code == f"{bad} is not a subsystem part; set `subsystem: true` on it in step 3 first"
    assert sysmodel.main(["level", top, "C1"]) == 0
    with pytest.raises(SystemExit) as e:
        sysmodel.main(["level", top, "C1"])
    assert e.value.code == f"{tmp_path / 'C1' / 'app.yaml'} exists already"


def test_level_refuses_while_a_level_above_is_not_approved(tmp_path):
    top, kid = tree(tmp_path)
    m = copy.deepcopy(APP)
    E(m, "tests", "T1")["name"] = "Create a link"
    top.write_text(yaml.safe_dump(m))
    with pytest.raises(SystemExit) as e:
        sysmodel.main(["level", str(kid), "C1.C1"])
    assert e.value.code.startswith(f"{top.resolve()} isn't fully approved (step 6 Test plan: changed since approved by ana")


# ---- a level waits for the one above ----

def stale(top):
    """The top level's test plan changes after its approval."""
    m = yaml.safe_load(top.read_text())
    E(m, "tests", "T1")["name"] = "Create a link"
    top.write_text(yaml.safe_dump(m))


def turns(f):
    return {r["step"]: (r["turn"], r["why"]) for r in sysmodel.progress(yaml.safe_load(f.read_text()), sysmodel.load_reviews(sysmodel.review_path(f)), f)}


def test_a_level_is_not_up_for_review_while_the_level_above_is_not_approved(tmp_path):
    top, kid = tree(tmp_path)
    assert turns(kid)[1] == ("person", "ready for review")
    stale(top)
    assert turns(kid)[1] == ("ai", "the level above is not approved")
    assert turns(kid)[2] == ("ai", "the level above is not approved") and turns(kid)[3] == ("ai", "not started")
    kid.write_text(yaml.safe_dump({**level(), "requirements": level()["requirements"][:-1]}))   # editing stays allowed
    assert turns(kid)[1][1].endswith("must fix")                                   # L01 asks for Q8 back


def whole_level():
    """The fixture's C1 level, finished: Router is a subsystem part of it that does both jobs."""
    m = level()
    m["components"] = [{"id": "C1.C1", "name": "Router", "parent": "C1", "subsystem": True}]
    for f in m["functions"]:
        if f["id"] in ("F11", "F12"):
            f["runs_in"] = "C1.C1"
    return m


def approve(f):
    m = yaml.safe_load(f.read_text())
    sysmodel.review_path(f).write_text(yaml.safe_dump(
        {n: {"decision": "approved", "by": "ana", "at": "2026-10-10T09:00", "fingerprint": sysmodel.fingerprint(m, n)} for n in range(1, 7)}))


def test_the_gate_goes_up_every_level(tmp_path):
    top, kid = tree(tmp_path, whole_level())
    approve(kid)
    assert sysmodel.main(["level", str(kid), "C1.C1"]) == 0
    grand = tmp_path / "C1" / "C1.C1" / "app.yaml"
    assert sysmodel.parent_of(grand) == kid.resolve()
    g = yaml.safe_load(grand.read_text())
    g["system"]["purpose"] = "Pick the endpoint that answers each request."
    grand.write_text(yaml.safe_dump(g))
    assert turns(grand)[1] == ("ai", "the AI is still working on it")              # `level` leaves the hand-off empty
    stale(top)                                                                      # the middle level is still approved
    assert [r["turn"] for r in sysmodel.progress(yaml.safe_load(kid.read_text()), sysmodel.load_reviews(sysmodel.review_path(kid)), kid)] == ["done"] * 6
    assert turns(grand)[1] == ("ai", "the level above is not approved")


def http_post(model, step, decision):
    """One approval sent to a review app serving model; returns (status, reply)."""
    srv = sysmodel.make_server(model, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        m = yaml.safe_load(Path(model).read_text())
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1])
        c.request("POST", "/api/review", json.dumps({"step": step, "decision": decision, "note": "", "checked": [],
                                                     "fingerprint": sysmodel.fingerprint(m, step)}), {"Content-Type": "application/json"})
        r = c.getresponse()
        return r.status, json.loads(r.read())
    finally:
        srv.shutdown()
        srv.server_close()


def test_a_level_cannot_be_approved_while_the_level_above_is_not_approved(tmp_path):
    top, kid = tree(tmp_path)
    stale(top)
    status, out = http_post(kid, 1, "approved")
    assert status == 409 and "level above isn't approved" in out["error"]
    assert not sysmodel.review_path(kid).exists()
    assert http_post(kid, 1, "sent back")[0] == 400                               # a send back still needs its note
    sysmodel.review_path(top).write_text(yaml.safe_dump(                          # the top level is approved again
        {n: {"decision": "approved", "by": "ana", "at": "2026-10-10T09:00", "fingerprint": sysmodel.fingerprint(yaml.safe_load(top.read_text()), n)}
         for n in range(1, 7)}))
    status, out = http_post(kid, 1, "approved")
    assert status == 200 and out["progress"][0]["turn"] == "done"


def test_no_step_of_a_level_can_be_approved_while_the_level_above_is_not_approved(tmp_path):
    top, kid = tree(tmp_path)
    approve(kid)
    stale(top)
    assert http_post(kid, 1, "approved")[0] == 409                                # already approved
    m = yaml.safe_load(kid.read_text())
    sysmodel.write_state(kid, handoff={})
    sysmodel.review_path(kid).write_text(yaml.safe_dump({2: {"decision": "sent back", "by": "ana", "at": "2026-10-10T09:00",
                                                           "fingerprint": sysmodel.fingerprint(m, 2), "note": "redo"}}))
    assert turns(kid)[2][0] == "ai" and http_post(kid, 2, "approved")[0] == 409   # sent back, not changed


def test_wait_hands_over_only_the_first_open_step_of_a_level(tmp_path, monkeypatch):
    monkeypatch.setattr(sysmodel.tempfile, "tempdir", str(tmp_path))
    top, kid = tree(tmp_path)
    assert turns(kid)[2][0] == "person"                                          # seeded, never worked on
    assert sysmodel.wait_for_review(kid) is None
    assert set(sysmodel.read_state(kid)["handoff"]) == {"1"}                      # the seeded steps 2, 5 and 6 stay the AI's


def test_a_level_with_drift_cannot_be_approved(tmp_path):
    m = level()
    drop(m, "items", "I4")
    _, kid = tree(tmp_path, m)
    status, out = http_post(kid, 1, "approved")
    assert status == 409 and "must-fix" in out["error"]


# ---- status ----

def test_status_lists_the_levels_below(tmp_path, capsys):
    top = Path(approved(tmp_path, APP))
    sysmodel.main(["status", str(top)])
    assert f"Levels below:\n  C1 needs its level: run level {top} C1\n" in capsys.readouterr().out
    assert sysmodel.main(["level", str(top), "C1"]) == 0
    capsys.readouterr()
    sysmodel.main(["status", str(top)])
    assert "Levels below:\n  C1 Web service: step 1 Problem, the AI's turn (1 must fix)\n" in capsys.readouterr().out
    kid = tmp_path / "C1" / "app.yaml"
    m = level()
    drop(m, "items", "I4")
    kid.write_text(yaml.safe_dump(m))
    sysmodel.main(["status", str(top)])
    assert "  C1 Web service: step 1 Problem, the AI's turn (5 must fix); 1 L01 findings, it has drifted from this level\n" in capsys.readouterr().out


def test_status_names_the_level_above_and_goes_down_levels(tmp_path, capsys):
    top, kid = tree(tmp_path)
    m = level()
    m["components"] = [{"id": "C1.C1", "name": "Router", "parent": "C1", "subsystem": True}]
    kid.write_text(yaml.safe_dump(m))
    sysmodel.main(["status", str(kid)])
    out = capsys.readouterr().out
    assert "Level above: ../app.yaml (this is C1 of it)" in out
    assert f"Levels below:\n  C1.C1 needs its level: run level {kid} C1.C1\n" in out
    sysmodel.main(["status", str(top)])
    out = capsys.readouterr().out
    assert "Level above" not in out and "  C1 Web service: step 1 Problem, waiting for a person (ready for review)" in out
    assert f"    C1.C1 needs its level: run level {kid} C1.C1" in out
    stale(top)
    sysmodel.main(["status", str(top)])
    assert "  C1 Web service: step 1 Problem, the AI's turn (the level above is not approved)" in capsys.readouterr().out


def test_status_says_when_a_folder_is_not_the_level(tmp_path, capsys):
    top = Path(approved(tmp_path, APP))
    (tmp_path / "C1").mkdir()
    (tmp_path / "C1" / "app.yaml").write_text(yaml.safe_dump({**level(), "system": {**level()["system"], "id": "X"}}))
    sysmodel.main(["status", str(top)])
    assert f"  C1: {tmp_path / 'C1' / 'app.yaml'} isn't its level (its system id must be C1); move or fix it" in capsys.readouterr().out


# ---- wait and the review app watch every level ----

def test_the_review_app_is_the_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(sysmodel.tempfile, "tempdir", str(tmp_path))
    top, kid = tree(tmp_path)
    assert sysmodel.serve_alive(kid) is None
    sysmodel.write_state(top, serve={"pid": os.getpid(), "url": "http://127.0.0.1:8765/"})
    assert sysmodel.serve_alive(kid)["url"] == "http://127.0.0.1:8765/"
    sysmodel.write_state(kid, handoff={"1": "x"})                                   # the hand-off stays with the level
    assert "handoff" not in sysmodel.read_state(top) and sysmodel.read_state(kid)["handoff"] == {"1": "x"}


def test_wait_reports_the_level_that_changed(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sysmodel.tempfile, "tempdir", str(tmp_path))
    top, kid = tree(tmp_path)
    sysmodel.write_state(top, serve={"pid": os.getpid(), "url": "u"})
    sent = {"decision": "sent back", "by": "ana", "at": "2026-10-10T09:05", "note": "Say more"}
    real_sleep = sysmodel.time.sleep
    def decide_then_sleep(_):                                                       # the person clicks in the child level
        sysmodel.review_path(kid).write_text(yaml.safe_dump({1: sent}))
        real_sleep(0)
    monkeypatch.setattr(sysmodel.time, "sleep", decide_then_sleep)
    assert sysmodel.main(["wait", str(top)]) == 0                                   # waiting on the root sees the child
    assert capsys.readouterr().out == ("Level C1: Step 1 Problem: sent back by ana, 2026-10-10 09:05\nNote: Say more\n\n"
                                       "Run `status` and go on with the loop.\n")
    handed = sysmodel.read_state(kid)["handoff"]                                    # every level is handed over
    assert handed["1"] == sysmodel.fingerprint(level(), 1)
    assert sysmodel.read_state(top)["handoff"] == {}                                # nothing of the root's is up for review
