#!/usr/bin/env python3
import base64
import importlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit


def load_env(path='.env'):
    if not Path(path).exists():
        return
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


def sh(cmd, stdin=None, timeout_seconds=None):
    if timeout_seconds is None:
        timeout_seconds = int(os.getenv('DB_COMMAND_TIMEOUT_SECONDS', '15'))
    try:
        res = subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'command timed out after {timeout_seconds}s: {cmd[0]}') from exc
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or f'command failed: {cmd}')
    return res.stdout.strip()


DATABASE_ACCESS_LOCAL = 'local'
DATABASE_ACCESS_STAGING = 'staging'
DATABASE_ACCESS_PRODUCTION = 'production'
VALID_DATABASE_ACCESS = {
    DATABASE_ACCESS_LOCAL,
    DATABASE_ACCESS_STAGING,
    DATABASE_ACCESS_PRODUCTION,
}

STORAGE_BACKEND_DATABASE = 'database'
STORAGE_BACKEND_JSON = 'json'
STORAGE_BACKEND_BOTH = 'both'
VALID_STORAGE_BACKENDS = {
    STORAGE_BACKEND_DATABASE,
    STORAGE_BACKEND_JSON,
    STORAGE_BACKEND_BOTH,
}

DASHBOARD_SOURCE_DATABASE = 'database'
DASHBOARD_SOURCE_JSON = 'json'
VALID_DASHBOARD_SOURCES = {
    DASHBOARD_SOURCE_DATABASE,
    DASHBOARD_SOURCE_JSON,
}

JSON_RUN_LOG_FILE_NAME = 'agent_run_logs.json'
JSON_MEMORY_FILE_NAME = 'agent_memory.json'
JSON_BLOGS_FILE_NAME = 'blogs.json'
BLOG_MASTER_DB_FILE_PREFIX = 'blog_master/'
SPACES_BLOG_MASTER_FILE_PREFIX = 'blog-master/'


def _normalize_database_access(value):
    access = str(value or DATABASE_ACCESS_LOCAL).strip().lower()
    if access not in VALID_DATABASE_ACCESS:
        raise ValueError(
            'DATABASE_ACCESS must be one of: local, staging, production'
        )
    return access


def _normalize_choice(value, env_name, valid_values, default):
    choice = str(value or default).strip().lower()
    if choice not in valid_values:
        raise ValueError(f"{env_name} must be one of: {', '.join(sorted(valid_values))}")
    return choice


def _first_env_value(*names, default=None):
    load_env()
    for name in names:
        value = os.getenv(name)
        if value not in (None, ''):
            return value
    return default


def database_access(use_staging=None):
    load_env()
    if use_staging is not None:
        return DATABASE_ACCESS_STAGING if use_staging else DATABASE_ACCESS_LOCAL
    return _normalize_database_access(os.getenv('DATABASE_ACCESS', DATABASE_ACCESS_LOCAL))


def operational_storage_backend():
    load_env()
    return _normalize_choice(
        os.getenv('AGENT_STORAGE_BACKEND', STORAGE_BACKEND_DATABASE),
        'AGENT_STORAGE_BACKEND',
        VALID_STORAGE_BACKENDS,
        STORAGE_BACKEND_DATABASE,
    )


def dashboard_data_source():
    load_env()
    return _normalize_choice(
        os.getenv('DASHBOARD_DATA_SOURCE', DASHBOARD_SOURCE_DATABASE),
        'DASHBOARD_DATA_SOURCE',
        VALID_DASHBOARD_SOURCES,
        DASHBOARD_SOURCE_DATABASE,
    )


def json_storage_dir():
    load_env()
    raw = (os.getenv('AGENT_JSON_STORAGE_DIR') or '.').strip() or '.'
    return Path(raw).expanduser().resolve()


def json_run_logs_path():
    return json_storage_dir() / JSON_RUN_LOG_FILE_NAME


def json_memory_path():
    return json_storage_dir() / JSON_MEMORY_FILE_NAME


def using_staging_db():
    return database_access() == DATABASE_ACCESS_STAGING


def using_production_db():
    return database_access() == DATABASE_ACCESS_PRODUCTION


def env_with_database_access(*names, default=None, use_staging=None, allow_local_fallback=True):
    load_env()
    access = database_access(use_staging=use_staging)
    if access != DATABASE_ACCESS_LOCAL:
        prefix = access.upper() + '_'
        for name in names:
            env_name = name if name.startswith(prefix) else prefix + name
            value = os.getenv(env_name)
            if value:
                return value
        if not allow_local_fallback:
            return default
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def env_with_staging(*names, default=None, use_staging=None):
    return env_with_database_access(*names, default=default, use_staging=use_staging)


def _database_port(use_staging=None):
    raw = env_with_database_access('DB_PORT', default='3306', use_staging=use_staging)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'invalid DB_PORT value: {raw!r}') from exc


def _required_database_env_names(access):
    if access == DATABASE_ACCESS_LOCAL:
        return ['DB_USER', 'DB_PASSWORD']
    prefix = access.upper() + '_'
    return [f'{prefix}DB_HOST', f'{prefix}DB_USER', f'{prefix}DB_PASSWORD']


def db_connection_config(use_staging=None):
    load_env()
    access = database_access(use_staging=use_staging)
    return {
        'access': access,
        'host': env_with_database_access(
            'DB_HOST',
            default='localhost' if access == DATABASE_ACCESS_LOCAL else None,
            use_staging=use_staging,
            allow_local_fallback=False,
        ),
        'user': env_with_database_access('DB_USER', use_staging=use_staging, allow_local_fallback=False),
        'password': env_with_database_access('DB_PASSWORD', use_staging=use_staging, allow_local_fallback=False),
        'port': _database_port(use_staging=use_staging),
    }


def db_target_info(use_staging=None):
    cfg = db_connection_config(use_staging=use_staging)
    return {
        'mode': cfg['access'].capitalize(),
        'host': cfg.get('host') or 'localhost',
        'publish_db_name': publish_db_name(use_staging=use_staging),
        'agent_db_name': operational_db_name(use_staging=use_staging),
    }


def dashboard_target_info(data_source=None, use_staging=None):
    source = data_source or dashboard_data_source()
    if source == DASHBOARD_SOURCE_JSON:
        return {
            'mode': 'JSON',
            'host': str(json_storage_dir()),
            'publish_db_name': publish_db_name(use_staging=use_staging),
            'agent_db_name': f'{json_run_logs_path().name}, {json_memory_path().name}',
            'source_kind': 'json',
            'source_label': f'{json_run_logs_path().name} and {json_memory_path().name}',
            'status_label': 'JSON files',
            'host_label': 'Directory',
            'agent_label': 'Files',
        }
    target = db_target_info(use_staging=use_staging)
    target.update({
        'source_kind': 'database',
        'source_label': 'AGENT_DB_NAME.agent_run_logs and AGENT_DB_NAME.agent_memory',
        'status_label': f"{target.get('mode', 'Unknown')} database",
        'host_label': 'Host',
        'agent_label': 'Agent DB',
    })
    return target


def blog_master_file_db_value(value, use_staging=None):
    if value is None:
        return None
    text = str(value or '').strip()
    if not text:
        return text
    if database_access(use_staging=use_staging) == DATABASE_ACCESS_LOCAL:
        return text
    path = urlsplit(text).path.lstrip('/') if '://' in text else text.lstrip('/')
    if path.startswith(SPACES_BLOG_MASTER_FILE_PREFIX):
        return BLOG_MASTER_DB_FILE_PREFIX + path[len(SPACES_BLOG_MASTER_FILE_PREFIX):]
    if path.startswith(BLOG_MASTER_DB_FILE_PREFIX):
        return path
    return path or text


def blog_master_file_public_url(value):
    text = str(value or '').strip()
    if not text or text.startswith(('http://', 'https://')):
        return text
    file_key = text
    if file_key.startswith(BLOG_MASTER_DB_FILE_PREFIX):
        file_key = SPACES_BLOG_MASTER_FILE_PREFIX + file_key[len(BLOG_MASTER_DB_FILE_PREFIX):]
    base_url = _first_env_value(
        'CDN_URL',
        'DO_SPACES_CDN_URL',
        'BUCKET_URL',
        'SPACES_BUCKET_URL',
        'DO_SPACES_BUCKET_URL',
    )
    if not base_url:
        bucket = _first_env_value('SPACES_BUCKET', 'DO_SPACES_BUCKET')
        endpoint = _first_env_value('SPACES_ENDPOINT', 'DO_SPACES_ENDPOINT')
        if bucket and endpoint:
            base_url = f'https://{bucket}.{endpoint}'
    if not base_url:
        return text
    return f"{base_url.rstrip('/')}/{quote(file_key, safe='/~_-.')}"


def _mysql_cli_available():
    return shutil.which('mysql') is not None


def _import_mysql_connector():
    try:
        return importlib.import_module('mysql.connector')
    except ModuleNotFoundError:
        return None


def _install_mysql_connector():
    timeout_seconds = int(os.getenv('DB_COMMAND_TIMEOUT_SECONDS', '15'))
    res = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', 'mysql-connector-python'],
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or 'failed to install mysql-connector-python')
    return importlib.import_module('mysql.connector')


def _mysql_connector_module():
    module = _import_mysql_connector()
    if module is not None:
        return module
    if _mysql_cli_available():
        return None
    return _install_mysql_connector()


def _split_sql_statements(sql):
    statements = []
    current = []
    quote = None
    escape = False
    for char in sql:
        if escape:
            current.append(char)
            escape = False
            continue
        if char == '\\':
            current.append(char)
            escape = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"', '`'):
            current.append(char)
            quote = char
            continue
        if char == ';':
            statement = ''.join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue
        current.append(char)
    trailing = ''.join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def _mysql_via_connector(sql, cfg):
    connector = _mysql_connector_module()
    if connector is None:
        raise RuntimeError('mysql.connector unavailable')
    connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT_SECONDS', '5'))
    conn = connector.connect(
        host=cfg['host'],
        port=cfg['port'],
        user=cfg['user'],
        password=cfg['password'],
        connection_timeout=connect_timeout,
        use_pure=True,
    )
    cursor = conn.cursor()
    output = ''
    try:
        for statement in _split_sql_statements(sql):
            cursor.execute(statement)
            if cursor.with_rows:
                rows = cursor.fetchall()
                output = '\n'.join(
                    '\t'.join('' if value is None else str(value) for value in row)
                    for row in rows
                )
            else:
                output = ''
        conn.commit()
        return output.strip()
    finally:
        cursor.close()
        conn.close()


def database_backend():
    if _import_mysql_connector() is not None:
        return 'mysql.connector'
    if _mysql_cli_available():
        return 'mysql'
    return 'auto-install'


def mysql(sql, use_staging=None):
    cfg = db_connection_config(use_staging=use_staging)
    if not cfg['host'] or not cfg['user'] or not cfg['password']:
        missing_names = _required_database_env_names(cfg['access'])
        raise RuntimeError(
            f"missing database credentials for {cfg['access']} access: {', '.join(missing_names)}"
        )
    connector = _mysql_connector_module()
    if connector is not None:
        return _mysql_via_connector(sql, cfg)
    if not _mysql_cli_available():
        raise RuntimeError('No MySQL backend available. Install mysql-connector-python or the mysql CLI.')
    connect_timeout = os.getenv('DB_CONNECT_TIMEOUT_SECONDS', '5')
    cmd = [
        'mysql',
        '-h',
        cfg['host'],
        '-P',
        str(cfg['port']),
        f"-u{cfg['user']}",
        f"-p{cfg['password']}",
        '--connect-timeout',
        str(connect_timeout),
        '--default-character-set=utf8mb4',
        '-N',
        '-B',
    ]
    return sh(cmd, stdin=sql)


def operational_db_name(use_staging=None):
    return env_with_database_access('AGENT_DB_NAME', default='health_ai_agent', use_staging=use_staging)


def publish_db_name(use_staging=None):
    return env_with_database_access('PUBLISH_DB_NAME', default='mydrscripts_new', use_staging=use_staging)


def current_run_id(prefix='run'):
    load_env()
    existing = os.getenv('RUN_ID')
    if existing:
        return existing
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return f'{prefix}-{stamp}-{uuid.uuid4().hex[:8]}'


def _b64(text):
    return base64.b64encode(text.encode('utf-8')).decode('ascii')


def text_expr(value):
    if value is None:
        return 'NULL'
    return f"CONVERT(FROM_BASE64('{_b64(str(value))}') USING utf8mb4)"


def text_equals_expr(column_sql, value):
    if value is None:
        return f'{column_sql} IS NULL'
    return f'BINARY {column_sql} = BINARY {text_expr(value)}'


def json_expr(value):
    if value is None:
        return 'NULL'
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text_expr(payload)


def int_expr(value):
    if value is None:
        return 'NULL'
    return str(int(value))


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _read_json_records(path):
    file_path = Path(path)
    if not file_path.exists():
        return []
    raw = file_path.read_text(encoding='utf-8').strip()
    if not raw:
        return []
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise RuntimeError(f'expected a JSON array in {file_path}')
    return payload


def _write_json_records(path, rows):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')


def _next_json_id(rows):
    return max((_safe_int(row.get('id')) for row in rows if isinstance(row, dict)), default=0) + 1


def _append_json_record(path, row):
    rows = _read_json_records(path)
    record = dict(row)
    if _safe_int(record.get('id')) <= 0:
        record['id'] = _next_json_id(rows)
    rows.append(record)
    _write_json_records(path, rows)
    return record


def normalize_usage_metrics(request_count=None, prompt_tokens=None, completion_tokens=None, total_tokens=None, details=None):
    details = details if isinstance(details, dict) else {}
    usage = details.get('usage') if isinstance(details.get('usage'), dict) else {}
    metrics = details.get('metrics') if isinstance(details.get('metrics'), dict) else {}

    def first_int(*values):
        for value in values:
            if value in (None, ''):
                continue
            return int(value)
        return None

    request_count = first_int(request_count, details.get('request_count'), usage.get('request_count'), metrics.get('request_count'))
    prompt_tokens = first_int(prompt_tokens, details.get('prompt_tokens'), details.get('input_tokens'), usage.get('prompt_tokens'), usage.get('input_tokens'), metrics.get('prompt_tokens'))
    completion_tokens = first_int(completion_tokens, details.get('completion_tokens'), details.get('output_tokens'), usage.get('completion_tokens'), usage.get('output_tokens'), metrics.get('completion_tokens'))
    total_tokens = first_int(total_tokens, details.get('total_tokens'), usage.get('total_tokens'), metrics.get('total_tokens'))

    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = int(prompt_tokens or 0) + int(completion_tokens or 0)
    if request_count is None and any(value is not None for value in (prompt_tokens, completion_tokens, total_tokens)):
        request_count = 1

    return {
        'request_count': request_count,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': total_tokens,
    }


def _table_columns(db_name, table_name, use_staging=None):
    rows = _query_rows(
        'SELECT column_name FROM information_schema.columns '
        f'WHERE {text_equals_expr("table_schema", db_name)} '
        f'AND {text_equals_expr("table_name", table_name)} '
        'ORDER BY ordinal_position;',
        1,
        use_staging=use_staging,
    )
    return {row[0] for row in rows}


def _ensure_columns(db_name, table_name, definitions, use_staging=None):
    existing = _table_columns(db_name, table_name, use_staging=use_staging)
    missing = [f"ADD COLUMN {name} {ddl}" for name, ddl in definitions.items() if name not in existing]
    if not missing:
        return ''
    sql = f"USE `{db_name}`; ALTER TABLE `{table_name}` {', '.join(missing)};"
    return mysql(sql, use_staging=use_staging)


def ensure_operational_tables(use_staging=None):
    db = operational_db_name(use_staging=use_staging)
    sql = f"""
CREATE DATABASE IF NOT EXISTS `{db}`;
USE `{db}`;
CREATE TABLE IF NOT EXISTS agent_memory (
  id INT PRIMARY KEY AUTO_INCREMENT,
  topic_slug VARCHAR(512),
  category_name VARCHAR(255),
  memory_key VARCHAR(255) NOT NULL,
  verified_fact TEXT NOT NULL,
  source_url VARCHAR(1024),
  confidence VARCHAR(32),
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agent_run_logs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  run_id VARCHAR(255) NOT NULL,
  step VARCHAR(128) NOT NULL,
  item_slug VARCHAR(512),
  status VARCHAR(64) NOT NULL,
  message TEXT,
  details_json JSON,
  request_count INT NOT NULL DEFAULT 0,
  prompt_tokens BIGINT NOT NULL DEFAULT 0,
  completion_tokens BIGINT NOT NULL DEFAULT 0,
  total_tokens BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
    mysql(sql, use_staging=use_staging)
    _ensure_columns(db, 'agent_run_logs', {
        'request_count': 'INT NOT NULL DEFAULT 0',
        'prompt_tokens': 'BIGINT NOT NULL DEFAULT 0',
        'completion_tokens': 'BIGINT NOT NULL DEFAULT 0',
        'total_tokens': 'BIGINT NOT NULL DEFAULT 0',
    }, use_staging=use_staging)
    return ''


def _store_log_event_in_database(run_id, step, status, message, item_slug=None, details=None, usage=None):
    ensure_operational_tables()
    db = operational_db_name()
    usage = usage or normalize_usage_metrics(details=details)
    sql = f"""
USE `{db}`;
INSERT INTO agent_run_logs (run_id, step, item_slug, status, message, details_json, request_count, prompt_tokens, completion_tokens, total_tokens)
VALUES (
  {text_expr(run_id)},
  {text_expr(step)},
  {text_expr(item_slug)},
  {text_expr(status)},
  {text_expr(message)},
  {json_expr(details)},
  {int_expr(usage['request_count'] or 0)},
  {int_expr(usage['prompt_tokens'] or 0)},
  {int_expr(usage['completion_tokens'] or 0)},
  {int_expr(usage['total_tokens'] or 0)}
);
"""
    return mysql(sql)


def _store_log_event_in_json(run_id, step, status, message, item_slug=None, details=None, usage=None):
    usage = usage or normalize_usage_metrics(details=details)
    details_json = '' if details is None else json.dumps(details, ensure_ascii=False, sort_keys=True)
    record = {
        'run_id': run_id,
        'step': step,
        'item_slug': item_slug or '',
        'status': status,
        'message': message,
        'details_json': details_json,
        'request_count': int(usage['request_count'] or 0),
        'prompt_tokens': int(usage['prompt_tokens'] or 0),
        'completion_tokens': int(usage['completion_tokens'] or 0),
        'total_tokens': int(usage['total_tokens'] or 0),
        'created_at': _json_timestamp(),
    }
    _append_json_record(json_run_logs_path(), record)
    return ''


def log_event(run_id, step, status, message, item_slug=None, details=None, request_count=None, prompt_tokens=None, completion_tokens=None, total_tokens=None):
    usage = normalize_usage_metrics(
        request_count=request_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        details=details,
    )
    backend = operational_storage_backend()
    failures = []
    if backend in {STORAGE_BACKEND_DATABASE, STORAGE_BACKEND_BOTH}:
        try:
            _store_log_event_in_database(run_id, step, status, message, item_slug=item_slug, details=details, usage=usage)
        except Exception as exc:
            if backend == STORAGE_BACKEND_DATABASE:
                raise
            failures.append(f'database: {exc}')
    if backend in {STORAGE_BACKEND_JSON, STORAGE_BACKEND_BOTH}:
        try:
            _store_log_event_in_json(run_id, step, status, message, item_slug=item_slug, details=details, usage=usage)
        except Exception as exc:
            if backend == STORAGE_BACKEND_JSON:
                raise
            failures.append(f'json: {exc}')
    if backend == STORAGE_BACKEND_BOTH and failures:
        if len(failures) == 2:
            raise RuntimeError('log_event failed for all configured backends: ' + '; '.join(failures))
        print('Agent log warning: partial mirror failure: ' + '; '.join(failures), file=sys.stderr)
    return ''


def safe_log_event(*args, **kwargs):
    try:
        log_event(*args, **kwargs)
        return True
    except Exception as exc:
        print(f'Agent log warning: {exc}', file=sys.stderr)
        return False


def _decode_b64(value):
    return base64.b64decode(value).decode('utf-8') if value else ''


def _sort_json_rows(rows):
    return sorted(
        rows,
        key=lambda row: (_safe_int(row.get('id')), row.get('created_at') or row.get('updated_at') or ''),
        reverse=True,
    )


def _normalize_json_log_row(row):
    details_json = row.get('details_json', '') if isinstance(row, dict) else ''
    if isinstance(details_json, (dict, list)):
        details_json = json.dumps(details_json, ensure_ascii=False, sort_keys=True)
    return {
        'id': _safe_int(row.get('id')),
        'run_id': str(row.get('run_id') or ''),
        'step': str(row.get('step') or ''),
        'item_slug': str(row.get('item_slug') or ''),
        'status': str(row.get('status') or ''),
        'message': str(row.get('message') or ''),
        'details_json': str(details_json or ''),
        'request_count': _safe_int(row.get('request_count')),
        'prompt_tokens': _safe_int(row.get('prompt_tokens')),
        'completion_tokens': _safe_int(row.get('completion_tokens')),
        'total_tokens': _safe_int(row.get('total_tokens')),
        'created_at': str(row.get('created_at') or ''),
    }


def _normalize_json_memory_row(row):
    return {
        'id': _safe_int(row.get('id')),
        'topic_slug': str(row.get('topic_slug') or ''),
        'category_name': str(row.get('category_name') or ''),
        'memory_key': str(row.get('memory_key') or ''),
        'verified_fact': str(row.get('verified_fact') or ''),
        'source_url': str(row.get('source_url') or ''),
        'confidence': str(row.get('confidence') or ''),
        'status': str(row.get('status') or 'active'),
        'created_at': str(row.get('created_at') or ''),
        'updated_at': str(row.get('updated_at') or row.get('created_at') or ''),
    }


def _blog_source_order():
    return ('json', 'database') if operational_storage_backend() == STORAGE_BACKEND_JSON else ('database', 'json')


def _blog_json_paths():
    configured = _first_env_value('AGENT_BLOGS_JSON_PATH', 'BLOG_JSON_PATH', 'BLOG_JSON_PATHS')
    bases = []
    if configured:
        for raw in configured.split(os.pathsep):
            text = str(raw or '').strip()
            if not text:
                continue
            candidate = Path(text).expanduser()
            if not candidate.is_absolute():
                candidate = json_storage_dir() / candidate
            bases.append(candidate.resolve())
    else:
        root = json_storage_dir()
        bases = [root, root / 'logs']

    paths = []
    seen = set()
    for base in bases:
        candidates = [base]
        if base.is_dir():
            candidates = [base / JSON_BLOGS_FILE_NAME, *sorted(base.glob('blog*.json'))]
        for candidate in candidates:
            path = Path(candidate).resolve()
            if not path.is_file():
                continue
            if path.name in {JSON_RUN_LOG_FILE_NAME, JSON_MEMORY_FILE_NAME}:
                continue
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def _normalize_json_blog_row(row, default_id=0):
    if not isinstance(row, dict):
        return None
    status = str(row.get('status') or 'active').strip().lower()
    if status and status not in {'active', 'published', 'live'}:
        return None
    summary = str(row.get('summary') or row.get('meta_description') or '').strip()
    content = str(row.get('content') or row.get('description') or '').strip()
    image_value = (
        row.get('image_url')
        or row.get('image')
        or row.get('thumbnail')
        or row.get('cover_image')
        or row.get('featured_image')
        or row.get('banner_image')
        or row.get('hero_image')
        or row.get('featuredImage')
        or ''
    )
    normalized = {
        'id': _safe_int(row.get('id'), default_id),
        'title': str(row.get('title') or row.get('blog_name') or '').strip(),
        'slug': str(row.get('slug') or '').strip(),
        'category_name': str(row.get('category_name') or row.get('category') or '').strip(),
        'summary': summary,
        'content': content,
        'image_url': str(image_value or '').strip(),
        'file_url': blog_master_file_public_url(row.get('file_url') or row.get('file') or ''),
        'source_url': str(row.get('source_url') or row.get('source') or '').strip(),
        'created_at': str(row.get('created_at') or row.get('updated_at') or '').strip(),
    }
    if not any([normalized['slug'], normalized['title'], normalized['file_url']]):
        return None
    return normalized


def _read_json_blog_rows():
    rows = []
    for path in _blog_json_paths():
        raw = path.read_text(encoding='utf-8').strip()
        if not raw:
            continue
        payload = json.loads(raw)
        if isinstance(payload, dict) and isinstance(payload.get('blogs'), list):
            entries = payload.get('blogs') or []
        elif isinstance(payload, list):
            entries = payload
        elif isinstance(payload, dict):
            entries = [payload]
        else:
            raise RuntimeError(f'unsupported blog JSON payload in {path}')
        for index, entry in enumerate(entries, start=1):
            normalized = _normalize_json_blog_row(entry, default_id=index)
            if normalized is not None:
                rows.append(normalized)
    return rows


def _sort_blog_rows(rows):
    return sorted(
        rows,
        key=lambda row: (str(row.get('created_at') or ''), _safe_int(row.get('id'))),
        reverse=True,
    )


def _blog_dedupe_key(row):
    slug = str(row.get('slug') or '').strip().lower()
    if slug:
        return f'slug:{slug}'
    file_url = str(row.get('file_url') or '').strip().lower()
    if file_url:
        return f'file:{file_url}'
    title = str(row.get('title') or '').strip().lower()
    if title:
        return f'title:{title}'
    return f"id:{_safe_int(row.get('id'))}"


def _merge_blog_rows(primary_rows, secondary_rows, limit=None):
    merged = []
    seen = set()
    for group in (_sort_blog_rows(primary_rows), _sort_blog_rows(secondary_rows)):
        for row in group:
            key = _blog_dedupe_key(row)
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    merged = _sort_blog_rows(merged)
    return merged[:int(limit)] if limit is not None else merged


def _fetch_latest_blogs_from_json(limit=8):
    return _sort_blog_rows(_read_json_blog_rows())[:int(limit)]


def _fetch_blog_detail_from_json(slug):
    wanted = str(slug or '').strip().lower()
    if not wanted:
        return None
    for row in _sort_blog_rows(_read_json_blog_rows()):
        if str(row.get('slug') or '').strip().lower() == wanted:
            return row
    return None


def _fetch_latest_blogs_from_database(limit=8):
    db = publish_db_name()
    blog_columns = _table_columns(db, 'blog_master')
    category_columns = _table_columns(db, 'blog_category')
    if not blog_columns or not category_columns:
        return []

    title_col = _pick_column(blog_columns, ['blog_name', 'title'])
    slug_col = _pick_column(blog_columns, ['slug'])
    summary_col = _pick_column(blog_columns, ['meta_description', 'summary', 'description'])
    image_col = _pick_column(blog_columns, ['image', 'thumbnail', 'cover_image', 'featured_image', 'banner_image', 'hero_image', 'featuredImage'])
    file_col = _pick_column(blog_columns, ['file'])
    category_name_col = _pick_column(category_columns, ['name', 'category_name'])
    category_fk_col = _pick_column(blog_columns, ['category_id'])
    category_pk_col = _pick_column(category_columns, ['id'])
    if not all([title_col, slug_col, category_name_col, category_fk_col, category_pk_col]):
        return []

    selects = [
        'bm.id',
        f"REPLACE(TO_BASE64({_blog_expr('bm', title_col)}), '\n', '')",
        f"REPLACE(TO_BASE64({_blog_expr('bm', slug_col)}), '\n', '')",
        f"REPLACE(TO_BASE64({_blog_expr('bc', category_name_col)}), '\n', '')",
        f"REPLACE(TO_BASE64({_blog_expr('bm', summary_col)}), '\n', '')" if summary_col else "''",
        f"REPLACE(TO_BASE64({_blog_expr('bm', image_col)}), '\n', '')" if image_col else "''",
        f"REPLACE(TO_BASE64({_blog_expr('bm', file_col)}), '\n', '')" if file_col else "''",
        _blog_datetime_expr('bm', blog_columns),
    ]
    active_filter = ""
    if 'status' in blog_columns:
        active_filter = "WHERE bm.status = 'active'"
    sql = f"""
USE `{db}`;
SELECT {', '.join(selects)}
FROM blog_master bm
LEFT JOIN blog_category bc ON bm.`{category_fk_col}` = bc.`{category_pk_col}`
{active_filter}
ORDER BY bm.id DESC
LIMIT {int(limit)};
"""
    rows = _query_rows(sql, 8)
    return [
        {
            'id': int(row[0] or 0),
            'title': _decode_b64(row[1]),
            'slug': _decode_b64(row[2]),
            'category_name': _decode_b64(row[3]),
            'summary': _decode_b64(row[4]),
            'image_url': _decode_b64(row[5]),
            'file_url': blog_master_file_public_url(_decode_b64(row[6])),
            'created_at': row[7],
        }
        for row in rows
    ]


def _fetch_blog_detail_from_database(slug):
    db = publish_db_name()
    blog_columns = _table_columns(db, 'blog_master')
    category_columns = _table_columns(db, 'blog_category')
    if not blog_columns or not category_columns:
        return None

    title_col = _pick_column(blog_columns, ['blog_name', 'title'])
    slug_col = _pick_column(blog_columns, ['slug'])
    summary_col = _pick_column(blog_columns, ['meta_description', 'summary', 'description'])
    content_col = _pick_column(blog_columns, ['description', 'content', 'blog_description'])
    image_col = _pick_column(blog_columns, ['image', 'thumbnail', 'cover_image', 'featured_image', 'banner_image', 'hero_image', 'featuredImage'])
    file_col = _pick_column(blog_columns, ['file'])
    source_col = _pick_column(blog_columns, ['source_url', 'source'])
    category_name_col = _pick_column(category_columns, ['name', 'category_name'])
    category_fk_col = _pick_column(blog_columns, ['category_id'])
    category_pk_col = _pick_column(category_columns, ['id'])
    if not all([title_col, slug_col, category_name_col, category_fk_col, category_pk_col]):
        return None

    selects = [
        'bm.id',
        f"REPLACE(TO_BASE64({_blog_expr('bm', title_col)}), '\n', '')",
        f"REPLACE(TO_BASE64({_blog_expr('bm', slug_col)}), '\n', '')",
        f"REPLACE(TO_BASE64({_blog_expr('bc', category_name_col)}), '\n', '')",
        f"REPLACE(TO_BASE64({_blog_expr('bm', summary_col)}), '\n', '')" if summary_col else "''",
        f"REPLACE(TO_BASE64({_blog_expr('bm', content_col)}), '\n', '')" if content_col else "''",
        f"REPLACE(TO_BASE64({_blog_expr('bm', image_col)}), '\n', '')" if image_col else "''",
        f"REPLACE(TO_BASE64({_blog_expr('bm', file_col)}), '\n', '')" if file_col else "''",
        f"REPLACE(TO_BASE64({_blog_expr('bm', source_col)}), '\n', '')" if source_col else "''",
        _blog_datetime_expr('bm', blog_columns),
    ]
    filters = [text_equals_expr(f"bm.`{slug_col}`", slug)]
    if 'status' in blog_columns:
        filters.append("bm.status = 'active'")
    sql = f"""
USE `{db}`;
SELECT {', '.join(selects)}
FROM blog_master bm
LEFT JOIN blog_category bc ON bm.`{category_fk_col}` = bc.`{category_pk_col}`
WHERE {' AND '.join(filters)}
ORDER BY bm.id DESC
LIMIT 1;
"""
    rows = _query_rows(sql, 10)
    if not rows:
        return None
    row = rows[0]
    return {
        'id': int(row[0] or 0),
        'title': _decode_b64(row[1]),
        'slug': _decode_b64(row[2]),
        'category_name': _decode_b64(row[3]),
        'summary': _decode_b64(row[4]),
        'content': _decode_b64(row[5]),
        'image_url': _decode_b64(row[6]),
        'file_url': blog_master_file_public_url(_decode_b64(row[7])),
        'source_url': _decode_b64(row[8]),
        'created_at': row[9],
    }


def _store_memory_fact_in_database(topic_slug, category_name, memory_key, verified_fact, source_url=None, confidence=None, status='active'):
    ensure_operational_tables()
    sql = f"""
USE `{operational_db_name()}`;
INSERT INTO agent_memory (topic_slug, category_name, memory_key, verified_fact, source_url, confidence, status)
VALUES (
  {text_expr(topic_slug)},
  {text_expr(category_name)},
  {text_expr(memory_key)},
  {text_expr(verified_fact)},
  {text_expr(source_url)},
  {text_expr(confidence)},
  {text_expr(status)}
);
"""
    return mysql(sql)


def _store_memory_fact_in_json(topic_slug, category_name, memory_key, verified_fact, source_url=None, confidence=None, status='active'):
    now = _json_timestamp()
    record = {
        'topic_slug': topic_slug or '',
        'category_name': category_name or '',
        'memory_key': memory_key,
        'verified_fact': verified_fact,
        'source_url': source_url or '',
        'confidence': confidence or '',
        'status': status or 'active',
        'created_at': now,
        'updated_at': now,
    }
    _append_json_record(json_memory_path(), record)
    return ''


def store_memory_fact(topic_slug, category_name, memory_key, verified_fact, source_url=None, confidence=None, status='active'):
    backend = operational_storage_backend()
    failures = []
    if backend in {STORAGE_BACKEND_DATABASE, STORAGE_BACKEND_BOTH}:
        try:
            _store_memory_fact_in_database(topic_slug, category_name, memory_key, verified_fact, source_url=source_url, confidence=confidence, status=status)
        except Exception as exc:
            if backend == STORAGE_BACKEND_DATABASE:
                raise
            failures.append(f'database: {exc}')
    if backend in {STORAGE_BACKEND_JSON, STORAGE_BACKEND_BOTH}:
        try:
            _store_memory_fact_in_json(topic_slug, category_name, memory_key, verified_fact, source_url=source_url, confidence=confidence, status=status)
        except Exception as exc:
            if backend == STORAGE_BACKEND_JSON:
                raise
            failures.append(f'json: {exc}')
    if backend == STORAGE_BACKEND_BOTH and failures:
        if len(failures) == 2:
            raise RuntimeError('store_memory_fact failed for all configured backends: ' + '; '.join(failures))
        print('Agent memory warning: partial mirror failure: ' + '; '.join(failures), file=sys.stderr)
    return ''


def _query_rows(sql, expected_cols, use_staging=None):
    output = mysql(sql, use_staging=use_staging)
    if not output:
        return []
    rows = []
    for line in output.splitlines():
        parts = line.split('\t')
        if len(parts) < expected_cols:
            parts += [''] * (expected_cols - len(parts))
        rows.append(parts[:expected_cols])
    return rows


def _pick_column(columns, names):
    for name in names:
        if name in columns:
            return name
    return None


def _blog_expr(alias, column_name):
    return f"COALESCE(CAST({alias}.`{column_name}` AS CHAR CHARACTER SET utf8mb4), '')"


def _blog_datetime_expr(alias, columns):
    expressions = []
    if 'createdAt' in columns:
        expressions.append(
            f"DATE_FORMAT(FROM_UNIXTIME(CASE WHEN {alias}.createdAt > 2000000000 "
            f"THEN {alias}.createdAt / 1000 ELSE {alias}.createdAt END), '%Y-%m-%d %H:%i:%s')"
        )
    if 'created_at' in columns:
        expressions.append(f"DATE_FORMAT({alias}.created_at, '%Y-%m-%d %H:%i:%s')")
    if 'updatedAt' in columns:
        expressions.append(
            f"DATE_FORMAT(FROM_UNIXTIME(CASE WHEN {alias}.updatedAt > 2000000000 "
            f"THEN {alias}.updatedAt / 1000 ELSE {alias}.updatedAt END), '%Y-%m-%d %H:%i:%s')"
        )
    if 'updated_at' in columns:
        expressions.append(f"DATE_FORMAT({alias}.updated_at, '%Y-%m-%d %H:%i:%s')")
    if expressions:
        return f"COALESCE({', '.join(expressions)})"
    return "''"


def fetch_latest_blogs(limit=8):
    limit = int(limit)
    source_order = _blog_source_order()
    rows_by_source = {'database': [], 'json': []}
    errors = []
    loaders = {
        'database': lambda: _fetch_latest_blogs_from_database(limit=limit),
        'json': lambda: _fetch_latest_blogs_from_json(limit=limit),
    }
    for source in source_order:
        try:
            rows_by_source[source] = loaders[source]()
        except Exception as exc:
            errors.append(f'{source}: {exc}')
    merged = _merge_blog_rows(
        rows_by_source[source_order[0]],
        rows_by_source[source_order[1]],
        limit=limit,
    )
    if merged or not errors:
        return merged
    raise RuntimeError('failed to load blogs: ' + '; '.join(errors))


def fetch_blog_detail(slug):
    wanted = str(slug or '').strip()
    if not wanted:
        return None
    errors = []
    loaders = {
        'database': lambda: _fetch_blog_detail_from_database(wanted),
        'json': lambda: _fetch_blog_detail_from_json(wanted),
    }
    for source in _blog_source_order():
        try:
            row = loaders[source]()
        except Exception as exc:
            errors.append(f'{source}: {exc}')
            continue
        if row is not None:
            return row
    if errors:
        raise RuntimeError('failed to load blog detail: ' + '; '.join(errors))
    return None


def fetch_memory_context(limit=50):
    backend = operational_storage_backend()
    if backend == STORAGE_BACKEND_JSON:
        rows = [
            _normalize_json_memory_row(row)
            for row in _read_json_records(json_memory_path())
            if isinstance(row, dict) and str(row.get('status') or 'active') == 'active'
        ]
        rows = _sort_json_rows(rows)[:int(limit)]
        return [
            {
                'topic_slug': row['topic_slug'],
                'category_name': row['category_name'],
                'memory_key': row['memory_key'],
                'verified_fact': row['verified_fact'],
                'source_url': row['source_url'],
                'confidence': row['confidence'],
            }
            for row in rows
        ]
    rows = _query_rows(
        f"USE `{operational_db_name()}`; SELECT topic_slug, category_name, memory_key, verified_fact, source_url, confidence FROM agent_memory WHERE status='active' ORDER BY id DESC LIMIT {int(limit)};",
        6,
    )
    return [
        {
            'topic_slug': row[0],
            'category_name': row[1],
            'memory_key': row[2],
            'verified_fact': row[3],
            'source_url': row[4],
            'confidence': row[5],
        }
        for row in rows
    ]


def _fetch_dashboard_snapshot_from_database(run_limit=20, log_limit=100, memory_limit=25, chart_day_limit=7, use_staging=None):
    db = operational_db_name(use_staging=use_staging)
    ensure_operational_tables(use_staging=use_staging)
    stats_rows = _query_rows(
        f"USE `{db}`; SELECT COUNT(*), COUNT(DISTINCT run_id), SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END), SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END), COALESCE(SUM(request_count), 0), COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0), COALESCE(SUM(total_tokens), 0) FROM agent_run_logs;",
        8,
        use_staging=use_staging,
    )
    memory_count_rows = _query_rows(f"USE `{db}`; SELECT COUNT(*) FROM agent_memory;", 1, use_staging=use_staging)
    run_rows = _query_rows(
        f"USE `{db}`; SELECT run_id, COUNT(*), SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END), SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END), COALESCE(SUM(request_count), 0), COALESCE(SUM(total_tokens), 0), DATE_FORMAT(MAX(created_at), '%Y-%m-%d %H:%i:%s') FROM agent_run_logs GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT {int(run_limit)};",
        7,
        use_staging=use_staging,
    )
    log_rows = _query_rows(
        f"USE `{db}`; SELECT id, run_id, step, COALESCE(item_slug, ''), status, REPLACE(TO_BASE64(COALESCE(message, '')), '\n', ''), REPLACE(TO_BASE64(COALESCE(CAST(details_json AS CHAR CHARACTER SET utf8mb4), '')), '\n', ''), request_count, prompt_tokens, completion_tokens, total_tokens, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') FROM agent_run_logs ORDER BY id DESC LIMIT {int(log_limit)};",
        12,
        use_staging=use_staging,
    )
    memory_rows = _query_rows(
        f"USE `{db}`; SELECT id, COALESCE(topic_slug, ''), COALESCE(category_name, ''), memory_key, REPLACE(TO_BASE64(verified_fact), '\n', ''), COALESCE(source_url, ''), COALESCE(confidence, ''), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') FROM agent_memory ORDER BY id DESC LIMIT {int(memory_limit)};",
        8,
        use_staging=use_staging,
    )
    activity_rows = _query_rows(
        f"USE `{db}`; SELECT day_label, total_count, success_count, error_count FROM (SELECT DATE_FORMAT(created_at, '%Y-%m-%d') AS day_label, COUNT(*) AS total_count, SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS success_count, SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END) AS error_count FROM agent_run_logs GROUP BY DATE(created_at) ORDER BY DATE(created_at) DESC LIMIT {int(chart_day_limit)}) daily ORDER BY day_label ASC;",
        4,
        use_staging=use_staging,
    )
    token_rows = _query_rows(
        f"USE `{db}`; SELECT day_label, request_count, prompt_tokens, completion_tokens, total_tokens FROM (SELECT DATE_FORMAT(created_at, '%Y-%m-%d') AS day_label, COALESCE(SUM(request_count), 0) AS request_count, COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, COALESCE(SUM(completion_tokens), 0) AS completion_tokens, COALESCE(SUM(total_tokens), 0) AS total_tokens FROM agent_run_logs GROUP BY DATE(created_at) ORDER BY DATE(created_at) DESC LIMIT {int(chart_day_limit)}) daily ORDER BY day_label ASC;",
        5,
        use_staging=use_staging,
    )
    stats = stats_rows[0] if stats_rows else ['0', '0', '0', '0', '0', '0', '0', '0']
    memory_count = memory_count_rows[0][0] if memory_count_rows else '0'
    return {
        'db_target': dashboard_target_info(data_source=DASHBOARD_SOURCE_DATABASE, use_staging=use_staging),
        'stats': {
            'total_events': int(stats[0] or 0),
            'total_runs': int(stats[1] or 0),
            'error_events': int(stats[2] or 0),
            'success_events': int(stats[3] or 0),
            'request_count': int(stats[4] or 0),
            'prompt_tokens': int(stats[5] or 0),
            'completion_tokens': int(stats[6] or 0),
            'total_tokens': int(stats[7] or 0),
            'memory_facts': int(memory_count or 0),
        },
        'runs': [
            {
                'run_id': row[0],
                'event_count': int(row[1] or 0),
                'success_count': int(row[2] or 0),
                'error_count': int(row[3] or 0),
                'request_count': int(row[4] or 0),
                'total_tokens': int(row[5] or 0),
                'last_seen': row[6],
            }
            for row in run_rows
        ],
        'logs': [
            {
                'id': int(row[0] or 0),
                'run_id': row[1],
                'step': row[2],
                'item_slug': row[3],
                'status': row[4],
                'message': _decode_b64(row[5]),
                'details_json': _decode_b64(row[6]),
                'request_count': int(row[7] or 0),
                'prompt_tokens': int(row[8] or 0),
                'completion_tokens': int(row[9] or 0),
                'total_tokens': int(row[10] or 0),
                'created_at': row[11],
            }
            for row in log_rows
        ],
        'memory': [
            {
                'id': int(row[0] or 0),
                'topic_slug': row[1],
                'category_name': row[2],
                'memory_key': row[3],
                'verified_fact': _decode_b64(row[4]),
                'source_url': row[5],
                'confidence': row[6],
                'created_at': row[7],
            }
            for row in memory_rows
        ],
        'charts': {
            'activity_by_day': [
                {
                    'label': row[0],
                    'total': int(row[1] or 0),
                    'success': int(row[2] or 0),
                    'error': int(row[3] or 0),
                }
                for row in activity_rows
            ],
            'tokens_by_day': [
                {
                    'label': row[0],
                    'request_count': int(row[1] or 0),
                    'prompt_tokens': int(row[2] or 0),
                    'completion_tokens': int(row[3] or 0),
                    'total_tokens': int(row[4] or 0),
                }
                for row in token_rows
            ],
        },
    }


def _fetch_dashboard_snapshot_from_json(run_limit=20, log_limit=100, memory_limit=25, chart_day_limit=7, use_staging=None):
    logs = [
        _normalize_json_log_row(row)
        for row in _read_json_records(json_run_logs_path())
        if isinstance(row, dict)
    ]
    memory = [
        _normalize_json_memory_row(row)
        for row in _read_json_records(json_memory_path())
        if isinstance(row, dict)
    ]
    logs_sorted = _sort_json_rows(logs)
    memory_sorted = _sort_json_rows(memory)

    runs_by_id = {}
    activity_by_day = {}
    tokens_by_day = {}
    for row in logs:
        run_id = row['run_id']
        bucket = runs_by_id.setdefault(
            run_id,
            {
                'run_id': run_id,
                'event_count': 0,
                'success_count': 0,
                'error_count': 0,
                'request_count': 0,
                'total_tokens': 0,
                'last_seen': '',
            },
        )
        bucket['event_count'] += 1
        bucket['success_count'] += int(row['status'] == 'SUCCESS')
        bucket['error_count'] += int(row['status'] == 'ERROR')
        bucket['request_count'] += row['request_count']
        bucket['total_tokens'] += row['total_tokens']
        if row['created_at'] > bucket['last_seen']:
            bucket['last_seen'] = row['created_at']

        day_label = row['created_at'][:10] if row['created_at'] else ''
        if day_label:
            activity = activity_by_day.setdefault(day_label, {'label': day_label, 'total': 0, 'success': 0, 'error': 0})
            activity['total'] += 1
            activity['success'] += int(row['status'] == 'SUCCESS')
            activity['error'] += int(row['status'] == 'ERROR')
            tokens = tokens_by_day.setdefault(
                day_label,
                {'label': day_label, 'request_count': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
            )
            tokens['request_count'] += row['request_count']
            tokens['prompt_tokens'] += row['prompt_tokens']
            tokens['completion_tokens'] += row['completion_tokens']
            tokens['total_tokens'] += row['total_tokens']

    ordered_days = sorted(activity_by_day)
    day_limit = int(chart_day_limit)
    selected_days = ordered_days[-day_limit:] if day_limit > 0 else ordered_days
    runs = sorted(runs_by_id.values(), key=lambda row: row['last_seen'], reverse=True)

    return {
        'db_target': dashboard_target_info(data_source=DASHBOARD_SOURCE_JSON, use_staging=use_staging),
        'stats': {
            'total_events': len(logs),
            'total_runs': len(runs_by_id),
            'error_events': sum(1 for row in logs if row['status'] == 'ERROR'),
            'success_events': sum(1 for row in logs if row['status'] == 'SUCCESS'),
            'request_count': sum(row['request_count'] for row in logs),
            'prompt_tokens': sum(row['prompt_tokens'] for row in logs),
            'completion_tokens': sum(row['completion_tokens'] for row in logs),
            'total_tokens': sum(row['total_tokens'] for row in logs),
            'memory_facts': len(memory),
        },
        'runs': runs[:int(run_limit)],
        'logs': logs_sorted[:int(log_limit)],
        'memory': memory_sorted[:int(memory_limit)],
        'charts': {
            'activity_by_day': [activity_by_day[day] for day in selected_days],
            'tokens_by_day': [tokens_by_day.get(day, {'label': day, 'request_count': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}) for day in selected_days],
        },
    }


def fetch_dashboard_snapshot(run_limit=20, log_limit=100, memory_limit=25, chart_day_limit=7, use_staging=None):
    if dashboard_data_source() == DASHBOARD_SOURCE_JSON:
        return _fetch_dashboard_snapshot_from_json(
            run_limit=run_limit,
            log_limit=log_limit,
            memory_limit=memory_limit,
            chart_day_limit=chart_day_limit,
            use_staging=use_staging,
        )
    return _fetch_dashboard_snapshot_from_database(
        run_limit=run_limit,
        log_limit=log_limit,
        memory_limit=memory_limit,
        chart_day_limit=chart_day_limit,
        use_staging=use_staging,
    )
