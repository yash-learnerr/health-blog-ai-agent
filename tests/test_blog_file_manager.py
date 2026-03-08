import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('blog_file_manager', Path('scripts/blog_file_manager.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class BlogFileManagerTests(unittest.TestCase):
    def setUp(self):
        self._original_env = dict(mod.os.environ)

    def tearDown(self):
        mod.os.environ.clear()
        mod.os.environ.update(self._original_env)

    def test_build_file_key_uses_prefix_and_extension(self):
        mod.os.environ['SPACES_PREFIX'] = 'blog-master'
        key = mod.build_file_key('who-guideline-mercury-free')
        self.assertTrue(key.startswith('blog-master/'))
        self.assertTrue(key.endswith('.html'))
        self.assertIn('who-guideline-mercury-free', key)

    def test_content_to_html_converts_markdown_to_html(self):
        html_text = mod.content_to_html('# Title\n\nParagraph with **bold** text.\n\n- Item 1\n- Item 2')
        self.assertIn('<h1>Title</h1>', html_text)
        self.assertIn('<p>Paragraph with <strong>bold</strong> text.</p>', html_text)
        self.assertIn('<ul><li>Item 1</li><li>Item 2</li></ul>', html_text)

    def test_render_html_contains_title_summary_and_html_body(self):
        html_bytes = mod.render_html('Title', 'Summary', '## Section\n\nLine 1\n\nLine 2')
        html_text = html_bytes.decode('utf-8')
        self.assertIn('<h1>Title</h1>', html_text)
        self.assertIn('<p>Summary</p>', html_text)
        self.assertIn('<h2>Section</h2>', html_text)
        self.assertIn('<p>Line 1</p>', html_text)
        self.assertIn('<p>Line 2</p>', html_text)

    def test_build_public_file_url_prefers_bucket_url(self):
        mod.os.environ['DO_SPACES_BUCKET_URL'] = 'https://example-bucket.nyc3.digitaloceanspaces.com'
        self.assertEqual(
            mod.build_public_file_url('blog-master/test-file.html'),
            'https://example-bucket.nyc3.digitaloceanspaces.com/blog-master/test-file.html',
        )

    def test_build_public_asset_url_prefers_cdn_url(self):
        mod.os.environ['CDN_URL'] = 'https://cdn.example.com'
        mod.os.environ['DO_SPACES_BUCKET_URL'] = 'https://example-bucket.nyc3.digitaloceanspaces.com'
        self.assertEqual(
            mod.build_public_asset_url('blog-master/test-file.jpg'),
            'https://cdn.example.com/blog-master/test-file.jpg',
        )

    def test_build_blog_insert_statement_uses_html_and_uploaded_file_url(self):
        query, params = mod.build_blog_insert_statement(
            {
                'createdAt', 'updatedAt', 'category_id', 'blog_name', 'slug', 'meta_title',
                'description', 'meta_description', 'meta_tags', 'status', 'file', 'image',
            },
            {
                'category_id': 10,
                'title': 'Sample',
                'slug': 'sample',
                'summary': 'Summary',
                'content': '# Heading\n\nBody',
                'keywords': ['one', 'two'],
            },
            123,
            file_url='https://files.example/sample.html',
            image_url='https://cdn.example/default.jpg',
        )
        self.assertIn('INSERT INTO blog_master', query)
        self.assertIn('file', query)
        self.assertIn('image', query)
        self.assertTrue(any(isinstance(value, str) and '<h1>Heading</h1>' in value for value in params))
        self.assertIn('https://files.example/sample.html', params)
        self.assertIn('https://cdn.example/default.jpg', params)

    def test_build_blog_insert_statement_requires_file_url_when_file_column_exists(self):
        with self.assertRaisesRegex(RuntimeError, 'missing generated file URL'):
            mod.build_blog_insert_statement(
                {
                    'createdAt', 'updatedAt', 'category_id', 'blog_name', 'slug', 'meta_title',
                    'description', 'meta_description', 'meta_tags', 'status', 'file',
                },
                {
                    'category_id': 10,
                    'title': 'Sample',
                    'slug': 'sample',
                    'summary': 'Summary',
                    'content': 'Body',
                    'keywords': ['one'],
                },
                123,
                file_url=None,
            )

    def test_build_blog_insert_statement_stores_relative_file_key_outside_local(self):
        original_database_access = mod.agent_db.database_access
        mod.agent_db.database_access = lambda use_staging=None: 'staging'
        try:
            _query, params = mod.build_blog_insert_statement(
                {
                    'createdAt', 'updatedAt', 'category_id', 'blog_name', 'slug', 'meta_title',
                    'description', 'meta_description', 'meta_tags', 'status', 'file',
                },
                {
                    'category_id': 10,
                    'title': 'Sample',
                    'slug': 'sample',
                    'summary': 'Summary',
                    'content': 'Body',
                    'keywords': ['one'],
                },
                123,
                file_url='https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/example.png',
            )
        finally:
            mod.agent_db.database_access = original_database_access

        self.assertIn('blog_master/example.png', params)
        self.assertNotIn('https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/example.png', params)

    def test_build_blog_insert_statement_omits_file_when_schema_has_no_file_column(self):
        query, params = mod.build_blog_insert_statement(
            {
                'createdAt', 'updatedAt', 'category_id', 'blog_name', 'slug', 'meta_title',
                'description', 'meta_description', 'meta_tags', 'status',
            },
            {
                'category_id': 10,
                'title': 'Sample',
                'slug': 'sample',
                'summary': 'Summary',
                'content': 'Body',
                'keywords': ['one'],
            },
            123,
            file_url=None,
        )
        self.assertNotIn('file', query)
        self.assertFalse(any(isinstance(value, str) and value.startswith('https://') for value in params[-1:]))

    def test_upload_blog_image_returns_none_when_no_image_source_exists(self):
        self.assertEqual(mod.upload_blog_image({'slug': 'sample'}), (None, None))

    def test_upload_blog_image_uses_temp_upload_and_move_flow_for_local_file(self):
        original_upload_temp = mod.upload_temp_file_to_app
        original_move_temp = mod.move_temp_file_to_blog_folder
        captured = {}

        def fake_upload_temp(filename, body, content_type):
            captured['upload'] = (filename, body, content_type)
            return 'tmp/cover.jpg'

        def fake_move_temp(file_key, folder=None):
            captured['move'] = (file_key, folder)
            return 'https://cdn.example/blog-master/cover.jpg'

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / 'cover.jpg'
            image_path.write_bytes(b'jpeg-bytes')
            mod.upload_temp_file_to_app = fake_upload_temp
            mod.move_temp_file_to_blog_folder = fake_move_temp
            try:
                result = mod.upload_blog_image({'slug': 'sample', 'image_path': str(image_path)})
            finally:
                mod.upload_temp_file_to_app = original_upload_temp
                mod.move_temp_file_to_blog_folder = original_move_temp
        self.assertEqual(result, ('tmp/cover.jpg', 'https://cdn.example/blog-master/cover.jpg'))
        self.assertEqual(captured['upload'][0], 'cover.jpg')
        self.assertEqual(captured['upload'][1], b'jpeg-bytes')
        self.assertEqual(captured['move'], ('tmp/cover.jpg', None))

    def test_upload_blog_image_falls_back_to_spaces_when_app_upload_route_fails(self):
        original_upload_temp = mod.upload_temp_file_to_app
        original_upload_spaces_asset = mod.upload_asset_to_spaces

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / 'cover.jpg'
            image_path.write_bytes(b'jpeg-bytes')
            mod.upload_temp_file_to_app = lambda filename, body, content_type: (_ for _ in ()).throw(RuntimeError('server down'))
            mod.upload_asset_to_spaces = lambda filename, body, content_type, folder=None: ('blog-master/fallback-cover.jpg', 'https://cdn.example/blog-master/fallback-cover.jpg')
            try:
                result = mod.upload_blog_image({'slug': 'sample', 'image_path': str(image_path)})
            finally:
                mod.upload_temp_file_to_app = original_upload_temp
                mod.upload_asset_to_spaces = original_upload_spaces_asset

        self.assertEqual(result, ('blog-master/fallback-cover.jpg', 'https://cdn.example/blog-master/fallback-cover.jpg'))

    def test_update_file_updates_file_url_and_optional_image(self):
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_mysql = mod.mysql
        mod.agent_db.publish_db_name = lambda: 'publish_db'
        mod.agent_db._table_columns = lambda db, table: {'file', 'updatedAt', 'image'}
        captured = {}
        mod.mysql = lambda sql: captured.setdefault('sql', sql) or sql
        try:
            mod.update_file(42, 'https://files.example/blog.html', 'https://cdn.example/default.jpg')
        finally:
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.mysql = original_mysql
        self.assertIn(mod.b64('https://files.example/blog.html'), captured['sql'])
        self.assertIn(mod.b64('https://cdn.example/default.jpg'), captured['sql'])
        self.assertIn('UPDATE blog_master SET', captured['sql'])
        self.assertNotIn('COALESCE(NULLIF', captured['sql'])

    def test_update_file_requires_generated_file_url_when_file_column_exists(self):
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        mod.agent_db.publish_db_name = lambda: 'publish_db'
        mod.agent_db._table_columns = lambda db, table: {'file', 'updatedAt'}
        try:
            with self.assertRaisesRegex(RuntimeError, 'missing generated file URL'):
                mod.update_file(42, None)
        finally:
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns

    def test_update_file_stores_relative_file_key_outside_local(self):
        original_publish_db_name = mod.agent_db.publish_db_name
        original_table_columns = mod.agent_db._table_columns
        original_database_access = mod.agent_db.database_access
        original_mysql = mod.mysql
        mod.agent_db.publish_db_name = lambda: 'publish_db'
        mod.agent_db._table_columns = lambda db, table: {'file', 'updatedAt'}
        mod.agent_db.database_access = lambda use_staging=None: 'production'
        captured = {}
        mod.mysql = lambda sql: captured.setdefault('sql', sql) or sql
        try:
            mod.update_file(42, 'https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/example.png')
        finally:
            mod.agent_db.publish_db_name = original_publish_db_name
            mod.agent_db._table_columns = original_table_columns
            mod.agent_db.database_access = original_database_access
            mod.mysql = original_mysql

        self.assertIn(mod.b64('blog_master/example.png'), captured['sql'])
        self.assertNotIn(mod.b64('https://mydrscript-staging-bucket.syd1.digitaloceanspaces.com/blog-master/example.png'), captured['sql'])

    def test_resolve_spaces_host_supports_do_spaces_bucket_url(self):
        mod.os.environ.pop('SPACES_BUCKET_URL', None)
        mod.os.environ['DO_SPACES_BUCKET_URL'] = 'https://example-bucket.nyc3.digitaloceanspaces.com'
        self.assertEqual(mod.resolve_spaces_host(), 'example-bucket.nyc3.digitaloceanspaces.com')

    def test_upload_temp_file_to_app_posts_multipart_and_reads_file_key(self):
        original_urlopen = mod.urlopen
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({'data': {'file_key': 'temp/cover.jpg'}}).encode('utf-8')

        def fake_urlopen(req):
            captured['url'] = req.full_url
            captured['headers'] = dict(req.header_items())
            captured['body'] = req.data
            return FakeResponse()

        mod.os.environ.pop('BLOG_IMAGE_API_BASE_URL', None)
        mod.os.environ['API_URL'] = 'http://192.168.1.38:1338'
        mod.urlopen = fake_urlopen
        try:
            file_key = mod.upload_temp_file_to_app('cover.jpg', b'image-bytes', 'image/jpeg')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(file_key, 'temp/cover.jpg')
        self.assertEqual(captured['url'], 'http://192.168.1.38:1338/api/doctor/upload-temp-file')
        self.assertIn('multipart/form-data', captured['headers']['Content-type'])
        self.assertIn(b'name="file"; filename="cover.jpg"', captured['body'])
        self.assertIn(b'image-bytes', captured['body'])

    def test_upload_temp_file_to_app_uses_api_url_when_specific_base_not_set(self):
        original_urlopen = mod.urlopen
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({'file_key': 'temp/from-api-url.jpg'}).encode('utf-8')

        def fake_urlopen(req):
            captured['url'] = req.full_url
            return FakeResponse()

        mod.os.environ.pop('BLOG_IMAGE_API_BASE_URL', None)
        mod.os.environ['API_URL'] = 'http://192.168.1.38:1338/api/'
        mod.urlopen = fake_urlopen
        try:
            file_key = mod.upload_temp_file_to_app('cover.jpg', b'image-bytes', 'image/jpeg')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(file_key, 'temp/from-api-url.jpg')
        self.assertEqual(captured['url'], 'http://192.168.1.38:1338/api/doctor/upload-temp-file')

    def test_upload_temp_file_to_app_keeps_api_url_when_it_already_contains_api_path(self):
        original_urlopen = mod.urlopen
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({'file_key': 'temp/from-api-path.jpg'}).encode('utf-8')

        def fake_urlopen(req):
            captured['url'] = req.full_url
            return FakeResponse()

        mod.os.environ.pop('BLOG_IMAGE_API_BASE_URL', None)
        mod.os.environ['API_URL'] = 'http://192.168.1.38:1338/api/'
        mod.urlopen = fake_urlopen
        try:
            file_key = mod.upload_temp_file_to_app('cover.jpg', b'image-bytes', 'image/jpeg')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(file_key, 'temp/from-api-path.jpg')
        self.assertEqual(captured['url'], 'http://192.168.1.38:1338/api/doctor/upload-temp-file')

    def test_move_temp_file_to_blog_folder_uses_api_url_route_when_configured(self):
        original_urlopen = mod.urlopen
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({'url': 'https://cdn.example/blog-master/cover.jpg'}).encode('utf-8')

        def fake_urlopen(req):
            captured['url'] = req.full_url
            captured['headers'] = dict(req.header_items())
            captured['body'] = json.loads(req.data.decode('utf-8'))
            return FakeResponse()

        mod.os.environ.pop('BLOG_IMAGE_API_BASE_URL', None)
        mod.os.environ['API_URL'] = 'http://192.168.1.38:1338'
        mod.os.environ['BLOG_IMAGE_MOVE_PATH'] = 'doctor/move-temp-file'
        mod.urlopen = fake_urlopen
        try:
            image_url = mod.move_temp_file_to_blog_folder('temp/cover.jpg')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(image_url, 'https://cdn.example/blog-master/cover.jpg')
        self.assertEqual(captured['url'], 'http://192.168.1.38:1338/api/doctor/move-temp-file')
        self.assertEqual(captured['headers']['Content-type'], 'application/json')
        self.assertEqual(captured['body'], {'file_key': 'temp/cover.jpg', 'folder': 'blog-master', 'is_public': True})

    def test_move_temp_file_to_blog_folder_keeps_api_url_when_it_already_contains_api_path(self):
        original_urlopen = mod.urlopen
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({'url': 'https://cdn.example/blog-master/cover.jpg'}).encode('utf-8')

        def fake_urlopen(req):
            captured['url'] = req.full_url
            return FakeResponse()

        mod.os.environ.pop('BLOG_IMAGE_API_BASE_URL', None)
        mod.os.environ['API_URL'] = 'http://192.168.1.38:1338/api/'
        mod.os.environ['BLOG_IMAGE_MOVE_PATH'] = 'doctor/move-temp-file'
        mod.urlopen = fake_urlopen
        try:
            image_url = mod.move_temp_file_to_blog_folder('temp/cover.jpg')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(image_url, 'https://cdn.example/blog-master/cover.jpg')
        self.assertEqual(captured['url'], 'http://192.168.1.38:1338/api/doctor/move-temp-file')

    def test_move_temp_file_to_blog_folder_falls_back_to_spaces_when_api_route_fails(self):
        original_urlopen = mod.urlopen
        calls = []

        class FakeResponse:
            def __init__(self, status, body=b''):
                self.status = status
                self._body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self._body

        def fake_urlopen(req):
            if 'doctor/move-temp-file' in req.full_url:
                raise RuntimeError('app route unavailable')
            calls.append({
                'url': req.full_url,
                'headers': {key.lower(): value for key, value in dict(req.header_items()).items()},
                'method': req.get_method(),
            })
            if len(calls) == 1:
                return FakeResponse(200, b'<CopyObjectResult/>')
            return FakeResponse(204, b'')

        mod.os.environ['API_URL'] = 'http://192.168.1.38:1338'
        mod.os.environ['BLOG_IMAGE_MOVE_PATH'] = 'doctor/move-temp-file'
        mod.os.environ['DO_SPACES_KEY'] = 'key'
        mod.os.environ['DO_SPACES_SECRET'] = 'secret'
        mod.os.environ['DO_SPACES_BUCKET'] = 'example-bucket'
        mod.os.environ['DO_SPACES_BUCKET_URL'] = 'https://example-bucket.nyc3.digitaloceanspaces.com'
        mod.os.environ['DO_SPACES_REGION'] = 'nyc3'
        mod.urlopen = fake_urlopen
        try:
            image_url = mod.move_temp_file_to_blog_folder('temp/cover.jpg')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(image_url, 'https://example-bucket.nyc3.digitaloceanspaces.com/blog-master/cover.jpg')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['method'], 'PUT')
        self.assertEqual(calls[1]['method'], 'DELETE')

    def test_move_temp_file_to_blog_folder_moves_object_in_spaces_and_returns_public_url(self):
        original_urlopen = mod.urlopen
        calls = []

        class FakeResponse:
            def __init__(self, status, body=b''):
                self.status = status
                self._body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self._body

        def fake_urlopen(req):
            calls.append({
                'url': req.full_url,
                'headers': {key.lower(): value for key, value in dict(req.header_items()).items()},
                'method': req.get_method(),
            })
            if len(calls) == 1:
                return FakeResponse(200, b'<CopyObjectResult/>')
            return FakeResponse(204, b'')

        mod.os.environ.pop('BLOG_IMAGE_MOVE_PATH', None)
        mod.os.environ.pop('BLOG_IMAGE_MOVE_URL', None)
        mod.os.environ['DO_SPACES_KEY'] = 'key'
        mod.os.environ['DO_SPACES_SECRET'] = 'secret'
        mod.os.environ['DO_SPACES_BUCKET'] = 'example-bucket'
        mod.os.environ['DO_SPACES_BUCKET_URL'] = 'https://example-bucket.nyc3.digitaloceanspaces.com'
        mod.os.environ['DO_SPACES_REGION'] = 'nyc3'
        mod.urlopen = fake_urlopen
        try:
            image_url = mod.move_temp_file_to_blog_folder('temp/cover.jpg')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(image_url, 'https://example-bucket.nyc3.digitaloceanspaces.com/blog-master/cover.jpg')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['method'], 'PUT')
        self.assertEqual(calls[0]['url'], 'https://example-bucket.nyc3.digitaloceanspaces.com/blog-master/cover.jpg')
        self.assertEqual(calls[0]['headers']['x-amz-copy-source'], '/example-bucket/temp/cover.jpg')
        self.assertEqual(calls[0]['headers']['x-amz-acl'], 'public-read')
        self.assertEqual(calls[1]['method'], 'DELETE')
        self.assertEqual(calls[1]['url'], 'https://example-bucket.nyc3.digitaloceanspaces.com/temp/cover.jpg')

    def test_extract_temp_file_key_accepts_temp_url(self):
        self.assertEqual(
            mod.extract_temp_file_key('https://cdn.example.com/temp/path/file.png?token=123'),
            'temp/path/file.png',
        )

    def test_upload_spaces_sets_public_read_acl_by_default(self):
        original_urlopen = mod.urlopen
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(req):
            captured['headers'] = dict(req.header_items())
            captured['url'] = req.full_url
            return FakeResponse()

        mod.os.environ['DO_SPACES_KEY'] = 'key'
        mod.os.environ['DO_SPACES_SECRET'] = 'secret'
        mod.os.environ['DO_SPACES_BUCKET_URL'] = 'https://example-bucket.nyc3.digitaloceanspaces.com'
        mod.os.environ['DO_SPACES_REGION'] = 'nyc3'
        mod.urlopen = fake_urlopen
        try:
            mod.upload_spaces('blog-master/test-file.html', b'<html></html>')
        finally:
            mod.urlopen = original_urlopen

        self.assertEqual(captured['url'], 'https://example-bucket.nyc3.digitaloceanspaces.com/blog-master/test-file.html')
        self.assertEqual(captured['headers']['X-amz-acl'], 'public-read')
        self.assertIn('x-amz-acl', captured['headers']['Authorization'])


if __name__ == '__main__':
    unittest.main()
