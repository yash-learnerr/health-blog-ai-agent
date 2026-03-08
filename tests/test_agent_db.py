import importlib.util
import json
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path


spec = importlib.util.spec_from_file_location('agent_db', Path('scripts/agent_db.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AgentDbTests(unittest.TestCase):
    def setUp(self):
        self._original_env = dict(mod.os.environ)
        self._original_load_env = mod.load_env
        mod.load_env = lambda path='.env': None

    def tearDown(self):
        mod.load_env = self._original_load_env
        mod.os.environ.clear()
        mod.os.environ.update(self._original_env)

    def test_current_run_id_uses_prefix(self):
        run_id = mod.current_run_id('dashboard')
        self.assertTrue(run_id.startswith('dashboard-'))

    def test_text_expr_wraps_base64_mysql_expression(self):
        expr = mod.text_expr("hello 'world'")
        self.assertIn('FROM_BASE64', expr)
        self.assertIn('utf8mb4', expr)

    def test_text_equals_expr_uses_binary_comparison(self):
        expr = mod.text_equals_expr('blog_master.slug', "hello 'world'")
        self.assertIn('BINARY blog_master.slug = BINARY', expr)
        self.assertIn('FROM_BASE64', expr)

    def test_json_expr_wraps_json_payload_as_text_expression(self):
        expr = mod.json_expr({'status': 'ok'})
        self.assertIn('FROM_BASE64', expr)
        self.assertIn('utf8mb4', expr)

    def test_normalize_usage_metrics_derives_total_and_request_count(self):
        metrics = mod.normalize_usage_metrics(details={'usage': {'prompt_tokens': 120, 'completion_tokens': 30}})
        self.assertEqual(metrics['request_count'], 1)
        self.assertEqual(metrics['total_tokens'], 150)

    def test_normalize_usage_metrics_prefers_explicit_values(self):
        metrics = mod.normalize_usage_metrics(request_count=4, prompt_tokens=10, completion_tokens=5, total_tokens=20, details={'usage': {'prompt_tokens': 999}})
        self.assertEqual(metrics['request_count'], 4)
        self.assertEqual(metrics['prompt_tokens'], 10)
        self.assertEqual(metrics['completion_tokens'], 5)
        self.assertEqual(metrics['total_tokens'], 20)

    def test_staging_publish_db_name_is_preferred(self):
        mod.os.environ['DATABASE_ACCESS'] = 'staging'
        mod.os.environ['STAGING_DB_HOST'] = 'staging-host'
        mod.os.environ['STAGING_DB_USER'] = 'staging-user'
        mod.os.environ['STAGING_DB_PASSWORD'] = 'staging-pass'
        mod.os.environ['STAGING_PUBLISH_DB_NAME'] = 'staging_publish'
        mod.os.environ['PUBLISH_DB_NAME'] = 'local_publish'
        self.assertTrue(mod.using_staging_db())
        self.assertEqual(mod.publish_db_name(), 'staging_publish')

    def test_local_publish_db_name_is_used_without_staging(self):
        mod.os.environ['DATABASE_ACCESS'] = 'local'
        mod.os.environ['STAGING_DB_HOST'] = 'staging-host'
        mod.os.environ['STAGING_DB_USER'] = 'staging-user'
        mod.os.environ['STAGING_DB_PASSWORD'] = 'staging-pass'
        mod.os.environ['PUBLISH_DB_NAME'] = 'local_publish'
        self.assertFalse(mod.using_staging_db())
        self.assertEqual(mod.publish_db_name(), 'local_publish')

    def test_local_override_ignores_staging_agent_db(self):
        mod.os.environ['STAGING_DB_HOST'] = 'staging-host'
        mod.os.environ['STAGING_DB_USER'] = 'staging-user'
        mod.os.environ['STAGING_DB_PASSWORD'] = 'staging-pass'
        mod.os.environ['STAGING_AGENT_DB_NAME'] = 'staging_agent'
        mod.os.environ['AGENT_DB_NAME'] = 'local_agent'
        self.assertEqual(mod.operational_db_name(use_staging=False), 'local_agent')
        self.assertEqual(mod.db_target_info(use_staging=False)['mode'], 'Local')

    def test_production_access_uses_production_variables(self):
        mod.os.environ['DATABASE_ACCESS'] = 'production'
        mod.os.environ['PRODUCTION_DB_HOST'] = 'prod-host'
        mod.os.environ['PRODUCTION_DB_USER'] = 'prod-user'
        mod.os.environ['PRODUCTION_DB_PASSWORD'] = 'prod-pass'
        mod.os.environ['PRODUCTION_DB_PORT'] = '4406'
        mod.os.environ['PRODUCTION_AGENT_DB_NAME'] = 'prod_agent'
        mod.os.environ['PRODUCTION_PUBLISH_DB_NAME'] = 'prod_publish'
        cfg = mod.db_connection_config()
        self.assertTrue(mod.using_production_db())
        self.assertEqual(cfg['host'], 'prod-host')
        self.assertEqual(cfg['port'], 4406)
        self.assertEqual(mod.publish_db_name(), 'prod_publish')
        self.assertEqual(mod.operational_db_name(), 'prod_agent')
        self.assertEqual(mod.db_target_info()['mode'], 'Production')

    def test_invalid_database_access_raises_value_error(self):
        mod.os.environ['DATABASE_ACCESS'] = 'qa'
        with self.assertRaises(ValueError):
            mod.db_connection_config()

    def test_blog_master_file_db_value_keeps_full_url_locally(self):
        mod.os.environ['DATABASE_ACCESS'] = 'local'
        value = 'https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/example.png'
        self.assertEqual(mod.blog_master_file_db_value(value), value)

    def test_blog_master_file_db_value_converts_remote_url_for_staging(self):
        mod.os.environ['DATABASE_ACCESS'] = 'staging'
        value = 'https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/example.png'
        self.assertEqual(mod.blog_master_file_db_value(value), 'blog_master/example.png')

    def test_fetch_latest_blogs_expands_stored_blog_master_file_key(self):
        mod.os.environ['DO_SPACES_BUCKET_URL'] = 'https://example-bucket.nyc3.digitaloceanspaces.com'
        with mock.patch.object(mod, '_table_columns') as columns_mock:
            with mock.patch.object(mod, '_query_rows', return_value=[[
                '7',
                mod._b64('Sample title'),
                mod._b64('sample-slug'),
                mod._b64('Research'),
                mod._b64('Summary'),
                mod._b64(''),
                mod._b64('blog_master/example.png'),
                '2026-03-08 13:00:00',
            ]]):
                columns_mock.side_effect = [
                    {'id', 'blog_name', 'slug', 'meta_description', 'file', 'category_id', 'status'},
                    {'id', 'name'},
                ]
                rows = mod.fetch_latest_blogs(limit=1)

        self.assertEqual(rows[0]['file_url'], 'https://example-bucket.nyc3.digitaloceanspaces.com/blog-master/example.png')

    def test_sh_timeout_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            mod.sh(['python3', '-c', 'import time; time.sleep(1)'], timeout_seconds=0)

    def test_database_backend_prefers_python_connector(self):
        with mock.patch.object(mod, '_import_mysql_connector', return_value=object()):
            self.assertEqual(mod.database_backend(), 'mysql.connector')

    def test_database_backend_uses_mysql_cli_when_connector_missing(self):
        with mock.patch.object(mod, '_import_mysql_connector', return_value=None):
            with mock.patch.object(mod, '_mysql_cli_available', return_value=True):
                self.assertEqual(mod.database_backend(), 'mysql')

    def test_split_sql_statements_keeps_semicolons_inside_strings(self):
        statements = mod._split_sql_statements("SELECT 'a;b'; INSERT INTO x VALUES (1, 'c;d');")
        self.assertEqual(statements, ["SELECT 'a;b'", "INSERT INTO x VALUES (1, 'c;d')"])

    def test_mysql_auto_installs_connector_when_no_backend_exists(self):
        completed = subprocess.CompletedProcess(args=['python', '-m', 'pip'], returncode=0, stdout='ok', stderr='')
        with mock.patch.object(mod, '_import_mysql_connector', return_value=None):
            with mock.patch.object(mod, '_mysql_cli_available', return_value=False):
                with mock.patch.object(mod.subprocess, 'run', return_value=completed) as run_mock:
                    with mock.patch.object(mod.importlib, 'import_module', return_value='connector-module') as import_mock:
                        module = mod._mysql_connector_module()
        self.assertEqual(module, 'connector-module')
        run_mock.assert_called_once()
        import_mock.assert_called_once_with('mysql.connector')

    def test_log_event_writes_json_when_storage_backend_is_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod.os.environ['AGENT_STORAGE_BACKEND'] = 'json'
            mod.os.environ['AGENT_JSON_STORAGE_DIR'] = temp_dir
            with mock.patch.object(mod, 'mysql', side_effect=AssertionError('mysql should not be used in json mode')):
                mod.log_event(
                    'run-1',
                    'writer',
                    'SUCCESS',
                    'Saved JSON log.',
                    details={'usage': {'prompt_tokens': 12, 'completion_tokens': 8}},
                )

            payload = json.loads(Path(temp_dir, 'agent_run_logs.json').read_text(encoding='utf-8'))
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]['run_id'], 'run-1')
            self.assertEqual(payload[0]['request_count'], 1)
            self.assertEqual(payload[0]['total_tokens'], 20)

    def test_store_memory_fact_writes_json_when_storage_backend_is_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod.os.environ['AGENT_STORAGE_BACKEND'] = 'json'
            mod.os.environ['AGENT_JSON_STORAGE_DIR'] = temp_dir
            with mock.patch.object(mod, 'mysql', side_effect=AssertionError('mysql should not be used in json mode')):
                mod.store_memory_fact(
                    topic_slug='sample-topic',
                    category_name='Clinical Guidelines',
                    memory_key='fact-1',
                    verified_fact='Important verified fact.',
                    source_url='https://example.com/fact',
                    confidence='high',
                )

            payload = json.loads(Path(temp_dir, 'agent_memory.json').read_text(encoding='utf-8'))
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]['topic_slug'], 'sample-topic')
            self.assertEqual(payload[0]['memory_key'], 'fact-1')
            self.assertEqual(payload[0]['status'], 'active')

    def test_fetch_dashboard_snapshot_reads_json_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod.os.environ['AGENT_JSON_STORAGE_DIR'] = temp_dir
            mod.os.environ['DASHBOARD_DATA_SOURCE'] = 'json'
            Path(temp_dir, 'agent_run_logs.json').write_text(json.dumps([
                {
                    'id': 1,
                    'run_id': 'run-1',
                    'step': 'runner',
                    'status': 'SUCCESS',
                    'message': 'Started',
                    'request_count': 1,
                    'prompt_tokens': 10,
                    'completion_tokens': 5,
                    'total_tokens': 15,
                    'created_at': '2026-03-07 10:00:00',
                },
                {
                    'id': 2,
                    'run_id': 'run-1',
                    'step': 'publisher',
                    'status': 'ERROR',
                    'message': 'Publish failed',
                    'request_count': 2,
                    'prompt_tokens': 20,
                    'completion_tokens': 10,
                    'total_tokens': 30,
                    'created_at': '2026-03-08 11:00:00',
                },
            ], ensure_ascii=False), encoding='utf-8')
            Path(temp_dir, 'agent_memory.json').write_text(json.dumps([
                {
                    'id': 1,
                    'topic_slug': 'sample-topic',
                    'category_name': 'Research',
                    'memory_key': 'fact-1',
                    'verified_fact': 'Fact text',
                    'confidence': 'high',
                    'status': 'active',
                    'created_at': '2026-03-08 12:00:00',
                }
            ], ensure_ascii=False), encoding='utf-8')

            snapshot = mod.fetch_dashboard_snapshot(run_limit=5, log_limit=5, memory_limit=5, chart_day_limit=7)

            self.assertEqual(snapshot['db_target']['mode'], 'JSON')
            self.assertEqual(snapshot['db_target']['status_label'], 'JSON files')
            self.assertEqual(snapshot['stats']['total_events'], 2)
            self.assertEqual(snapshot['stats']['error_events'], 1)
            self.assertEqual(snapshot['stats']['total_tokens'], 45)
            self.assertEqual(snapshot['runs'][0]['run_id'], 'run-1')
            self.assertEqual(snapshot['runs'][0]['event_count'], 2)
            self.assertEqual(snapshot['memory'][0]['memory_key'], 'fact-1')
            self.assertEqual(snapshot['charts']['activity_by_day'][-1]['label'], '2026-03-08')


if __name__ == '__main__':
    unittest.main()
