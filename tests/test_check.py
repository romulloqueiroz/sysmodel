import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
SCRIPT = HERE.parent / "sysmodel.py"
sys.path.insert(0, str(HERE.parent))
import sysmodel  # noqa: E402

VALID = yaml.safe_load((HERE / "fixtures" / "valid.yaml").read_text())


def E(m, key, id):
    return next(x for x in m[key] if x["id"] == id)


def rules(m):
    return {f["rule"] for f in sysmodel.check_model(m)}


def drop(m, key, id):
    m[key] = [x for x in m[key] if x["id"] != id]


def add_fn(m, n):
    for k in range(n):
        m["functions"].append({"id": f"X{k}", "name": "extra", "parent": "F0"})


def two_roots(m):
    del E(m, "functions", "F2")["parent"]


def req_cycle(m):
    E(m, "requirements", "Q0")["parent"] = "Q1"


def fn_cycle(m):
    E(m, "functions", "F1")["parent"] = "F11"


def comp_cycle(m):
    E(m, "components", "C1")["parent"] = "C11"


def obj_cycle(m):
    m["objectives"] = [{"id": "O1", "name": "a", "parent": "O2"}, {"id": "O2", "name": "b", "parent": "O1"}]


def spec(q, *ids):
    return lambda m: E(m, "requirements", q).update(specifies=list(ids))


def setf(key, id, **kw):
    return lambda m: E(m, key, id).update(kw)


def unset(key, id, field):
    return lambda m: E(m, key, id).pop(field)


def no_funcs(m):
    m["functions"] = []


def lone_comp(m):
    m["components"].append({"id": "C3", "name": "Cache", "parent": "S"})


DERIVED = {"id": "Q9", "text": "The database shall be available 99.97% of each month.", "category": "system-wide",
           "subcategory": "quality", "stage": "release", "derived_from": ["Q3"], "threshold": "99.97% monthly availability"}


CASES = [
    ("S02", lambda m: m["items"].append({"id": "I1", "name": "dup"})),
    ("S02", lambda m: m["system"].update(id="Q1")),
    ("S03", setf("requirements", "Q1", parent="NOPE")),
    ("S03", setf("functions", "F11", runs_in="I1")),
    ("S03", setf("requirements", "Q1", source="SH1")),
    ("S03", setf("requirements", "Q1", derived_from=["F1"])),
    ("S03", setf("requirements", "Q1", specifies=["T1"])),
    ("S03", setf("requirements", "Q4", objective="Q1")),
    ("S03", setf("sources", "SRC1", stakeholder="NOPE")),
    ("S03", setf("components", "C11", parent="F1")),
    ("S03", setf("interfaces", "IF1", between=["E1", "I1"])),
    ("S03", setf("tests", "T1", verifies=["F1"])),
    ("S03", setf("external", "E1", sends=["F1"])),
    ("R01", unset("requirements", "Q1", "category")),
    ("R02", setf("requirements", "Q1", subcategory="technology")),
    ("R02", unset("requirements", "Q1", "subcategory")),
    ("R03", setf("requirements", "Q1", stage="running")),
    ("R03", unset("requirements", "Q1", "stage")),
    ("R04", setf("requirements", "Q0", specifies=["S"])),
    ("R04", lambda m: m["tests"].append({"id": "T9", "name": "t", "method": "manual", "verifies": ["Q0"]})),
    ("R05", spec("Q2", "F11")),
    ("R05", spec("Q2", "I1")),
    ("R05", spec("Q2", "I1", "F1")),
    ("R06", spec("Q3", "S", "F0")),
    ("R06", spec("Q3", "C1")),
    ("R06", lambda m: m["requirements"].append({**DERIVED, "specifies": ["F2"]})),
    ("R07", spec("Q1", "F11")),
    ("R07", spec("Q1", "I1")),
    ("R08", lambda m: add_fn(m, 6)),
    ("R08", lambda m: drop(m, "functions", "F2")),
    ("R09", two_roots),
    ("R09", no_funcs),
    ("R10", setf("external", "E1", sends=["I1", "I2"])),
    ("R10", setf("external", "E1", receives=["I2", "I3"])),
    ("R11", fn_cycle),
    ("R11", comp_cycle),
    ("R11", req_cycle),
    ("R11", obj_cycle),
    ("R14", unset("functions", "F11", "runs_in")),
    ("R14", setf("functions", "F11", runs_in="C1")),
    ("R14", setf("functions", "F1", runs_in="C2")),
    ("R15", setf("functions", "F12", runs_in="C2")),
    ("R16", lone_comp),
    ("R17", setf("functions", "F2", runs_in="C12")),
    ("R17", setf("functions", "F12", runs_in="C2")),
    ("R18", lambda m: E(m, "external", "E2").update(kind="context", receives=["I2"])),
    ("R20", unset("functions", "F11", "done_when")),
    ("R21", unset("requirements", "Q1", "source")),
    ("R21", lambda m: (E(m, "requirements", "Q1").pop("source"), E(m, "requirements", "Q1").update(derived_from=[]))),
    ("R23", unset("requirements", "Q3", "threshold")),
    ("R24", lambda m: E(m, "requirements", "Q1").update(text="The system shall create links, rules TBD.")),
    ("R24", setf("requirements", "Q3", threshold="tbr")),
    ("R24", setf("requirements", "Q0", text="Group of TBD things")),
    ("R25", lambda m: drop(m, "tests", "T1")),
    ("R25", lambda m: drop(m, "tests", "T3")),
    ("R26", setf("requirements", "Q1", text="The system creates short links.")),
    ("R29", setf("interfaces", "IF2", between=["C1", "C1"])),
    ("R29", setf("interfaces", "IF1", between=["E1", "E2"])),
    ("R30", spec("Q3")),
    ("R30", spec("Q1", "E1")),
    ("R30", setf("interfaces", "IF2", carries=["I6"])),
    ("R30", lambda m: drop(m, "interfaces", "IF1")),
    ("R30", setf("interfaces", "IF1", between=["E1", "C11"])),
]


def test_valid_has_no_findings():
    assert sysmodel.check_model(copy.deepcopy(VALID)) == []


def test_derived_system_wide_requirement_specifies_its_parts():
    # Step 4 shares a system-wide number out to the parts it applies to (p. 249).
    m = copy.deepcopy(VALID)
    m["requirements"].append({**DERIVED, "specifies": ["C2"]})
    assert "R06" not in rules(m)


@pytest.mark.parametrize("rule,mutate", CASES)
def test_rule_fires(rule, mutate):
    m = copy.deepcopy(VALID)
    mutate(m)
    assert rule in rules(m)


def test_every_rule_has_a_case():
    assert {r[0] for r in sysmodel.RULES} - {"S01"} <= {r for r, _ in CASES}


def test_s01_stops_everything_else():
    m = copy.deepcopy(VALID)
    del m["system"]["name"]
    m["items"].append({"id": "I1", "name": "dup"})
    assert rules(m) == {"S01"}


def test_s01_unknown_field():
    m = copy.deepcopy(VALID)
    m["bogus"] = 1
    assert rules(m) == {"S01"}


def test_s01_says_what_is_wrong_and_where():
    # Our own small checker covers each keyword schema.json uses.
    m = copy.deepcopy(VALID)
    del m["system"]["name"]
    m["requirements"][0]["stage"] = "later"
    E(m, "items", "I1")["id"] = "9x"
    m["objectives"] = [{"id": "O1", "name": "a", "weight": 3}]
    E(m, "interfaces", "IF1")["between"] = ["E1"]
    m["tests"][0]["method"] = 7
    m["bogus"] = 1
    got = {(f["element"], f["message"]) for f in sysmodel.check_model(m)}
    assert got == {
        ("(file)", "Additional properties are not allowed ('bogus' unexpected)"),
        ("system", "'name' is a required property"),
        ("requirements/0/stage", "'later' is not one of ['build', 'release', 'running', 'updates', 'shutdown']"),
        ("items/0/id", "'9x' does not match '^[A-Za-z][A-Za-z0-9_.-]*$'"),
        ("objectives/0/weight", "3 is greater than the maximum of 1"),
        ("interfaces/0/between", "['E1'] should have at least 2 items"),
        ("tests/0/method", "7 is not one of ['automated', 'manual']")}


def test_r30_parts_are_distinguishable():
    m = copy.deepcopy(VALID)
    spec("Q3")(m)
    assert [f["message"][:3] for f in sysmodel.check_model(m) if f["rule"] == "R30"] == ["(a)"]
    m = copy.deepcopy(VALID)
    drop(m, "interfaces", "IF1")
    assert {f["message"][:3] for f in sysmodel.check_model(m) if f["rule"] == "R30"} == {"(b)"}


def test_interface_at_parent_covers_children():
    # IF1/IF2 sit on C1, yet cover flows to C11 and C12; moving IF2 to C11 breaks the C12 flow.
    m = copy.deepcopy(VALID)
    E(m, "interfaces", "IF2")["between"] = ["C11", "C2"]
    msgs = [f["message"] for f in sysmodel.check_model(m) if f["rule"] == "R30"]
    assert len(msgs) == 1 and "C2 -> C12" in msgs[0]


def test_tbd_is_whole_word():
    m = copy.deepcopy(VALID)
    E(m, "requirements", "Q1")["text"] = "The system shall handle outbound TBDX links."
    assert "R24" not in rules(m)


def test_custom_stages():
    m = copy.deepcopy(VALID)
    m["stages"] = ["build"]
    assert [f["element"] for f in sysmodel.check_model(m) if f["rule"] == "R03"] == ["Q1", "Q2", "Q3", "Q4"]


def test_group_requirements_skip_leaf_rules():
    m = copy.deepcopy(VALID)
    assert "Q0" not in {f["element"] for f in sysmodel.check_model(m)}


def run_cli(tmp_path, m, *flags):
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(m))
    return subprocess.run([sys.executable, str(SCRIPT), "check", str(p), *flags],
                          capture_output=True, text=True)


def test_cli_valid(tmp_path):
    r = run_cli(tmp_path, VALID)
    assert r.returncode == 0
    assert "Needs human sign-off" in r.stdout and "R27" in r.stdout
    assert "0 errors, 0 warnings, 0 advice" in r.stdout


def test_cli_error_line_and_order(tmp_path):
    m = copy.deepcopy(VALID)
    unset("functions", "F11", "runs_in")(m)
    unset("functions", "F11", "done_when")(m)
    r = run_cli(tmp_path, m)
    assert r.returncode == 1
    lines = r.stdout.splitlines()
    assert 'R14 error  F11 "Create short link": not allocated to a component (book p.243)' in lines
    assert lines.index(next(x for x in lines if x.startswith("R14"))) < lines.index(
        next(x for x in lines if x.startswith("R20")))


def test_cli_json(tmp_path):
    m = copy.deepcopy(VALID)
    unset("functions", "F11", "done_when")(m)
    r = run_cli(tmp_path, m, "--json")
    out = json.loads(r.stdout)
    assert r.returncode == 0
    assert out["findings"] == [{"rule": "R20", "severity": "warning", "element": "F11",
                                "message": "no done_when", "page": 58}]
    assert [j["rule"] for j in out["judgment"]] == ["R12", "R13", "R19", "R27", "R28"]
    assert out["counts"] == {"error": 0, "warning": 1, "advice": 0}


def test_r30a_skips_trade_off_and_qualification():
    # Trade-off preferences apply to the whole design; only io and system-wide must reach a component.
    m = copy.deepcopy(VALID)
    E(m, "requirements", "Q4").update(category="trade-off", specifies=[])
    assert "R30" not in rules(m)


def test_system_as_interface_endpoint_covers_components():
    # Before components are designed, the book draws external interfaces on the system itself.
    m = copy.deepcopy(VALID)
    E(m, "interfaces", "IF1")["between"] = ["E1", "S"]
    assert sysmodel.check_model(m) == []


def step1_model():
    """The fixture as it looks after step 1: problem defined, nothing designed yet."""
    m = copy.deepcopy(VALID)
    for key in ("functions", "components", "interfaces", "tests"):
        del m[key]
    for r in m["requirements"]:
        if r.get("category") == "io":
            r.pop("specifies", None)
    return m


def test_step1_model_is_clean_at_step1():
    assert sysmodel.check_model(step1_model(), step=1) == []


def test_step1_model_fails_at_step2():
    assert {"R05", "R07", "R09"} <= rules_at(step1_model(), 2)


def test_later_rules_wait_for_their_step():
    m = copy.deepcopy(VALID)
    del m["tests"]
    assert "R25" not in rules_at(m, 5)
    assert "R25" in rules_at(m, 6)


def test_every_rule_has_a_step():
    assert all(1 <= r[1] <= 6 for r in sysmodel.RULES)
    assert all(1 <= j[1] <= 6 for j in sysmodel.JUDGMENT)


def test_cli_step_filters_checklist():
    out = subprocess.run([sys.executable, str(SCRIPT), "check", str(HERE / "fixtures" / "valid.yaml"), "--step", "1"],
                         capture_output=True, text=True).stdout
    assert out.startswith("Checking steps 1-1: Problem")
    assert "R19" in out and "R12" not in out


def rules_at(m, step):
    return {f["rule"] for f in sysmodel.check_model(m, step)}


# ---- render ----

def page_data(html):
    blob = html.split('<script type="application/json" id="data">')[1].split("</script>")[0]
    return json.loads(blob)


def test_render_embeds_model_findings_and_checklist():
    m = copy.deepcopy(VALID)
    E(m, "functions", "F2").pop("runs_in")
    d = page_data(sysmodel.render(m, 4))
    assert d["drawable"] and d["step"] == 4 and d["model"]["system"]["id"] == "S"
    assert {(f["rule"], f["element"], f["step"]) for f in d["findings"]} >= {("R14", "F2", 4)}
    assert {j["rule"] for j in d["judgment"]} == {"R12", "R13", "R19", "R27", "R28"}
    assert all(f["step"] <= 4 for f in d["findings"])


def test_render_escapes_script_end():
    m = copy.deepcopy(VALID)
    m["system"]["purpose"] = "</script><b>hi</b>"
    html = sysmodel.render(m)
    assert page_data(html)["model"]["system"]["purpose"] == "</script><b>hi</b>"
    assert html.count("</script>") == html.count("<script")


def test_render_schema_errors_not_drawable():
    m = copy.deepcopy(VALID)
    m["bogus"] = 1
    d = page_data(sysmodel.render(m))
    assert not d["drawable"] and d["findings"][0]["rule"] == "S01"


def test_cli_render_writes_next_to_model(tmp_path):
    src = tmp_path / "app.yaml"
    src.write_text((HERE / "fixtures" / "valid.yaml").read_text())
    r = subprocess.run([sys.executable, str(SCRIPT), "render", str(src), "--step", "2"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert page_data((tmp_path / "app.html").read_text())["step"] == 2
