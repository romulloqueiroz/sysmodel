# Step 3 · Parts: What is it made of?

Decide the parts the app is built from: a tree of components (p. 210) from the system down to the smallest pieces someone builds and tests (configuration items, p. 210). Step 4 puts every leaf function into one leaf part and step 5 connects the parts, so this tree fixes who owns what and where the seams are. Book: Ch 8, activities A1131–A1133 (p. 215).

## Fills in
- `components[]` (physical architecture, p. 210): one entry per part: `id`, `name`, `parent`, `choice`.
- `parent` (decomposition, p. 210): the system id for first-level parts, a component id below. A component that nobody names as `parent` is a leaf (a configuration item).
- `choice`: the option the chosen alternative uses for that part (a product, language or service, such as SQLite), so the build spec can say what to build it with. `name` stays the role. Leave it out where no option was picked.
- Nothing else. The generic architecture, the morphological box, the alternatives and the reason for the pick have no field. They go in `decisions.md` (Do 7).

## Start from
- Step 2: `functions`. Every leaf function needs a home (p. 211); the first-level functions guide the first-level parts (p. 214).
- Step 1: `objectives` and their weights, the system-wide and trade-off requirements with their thresholds, `external`, `stages`. These are what you judge alternatives against (p. 214).
- Step 1 `decisions.md`: the feasibility risks.
- Read the `### For step 3` notes in `decisions.md` (work earlier steps deferred to this one).
- Technology requirements already in the model fix some choices. Read them before brainstorming.

## Do
1. **Settle the overall style first** (A1131, p. 219, 225–229). A morphological box only works inside one system concept, so choose the big shape before filling it: one deployable or several services, client-server, serverless, centralized or spread out. Centralized is easier to design and test but is a single point of failure and a bottleneck (p. 225, 227).
   **Ask:** Is anything already decided or off-limits: language, host, database, vendor, an existing service to reuse? (Each answer turns a column of the box into a fixed choice, p. 218.)
2. **Generic architecture** (A1131, p. 211–214). List the parts in general terms: role names, no products, no numbers (p. 213). Work top-down, one level at a time, alongside step 2 (p. 214). Aim for one first-level part per first-level function, each a chunk one person or team can build on its own (p. 214). Give every leaf function a home, including build- and release-stage work (p. 211), and include parts that are not code when a function needs them, such as an operating runbook or user guide (p. 213). A host is a `choice` on the part it runs, not a part of its own, unless a job needs it. A similar app's parts are a good memory jogger; check they fit before trusting them (p. 221). Think hard here: some alternatives die on the split alone (p. 214).
   If the functions will not split into clean parts, regroup the functions. That edits step 2: propose it and ask first.
3. **Morphological box** (A1132, p. 214, 217–219). One column per generic part at the level you are working. Fill each column with two or more concrete options that have known cost and speed traits (p. 214, 218). Write more options than you will use (p. 216). Ways to find options: analogy, take a working design and vary one attribute, or take one key requirement and list options for it (p. 221–222). A column for optional extras may allow several picks at once (p. 218). Mark pairs of options that cannot work together (p. 219). State only enough (size, cost, speed class) to judge the requirements; do not design a part's insides (p. 210).
4. **Choose** (A1133, p. 214, 217, 223, 225). One option from each column is an alternative; make each one a theme built on some objectives, such as cheapest to run, fastest, easiest to use (p. 217). Build a few with different themes, not one. Then scan the box for combinations nobody listed (the book's case study found two this way, p. 225). Compare on the book's four issues: functional performance, availability and fault tolerance, room to grow, cost (p. 223). Score against the `objectives` weights and the thresholds in the requirements. Drop any alternative that breaks a threshold.
   If an availability requirement exists and one part everything depends on is a single point of failure, say how you handled it (p. 227, 231, 236). A standby or replica adds parts and usually functions such as detect failure and switch over (p. 231, 233): that edits step 2, so propose and ask first.
   **Ask:** (only if the weights do not settle it) When cost, speed and availability conflict, which wins here?
   The pick is provisional: step 4 may send you back here (p. 216). Propose the pick (propose it; the engineer confirms in review).
5. **Write the tree** (p. 210, 214). Put the chosen alternative's parts in `components`. `name` is the role ("Database"); put the chosen alternative's option for that part in `choice` ("SQLite"). If the engineer wants a product to be binding, that is a technology requirement, which edits step 1: propose it and ask first. Go down only as far as the leaf functions need: step 4 warns about a leaf part that no function runs in.
6. **Check the partition** (R13, p. 102). For each level, write one line per part saying what it owns. No two parts may own the same thing (overlap) and nothing the app must do may be owned by none (gap). Fix both before the hand-off.
7. **Decisions content.** The model keeps only the pick, so write to `decisions.md` under this step's heading: the generic parts, the box (columns and options), the alternatives with their themes, how each did on the four issues, the combinations you ruled out, the pick and why it beat the others, and any step 1 or 2 change you propose.

## Good vs bad
- Generic first, instances second (p. 211, 213). Bad: parts named `Redis`, `Express`, `Vercel`. Good: `name: Cache, choice: Redis`, `name: Web service, choice: Express on Vercel`; the products are options in the box, and the pick goes in `choice`. A host is part of the choice of the part it runs.
- Every column has two or more real options; a column with one is a decision already made (p. 218). Say which ones are fixed.
- Never compare one or two designs only (p. 217). Make many options first, prune later (p. 216).
- One box per system concept; do not mix options from different styles in one box (p. 219).
- One part per first-level function where you can; easier at the top than the bottom, never forced (p. 214). Networked designs may need bottom-up thinking, but then walk the functions top-down so nothing is left out (p. 214).
- Prefer simple, independent, self-contained parts (p. 230).
- Watch for one part that every other part depends on (p. 227, 236).
- Analogies are the most useful idea source and can mislead if unchecked (p. 221).
- State representative instances, not detailed designs (p. 210).

## Checks
No `sysmodel check` rule starts at step 3. Earlier rules still catch slips here: S02 (duplicate id), S03 (`parent` must be the system id or another component), R11 (a parent chain that loops).
Step 4 will later warn R16 (leaf part with no function) and advise R17 (first-level parts and functions not one-to-one). Build the tree with those in mind.

A person signs off: R13 (p. 102), the component breakdown is a partition.

## Example
`decisions.md` sketch for the URL shortener (not stored in the model):
```
Box:  Web service        | Datastore         | Hosting
      one server process | file database     | one virtual machine
      serverless funcs   | managed key-value | serverless platform
      container service  | managed Postgres  | container platform
A  cheapest: process + file database + one VM. One VM is a single point of failure against Q3.
B  pay-per-use: functions + key-value + serverless. Fits O1/Q4 and Q3 best on rough estimates.
Ruled out: serverless functions + file database (no shared disk).
Pick: B.
```
What lands in the model (matches `tests/fixtures/valid.yaml`):
```yaml
components:
  - {id: C1, name: Web service, parent: S, choice: Serverless functions}
  - {id: C11, name: Shorten endpoint, parent: C1}
  - {id: C12, name: Redirect endpoint, parent: C1}
  - {id: C2, name: Database, parent: S, choice: Managed key-value}
```
