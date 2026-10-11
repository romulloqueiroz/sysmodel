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


def rules(m, up=None):
    return {f["rule"] for f in sysmodel.check_model(m, up=up)}


def settled(found):
    """Findings other than C03: the fixture has no qualification requirements, so C03 advises on all four."""
    return [f for f in found if f["rule"] != "C03"]


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


def add_e2(m, **kw):
    m["external"].append({"id": "E2", "name": "Build pipeline", "kind": "enabling", **kw})


def drifted_level(m):
    """m becomes the own level of part C2, with a boundary item renamed; returns the level above."""
    up = copy.deepcopy(m)
    E(up, "components", "C2")["subsystem"] = True
    m.clear()
    m.update(sysmodel.contract(up, "C2"))
    E(m, "items", "I5")["name"] = "Row"
    return up


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
    ("R05", spec("Q2", "I1", "F12")),
    ("R05", spec("Q2", "I1", "I3", "F11")),
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
    ("R10", setf("external", "E1", sends=["I3"])),
    ("R10", setf("external", "E1", receives=["I2"])),
    ("R10", setf("functions", "F11", inputs=["I1", "I7"])),
    ("R11", fn_cycle),
    ("R11", comp_cycle),
    ("R11", req_cycle),
    ("R11", lambda m: E(m, "requirements", "Q1").update(derived_from=["Q1"])),
    ("R11", lambda m: (E(m, "requirements", "Q1").update(derived_from=["Q2"]),
                       E(m, "requirements", "Q2").update(derived_from=["Q1"]))),
    ("R11", obj_cycle),
    ("R14", unset("functions", "F11", "runs_in")),
    ("R14", setf("functions", "F11", runs_in="C1")),
    ("R14", setf("functions", "F1", runs_in="C2")),
    ("R15", setf("functions", "F12", runs_in="C2")),
    ("R16", lone_comp),
    ("R17", setf("functions", "F2", runs_in="C12")),
    ("R17", setf("functions", "F12", runs_in="C2")),
    ("R18", setf("external", "E1", kind="context")),
    ("R18", lambda m: add_e2(m)),
    ("R18", setf("external", "E1", kind="external", receives=[], sends=["I1", "I3"])),
    ("R18", setf("external", "E1", kind="context", sends=[])),
    ("R20", unset("functions", "F11", "done_when")),
    ("R21", unset("requirements", "Q1", "source")),
    ("R21", lambda m: (E(m, "requirements", "Q1").pop("source"), E(m, "requirements", "Q1").update(derived_from=[]))),
    ("R23", unset("requirements", "Q3", "threshold")),
    ("R23", unset("requirements", "Q4", "threshold")),
    ("R23", lambda m: E(m, "requirements", "Q4").update(subcategory="schedule", threshold="")),
    ("R24", lambda m: E(m, "requirements", "Q1").update(text="The system shall create links, rules TBD.")),
    ("R24", setf("requirements", "Q3", threshold="tbr")),
    ("R24", setf("requirements", "Q0", text="Group of TBD things")),
    ("R24", lambda m: m["system"].update(purpose="TBD")),
    ("R25", lambda m: drop(m, "tests", "T1")),
    ("R25", lambda m: drop(m, "tests", "T3")),
    ("R26", setf("requirements", "Q1", text="The system creates short links.")),
    ("R29", setf("interfaces", "IF2", between=["C1", "C1"])),
    ("R29", lambda m: (add_e2(m, sends=["I1"]), E(m, "interfaces", "IF1").update(between=["E1", "E2"]))),
    ("R30", spec("Q3")),
    ("R30", spec("Q1", "E1")),
    ("R30", setf("interfaces", "IF2", carries=["I6"])),
    ("R30", lambda m: drop(m, "interfaces", "IF1")),
    ("R30", setf("interfaces", "IF1", between=["E1", "C11"])),
    ("C01", spec("Q2", "F11")),
    ("C02", lambda m: m["objectives"].append({"id": "O2", "name": "Fast"})),
    ("C02", lambda m: m["objectives"].append({"id": "O2", "name": "Cheap hosting", "parent": "O1"})),
    ("C03", lambda m: None),
    ("C04", lambda m: m["objectives"].append({"id": "O2", "name": "Fast", "weight": 0.5})
     or E(m, "objectives", "O1").update(weight=0.3)),
    ("C05", lambda m: m.update(scenarios=[{"id": "SC1", "name": "Visit", "steps": ["Web visitor sends Short code"]}])),
    ("C06", setf("interfaces", "IF2", carries=["I5", "I6", "I1"])),
    ("C06", setf("interfaces", "IF1", carries=["I1", "I2", "I3", "I4", "I5"])),
    ("L01", drifted_level),
    ("L02", setf("components", "C1", subsystem=True)),
    ("L03", setf("components", "C2", subsystem=True)),
    ("L04", setf("components", "C12", subsystem=True)),
]


def test_valid_has_no_errors_or_warnings():
    found = sysmodel.check_model(copy.deepcopy(VALID))
    assert [(f["rule"], f["element"], f["severity"]) for f in found] == [("C03", "S", "advice")] * 4
    assert settled(found) == []


def test_valid_models_every_unit_of_the_boundary():
    # Each external exchanges items, and each item crosses the boundary one way or the other.
    assert {e["id"] for e in VALID["external"]} == {"E1"}


def test_derived_system_wide_requirement_specifies_its_parts():
    # Step 4 shares a system-wide number out to the parts it applies to (p. 249).
    m = copy.deepcopy(VALID)
    m["requirements"].append({**DERIVED, "specifies": ["C2"]})
    assert "R06" not in rules(m)


@pytest.mark.parametrize("rule,mutate", CASES)
def test_rule_fires(rule, mutate):
    m = copy.deepcopy(VALID)
    up = mutate(m)                                                # a case may return the level above
    assert rule in rules(m, up if isinstance(up, dict) else None)


def test_every_rule_has_a_case():
    assert {r[0] for r in sysmodel.RULES} - {"S01"} <= {r for r, _ in CASES}


def test_s01_stops_everything_else():
    m = copy.deepcopy(VALID)
    del m["system"]["name"]
    m["items"].append({"id": "I1", "name": "dup"})
    assert rules(m) == {"S01"}


def test_component_choice_is_a_string():
    m = copy.deepcopy(VALID)
    assert E(m, "components", "C2")["choice"] == "Managed key-value" and rules(m) == {"C03"}
    E(m, "components", "C2")["choice"] = 7
    assert rules(m) == {"S01"}


def test_s01_unknown_field():
    m = copy.deepcopy(VALID)
    m["bogus"] = 1
    assert rules(m) == {"S01"}


def test_item_and_test_descriptions_are_strings():
    m = copy.deepcopy(VALID)
    assert "S01" not in rules(m)
    E(m, "items", "I1")["description"] = 5
    E(m, "tests", "T1")["description"] = ["x"]
    got = {f["element"] for f in sysmodel.check_model(m) if f["rule"] == "S01"}
    assert got == {"items/0/description", "tests/0/description"}


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
    assert [f["message"] for f in sysmodel.check_model(m) if f["rule"] == "R30"] == ["nothing it points to runs in a part; match its job to a part"]
    m = copy.deepcopy(VALID)
    drop(m, "interfaces", "IF1")
    assert all("no connection carries it" in f["message"] for f in sysmodel.check_model(m) if f["rule"] == "R30")


def test_interface_at_parent_covers_children():
    # IF1/IF2 sit on C1, yet cover flows to C11 and C12; moving IF2 to C11 breaks the C12 flow.
    m = copy.deepcopy(VALID)
    E(m, "interfaces", "IF2")["between"] = ["C11", "C2"]
    msgs = [f["message"] for f in sysmodel.check_model(m) if f["rule"] == "R30"]
    assert len(msgs) == 1 and "from C2 to C12" in msgs[0]


def msgs(m, rule, step=6):
    return [(f["element"], f["message"]) for f in sysmodel.check_model(m, step) if f["rule"] == rule]


def test_r18_says_what_the_outside_system_lacks():
    m = copy.deepcopy(VALID)
    add_e2(m)
    assert msgs(m, "R18") == [("E2", "sends and receives nothing; an outside system must exchange items. "
                                      "If it only sets requirements, make it a source; "
                                      "if it is a design choice, move it to step 3")]
    m = copy.deepcopy(VALID)
    E(m, "external", "E1").update(sends=[], receives=["I2", "I4"], kind="context")
    assert [x[1][:20] for x in msgs(m, "R18")] == ["is background the sy", "sends nothing to the"]
    m = copy.deepcopy(VALID)
    E(m, "external", "E1")["receives"] = []
    assert msgs(m, "R18") == [("E1", "receives nothing from the system; if the system does not affect it, make its `kind` context")]
    add_e2(m, sends=["I1"])                       # an enabling system may send only
    assert [x[0] for x in msgs(m, "R18")] == ["E1"]


def test_r10_converse_names_the_function():
    m = copy.deepcopy(VALID)
    E(m, "external", "E1")["sends"] = ["I1"]
    assert msgs(m, "R10") == [("F12", "takes in I3, but no other job and no outside system provides it")]
    m = copy.deepcopy(VALID)
    E(m, "external", "E1")["receives"] = ["I2"]
    assert msgs(m, "R10") == [("F12", "gives out I4, but no other job and no outside system uses it")]


def test_r05_item_must_belong_to_a_specified_leaf():
    m = copy.deepcopy(VALID)
    spec("Q2", "I1", "I3", "F11")(m)
    assert msgs(m, "R05") == [("Q2", "`specifies` lists I3, but none of the jobs it lists takes or gives it")]
    spec("Q2", "I1", "I3", "F11", "F12")(m)           # I3 is F12's input
    assert msgs(m, "R05") == []


def test_r11_finds_derived_from_loops():
    m = copy.deepcopy(VALID)
    E(m, "requirements", "Q1")["derived_from"] = ["Q1"]
    assert msgs(m, "R11") == [("Q1", "`derived_from` links go in a circle; break the loop")]
    m = copy.deepcopy(VALID)
    E(m, "requirements", "Q1")["derived_from"] = ["Q2"]
    E(m, "requirements", "Q2")["derived_from"] = ["Q1"]
    assert {x[0] for x in msgs(m, "R11")} == {"Q1", "Q2"}
    m = copy.deepcopy(VALID)
    m["requirements"].append({**DERIVED, "specifies": ["C2"]})     # a plain chain is fine
    assert msgs(m, "R11") == []


def test_r23_wants_a_threshold_on_quality_cost_and_schedule():
    for sub in ("quality", "cost", "schedule"):
        m = copy.deepcopy(VALID)
        E(m, "requirements", "Q4").update(subcategory=sub)
        unset("requirements", "Q4", "threshold")(m)
        assert msgs(m, "R23") == [("Q4", f"a {sub} requirement needs a `threshold` (a number with units)")]
    m = copy.deepcopy(VALID)
    E(m, "requirements", "Q4").update(category="trade-off", subcategory="cost")
    unset("requirements", "Q4", "threshold")(m)
    assert msgs(m, "R23") == []


def test_c01_names_the_item():
    m = copy.deepcopy(VALID)
    spec("Q5", "F1")(m)
    assert msgs(m, "C01") == [("I3", "E1 sends or receives it, but no requirement of category io lists it in `specifies`"),
                              ("I4", "E1 sends or receives it, but no requirement of category io lists it in `specifies`")]
    assert msgs(VALID, "C01") == []


def test_c02_c04_c05_c03_messages():
    m = copy.deepcopy(VALID)
    m["objectives"] += [{"id": "O2", "name": "Fast", "parent": "O1"}]
    assert msgs(m, "C02") == [("O2", "no requirement points to this objective in `objective`")]
    m = copy.deepcopy(VALID)
    E(m, "objectives", "O1")["weight"] = 0.9
    assert msgs(m, "C04") == [("O1", "objective weights at the top add up to 0.9, they should add up to 1")]
    E(m, "objectives", "O1")["weight"] = 0.995                     # within the tolerance
    assert msgs(m, "C04") == []
    m["objectives"] += [{"id": "O2", "name": "Fast", "parent": "O1", "weight": 0.5},
                        {"id": "O3", "name": "Cheap", "parent": "O1", "weight": 0.2},
                        {"id": "O4", "name": "Simple", "parent": "O1"}]
    assert msgs(m, "C04") == []                                    # one sibling has no weight: skipped
    E(m, "objectives", "O4")["weight"] = 0.3
    assert msgs(m, "C04") == []
    E(m, "objectives", "O4")["weight"] = 0.4
    assert msgs(m, "C04") == [("O1", "objective weights under O1 add up to 1.1, they should add up to 1")]
    m = copy.deepcopy(VALID)
    m["scenarios"] = [{"id": "SC1", "name": "Visit", "steps": ["Web visitor sends Short code"]}]
    assert msgs(m, "C05") == [("SC1", "no test lists this scenario in `scenarios`")]
    E(m, "tests", "T1")["scenarios"] = ["SC1"]
    assert msgs(m, "C05") == [] and "S03" not in rules(m)
    E(m, "tests", "T1")["scenarios"] = ["Q1"]
    assert "S03" in rules(m)
    for sub in ("observance", "verification-plan", "validation-plan", "acceptance-plan"):
        m["requirements"].append({"id": f"QQ-{sub}", "text": "The system shall be proven.", "category": "qualification",
                                  "subcategory": sub, "stage": "release", "source": "SRC1"})
    assert msgs(m, "C03") == []
    assert [f["severity"] for f in sysmodel.check_model(VALID) if f["rule"] == "C03"] == ["advice"] * 4


def test_c06_converse_of_r30b():
    m = copy.deepcopy(VALID)
    E(m, "interfaces", "IF2")["carries"] = ["I5", "I6", "I1"]
    assert msgs(m, "C06") == [("IF2", "carries I1, but nothing goes between C1 and C2; remove it from `carries`")]
    m = copy.deepcopy(VALID)
    E(m, "interfaces", "IF1")["between"] = ["E1", "S"]           # an end that covers the parts still sees the flows
    assert msgs(m, "C06") == []


def test_schema_wants_a_purpose_and_a_carried_item():
    m = copy.deepcopy(VALID)
    del m["system"]["purpose"]
    E(m, "interfaces", "IF1")["carries"] = []
    got = {(f["element"], f["message"]) for f in sysmodel.check_model(m)}
    assert got == {("system", "'purpose' is a required property"), ("interfaces/0/carries", "[] should have at least 1 items")}


def test_requirement_may_specify_an_interface():
    m = copy.deepcopy(VALID)
    m["requirements"].append({"id": "Q6", "text": "The public HTTP interface shall answer within 200 ms.",
                              "category": "io", "subcategory": "external-interface", "stage": "release",
                              "source": "SRC1", "specifies": ["I2", "F11", "IF1"]})
    m["tests"].append({"id": "T7", "name": "Latency probe", "method": "manual", "verifies": ["Q6"]})
    assert settled(sysmodel.check_model(m)) == []                  # S03 accepts it, R30(a) reaches C1 through its end
    spec("Q6", "IF1")(m)
    assert {f["rule"] for f in sysmodel.check_model(m)} == {"C03", "R05"}   # no item or leaf function: R05, but no crash
    E(m, "interfaces", "IF1")["between"] = ["E1", "E1"]            # no component at an end: reaches nothing
    assert "R30" in rules(m)
    c = sysmodel.index(m)
    assert sysmodel.reach(c, E(m, "requirements", "Q6")) == set()
    E(m, "interfaces", "IF1")["between"] = ["E1", "C1"]
    assert sysmodel.reach(sysmodel.index(m), E(m, "requirements", "Q6")) == {"C11", "C12"}


def test_interface_links_belong_to_step_5_alone():
    m = copy.deepcopy(VALID)
    before = {n: sysmodel.fingerprint(m, n) for n in range(1, 7)}
    E(m, "requirements", "Q1")["specifies"] = ["F1", "I2", "IF1"]
    after = {n: sysmodel.fingerprint(m, n) for n in range(1, 7)}
    assert [n for n in before if before[n] != after[n]] == [5]


def test_tbd_is_whole_word():
    m = copy.deepcopy(VALID)
    E(m, "requirements", "Q1")["text"] = "The system shall handle outbound TBDX links."
    assert "R24" not in rules(m)


def test_custom_stages():
    m = copy.deepcopy(VALID)
    m["stages"] = ["build"]
    assert [f["element"] for f in sysmodel.check_model(m) if f["rule"] == "R03"] == ["Q1", "Q2", "Q3", "Q4", "Q5"]


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
    assert "0 errors, 0 warnings, 4 advice" in r.stdout


def test_cli_error_line_and_order(tmp_path):
    m = copy.deepcopy(VALID)
    unset("functions", "F11", "runs_in")(m)
    unset("functions", "F11", "done_when")(m)
    r = run_cli(tmp_path, m)
    assert r.returncode == 1
    lines = r.stdout.splitlines()
    assert 'R14 error  F11 "Create short link": has no part to run in; set `runs_in` (book p.243)' in lines
    assert lines.index(next(x for x in lines if x.startswith("R14"))) < lines.index(
        next(x for x in lines if x.startswith("R20")))


def test_cli_json(tmp_path):
    m = copy.deepcopy(VALID)
    unset("functions", "F11", "done_when")(m)
    r = run_cli(tmp_path, m, "--json")
    out = json.loads(r.stdout)
    assert r.returncode == 0
    assert out["findings"] == [{"rule": "R20", "severity": "warning", "element": "F11",
                                "message": "has no `done_when`; say how to tell the job is finished", "page": 58}] + [
        {"rule": "C03", "severity": "advice", "element": "S", "message": f"there is no {sub} requirement", "page": 142}
        for sub in ("observance", "verification-plan", "validation-plan", "acceptance-plan")]
    assert [j["rule"] for j in out["judgment"]] == ["R12", "R13", "R19", "R27", "R28", "R31", "R32"]
    assert out["counts"] == {"error": 0, "warning": 1, "advice": 4}


def test_r30a_skips_trade_off_and_qualification():
    # Trade-off preferences apply to the whole design; only io and system-wide must reach a component.
    m = copy.deepcopy(VALID)
    E(m, "requirements", "Q4").update(category="trade-off", specifies=[])
    assert "R30" not in rules(m)


def test_system_as_interface_endpoint_covers_components():
    # Before components are designed, the book draws external interfaces on the system itself.
    m = copy.deepcopy(VALID)
    E(m, "interfaces", "IF1")["between"] = ["E1", "S"]
    assert settled(sysmodel.check_model(m)) == []


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
    assert settled(sysmodel.check_model(step1_model(), step=1)) == []


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
    assert {j["rule"] for j in d["judgment"]} == {"R12", "R13", "R19", "R27", "R28", "R31", "R32"}
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
