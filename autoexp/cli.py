"""CLI dispatcher for autoexp."""

import argparse
import json
import shutil
import sys
from pathlib import Path

from autoexp.config import get_autoexp_dir, load_config, DB_FILE, CONFIG_FILE, PROGRAM_FILE
from autoexp import db, git_ops, validate, train, report


TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def cmd_init(args):
    """Initialize .autoexp/ in current project."""
    d = get_autoexp_dir()
    d.mkdir(exist_ok=True)

    # Copy templates
    for name in (CONFIG_FILE, PROGRAM_FILE):
        dest = d / name
        src = TEMPLATES_DIR / name
        if not dest.exists() and src.exists():
            shutil.copy(src, dest)
            print(f"Created {dest}")
        elif dest.exists():
            print(f"Already exists: {dest}")

    # Init DB
    db_path = d / DB_FILE
    conn = db.init_db(db_path)
    conn.close()
    print(f"Database: {db_path}")
    print("\nDone. Edit .autoexp/program.md with your research goal.")


def cmd_status(args):
    """Show current experiment state."""
    conn = db.init_db(get_autoexp_dir() / DB_FILE)

    running = db.get_experiments(conn, status="running")
    if running:
        print("RUNNING:")
        for exp in running:
            print(f"  {exp['id']}: {exp['hypothesis']}")
            if exp["train_command"]:
                print(f"    command: {exp['train_command']}")
            print(f"    started: {exp['started_at']}")
    else:
        print("No experiments running.")

    recent = db.get_experiments(conn, last_n=3)
    if recent:
        print("\nRecent:")
        for exp in recent:
            print(f"  {exp['id']}: [{exp['status']}] {exp['hypothesis']}")
    conn.close()


def cmd_validate(args):
    """Validate files."""
    config = load_config()
    ok, reason = validate.validate_files(args.files, config)
    if ok:
        print(f"OK: {len(args.files)} file(s) valid")
    else:
        print(f"FAIL: {reason}", file=sys.stderr)
        sys.exit(1)


def cmd_commit(args):
    """Commit changes as an experiment."""
    conn = db.init_db(get_autoexp_dir() / DB_FILE)

    # Get changed files if not specified
    files = args.files
    if not files:
        files = git_ops.get_changed_files()
    # Filter out .autoexp/ internal files
    files = [f for f in files if not f.startswith(".autoexp/")]
    if not files:
        print("No changes to commit.", file=sys.stderr)
        sys.exit(1)

    # Validate first
    config = load_config()
    ok, reason = validate.validate_files(
        [f for f in files if Path(f).exists()], config
    )
    if not ok:
        print(f"Validation failed: {reason}", file=sys.stderr)
        sys.exit(1)

    # Create experiment
    exp_id = db.next_experiment_id(conn)
    sha = git_ops.commit(f"[{exp_id}] {args.hypothesis}", files)
    db.create_experiment(conn, exp_id, sha, args.hypothesis)

    print(f"Experiment {exp_id} committed ({sha[:8]})")
    print(f"  hypothesis: {args.hypothesis}")
    print(f"  files: {', '.join(files)}")
    conn.close()


def cmd_train(args):
    """Run training with monitoring."""
    conn = db.init_db(get_autoexp_dir() / DB_FILE)
    config = load_config()

    # Find or use specified experiment
    exp_id = args.experiment
    if not exp_id:
        experiments = db.get_experiments(conn, last_n=1)
        if not experiments:
            print("No experiments found. Run 'autoexp commit' first.", file=sys.stderr)
            sys.exit(1)
        exp_id = experiments[0]["id"]

    db.update_experiment(conn, exp_id, status="running", train_command=args.command)

    print(f"Training {exp_id}: {args.command}")
    if args.timeout:
        print(f"  timeout: {args.timeout}")

    result = train.run_training(
        command=args.command,
        timeout=args.timeout,
        abort_rules=config.get("abort_rules", []),
        on_line=lambda line: print(f"  | {line}"),
    )

    db.update_experiment(
        conn,
        exp_id,
        status=result.status,
        finished_at=db._now(),
        abort_reason=result.abort_reason,
    )

    print(f"\nResult: {result.status} ({result.duration_seconds}s)")
    if result.abort_reason:
        print(f"  abort reason: {result.abort_reason}")
    if result.exit_code and result.exit_code != 0:
        print(f"  exit code: {result.exit_code}")

    conn.close()


def cmd_eval(args):
    """Run evaluation and record results."""
    conn = db.init_db(get_autoexp_dir() / DB_FILE)

    exp_id = args.experiment
    if not exp_id:
        experiments = db.get_experiments(conn, last_n=1)
        if not experiments:
            print("No experiments found.", file=sys.stderr)
            sys.exit(1)
        exp_id = experiments[0]["id"]

    print(f"Evaluating {exp_id}: {args.command}")

    import subprocess
    r = subprocess.run(args.command, shell=True, capture_output=True, text=True)
    output = r.stdout + r.stderr

    print(output)

    # Try to extract numeric scores from output
    import re
    scores_found = 0
    for line in output.splitlines():
        # Match patterns like "metric_name: 0.85" or "metric_name=0.85"
        for match in re.finditer(r"(\w+)\s*[=:]\s*([\d.eE+-]+)", line):
            name, value = match.group(1), match.group(2)
            try:
                score = float(value)
                db.record_eval(conn, exp_id, name, score, output)
                db.record_metric(conn, exp_id, name, score, source="eval")
                scores_found += 1
            except ValueError:
                continue

    if scores_found:
        print(f"\nRecorded {scores_found} metric(s) for {exp_id}")
    else:
        print(f"\nNo metrics extracted. Raw output saved for {exp_id}")
        db.record_eval(conn, exp_id, "raw", 0.0, output)

    db.update_experiment(conn, exp_id, eval_command=args.command)
    conn.close()


def cmd_revert(args):
    """Revert last experiment."""
    conn = db.init_db(get_autoexp_dir() / DB_FILE)

    exp_id = args.experiment
    if not exp_id:
        experiments = db.get_experiments(conn, last_n=1)
        if not experiments:
            print("No experiments to revert.", file=sys.stderr)
            sys.exit(1)
        exp_id = experiments[0]["id"]

    ok, msg = git_ops.revert_head()
    if ok:
        db.update_experiment(conn, exp_id, status="discarded", finished_at=db._now())
        print(f"Reverted {exp_id}")
    else:
        print(f"Revert failed: {msg}", file=sys.stderr)
        sys.exit(1)
    conn.close()


def cmd_results(args):
    """Query experiment database."""
    conn = db.init_db(get_autoexp_dir() / DB_FILE)

    if args.best:
        best = db.get_best(conn, args.best)
        if best:
            if args.json:
                print(json.dumps(best, indent=2))
            else:
                print(f"Best {args.best}: {best.get('best_value')} ({best['id']})")
                print(f"  hypothesis: {best['hypothesis']}")
        else:
            print(f"No completed experiments with metric '{args.best}'")
        conn.close()
        return

    experiments = db.get_experiments(conn, last_n=args.last)
    if args.json:
        # Enrich with evals
        for exp in experiments:
            exp["evaluations"] = db.get_evals(conn, exp["id"])
            exp["metrics"] = db.get_metrics(conn, exp["id"])
        print(json.dumps(experiments, indent=2))
    else:
        if not experiments:
            print("No experiments recorded.")
        else:
            for exp in experiments:
                evals = db.get_evals(conn, exp["id"])
                eval_str = ", ".join(f"{e['eval_name']}={e['score']:.3f}" for e in evals)
                print(f"{exp['id']} [{exp['status']}] {exp['hypothesis']}")
                if eval_str:
                    print(f"  evals: {eval_str}")
    conn.close()


def cmd_report(args):
    """Generate RESEARCH.md."""
    conn = db.init_db(get_autoexp_dir() / DB_FILE)
    print(report.generate_report(conn))
    conn.close()


def main():
    parser = argparse.ArgumentParser(prog="autoexp", description="ML experiment toolkit")
    sub = parser.add_subparsers(dest="subcommand")

    sub.add_parser("init", help="Initialize .autoexp/ in current project")
    sub.add_parser("status", help="Show current experiment state")

    p = sub.add_parser("validate", help="Validate files")
    p.add_argument("files", nargs="+")

    p = sub.add_parser("commit", help="Commit changes as experiment")
    p.add_argument("hypothesis", help="Experiment hypothesis")
    p.add_argument("--files", nargs="*", default=None)

    p = sub.add_parser("train", help="Run training with monitoring")
    p.add_argument("command", help="Training command to run")
    p.add_argument("--timeout", default=None, help="Timeout (e.g. 20m, 2h, 30s)")
    p.add_argument("--experiment", default=None, help="Experiment ID")

    p = sub.add_parser("eval", help="Run evaluation")
    p.add_argument("command", help="Evaluation command to run")
    p.add_argument("--experiment", default=None, help="Experiment ID")

    p = sub.add_parser("revert", help="Revert last experiment")
    p.add_argument("--experiment", default=None, help="Experiment ID")

    p = sub.add_parser("results", help="Query experiments")
    p.add_argument("--last", type=int, default=10)
    p.add_argument("--best", default=None, help="Show best by metric name")
    p.add_argument("--json", action="store_true")

    sub.add_parser("report", help="Generate RESEARCH.md")

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "validate": cmd_validate,
        "commit": cmd_commit,
        "train": cmd_train,
        "eval": cmd_eval,
        "revert": cmd_revert,
        "results": cmd_results,
        "report": cmd_report,
    }
    commands[args.subcommand](args)


if __name__ == "__main__":
    main()
