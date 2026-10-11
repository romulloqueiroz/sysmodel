# Levels: a subsystem designed in its own model

Some parts are big enough that their insides need a design of their own. Once a level's allocated architecture is approved, such a part (a subsystem) gets its own model and goes through the six steps again, one level down. The team that gets it does not start from scratch: it extends the work of the level above (p. 321). This guide says when to split, what the new level starts with, and how to keep the two levels consistent. Book: Ch 12, section 12.10 (pp. 321-322); specifications for subsystems, section 9.8 (p. 259).

## Fills in
- `components[].subsystem: true` on a part in step 3 of the level above. It marks the part as a subsystem; nothing else in the model changes.
- `sysmodel level <model> <component>` then writes the child model to `<dir>/<component>/<same file name>`. That folder has its own `decisions.md`, `answers.md`, `.review.yaml` and `specs/`.
- The child's `system.id` is the part's id (`C1`). The child is a normal model: steps 1 to 6, the same rules, the same review app.
- Nothing else. Change requests have no field; they go in `decisions.md` (Do 5).

## Start from
- The level above, fully approved and free of L01 at its own level, and so is every level above that (`level` refuses otherwise).
- The part's `choice` in the level above. The command prints it and writes it into the child's `decisions.md` under `## Step 3 Parts`. It is fixed there: change it by a change request.
- The child model the command wrote. Read the whole file before editing it.

## Do
1. **Decide which parts are subsystems** (step 3 of the level above). A part is a subsystem only if all three hold:
   - Its insides need their own function and part breakdown, beyond what this level needs (pp. 202, 210, 238).
   - It can be handed off and designed on its own, by a separate team or in a separate stack (p. 214).
   - It owns whole functions that no sibling part shares (p. 322).

   When one fails, keep it a part inside this model and split it there (C2 into C21 and C22). Each level costs six more reviews. **Ask:** Which parts will a different person or team build, or use a different stack, or need more than a handful of jobs of their own?
2. **Make the level.** When every step of the level above is approved, run `level` for each subsystem. A subsystem must be a smallest part of its level (L02). This is the tool's tailoring: the book's subsystems are the first-level parts (p. 321), and the rule keeps each inside in exactly one place. A child may mark its own parts as subsystems; they get levels one deeper.
3. **Know what the child inherits.** The command computes this from the approved level above.

   Frozen, checked by L01. The child may not edit these; a difference is an error:
   - the boundary: every far end of the part's connections, rolled up to the highest ancestor that does not hold the part (id, and the items it `sends` and `receives`), and the items that cross (name, description);
   - the requirements that are the part's own, and the system-wide constraints that apply to the whole app, such as a required technology (text, category, subcategory, stage, threshold, objective). The second kind is the book's equivalence technique (p. 252). Quality, cost and schedule budgets are not copied: the part gets only the share apportioned to it (pp. 251-252);
   - objective ids and names under a new root `C1.O0`;
   - the interfaces that touch the part (id, far end, what they carry). The near end is the part or any part inside it, since this level designs those parts.

   Seeded once, then yours to edit:
   - `purpose`, as `TBD`; step 1 cannot pass until you write it (R24);
   - `specifies` on the inherited requirements, now pointing at `C1`, an item or the seeded functions;
   - the largest functions that lie wholly inside the part, with their subtrees. One becomes the root; several sit under `C1.F0`;
   - the scenarios that mention boundary items, the `stages`, and the tests that verify inherited requirements;
   - the external `kind`, and objective weights (derive them, Fig 9.8, pp. 252-253);
   - one source, `UP`, named by the path of the level above.

   Not inherited: validation-plan and acceptance-plan requirements (p. 255); whole-app trade-off, observance and verification-plan requirements (the child derives its own, pp. 252, 255); the level above's other parts.

   Why: the level above made promises to its stakeholders and to its other parts. The boundary and the inherited requirements are those promises. Freezing them lets each level be reviewed and tested alone. Everything inside is the child's to design.
4. **Extend the level above, step by step** (pp. 321-322):
   - Step 1: purpose, scenarios (extend the seeded ones with ones only this part sees), externals, objectives (weights), requirements (most exist already; add only the part's own, with `derived_from` on an inherited id). See the note on approval below.
   - Step 2: break the seeded functions down. New items stay inside the part unless they cross the boundary.
   - Step 3: the part's own tree. Its `choice` is fixed by the level above.
   - Step 4: allocate and derive shares of the part's budgets.
   - Step 5: connect the parts inside. The inherited interfaces may end at the part or at any part inside it; say which.
   - Step 6: tests for the inherited requirements, plus the part's own. No validation or acceptance plan (p. 255). Record the integration order and the stubs in `decisions.md` (SKILL.md, Building).
5. **Change requests** (p. 321). If the child cannot live with something frozen, do not edit it. Write it under `## Change requests` in the child's `decisions.md`: what to change in the level above, and what fails without it. The AI copies each into the level above's `decisions.md` under `### Waiting for your yes`, in the step it touches. If the engineer says yes and the level above is re-approved, L01 in the child lists exactly what to update. If a request is declined, the child designs around it.
6. **Approve the child's step 1 as the preliminary design review** (p. 259). Hold it soon after the child starts, with the stakeholders, so they can say yes to proceeding. **Ask:** Which stakeholders must take part in the review of this part's step 1?
7. **Keep the gate.** A child's steps can be approved only while every level above is fully approved and free of L01. Editing a child meanwhile is fine, since the chunks of a design proceed concurrently (p. 242). If the level above is edited, its approvals go stale, and so does the gate. Read the child's `status` for the reason.

## Good vs bad
- One function, one subsystem (p. 322). Bad: two subsystems each taking half of "Resize image". Good: one function, one subsystem; regroup the functions first (step 2, ask).
- Bad: a subsystem for every part. Good: a subsystem only where the three conditions hold.
- Bad: editing a frozen requirement in the child to fit the design. Good: a change request, and a design that works until it is answered.
- New ids in a child carry the system id as a prefix (`C1.F1`, `C1.Q1`), so they never clash with the level above. Ids copied from the level above keep their own.
- The child's `sources` list the inherited ones as `UP`. A requirement the child writes cites a source of its own, or `derived_from` an inherited id.

## Checks
| Rule | What it means | Usual fix |
|---|---|---|
| L01 (p. 321), error, step 1, child only | the child differs from what the level above set: a missing or changed external, item, requirement, objective or interface, or an extra send or receive | read the message; restore the child to match, or send a change request. After the level above changes, update the child to match |
| L02 (p. 321), error, step 3 | a subsystem part has parts of its own in this model | remove its parts or its `subsystem` flag; design the insides in the child |
| L03 (pp. 251-252), warning, step 4 | a subsystem part has no share of a system-wide quality, cost or schedule requirement | derive a requirement from it that `specifies` the part (4-match.md, Do 4) |
| L04 (p. 322), warning, step 4 | a job split into smaller jobs has smallest jobs both inside a subsystem part and outside it | regroup the jobs (step 2, ask) or move them (`runs_in`) so the subsystem owns whole jobs |

How to read L01. A message names the element and the difference, for example `E1 "Web visitor": sends I9, the level above does not` (the child sends something the boundary does not carry) or `Q6 is in the level above but missing here`. The first words tell which kind it is: `is in the level above but missing here` means add it back; `is X here but Y in the level above` means set it back. A fresh child's only must-fix problem at step 1 is R24 (the purpose); C03 also advises its own observance and verification-plan requirements (p. 255).

L02 is the tool's tailoring, not a book rule. L01 is the book's consistency goal: success means no subsystem team needed to change the level above (p. 321).

A person signs off the same judgment items as in each step, level by level. The child's step 1 approval is also the preliminary design review.

## Example
A URL shortener whose "Redirect service" (C2) is its own level. Step 3 of the app marks it:
```yaml
components:
  - {id: C2, name: Redirect service, parent: S, choice: Go service, subsystem: true}
```
After all six steps are approved, `level design/system.yaml C2` writes `design/C2/system.yaml` and `design/C2/decisions.md`. The child then holds `system: {id: C2}`, the external `E1 "Web visitor"` with the items it sends and receives, the inherited requirements, objectives under `C2.O0`, the seeded functions, and `TBD` for the purpose. It has one error at step 1: R24. The AI writes the purpose, asks the engineer the step 1 questions, and goes on.

A `decisions.md` sketch in the child:
```
## Change requests
- Q4 (redirect within 200 ms) cannot hold if E2 stays a remote store with 150 ms round trips. Ask the level above to relax Q4 to 300 ms, or allow a local cache next to C2.
```
