# Step 4 · Match: Which part does each job?

Decide which leaf part runs each leaf function, and what each part must meet. This is where functions and parts come together (p. 238). Step 5 puts an interface wherever an item crosses from one part to another, so this matching decides which interfaces exist (p. 249), and step 6 proves requirements part by part. Book: Ch 9, activities A1141–A1145 (p. 240).

## Fills in
- `functions[].runs_in` (allocated to, p. 243): the one leaf component that performs a leaf function. Leaf functions only.
- `requirements[].derived_from` (derived requirements, p. 249): on each requirement you add, the requirements it comes from. Use it instead of `source`.
- `requirements[].specifies` (p. 249): on new requirements, the item and function, or the components, they constrain. The step 1 system-wide requirements keep pointing at the system.
- New requirements use the step 1 fields: `category`, `subcategory`, `stage` (same as the parent's), "shall" text, `threshold`, `objective`.
- No field exists for activation and control structure (A1142), performance and risk analyses (A1143), or the reasons for the allocation. They go in the hand-off (Do 7–9).

## Start from
- Step 2: `functions` (the leaves are what you place) and `items`. An internal item is one a leaf function produces, another takes, and no external sends or receives.
- Step 3: `components` (the leaves are where you place). The alternatives you weighed there are in your step 3 hand-off, not the model; this step can send you back to them (p. 216).
- Step 1: system-wide and trade-off requirements with thresholds (the numbers to share out) and `objectives` with weights (what the allocation should serve, p. 244).

## Do
1. **Allocate** (A1141, p. 243–249). Set `runs_in` on every leaf function to exactly one leaf component. Only leaves carry it; the root belongs to the system and each first-level function to one first-level part (p. 249), so settle that pairing first, then place the leaves under it. Choose by the book's three aims (p. 244): serve the objectives (use the weights); keep interfaces few and simple, so functions that swap many items share a part and each part hides its details (p. 244, 247); and get early chances to test risky pieces, by spreading them or keeping them together. App-sized versions of the book's human/machine/hardware/software calls (p. 244–246): client or server, own code or managed service, automated or done by a person. Several functions may share a part (p. 243); no function may run in two. Treat the first allocation as a hypothesis, not final (p. 246). If two allocations are close, compare them on the objectives and say why you chose in the hand-off (p. 246–247).
2. **If the match shows an earlier step is wrong**, do not quietly edit it. A function that needs two parts is too coarse (step 2). A part with nothing to do, or a split that forces shared functions, is a step 3 problem. Propose the fix and ask first: it undoes that step's approval. Changing only `runs_in` is yours to do. Editing an existing requirement reopens step 1, so ask first too. Adding derived requirements (below) is this step's job and leaves step 1's approval alone: do it, and list the new ids in the hand-off.
3. **Internal items** (A1141, p. 251). For each internal item write two io requirements: the system produces it (`specifies` the item and the producing function) and the system takes it (the item and the consuming function). Set `derived_from` to the requirement behind the function. If the item ties to an objective, carry that range into `objective` and `threshold` (p. 255, 320). Heads-up: every derived io requirement needs a test in step 6 (R25).
4. **System-wide and technology requirements** (A1141, p. 249–252). The step 1 ones keep `specifies: [S]` (R06); S is the root of the component tree, so they reach every part (R30(a)). Where a requirement applies to only some parts, or its number must be shared out, add derived system-wide requirements that `specify` just those parts (p. 249, 320). Pick a technique (Grady, p. 251):

   | Technique | Fits | In the model |
   |---|---|---|
   | Equivalence (p. 252) | constraints, such as a required technology | nothing new: the requirement already covers every part |
   | Apportionment (p. 251) | cost, availability, reliability: split one number, same units | one system-wide requirement per part: same subcategory, `derived_from` the system one, `specifies` the part, `threshold` with its share |
   | Synthesis (p. 252) | outputs such as response time, needing a model | io requirements on the items and functions along the path; `runs_in` places them on parts |

   **Ask:** The budget for this is X. May I split it as A, B and C, keeping Y% in reserve?
   (You propose; the engineer confirms.)
5. **Trade-off requirements** (A1141, p. 252–255). Derive a per-part one only from an existing system-level one, with the same `objective`; never create a part requirement with nothing above it (p. 252). Value curves and weights have no field (p. 252–255): skip them. Leave qualification requirements to step 6 (tests).
6. **Check** and decide each finding (see Checks). List every warning or advice you leave in place, with the reason.
7. **Activation and control** (A1142, p. 255–258). Not in the schema: bring it up in the hand-off. For each leaf function, what must be present to start it and what ends it (`done_when` already holds the end, p. 256), and what must come before or after it. Then look for dynamic traps (p. 256–257): parts that wait on each other in a loop (deadlock), work that cycles without finishing (livelock), a function that never gets the resource it needs (starvation), several workers racing for the same job (surge). The item flows between parts are your first map; the model does not say which calls block, so state your assumptions.
8. **Performance and risk** (A1143, p. 258). Not in the schema: bring it up in the hand-off. For each system-wide and trade-off requirement with a threshold, say whether this allocation plausibly meets it, with rough numbers and assumptions. Name the riskiest requirements or parts and what would test them early (p. 244).
9. **Document and approve** (A1144, p. 259). The book wants the why kept, since it is rarely recoverable later (p. 259), and the model cannot hold it. Hand-off: close allocation calls, accepted warnings, splits you could not store, added requirement ids, proposed changes to steps 1–3. Subsystem specifications (A1145) come later as a separate command; do not write them here.

## Good vs bad
- Each leaf function in one leaf part (p. 243). Bad: "Create short link" half in the web service, half in the database. Good: split it in step 2 (ask first) into a function for each part.
- Shares are not equal by default and need not add up to the total; hold back a reserve of 5–10% (p. 251). Q4 is 20 USD: web service 12, database 6, 2 in reserve.
- Parts in series each need a higher number than the system (p. 252). Bad: two required parts at 99.9% each for a 99.9% target (the product is 99.8%). Good: above 99.95% each.
- Component requirements need a system-level parent (p. 252). Bad: "The database shall store 10 million links" with no requirement above it. Good: `derived_from` the requirement it serves.
- One-to-one at the top is worth having and never forced (p. 214, 249).
- Shared functions make part owners coordinate on the same inputs and outputs; give each function one owner (p. 322).

## Checks
| Rule | What it means | Usual fix |
|---|---|---|
| R14 error (p. 243) | A leaf function has no `runs_in`, a non-leaf function has one, or `runs_in` is not a leaf part | Set it to one leaf part. A function needing two: split it (step 2, ask). A part that should be split: add a leaf (step 3, ask) |
| R15 warning (p. 249) | Leaf functions under one first-level function run in more than one first-level part | Move leaves with `runs_in`, or regroup the functions (step 2, ask) |
| R16 warning (p. 243) | A leaf part has no function running in it | A function is missing (step 2, ask) or the part is not needed (step 3, ask) |
| R17 advice (p. 214) | First-level functions and parts do not map one-to-one: two functions land on one part, or a part gets none | See below |
| R30 (a) error (p. 57) | An io or system-wide requirement reaches no part: it specifies a function with no placed leaf, an item no leaf function uses, or only an external | Place the function (as R14) or point `specifies` at the function or item it is about. System-wide: `specifies: [S]` |

One wrong `runs_in` often triggers R15, R16 and R17 together. Fix the cause first.
Errors are never accepted. When to accept the rest, with the engineer's OK and a line in the hand-off:
- R15: the book wants shared functions resolved so part owners can work apart (p. 322). Prefer making the shared work its own first-level function and part (steps 2 and 3, ask). Accept only for work that is truly everywhere, such as logging, or a networked design where one-to-one is hard (p. 214).
- R16: the book offers no accept path: drop the part or revisit the functions (p. 243). If the engineer insists on keeping the part, say why in the hand-off.
- R17: it may not always be possible and should not be forced (p. 214). Two functions on one part is fine (p. 243), but ask whether they are really one function. Accept when forcing one-to-one would split a natural part or invent a function. A first-level part with no function is R16 at the top: fix it.

No judgment item starts at step 4.

## Example
Starts from `tests/fixtures/valid.yaml`, which already has these `runs_in` values. The five requirements are new:
```yaml
functions:
  - {id: F11, name: Create short link, parent: F1, inputs: [I1], outputs: [I2, I5], done_when: Short link returned, runs_in: C11}
  - {id: F12, name: Redirect visitor, parent: F1, inputs: [I3, I6], outputs: [I4], done_when: Visitor redirected, runs_in: C12}
  - {id: F2, name: Store links, parent: F0, inputs: [I5], outputs: [I6], done_when: Link persisted, runs_in: C2}
requirements:   # new entries, added to the existing list
  # I5 (Link record) is internal: F11 makes it, F2 takes it
  - {id: Q5, text: The system shall produce a link record for each short link created., category: io, subcategory: output, stage: release, derived_from: [Q1], specifies: [I5, F11]}
  - {id: Q6, text: The system shall accept a link record for storage., category: io, subcategory: input, stage: release, derived_from: [Q1], specifies: [I5, F2]}
  # Q4 (20 USD a month) shared out: 12 + 6, 2 held back
  - {id: Q7, text: The web service shall cost less than 12 USD per month to run., category: system-wide, subcategory: cost, stage: release, derived_from: [Q4], objective: O1, specifies: [C1]}
  - {id: Q8, text: The database shall cost less than 6 USD per month to run., category: system-wide, subcategory: cost, stage: release, derived_from: [Q4], objective: O1, specifies: [C2]}
  # Q3 (99.9%) shared out: two parts in series
  - {id: Q9, text: The database shall be available 99.97% of each month., category: system-wide, subcategory: quality, stage: release, derived_from: [Q3], specifies: [C2], threshold: 99.97% monthly availability}
```
Hand-off notes for the same model (not stored):
```
Control: C1 calls C2 (sends I5, gets I6 back); C2 never calls C1, so there is no wait loop.
Risk: Q3 (99.9%): C1 at 99.95% and C2 at 99.97% (Q9), in series, give 99.92%. C2 is the hard number, so test it early.
```
