# Step 6 · Test plan: How will we prove it works?

Decides how each requirement gets proven, by whom, and what counts as a pass. It comes last because every test points at a requirement, and a requirement you cannot turn into pass or fail goes back to step 1. The book calls the whole thing qualification: verification, validation and acceptance (p. 284). Book: Ch 11, activity A116 (pp. 241, 298, 300), planning activities A116.P1-P4 (Table 11.2, p. 298).

## Fills in
- `tests` (verification requirement, p. 59; qualification activity, p. 298): `id`, `name`. One thing that is run or checked. Name what is exercised and the pass line, for example "Availability probe, 30 days, at least 99.9%". The book's test requirements likewise give counts and how a result is judged (p. 316).
- `method` (qualification method, Table 11.3, p. 301): the book's four become two. `automated`: a script decides pass or fail and anyone can rerun it (the book's instrumented test). `manual`: a person performs or judges it (inspection, demonstration, analysis, user trial).
- `verifies` (qualifies, p. 142): the requirement ids this test proves. One test may prove several; a requirement may need several tests.
- The pass line has no field: it is the requirement's `threshold` (or the number in its text), plus trial counts or duration in the test `name`.
- The model cannot hold these, so put them in the hand-off message: the kind of each test (verification, validation or acceptance), steps and data of manual tests, the test environment and stand-ins for outside systems, risks to finishing the tests, what you skipped.
- Tests change only step 6. A new requirement also changes step 1: propose it and ask first.

## Start from
- Step 1 `requirements`: leaf io and system-wide ones need tests (R25). Read their `threshold`s, the qualification requirements (`observance`, `verification-plan`, `validation-plan`, `acceptance-plan`), `scenarios` and `objectives`.
- Step 5 `interfaces` and any fault-handling jobs: they need tests too.
- Run `sysmodel check --step 6`. The test plan table in `sysmodel serve` shows each requirement as Covered, Needs a test (io and system-wide) or Optional (trade-off and qualification).

## Do
1. **Pass lines (A116.P1.1-P1.3, p. 297).** The objectives drive what you prove. Take each pass line from the requirement's `threshold`. The book wants it neither too low (the test proves nothing) nor too high (money spent fixing what is not worth fixing, p. 297). When a measured requirement has no threshold, **Ask:** What is the least that counts as a pass for X? A threshold change edits step 1. If you cannot say what pass or fail looks like, the requirement is not testable (p. 287, R27): propose a rewrite and send it back to step 1.
2. **Qualification requirements (A116.P1.5, p. 297; categories p. 142).** Step 1 should have written them. Your tests carry them out:

   | `subcategory` | Question | Run by | Usual tests |
   |---|---|---|---|
   | `observance` | which proof is collected for each io and system-wide requirement, and by what method (p. 142) | whoever runs each test | the `tests` list itself |
   | `verification-plan` | built right? Each part and the system meet their requirements (pp. 55, 287) | development team | automated tests against thresholds |
   | `validation-plan` | right app? Meets the operational concept and the stakeholders' performance, cost and trade-off needs (pp. 142, 285) | development team | whole-scenario runs, cost check |
   | `acceptance-plan` | do the stakeholders accept it? (p. 285) | stakeholders, real users | manual trial of key tasks |

   Verification, validation and acceptance overlap in time; none waits for the one before to end (p. 287). If a kind is missing, draft one line and ask first. **Ask:** Who will try the finished app, and what must they manage to do for you to accept it?
3. **Cover every io and system-wide requirement (A116.P1.8, pp. 297-298; R25).** The book wants every requirement tested individually (p. 297). This tool requires a test for each leaf io and system-wide requirement (see 9 for the rest). Never test a group (R04).
   - io requirement: functional (black-box) test, right output for a given input. Positive cases come from the requirements; negative cases try inputs the requirements missed (Table 11.6, p. 303).
   - system-wide requirement: structural test of performance, recovery, stress, security or availability (Table 11.4, p. 302).
   - One test may prove several requirements; do not repeat checks (p. 299). A failing test should point at where it broke (p. 295). Where a requirement's job sits in one part (`runs_in`), also test that part alone with its neighbours faked (A116.P3, p. 299; p. 320).
4. **Method (A116.P2.1, Table 11.3, p. 301).** `automated` whenever a script can decide. `manual` when a person must judge (reading a screen or docs: inspection), watch someone use the app (demonstration), or work from collected data or a model because a direct test is too costly or impossible (analysis: monthly uptime report, cost projection).
5. **Scenario tests (A116.P1.4, P4.1, pp. 297-298; p. 305).** Give each `scenarios` entry at least one test that walks its steps from the outside, and name the scenario in the test. Tasks come from the operational concept, each with a setting, circumstances, a clear outcome and a time limit (p. 305). Whole scenarios serve acceptance and late validation; segments serve earlier work (p. 305).
6. **Interface and fault tests (Table 11.4, p. 302).** Every interface from step 5 needs a test that sends its items across it. Every fault-handling job needs a test that causes the fault and checks recovery. Link them to the requirement that justifies the interface or job; if there is none, that is a step 1 gap: propose one. Spend effort where faults cost most and happen most: the book's fault scale puts lost inputs, mixed-up data and silent database corruption high (p. 296) and weighs consequence by frequency (pp. 296-297).
7. **Acceptance (pp. 302-305).** Stakeholders decide acceptance, with thresholds agreed early (p. 302). A small, representative group of real users does it, and usability is the focus (p. 303): learnability, efficiency, memorability, error rate, satisfaction, written as system-wide requirements (p. 305). Two designs (p. 304): assume the app is acceptable and try to fail it with a few hard key tasks, or assume it is not and require most ordinary tasks to pass. **Ask:** Who are the representative users, and which tasks decide yes or no? Expect `manual` tests.
8. **What did we forget? (pp. 303-304).** The key question in verification and validation is "what have we forgotten to test?" Brainstorm odd input orders and paths you think cannot matter. The book's cases: Therac-25, a rare command sequence (p. 307), and Ariane 5, an old requirement carried into a new setting (p. 308). A found hole usually needs a new requirement first (step 1: propose, ask), then a test.
9. **Coverage (A116.P1.8-P1.10, p. 297).** Run `sysmodel check --step 6` until R25 is clean. The tool does not check these; sweep them yourself (pp. 286, 288): each scenario has a test; each objective has a requirement with a test; each external connection has an `external-interface` requirement; each item entering or leaving has an io requirement. Trade-off rows show Optional; add a test where a number exists (validation covers cost and trade-offs, p. 142). The `tests` list is the master plan.
10. **Skip or mention (A1161-A1166, P1.6-P1.7, P2.2-P2.5, P3.2-P3.6, P4.5; pp. 297-300).** Skip designing a qualification system (its functions, parts, interfaces, models), organizations, resources, assignments and schedules. Mention only what limits testing: staging, test accounts and data, stand-ins for outside systems you cannot call in tests (p. 293), and risks to finishing (P1.9, pp. 297-298). Test code, data and manual procedures (P4.2-P4.4) live in the repo, not the model. Grow tests from parts to whole; assembling everything untested at once makes errors hard to trace (pp. 293, 295).

## Good vs bad
- Every requirement tested individually (p. 297); only single, clear, checkable statements can be verified (p. 287).
- Verification alone does not show the right app; the two chains of checks are only as strong as their weakest link (pp. 287, 306).
- No one procedure answers every question, so use complementary tests (p. 295).
- Bad: `name: Works well` verifying Q3. Good: `name: Availability probe, 30 days, at least 99.9%`.
- Bad: `method: manual` for "Long URL accepted". Good: `automated`, since a script can decide.
- Bad: one test "Everything" verifying five unrelated requirements. Good: a test per requirement or tight group, so a failure says where.

## Checks
| Rule | What it means | Usual fix |
|---|---|---|
| R25 (p. 142), error | every leaf io and system-wide requirement is in some test's `verifies` | add a test; if no test can pass or fail, rewrite the requirement in step 1 (ask) |

Earlier rules still apply: S03 (`verifies` must point at requirements) and R04 (step 1: a group is never tested). A person signs off: no judgment item starts at this step. In the hand-off, say which tests are verification, validation and acceptance, and what you skipped.

## Example
```yaml
scenarios:                       # from step 1
  - id: SC1
    name: Marketer shares a link
    steps: ["Marketer submits a long URL", "System returns a short link", "Visitor opens it", "System redirects the visitor"]
tests:                           # T1-T4 as in valid.yaml; T3 and T4 now carry their pass lines
  - {id: T1, name: Create link end to end, method: automated, verifies: [Q1]}
  - {id: T2, name: Long URL of 2000 characters accepted, method: automated, verifies: [Q2]}
  - {id: T3, name: "Availability probe, 30 days, at least 99.9%", method: manual, verifies: [Q3]}
  - {id: T4, name: Cloud bill for one month under 20 USD, method: manual, verifies: [Q4]}
  - {id: T5, name: "SC1 walk-through: create link, open it, land on target", method: automated, verifies: [Q1]}
  - {id: T6, name: "Storage fault injected, write retried", method: automated, verifies: [Q1]}   # only if step 5 added F13
# Gap: no requirement covers SC1's last step (the redirect). Propose one in step 1, then T5 should verify it too.
```
