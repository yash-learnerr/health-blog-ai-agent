#!/usr/bin/env python3
import argparse, base64, hashlib, hmac, html, json, mimetypes, os, re, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_db


def load_env(path='.env'):
    if not Path(path).exists():
        return
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


def sh(cmd, stdin=None):
    res = subprocess.run(cmd, input=stdin, text=True, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or f'command failed: {cmd}')
    return res.stdout.strip()


def mysql(sql):
    return agent_db.mysql(sql)


def b64(text):
    return base64.b64encode(text.encode('utf-8')).decode('ascii')


def env_first(*names, default=None):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def build_file_key(slug, ext='html'):
    prefix = os.getenv('SPACES_PREFIX', 'blog-master').strip('/')
    safe_slug = ''.join(ch if ch.isalnum() or ch in '-_' else '-' for ch in slug).strip('-') or 'blog'
    return f'{prefix}/{uuid.uuid4()}-{safe_slug}.{ext}'


def build_public_file_url(file_key):
    bucket_url = env_first('SPACES_BUCKET_URL', 'DO_SPACES_BUCKET_URL')
    base_url = bucket_url.rstrip('/') if bucket_url else f"https://{resolve_spaces_host()}"
    return f"{base_url}/{quote(file_key, safe='/~_-.')}"


def build_public_asset_url(file_key):
    base_url = env_first('CDN_URL', 'DO_SPACES_CDN_URL', 'BUCKET_URL', 'SPACES_BUCKET_URL', 'DO_SPACES_BUCKET_URL')
    if base_url:
        return f"{base_url.rstrip('/')}/{quote(file_key, safe='/~_-.')}"
    return build_public_file_url(file_key)


def resolve_spaces_host():
    bucket_url = env_first('SPACES_BUCKET_URL', 'DO_SPACES_BUCKET_URL')
    if bucket_url:
        return urlsplit(bucket_url).netloc or bucket_url.replace('https://', '').replace('http://', '').strip('/')
    endpoint = env_first('SPACES_ENDPOINT', 'DO_SPACES_ENDPOINT')
    bucket = env_first('SPACES_BUCKET', 'DO_SPACES_BUCKET')
    if not endpoint or not bucket:
        missing = []
        if not endpoint:
            missing.append('SPACES_ENDPOINT/DO_SPACES_ENDPOINT')
        if not bucket:
            missing.append('SPACES_BUCKET/DO_SPACES_BUCKET')
        raise KeyError(', '.join(missing))
    endpoint = endpoint.replace('https://', '').replace('http://', '').strip('/')
    return endpoint if endpoint.startswith(f'{bucket}.') else f'{bucket}.{endpoint}'


def _contains_html_markup(text):
    return bool(re.search(r'</?[A-Za-z][^>]*>', text or ''))


def _render_inline_markdown(text):
    escaped = html.escape(text or '', quote=True)
    escaped = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', escaped)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
    escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
    return escaped


def content_to_html(content):
    text = (content or '').replace('\r\n', '\n').strip()
    if not text:
        return ''
    if _contains_html_markup(text):
        return text

    blocks = []
    paragraph = []
    unordered = []
    ordered = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{' '.join(_render_inline_markdown(line) for line in paragraph)}</p>")
            paragraph = []

    def flush_unordered():
        nonlocal unordered
        if unordered:
            blocks.append('<ul>' + ''.join(f'<li>{item}</li>' for item in unordered) + '</ul>')
            unordered = []

    def flush_ordered():
        nonlocal ordered
        if ordered:
            blocks.append('<ol>' + ''.join(f'<li>{item}</li>' for item in ordered) + '</ol>')
            ordered = []

    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            continue
        if line in {'---', '***', '___'}:
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            blocks.append('<hr>')
            continue
        heading = re.match(r'^(#{1,6})\s+(.*)$', line)
        if heading:
            flush_paragraph()
            flush_unordered()
            flush_ordered()
            level = len(heading.group(1))
            blocks.append(f'<h{level}>{_render_inline_markdown(heading.group(2))}</h{level}>')
            continue
        unordered_match = re.match(r'^[-*]\s+(.*)$', line)
        if unordered_match:
            flush_paragraph()
            flush_ordered()
            unordered.append(_render_inline_markdown(unordered_match.group(1)))
            continue
        ordered_match = re.match(r'^[0-9]+\.\s+(.*)$', line)
        if ordered_match:
            flush_paragraph()
            flush_unordered()
            ordered.append(_render_inline_markdown(ordered_match.group(1)))
            continue
        flush_unordered()
        flush_ordered()
        paragraph.append(line)

    flush_paragraph()
    flush_unordered()
    flush_ordered()
    return '\n'.join(blocks)


def normalize_keywords(keywords):
    if keywords is None:
        return []
    if isinstance(keywords, str):
        return [item.strip() for item in keywords.split(',') if item.strip()]
    if isinstance(keywords, (list, tuple, set)):
        return [str(item).strip() for item in keywords if str(item).strip()]
    value = str(keywords).strip()
    return [value] if value else []


def pick_first_column(columns, names):
    for name in names:
        if name in columns:
            return name
    return None


def resolve_blog_image_source(blog):
    image_keys = [
        'image_path', 'local_image_path', 'image_file', 'image_source', 'image_source_url',
        'image_url', 'image', 'featured_image', 'thumbnail', 'cover_image', 'banner_image', 'hero_image',
    ]
    for key in image_keys:
        value = blog.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested_key in ['path', 'url', 'src', 'source']:
                nested_value = value.get(nested_key)
                if isinstance(nested_value, str) and nested_value.strip():
                    return nested_value.strip()
    return None


def build_api_url(direct_env_name, path_env_name, default_path):
    direct_url = os.getenv(direct_env_name)
    if direct_url:
        return direct_url.strip()
    configured_base_url = os.getenv('BLOG_IMAGE_API_BASE_URL', '').strip()
    api_url = os.getenv('API_URL', '').strip()
    base_url = configured_base_url or api_url
    if not base_url:
        raise RuntimeError(f'missing {direct_env_name}, BLOG_IMAGE_API_BASE_URL, or API_URL for blog image upload flow')
    path = os.getenv(path_env_name, default_path).strip().lstrip('/')
    if (
        (configured_base_url or api_url)
        and not re.search(r'/api/?$', base_url.rstrip('/'), re.IGNORECASE)
        and not path.startswith('api/')
    ):
        path = f'api/{path}'
    return base_url.rstrip('/') + '/' + path


def parse_json_headers_env(env_name):
    raw = os.getenv(env_name, '').strip()
    if not raw:
        return {}
    headers = json.loads(raw)
    if not isinstance(headers, dict):
        raise RuntimeError(f'{env_name} must be a JSON object')
    return {str(key): str(value) for key, value in headers.items() if value is not None}


def env_truthy(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {'', '0', 'false', 'no', 'off'}


def request_json(url, method='GET', headers=None, body=None):
    req = Request(url, data=body, method=method, headers=headers or {})
    with urlopen(req) as res:
        payload = res.read().decode('utf-8').strip()
    if not payload:
        return {}
    return json.loads(payload)


def find_response_value(payload, *candidate_keys):
    queue = [payload]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            for key in candidate_keys:
                value = current.get(key)
                if value not in (None, ''):
                    return value
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return None


def build_multipart_form_data(field_name, filename, body, content_type):
    boundary = f'----HealthAiAgent{uuid.uuid4().hex}'
    chunks = [
        f'--{boundary}\r\n'.encode('utf-8'),
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode('utf-8'),
        f'Content-Type: {content_type}\r\n\r\n'.encode('utf-8'),
        body,
        b'\r\n',
        f'--{boundary}--\r\n'.encode('utf-8'),
    ]
    return boundary, b''.join(chunks)


def fetch_binary_asset(asset_source, default_name='blog-image'):
    if re.match(r'^https?://', asset_source or '', re.IGNORECASE):
        req = Request(asset_source, headers={'User-Agent': 'HealthAiAgent/1.0'})
        with urlopen(req) as res:
            body = res.read()
            headers = getattr(res, 'headers', None)
            content_type = headers.get('Content-Type') if headers and hasattr(headers, 'get') else None
            resolved_url = res.geturl() if hasattr(res, 'geturl') else asset_source
        filename = Path(urlsplit(resolved_url).path).name or Path(urlsplit(asset_source).path).name or default_name
        return filename, body, (content_type or 'application/octet-stream').split(';', 1)[0]

    asset_path = Path(asset_source).expanduser()
    if not asset_path.is_absolute():
        asset_path = Path.cwd() / asset_path
    if not asset_path.exists() or not asset_path.is_file():
        raise RuntimeError(f'blog image not found: {asset_source}')
    content_type = mimetypes.guess_type(asset_path.name)[0] or 'application/octet-stream'
    return asset_path.name, asset_path.read_bytes(), content_type


def sanitize_object_name(filename, fallback='asset'):
    raw_name = Path(filename or '').name.strip()
    if not raw_name:
        raw_name = fallback
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '-', raw_name).strip('-')
    return safe_name or fallback


def build_asset_file_key(filename, folder=None):
    destination_folder = (folder or os.getenv('BLOG_IMAGE_DESTINATION_FOLDER', 'blog-master')).strip().strip('/')
    safe_name = sanitize_object_name(filename, fallback='blog-image')
    return f'{destination_folder}/{uuid.uuid4()}-{safe_name}' if destination_folder else f'{uuid.uuid4()}-{safe_name}'


def should_fallback_to_spaces():
    return env_truthy('BLOG_IMAGE_API_FALLBACK_TO_SPACES', default=True)


def upload_asset_to_spaces(filename, body, content_type, folder=None):
    file_key = build_asset_file_key(filename, folder=folder)
    upload_spaces(file_key, body, content_type=content_type)
    return file_key, build_public_asset_url(file_key)


def upload_temp_file_to_app(filename, body, content_type):
    field_name = os.getenv('BLOG_IMAGE_UPLOAD_FIELD_NAME', 'file').strip() or 'file'
    headers = parse_json_headers_env('BLOG_IMAGE_API_HEADERS_JSON')
    boundary, payload = build_multipart_form_data(field_name, filename, body, content_type)
    headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
    response = request_json(
        build_api_url('BLOG_IMAGE_UPLOAD_URL', 'BLOG_IMAGE_UPLOAD_PATH', 'doctor/upload-temp-file'),
        method='POST',
        headers=headers,
        body=payload,
    )
    file_key = find_response_value(response, 'file_key', 'fileKey')
    if not file_key:
        raise RuntimeError('upload-temp-file response did not include file_key')
    return file_key


def extract_temp_file_key(input_value):
    if not isinstance(input_value, str) or not input_value.strip():
        return None
    candidate = input_value.strip()
    if candidate.startswith('temp/'):
        return candidate.split('?', 1)[0].split('#', 1)[0]
    if '/temp/' in candidate:
        return 'temp/' + candidate.split('/temp/', 1)[1].split('?', 1)[0].split('#', 1)[0].lstrip('/')
    return None


def resolve_spaces_bucket_name():
    bucket = env_first('SPACES_BUCKET', 'DO_SPACES_BUCKET', 'BUCKET')
    if bucket:
        return bucket.strip()
    bucket_url = env_first('BUCKET_URL', 'SPACES_BUCKET_URL', 'DO_SPACES_BUCKET_URL')
    if bucket_url:
        host = urlsplit(bucket_url).netloc or bucket_url.replace('https://', '').replace('http://', '').strip('/')
        if host:
            return host.split('.')[0]
    raise KeyError('SPACES_BUCKET/DO_SPACES_BUCKET/BUCKET')


def resolve_spaces_credentials():
    access = env_first('SPACES_KEY', 'DO_SPACES_KEY', 'ACCESS_KEY_ID')
    secret = env_first('SPACES_SECRET', 'DO_SPACES_SECRET', 'SECRET_ACCESS_KEY')
    region = env_first('SPACES_REGION', 'DO_SPACES_REGION', 'REGION', default='us-east-1')
    host = resolve_spaces_host()
    bucket = resolve_spaces_bucket_name()
    if not access:
        raise KeyError('SPACES_KEY/DO_SPACES_KEY/ACCESS_KEY_ID')
    if not secret:
        raise KeyError('SPACES_SECRET/DO_SPACES_SECRET/SECRET_ACCESS_KEY')
    return access, secret, region, host, bucket


def spaces_signed_request(method, file_key, body=b'', headers=None, expected_statuses=(200, 204)):
    access, secret, region, host, _bucket = resolve_spaces_credentials()
    payload = body if body is not None else b''
    uri = '/' + quote(file_key, safe='/~_-.')
    now = datetime.now(timezone.utc)
    amz_date = now.strftime('%Y%m%dT%H%M%SZ')
    short_date = now.strftime('%Y%m%d')
    payload_hash = hashlib.sha256(payload).hexdigest()
    canonical_headers_map = {'host': host, 'x-amz-content-sha256': payload_hash, 'x-amz-date': amz_date}
    for key, value in (headers or {}).items():
        canonical_headers_map[key.lower()] = value
    signed_headers = ';'.join(sorted(canonical_headers_map))
    canonical_headers = ''.join(f'{key}:{canonical_headers_map[key]}\n' for key in sorted(canonical_headers_map))
    canonical_request = f'{method}\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    scope = f'{short_date}/{region}/s3/aws4_request'
    string_to_sign = 'AWS4-HMAC-SHA256\n' + amz_date + '\n' + scope + '\n' + hashlib.sha256(canonical_request.encode()).hexdigest()
    k_date = sign(('AWS4' + secret).encode('utf-8'), short_date)
    k_region = hmac.new(k_date, region.encode('utf-8'), hashlib.sha256).digest()
    k_service = hmac.new(k_region, b's3', hashlib.sha256).digest()
    k_signing = hmac.new(k_service, b'aws4_request', hashlib.sha256).digest()
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    auth = f'AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed_headers}, Signature={signature}'
    request_headers = {**canonical_headers_map, 'Authorization': auth}
    data = payload if method not in {'GET', 'DELETE'} else None
    req = Request(f'https://{host}{uri}', data=data, method=method, headers=request_headers)
    with urlopen(req) as res:
        status = getattr(res, 'status', 200)
        response_body = res.read()
    if status not in expected_statuses:
        raise RuntimeError(f'Spaces {method} failed for {file_key}: HTTP {status}')
    return response_body


def move_temp_object_in_spaces(input_value, target_folder, is_public=False):
    source_key = extract_temp_file_key(input_value)
    if not source_key or not target_folder:
        return None
    bucket = resolve_spaces_bucket_name()
    file_name = source_key.split('/')[-1]
    target_key = f"{target_folder.strip('/')}/{file_name}"
    content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
    headers = {
        'x-amz-copy-source': f"/{bucket}/{quote(source_key, safe='/~_-.')}",
        'content-type': content_type,
        'content-disposition': 'inline',
        'x-amz-metadata-directive': 'REPLACE',
    }
    if is_public:
        headers['x-amz-acl'] = 'public-read'
    spaces_signed_request('PUT', target_key, body=b'', headers=headers, expected_statuses=(200,))
    spaces_signed_request('DELETE', source_key, headers={}, expected_statuses=(200, 204))
    return target_key


def move_temp_file_via_api(file_key, destination_folder, is_public=False):
    headers = parse_json_headers_env('BLOG_IMAGE_API_HEADERS_JSON')
    headers['Content-Type'] = 'application/json'
    response = request_json(
        build_api_url('BLOG_IMAGE_MOVE_URL', 'BLOG_IMAGE_MOVE_PATH', 'doctor/move-temp-file'),
        method='POST',
        headers=headers,
        body=json.dumps({'file_key': file_key, 'folder': destination_folder, 'is_public': is_public}).encode('utf-8'),
    )
    image_value = find_response_value(response, 'url', 'file_url', 'fileUrl', 'location', 'file_key', 'fileKey', 'key')
    if not image_value:
        raise RuntimeError('move temp file response did not include url')
    return image_value if re.match(r'^https?://', str(image_value), re.IGNORECASE) else build_public_asset_url(str(image_value))


def move_temp_file_to_blog_folder(file_key, folder=None):
    destination_folder = (folder or os.getenv('BLOG_IMAGE_DESTINATION_FOLDER', 'blog-master')).strip() or 'blog-master'
    is_public = env_truthy('BLOG_IMAGE_MOVE_PUBLIC', default=True)
    if os.getenv('BLOG_IMAGE_MOVE_URL') or os.getenv('BLOG_IMAGE_MOVE_PATH'):
        try:
            return move_temp_file_via_api(file_key, destination_folder, is_public=is_public)
        except Exception:
            if not should_fallback_to_spaces():
                raise
    moved_key = move_temp_object_in_spaces(file_key, destination_folder, is_public=is_public)
    if not moved_key:
        raise RuntimeError(f'moveTempFile: invalid input {file_key!r}. Expected temp key or URL containing /temp/.')
    return build_public_asset_url(moved_key)


def upload_blog_image(blog):
    image_source = resolve_blog_image_source(blog)
    if not image_source:
        return None, None
    filename, body, content_type = fetch_binary_asset(image_source, default_name=f"{blog.get('slug') or 'blog'}-image")
    try:
        file_key = upload_temp_file_to_app(filename, body, content_type)
        return file_key, move_temp_file_to_blog_folder(file_key)
    except Exception:
        if not should_fallback_to_spaces():
            raise
        try:
            return upload_asset_to_spaces(filename, body, content_type)
        except (HTTPError, URLError, KeyError, RuntimeError, ValueError):
            raise


def build_blog_insert_statement(columns, blog, timestamp, file_url=None, image_url=None):
    title_column = pick_first_column(columns, ['blog_name', 'title'])
    summary_column = pick_first_column(columns, ['meta_description', 'summary'])
    content_column = pick_first_column(columns, ['description', 'content'])
    keywords_column = pick_first_column(columns, ['meta_tags', 'keywords'])
    image_column = pick_first_column(columns, ['image', 'thumbnail', 'cover_image', 'featured_image', 'banner_image', 'hero_image', 'featuredImage'])
    if not title_column or not summary_column or not content_column or 'slug' not in columns or 'category_id' not in columns:
        raise RuntimeError('blog_master schema is missing required publish columns')

    query_columns = []
    params = []

    def add(column_name, value):
        if column_name in columns:
            query_columns.append(column_name)
            params.append(value)

    add('createdAt', timestamp)
    add('updatedAt', timestamp)
    add('category_id', blog['category_id'])
    add(title_column, blog['title'])
    add('slug', blog['slug'])
    add('meta_title', blog['title'])
    add(content_column, content_to_html(blog.get('content', '')))
    add(summary_column, blog.get('summary', ''))
    if keywords_column == 'keywords':
        add(keywords_column, json.dumps(normalize_keywords(blog.get('keywords')), ensure_ascii=False))
    else:
        add(keywords_column, ', '.join(normalize_keywords(blog.get('keywords'))))
    add('source_url', blog.get('source_url'))
    add('status', 'active')
    stored_file_value = agent_db.blog_master_file_db_value(file_url)
    if 'file' in columns and not stored_file_value:
        raise RuntimeError('missing generated file URL for blog_master.file insert')
    if stored_file_value:
        add('file', stored_file_value)
    if image_column and image_url:
        add(image_column, image_url)

    placeholders = ', '.join(['%s'] * len(query_columns))
    column_sql = ', '.join(query_columns)
    return f"INSERT INTO blog_master ({column_sql}) VALUES ({placeholders})", tuple(params)


def render_html(title, summary, content):
    title_html = html.escape(title or '')
    summary_html = html.escape(summary or '')
    body_html = content_to_html(content)
    summary_block = f'<p>{summary_html}</p>' if summary_html else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>{title_html}</title></head><body><h1>{title_html}</h1>{summary_block}<hr><div>{body_html}</div></body></html>'''.encode('utf-8')


def upload_blog_html(blog):
    file_key = build_file_key(blog['slug'])
    upload_spaces(file_key, render_html(blog['title'], blog.get('summary', ''), blog['content']))
    return file_key, build_public_file_url(file_key)


def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()


def upload_spaces(file_key, body, content_type='text/html; charset=utf-8'):
    access = env_first('SPACES_KEY', 'DO_SPACES_KEY')
    secret = env_first('SPACES_SECRET', 'DO_SPACES_SECRET')
    region = env_first('SPACES_REGION', 'DO_SPACES_REGION', default='us-east-1')
    object_acl = env_first('SPACES_OBJECT_ACL', 'DO_SPACES_OBJECT_ACL', default='public-read')
    host = resolve_spaces_host()
    if not access:
        raise KeyError('SPACES_KEY/DO_SPACES_KEY')
    if not secret:
        raise KeyError('SPACES_SECRET/DO_SPACES_SECRET')
    uri = '/' + quote(file_key, safe='/~_-.' )
    now = datetime.now(timezone.utc)
    amz_date = now.strftime('%Y%m%dT%H%M%SZ')
    short_date = now.strftime('%Y%m%d')
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {'host': host, 'x-amz-content-sha256': payload_hash, 'x-amz-date': amz_date}
    if object_acl:
        headers['x-amz-acl'] = object_acl
    signed_headers = ';'.join(sorted(headers))
    canonical_headers = ''.join(f'{k}:{headers[k]}\n' for k in sorted(headers))
    canonical_request = f'PUT\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    scope = f'{short_date}/{region}/s3/aws4_request'
    string_to_sign = 'AWS4-HMAC-SHA256\n' + amz_date + '\n' + scope + '\n' + hashlib.sha256(canonical_request.encode()).hexdigest()
    k_date = sign(('AWS4' + secret).encode('utf-8'), short_date)
    k_region = hmac.new(k_date, region.encode('utf-8'), hashlib.sha256).digest()
    k_service = hmac.new(k_region, b's3', hashlib.sha256).digest()
    k_signing = hmac.new(k_service, b'aws4_request', hashlib.sha256).digest()
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    auth = f'AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed_headers}, Signature={signature}'
    req = Request(f'https://{host}{uri}', data=body, method='PUT', headers={**headers, 'Authorization': auth, 'Content-Type': content_type})
    with urlopen(req) as res:
        if res.status not in (200, 201):
            raise RuntimeError(f'Spaces upload failed: HTTP {res.status}')
    return file_key


def fetch_blog(blog_id):
    db = agent_db.publish_db_name()
    columns = agent_db._table_columns(db, 'blog_master')
    title_col = pick_first_column(columns, ['blog_name', 'title'])
    summary_col = pick_first_column(columns, ['meta_description', 'summary'])
    content_col = pick_first_column(columns, ['description', 'content'])
    if not title_col or not content_col:
        raise RuntimeError('blog_master schema is missing title/content columns')
    summary_expr = f"REPLACE(TO_BASE64(COALESCE(CAST(`{summary_col}` AS CHAR CHARACTER SET utf8mb4), '')), '\n', '')" if summary_col else "''"
    sql = (
        f"USE `{db}`; SELECT id, slug, "
        f"REPLACE(TO_BASE64(COALESCE(CAST(`{title_col}` AS CHAR CHARACTER SET utf8mb4), '')), '\n', ''), "
        f"{summary_expr}, "
        f"REPLACE(TO_BASE64(COALESCE(CAST(`{content_col}` AS CHAR CHARACTER SET utf8mb4), '')), '\n', '') "
        f"FROM blog_master WHERE id={int(blog_id)} LIMIT 1;"
    )
    row = mysql(sql)
    if not row:
        raise RuntimeError(f'blog {blog_id} not found')
    blog_id, slug, title_b64, summary_b64, content_b64 = row.split('\t')
    dec = lambda s: base64.b64decode(s).decode('utf-8') if s else ''
    return {'id': int(blog_id), 'slug': slug, 'title': dec(title_b64), 'summary': dec(summary_b64), 'content': dec(content_b64)}


def update_file(blog_id, file_url, image_url=None):
    db = agent_db.publish_db_name()
    columns = agent_db._table_columns(db, 'blog_master')
    image_column = pick_first_column(columns, ['image', 'thumbnail', 'cover_image', 'featured_image', 'banner_image', 'hero_image', 'featuredImage'])
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    assignments = []
    stored_file_value = agent_db.blog_master_file_db_value(file_url)
    if 'file' in columns and not stored_file_value:
        raise RuntimeError('missing generated file URL for blog_master.file update')
    if 'file' in columns and stored_file_value:
        assignments.append(f"file={agent_db.text_expr(stored_file_value)}")
    if image_column and image_url:
        assignments.append(f"`{image_column}`={agent_db.text_expr(image_url)}")
    if 'updatedAt' in columns:
        assignments.append(f'updatedAt={ts}')
    elif 'updated_at' in columns:
        assignments.append('updated_at=CURRENT_TIMESTAMP')
    if not assignments:
        raise RuntimeError('blog_master schema is missing file/image update columns')
    select_fields = ['id', 'slug']
    if 'file' in columns:
        select_fields.append('file')
    if image_column:
        select_fields.append(f'`{image_column}`')
    sql = (
        f"USE `{db}`; UPDATE blog_master SET {', '.join(assignments)} WHERE id={int(blog_id)}; "
        f"SELECT {', '.join(select_fields)} FROM blog_master WHERE id={int(blog_id)};"
    )
    return mysql(sql)


def main():
    load_env()
    run_id = agent_db.current_run_id('blog-file-manager')
    parser = argparse.ArgumentParser(description='Upload a blog file to Spaces and update blog_master.file.')
    parser.add_argument('--blog-id', type=int, help='Existing blog_master.id to backfill.')
    parser.add_argument('--json', help='Path to generated blog JSON with title/slug/summary/content.')
    args = parser.parse_args()
    if not args.blog_id and not args.json:
        parser.error('provide --blog-id or --json')
    details = {'blog_id': args.blog_id, 'json_path': args.json}
    blog = None
    try:
        agent_db.safe_log_event(run_id, 'blog_file_manager', 'STARTED', 'Starting blog file upload flow.', details=details)
        if args.json:
            blog = json.loads(Path(args.json).read_text())
        else:
            blog = fetch_blog(args.blog_id)
        for key in ['slug', 'title', 'content']:
            if not blog.get(key):
                raise RuntimeError(f'missing required field: {key}')
        file_key, file_url = upload_blog_html(blog)
        image_file_key, image_url = upload_blog_image(blog)
        print(f'SPACES_FILE_KEY={file_key}')
        print(f'SPACES_FILE_URL={file_url}')
        if image_file_key:
            print(f'BLOG_IMAGE_FILE_KEY={image_file_key}')
        if image_url:
            print(f'BLOG_IMAGE_URL={image_url}')
        if args.blog_id:
            print(update_file(args.blog_id, file_url, image_url))
        agent_db.safe_log_event(
            run_id,
            'blog_file_manager',
            'SUCCESS',
            'Uploaded blog file and completed optional backfill.',
            item_slug=blog.get('slug'),
            details={
                **details,
                'file_key': file_key,
                'file_url': file_url,
                'image_file_key': image_file_key,
                'image_url': image_url,
            },
        )
        return 0
    except KeyError as exc:
        message = f'missing environment variable: {exc.args[0]}'
    except Exception as exc:
        message = str(exc)
    agent_db.safe_log_event(
        run_id,
        'blog_file_manager',
        'ERROR',
        message,
        item_slug=blog.get('slug') if blog else None,
        details=details,
    )
    print(message, file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
