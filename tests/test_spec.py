import copy
import re
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import sysmodel  # noqa: E402
from test_check import E, VALID  # noqa: E402

PURPOSE = "Turn long URLs into short links and redirect visitors"


def approved(tmp_path, m=VALID):
    """Write m to app.yaml with all six steps approved as they are now; returns the path."""
    src = tmp_path / "app.yaml"
    src.write_text(yaml.safe_dump(m))
    ok = lambda n: {"decision": "approved", "by": "ana", "at": f"2026-10-10T09:0{n}", "fingerprint": sysmodel.fingerprint(m, n)}
    sysmodel.review_path(src).write_text(yaml.safe_dump({n: ok(n) for n in range(1, 7)}))
    return str(src)


def build(model, part, capsys):
    assert sysmodel.main(["spec", model, part]) == 0
    return capsys.readouterr().out


def under(out, heading):
    """The text below one heading, up to the next heading of the same or a higher level."""
    return re.split(rf"\n#{{1,{heading.index(' ')}}} ", out.split(heading + "\n", 1)[1])[0]


def test_spec_waits_for_every_step_to_be_approved(tmp_path, capsys):
    src = tmp_path / "app.yaml"
    src.write_text(yaml.safe_dump(VALID))
    assert sysmodel.main(["spec", str(src), "C11"]) == 1
    cap = capsys.readouterr()
    assert cap.out == ""
    assert cap.err.startswith("No spec yet: the design isn't fully approved.\n  step 1 Problem: ready for review\n")
    assert "  step 6 Test plan: ready for review" in cap.err
    m = copy.deepcopy(VALID)                                      # approved, then step 6 changed
    model = approved(tmp_path, m)
    E(m, "tests", "T1").update(name="Create a link")
    Path(model).write_text(yaml.safe_dump(m))
    assert sysmodel.main(["spec", model, "C11"]) == 1
    cap = capsys.readouterr()
    assert cap.out == "" and "  step 6 Test plan: changed since approved by ana, 2026-10-10 09:06: review again" in cap.err
    assert "step 5" not in cap.err


def test_spec_names_the_parts_when_asked_for_something_else(tmp_path):
    model = approved(tmp_path)
    for bad in ("S", "F1", "X9"):
        with pytest.raises(SystemExit) as e:
            sysmodel.main(["spec", model, bad])
        assert e.value.code == (f"unknown part {bad}; parts: C1 Web service, C11 Shorten endpoint, "
                                "C12 Redirect endpoint, C2 Database")


def test_spec_for_a_leaf_part(tmp_path, capsys):
    model = approved(tmp_path)
    out = build(model, "C11", capsys)
    assert out.startswith(f"# Spec: C11 Shorten endpoint\n\nPart of C1 Web service, in S URL shortener: {PURPOSE}.\n\nGenerated from")
    assert f"Generated from {model} after all six steps were approved (latest: step 6 by ana, 2026-10-10 09:06). Build what it says." in out
    assert "Made of" not in out and "Runs in" not in out
    jobs = under(out, "## Jobs")
    assert "### F11 Create short link (part of F1 Handle requests)" in jobs and "F12" not in jobs
    assert "- Takes: I1 Long URL from E1 Web visitor\n" in jobs
    assert "- Gives: I2 Short link to E1 Web visitor; I5 Link record to C2 Database\n" in jobs
    assert "- Done when: Short link returned" in jobs
    conn = under(out, "## Connections")
    assert "| IF1 Public HTTP | E1 Web visitor | I1 Long URL | I2 Short link |" in conn
    assert "| IF2 Storage access | C2 Database |  | I5 Link record |" in conn
    assert "I6" not in conn and "C12" not in conn
    io, whole = under(out, "### Inputs and outputs"), under(out, "### Whole app")
    assert "- **Q2** (input) The system shall accept a long URL of up to 2000 characters.\n" in io
    assert "Tested by: T1 · Shared with: C12 Redirect endpoint" in io and "Shared with" not in whole
    assert "These apply to the whole app; this part must not break them." in whole
    assert "**Q3**" in whole and "**Q4**" in whole and "Q3" not in io and "Q4" not in io
    assert "Objective: O1 Low running cost" in whole and "Threshold: 99.9% monthly availability" in whole
    tests, wholetests = under(out, "## Tests").split("### Whole app\n")
    assert "| T1 Create link end to end | automated | Q1 |" in tests and "| T2 Long URL accepted | automated | Q2 |" in tests
    assert "T3" not in tests and "T4" not in tests
    assert wholetests == ("\n| Test | Method | Proves |\n|---|---|---|\n| T3 Availability probe | manual | Q3 |\n"
                          "| T4 Monthly bill review | manual | Q4 |\n")
    assert "| Q2 |\n| T6 Redirect end to end | automated | Q5 |\n\n- **T2** Submit a 2000-character URL" in tests and "- **T2**" not in wholetests


def test_spec_lists_the_items_the_part_takes_or_gives(tmp_path, capsys):
    out = build(approved(tmp_path), "C11", capsys)
    assert ("## Items\n\n- **I1 Long URL**: The URL to shorten: an absolute http or https URL, 1 to 2000 characters. "
            "Example: https://example.com/spring-sale?utm=mail\n- **I2 Short link**\n- **I5 Link record**: What is stored per link") in out
    assert out.index("## Connections") < out.index("## Items") < out.index("## Requirements")
    assert out.count("- **I1 Long URL**") == 1 and "I6" not in under(out, "## Items")
    m = copy.deepcopy(VALID)
    for i in m["items"]:
        i.pop("description", None)
    out = build(approved(tmp_path, m), "C11", capsys)
    assert "## Items" not in out and "- **I1" not in out
    assert "- **T2**" in out                                      # a test description still prints
    for t in m["tests"]:
        t.pop("description", None)
    assert "- **T2**" not in build(approved(tmp_path, m), "C11", capsys)


def test_a_whole_app_test_is_listed_once(tmp_path, capsys):
    m = copy.deepcopy(VALID)
    E(m, "tests", "T3")["verifies"] = ["Q3", "Q2"]
    out = build(approved(tmp_path, m), "C11", capsys)
    assert out.count("| T3 ") == 1 and "| T3 Availability probe | manual | Q2 |" in out


def test_spec_for_a_part_made_of_parts(tmp_path, capsys):
    out = build(approved(tmp_path), "C1", capsys)
    assert f"Part of S URL shortener: {PURPOSE}.\n\nBuilt with: Serverless functions\n\nMade of: C11 Shorten endpoint, C12 Redirect endpoint\n\nGenerated" in out
    jobs = under(out, "## Jobs")
    assert "- Runs in: C11 Shorten endpoint" in jobs and "- Runs in: C12 Redirect endpoint" in jobs
    assert "- Takes: I3 Short code from E1 Web visitor; I6 Stored target from C2 Database" in jobs
    conn = under(out, "## Connections")
    assert "| IF1 Public HTTP | E1 Web visitor | I1 Long URL, I3 Short code | I2 Short link, I4 Redirect |" in conn
    assert "| IF2 Storage access | C2 Database | I6 Stored target | I5 Link record |" in conn
    assert conn.count("\n| ") == 3                                # header and the two interfaces; nothing between C11 and C12
    assert "Shared with" not in out                               # Q1 stays inside C1


def test_spec_says_what_the_part_is_built_with(tmp_path, capsys):
    out = build(approved(tmp_path), "C2", capsys)
    assert f"Part of S URL shortener: {PURPOSE}.\n\nBuilt with: Managed key-value\n\nGenerated" in out
    assert "Built with" not in build(approved(tmp_path), "C11", capsys)   # C1's choice is not its child's


def test_spec_gives_a_derived_requirement_to_the_part_it_names(tmp_path, capsys):
    m = copy.deepcopy(VALID)
    m["requirements"].append({"id": "Q9", "text": "The database shall be available 99.97% of each month.",
                              "category": "system-wide", "subcategory": "quality", "stage": "release",
                              "derived_from": ["Q3"], "specifies": ["C2"], "threshold": "99.97% monthly availability"})
    m["tests"].append({"id": "T5", "name": "Database probe", "method": "manual", "verifies": ["Q9"]})
    assert not [f for f in sysmodel.check_model(m) if f["severity"] == "error"]
    model = approved(tmp_path, m)
    out = build(model, "C2", capsys)
    assert ("- **Q9** (quality) The database shall be available 99.97% of each month.\n"
            "  Threshold: 99.97% monthly availability · Stage: release · From: Q3 · Tested by: T5\n") in under(out, "### System-wide")
    assert "| T5 Database probe | manual | Q9 |" in under(out, "## Tests")
    assert "- Takes: I5 Link record from C11 Shorten endpoint" in out
    assert "Q9" not in build(model, "C11", capsys)


def test_status_points_at_spec_once_everything_is_approved(tmp_path, capsys):
    assert sysmodel.main(["status", approved(tmp_path)]) == 0
    assert "All six steps are approved. Build each part from `spec <component>`." in capsys.readouterr().out


def test_spec_shows_the_scenarios_that_name_the_parts_items(tmp_path, capsys):
    m = copy.deepcopy(VALID)
    m["scenarios"] = [{"id": "SC1", "name": "Visitor follows a short link",
                       "steps": ["Web visitor sends Short code", "System sends Redirect to Web visitor"]},
                      {"id": "SC2", "name": "Marketer shortens a link",
                       "steps": ["Marketer sends long url", "System sends Short link to Marketer"]}]
    model = approved(tmp_path, m)
    out = build(model, "C12", capsys)
    assert ("## Scenarios\n\nThe step 1 scenarios that mention something this part takes or gives.\n\n"
            "### SC1 Visitor follows a short link\n1. Web visitor sends Short code\n2. System sends Redirect to Web visitor\n\n"
            "## Jobs") in out
    assert "SC2" not in out
    out = build(model, "C11", capsys)                              # matched whatever the case: "long url"
    assert "### SC2 Marketer shortens a link" in out and "SC1" not in out
    assert "## Scenarios" not in build(model, "C2", capsys)       # the database's items are internal


def test_spec_for_a_subsystem_is_a_stub_spec(tmp_path, capsys):
    app = yaml.safe_load((HERE / "fixtures" / "levels" / "app.yaml").read_text())
    plain = copy.deepcopy(app)
    E(plain, "components", "C1").pop("subsystem")
    out = build(approved(tmp_path, app), "C1", capsys)
    assert "This part is a subsystem, designed at its own level: `C1/app.yaml`." in out
    stub = under(out, "## Stub")
    assert stub.startswith("\nBuild a stub, not the real part") and "honours the connections and items" in stub
    assert "The jobs say the behaviour to fake" in stub and "Run them after the swap" in stub
    assert out.index("## Stub") < out.index("## Jobs") and "### F11 Create short link" in out and "## Connections" in out
    assert "These apply to the whole app, for reference." in out and "must not break" not in out
    (tmp_path / "other").mkdir()
    plain_out = build(approved(tmp_path / "other", plain), "C1", capsys)
    assert "## Stub" not in plain_out and "designed at its own level" not in plain_out and "must not break them" in plain_out
    assert build(approved(tmp_path, app), "C2", capsys).replace(str(tmp_path), "") == \
        build(approved(tmp_path / "other", plain), "C2", capsys).replace(str(tmp_path / "other"), "")
