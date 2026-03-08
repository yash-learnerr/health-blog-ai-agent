import importlib.util
import unittest
from unittest import mock
from pathlib import Path


spec = importlib.util.spec_from_file_location('run_workflow', Path('scripts/run_workflow.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RunWorkflowTests(unittest.TestCase):
    def test_extract_image_url_prefers_open_graph_and_twitter_tags(self):
        html_text = '''
        <html><head>
        <meta property="og:image" content="https://cdn.example.com/cover-og.jpg">
        <meta name="twitter:image" content="https://cdn.example.com/cover-twitter.jpg">
        </head></html>
        '''
        self.assertEqual(mod.extract_image_url(html_text), 'https://cdn.example.com/cover-og.jpg')

    def test_publish_blog_stores_uploaded_image_url_in_file_column(self):
        original_category_id_for = mod.category_id_for
        original_upload_blog_image = mod.blog_file_manager.upload_blog_image
        original_database_access = mod.agent_db.database_access
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_query_rows = mod.agent_db._query_rows
        original_safe_log_event = mod.agent_db.safe_log_event

        captured = {}
        mod.category_id_for = lambda blog: 9
        mod.blog_file_manager.upload_blog_image = lambda blog: ('blog-master/cover.jpg', 'https://cdn.example.com/blog-master/cover.jpg')
        mod.agent_db.database_access = lambda use_staging=None: 'local'
        mod.agent_db.publish_db_name = lambda: 'mydrscripts_new'
        mod.agent_db._table_columns = lambda db, table: {
            'createdAt', 'updatedAt', 'category_id', 'blog_name', 'meta_title',
            'description', 'meta_description', 'meta_tags', 'file', 'status', 'slug',
        }
        mod.agent_db.safe_log_event = lambda *args, **kwargs: True

        def fake_query_rows(sql, expected_cols):
            captured['sql'] = sql
            return [['123']]

        mod.agent_db._query_rows = fake_query_rows
        try:
            blog_id = mod.publish_blog(
                'run-1',
                {
                    'slug': 'sample-slug',
                    'title': 'Sample title',
                    'summary': 'Summary',
                    'content': 'Body',
                    'keywords': ['one', 'two', 'three', 'four', 'five'],
                    'source_url': 'https://www.who.int/news/item/sample',
                    'image_source_url': 'https://www.who.int/images/sample.jpg',
                },
            )
        finally:
            mod.category_id_for = original_category_id_for
            mod.blog_file_manager.upload_blog_image = original_upload_blog_image
            mod.agent_db.database_access = original_database_access
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.agent_db._query_rows = original_query_rows
            mod.agent_db.safe_log_event = original_safe_log_event

        self.assertEqual(blog_id, 123)
        self.assertIn('file', captured['sql'])
        self.assertIn('blog_name', captured['sql'])
        self.assertIn('meta_description', captured['sql'])
        self.assertIn('meta_tags', captured['sql'])
        self.assertIn(mod.agent_db._b64('https://cdn.example.com/blog-master/cover.jpg'), captured['sql'])

    def test_publish_blog_stores_relative_file_key_in_staging(self):
        original_category_id_for = mod.category_id_for
        original_upload_blog_image = mod.blog_file_manager.upload_blog_image
        original_database_access = mod.agent_db.database_access
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_query_rows = mod.agent_db._query_rows
        original_safe_log_event = mod.agent_db.safe_log_event

        captured = {}
        mod.category_id_for = lambda blog: 9
        mod.blog_file_manager.upload_blog_image = lambda blog: (
            'blog-master/cover.jpg',
            'https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/cover.jpg',
        )
        mod.agent_db.database_access = lambda use_staging=None: 'staging'
        mod.agent_db.publish_db_name = lambda: 'mydrscripts_new'
        mod.agent_db._table_columns = lambda db, table: {
            'createdAt', 'updatedAt', 'category_id', 'blog_name', 'meta_title',
            'description', 'meta_description', 'meta_tags', 'file', 'status', 'slug',
        }
        mod.agent_db.safe_log_event = lambda *args, **kwargs: True

        def fake_query_rows(sql, expected_cols):
            captured['sql'] = sql
            return [['125']]

        mod.agent_db._query_rows = fake_query_rows
        try:
            blog_id = mod.publish_blog(
                'run-3',
                {
                    'slug': 'sample-slug',
                    'title': 'Sample title',
                    'summary': 'Summary',
                    'content': 'Body',
                    'keywords': ['one', 'two', 'three', 'four', 'five'],
                    'source_url': 'https://www.who.int/news/item/sample',
                    'image_source_url': 'https://www.who.int/images/sample.jpg',
                },
            )
        finally:
            mod.category_id_for = original_category_id_for
            mod.blog_file_manager.upload_blog_image = original_upload_blog_image
            mod.agent_db.database_access = original_database_access
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.agent_db._query_rows = original_query_rows
            mod.agent_db.safe_log_event = original_safe_log_event

        self.assertEqual(blog_id, 125)
        self.assertIn(mod.agent_db._b64('blog_master/cover.jpg'), captured['sql'])
        self.assertNotIn(mod.agent_db._b64('https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/cover.jpg'), captured['sql'])

    def test_publish_blog_falls_back_to_source_image_url_when_upload_fails(self):
        original_category_id_for = mod.category_id_for
        original_upload_blog_image = mod.blog_file_manager.upload_blog_image
        original_database_access = mod.agent_db.database_access
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_query_rows = mod.agent_db._query_rows
        original_safe_log_event = mod.agent_db.safe_log_event

        captured = {'logs': []}
        mod.category_id_for = lambda blog: 9
        mod.blog_file_manager.upload_blog_image = lambda blog: (_ for _ in ()).throw(RuntimeError('upload unavailable'))
        mod.agent_db.database_access = lambda use_staging=None: 'local'
        mod.agent_db.publish_db_name = lambda: 'mydrscripts_new'
        mod.agent_db._table_columns = lambda db, table: {
            'createdAt', 'updatedAt', 'category_id', 'blog_name', 'meta_title',
            'description', 'meta_description', 'meta_tags', 'file', 'status', 'slug',
        }
        mod.agent_db.safe_log_event = lambda *args, **kwargs: captured['logs'].append((args, kwargs)) or True

        def fake_query_rows(sql, expected_cols):
            captured['sql'] = sql
            return [['124']]

        mod.agent_db._query_rows = fake_query_rows
        try:
            blog_id = mod.publish_blog(
                'run-2',
                {
                    'slug': 'sample-slug',
                    'title': 'Sample title',
                    'summary': 'Summary',
                    'content': 'Body',
                    'keywords': ['one', 'two', 'three', 'four', 'five'],
                    'source_url': 'https://www.who.int/news/item/sample',
                    'image_source_url': 'https://www.who.int/images/sample.jpg',
                },
            )
        finally:
            mod.category_id_for = original_category_id_for
            mod.blog_file_manager.upload_blog_image = original_upload_blog_image
            mod.agent_db.database_access = original_database_access
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.agent_db._query_rows = original_query_rows
            mod.agent_db.safe_log_event = original_safe_log_event

        self.assertEqual(blog_id, 124)
        self.assertIn('file', captured['sql'])
        self.assertIn(mod.agent_db._b64('https://www.who.int/images/sample.jpg'), captured['sql'])
        self.assertTrue(any('Image upload failed' in args[3] for args, _kwargs in captured['logs']))

    def test_duplicate_exists_skips_source_url_lookup_when_schema_has_no_source_column(self):
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_query_rows = mod.agent_db._query_rows
        captured = {'queries': []}
        mod.agent_db.publish_db_name = lambda: 'mydrscripts_new'
        mod.agent_db._table_columns = lambda db, table: {'blog_name', 'slug', 'status'}

        def fake_query_rows(sql, expected_cols):
            captured['queries'].append(sql)
            return []

        mod.agent_db._query_rows = fake_query_rows
        try:
            result = mod.duplicate_exists('sample-slug', 'https://example.com/source')
        finally:
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.agent_db._query_rows = original_query_rows

        self.assertEqual(result, (False, ''))
        self.assertEqual(len(captured['queries']), 1)
        self.assertIn('WHERE BINARY slug = BINARY', captured['queries'][0])
        self.assertNotIn('source_url', captured['queries'][0])

    def test_category_id_for_uses_name_column_for_new_schema(self):
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_query_rows = mod.agent_db._query_rows
        original_mysql = mod.agent_db.mysql
        captured = {}
        mod.agent_db.publish_db_name = lambda: 'mydrscripts_new'
        mod.agent_db._table_columns = lambda db, table: {'createdAt', 'updatedAt', 'id', 'name', 'status'}

        def fake_query_rows(sql, expected_cols):
            captured.setdefault('queries', []).append(sql)
            if 'SELECT id FROM blog_category' in sql:
                return []
            return [['9']]

        mod.agent_db._query_rows = fake_query_rows
        mod.agent_db.mysql = lambda sql: captured.setdefault('updates', []).append(sql)
        try:
            category_id = mod.category_id_for({'category_name': 'Medical Research', 'category_slug': 'medical-research'})
        finally:
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.agent_db._query_rows = original_query_rows
            mod.agent_db.mysql = original_mysql

        self.assertEqual(category_id, 9)
        self.assertEqual(len(captured['queries']), 2)
        self.assertIn('SELECT id FROM blog_category', captured['queries'][0])
        self.assertIn('INSERT INTO blog_category (`name`, `status`, `createdAt`, `updatedAt`)', captured['queries'][1])
        self.assertNotIn('category_slug', captured['queries'][1])
        self.assertEqual(captured.get('updates'), None)

    def test_category_id_for_reuses_existing_category_before_insert(self):
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_query_rows = mod.agent_db._query_rows
        original_mysql = mod.agent_db.mysql
        captured = {}
        mod.agent_db.publish_db_name = lambda: 'mydrscripts_new'
        mod.agent_db._table_columns = lambda db, table: {'createdAt', 'updatedAt', 'id', 'name', 'status', 'category_slug'}

        def fake_query_rows(sql, expected_cols):
            captured.setdefault('queries', []).append(sql)
            if 'SELECT id FROM blog_category' in sql:
                return [['4']]
            raise AssertionError('insert should not be attempted when category already exists')

        mod.agent_db._query_rows = fake_query_rows
        mod.agent_db.mysql = lambda sql: captured.setdefault('updates', []).append(sql)
        try:
            category_id = mod.category_id_for({'category_name': '  Medical   Research  ', 'category_slug': 'medical-research'})
        finally:
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.agent_db._query_rows = original_query_rows
            mod.agent_db.mysql = original_mysql

        self.assertEqual(category_id, 4)
        self.assertEqual(len(captured['queries']), 1)
        self.assertIn('SELECT id FROM blog_category', captured['queries'][0])
        self.assertIn(mod.agent_db._b64('medical-research'), captured['queries'][0])
        self.assertIn(mod.agent_db._b64('Medical Research'), captured['updates'][0])
        self.assertIn('UPDATE blog_category SET', captured['updates'][0])

    def test_fetch_recent_news_broadens_when_first_candidates_are_only_duplicates(self):
        source = mod.SourceConfig('WHO', 'https://feeds.example.com/who.xml', 'https://www.who.int/news', 1)
        duplicate_article = mod.Article(
            title='Duplicate article',
            url='https://example.com/duplicate',
            source='WHO',
            published_at=mod.now_utc(),
            description='Duplicate candidate description',
            source_feed_url=source.feed_url,
            tier=1,
        )
        fresh_article = mod.Article(
            title='Fresh article',
            url='https://example.com/fresh',
            source='WHO',
            published_at=mod.now_utc(),
            description='Fresh candidate description',
            source_feed_url=source.feed_url,
            tier=1,
        )
        articles_by_window = {
            24: [],
            72: [duplicate_article],
            168: [duplicate_article, fresh_article],
        }
        captured_logs = []

        with mock.patch.object(mod, 'source_configs', return_value=[source]):
            with mock.patch.object(mod, 'fetch_url', return_value='<rss />'):
                with mock.patch.object(mod, 'parse_feed_items', side_effect=lambda _source, _xml_text, window: list(articles_by_window[window])):
                    with mock.patch.object(mod, 'duplicate_exists', side_effect=lambda _slug, source_url: (source_url.endswith('/duplicate'), 'slug match' if source_url.endswith('/duplicate') else '')):
                        with mock.patch.object(mod.agent_db, 'safe_log_event', side_effect=lambda *args, **kwargs: captured_logs.append((args, kwargs)) or True):
                            articles = mod.fetch_recent_news('run-1', recency_hours=24)

        self.assertEqual(sorted(article.url for article in articles), ['https://example.com/duplicate', 'https://example.com/fresh'])
        messages = [args[3] for args, _kwargs in captured_logs]
        self.assertIn('No items found within 24h; broadened window to 72h.', messages)
        self.assertIn('Only duplicate candidates found within 72h; broadened window to 168h.', messages)
        self.assertIn('Fetched 2 candidate articles.', messages)

    def test_fetch_recent_news_returns_last_candidates_when_all_windows_are_duplicates(self):
        source = mod.SourceConfig('WHO', 'https://feeds.example.com/who.xml', 'https://www.who.int/news', 1)
        duplicate_article = mod.Article(
            title='Duplicate article',
            url='https://example.com/duplicate',
            source='WHO',
            published_at=mod.now_utc(),
            description='Duplicate candidate description',
            source_feed_url=source.feed_url,
            tier=1,
        )
        articles_by_window = {
            24: [],
            72: [duplicate_article],
            168: [duplicate_article],
        }
        captured_logs = []

        with mock.patch.object(mod, 'source_configs', return_value=[source]):
            with mock.patch.object(mod, 'fetch_url', return_value='<rss />'):
                with mock.patch.object(mod, 'parse_feed_items', side_effect=lambda _source, _xml_text, window: list(articles_by_window[window])):
                    with mock.patch.object(mod, 'duplicate_exists', return_value=(True, 'slug match')):
                        with mock.patch.object(mod.agent_db, 'safe_log_event', side_effect=lambda *args, **kwargs: captured_logs.append((args, kwargs)) or True):
                            articles = mod.fetch_recent_news('run-2', recency_hours=24)

        self.assertEqual([article.url for article in articles], ['https://example.com/duplicate'])
        messages = [args[3] for args, _kwargs in captured_logs]
        self.assertIn('Fetched 1 candidate articles, but none were new after duplicate screening.', messages)

    def test_fetch_memory_context_delegates_to_agent_db_helper(self):
        with mock.patch.object(mod.agent_db, 'fetch_memory_context', return_value=[{'memory_key': 'fact-1'}]) as helper:
            rows = mod.fetch_memory_context()
        helper.assert_called_once_with(limit=50)
        self.assertEqual(rows, [{'memory_key': 'fact-1'}])

    def test_store_memory_delegates_to_agent_db_storage_helper(self):
        captured = []
        blog = {
            'slug': 'sample-topic',
            'category_name': 'Medical Research',
            'source_url': 'https://example.com/topic',
            'research': {
                'confirmed_findings': [
                    {'claim': 'Fact one', 'confidence': 'high'},
                    {'claim': 'Fact two', 'confidence': 'medium'},
                ]
            },
        }

        with mock.patch.object(mod.agent_db, 'store_memory_fact', side_effect=lambda **kwargs: captured.append(kwargs)) as helper:
            facts = mod.store_memory(blog)

        self.assertEqual(len(facts), 2)
        self.assertEqual(len(captured), 2)
        helper.assert_called()
        self.assertEqual(captured[0]['topic_slug'], 'sample-topic')
        self.assertEqual(captured[0]['memory_key'], 'sample-topic-fact-1')
        self.assertEqual(captured[0]['status'], 'active')

    def test_ensure_publish_tables_skips_operational_db_init_in_json_mode(self):
        original_publish_db_name = mod.agent_db.publish_db_name
        original_operational_storage_backend = mod.agent_db.operational_storage_backend
        original_mysql = mod.agent_db.mysql
        original_migrate_publish_tables = mod.migrate_publish_tables
        original_ensure_operational_tables = mod.agent_db.ensure_operational_tables
        captured = {}

        mod.agent_db.publish_db_name = lambda: 'publish_db'
        mod.agent_db.operational_storage_backend = lambda: mod.agent_db.STORAGE_BACKEND_JSON
        mod.agent_db.mysql = lambda sql: captured.setdefault('sql', sql)
        mod.migrate_publish_tables = lambda publish_db=None: captured.setdefault('publish_db', publish_db)
        mod.agent_db.ensure_operational_tables = lambda: (_ for _ in ()).throw(AssertionError('should not initialize operational tables in json mode'))
        try:
            mod.ensure_publish_tables()
        finally:
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db.operational_storage_backend = original_operational_storage_backend
            mod.agent_db.mysql = original_mysql
            mod.migrate_publish_tables = original_migrate_publish_tables
            mod.agent_db.ensure_operational_tables = original_ensure_operational_tables

        self.assertIn('CREATE DATABASE IF NOT EXISTS `publish_db`;', captured['sql'])
        self.assertNotIn('health_ai_agent', captured['sql'])
        self.assertEqual(captured['publish_db'], 'publish_db')


if __name__ == '__main__':
    unittest.main()
