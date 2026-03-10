#!/usr/bin/env python3
import os
import shlex
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_db


def default_command(cli_args):
    configured_python = os.getenv('AGENT_PYTHON_COMMAND', '').strip()
    python_parts = shlex.split(configured_python) if configured_python else [sys.executable or 'python3']
    workflow_script = REPO_ROOT / 'scripts' / 'run_workflow.py'
    if cli_args:
        return [*python_parts, str(workflow_script), *cli_args], False
    recency_hours = os.getenv('AGENT_START_RECENCY_HOURS', '24').strip() or '24'
    return [*python_parts, str(workflow_script), '--recency-hours', recency_hours], False


def resolve_command(cli_args):
    agent_db.load_env(str(REPO_ROOT / '.env'))
    command_override = os.getenv('AGENT_START_COMMAND', '').strip()
    if command_override:
        return command_override, True
    return default_command(cli_args)


def main(argv=None):
    cli_args = list(sys.argv[1:] if argv is None else argv)
    command, use_shell = resolve_command(cli_args)
    print('AGENT.md/workflow review complete -> starting workflow automatically...', flush=True)
    completed = subprocess.run(command, cwd=REPO_ROOT, shell=use_shell)
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())