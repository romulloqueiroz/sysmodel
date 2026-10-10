# Step 1 · Problem: Who uses it, and what must it do?

Fix the design problem: how the app is used (scenarios), where it stops and what crosses that line, what stakeholders value, and the requirements every later step must meet or trace to. Step 2 builds functions from these items and requirements; step 6 tests them. A vague or untraced requirement here becomes rework in every later step. Book: Ch 6, activity A111 (p. 135); Ch 12 does it for a soda machine (pp. 310-316).

## Fills in
- `stages` (life-cycle phases, p. 137): keep the default `[build, release]`.
- `system.purpose` (vision, p. 146): one sentence, what the app is, in general terms, no technology.
- `stakeholders` (p. 132): each group with a stake.
- `sources` (documents or statements requirements trace to, p. 145): `title`, and `stakeholder` for who said it.
- `scenarios` (operational concept, p. 146): `name` and `steps`; each step is one exchange between the system and an outside party.
- `external` (external systems, p. 133): `kind` is `external`, `enabling` or `context`; `sends` and `receives` list item ids.
- `items` (inputs and outputs of the system, p. 151): only what crosses the boundary. Step 2 adds internal items.
- `objectives` (objectives hierarchy, p. 154): `name`, `parent`, `weight` (0 to 1).
- `requirements` (p. 137): `category`, `subcategory`, `stage`, `source`, `threshold`, `objective`, `parent` (for groups), `specifies` (system-wide ones only now).
- The model cannot hold these, so put them in the hand-off message: the reason behind each requirement (p. 163), objective value ranges and value curves (p. 156), the feasibility argument (A1115), and every number you proposed that the engineer did not give.

## Start from
- The model has nothing yet. Read the engineer's brief, README, issues, API routes or OpenAPI file, deploy config, and any running app: existing systems shape the requirements (p. 134).
- If the file already has content (a sent-back pass), read all of it and the review note. Edit; do not overwrite.
- Work at system level: the whole app is a black box. No parts, no internals (p. 134).

## Do
1. **Stakeholders and sources** (the stakeholder inputs that feed A1111-A1114, Fig 6.3 p. 135; pp. 132, 145)
   - Propose `stakeholders` from the brief and repo. Think past "user": payer, developer, tester, deployer, operator on call, maintainer, support, anyone harmed by a failure (p. 132). Each sees the system differently; leaving one out makes the app look like a failure from that view.
   - **Ask:** Who uses this app, who pays for it, who builds and runs it, and who is hurt if it fails?
   - Add a `sources` entry for each document or talk the requirements come from (brief, ticket, interview, policy, contract).
   - **Ask:** Which documents or conversations say what you need? With none, record the engineer's answers, dated, as the source (a statement counts, p. 145).
   - Never cite a source nobody gave. R21 only checks that a source id exists.
2. **Operational concept** (A1111, pp. 136, 146-151)
   - Set `system.purpose`. **Ask:** In a sentence or two, what problem does this solve, and for whom? State it without a solution, and check it is the right level, not too big or small (pp. 132-133).
   - Write `scenarios`: one or more per stakeholder group, for build as well as release (p. 148). Black box: each step is one exchange, who sends what to whom, in time order (pp. 148, 151). Never say how the app processes it. Use the same words you will use for externals and items (R19 compares them, and `spec` finds each part's scenarios by the item names).
   - Order (p. 149): the main user's simple scenarios, then other stakeholders, then add failures, extremes and constraints. Cover the usual kinds: first deploy, normal use, peak load, upgrade and maintenance, other systems failing, the app failing and degrading, shutdown, retirement. The book counts 25 to 50 for a simple system: expect more than a handful.
   - The agent proposes from the repo; the engineer confirms. **Ask:** Walk me through the most important use: what does the person give the app, and what do they get back? Which failures matter most?
   - Mission measures (what stakeholders need to achieve with the app, pp. 148, 151) become the top objectives in 4.
3. **System boundary** (A1112, pp. 133-134, 151-152)
   - Inside is open to change; outside is fixed and produces the constraint requirements (p. 151). **Ask:** Which of these can you change and which are fixed (third-party APIs, the host, the browser)?
   - Add an `external` for each outside party in the scenarios. `external`: exchanges items both ways (browser, payment API, partner service). `enabling`: supports building and shipping, not running (CI pipeline, package registry, test environment; p. 43). `context`: can affect the app, which cannot affect it (law, browser standards, traffic patterns; p. 134).
   - Add one `item` per distinct thing crossing the boundary (data, event, file, request), named as in the scenarios. `sends` = items it gives the app; `receives` = items the app gives it. A context only sends (R18).
   - Validity (p. 152): every output of the app goes to some external. An `external` that receives nothing from the app is really context.
   - For each external ask "only sends? only receives? does that make sense?" A gap often means a missing scenario (p. 311).
   - If you merge items to keep it readable, remember each detailed input/output still needs its own requirement (p. 312).
   - Step 2 matches every sent or received item to a function (R10), so list no item the app does not use.
4. **Objectives hierarchy** (A1113, pp. 152-156)
   - An objective is something stakeholders value enough to pay for: more of it, or less cost (p. 154). Root = overall value; children are its natural parts. Usually 2 to 5 levels; do not decompose too far (pp. 154, 156). Leaves are measurable (response time, availability, monthly cost).
   - Drop means objectives (how: "use serverless", "add a cache") and strategic ones the app cannot settle ("grow brand awareness"). If one objective matters only because it improves another, it is a means (p. 154).
   - `weight` says how much a swing from an objective's worst acceptable to best likely value matters among its siblings (p. 156). The book's sibling weights add to 1 (p. 155). Weights are the stakeholders' values, not the engineer's guess (p. 156).
   - **Ask:** first what the app must be good at: offer the objectives you drafted, and let the engineer add or drop. Then: If you could improve only one of these, from the worst value you would accept to the best you expect, which first? How do you rank the rest?
   - The value range per leaf has no field: its worst value goes in a linked requirement's `threshold`, its best as the design goal in that requirement's text; value curves go in the hand-off.
   - Each leaf objective should be the `objective` of at least one requirement (Fig 6.4, p. 143).
5. **Requirements** (A1114, pp. 137-146, 158-163)
   - Topics come from the scenarios, the externals and items, and the objectives (pp. 134, 159). Keep them at system level, not metasystem or parts (p. 134).
   - **io**: `input` (one or more per input), `output` (one or more per output), `external-interface` (limits an outside party puts on how inputs arrive or outputs leave: protocol, format, auth, rate limit; pp. 140, 160), `functional` (the two to seven first-level jobs, not a feature list; features show up as inputs and outputs, p. 141; step 2 turns them into functions, p. 317). For each item think quality, quantity, timing (Table 6.2, p. 140) and out-of-range inputs with the response. For each context element (load peaks, bad networks) ask which variations the app must handle and whether it must protect itself (p. 160). Put the item's name in the text; step 2 links it (R05, R07).
   - **system-wide**: `technology` (a mandated tool or platform; engineers prefer none, so give the reason, p. 161), `quality` (availability, reliability, security, usability, maintainability, testability; laws such as accessibility or privacy go here, p. 161), `cost`, `schedule` (nearly always one of each per stage, p. 161). Set `specifies` to the system id (R06).
   - **trade-off**: `performance`, `cost`, `cost-performance` say how to compare two designs, from the objective weights (pp. 141, 161). Set `objective`. Weights and preferences come from stakeholders (R28).
   - **qualification**: see 7.
   - Every leaf has `category`, `subcategory`, `stage`, a `source`, and "shall" in its text. Stage is the system the requirement is about: `build` = making the app (code, CI, tests), `release` = the app shipped and in use. Almost every requirement is `release`; `build` is for how the app is made (for example, CI time). If unsure, ask once and keep that rule.
   - A requirement with children is a group: `id` and `text` only, no tests, no `specifies` (R04, p. 50). Use groups to organise by category.
   - `source` points to a `sources` id, not a stakeholder: every requirement here traces to what a stakeholder said (p. 145). Leave `derived_from` empty; it is for requirements step 4 derives for the parts, and step 1's approval does not cover them.
   - Put every number in `threshold` with units (the worst acceptable value, p. 138), and the better value in the text as "The design goal is ..." (p. 146).
   - **Ask:** What is the worst value of X you would still accept, and beyond what value would you stop caring? What is the monthly running cost ceiling? When must the first release ship? Is any technology mandatory, and why?
   - Never write TBD or TBR (R24). If the engineer says "you pick", write your value and list it in the hand-off as unconfirmed.
   - Numbers that depend on real users (task time, error rate) come from a prototype and usability test with the app's actual users (pp. 158-159, Table 6.5). You cannot run one: draft a storyboard and mark those numbers as proposed in the hand-off.
6. **Feasibility** (A1115, pp. 134, 136, 164)
   - Show that at least one design can meet all requirements together within the cost and date. Requirements that look fine alone often conflict (the book finds 5 to 20 unmet late, p. 134).
   - Check pairs with rough numbers (provider prices, typical latency, effort): cost ceiling vs availability or speed, deadline vs scope, mandated technology vs a quality target.
   - A conflict goes back to 5, not forward (p. 135). **Ask:** These cannot both hold: X against Y. Which do you relax?
   - Do not over-constrain: leave room for several designs (p. 132). Put the feasibility argument in the hand-off, one line per tight requirement.
7. **Qualification requirements** (A1116, pp. 137, 142, 162-163; step 6 builds the tests)
   - Write at least one `category: qualification` requirement per kind: `observance` (what data is collected for each io and system-wide requirement, and where: logs, probes, test runs), `verification-plan` (how the data shows the build meets the requirements), `validation-plan` (how it shows the app meets stakeholders' needs), `acceptance-plan` (what the stakeholders accept as proof).
   - The book treats the acceptance plan as the true exit: once stakeholders approve it, the rest is presumed defined well enough (p. 130). **Ask:** What would you need to see to say "yes, ship it"?
   - Name tooling the plan needs (staging site, load generator) in the text. If it sits outside the app, add it as an `enabling` external.
8. **Approval** (A1117, pp. 135, 137). The engineer decides. Issues stakeholders raise go back to the scenarios and the boundary first (Fig 6.3, p. 135), so expect to edit those.

## Good vs bad
- Scenarios are black-box exchanges, not processing (p. 148). Boundary items match the scenario words (R19, p. 48).
- Objectives are values stakeholders would pay for, not means or far-off goals (p. 154); weights come from them (p. 156).
- A requirement is: subject, "shall", relation, threshold with units (p. 145). "Will" states a fact, "should" a goal (p. 145).
- One predicate each: "shall fit, weigh, cost" breaks traceability (p. 146). No negatives: say what it shall do. No "and/or". No leading "If": put conditions last. No "maximize", "minimize", "accommodate", "easy", "robust", "rapid", "user-friendly" (p. 146).
- Say what and how well, not how: design independent (pp. 145, 160); not too strategic and not a means (p. 138). A requirement lives in one category only (p. 139).
- Verifiable: a finite, affordable check exists (p. 145). Unique, consistent, attainable, no TBD/TBR (p. 145).
- Bad: "The system shall be fast, reliable and use Redis." Good: "The system shall redirect a visitor within 200 ms for 99% of requests." (threshold `200 ms at the 99th percentile`; availability is its own requirement; Redis waits for step 3; tail form p. 148).
- Bad: "The system shall not crash on bad input." Good: "The system shall answer a submitted URL that is not a valid http or https address with an error response."
- Bad objective: "Use serverless functions" (a means). Good: "Low running cost".

## Checks
| Rule | What it means | Usual fix |
|---|---|---|
| S01 | file matches `schema.json` | use schema fields and values only; `weight` is 0 to 1; `steps` has at least one entry |
| S02 | ids unique in the whole file | rename; prefix by kind (SH, SRC, O, SC, E, I, Q) |
| S03 | references point at the right kind (`source` -> a source, `objective` -> an objective, `sends` -> items, `parent` -> same kind) | fix the id or add the missing entry |
| R01 (p. 139) | each leaf requirement has a `category` | set one of the four; a requirement with children is a group |
| R02 (p. 140) | `subcategory` belongs to the category | io: input, output, external-interface, functional. system-wide: technology, quality, cost, schedule. trade-off: performance, cost, cost-performance. qualification: observance, verification-plan, validation-plan, acceptance-plan |
| R03 (p. 143) | each leaf has a `stage` in `stages` | set `build` or `release` |
| R04 (p. 50) | a group is not tested and specifies nothing | move `specifies` to its children |
| R06 (p. 59) | a system-wide requirement specifies only the system | `specifies: [S]` |
| R11 (p. 100) | no `parent` loops | break the loop |
| R18 (p. 43) | a `context` receives nothing | if the app gives it items, make it `external`; else drop `receives` |
| R21 (p. 145) | each leaf has a `source` or `derived_from` | add a source (ask) |
| R23 (p. 138) | a system-wide `quality` requirement has a `threshold` | add the number with units |
| R24 (p. 145) | no TBD or TBR in `text` or `threshold` | ask for the value |
| R26 (p. 145), warning | `text` contains "shall" | rewrite as a requirement |

R05 and R07 (step 2) need io `specifies`; R25 (step 6) needs a test per io and system-wide requirement, so write each so a test can pass or fail.

A person signs off:
- R19 (p. 48): the externals and items match the scenarios.
- R27 (p. 58): each requirement is one testable statement: subject, shall, relation, threshold with units; no "and/or", no negatives.
- R28 (p. 141): trade-off requirements reflect stakeholder preferences (objectives).

## Example
```yaml
stakeholders: [{id: SH1, name: Marketing team}]
sources: [{id: SRC1, title: Marketing interview, stakeholder: SH1}]
objectives:
  - {id: O0, name: Good value for marketing}
  - {id: O1, name: Low running cost, parent: O0, weight: 0.4}
  - {id: O2, name: Fast redirects, parent: O0, weight: 0.6}
scenarios:
  - id: SC1
    name: Visitor follows a short link
    steps: ["Web visitor sends Short code", "System sends Redirect to Web visitor"]
  - id: SC2
    name: Visitor follows an unknown short link
    steps: ["Web visitor sends Short code", "System sends Not found notice to Web visitor"]
external:
  - {id: E1, name: Web visitor, kind: external, sends: [I1, I3], receives: [I2, I4, I7]}
  - {id: E2, name: Build pipeline, kind: enabling}
  - {id: E3, name: Data protection law, kind: context}
items: [{id: I3, name: Short code}, {id: I4, name: Redirect}, {id: I7, name: Not found notice}]   # I1, I2 as in valid.yaml
requirements:
  - {id: Q0, text: Input and output requirements}
  - {id: Q5, text: The system shall redirect a visitor within 200 ms for 99% of requests., category: io, subcategory: output, stage: release, parent: Q0, source: SRC1, threshold: 200 ms at the 99th percentile, objective: O2}
  - {id: Q3, text: The system shall be available 99.9% of each month., category: system-wide, subcategory: quality, stage: release, source: SRC1, specifies: [S], threshold: 99.9% monthly availability}
  - {id: Q6, text: The system shall cost 20 USD per month or less to run. The design goal is 10 USD., category: system-wide, subcategory: cost, stage: release, source: SRC1, specifies: [S], threshold: 20 USD per month, objective: O1}
  - {id: Q7, text: The system shall be compared with other designs using weight 0.4 on running cost and 0.6 on redirect speed., category: trade-off, subcategory: cost-performance, stage: release, source: SRC1, objective: O0}
  - {id: Q8, text: The system shall be accepted when marketing completes scenarios SC1 and SC2 on the staging site with no failures., category: qualification, subcategory: acceptance-plan, stage: build, source: SRC1}
```
