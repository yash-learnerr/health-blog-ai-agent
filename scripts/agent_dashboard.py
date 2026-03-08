#!/usr/bin/env python3
import argparse
import hashlib
import html
import hmac
import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
FRONTEND_DIR = REPO_ROOT / 'frontend'
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_db


def _env_flag(name, default=False):
    agent_db.load_env()
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def dashboard_login_config():
    agent_db.load_env()
    enabled = _env_flag('DASHBOARD_LOGIN_ENABLED', default=False)
    username = os.getenv('DASHBOARD_LOGIN_USERNAME', '')
    password = os.getenv('DASHBOARD_LOGIN_PASSWORD', '')
    secret = os.getenv('DASHBOARD_LOGIN_SECRET') or password
    return {'enabled': enabled, 'username': username, 'password': password, 'secret': secret}


def build_login_html(error=''):
    error_html = f"<div class='error'>{html.escape(error)}</div>" if error else ''
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Dashboard Login</title>
<style>
body{{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;min-height:100vh;display:grid;place-items:center;padding:24px}}.card{{width:100%;max-width:420px;background:#111827;border:1px solid #334155;border-radius:16px;padding:24px;box-sizing:border-box}}h1{{margin:0 0 12px}}p{{color:#94a3b8}}label{{display:block;margin:14px 0 6px}}input{{width:100%;padding:12px;border-radius:10px;border:1px solid #475569;background:#0b1220;color:#e2e8f0;box-sizing:border-box}}button{{margin-top:16px;width:100%;padding:12px;border:0;border-radius:10px;background:#2563eb;color:#fff;font-weight:700;cursor:pointer}}.error{{background:#7f1d1d;border:1px solid #ef4444;padding:12px;border-radius:12px;margin:0 0 16px}}
</style></head><body><div class='card'><h1>AI Agent Dashboard</h1><p>Sign in to view the live dashboard.</p>{error_html}<form method='post' action='/login'><label for='username'>Username</label><input id='username' name='username' autocomplete='username' required><label for='password'>Password</label><input id='password' type='password' name='password' autocomplete='current-password' required><button type='submit'>Login</button></form></div></body></html>"""


def _session_signature(username, secret):
    return hmac.new(secret.encode('utf-8'), username.encode('utf-8'), hashlib.sha256).hexdigest()


def build_session_cookie(username, secret):
    return f"{username}:{_session_signature(username, secret)}"


def is_authenticated(cookie_header, config=None):
    config = config or dashboard_login_config()
    if not config.get('enabled'):
        return True
    secret = config.get('secret') or ''
    username = config.get('username') or ''
    if not cookie_header or not secret or not username:
        return False
    cookies = {}
    for chunk in cookie_header.split(';'):
        if '=' in chunk:
            key, value = chunk.strip().split('=', 1)
            cookies[key] = value
    session = cookies.get('dashboard_session', '')
    if ':' not in session:
        return False
    session_username, signature = session.split(':', 1)
    expected = _session_signature(username, secret)
    return session_username == username and hmac.compare_digest(signature, expected)


def _format_number(value):
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def _chart_svg(points, series, height=220):
    labels = [point.get('label', '') for point in points] or ['No data']
    max_value = max((point.get(key, 0) for point in points for key, _label, _color in series), default=0) or 1
    bar_group_width = 70
    chart_width = max(520, len(labels) * bar_group_width + 80)
    chart_height = height
    plot_height = height - 70
    plot_bottom = height - 34
    plot_top = 20
    left = 52
    right = chart_width - 16
    inner_width = max(1, right - left)
    group_width = inner_width / max(1, len(labels))
    bar_width = max(10, min(22, (group_width - 12) / max(1, len(series))))
    grid = ''.join(
        f"<line x1='{left}' y1='{y}' x2='{right}' y2='{y}' stroke='#334155' stroke-width='1' />"
        for y in [plot_top, plot_top + plot_height * 0.25, plot_top + plot_height * 0.5, plot_top + plot_height * 0.75, plot_bottom]
    )
    bars = []
    for index, point in enumerate(points or [{'label': 'No data'}]):
        group_x = left + index * group_width + 8
        label = html.escape(point.get('label', ''))
        bars.append(f"<text x='{group_x + group_width / 2 - 8}' y='{chart_height - 10}' fill='#94a3b8' font-size='11'>{label}</text>")
        for series_index, (key, legend_label, color) in enumerate(series):
            value = int(point.get(key, 0) or 0)
            bar_height = 0 if value <= 0 else max(2, (value / max_value) * (plot_height - 10))
            x = group_x + series_index * (bar_width + 4)
            y = plot_bottom - bar_height
            bars.append(
                f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_width:.1f}' height='{bar_height:.1f}' rx='4' fill='{color}'>"
                f"<title>{html.escape(legend_label)}: {_format_number(value)}</title></rect>"
            )
    legend = ''.join(
        f"<span class='legend-item'><span class='legend-dot' style='background:{color}'></span>{html.escape(label)}</span>"
        for _key, label, color in series
    )
    return (
        f"<div class='chart-legend'>{legend}</div>"
        f"<svg viewBox='0 0 {chart_width} {chart_height}' class='chart-svg' role='img' aria-label='chart'>"
        f"{grid}{''.join(bars)}</svg>"
    )


def build_dashboard_html(snapshot=None, error=None, show_logout=False):
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')
    db_target = snapshot.get('db_target', {}) if snapshot else {}
    stats = snapshot.get('stats', {}) if snapshot else {}
    runs = snapshot.get('runs', []) if snapshot else []
    logs = snapshot.get('logs', []) if snapshot else []
    memory = snapshot.get('memory', []) if snapshot else []
    charts = snapshot.get('charts', {}) if snapshot else {}
    cards = [
        ('Total events', stats.get('total_events', 0)),
        ('Runs', stats.get('total_runs', 0)),
        ('Requests', stats.get('request_count', 0)),
        ('Errors', stats.get('error_events', 0)),
        ('Success events', stats.get('success_events', 0)),
        ('Prompt tokens', stats.get('prompt_tokens', 0)),
        ('Completion tokens', stats.get('completion_tokens', 0)),
        ('Total tokens', stats.get('total_tokens', 0)),
        ('Memory facts', stats.get('memory_facts', 0)),
    ]
    card_html = ''.join(f"<div class='card'><h3>{html.escape(label)}</h3><strong>{_format_number(value)}</strong></div>" for label, value in cards)
    activity_chart_html = _chart_svg(
        charts.get('activity_by_day', []),
        [('total', 'Total events', '#38bdf8'), ('success', 'Success', '#22c55e'), ('error', 'Error', '#ef4444')],
    )
    token_chart_html = _chart_svg(
        charts.get('tokens_by_day', []),
        [('request_count', 'Requests', '#a78bfa'), ('prompt_tokens', 'Prompt tokens', '#f59e0b'), ('completion_tokens', 'Completion tokens', '#10b981'), ('total_tokens', 'Total tokens', '#60a5fa')],
        height=240,
    )
    run_rows = ''.join(
        f"<tr><td>{html.escape(row['run_id'])}</td><td>{row['event_count']}</td><td>{row['success_count']}</td><td>{row['error_count']}</td><td>{row['request_count']}</td><td>{_format_number(row['total_tokens'])}</td><td>{html.escape(row['last_seen'])}</td></tr>"
        for row in runs
    ) or "<tr><td colspan='7'>No run data yet.</td></tr>"
    log_rows = ''.join(
        f"<tr><td>{row['id']}</td><td>{html.escape(row['created_at'])}</td><td>{html.escape(row['run_id'])}</td><td>{html.escape(row['step'])}</td><td>{html.escape(row['status'])}</td><td>{html.escape(row['item_slug'])}</td><td>{row['request_count']}</td><td>{_format_number(row['total_tokens'])}</td><td>{html.escape(row['message'])}<details><summary>details</summary><pre>{html.escape(row['details_json'] or '{}')}</pre></details></td></tr>"
        for row in logs
    ) or "<tr><td colspan='9'>No log data yet.</td></tr>"
    memory_rows = ''.join(
        f"<tr><td>{row['id']}</td><td>{html.escape(row['topic_slug'])}</td><td>{html.escape(row['category_name'])}</td><td>{html.escape(row['memory_key'])}</td><td>{html.escape(row['confidence'])}</td><td>{html.escape(row['verified_fact'])}</td></tr>"
        for row in memory
    ) or "<tr><td colspan='6'>No memory facts yet.</td></tr>"
    db_mode = html.escape(db_target.get('mode', 'Unknown'))
    status_label = html.escape(db_target.get('status_label', f'{db_mode} database'))
    source_label = html.escape(db_target.get('source_label', 'AGENT_DB_NAME.agent_run_logs and AGENT_DB_NAME.agent_memory'))
    db_host = html.escape(db_target.get('host', ''))
    host_label = html.escape(db_target.get('host_label', 'Host'))
    publish_db_name = html.escape(db_target.get('publish_db_name', ''))
    agent_db_name = html.escape(db_target.get('agent_db_name', ''))
    agent_label = html.escape(db_target.get('agent_label', 'Agent DB'))
    status_class = html.escape(db_target.get('source_kind', db_mode.lower()))
    error_html = f"<div class='error'>{html.escape(error)}</div>" if error else ''
    logout_html = "<a href='/logout'>Logout</a>" if show_logout else ''
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>AI Agent Dashboard</title>
<style>
body{{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}h1,h2,h3{{margin:0 0 12px}}.muted{{color:#94a3b8}}.small{{font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0 24px}}.card{{background:#111827;border:1px solid #334155;border-radius:12px;padding:16px}}table{{width:100%;border-collapse:collapse;background:#111827;border-radius:12px;overflow:hidden}}th,td{{border:1px solid #334155;padding:10px;text-align:left;vertical-align:top}}section{{margin-top:24px}}pre{{white-space:pre-wrap;word-break:break-word;margin:8px 0 0}}details summary{{cursor:pointer;color:#93c5fd}}.error{{background:#7f1d1d;border:1px solid #ef4444;padding:12px;border-radius:12px;margin:16px 0}}.two-col{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}.chart-svg{{width:100%;height:auto;background:#0b1220;border-radius:12px;border:1px solid #334155}}.chart-legend{{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 10px}}.legend-item{{display:flex;align-items:center;gap:6px;color:#cbd5e1;font-size:13px}}.legend-dot{{width:10px;height:10px;border-radius:999px;display:inline-block}}.status-banner{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:14px 0 6px}}.status-pill{{display:inline-block;padding:6px 12px;border-radius:999px;font-weight:700}}.status-pill.staging{{background:#14532d;color:#dcfce7;border:1px solid #22c55e}}.status-pill.local{{background:#1e3a8a;color:#dbeafe;border:1px solid #60a5fa}}.status-pill.production{{background:#7c2d12;color:#ffedd5;border:1px solid #fb923c}}.status-pill.json{{background:#312e81;color:#e0e7ff;border:1px solid #818cf8}}.status-pill.database{{background:#334155;color:#e2e8f0;border:1px solid #64748b}}.topbar{{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}}a{{color:#93c5fd}}
</style></head><body>
<div class='topbar'>
<h1>AI Agent Dashboard</h1>
{logout_html}
</div>
<p class='muted'>Source of truth: <code>{source_label}</code>. Generated at {generated_at}.</p>
<div class='status-banner'><span class='status-pill {status_class}'>{status_label}</span><span class='muted'>{host_label}: <code>{db_host}</code></span><span class='muted'>Publish DB: <code>{publish_db_name}</code></span><span class='muted'>{agent_label}: <code>{agent_db_name}</code></span></div>
{error_html}
<div class='grid'>{card_html}</div>
<section><h2>Dashboard graphs</h2><div class='two-col'><div class='card'><h3>Activity by day</h3>{activity_chart_html}</div><div class='card'><h3>Token usage by day</h3>{token_chart_html}</div></div></section>
<section><h2>Recent runs</h2><table><thead><tr><th>Run ID</th><th>Events</th><th>Success</th><th>Error</th><th>Requests</th><th>Total tokens</th><th>Last seen</th></tr></thead><tbody>{run_rows}</tbody></table></section>
<section><h2>Recent agent activity</h2><table><thead><tr><th>ID</th><th>Created</th><th>Run ID</th><th>Step</th><th>Status</th><th>Item</th><th>Requests</th><th>Total tokens</th><th>Message</th></tr></thead><tbody>{log_rows}</tbody></table></section>
<section><h2>Recent memory facts</h2><table><thead><tr><th>ID</th><th>Topic</th><th>Category</th><th>Key</th><th>Confidence</th><th>Fact</th></tr></thead><tbody>{memory_rows}</tbody></table></section>
</body></html>"""


def generate_dashboard_html(run_limit, log_limit, memory_limit, chart_day_limit=7, show_logout=False):
    try:
        snapshot = agent_db.fetch_dashboard_snapshot(run_limit=run_limit, log_limit=log_limit, memory_limit=memory_limit, chart_day_limit=chart_day_limit)
        return build_dashboard_html(snapshot=snapshot, show_logout=show_logout)
    except Exception as exc:
        return build_dashboard_html(error=str(exc), show_logout=show_logout)


def fetch_dashboard_api_payload(run_limit, log_limit, memory_limit, chart_day_limit=7):
    snapshot = agent_db.fetch_dashboard_snapshot(
        run_limit=run_limit,
        log_limit=log_limit,
        memory_limit=memory_limit,
        chart_day_limit=chart_day_limit,
    )
    return {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ'),
        'snapshot': snapshot,
    }


def fetch_blogs_api_payload(limit=12):
    return {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ'),
        'db_target': agent_db.db_target_info(),
        'blogs': agent_db.fetch_latest_blogs(limit=limit),
    }


def fetch_blog_detail_api_payload(slug):
    blog = agent_db.fetch_blog_detail(slug)
    if blog is None:
        raise KeyError(slug)
    return {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ'),
        'db_target': agent_db.db_target_info(),
        'blog': blog,
    }


def frontend_asset_path(request_path):
    parsed = urlparse(request_path)
    raw_path = parsed.path
    if raw_path in {'/', '/index.html'}:
        relative = 'index.html'
    elif raw_path.startswith('/frontend/'):
        relative = raw_path[len('/frontend/'):]
    else:
        return None
    candidate = (FRONTEND_DIR / relative).resolve()
    try:
        candidate.relative_to(FRONTEND_DIR.resolve())
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def write_dashboard(output_path, run_limit, log_limit, memory_limit, chart_day_limit):
    html_text = generate_dashboard_html(run_limit, log_limit, memory_limit, chart_day_limit)
    Path(output_path).write_text(html_text, encoding='utf-8')
    print(f'Dashboard written to {output_path}')


def serve_dashboard(host, port, run_limit, log_limit, memory_limit, chart_day_limit):
    login_config = dashboard_login_config()

    class Handler(BaseHTTPRequestHandler):
        def _send_html(self, html_text, status=200, extra_headers=None):
            payload = html_text.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            for key, value in extra_headers or []:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path):
            body = path.read_bytes()
            content_type, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header('Content-Type', content_type or 'application/octet-stream')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location, extra_headers=None):
            self.send_response(302)
            self.send_header('Location', location)
            for key, value in extra_headers or []:
                self.send_header(key, value)
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == '/api/dashboard':
                try:
                    payload = fetch_dashboard_api_payload(run_limit, log_limit, memory_limit, chart_day_limit)
                except Exception as exc:
                    return self._send_json({'error': str(exc)}, status=500)
                return self._send_json(payload)
            if parsed.path == '/api/blogs':
                params = parse_qs(parsed.query)
                blog_limit = int((params.get('limit') or ['12'])[0])
                try:
                    payload = fetch_blogs_api_payload(limit=blog_limit)
                except Exception as exc:
                    return self._send_json({'error': str(exc)}, status=500)
                return self._send_json(payload)
            if parsed.path == '/api/blog':
                params = parse_qs(parsed.query)
                slug = (params.get('slug') or [''])[0].strip()
                if not slug:
                    return self._send_json({'error': 'Missing slug parameter.'}, status=400)
                try:
                    payload = fetch_blog_detail_api_payload(slug)
                except KeyError:
                    return self._send_json({'error': 'Blog not found.'}, status=404)
                except Exception as exc:
                    return self._send_json({'error': str(exc)}, status=500)
                return self._send_json(payload)
            if login_config.get('enabled'):
                if parsed.path == '/login':
                    return self._send_html(build_login_html())
                if parsed.path == '/logout':
                    return self._redirect('/login', [('Set-Cookie', 'dashboard_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0')])
                if not is_authenticated(self.headers.get('Cookie', ''), login_config):
                    return self._redirect('/login')
            asset = frontend_asset_path(self.path)
            if asset is not None:
                return self._send_file(asset)
            if parsed.path == '/legacy':
                html_text = generate_dashboard_html(run_limit, log_limit, memory_limit, chart_day_limit, show_logout=login_config.get('enabled'))
                return self._send_html(html_text, extra_headers=[])
            self._send_html('Not found', status=404)

        def do_POST(self):
            if self.path != '/login' or not login_config.get('enabled'):
                return self._send_html('Not found', status=404)
            length = int(self.headers.get('Content-Length', '0') or 0)
            raw_body = self.rfile.read(length).decode('utf-8') if length > 0 else ''
            form = parse_qs(raw_body)
            username = (form.get('username') or [''])[0]
            password = (form.get('password') or [''])[0]
            if username == login_config.get('username') and password == login_config.get('password'):
                cookie = build_session_cookie(username, login_config.get('secret') or '')
                return self._redirect('/', [('Set-Cookie', f'dashboard_session={cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800')])
            return self._send_html(build_login_html('Invalid username or password.'), status=401)

        def log_message(self, fmt, *args):
            return

    server = HTTPServer((host, port), Handler)
    print(f'AI Agent Dashboard serving at http://{host}:{port}')
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description='Render or serve an AI Agent dashboard from the configured operational data source.')
    parser.add_argument('--output', default='frontend/dashboard.html', help='HTML file to generate when not using --serve')
    parser.add_argument('--serve', action='store_true', help='Serve the dashboard over HTTP instead of writing a file')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--run-limit', type=int, default=20)
    parser.add_argument('--log-limit', type=int, default=100)
    parser.add_argument('--memory-limit', type=int, default=25)
    parser.add_argument('--chart-day-limit', type=int, default=7)
    args = parser.parse_args()
    if args.serve:
        serve_dashboard(args.host, args.port, args.run_limit, args.log_limit, args.memory_limit, args.chart_day_limit)
        return 0
    write_dashboard(args.output, args.run_limit, args.log_limit, args.memory_limit, args.chart_day_limit)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
