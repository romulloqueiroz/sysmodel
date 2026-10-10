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

- `status`: whose turn each step is (DONE, AI, PERSON) and the next step. **Run it first, every time.**
- `check --step N`: rule problems for steps 1..N, each with the book page. Exits 1 while anything must be fixed.
- `serve`: the review app where people see the pictures and approve or send back each step. It runs until stopped, so
  start it in the background, once per session, and give the engineer the URL it prints. It reloads by itself when the model changes.
- `render`: a static HTML snapshot next to the model, for sharing. Read-only.
- `spec <model> <component>`: the build spec for one part: its scenarios, jobs, connections, requirements and tests, taken from
  the model. It refuses until all six steps are approved.

## Files

- **Model**: use the project's existing model (a YAML file with top-level `system:` and `requirements:`; `design/system.yaml` by
  convention). No model yet: ask what the app is for and who uses it, create `design/system.yaml`, and start step 1.
- **Schema**: `${CLAUDE_SKILL_DIR}/schema.json` lists the only fields the model may have. A small valid model to copy from:
  `${CLAUDE_SKILL_DIR}/tests/fixtures/valid.yaml`.
- **Answers**: `answers.md` next to the model. After each round of questions, append the date, each question and the
  engineer's answer, word for word. A source that is a conversation points here (title it `answers.md, <date>`), so a
  later session can tell what the engineer said from what you proposed.
- **Reviews**: `<model>.review.yaml` next to the model, written by `serve` when a person clicks Approve or Send back.
  Read it for the notes. **Never edit it.**

## The six steps

Read the step's guide before working on it. Each says what the step fills in, what to do in the book's order, what to ask the engineer, and which checks apply.

| Step | Question | Guide |
|---|---|---|
| 1 Problem | Who uses it, and what must it do? | [steps/1-problem.md](steps/1-problem.md) |
| 2 Functions | What does it do, step by step? | [steps/2-functions.md](steps/2-functions.md) |
| 3 Parts | What is it made of? | [steps/3-parts.md](steps/3-parts.md) |
| 4 Match | Which part does each job? | [steps/4-match.md](steps/4-match.md) |
| 5 Interfaces | How do the parts connect? | [steps/5-interfaces.md](steps/5-interfaces.md) |
| 6 Test plan | How will we prove it works? | [steps/6-test-plan.md](steps/6-test-plan.md) |

## The loop

1. Run `status`. Work on the **Next** step when it is the AI's turn. When it waits for a person, say so and stop; work
   ahead on a later step only if the engineer asks. When all six are approved, go to Building.
2. Read that step's guide, then the model.
3. If the step was sent back, the note is your task list. Handle every point in it; ask about any point you don't understand.
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
     a proposal to the engineer's answers.
   - Without the AskUserQuestion tool, ask the same small rounds as a numbered list with the suggested answers.
5. Edit the model. Keep ids stable: links and approvals hang on them. For a new model use short ids like the example's (`Q1`, `F11`, `C2`);
   otherwise follow the style already in the file.
6. Run `check --step N` until nothing must be fixed. Read the warnings: fix them, or say in the hand-off why they stay.
7. Run `status` and confirm the step now waits for a person.
8. Hand off (below).

## Approved steps are a baseline

An approval covers exactly what that step decided. Changing it makes the approval stale, and the step needs another review.
Before you change anything an approved step covers, tell the engineer which steps would need re-approval and why, and wait
for a yes, unless they asked for that very change. A step's own additions don't undo earlier approvals: new internal
items and `specifies` links in step 2, `runs_in` and derived requirements in step 4. Which steps cover what:

| Piece of the model | Steps |
|---|---|
| `stages`, `stakeholders`, `sources`, `objectives`, `scenarios` | 1 |
| `system` | 1, 3 |
| `external` | 1, 5 |
| `items` an external system sends or receives | 1, 2, 5 |
| other `items` | 2, 5 |
| `requirements` without `derived_from` (all fields but `specifies`) | 1, 6 |
| `requirements` with `derived_from` (all fields but `specifies`) | 4, 6 |
| `specifies` links to the system | 1 |
| `specifies` links to functions and items | 2 |
| `specifies` links to components | 4 |
| `functions` (all fields but `runs_in`) | 2, 4 |
| `runs_in` | 4 |
| `components` | 3, 4, 5 |
| `interfaces` | 5 |
| `tests` | 6 |

## Building

Only when `status` says all six steps are approved.

1. Build the smallest parts first, one at a time: run `spec` for the part and build what it says, with its tests.
   Then join the parts and run the tests of the larger parts and the whole app (bottom-up, book p. 320).
2. Put the test id in each test's name (`T2 long URL accepted`) so results trace back to the model.
3. The spec is the contract. If building shows it is wrong or missing something, stop and propose the model change
   (the book's change request, p. 321). It goes back through review; don't drift from it in code.

## Hand-off

After each round, tell the engineer, in plain words and briefly:

- what you added or changed, by step;
- what you assumed, and the questions still open;
- what the guide asked you to bring up that the model can't hold (alternatives you weighed and why you chose, risks);
- which step to review now, at the `serve` URL.

## The book

Buede & Miller, *The Engineering Design of Systems*, 4th ed. Page numbers in the guides and in `check` output are printed pages.
This project tailors the method for apps: requirements use only the 4 categories (io, system-wide, trade-off, qualification);
life-cycle stages are build and release; tests are automated or manual; item types are not tracked.
