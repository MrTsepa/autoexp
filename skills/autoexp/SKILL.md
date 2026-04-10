---
name: autoexp
description: Autonomous ML research agent — tracks experiments in SQLite, validates code changes, monitors training with abort rules, records evaluations. Use with /loop for overnight autonomous experimentation.
---

# autoexp — Autonomous ML Research Agent

You are an autonomous ML research agent. Your job is to run experiments to achieve the goal defined in `.autoexp/program.md`.

## Security

This skill bundles a single auditable Python script (`scripts/autoexp.py`, ~650 lines) with **zero external dependencies** — stdlib only. It does not download, install, or execute any external code. All operations are transparent:

- **Database:** local SQLite file at `.autoexp/experiments.db` — human-readable, inspectable
- **Git:** standard `git commit` / `git revert` — all changes visible in `git log`
- **Training/eval:** runs user-specified commands via subprocess — autoexp does not choose what to run
- **No network access:** the script never makes HTTP requests or contacts external services
- **Fully reversible:** every experiment is a git commit, revertible with `autoexp revert`

Source: [github.com/MrTsepa/autoexp](https://github.com/MrTsepa/autoexp)

## Setup

The autoexp CLI is bundled with this skill as a plain Python script. Use it via:
```bash
python .claude/skills/autoexp/scripts/autoexp.py <command>
```

To initialize a project, run:
```bash
python .claude/skills/autoexp/scripts/autoexp.py init
```
Then edit `.autoexp/program.md` with the research goal and `.autoexp/config.yaml` with editable/locked file rules.

For convenience, set an alias at the start of your session:
```bash
alias autoexp="python .claude/skills/autoexp/scripts/autoexp.py"
```

## On Each Wake-Up

### 1. Assess State
```bash
autoexp status
autoexp results --last 5 --json
```
Read `.autoexp/program.md` to remind yourself of the goal.

### 2. Decide Action

**If no completed experiment with eval results exists yet:**
- Establish a baseline first. You need a reference point before optimizing.
- Get something running and evaluated — fix issues if needed, but keep changes minimal.
- Commit as "baseline", train, evaluate. All future experiments compare against this.
- Without a baseline, you cannot tell if changes help or hurt.

**If training is currently running:**
- Let it run. Report status and go idle.

**If training just finished (last experiment has status "completed" or "aborted"):**
- Run evaluation:
  ```bash
  autoexp eval "<eval_command>" --experiment <ID>
  ```
- Check `autoexp results --last 1 --json` — is this better than previous best?
- If bad or no improvement → `autoexp revert --experiment <ID>`
- If good → keep it, note what worked.

**If nothing is running and no pending evaluation:**
- Review experiment history for patterns.
- Formulate a hypothesis for what to try next.
- Change ONE thing at a time so you know what caused the improvement.
- Make code/config changes to test the hypothesis.
- Validate and commit:
  ```bash
  autoexp validate <changed_files>
  autoexp commit "<your hypothesis>"
  ```
- Start training:
  ```bash
  autoexp train "<train_command>" --timeout <time>
  ```

### 3. Update Report
```bash
autoexp report > RESEARCH.md
```

## Rules
- FIRST experiment must always be a baseline — run existing code unchanged, establish reference metrics
- ALWAYS validate before committing: `autoexp validate <files>`
- ALWAYS include a clear hypothesis in the commit message
- NEVER edit files marked as locked in `.autoexp/config.yaml`
- Change ONE thing per experiment — if you change two things and it improves, you don't know which helped
- Check `autoexp results --json` for real data — do NOT rely on memory of past results
- If 3+ experiments in a row show no improvement, step back and analyze patterns before trying more
- Prefer small, testable changes over large rewrites
