#!/usr/bin/env python3
"""sysmodel: check a system model YAML against schema.json and book rules, render it as a review page,
or serve that page so people can approve each step."""
import argparse
import errno
import getpass
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import threading
import time
import webbrowser
from collections import defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().with_name("vendor")))  # bundled PyYAML: nothing to install
import yaml  # noqa: E402

KINDS = {"stakeholders": "stakeholder", "sources": "source", "objectives": "objective",
         "scenarios": "scenario", "external": "external", "items": "item",
         "requirements": "requirement", "functions": "function", "components": "component",
         "interfaces": "interface", "tests": "test"}
SUBCATS = {"io": ("input", "output", "external-interface", "functional"),
           "system-wide": ("technology", "quality", "cost", "schedule"),
           "trade-off": ("performance", "cost", "cost-performance"),
           "qualification": ("observance", "verification-plan", "validation-plan", "acceptance-plan")}
REFS = [  # (kind, field, allowed target kinds)
    ("requirement", "parent", ("requirement",)), ("requirement", "source", ("source",)),
    ("requirement", "derived_from", ("requirement",)),
    ("requirement", "specifies", ("function", "item", "component", "interface", "system")),
    ("requirement", "objective", ("objective",)), ("objective", "parent", ("objective",)),
    ("source", "stakeholder", ("stakeholder",)), ("function", "parent", ("function",)),
    ("function", "inputs", ("item",)), ("function", "outputs", ("item",)),
    ("function", "runs_in", ("component",)), ("component", "parent", ("component", "system")),
    ("external", "sends", ("item",)), ("external", "receives", ("item",)),
    ("interface", "between", ("component", "system", "external")), ("interface", "carries", ("item",)),
    ("test", "verifies", ("requirement",)), ("test", "scenarios", ("scenario",))]
JUDGMENT = [  # (id, step it starts at, book page, text)
    ("R12", 2, 102, "Each job's sub-jobs together do exactly that job: nothing missing, nothing done twice."),
    ("R13", 3, 102, "Each part's sub-parts together make up exactly that part: nothing missing, nothing counted twice."),
    ("R19", 1, 48, "The outside systems, and what they send and get, match the stories (scenarios)."),
    ("R27", 1, 58, "Each requirement says one testable thing, with a number and units when it measures something."),
    ("R28", 1, 141, "The weights for comparing designs follow your priorities."),
    ("R31", 1, 138, "Neither the purpose nor any requirement names a product, technology or host, "
                    "unless you set it as a rule."),
    ("R32", 1, 134, "All the requirements can be met together within the budget and date (see the AI's notes).")]
SEVERITIES = ("error", "warning", "advice")

# ---- model index and helpers -------------------------------------------------

def table(m, key):
    d = {}
    for el in m.get(key) or []:
        d.setdefault(el["id"], el)
    return d

def index(m):
    c = SimpleNamespace(m=m, sid=m["system"]["id"])
    c.all = [("system", m["system"])] + [(k, el) for key, k in KINDS.items() for el in m.get(key) or []]
    c.by = {}
    for k, el in c.all:
        c.by.setdefault(el["id"], (k, el))
    c.funcs, c.comps, c.objs = table(m, "functions"), table(m, "components"), table(m, "objectives")
    c.reqlist = m["requirements"]
    m.setdefault("functions", [])
    m.setdefault("components", [])
    c.reqs = table(m, "requirements")
    c.fkids, c.ckids = defaultdict(list), defaultdict(list)
    for f in m["functions"]:
        c.fkids[f.get("parent")].append(f["id"])
    for x in m["components"]:
        c.ckids[x.get("parent")].append(x["id"])
    c.fleaf = {i for i in c.funcs if i not in c.fkids}
    c.cleaf = {i for i in c.comps if i not in c.ckids}
    c.roots = [i for i, f in c.funcs.items() if not f.get("parent")]
    c.first = [k for r in c.roots for k in c.fkids.get(r, [])]
    c.groups = {r["parent"] for r in c.reqlist if r.get("parent")}
    c.leafreqs = [r for r in c.reqlist if r["id"] not in c.groups]
    c.fins = {i for f in c.fleaf for i in c.funcs[f].get("inputs") or []}
    c.fouts = {i for f in c.fleaf for i in c.funcs[f].get("outputs") or []}
    c.tested = {v for t in m.get("tests") or [] for v in t["verifies"]}
    return c

def kind(c, i):
    return c.by.get(i, (None,))[0]

def spec(r):
    return r.get("specifies") or []

def ancestors(nodes, i):
    """Parent chain of i (cycle-safe; a cycle through i ends with i itself)."""
    out, p = [], nodes.get(i, {}).get("parent")
    while p in nodes and p not in out:
        out.append(p)
        p = nodes[p].get("parent")
    return out

def leaves_under(c, f):
    out, stack, seen = [], [f], set()
    while stack:
        x = stack.pop()
        if x not in seen:
            seen.add(x)
            if x in c.fleaf:
                out.append(x)
            stack += c.fkids.get(x, [])
    return out

def where(c, f):
    """Component function f runs in, or None."""
    ru = c.funcs[f].get("runs_in")
    return ru if ru in c.comps else None

def top(c, comp):
    """First-level component that contains comp (or is comp)."""
    for x in [comp] + ancestors(c.comps, comp):
        if c.comps[x].get("parent") == c.sid:
            return x

def tops(c, f):
    return {top(c, where(c, g)) for g in leaves_under(c, f) if where(c, g)} - {None}

def covers(c, x, node):
    return x == node or (node in c.comps and (x == c.sid or x in ancestors(c.comps, node)))

# ---- structural rules --------------------------------------------------------

def s02(c):
    counts = defaultdict(int)
    for _, el in c.all:
        counts[el["id"]] += 1
    for i, n in counts.items():
        if n > 1:
            yield i, f"id used {n} times"

def s03(c):
    for k, field, targets in REFS:
        for k2, el in c.all:
            if k2 != k:
                continue
            vals = el.get(field) or []
            for v in [vals] if isinstance(vals, str) else vals:
                got = kind(c, v)
                if got not in targets:
                    why = "missing id" if got is None else f"is a {got}"
                    yield el["id"], f"`{field}` points to {v}, which is {'not in the model' if got is None else 'a '+got}; it should be {' or '.join(targets)}"

# ---- book rules --------------------------------------------------------------

def r01(c):
    for r in c.leafreqs:
        if not r.get("category"):
            yield r["id"], "has no `category`; pick one"

def r02(c):
    for r in c.leafreqs:
        cat = r.get("category")
        if cat and r.get("subcategory") not in SUBCATS[cat]:
            yield r["id"], f"`subcategory` {r.get('subcategory')!r} does not fit category {cat}; pick one that does"

def r03(c):
    allowed = c.m.get("stages", ["build", "release"])
    for r in c.leafreqs:
        if r.get("stage") not in allowed:
            yield r["id"], f"`stage` {r.get('stage')!r} is missing or not one of {allowed}"

def r04(c):
    for r in c.reqlist:
        if r["id"] in c.groups and (r["id"] in c.tested or spec(r)):
            yield r["id"], "is a heading for smaller requirements, so no test should check it and it should not list `specifies`"

def r05(c):
    for r in c.leafreqs:
        if r.get("category") == "io" and r.get("subcategory") in ("input", "output", "external-interface"):
            s = spec(r)
            items, leaves = [x for x in s if kind(c, x) == "item"], [x for x in s if x in c.fleaf]
            if not items or not leaves:
                yield r["id"], "`specifies` must list at least one item and at least one job with no smaller jobs"
                continue
            moved = {i for f in leaves for k in ("inputs", "outputs") for i in c.funcs[f].get(k) or []}
            for i in items:
                if i not in moved:
                    yield r["id"], f"`specifies` lists {i}, but none of the jobs it lists takes or gives it"

def r06(c):
    for r in c.leafreqs:
        if r.get("category") != "system-wide":
            continue
        if r.get("derived_from"):  # derived for the parts it applies to (p. 249)
            if not spec(r) or any(kind(c, x) not in ("system", "component") for x in spec(r)):
                yield r["id"], "`specifies` must list the system or the parts it applies to"
        elif set(spec(r)) != {c.sid}:
            yield r["id"], f"`specifies` must list only the system ({c.sid})"

def r07(c):
    ok = set(c.roots) | set(c.first)
    for r in c.leafreqs:
        if r.get("category") == "io" and r.get("subcategory") == "functional" and not ok & set(spec(r)):
            yield r["id"], "`specifies` must list the top job or one of the jobs just below it"

def r08(c):
    for r in c.roots:
        n = len(c.fkids.get(r, []))
        if not 2 <= n <= 7:
            yield r, f"the top job is split into {n} jobs, it should be 2 to 7"

def r09(c):
    if len(c.roots) != 1:
        yield c.sid, f"there should be exactly one top job (one with no `parent`), found {len(c.roots)}"

def r10(c):
    for e in c.m.get("external") or []:
        for i in e.get("sends") or []:
            if i not in c.fins:
                yield e["id"], f"sends {i}, but no job with no smaller jobs takes it in"
        for i in e.get("receives") or []:
            if i not in c.fouts:
                yield e["id"], f"receives {i}, but no job with no smaller jobs gives it out"
    sent = {i for e in c.m.get("external") or [] for i in e.get("sends") or []}
    received = {i for e in c.m.get("external") or [] for i in e.get("receives") or []}
    for f in sorted(c.fleaf):
        for i in c.funcs[f].get("inputs") or []:
            if i not in c.fouts and i not in sent:
                yield f, f"takes in {i}, but no other job and no outside system provides it"
        for i in c.funcs[f].get("outputs") or []:
            if i not in c.fins and i not in received:
                yield f, f"gives out {i}, but no other job and no outside system uses it"

def r11(c):
    for nodes in (c.funcs, c.comps, c.reqs, c.objs):
        for i in nodes:
            if i in ancestors(nodes, i):
                yield i, "`parent` links go in a circle; break the loop"
    for i in c.reqs:
        seen, stack = set(), list(c.reqs[i].get("derived_from") or [])
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack += c.reqs.get(x, {}).get("derived_from") or []
        if i in seen:
            yield i, "`derived_from` links go in a circle; break the loop"

def r14(c):
    for i, f in c.funcs.items():
        ru = f.get("runs_in")
        if i not in c.fleaf:
            if ru:
                yield i, "is split into smaller jobs, so remove its `runs_in`; set it on the smallest jobs"
        elif not ru:
            yield i, "has no part to run in; set `runs_in`"
        elif ru not in c.cleaf:
            yield i, f"`runs_in` {ru} is a part made of smaller parts; use one of its smallest parts"

def r15(c):
    for f in c.first:
        if len(tops(c, f)) > 1:
            yield f, f"its smallest jobs run in several big parts ({', '.join(sorted(tops(c, f)))}); keep them in one"

def r16(c):
    used = {f.get("runs_in") for f in c.funcs.values()}
    for i in sorted(c.cleaf - used):
        yield i, "no job runs in this part; give it a job or remove it"

def r17(c):
    land = {f: tops(c, f) for f in c.first}
    owners = defaultdict(list)
    for f, ts in land.items():
        for t in ts:
            owners[t].append(f)
    for t, fs in owners.items():
        if len(fs) > 1:
            yield t, f"jobs {', '.join(fs)} all end up in this one part; give each its own part"
    for i, x in c.comps.items():
        if x.get("parent") == c.sid and i not in owners:
            yield i, "this big part gets none of the top-level jobs; give it one or remove it"

def r18(c):
    for e in c.m.get("external") or []:
        sends, receives = e.get("sends"), e.get("receives")
        if e["kind"] == "context" and receives:
            yield e["id"], "is background the system cannot affect, so it should not receive items; remove `receives` or make it `external`"
        if not sends and not receives:
            yield e["id"], ("sends and receives nothing; an outside system must exchange items. "
                            "If it only sets requirements, make it a source; if it is a design choice, move it to step 3")
        elif e["kind"] == "external" and not receives:
            yield e["id"], "receives nothing from the system; if the system does not affect it, make its `kind` context"
        elif e["kind"] == "context" and not sends:
            yield e["id"], "sends nothing to the system, so it has no effect; add `sends` or remove it"

def r20(c):
    for f in sorted(c.fleaf):
        if not c.funcs[f].get("done_when"):
            yield f, "has no `done_when`; say how to tell the job is finished"

def r21(c):
    for r in c.leafreqs:
        if not r.get("source") and not r.get("derived_from"):
            yield r["id"], "has no `source` or `derived_from`; say where it comes from"

def r23(c):
    for r in c.leafreqs:
        if r.get("category") == "system-wide" and r.get("subcategory") in ("quality", "cost", "schedule") \
                and not r.get("threshold"):
            yield r["id"], f"a {r['subcategory']} requirement needs a `threshold` (a number with units)"

def r24(c):
    for r in c.reqlist:
        for field in ("text", "threshold"):
            if re.search(r"\b(TBD|TBR)\b", r.get(field) or "", re.I):
                yield r["id"], f"`{field}` still says TBD or TBR; write the real value"

def r25(c):
    for r in c.leafreqs:
        if r.get("category") in ("io", "system-wide") and r["id"] not in c.tested:
            yield r["id"], "no test checks it; add one in step 6"

def r26(c):
    for r in c.leafreqs:
        if not re.search(r"\bshall\b", r["text"], re.I):
            yield r["id"], '`text` should say "shall"'

def r29(c):
    for i in c.m.get("interfaces") or []:
        a, b = i["between"]
        if a == b:
            yield i["id"], f"connects {a} to itself; the two ends in `between` must differ"
        elif kind(c, a) not in ("component", "system") and kind(c, b) not in ("component", "system"):
            yield i["id"], "neither end in `between` is the system or a part"

def reaches(c, x):
    k = kind(c, x)
    if k == "function":
        return any(where(c, g) for g in leaves_under(c, x))
    if k == "item":
        return x in c.fins | c.fouts
    if k == "interface":
        return any(reaches(c, e) for e in c.by[x][1]["between"])
    return k in ("system", "component")

def r30a(c):
    for r in c.leafreqs:
        if r.get("category") in ("io", "system-wide") and not any(reaches(c, x) for x in spec(r)):
            yield r["id"], "nothing it points to runs in a part; match its job to a part"

def flows(c):
    """(producer node, consumer node, item); a node is a component id or an external id."""
    ext = c.m.get("external") or []
    for f in c.fleaf:
        fi, fo = c.funcs[f].get("inputs") or [], c.funcs[f].get("outputs") or []
        for i in fo:
            for g in c.fleaf:
                if i in (c.funcs[g].get("inputs") or []):
                    yield where(c, f), where(c, g), i
            for e in ext:
                if i in (e.get("receives") or []):
                    yield where(c, f), e["id"], i
        for e in ext:
            for i in e.get("sends") or []:
                if i in fi:
                    yield e["id"], where(c, f), i

def carriers(c, p, q, item):
    """Interfaces carrying item between p and q, either way round."""
    out = []
    for i in c.m.get("interfaces") or []:
        a, b = i["between"]
        if item in i["carries"] and ((covers(c, a, p) and covers(c, b, q)) or (covers(c, a, q) and covers(c, b, p))):
            out.append(i)
    return out

def carried(c, p, q, item):
    return bool(carriers(c, p, q, item))

def r30b(c):
    seen = set()
    for p, q, item in flows(c):
        if p and q and p != q and (p, q, item) not in seen and not carried(c, p, q, item):
            seen.add((p, q, item))
            yield item, f"{item} goes from {p} to {q}, between parts, but no connection carries it; add it to an interface"

def c01(c):
    seen = set()
    said = {x for r in c.leafreqs if r.get("category") == "io" for x in spec(r)}
    for e in c.m.get("external") or []:
        for i in (e.get("sends") or []) + (e.get("receives") or []):
            if i not in said and i not in seen:
                seen.add(i)
                yield i, f"{e['id']} sends or receives it, but no requirement of category io lists it in `specifies`"

def c02(c):
    named_by = {r.get("objective") for r in c.reqlist}
    parents = {o.get("parent") for o in c.objs.values()}
    for i in c.objs:
        if i not in parents and i not in named_by:
            yield i, "no requirement points to this objective in `objective`"

def c03(c):
    have = {r.get("subcategory") for r in c.leafreqs if r.get("category") == "qualification"}
    for sub in SUBCATS["qualification"]:
        if sub not in have:
            yield c.sid, f"there is no {sub} requirement"

def c04(c):
    sibs = defaultdict(list)
    for o in c.objs.values():
        sibs[o.get("parent")].append(o)
    for parent, os in sibs.items():
        if all(o.get("weight") is not None for o in os):
            total = sum(o["weight"] for o in os)
            if abs(total - 1) > 0.01 + 1e-9:
                where_ = f"under {parent}" if parent else "at the top"
                yield parent or os[0]["id"], f"objective weights {where_} add up to {round(total, 4):g}, they should add up to 1"

def c05(c):
    named_by = {s for t in c.m.get("tests") or [] for s in t.get("scenarios") or []}
    for s in c.m.get("scenarios") or []:
        if s["id"] not in named_by:
            yield s["id"], "no test lists this scenario in `scenarios`"

def c06(c):
    made = {(p, q, i) for p, q, i in flows(c) if p and q and p != q}
    for f in c.m.get("interfaces") or []:
        a, b = f["between"]
        for i in f["carries"]:
            if not any(item == i and ((covers(c, a, p) and covers(c, b, q)) or (covers(c, a, q) and covers(c, b, p)))
                       for p, q, item in made):
                yield f["id"], f"carries {i}, but nothing goes between {a} and {b}; remove it from `carries`"

STEPS = {1: "Problem", 2: "Functions", 3: "Parts", 4: "Match", 5: "Interfaces", 6: "Test plan"}

# id, step it starts at, severity, book page, short description, check function
RULES = [
    ("S01", 1, "error", None, "file matches schema.json", None),
    ("S02", 1, "error", None, "ids are unique", s02),
    ("S03", 1, "error", None, "references resolve to the right kind", s03),
    ("R01", 1, "error", 139, "every smallest requirement has a category", r01),
    ("R02", 1, "error", 140, "every smallest requirement has a subcategory that fits", r02),
    ("R03", 1, "error", 143, "every smallest requirement has an allowed stage", r03),
    ("R04", 1, "error", 50, "a heading requirement is not tested and lists nothing", r04),
    ("R05", 2, "error", 59, "an input/output/interface requirement lists an item and a smallest job", r05),
    ("R06", 1, "error", 59, "a system-wide requirement lists the system", r06),
    ("R07", 2, "error", 59, "a functional requirement lists the top job or a job just below it", r07),
    ("R08", 2, "warning", 141, "the top job is split into 2 to 7 jobs", r08),
    ("R09", 2, "error", 51, "exactly one top job", r09),
    ("R10", 2, "error", 51, "what outside systems send and receive matches what the smallest jobs take and give, both ways", r10),
    ("R11", 1, "error", 100, "no circular parent or derived_from links", r11),
    ("R14", 4, "error", 243, "only the smallest jobs run in parts, and only in the smallest parts", r14),
    ("R15", 4, "warning", 249, "a top-level job stays inside one big part", r15),
    ("R16", 4, "warning", 243, "every smallest part has a job", r16),
    ("R17", 4, "advice", 214, "top-level jobs and big parts pair up one-to-one", r17),
    ("R18", 1, "error", 43, "every outside system exchanges items; background receives nothing, an external one receives some", r18),
    ("R20", 2, "warning", 58, "every smallest job says when it is done", r20),
    ("R21", 1, "error", 145, "every smallest requirement traces to a source or a higher requirement", r21),
    ("R23", 1, "error", 138, "quality, cost and schedule requirements have a number", r23),
    ("R24", 1, "error", 145, "no TBD/TBR", r24),
    ("R25", 6, "error", 142, "io and system-wide requirements have a test", r25),
    ("R26", 1, "warning", 145, "requirement text says shall", r26),
    ("R29", 5, "error", 61, "an interface joins two different ends, one of them the system or a part", r29),
    ("R30", 4, "error", 57, "(a) io and system-wide requirements reach a part", r30a),
    ("R30", 5, "error", 57, "(b) anything passing between parts is carried by an interface", r30b),
    ("C01", 2, "warning", 59, "items an outside system exchanges are listed by an io requirement", c01),
    ("C02", 1, "warning", 143, "every smallest objective is named by a requirement", c02),
    ("C03", 1, "advice", 142, "every kind of qualification has a requirement", c03),
    ("C04", 1, "warning", 155, "objective weights at the same level add up to 1", c04),
    ("C05", 6, "warning", 56, "every scenario is named by a test", c05),
    ("C06", 5, "warning", 48, "every item an interface carries really passes between its ends", c06),
]

# ---- running and output ------------------------------------------------------

def label(c, i):
    k = c.by.get(i)
    if not k:
        return i
    name = k[1].get("name") or k[1].get("title") or k[1].get("text") or ""
    return f'{i} "{name[:50]}"' if name else i

JSON_TYPES = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
              "string": lambda x: isinstance(x, str),
              "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)}

def schema_errors(x, s, defs, path=()):
    """(path, message) for each way x breaks schema s. Only the JSON Schema keywords schema.json uses."""
    if "$ref" in s:  # the referenced schema, then this one's own keywords (minItems next to a $ref)
        yield from schema_errors(x, defs[s["$ref"].rsplit("/", 1)[1]], defs, path)
    if "type" in s and not JSON_TYPES[s["type"]](x):
        yield path, f"{x!r} is not of type {s['type']!r}"
        return
    if "enum" in s and x not in s["enum"]:
        yield path, f"{x!r} is not one of {s['enum']}"
    if "pattern" in s and not re.search(s["pattern"], x):
        yield path, f"{x!r} does not match {s['pattern']!r}"
    if "minimum" in s and x < s["minimum"]:
        yield path, f"{x!r} is less than the minimum of {s['minimum']}"
    if "maximum" in s and x > s["maximum"]:
        yield path, f"{x!r} is greater than the maximum of {s['maximum']}"
    if isinstance(x, list):
        if len(x) < s.get("minItems", 0):
            yield path, f"{x!r} should have at least {s['minItems']} items"
        if len(x) > s.get("maxItems", len(x)):
            yield path, f"{x!r} should have at most {s['maxItems']} items"
        for i, v in enumerate(x):
            yield from schema_errors(v, s.get("items", {}), defs, path + (i,))
    if isinstance(x, dict):
        props = s.get("properties", {})
        yield from ((path, f"{k!r} is a required property") for k in s.get("required", []) if k not in x)
        extra = [k for k in x if k not in props]
        if extra and s.get("additionalProperties") is False:
            yield path, f"Additional properties are not allowed ({', '.join(map(repr, extra))} unexpected)"
        for k, v in x.items():
            if k in props:
                yield from schema_errors(v, props[k], defs, path + (k,))

def check_model(m, step=6):
    """Findings for the rules of steps 1..step."""
    schema = json.loads(Path(__file__).with_name("schema.json").read_text())
    errs = sorted(schema_errors(m, schema, schema["$defs"]), key=lambda e: [str(p) for p in e[0]])
    if errs:
        return [dict(rule="S01", step=1, severity="error", page=None, message=msg, label=el, element=el)
                for path, msg in errs for el in ["/".join(map(str, path)) or "(file)"]]
    c = index(m)
    out = []
    for rule, st, sev, page, _, fn in RULES[1:]:
        if st > step:
            continue
        for element, message in fn(c):
            out.append(dict(rule=rule, step=st, severity=sev, page=page, element=element, message=message,
                            label=label(c, element)))
    out.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["rule"]))
    return out

OWNERS = [  # pieces of the model, and the steps whose approval covers each; SKILL.md shows this table to the AI.
    # A step's own additions (internal items, links to its own elements, derived requirements) don't undo earlier approvals.
    ("`stages`, `stakeholders`, `sources`, `objectives`, `scenarios`", (1,)),
    ("`system`", (1, 3)),
    ("`external`", (1, 5)),
    ("`items` an external system sends or receives", (1, 2, 5)),
    ("other `items`", (2, 5)),
    ("`requirements` without `derived_from` (all fields but `specifies`)", (1, 6)),
    ("`requirements` with `derived_from` (all fields)", (4, 6)),
    ("`specifies` links of requirements without `derived_from` to the system", (1,)),
    ("`specifies` links of requirements without `derived_from` to functions and items", (2,)),
    ("`specifies` links of requirements without `derived_from` to components", (4,)),
    ("`specifies` links of requirements without `derived_from` to interfaces", (5,)),
    ("`functions` (all fields but `runs_in`)", (2, 4)),
    ("`runs_in`", (4,)),
    ("`components`", (3, 4, 5)),
    ("`interfaces`", (5,)),
    ("`tests`", (6,))]

def pieces(m):
    """The model cut into the OWNERS pieces, in the same order."""
    g = lambda k: m.get(k) or []
    ids = lambda *ks: {x["id"] for k in ks for x in g(k)}
    edge = {i for e in g("external") for i in (e.get("sends") or []) + (e.get("receives") or [])}
    plain = [r for r in g("requirements") if not r.get("derived_from")]
    def links(targets):
        return [[r["id"], ts] for r in plain if (ts := [t for t in r.get("specifies") or [] if t in targets])]
    return [[m.get(k) for k in ("stages", "stakeholders", "sources", "objectives", "scenarios")],
            m.get("system"), g("external"),
            [i for i in g("items") if i["id"] in edge], [i for i in g("items") if i["id"] not in edge],
            [{k: v for k, v in r.items() if k != "specifies"} for r in plain],
            [r for r in g("requirements") if r.get("derived_from")],
            links({m["system"]["id"]}), links(ids("functions", "items")), links(ids("components")),
            links(ids("interfaces")),
            [{k: v for k, v in f.items() if k != "runs_in"} for f in g("functions")],
            [[f["id"], f["runs_in"]] for f in g("functions") if f.get("runs_in")],
            g("components"), g("interfaces"), g("tests")]

def digest(x, n=12):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:n]

def fingerprint(m, step):
    """Short hash of the pieces a step's approval covers (see OWNERS)."""
    return digest([p for p, (_, steps) in zip(pieces(m), OWNERS) if step in steps])

PAIRS = {7, 8, 9, 10, 12}   # OWNERS pieces that are [id, ...] pairs (links), keyed by their first id

def elements(m, step):
    """{id: short hash} of every element in the step's pieces; a link is keyed by the requirement or function that owns it."""
    acc = defaultdict(list)
    for i, (p, (_, steps)) in enumerate(zip(pieces(m), OWNERS)):
        if step in steps:
            flat = [e for x in p for e in x or []] if i == 0 else [p] if isinstance(p, dict) else p or []
            for e in flat:
                acc[e[0] if i in PAIRS else e["id"] if isinstance(e, dict) else "stages"].append(e)
    return {k: digest(v, 8) for k, v in acc.items()}

def state_path(model):
    """Per-model scratch file in the temp dir (not the user's repo): the running review app and the AI's hand-off."""
    return Path(tempfile.gettempdir()) / f"sysmodel-{hashlib.sha256(str(Path(model).resolve()).encode()).hexdigest()[:12]}.json"

def read_state(model):
    try:
        d = json.loads(state_path(model).read_text())
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}

def write_state(model, **changes):
    """Set keys of the state file (a None value removes the key)."""
    d = {**read_state(model), **changes}
    d = {k: v for k, v in d.items() if v is not None}
    try:
        state_path(model).write_text(json.dumps(d))
    except OSError:
        pass

def serve_alive(model):
    """The recorded `serve` entry if its process still runs, else None."""
    s = read_state(model).get("serve")
    try:
        os.kill(int(s["pid"]), 0)
        return s
    except (TypeError, KeyError, ValueError, OSError):
        return None

def review_path(model):
    return Path(model).with_suffix(".review.yaml")

def load_reviews(path):
    """Latest decision per step, from the review file next to the model."""
    d = yaml.safe_load(path.read_text()) if path.exists() else None
    return {int(k): v for k, v in (d or {}).items()}

def review_state(m, decisions, step):
    """Per step: the fingerprint now, the last decision, and whether that decision was about what the model says now."""
    out = {}
    for n in range(1, step + 1):
        fp, last = fingerprint(m, n), decisions.get(n)
        was, now = (last or {}).get("elements") or {}, elements(m, n) if last else {}
        out[n] = {"fingerprint": fp, "last": last, "current": bool(last) and last.get("fingerprint") == fp,
                  "changed": {"added": sorted(now.keys() - was.keys()) if was else [],
                              "changed": sorted(k for k in now.keys() & was.keys() if now[k] != was[k]),
                              "removed": sorted(was.keys() - now.keys())}}
    return out

def read_notes(model):
    f = Path(model).with_name("decisions.md")
    return f.read_text() if f.is_file() else None

def read_answers(model):
    f = Path(model).with_name("answers.md")
    return f.read_text() if f.is_file() else None

def render(m, step=6, decisions=None, live=None, notes=None, model=None):
    """Self-contained HTML review page for steps 1..step (pictures drawn in the browser).
    decisions: from load_reviews. notes: text of decisions.md. model: path of the model file (for the AI's hand-off record). live: {"version": ...} when `serve` hands the page out, so it can save decisions."""
    found = check_model(m, step)
    drawable = not any(f["rule"] == "S01" for f in found)
    data = {"model": m, "step": step, "steps": STEPS, "findings": found, "drawable": drawable,
            "judgment": [{"rule": r, "step": st, "text": t, "page": pg} for r, st, pg, t in JUDGMENT if st <= step],
            "review": review_state(m, decisions or {}, step) if drawable else {}, "live": live, "notes": notes, "answers": read_answers(model) if model else None,
            "progress": progress(m, decisions or {}, model) if drawable else []}
    blob = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    return Path(__file__).with_name("render.html").read_text().replace("/*DATA*/null", blob)

def wait_for_review(model, every=1.0):
    """Block until a person approves or sends back a step in `serve`; returns {step: decision} for what changed."""
    path = review_path(model)
    before = load_reviews(path)
    try:
        m = yaml.safe_load(Path(model).read_text())
        write_state(model, handoff={str(r["step"]): fingerprint(m, r["step"]) for r in progress(m, before) if r["turn"] == "person"})
    except (OSError, yaml.YAMLError, KeyError, TypeError, AttributeError):
        pass
    while True:
        time.sleep(every)
        changed = {n: d for n, d in load_reviews(path).items() if d != before.get(n)}
        if changed:
            return changed
        if not serve_alive(model):
            return None

STARTED = {  # does the model have anything for this step yet?
    1: lambda m: m.get("requirements"), 2: lambda m: m.get("functions"), 3: lambda m: m.get("components"),
    4: lambda m: any(f.get("runs_in") for f in m.get("functions") or []),
    5: lambda m: m.get("interfaces"), 6: lambda m: m.get("tests")}

def progress(m, decisions, model=None):
    """Whose turn each step is: done (approved, unchanged since, nothing to fix), ai (not started, must-fix problems, or sent back),
    or person (waiting for a review in `serve`). With a model path and a hand-off record (from `wait`), a step the AI changed since
    the hand-off is still the AI's."""
    handoff = read_state(model).get("handoff") if model else None
    found = check_model(m)
    if any(f["rule"] == "S01" for f in found):
        return [dict(step=n, name=STEPS[n], turn="ai", why="the file doesn't match schema.json (run check)",
                     errors=0, warnings=0) for n in STEPS]
    rows = []
    for n, r in review_state(m, decisions, 6).items():
        errors = sum(f["step"] == n and f["severity"] == "error" for f in found)
        warnings = sum(f["step"] == n and f["severity"] == "warning" for f in found)
        last = r["last"] or {}
        who = f"{last.get('by')}, {str(last.get('at', '')).replace('T', ' ')}"
        if not STARTED[n](m):
            turn, why = "ai", "not started"
        elif last.get("decision") == "approved" and r["current"] and not errors:
            turn, why = "done", f"approved by {who}"
        elif errors:
            turn, why = "ai", f"{errors} must fix"
        elif last.get("decision") == "sent back" and r["current"]:
            turn, why = "ai", f"sent back by {who}: {last.get('note')}"
        elif last.get("decision") == "approved":
            turn, why = "person", f"changed since approved by {who}: review again"
        elif last:
            turn, why = "person", f"changed since sent back by {who}: review again"
        else:
            turn, why = "person", "ready for review"
        if turn == "person" and isinstance(handoff, dict) and handoff.get(str(n)) != r["fingerprint"]:
            turn, why = "ai", "the AI is still working on it"
        rows.append(dict(step=n, name=STEPS[n], turn=turn, why=why, errors=errors, warnings=warnings))
    return rows

# ---- build spec for one part -------------------------------------------------

def named(c, i):
    """`id name` of any node (a source has a title instead)."""
    el = c.by.get(i, (None, {}))[1]
    return f"{i} {el.get('name') or el.get('title') or ''}".strip()

def in_order(c, ids):
    """Distinct ids in model order (None last)."""
    pos = {}
    for n, (_, el) in enumerate(c.all):
        pos.setdefault(el["id"], n)
    return sorted(set(ids), key=lambda i: pos.get(i, len(pos)))

def names(c, ids):
    return ", ".join(named(c, i) for i in in_order(c, ids))

def comps_under(c, x):
    return [x] + [d for k in c.ckids.get(x, []) for d in comps_under(c, k)]

def ends(c, item, sub, back):
    """Where item comes from (back) or goes to: externals and leaf functions; a function outside sub is named by its component."""
    side = ("sends", "outputs") if back else ("receives", "inputs")
    out = [e["id"] for e in c.m.get("external") or [] if item in (e.get(side[0]) or [])]
    for f in c.fleaf:
        if item in (c.funcs[f].get(side[1]) or []):
            w = where(c, f)
            out.append(w if w and w not in sub else f)
    return names(c, out) or "(nowhere)"

def job(c, f, sub, comp):
    fn = c.funcs[f]
    out = [f"### {named(c, f)}" + (f" (part of {named(c, fn['parent'])})" if fn.get("parent") else "")]
    for key, word, back in (("inputs", "Takes", True), ("outputs", "Gives", False)):
        items = "; ".join(f"{named(c, i)} {'from' if back else 'to'} {ends(c, i, sub, back)}" for i in fn.get(key) or [])
        out.append(f"- {word}: {items or 'nothing'}")
    if fn.get("done_when"):
        out.append(f"- Done when: {fn['done_when']}")
    if comp not in c.cleaf:
        out.append(f"- Runs in: {named(c, fn['runs_in'])}")
    return out

def connections(c, sub):
    """{(interface id or None, other end): (items coming in, items going out)} for flows with one end in sub."""
    cells = defaultdict(lambda: ([], []))
    for p, q, item in set(flows(c)):
        if p and q and (p in sub) != (q in sub):
            far, k = (q, 1) if p in sub else (p, 0)
            for i in [x["id"] for x in carriers(c, p, q, item)] or [None]:
                cells[i, far][k].append(item)
    return cells

def reach(c, r):
    """Leaf components requirement r reaches through what it specifies."""
    out = set()
    for x in spec(r):
        k = kind(c, x)
        if k in ("system", "component"):
            out |= {l for l in c.cleaf if covers(c, x, l)}
        elif k == "interface":
            out |= {l for e in c.by[x][1]["between"] if kind(c, e) in ("system", "component")
                    for l in c.cleaf if covers(c, e, l)}
        elif k == "function":
            out |= {where(c, g) for g in leaves_under(c, x)} - {None}
    return out

def req_lines(c, r, shared=()):  # every spec is of an approved model, so "to confirm" has been confirmed
    cat = f" ({r['subcategory']})" if r.get("subcategory") else ""
    tests = [t["id"] for t in c.m.get("tests") or [] if r["id"] in t["verifies"]]
    fields = [("Threshold", r.get("threshold")), ("Stage", r.get("stage")), ("From", ", ".join(r.get("derived_from") or [])),
              ("Source", r.get("source") and named(c, r["source"]).replace("to confirm in review", "approved in review")), ("Objective", r.get("objective") and named(c, r["objective"])),
              ("Tested by", ", ".join(tests)), ("Shared with", names(c, shared))]
    got = [f"{k}: {v}" for k, v in fields if v]
    return [f"- **{r['id']}**{cat} {r['text']}"] + (["  " + " · ".join(got)] if got else [])

def part_spec(m, comp, decisions, source):
    """Markdown build spec for component comp of an approved model."""
    c = index(m)
    sub = set(comps_under(c, comp))
    subleaf, parent, system = c.cleaf & sub, c.comps[comp].get("parent"), named(c, c.sid)
    purpose = (m["system"].get("purpose") or "").rstrip(".")
    n = max(range(1, 7), key=lambda s: (str(decisions[s].get("at")), s))   # same minute: the later step
    out = [f"# Spec: {named(c, comp)}", "",
           (f"Part of {system}" if parent == c.sid else f"Part of {named(c, parent)}, in {system}") + (f": {purpose}." if purpose else ".")]
    if c.comps[comp].get("choice"):
        out += ["", f"Built with: {c.comps[comp]['choice']}"]
    if comp not in c.cleaf:
        out += ["", f"Made of: {names(c, c.ckids[comp])}"]
    out += ["", f"Generated from {source} after all six steps were approved (latest: step {n} by {decisions[n].get('by')}, "
            f"{str(decisions[n].get('at')).replace('T', ' ')}). Build what it says. If it is wrong or incomplete, "
            "change the model and get it approved again; don't work around it in code.", ""]
    jobs = [f for f in c.funcs if f in c.fleaf and where(c, f) in sub]
    names_used = [c.by[i][1]["name"] for f in jobs for k in ("inputs", "outputs") for i in c.funcs[f].get(k) or [] if i in c.by]
    said = lambda step: any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", step, re.I) for n in names_used)
    stories = [s for s in m.get("scenarios") or [] if any(said(x) for x in s["steps"])]   # R19 keeps the words in step with the items
    if stories:
        out += ["## Scenarios", "", "The step 1 stories that mention something this part takes or gives.", ""]
        for s in stories:
            out += [f"### {s['id']} {s['name']}"] + [f"{n}. {x}" for n, x in enumerate(s["steps"], 1)] + [""]
    out += ["## Jobs", ""]
    for f in jobs:
        out += job(c, f, sub, comp) + [""]
    if not jobs:
        out += ["None: no job runs in this part.", ""]
    cells = connections(c, sub)
    if cells:
        out += ["## Connections", "", "| Interface | Other end | Comes in | Goes out |", "|---|---|---|---|"]
        for i in in_order(c, [k[0] for k in cells]):
            for o in in_order(c, [k[1] for k in cells if k[0] == i]):
                out.append(f"| {named(c, i) if i else '(none)'} | {named(c, o)} | {names(c, cells[i, o][0])} | {names(c, cells[i, o][1])} |")
        out.append("")
    used = in_order(c, [i for f in jobs for k in ("inputs", "outputs") for i in c.funcs[f].get(k) or [] if i in c.by])
    if any(c.by[i][1].get("description") for i in used):
        out += ["## Items", ""] + [f"- **{named(c, i)}**" + (f": {c.by[i][1]['description']}" if c.by[i][1].get("description") else "") for i in used] + [""]
    own, whole = [], []
    for r in c.leafreqs:
        got = reach(c, r)
        if c.sid in spec(r) or not spec(r):
            whole.append(r)
        elif got & subleaf:
            own.append((r, got - subleaf))
    reqs = []
    for cat, title in (("io", "Inputs and outputs"), ("system-wide", "System-wide"),
                       ("trade-off", "Trade-offs"), ("qualification", "Qualification")):
        lines = [x for r, shared in own if r.get("category") == cat for x in req_lines(c, r, shared)]
        reqs += [f"### {title}", ""] + lines + [""] if lines else []
    if whole:
        reqs += ["### Whole app", "", "These apply to the whole app; this part must not break them.", ""]
        reqs += [x for r in whole for x in req_lines(c, r)] + [""]
    if reqs:
        out += ["## Requirements", ""] + reqs
    allt = c.m.get("tests") or []
    groups = [("", {r["id"] for r, _ in own}), ("### Whole app", {r["id"] for r in whole})]
    shown, tables = set(), []
    for title, ids in groups:
        tests = [t for t in allt if ids & set(t["verifies"]) and t["id"] not in shown]
        shown |= {t["id"] for t in tests}
        if tests:
            tables += ([title, ""] if title else []) + ["| Test | Method | Proves |", "|---|---|---|"]
            tables += [f"| {named(c, t['id'])} | {t['method']} | {', '.join(i for i in t['verifies'] if i in ids)} |" for t in tests] + [""]
            said = [f"- **{t['id']}** {t['description']}" for t in tests if t.get("description")]
            tables += said + [""] if said else []
    if tables:
        out += ["## Tests", ""] + tables
    return "\n".join(out).rstrip()

VENDOR = {  # what the page loads from the web, and the offline copy in vendor/ that `serve` uses instead
    "https://fonts.googleapis.com/css2?family=Patrick+Hand&family=Atkinson+Hyperlegible:wght@400;700&display=swap": "fonts.css",
    "https://cdn.jsdelivr.net/npm/roughjs@4.6.6/bundled/rough.js": "rough.js",
    "https://cdn.jsdelivr.net/npm/elkjs@0.9.3/lib/elk.bundled.js": "elk.bundled.js"}
TYPES = {".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2"}
UNREADABLE = """<!doctype html><meta charset="utf-8"><meta name="color-scheme" content="light dark">
<title>Model can't be read</title>
<style>body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; }}
pre {{ white-space: pre-wrap; padding: 12px; border: 1px solid #8884; border-radius: 8px; }}</style>
<h1>Can't read {name}</h1><pre>{error}</pre><p>This page reloads by itself when the file changes.</p>
<script>setInterval(async () => {{ try {{ const r = await (await fetch("api/version", {{ cache: "no-store" }})).json();
  if (r.version !== {version}) location.reload(); }} catch (e) {{}} }}, 1500);</script>
"""

def make_server(model, step=6, port=8765):
    """Local review app for one model file: the page, live reload, and approve / send back saved to the review file."""
    model = Path(model).resolve()
    reviews, vendor, lock = review_path(model), Path(__file__).with_name("vendor").resolve(), threading.Lock()

    def version():
        return "-".join(f"{s.st_mtime_ns}.{s.st_size}" if s else "0" for s in
                        (p.stat() if p.exists() else None for p in (model, reviews, model.with_name("decisions.md"))))

    def decide(body):
        """Save one decision; returns (http status, reply)."""
        m = yaml.safe_load(model.read_text())
        n, decision, note = body.get("step"), body.get("decision"), str(body.get("note") or "").strip()
        if n not in range(1, step + 1) or decision not in ("approved", "sent back"):
            return 400, {"error": "Unknown step or decision."}
        if decision == "sent back" and not note:
            return 400, {"error": "Say what should change, then send it back."}
        found = check_model(m, step)
        if any(f["rule"] == "S01" for f in found):
            return 409, {"error": "The file doesn't match the format, so it can't be reviewed yet.", "reload": True}
        if body.get("fingerprint") != fingerprint(m, n):
            return 409, {"error": "The model changed while you were looking, so nothing was saved.", "reload": True}
        if decision == "approved" and not STARTED[n](m):
            return 409, {"error": "This step isn't started yet, so there is nothing to approve."}
        errors = sum(f["step"] == n and f["severity"] == "error" for f in found)
        if decision == "approved" and errors:
            return 409, {"error": f"Fix the {errors} must-fix problems first."}
        decisions = load_reviews(reviews)
        if decision == "approved":
            rows = progress(m, decisions, model)
            early = next((r for r in rows if r["step"] < n and r["turn"] != "done"), None)
            if early:
                return 409, {"error": f"Step {early['step']} {early['name']} isn't approved yet. Approve the steps in order."}
            if rows[n - 1]["why"] == "the AI is still working on it":
                return 409, {"error": "The AI is still working on this step. Wait until it hands the step over."}
        rules = {r for r, st, _, _ in JUDGMENT if st == n}
        decisions[n] = {"decision": decision, "by": getpass.getuser(), "at": datetime.now().isoformat(timespec="minutes"),
                        "fingerprint": fingerprint(m, n), "note": note, "elements": elements(m, n),
                        "checked": [r for r in body.get("checked") or [] if r in rules]}
        tmp = reviews.with_suffix(".tmp")
        tmp.write_text("# Review decisions from `sysmodel serve`, latest per step. An approval holds while the\n"
                       "# step's fingerprint matches the model; a change to what the step shows makes it stale.\n"
                       + yaml.safe_dump(dict(sorted(decisions.items())), sort_keys=False, allow_unicode=True))
        os.replace(tmp, reviews)
        return 200, {"version": version(), "review": review_state(m, decisions, step), "progress": progress(m, decisions, model)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, body, ctype="application/json", cache="no-store"):
            data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if not ctype.startswith("font") else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(data)

        def local(self):
            """Only pages this server handed out may talk to it (blocks other sites and DNS rebinding)."""
            hosts = {f"127.0.0.1:{self.server.server_address[1]}", f"localhost:{self.server.server_address[1]}"}
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (origin is None or urlparse(origin).netloc in hosts)

        def do_GET(self):
            path = urlparse(self.path).path
            if not self.local():
                return self.reply(403, {"error": "forbidden"})
            if path == "/api/version":
                return self.reply(200, {"version": version()})
            if path.startswith("/vendor/"):
                f = (vendor / path[len("/vendor/"):]).resolve()
                if vendor in f.parents and f.is_file() and f.suffix in TYPES:
                    return self.reply(200, f.read_bytes(), TYPES[f.suffix], "max-age=86400")
                return self.reply(404, {"error": "not found"})
            if path != "/":
                return self.reply(404, {"error": "not found"})
            v = version()
            try:
                m = yaml.safe_load(model.read_text())
            except (OSError, yaml.YAMLError) as e:
                page = UNREADABLE.format(name=html.escape(model.name), error=html.escape(str(e)), version=json.dumps(v))
                return self.reply(200, page, "text/html")
            page = render(m, step, load_reviews(reviews), {"version": v}, read_notes(model), model)
            for url, name in VENDOR.items():
                page = page.replace(url, "/vendor/" + name)
            self.reply(200, page, "text/html")

        def do_POST(self):
            if not self.local():
                return self.reply(403, {"error": "forbidden"})
            if urlparse(self.path).path != "/api/review":
                return self.reply(404, {"error": "not found"})
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.reply(415, {"error": "send JSON"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
                with lock:
                    code, out = decide(body if isinstance(body, dict) else {})
            except (OSError, ValueError, yaml.YAMLError) as e:
                code, out = 400, {"error": f"Couldn't save: {e}"}
            self.reply(code, out)

    try:
        return ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        return ThreadingHTTPServer(("127.0.0.1", 0), Handler)   # port taken (another model open?): any free one

def main(argv=None):
    ap = argparse.ArgumentParser(prog="sysmodel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="validate a model file")
    p.add_argument("model")
    p.add_argument("--step", type=int, choices=range(1, 7), default=6,
                   help="check only the rules for steps 1..N (default 6, everything)")
    p.add_argument("--json", action="store_true")
    r = sub.add_parser("render", help="write a review web page with the pictures for each step")
    r.add_argument("model")
    r.add_argument("--step", type=int, choices=range(1, 7), default=6, help="draw steps 1..N (default 6)")
    r.add_argument("-o", "--out", help="output .html file (default: next to the model)")
    st = sub.add_parser("status", help="where each step stands: done, the AI's turn, or waiting for a review")
    st.add_argument("model")
    w = sub.add_parser("wait", help="wait until a person approves or sends back a step in `serve`, then print it")
    w.add_argument("model")
    sp = sub.add_parser("spec", help="print the build spec for one part (component) of an approved design")
    sp.add_argument("model")
    sp.add_argument("component")
    s = sub.add_parser("serve", help="open the review app in the browser; approve or send back each step")
    s.add_argument("model")
    s.add_argument("--step", type=int, choices=range(1, 7), default=6, help="review steps 1..N (default 6)")
    s.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    if args.cmd == "serve":
        if not Path(args.model).is_file():
            sys.exit(f"cannot find {args.model}")
        srv = make_server(args.model, args.step, args.port)
        url = f"http://127.0.0.1:{srv.server_address[1]}/"
        print(f"Reviewing {args.model} at {url}\nDecisions go to {review_path(args.model)}. Press Ctrl+C to stop.", flush=True)  # flush: seen at once when run in the background
        write_state(args.model, serve={"pid": os.getpid(), "url": url})
        webbrowser.open(url)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            write_state(args.model, serve=None)
        return 0
    if args.cmd == "wait":
        if not Path(args.model).is_file():
            sys.exit(f"cannot find {args.model}")
        done = wait_for_review(args.model)
        if done is None:
            print("The review app stopped. Start `serve` again, then `wait`.", file=sys.stderr)
            return 2
        for n, d in sorted(done.items()):
            print(f"Step {n} {STEPS[n]}: {d.get('decision')} by {d.get('by')}, {str(d.get('at', '')).replace('T', ' ')}")
            if d.get("note"):
                print(f"Note: {d['note']}")
        print("\nRun `status` and go on with the loop.")
        return 0
    try:
        m = yaml.safe_load(Path(args.model).read_text())
    except (OSError, yaml.YAMLError) as e:
        sys.exit(f"cannot load {args.model}: {e}")
    if args.cmd == "status":
        rows = progress(m, load_reviews(review_path(args.model)), args.model)
        app = serve_alive(args.model)
        print(f"Review app: {app['url']}" if app else "Review app: not running; start serve")
        for r in rows:
            extra = f" ({r['warnings']} worth a look)" if r["warnings"] and r["turn"] != "done" else ""
            print(f"{r['step']} {r['name']:<11} {r['turn'].upper():<7} {r['why']}{extra}")
        nxt = next((r for r in rows if r["turn"] != "done"), None)
        print("\nAll six steps are approved. Build each part from `spec <component>`." if not nxt else
              f"\nNext: step {nxt['step']} {nxt['name']}, " +
              ("the AI's turn." if nxt["turn"] == "ai" else "waiting for a person to review it in `sysmodel serve`."))
        return 0
    if args.cmd == "spec":
        decisions = load_reviews(review_path(args.model))
        todo = [r for r in progress(m, decisions) if r["turn"] != "done"]
        if todo:
            print("No spec yet: the design isn't fully approved.", file=sys.stderr)
            for r in todo:
                print(f"  step {r['step']} {r['name']}: {r['why']}", file=sys.stderr)
            return 1
        c = index(m)
        if args.component not in c.comps:
            sys.exit(f"unknown part {args.component}; parts: " + ", ".join(named(c, i) for i in c.comps))
        print(part_spec(m, args.component, decisions, args.model))
        return 0
    if args.cmd == "render":
        out = Path(args.out or Path(args.model).with_suffix(".html"))
        out.write_text(render(m, args.step, load_reviews(review_path(args.model)), notes=read_notes(args.model), model=args.model))
        print(f"wrote {out}")
        return 0
    found = check_model(m, args.step)
    judgment = [j for j in JUDGMENT if j[1] <= args.step]
    counts = {s: sum(f["severity"] == s for f in found) for s in SEVERITIES}
    if args.json:
        keys = ("rule", "severity", "element", "message", "page")
        print(json.dumps({"findings": [{k: f[k] for k in keys} for f in found],
                          "judgment": [{"rule": r, "step": st, "text": t, "page": pg} for r, st, pg, t in judgment],
                          "counts": counts}, indent=2))
    else:
        print(f"Checking steps 1-{args.step}: {', '.join(STEPS[i] for i in range(1, args.step + 1))}\n")
        for f in found:
            book = f" (book p.{f['page']})" if f["page"] else ""
            print(f"{f['rule']} {f['severity']}  {f['label']}: {f['message']}{book}")
        print("\nNeeds human sign-off:")
        for r, st, pg, t in judgment:
            print(f"  [ ] {r} (book p.{pg}) {t}")
        print(f"\n{counts['error']} errors, {counts['warning']} warnings, {counts['advice']} advice")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
