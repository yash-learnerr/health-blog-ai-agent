import importlib.util
import sys
import unittest
from pathlib import Path


scripts_dir = Path('scripts').resolve()
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

spec = importlib.util.spec_from_file_location('agent_dashboard', scripts_dir / 'agent_dashboard.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AgentDashboardTests(unittest.TestCase):
    def setUp(self):
        self._original_env = dict(mod.os.environ)

    def tearDown(self):
        mod.os.environ.clear()
        mod.os.environ.update(self._original_env)

    def test_build_dashboard_html_contains_sections(self):
        html = mod.build_dashboard_html(snapshot={
            'db_target': {'mode': 'Staging', 'host': 'staging-db', 'publish_db_name': 'staging_publish', 'agent_db_name': 'staging_agent'},
            'stats': {'total_events': 3, 'total_runs': 1, 'error_events': 0, 'success_events': 2, 'memory_facts': 1, 'request_count': 2, 'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            'runs': [{'run_id': 'run-1', 'event_count': 3, 'success_count': 2, 'error_count': 0, 'request_count': 2, 'total_tokens': 150, 'last_seen': '2026-03-06 00:00:00'}],
            'logs': [{'id': 1, 'run_id': 'run-1', 'step': 'publish', 'status': 'SUCCESS', 'item_slug': 'slug-1', 'message': 'Published', 'details_json': '{"blog_id": 1}', 'request_count': 1, 'total_tokens': 75, 'created_at': '2026-03-06 00:00:00'}],
            'memory': [{'id': 1, 'topic_slug': 'topic', 'category_name': 'Therapeutics', 'memory_key': 'fact', 'confidence': 'high', 'verified_fact': 'Verified fact', 'created_at': '2026-03-06 00:00:00'}],
            'charts': {
                'activity_by_day': [{'label': '2026-03-05', 'total': 3, 'success': 2, 'error': 1}],
                'tokens_by_day': [{'label': '2026-03-05', 'request_count': 2, 'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}],
            },
        })
        self.assertIn('AI Agent Dashboard', html)
        self.assertIn('Staging database', html)
        self.assertIn('staging_publish', html)
        self.assertIn('Dashboard graphs', html)
        self.assertIn('Token usage by day', html)
        self.assertNotIn('Latest blogs', html)
        self.assertIn('Recent agent activity', html)
        self.assertIn('Recent memory facts', html)

    def test_env_flag_supports_zero_and_one_values(self):
        mod.os.environ['DASHBOARD_LOGIN_ENABLED'] = '1'
        self.assertTrue(mod._env_flag('DASHBOARD_LOGIN_ENABLED'))
        mod.os.environ['DASHBOARD_LOGIN_ENABLED'] = '0'
        self.assertFalse(mod._env_flag('DASHBOARD_LOGIN_ENABLED'))

    def test_build_login_html_contains_login_form(self):
        html = mod.build_login_html('Invalid username or password.')
        self.assertIn('<form method=', html)
        self.assertIn('Invalid username or password.', html)
        self.assertIn('name=\'username\'', html)

    def test_is_authenticated_validates_signed_cookie(self):
        config = {'enabled': True, 'username': 'admin', 'password': 'secret', 'secret': 'cookie-secret'}
        cookie = mod.build_session_cookie('admin', config['secret'])
        self.assertTrue(mod.is_authenticated(f'dashboard_session={cookie}', config))
        self.assertFalse(mod.is_authenticated('dashboard_session=admin:bad-signature', config))

    def test_generate_dashboard_html_uses_default_database_selection(self):
        original = mod.agent_db.fetch_dashboard_snapshot
        seen = {}

        def fake_fetch_dashboard_snapshot(**kwargs):
            seen.update(kwargs)
            return {
                'db_target': {'mode': 'Local', 'host': 'localhost', 'publish_db_name': 'local_publish', 'agent_db_name': 'local_agent'},
                'stats': {}, 'runs': [], 'logs': [], 'memory': [], 'charts': {},
            }

        mod.agent_db.fetch_dashboard_snapshot = fake_fetch_dashboard_snapshot
        try:
            html = mod.generate_dashboard_html(1, 1, 1, 1)
        finally:
            mod.agent_db.fetch_dashboard_snapshot = original

        self.assertNotIn('use_staging', seen)
        self.assertIn('Local database', html)

    def test_fetch_dashboard_api_payload_wraps_snapshot(self):
        original = mod.agent_db.fetch_dashboard_snapshot

        def fake_fetch_dashboard_snapshot(**kwargs):
            return {'stats': {'total_events': 4}, 'runs': [], 'logs': [], 'memory': [], 'charts': {}, 'db_target': {'mode': 'Local'}}

        mod.agent_db.fetch_dashboard_snapshot = fake_fetch_dashboard_snapshot
        try:
            payload = mod.fetch_dashboard_api_payload(3, 4, 5, 6)
        finally:
            mod.agent_db.fetch_dashboard_snapshot = original

        self.assertEqual(payload['snapshot']['stats']['total_events'], 4)
        self.assertIn('generated_at', payload)

    def test_build_dashboard_html_supports_json_source_labels(self):
        html = mod.build_dashboard_html(snapshot={
            'db_target': {
                'mode': 'JSON',
                'host': '/tmp/dashboard-json',
                'publish_db_name': 'publish_db',
                'agent_db_name': 'agent_run_logs.json, agent_memory.json',
                'status_label': 'JSON files',
                'source_kind': 'json',
                'source_label': 'agent_run_logs.json and agent_memory.json',
                'host_label': 'Directory',
                'agent_label': 'Files',
            },
            'stats': {}, 'runs': [], 'logs': [], 'memory': [], 'charts': {},
        })
        self.assertIn('JSON files', html)
        self.assertIn('Directory:', html)
        self.assertIn('agent_run_logs.json and agent_memory.json', html)

    def test_fetch_blogs_api_payload_returns_blogs_and_target(self):
        original_fetch = mod.agent_db.fetch_latest_blogs
        original_target = mod.agent_db.db_target_info
        mod.agent_db.fetch_latest_blogs = lambda limit=12: [{'id': 1, 'title': 'Latest'}]
        mod.agent_db.db_target_info = lambda: {'publish_db_name': 'publish_db', 'host': 'localhost'}
        try:
            payload = mod.fetch_blogs_api_payload(limit=5)
        finally:
            mod.agent_db.fetch_latest_blogs = original_fetch
            mod.agent_db.db_target_info = original_target

        self.assertEqual(payload['blogs'][0]['title'], 'Latest')
        self.assertEqual(payload['db_target']['publish_db_name'], 'publish_db')

    def test_fetch_blog_detail_api_payload_raises_for_missing_blog(self):
        original_fetch = mod.agent_db.fetch_blog_detail
        mod.agent_db.fetch_blog_detail = lambda slug: None
        try:
            with self.assertRaises(KeyError):
                mod.fetch_blog_detail_api_payload('missing-blog')
        finally:
            mod.agent_db.fetch_blog_detail = original_fetch

    def test_frontend_asset_path_resolves_safe_files(self):
        asset = mod.frontend_asset_path('/frontend/styles.css')
        self.assertTrue(asset.name.endswith('styles.css'))
        dashboard_asset = mod.frontend_asset_path('/frontend/dashboard.html')
        self.assertTrue(dashboard_asset.name.endswith('dashboard.html'))
        self.assertIsNone(mod.frontend_asset_path('/frontend/../../secret.txt'))

    def test_frontend_pages_include_theme_toggle_assets(self):
        for path in [
            Path('frontend/index.html'),
            Path('frontend/blogs.html'),
            Path('frontend/blog-detail.html'),
            Path('frontend/run-guide.html'),
        ]:
            text = path.read_text(encoding='utf-8')
            self.assertIn('theme-toggle', text)
            self.assertIn('health-agent-theme', text)
        app_text = Path('frontend/app.js').read_text(encoding='utf-8')
        self.assertIn('THEME_STORAGE_KEY', app_text)
        self.assertIn('initThemeToggle()', app_text)
        self.assertIn('page === "run-guide"', app_text)

    def test_frontend_metric_and_chart_enhancements_exist(self):
        app_text = Path('frontend/app.js').read_text(encoding='utf-8')
        css_text = Path('frontend/styles.css').read_text(encoding='utf-8')
        self.assertIn('metric-card-head', app_text)
        self.assertIn('dashboardChartSeries()', app_text)
        self.assertIn('--chart-total', css_text)
        self.assertIn('.metric-icon', css_text)
        self.assertIn('@keyframes border-shift', css_text)

    def test_dashboard_auto_refresh_and_live_summary_exist(self):
        index_text = Path('frontend/index.html').read_text(encoding='utf-8')
        app_text = Path('frontend/app.js').read_text(encoding='utf-8')
        css_text = Path('frontend/styles.css').read_text(encoding='utf-8')
        self.assertIn('dashboard-header-meta', index_text)
        self.assertIn('refresh-countdown', index_text)
        self.assertIn('30s', index_text)
        self.assertNotIn('dashboard-refresh-button', index_text)
        self.assertNotIn('Data source', index_text)
        self.assertNotIn('Host', index_text)
        self.assertNotIn('>Refresh<', index_text)
        self.assertNotIn('Total tokens', index_text)
        self.assertNotIn('Dashboard health', index_text)
        self.assertNotIn('Health AI agent dashboard', index_text)
        self.assertIn('DASHBOARD_REFRESH_INTERVAL_MS = 30000', app_text)
        self.assertNotIn('Prompt tokens', app_text)
        self.assertNotIn('Completion tokens', app_text)
        self.assertNotIn('Total tokens', app_text)
        self.assertIn('initDashboardAutoRefresh()', app_text)
        self.assertIn('refreshDashboardData({ background: true })', app_text)
        self.assertIn('.dashboard-header-meta', css_text)
        self.assertIn('.dashboard-live-pill', css_text)
        self.assertIn('body[data-page="dashboard"] .shell', css_text)


if __name__ == '__main__':
    unittest.main()
