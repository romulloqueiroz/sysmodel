# sysmodel

**Design the app before the AI writes it.**

AI agents write code fast. They're less good at deciding *what* should be built: who it's for, what "fast enough" means, which part owns which job, and how you'll know it works. Skip that thinking and you get a lot of code quickly, much of it solving the wrong problem.

sysmodel puts a proven engineering method between your idea and the code. The AI does the legwork, you make the decisions, and nothing gets built until a person has approved the design one step at a time.

```
idea ──▶ AI drafts the design ──▶ you review & approve ──▶ build spec per part ──▶ code
              ▲                          │
              └────── sent back ─────────┘
```

## Why it works

- **One model, one source of truth.** The whole design lives in a single YAML file: requirements, jobs, parts, interfaces and tests, all linked. The pictures, the checks and the specs are all generated from it, so they can't drift apart.
- **The AI asks; it doesn't invent.** Facts only you can know (users, budgets, thresholds, deadlines) are asked, never guessed or left as "TBD".
- **Rules from the book, checked by machine.** 28 checks catch gaps before they become rework: a requirement nobody tests, a job with no part to run it, data crossing between parts with no interface.
- **People sign off where machines can't.** Each step ends in a review screen, where you approve it or send it back with a note. Change something later and the approval goes stale, so you see exactly what needs another look.
- **Specs, not vibes.** When the design is approved, `spec` writes a build spec for each part: its scenarios, jobs, connections, requirements and the tests that prove them. That's everything a coding agent needs, and nothing it has to guess.

## The six steps

Each step answers one plain question, the way systems engineers have done for decades:

| Step | Question | You get |
|---|---|---|
| 1 Problem | Who uses it, and what must it do? | Stakeholders, scenarios, the system boundary, objectives, requirements |
| 2 Functions | What does it do, step by step? | A tree of jobs and the data flowing between them |
| 3 Parts | What is it made of? | The components, chosen from real alternatives |
| 4 Match | Which part does each job? | Every job given to one part, and budgets shared out |
| 5 Interfaces | How do the parts connect? | Every connection and what it carries |
| 6 Test plan | How will we prove it works? | A test for every requirement that needs one |

## Quick start

You need [Claude Code](https://claude.com/claude-code) and Python 3.9 or newer, which most Macs and Linux machines already have. There's nothing else to install: the few libraries sysmodel uses come bundled.

```sh
git clone https://github.com/romulloqueiroz/sysmodel.git
mkdir -p ~/.claude/skills
ln -s "$PWD/sysmodel" ~/.claude/skills/sysmodel
```

sysmodel is a Claude Code skill, and this folder *is* the skill: `SKILL.md` teaches the AI the method and the commands, and `steps/` holds a guide for each of the six steps, which the AI reads before working on that step. The link makes `/sysmodel` available in every project, and `git pull` keeps it up to date.

Then, in any project:

```
/sysmodel I want to build a URL shortener for our marketing team
```

The AI starts step 1, asks you what it needs to know, and writes the model to `design/system.yaml`. It opens the review app so you can see the pictures and approve each step.

## Commands

The skill runs these for you; you can run them yourself too.

```sh
python3 sysmodel.py status design/system.yaml       # whose turn each step is
python3 sysmodel.py check  design/system.yaml       # rule problems, with the book page for each
python3 sysmodel.py serve  design/system.yaml       # the review app: pictures, approve, send back
python3 sysmodel.py render design/system.yaml       # a static HTML snapshot to share
python3 sysmodel.py spec   design/system.yaml C11   # the build spec for one part (once approved)
```

The review app runs locally and works offline. Decisions are saved next to the model in `system.review.yaml`, so they live in your repo and show up in your diffs.

## Built on a classic

The method comes from Dennis M. Buede and William D. Miller, *The Engineering Design of Systems: Models and Methods* (4th ed., Wiley), tailored for software apps. Rules and guides cite the book's pages, so if you own it you can look up why each rule exists. The book isn't required to use sysmodel, and none of its text is reproduced here.

## License

MIT. The bundled libraries (PyYAML, rough.js, elkjs) and fonts keep their own licenses; see [`vendor/`](vendor/).
