# Step 2 · Functions: What does it do, step by step?

Open the black box from step 1: one tree of jobs (functions, p. 178), the items that flow between them, and a trace from each input/output requirement to the jobs and items it is about. Step 3 builds parts to match this tree and step 4 gives each leaf job to one part, so a gap or overlap here becomes rework there. The book expects this tree to be revised after step 4 (p. 183): aim for a sound first version, not a perfect one. Book: Ch 7, activity A112 (p. 181).

## Fills in
- `functions` (functional decomposition, p. 179): `id`, `name`, `parent`. One function has no parent (the system function, p. 51); the rest hang under it. A leaf has no children.
- `functions[].inputs` / `outputs` (inputs and outputs, p. 178): item ids. Fill them on leaves; the checks read only leaves, so on parents they are optional.
- `functions[].done_when` (completion criterion for an exit, pp. 58, 178): when a leaf function is finished.
- `items` (items and data model, pp. 53, 181): `id`, `name`, and optionally `description`. Step 1 made the boundary items; you add the internal ones.
- `items[].description` (data model, p. 181): what the item holds: its fields, format and limits, with one example. The build spec prints it. Write one for every item that carries data.
- `requirements[].specifies` (traced to, p. 59): on io requirements, the functions and items they are about.
- Do not set `runs_in`; that is step 4.
- If requirements exist for the build stage, write jobs for them.
- The model cannot hold these, so write them to `decisions.md` under this step's heading: simple functionalities, alternative decompositions, relations between items, operating modes and states, deferred error-handling functions. It has no control or trigger link either: list those items under `inputs` and name them so the role shows (`Redirect request`, `Rate-limit setting`; p. 53).

## Start from
- Read from step 1: `scenarios` (steps), `external` (`sends`/`receives`), the boundary `items`, and io `requirements` (input, output, external-interface, functional).
- Read the `### For step 2` notes in `decisions.md` (work earlier steps deferred to this one).
- Functional requirements are the book's first-level functions (pp. 141, 317). Start the top split from them. Changing the first level means changing them too, which is a step 1 edit: say so.

## Do
1. **Simple functionalities (A1121, pp. 179-181).** For each scenario write the chain one input follows to one output: external input, function, item, function, ... external output (p. 179). Many small chains with plain verb-object names; they are low-level functions (p. 182). They are working notes (no field); do not edit `scenarios`. Use them to find functions now and to test the draft in 3. Put one chain per scenario in `decisions.md`.
2. **Draft the tree and wire the flows (A1122, pp. 181-185, 200-202).**
   - Root: one function, the system's whole job, named from `system.purpose`. It stands for everything the system takes in and gives out (p. 51).
   - First level: 2 to 7 functions (p. 141), from the functional requirements. Split by one of these keys (pp. 183-185): operating modes (if the app has any), outputs, inputs, stimulus-response threads (the book's preferred key), or the six generic jobs (p. 184): user interface, validate and format inputs, core transform, control processing, format outputs, maintenance and self-test (health checks, logging, backup). The system's objectives can guide the split too (p. 185).
   - Method: top-down for a variation of something that exists, bottom-up from the chains for something new, usually a mix (pp. 182-183). **Ask:** Is this a new kind of app or a variation of one that already exists?
   - Prefer pieces that could each live in one major part (service, database, UI; pp. 182, 202), since step 4 gives every leaf to exactly one part (p. 249).
   - Go two to four levels deep (p. 202). Split a function only where more detail helps (p. 182). Keep housekeeping (logging, backup) apart from the main jobs at lower levels (p. 185).
   - Wire each leaf: boundary items go to the leaf that takes or gives them; add internal items for what leaves pass to each other (p. 181). Do not trivialize how siblings interact: build the flows from many simple functionalities, with the feedback they need (p. 201).
   - Propose the first-level split (propose it; the engineer confirms in review).
3. **Evaluate the draft (A1122, pp. 192-193, 201).**
   - Walk each scenario chain through the tree (p. 193): start at its first external input, follow the item into the leaf that takes it, pick the output that leads on, and repeat until the scenario's external output. A break is a shortfall (missing function or flow).
   - Look for shortfalls (no function for some input; an output nobody produces; no feedback; pp. 192-193) and overlaps (two functions doing one job; p. 193).
   - For each leaf list the unwanted inputs (malformed, too large, duplicate, unauthorized, dependency down; p. 192) and check something answers each. Add a function and an output item (for example `Error response`) where nothing does. **Ask:** For `<unwanted input>`, should the app reject it, ignore it, retry, or alert someone?
   - Feedback (pp. 189-190, 193): for each key output, name the item that shows whether it worked (acknowledgement, error, status).
   - Go through Sidebar 7.2 (p. 201); see Good vs bad. Try one alternative split and keep the better (pp. 200-201); list the alternative in `decisions.md`.
4. **Data model (A1123, pp. 181, 202).** The items are the data model. Review the item list for missing or redundant items (p. 200). Name items with nouns (p. 201). Every item comes from an external or a leaf and goes to an external or a leaf. The model keeps no relations, but sketching them often exposes design issues the function view hid (p. 202): put what you find in `decisions.md`. Put each item's fields, format and limits in its `description`. **Ask:** when a business rule appears: can one long URL have several short codes? Do codes expire? Business rules a job follows (how codes are made, uniqueness, expiry, what repeats do) are decisions about behaviour: write each as an io requirement, so it reaches the spec and gets a test.
5. **Complete the models (A1124, pp. 178, 181, 201-205).**
   - `done_when` on every leaf: the observable result that ends it (exit criterion, p. 178). Name each way it can end (`Short link returned; or error response returned`). A time or size limit belongs in an io requirement (Table 6.2, p. 140). Propose each one (propose it; the engineer confirms in review).
   - External match (R10): every item an external `sends` is an input of some leaf; every item it `receives` is an output of some leaf. Fix the function wiring first; change `external` only if step 1 was wrong, and say so. The converse (R10): every input of a leaf is given by another leaf or sent by an external, and every output of a leaf is taken by another leaf or received by an external. Settings and secrets a part needs (an API token, a base URL) are items sent by whoever owns them: the outside system that issues them (the chat service issues the bot token) or the person who runs the app (an operator). Never by a host or deploy tool: that is a step 3 choice.
   - Error handling (pp. 202-205): add input error trapping now (check type and range, tell the user, ask again). Error detection, damage confinement, recovery and fault reporting depend on the parts (p. 202): add what you can, list what you deferred in `decisions.md` under `### For step 4` (or the step that will do it).
   - Review (pp. 181, 201): the book has other engineers and stakeholders critique the draft for missing functions and other splits. Hand the engineer the tree, the scenario chains and the alternative split.
6. **Trace io requirements (A1125, pp. 182, 205-207).** Set `specifies` on each leaf requirement:
   - input or output: the item and the leaf that receives or produces it (pp. 59, 205). Every item you list must be one that a listed leaf takes or gives (R05). The book also traces to every ancestor of that leaf; the tree already implies them, so do not list them.
   - external-interface: the items the interface carries and the leaf that receives or sends them (p. 205).
   - functional: the first-level function, or the root (pp. 59, 205).
   - Exit test (pp. 177, 207): every io requirement has a function and an item (functional ones, a function); every leaf touching an external item has a requirement; every external item has one. Internal items get theirs later (pp. 206, 249).
   - A requirement that fits no single function, or a gap, can mean the tree is wrong (p. 182): go back to 2. **Ask:** `X` flows in but no requirement says what the app must do with it; what must it do? You may draft the requirement for confirmation; it needs `category`, `subcategory`, `stage` and a `source`. A new or changed requirement is a step 1 edit: step 1 needs review again.

## Good vs bad
- Name = verb + object, no goal word (p. 201): `Maximize redirect speed` -> `Redirect visitor`. Items are nouns: `Create link` -> `Link record`.
- Partition (p. 102; R12): each thing the parent does belongs to one child, none left out; siblings sit at one level (p. 201); a function is never its own child.
  Bad: root children [`Create short link`, `Query the database`, `Redirect visitor`], where the query is a step inside the other two. Good: [`Handle requests`, `Store links`], with the database work under `Store links`.
- Bad: F2 gives I6 Stored target with nothing going in. Good: a job that looks data up takes an item that carries the key (I3 Short code).
- Gap: Q2 limits URLs to 2000 characters but nothing returns an error for a longer one (pp. 192-193): add a function or output.
- Model the system, not the externals (p. 201): `Visitor clicks link` is the visitor's job; the system's is `Redirect visitor`.
- Conserve (pp. 182, 201): the leaves together take from outside exactly what the system takes and give exactly what it gives; none added, none dropped.
- No output from thin air (p. 201): a `Monitor health` function needs an input item about the functions it watches. R10 flags an input that no leaf gives and no external sends.
- 2 to 7 first-level functions (p. 141); keep every node's children few enough to read (p. 183).
- Every key output has feedback (p. 193).

## Checks
| Rule | Means | Usual fix |
|---|---|---|
| R05 error (p. 59) | input/output/external-interface requirement specifies no item or no leaf function, or an item that none of the leaf functions it specifies takes or gives | add the item and the leaf that takes or gives it; add the function if none does; drop an item the leaf does not move |
| R07 error (p. 59) | functional requirement does not specify the root or a first-level function | point `specifies` at the matching first-level function; if none matches, the split is missing one |
| R08 warning (p. 141) | root has fewer than 2 or more than 7 children | above 7, group related functions under a new one; below 2, decompose the root |
| R09 error (p. 51) | not exactly one function without a parent | give each stray function a parent, or add the missing root |
| R10 error (p. 51) | an external sends/receives an item no leaf takes/gives, or a leaf takes/gives an item that no leaf gives/takes and no external sends/receives | wire the item into a leaf, or add the function that produces or uses it; correct `external` only if step 1 was wrong |
| R20 warning (p. 58) | leaf has no `done_when` | state when it is finished |
| C01 warning (p. 59) | an item an outside system sends or receives is specified by no io requirement | add an io requirement for it (6), or add the item to one that is about it |

Earlier rules also apply: S03 (references resolve: `parent` to a function, `inputs`/`outputs` to items) and R11 (no `parent` or `derived_from` loops).

A person signs off: **R12** (p. 102), each function's subfunctions partition its behavior, no overlaps, no gaps. Give the engineer the scenario chains from 1 and 3 to judge it.

## Example
```yaml
items:                      # I1-I4 came from step 1; I5-I6 are internal
  - {id: I1, name: Long URL, description: "The URL to shorten: an absolute http or https URL, 1 to 2000 characters. Example: https://example.com/spring-sale?utm=mail"}
  - {id: I2, name: Short link}
  - {id: I3, name: Short code, description: "The key of a link: 6 characters from a-z and 0-9, unique. Example: k3x9qa"}
  - {id: I4, name: Redirect}
  - {id: I5, name: Link record}
  - {id: I6, name: Stored target}
functions:                  # no runs_in: step 4
  - {id: F0, name: Shorten and redirect}
  - {id: F1, name: Handle requests, parent: F0}
  - {id: F11, name: Create short link, parent: F1, inputs: [I1], outputs: [I2, I5], done_when: Short link returned}
  - {id: F12, name: Redirect visitor, parent: F1, inputs: [I3, I6], outputs: [I4], done_when: Visitor redirected}
  - {id: F2, name: Store links, parent: F0, inputs: [I5], outputs: [I6], done_when: Link persisted}
requirements:               # step 1 fields as before; only specifies is new
  - id: Q1                  # functional -> first-level function, and an outside item it gives (C01)
    text: The system shall create a short link for a submitted long URL.
    category: io
    subcategory: functional
    stage: release
    parent: Q0
    source: SRC1
    specifies: [F1, I2]
  - id: Q2                  # input -> item and the leaf that takes it
    text: The system shall accept a long URL of up to 2000 characters.
    category: io
    subcategory: input
    stage: release
    parent: Q0
    source: SRC1
    specifies: [I1, F11]
  # Q5 in valid.yaml does the same for I3 and I4
```
