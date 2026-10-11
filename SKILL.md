---
name: sysmodel
description: Designs an app step by step with the systems engineering method of Buede & Miller (The Engineering Design of Systems), keeping the design in one YAML model that engineers review and approve per step in a local web app. Use when the user wants to design or rework an app's architecture, write requirements, break down its jobs (functions) or parts (components), match jobs to parts, define interfaces, plan tests, check or review the system model, act on review notes sent back from `sysmodel serve`, or build a part of an approved design.
argument-hint: "[step number, or what to do]"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/sysmodel.py *)
---

# sysmodel: design an app with the Buede & Miller method

The design lives in one YAML file, the **model**. You edit the model; people approve it one step at a time in the review app.
You never approve anything yourself.

## Commands

Run `python3 ${CLAUDE_SKILL_DIR}/sysmodel.py <command> <model>`:

- `status`: whose turn each step is (DONE, AI, PERSON) and the next step, and `Review app: <url>` or `not running; start serve`.
  **Run it first, every time.**
- `check --step N`: rule problems for steps 1..N, each with the book page. Exits 1 while anything must be fixed.
- `serve`: the review app where people see the pictures and approve or send back each step. It runs until stopped, so
  start it in the background, once per session, and give the engineer the URL it prints. It reloads by itself when the model changes.
- `wait`: when it starts it records the hand-off (which steps are ready for review); the page lets the engineer approve only
  those steps. It then blocks until a person approves or sends back a step in `serve`, and prints the decision and the note.
  Start it in the background right after your edits and **before** the hand-off message; when it ends, you are woken to carry on,
  with no prompt needed. It exits with code 2 if `serve` stopped.
- `render`: a static HTML snapshot next to the model, for sharing. Read-only.
- `spec <model> <component>`: the build spec for one part: its scenarios, jobs, connections, requirements and tests, taken from
  the model. It refuses until all six steps are approved.
- `level <model> <component>`: starts the level for a part marked `subsystem: true`: writes its model, seeded from the approved
  level above, to `<dir>/<component>/` and prints the part's `choice`. It refuses until every level above is fully approved and
  free of L01, and when the part is not a subsystem or its level exists. Read [steps/levels.md](steps/levels.md) first.

## Files

- **Model**: use the project's existing model (a YAML file with top-level `system:` and `requirements:`; `design/system.yaml` by
  convention). No model yet: ask what the app is for and who uses it, create `design/system.yaml`, and start step 1.
- **Schema**: `${CLAUDE_SKILL_DIR}/schema.json` lists the only fields the model may have. A small valid model to copy from:
  `${CLAUDE_SKILL_DIR}/tests/fixtures/valid.yaml`.
- **Answers**: `answers.md` next to the model. After each round of questions, append the date, each question and the
  engineer's answer, word for word. A source that is a conversation points here (title it `answers.md, <date>`), so a
  later session can tell what the engineer said from what you proposed.
- **Decisions**: `decisions.md` next to the model, one `## Step N Name` heading per step. Under it, what the step's guide says
  the model can't hold: the pick, the runner-up and why; assumptions; risks and estimates; warnings left on purpose, with the
  reason; work deferred to a later step; proposed changes waiting for a yes; open questions.
  Update the step's section each round and keep it short. Proposals that need a yes (a change to an approved step, anything a
  guide says to "propose and ask first") are bullets under `### Waiting for your yes` in the step's section; the review page
  shows them at the top. When one is answered, move it to done or declined. Work deferred to a later step goes under
  `### For step N` in the deferring step's section. Open questions are only facts the engineer can't know yet. Unlike `answers.md` (the engineer's words only), this is the AI's record.
- **Levels**: a part marked `subsystem: true` in step 3 is designed in its own model, one level down. A design is a tree:
  `design/system.yaml` for the top, `design/C1/system.yaml` for subsystem C1 (same file name), `design/C1/C11/system.yaml` below that. Each level
  has its own `decisions.md`, `answers.md`, `<name>.review.yaml` and `specs/` in its own folder, and its own six steps.
  `serve` and `wait` take the top model. A level's ids are its own: prefix new ones with its system id (`C1.F1`). Small
  splits stay in one model; mark a subsystem only as [steps/levels.md](steps/levels.md) says.
- **Reviews**: `<model>.review.yaml` next to the model, written by `serve` when a person clicks Approve or Send back.
  Read it for the notes. **Never edit it.**

## The six steps

Read the step's guide before working on it; every level repeats the six steps. Each says what the step fills in, what to do in the book's order, what to ask the engineer, and which checks apply.

| Step | Question | Guide |
|---|---|---|
| 1 Problem | Who uses it, and what must it do? | [steps/1-problem.md](steps/1-problem.md) |
| 2 Functions | What does it do, step by step? | [steps/2-functions.md](steps/2-functions.md) |
| 3 Parts | What is it made of? | [steps/3-parts.md](steps/3-parts.md) |
| 4 Match | Which part does each job? | [steps/4-match.md](steps/4-match.md) |
| 5 Interfaces | How do the parts connect? | [steps/5-interfaces.md](steps/5-interfaces.md) |
| 6 Test plan | How will we prove it works? | [steps/6-test-plan.md](steps/6-test-plan.md) |

## The loop

1. Run `status`. Work on the **Next** step when it is the AI's turn. When it waits for a person, say so, start `wait` in the background and stop; work
   ahead on a later step only if the engineer asks. When all six are approved, go to Building. If `status` says the review
   app is not running, start `serve` first.
   With levels, `status` shows the tree: work on the level and the step it names, and read the child's model for that level. When a level
   is approved and `status` says a subsystem needs its level, run `level` for it and start that level's step 1.
2. Read that step's guide, then the model and `decisions.md`.
3. Every review note, approved or sent back, is copied word for word into `answers.md` with the date, and acted on: an approval
   note can ask for changes too. If the step was sent back, the note is your task list. Handle every point in it; ask about any
   point you don't understand.
4. Ask the engineer what only they can know: users, priorities, thresholds, budgets, any fixed date. Don't invent these
   facts, and don't park them as TBD (rule R24).
   - The guide's **Ask:** lines are a list to choose from, not a script. Skip what the brief, the repo or an earlier
     answer already settles.
   - Ask with the AskUserQuestion tool, in rounds of at most 4 questions, most important first (the guide's order).
     Give each question 2-4 likely answers drafted from what you know; the engineer can always type their own.
     Numbers too: offer 2-4 sensible values. Mark a recommendation "(Recommended)" only on a choice you can judge.
     Recommend nothing for facts only the engineer knows (team size, dates) or for what matters most (rule R28).
   - One thing per question (one number each), in one short line. Ask another round only for what the answers left open.
   - Don't ask how to build it (web or native, which database): that's step 3, unless the engineer sets it as a rule.
   - Where you can propose a sensible value yourself (wording, a technical default), don't ask: use it, give it a
     source of its own titled "Proposed by the AI, to confirm in review", and list it in the hand-off. Never credit
     a proposal to the engineer's answers. A requirement with any proposed part (a limit, a design goal, a detail,
     weights you turned from a ranking) takes the proposal source.
   - Before the hand-off, ask a last round about anything still open that only the engineer can decide (scope,
     who may do what). Never park these for the review or defer them to a later step.
   - Without the AskUserQuestion tool, ask the same small rounds as a numbered list with the suggested answers.
5. Edit the model. Keep ids stable: links and approvals hang on them. For a new model use short ids like the example's (`Q1`, `F11`, `C2`);
   otherwise follow the style already in the file.
6. Run `check --step N` until nothing must be fixed. Read the warnings: fix them, or say in `decisions.md` why they stay, one line
   each as `Accepted: <rule> <id>: <reason>` (the review page shows it on the warning).
7. Run `status` and confirm the step now waits for a person.
8. Write `decisions.md`, start `wait` in the background, then hand off in chat (below). Starting `wait` first matters: the page
   accepts an approval only for steps it handed off. If `wait` exits 2, start `serve` again, then `wait`. When it ends, start
   again at 1.

## Approved steps are a baseline

An approval covers exactly what that step decided. Changing it makes the approval stale, and the step needs another review.
Before you change anything an approved step covers, tell the engineer which steps would need re-approval and why, and wait
for a yes, unless they asked for that very change. A review note that asks for a change to an earlier step counts as asking
   for that change. A step's own additions don't undo earlier approvals: new internal
items and `specifies` links in step 2, `runs_in` and derived requirements in step 4. After editing anything an approved step covers, run `check` (all steps) and `status`, and list in the hand-off
which steps went stale. Which steps cover what:

| Piece of the model | Steps |
|---|---|
| `stages`, `stakeholders`, `sources`, `objectives`, `scenarios` | 1 |
| `system` | 1, 3 |
| `external` | 1, 5 |
| `items` an external system sends or receives | 1, 2, 5 |
| other `items` | 2, 5 |
| `requirements` without `derived_from` (all fields but `specifies`) | 1, 6 |
| `requirements` with `derived_from` (all fields) | 4, 6 |
| `specifies` links of requirements without `derived_from` to the system | 1 |
| `specifies` links of requirements without `derived_from` to functions and items | 2 |
| `specifies` links of requirements without `derived_from` to components | 4 |
| `specifies` links of requirements without `derived_from` to interfaces | 5 |
| `functions` (all fields but `runs_in`) | 2, 4 |
| `runs_in` | 4 |
| `components` | 3, 4, 5 |
| `interfaces` | 5 |
| `tests` | 6 |

## Building

Only when `status` says all six steps of a level are approved.

1. Build top-down by default, one level at a time (the book's alternative to bottom-up, pp. 289, 293-294). For the approved level:
   build its smallest parts, and a **stub** for each subsystem from `spec` (a fake that honours the connections and items), then
   run that level's tests. Then `level` for each subsystem and take it through its six steps (children may overlap with
   building their parent), then build it the same way. A model with no subsystem is built as before: smallest parts first, then
   the larger parts and the whole app.
2. Each level's step 6 records in `decisions.md` its integration order and its stubs (Fig 1.20, p. 34; Table 11.2, p. 298). Build a
   subsystem for real instead of stubbing it when it is reused, off-the-shelf or cheaper than a fake (p. 294). Say the risks of the
   order you chose (Table 11.1, p. 294).
3. Before running a level's tests, mark which of them mean anything against a stub. A test of a requirement whose jobs run in a
   stubbed subsystem waits for the swap. Validation and acceptance count as passed only after every stub in the tree is swapped (p. 306).
4. When a real subsystem replaces its stub, re-run the tests of every level above it up to the top (integration, Table 11.1,
   p. 294). A fix re-runs the tests of the level that was fixed (regression, p. 290).
5. Before building a part, read `decisions.md` (steps 3-5) along with the spec, and save the spec to `<level dir>/specs/<id>.md`.
   Put the test id in each test's name (`T2 long URL accepted`) so results trace back to the model.
6. The spec is the contract. If building shows it is wrong or missing something, stop and propose the model change
   (the book's change request, p. 321). It goes back through review; don't drift from it in code. A proposed model change
   blocks `spec` until it is re-approved: keep building the unaffected parts from their saved specs meanwhile. A subsystem's change
   request goes in its `decisions.md` under `## Change requests`, and you copy it to the level above (steps/levels.md).

## Hand-off

After each round, first write its content into `decisions.md` and start `wait`. Then tell the engineer in chat, in plain words and briefly;
the review page shows the full detail, so point them there, never to the files:

- what you added or changed, by step;
- what you assumed, and the questions still open;
- what the guide asked you to bring up that the model can't hold (alternatives you weighed and why you chose, risks);
- which steps went stale, if you changed anything an approved step covers;
- which step to review now, at the `serve` URL, and that you will see their decision there without being told.

## The book

Buede & Miller, *The Engineering Design of Systems*, 4th ed. Page numbers in the guides and in `check` output are printed pages.
This project tailors the method for apps: requirements use only the 4 categories (io, system-wide, trade-off, qualification);
life-cycle stages are build and release; tests are automated or manual; item types are not tracked.
