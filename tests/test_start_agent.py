import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


spec = importlib.util.spec_from_file_location('start_agent', Path('scripts/start_agent.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class StartAgentTests(unittest.TestCase):
    def test_resolve_command_uses_default_workflow_command(self):
        with mock.patch.dict(mod.os.environ, {'AGENT_START_RECENCY_HOURS': '48'}, clear=True):
            with mock.patch.object(mod.agent_db, 'load_env'):
                command, use_shell = mod.resolve_command([])

        self.assertFalse(use_shell)
        self.assertEqual(command[-2:], ['--recency-hours', '48'])
        self.assertTrue(command[1].endswith('scripts/run_workflow.py'))

    def test_resolve_command_uses_override_when_present(self):
        override = 'python scripts/run_workflow.py --recency-hours 12'
        with mock.patch.dict(mod.os.environ, {'AGENT_START_COMMAND': override}, clear=True):
            with mock.patch.object(mod.agent_db, 'load_env'):
                command, use_shell = mod.resolve_command([])

        self.assertTrue(use_shell)
        self.assertEqual(command, override)

    def test_main_forwards_cli_args_to_workflow(self):
        with mock.patch.dict(mod.os.environ, {}, clear=True):
            with mock.patch.object(mod.agent_db, 'load_env'):
                with mock.patch.object(mod.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as runner:
                    result = mod.main(['--recency-hours', '72'])

        self.assertEqual(result, 0)
        args, kwargs = runner.call_args
        self.assertEqual(args[0][-2:], ['--recency-hours', '72'])
        self.assertEqual(kwargs['cwd'], mod.REPO_ROOT)
        self.assertFalse(kwargs['shell'])


if __name__ == '__main__':
    unittest.main()