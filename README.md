# autoexp

ML experiment toolkit for autonomous agents.

autoexp gives any AI agent (Claude Code, OpenClaw, Aider, or a simple script) the infrastructure to run ML experiments autonomously: structured tracking in SQLite, git-based experiment identity, file validation, training monitoring with abort rules, and evaluation recording.

The agent does the thinking. autoexp does the bookkeeping.

Single Python file. Zero dependencies. Install as a skill and go.

## Install

```bash
npx skills add MrTsepa/autoexp
```

That's it. The CLI is bundled in the skill at `.claude/skills/autoexp/scripts/autoexp.py`.

## Quick Start

```bash
# In your ML project
python .claude/skills/autoexp/scripts/autoexp.py init

# Edit the research goal
vim .autoexp/program.md

# Edit what files the agent can/can't touch
vim .autoexp/config.yaml
```

### Autonomous Mode (Claude Code)

```bash
/loop 30m /autoexp
```

Claude Code wakes up every 30 minutes, checks state, decides what to do, runs an experiment, evaluates, and goes back to sleep.

### With Any Agent

Any agent that can run bash commands can drive autoexp. The CLI outputs JSON with `--json` for machine consumption:

```bash
python .claude/skills/autoexp/scripts/autoexp.py results --json
```

## How It Works

```
Agent (Claude Code, OpenClaw, etc.)
  │
  │  "Try lower learning rate"
  │
  ├── autoexp validate configs/exp.yaml    # check syntax + locked files
  ├── autoexp commit "lower lr to 1e-4"    # git commit + register in DB
  ├── autoexp train "uv run train" --timeout 2h  # run with monitoring
  ├── autoexp eval "uv run eval"           # evaluate + record metrics
  ├── autoexp results --json               # structured results from DB
  └── autoexp revert                       # discard if bad
```

Each experiment is a git commit. Results live in SQLite, not text files. The agent queries real data, not its own prose.

## Commands

| Command | Description |
|---------|-------------|
| `autoexp init` | Initialize `.autoexp/` in current project |
| `autoexp status` | Show what's running and recent experiments |
| `autoexp validate <files>` | Check syntax, compilation, locked file rules |
| `autoexp commit "<hypothesis>"` | Git commit + register experiment in DB |
| `autoexp train "<cmd>" [--timeout T]` | Run training with timeout and abort monitoring |
| `autoexp eval "<cmd>" [--experiment ID]` | Run evaluation, extract and record metrics |
| `autoexp revert [--experiment ID]` | Git revert + mark experiment as discarded |
| `autoexp results [--last N] [--best M] [--json]` | Query experiment database |
| `autoexp report` | Generate markdown experiment report from DB |

## Configuration

`.autoexp/config.yaml`:

```yaml
# Files the agent can modify
editable_files:
  - "configs/*.yaml"
  - "src/**/*.py"

# Files the agent must never modify
locked_files:
  - "eval.py"
  - ".autoexp/*"

# Kill training if these conditions are met
abort_rules:
  - pattern: "loss"
    condition: "above"
    threshold: 100.0
    after_lines: 500
```

## Example: Solving LunarLander Autonomously

Using `/loop 30m /autoexp` with Claude Code, the agent solved LunarLander-v3 in 4 experiments (~25 minutes total):

| Experiment | Hypothesis | Result |
|---|---|---|
| auto_001 | baseline: default PPO hyperparams, 100k steps | failed (user stopped) |
| auto_002 | wider network [256,256] + 300k steps | timeout — too slow on CPU |
| auto_003 | smaller net [64,64] + higher lr (7e-4) + 300k steps | timeout — still too slow |
| auto_004 | n_envs 4→8 for 2x throughput, lr 1e-3 | **mean_reward: 252.3, solved_rate: 95%** |

The agent learned from its own failures: timeouts in auto_002/003 led it to increase parallelism (n_envs) and learning rate, which solved the environment in auto_004.

Full POC: [autoexp-lunarlander-demo](https://github.com/MrTsepa/autoexp-lunarlander-demo)

## Design Principles

- **Git is the experiment tracker.** Each experiment = a commit. Reproducible by checkout + rerun.
- **SQLite is the source of truth.** Metrics are numbers in a database, not claims in a text file.
- **Agent-agnostic.** Works with Claude Code, OpenClaw, Aider, or a bash script.
- **Zero dependencies.** Single Python file, stdlib only.
- **Zero opinion on your ML stack.** Runs any command. Parses `key: value` or `key=value` from stdout for metrics.

## License

MIT
