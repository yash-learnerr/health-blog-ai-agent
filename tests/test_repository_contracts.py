from pathlib import Path
import unittest


class RepositoryContractTests(unittest.TestCase):
    def test_agent_preapproves_local_command_execution(self):
        text = Path('AGENT.md').read_text(encoding='utf-8')
        self.assertIn('Local command execution', text)
        self.assertIn('python3', text)
        self.assertIn('without asking for approval first', text)

    def test_scripts_directory_does_not_store_sql_files(self):
        sql_files = sorted(path.name for path in Path('scripts').glob('*.sql'))
        self.assertEqual(sql_files, [])
        self.assertFalse(Path('examples/blog1.sql').exists())

    def test_dashboard_script_exists(self):
        self.assertTrue(Path('scripts/agent_dashboard.py').exists())
        self.assertTrue(Path('scripts/agent_db.py').exists())

    def test_dashboard_snapshot_lives_under_frontend(self):
        self.assertTrue(Path('frontend/dashboard.html').exists())
        self.assertFalse(Path('dashboard.html').exists())

    def test_run_guide_exists_under_frontend(self):
        self.assertTrue(Path('frontend/run-guide.html').exists())

    def test_homepage_links_to_run_guide(self):
        text = Path('frontend/index.html').read_text(encoding='utf-8')
        self.assertIn('/frontend/run-guide.html', text)
        self.assertIn('Open Run Guide', text)

    def test_docs_directory_consolidates_agent_markdown_layers(self):
        self.assertTrue(Path('docs/workflows/MAIN_WORKFLOW.md').exists())
        self.assertTrue(Path('docs/verifier/MEDICAL_EVIDENCE_RUBRIC.md').exists())
        self.assertTrue(Path('docs/templates/BLOG_TEMPLATE.md').exists())
        self.assertFalse(Path('workflows').exists())
        self.assertFalse(Path('verifier').exists())
        self.assertFalse(Path('templates').exists())
        self.assertFalse(Path('roles/MEMORY_MANAGER.md').exists())

    def test_agent_contract_requires_autonomous_execution_without_human_permission(self):
        text = Path('AGENT.md').read_text(encoding='utf-8')
        self.assertIn('Never pause for human input', text)
        self.assertIn('Once the workflow starts, decide autonomously', text)
        self.assertIn('you are the task owner', text)
        self.assertIn('without asking for approval first', text)
        self.assertIn('install or recover it automatically and continue', text)
        self.assertIn('Do not tell the human to run repository commands on your behalf', text)
        self.assertIn('No command handoff', text)

    def test_readme_and_scheduler_describe_autonomous_start_not_ai_mediation(self):
        readme = Path('README.md').read_text(encoding='utf-8')
        scheduler = Path('config/SCHEDULER.md').read_text(encoding='utf-8')
        self.assertIn('Start the Autonomous Workflow', readme)
        self.assertIn('agent owns execution', readme)
        self.assertIn('must not reply with "run this command"', readme)
        self.assertNotIn('Tell your AI assistant', readme)
        self.assertIn('Manual Start of the Autonomous Agent', scheduler)
        self.assertIn('continue autonomously without human intervention', scheduler)
        self.assertIn('does not hand commands back to the human', scheduler)
        self.assertNotIn('Tell your AI', scheduler)

    def test_agent_contract_forbids_destructive_database_operations(self):
        combined = '\n'.join([
            Path('AGENT.md').read_text(encoding='utf-8'),
            Path('docs/workflows/MAIN_WORKFLOW.md').read_text(encoding='utf-8'),
            Path('docs/roles/PUBLISHER.md').read_text(encoding='utf-8'),
            Path('config/DATABASE.md').read_text(encoding='utf-8'),
        ])
        self.assertIn('Never execute `DELETE`, `DROP`, `TRUNCATE`', combined)

    def test_scripts_do_not_contain_destructive_database_sql(self):
        destructive_tokens = ['DELETE FROM', 'DROP TABLE', 'TRUNCATE TABLE']
        for path in Path('scripts').glob('*.py'):
            text = path.read_text(encoding='utf-8')
            for token in destructive_tokens:
                self.assertNotIn(token, text, msg=f'{path} should not contain {token}')



if __name__ == '__main__':
    unittest.main()
