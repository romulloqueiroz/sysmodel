# Step 5 · Interfaces: How do the parts connect?

Decides every connection an item crosses, between two parts or between a part (or the whole system) and an outside system, and what each one carries. The book calls interfaces the most common failure point of a system and the engineer's own job (pp. 266, 281). Step 6 tests what you connect here. Book: Ch 10, activity A115 (pp. 241, 280).

## Fills in
- `interfaces` (interface, pp. 266-267): `id`, `name`. Name the mechanism or standard it uses ("Public HTTP", "SQL over TCP"), not "API" or "link". Use `name` for the physical choice (A115.4).
- `between` (external or internal interface, p. 267): exactly two ids. Each is a component, the system, or an external system. At least one must be the system or a component (R29). The ends decide the kind: an `external` end makes it an external interface. Two ends that talk over two mechanisms get two interfaces.
- `carries` (items to be transported by the interface, p. 280): at least one item; every item that crosses this connection, either direction. Direction is already in the jobs' `inputs` and `outputs`.
- `requirements[].specifies` (p. 59): a requirement may name an interface it constrains, as well as the items and leaf job it already names. Step 5 approves these links.
- Step 5 writes `interfaces` and these links only. The model cannot hold the rest, so write them to `decisions.md` under this step's heading: candidate architectures and why one won, fault analysis, speed estimates, any custom design.
- Externals, items, jobs, parts and requirements belong to steps 1-4. Editing them makes those approvals stale, so where this guide says "propose and ask first", the engineer must agree before you write it.

## Start from
- Step 1: `external` (`sends`/`receives`), `items`, `external-interface` requirements, performance requirements and their `threshold`s, `objectives`.
- Read the `### For step 5` notes in `decisions.md` (work earlier steps deferred to this one).
- Step 2: each leaf job's `inputs` and `outputs`. Step 4: `runs_in`. Together they fix every flow: item X leaves part A and enters part B or an outside system. Step 2 may have deferred error-handling jobs (pp. 202-205); they are under `### For step 5` or `### For step 4` in step 2's section of `decisions.md`.
- Run `sysmodel check --step 5` before writing anything. Each R30(b) finding is one flow, `producer -> consumer`, with the item named. Group the findings by pair of ends: each pair is a candidate interface.

## Do
1. **Define interface requirements (A115.1, p. 280).**
   - Items (A115.1.1): from the grouped findings, list what each connection must carry. Check the scenarios and the external list agree (A115.1.2-3): every external that sends or receives has a connection.
   - Find the requirements that already bear on each connection: `external-interface` requirements and those specifying the carried items. Interface requirements are derived from system-level ones (p. 266).
   - Two things to cover (pp. 266, 279): performance (throughput, response time) and fidelity (the item arrives unchanged, every item sent is delivered and none is invented, delivery takes a reasonable time, faults are detected early and recovered from).
   - Objectives to compare candidates (A115.1.4): the book's example uses availability, fidelity, running cost and build cost (p. 281). Reuse `objectives` from step 1.
   - A gap means a new derived requirement (A115.1.5): `derived_from` the parent, `threshold` with units, io or system-wide. If you chose a number yourself, also set `source` to the proposal source ("Proposed by the AI, to confirm in review"). It changes what steps 4 and 6 cover (R25 will want a test), so propose it and ask first. **Ask:** How fast must X cross (response time), and how many per second at the busiest time? Never write TBD (R24).
2. **Choose a high-level architecture per connection (A115.2, pp. 280-281).**
   - If the other end fixes the interface (a browser, a third-party API) or a standard fits (HTTP, SQL), pick it and stop: the book skips the rest of the design then (p. 281). Standards bring swappable parts, more outside systems you can work with, lower cost and risk, longer life (p. 272). Most app connections end here. Say so in `decisions.md`.
   - Otherwise list 2 or 3 candidates (A115.2.1) from the three generic styles (pp. 267-271):

     | Style | In an app | Book's fit and warning |
     |---|---|---|
     | Message passing | queue, event bus, background jobs | large messages the receiver handles when ready (p. 267); a full buffer, bandwidth and delay are the limits (p. 269) |
     | Shared memory | shared database, cache or file both sides read and write | small requests on data mostly used by one side; warns of contention, copies drifting apart, poor scaling (p. 270); locks reset Mars Pathfinder (p. 282) |
     | Network | request and response between separate services | calls at any time, of any size, with built-in fault checking (pp. 269-270); layouts: pipeline, bus, hub-and-spoke, ring, mesh (p. 271) |

   - Define a trial interface for each (A115.2.2), for example "queue, one worker". Score each against the performance, cost and trade-off requirements (A115.2.3). Choose one (A115.2.4); put the dropped candidates and reasons in `decisions.md`. **Ask:** when the requirements do not separate them: "X is faster but costs more per month; which matters more here?" Trade-offs follow stakeholder preferences (R28), not yours.
   - A winner that needs a part of its own (queue, broker, gateway) is a new component plus new jobs: propose and ask first, then connect each part to it with its own interface. With a shared bus a new part needs one connection, not one per existing part (p. 278).
3. **Functional interface: fault detection and recovery (A115.3, p. 280; A115.3.3).**
   - A standard interface needs no jobs of its own (p. 281). A custom one may need jobs that make the hop work: connect, transfer, check errors, control flow, release (layer functions, p. 276; p. 279).
   - For each connection ask what can go wrong with an item: lost, changed, late, duplicated, other side down (pp. 266, 279). Handle the critical ones (p. 280).
   - The book's four fault jobs (pp. 203-204): detect the error (type and range checks, consistency checks, timers); confine the damage; recover (return to the last good state and tell the user, or end a job taking too long); isolate and report where it broke. Check what outside systems and users send before using it (p. 204).
   - Each is an ordinary job (`inputs`, `outputs`, `done_when`) that runs in a part. An interface cannot run a job. Adding them edits steps 2 and 4, so propose them and ask first. After they are approved, add their items to `carries`. **Ask:** Which failure at this connection would hurt users most: a lost item, a wrong item, or a slow one?
4. **Physical interface (A115.4, p. 280).** Name the concrete mechanism: protocol, driver, queue product, file format. Candidates follow from the architecture chosen (A115.4.1); drop those the platform or a `technology` requirement rules out (A115.4.2).
5. **Allocated interface (A115.5, p. 280).** `between` says which part holds each end. Check the choice against the speed and size numbers (A115.5.2) and keep the working in `decisions.md`. Write the final `interfaces` (A115.5.3-4).
6. **Re-check.** Run `sysmodel check --step 5`. The book's exit test (p. 267): the interfaces fit the parts and meet the performance requirements. When parts or jobs change later, redo this step (p. 267).

## Good vs bad
- Every item that crosses a part boundary rides on some interface (p. 57, R30(b)). Carry only items that really cross: C06 warns about extras.
- The interface does not change items, loses none, invents none (p. 266). Judge candidates against the requirements, not taste (pp. 280-281).
- Take a standard before building your own (p. 281). The Ch 12 exercise starts from the outside items and gives each one its device (p. 320, Table 12.1 on p. 321).
- Once parts exist, end an interface on the part, not on the system. An end also covers the parts under it: `[E1, C1]` serves C11 and C12.
- Bad: `between` two outside systems (for example E1 and a payment API). Good: `between: [E1, C1]`; the system or a part must be at one end (R29).
- Bad: `name: API`. Good: `name: Public HTTP`.
- Bad: IF2 carries `[I5]` while F2 outputs I6 for F12. Good: `carries: [I5, I6]`; R30(b) names the missing item.

## Checks
| Rule | What it means | Usual fix |
|---|---|---|
| R29 (p. 61), error | an interface's two ends differ, and at least one is the system or a component | change an end: connect an outside system to a part, never to another outside system or to itself |
| R30(b) (p. 57), error | every item that goes between two parts, or between a part and an outside system, is in `carries` of an interface whose ends cover both | add the item to an existing interface between those ends, or add one. If the flow itself is wrong (job in the wrong part), that is a step 4 fix: ask |
| C06 (p. 48), warning | every item in `carries` flows between the interface's ends | remove the item, or fix the flow it should follow (a step 4 fix: ask) |

R30(b) skips jobs with no `runs_in`, so a clean result means little until step 4 is done. A person signs off: no judgment item starts at this step; give the engineer your candidate comparison, written in `decisions.md`.

## Example
```yaml
# Flows the checker derives (producer -> consumer: item)
#   E1 -> C11: I1    C11 -> E1: I2    E1 -> C12: I3    C12 -> E1: I4
#   C11 -> C2: I5    C2 -> C12: I6
interfaces:
  - {id: IF1, name: Public HTTP, between: [E1, C1], carries: [I1, I2, I3, I4]}   # C1 covers C11 and C12
  - {id: IF2, name: Storage access, between: [C1, C2], carries: [I5, I6]}
# Fault handling, only proposed (edits steps 2 and 4: ask first). Storage can fail while F11 saves a link.
#   items:      {id: I7, name: Write failure}                      # F2 would output [I6, I7]
#   functions:  {id: F13, name: Retry failed write, parent: F1, inputs: [I7], outputs: [I5], done_when: Write retried, runs_in: C11}
#   once approved: IF2 carries [I5, I6, I7]
# A requirement that constrains an interface names it in `specifies` (here a rate limit on IF1):
requirements:
  - {id: Q11, text: The system shall accept up to 50 requests per second from one web visitor., category: io, subcategory: external-interface, stage: release, source: SRC1, specifies: [I1, F11, IF1], threshold: 50 requests per second}
```
