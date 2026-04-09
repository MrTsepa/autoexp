# autoexp

ML experiment toolkit for autonomous agents.

autoexp gives any AI agent (Claude Code, OpenClaw, Aider, or a simple script) the infrastructure to run ML experiments autonomously: structured tracking in SQLite, git-based experiment identity, file validation, training monitoring with abort rules, and evaluation recording.

The agent does the thinking. autoexp does the bookkeeping.

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

## Install

```bash
# From source
git clone https://github.com/MrTsepa/autoexp.git
cd autoexp
uv sync

# Or pip
pip install -e .
```

## Quick Start

```bash
# In your ML project
cd my-ml-project
autoexp init

# Edit the research goal
vim .autoexp/program.md

# Edit what files the agent can/can't touch
vim .autoexp/config.yaml
```

### With Claude Code

Install the skill, then:

```bash
/loop 30m /autoexp
```

Claude Code wakes up every 30 minutes, checks state, decides what to do, runs an experiment, evaluates, and goes back to sleep.

### With Any Agent

Any agent that can run bash commands can drive autoexp. The CLI outputs JSON with `--json` for machine consumption.

### Manual

```bash
# Make a change, then:
autoexp validate train.py configs/new.yaml
autoexp commit "add attention to policy network"
autoexp train "uv run python train.py --config configs/new.yaml" --timeout 1h
autoexp eval "uv run python eval.py --checkpoint runs/latest/best"
autoexp results --best win_rate
autoexp report > RESEARCH.md
```

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

## Design Principles

- **Git is the experiment tracker.** Each experiment = a commit. Reproducible by checkout + rerun.
- **SQLite is the source of truth.** Metrics are numbers in a database, not claims in a text file. Agents query real data.
- **Agent-agnostic.** Works with Claude Code, OpenClaw, Aider, or a bash script. No vendor lock-in.
- **Validation before execution.** Locked files can't be touched. Syntax is checked. Bad code doesn't get committed.
- **Zero opinion on your ML stack.** Runs any command. Parses `key: value` or `key=value` from stdout for metrics.

## Project Structure

```
.autoexp/
├── config.yaml       # what's editable, what's locked, abort rules
├── program.md        # research goal (read by the agent)
└── experiments.db    # SQLite database (source of truth)
```

## License

MIT
